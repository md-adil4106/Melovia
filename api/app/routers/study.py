"""Study Mode API router for double-blind A/B evaluation (Phase 15).

Security & Architecture Constraints:
- Purely double-blind: zero leakage of recommendation arm (Hybrid vs Baseline) to the client.
- Strict token protection on admin CSV export (STUDY_ADMIN_TOKEN).
- Zero PII: only anonymous hashed device identifier recorded.
- Graceful database degradation: caches ratings in-memory if DB is unavailable.
"""

import csv
import io
import logging
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import StudyRating
from app.db.session import get_db_session
from app.errors import AppException
from app.recsys import (
    CandidateFilters,
    CatalogStore,
    RecsysConfig,
    build_modes,
    generate_candidates,
    genre_baseline,
    rerank_candidates,
    score_candidates,
)
from app.routers.cookies import get_or_create_device_id
from app.schemas.study import (
    StudyRatingRequest,
    StudyRatingResponse,
    StudySeedTrack,
    StudySessionResponse,
    StudySessionTrack,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study", tags=["study"])

# In-memory trial arm cache to unblind ratings on submission
# session_id -> { "seed_set_id": str, "arm_order": str,
#                  "playlist_a_arm": str, "playlist_b_arm": str, "created_at": datetime }
_active_trials: dict[str, dict[str, Any]] = {}

# In-memory fallback for ratings if database operations degrade
_memory_ratings: list[dict[str, Any]] = []

# Cached seed sets from yaml
_cached_seed_sets: list[dict[str, Any]] = []


def _load_study_seedsets() -> list[dict[str, Any]]:
    """Loads pre-configured seed sets from eval/seedsets.yaml or returns built-in presets."""
    global _cached_seed_sets
    if _cached_seed_sets:
        return _cached_seed_sets

    potential_paths = [
        Path(__file__).resolve().parents[3] / "eval" / "seedsets.yaml",
        Path("eval/seedsets.yaml"),
        Path("../eval/seedsets.yaml"),
    ]

    for p in potential_paths:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    sets = data.get("seed_sets", [])
                    if sets:
                        _cached_seed_sets = sets
                        return _cached_seed_sets
            except Exception as e:
                logger.warning("Failed to parse %s: %s", p, e)

    # Built-in fallback presets using shipping catalog tracks
    _cached_seed_sets = [
        {
            "id": "study_seedset_ambient",
            "name": "Ambient Focus & Texture",
            "seed_track_ids": [
                "b7ac542c-1b90-550d-a778-f94510231bd5",
                "c73dc950-5de6-54c7-8fb6-2d8c095521ef",
            ],
        },
        {
            "id": "study_seedset_electronic",
            "name": "Electronic & Pulse Horizon",
            "seed_track_ids": [
                "e6e33bfb-d1c8-52c4-b400-09b91558864b",
                "9558a519-9578-5a1e-bf33-0e61c9c274b4",
            ],
        },
        {
            "id": "study_seedset_drift",
            "name": "Cosmic Drift & Paradox",
            "seed_track_ids": [
                "f312f449-e24b-5b91-83a4-69c6e61ff5b1",
                "ee84d0a1-0a12-5973-9b4e-de6a9635b586",
            ],
        },
    ]
    return _cached_seed_sets


@router.get(
    "/session",
    response_model=StudySessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a double-blind A/B evaluation trial session",
    description=(
        "Returns reference seed tracks and two anonymized candidate playlists "
        "(Playlist A vs Playlist B). The assignment of System Hybrid vs Baseline "
        "is strictly randomized and concealed from client output."
    ),
)
async def get_study_session(
    request: Request,
    response: Response,
    seed_set_id: str | None = Query(None, description="Optional seed set ID to evaluate"),
) -> StudySessionResponse:
    catalog: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    _, _ = get_or_create_device_id(request, response)
    seedsets = _load_study_seedsets()

    selected_set: dict[str, Any] | None = None
    if seed_set_id:
        for s in seedsets:
            if s.get("id") == seed_set_id:
                selected_set = s
                break

    if not selected_set:
        selected_set = random.choice(seedsets)

    raw_seed_ids: list[str] = selected_set.get("seed_track_ids", [])
    valid_seed_ids = [sid for sid in raw_seed_ids if catalog.contains_id(sid)]

    if not valid_seed_ids:
        # Fallback to first available catalog tracks
        valid_seed_ids = [catalog.get_id(0), catalog.get_id(1)]

    # 1. Generate Hybrid Playlist (system pipeline)
    config = RecsysConfig()
    modes = build_modes(valid_seed_ids, catalog, config)
    candidates = generate_candidates(
        modes=modes,
        catalog=catalog,
        filters=CandidateFilters(excluded_track_ids=set(valid_seed_ids)),
        k_per_mode=config.k_candidates,
    )
    scored = score_candidates(candidates, catalog, config=config)
    reranked = rerank_candidates(
        pool=candidates,
        scored_list=scored,
        catalog=catalog,
        discovery=0.35,
        n=12,
        config=config,
    )
    hybrid_indices = [item.track_idx for item in reranked.items]
    hybrid_tracks = [catalog.get_track_dict(idx) for idx in hybrid_indices]

    # 2. Generate Baseline Playlist (genre / folksonomy tag overlap)
    baseline_tracks = genre_baseline(valid_seed_ids, catalog, n=12)

    # 3. Double-blind random assignment (coin flip)
    is_hybrid_a = random.random() < 0.5
    session_id = str(uuid.uuid4())

    if is_hybrid_a:
        playlist_a_raw = hybrid_tracks
        playlist_b_raw = baseline_tracks
        arm_order = "hybrid_first"
        playlist_a_arm = "hybrid"
        playlist_b_arm = "baseline"
    else:
        playlist_a_raw = baseline_tracks
        playlist_b_raw = hybrid_tracks
        arm_order = "baseline_first"
        playlist_a_arm = "baseline"
        playlist_b_arm = "hybrid"

    # Store mapping in server memory cache
    _active_trials[session_id] = {
        "seed_set_id": selected_set.get("id", "custom"),
        "arm_order": arm_order,
        "playlist_a_arm": playlist_a_arm,
        "playlist_b_arm": playlist_b_arm,
        "created_at": datetime.now(UTC),
    }

    # Format seed tracks
    seed_track_models: list[StudySeedTrack] = []
    for sid in valid_seed_ids:
        idx = catalog.get_idx(sid)
        td = catalog.get_track_dict(idx)
        seed_track_models.append(
            StudySeedTrack(
                id=td["id"],
                track_idx=td["track_idx"],
                title=td["title"],
                artist_name=td["artist_name"],
                year=td.get("year"),
            )
        )

    # Format blind playlist items (strictly stripped of signals, ranks, or discovery scores)
    def _to_blind_track(td: dict[str, Any]) -> StudySessionTrack:
        return StudySessionTrack(
            id=td["id"],
            track_idx=td["track_idx"],
            title=td["title"],
            artist_name=td["artist_name"],
            year=td.get("year"),
            popularity_pct=float(td.get("popularity_pct", 50.0)),
            tags=td.get("tags") or [],
        )

    return StudySessionResponse(
        session_id=session_id,
        seed_set_id=selected_set.get("id", "custom"),
        seed_set_name=selected_set.get("name", "Curated Selection"),
        seed_tracks=seed_track_models,
        playlist_a=[_to_blind_track(t) for t in playlist_a_raw],
        playlist_b=[_to_blind_track(t) for t in playlist_b_raw],
    )


@router.post(
    "/rate",
    response_model=StudyRatingResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit participant ratings for blind study playlists",
    description=(
        "Validates Likert scores (1-5), unblinds arms server-side, and stores evaluation record."
    ),
)
async def submit_study_rating(
    payload: StudyRatingRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> StudyRatingResponse:
    _, device_hash = get_or_create_device_id(request, response)

    trial_info = _active_trials.get(payload.session_id)
    if not trial_info:
        # Fallback if server restarted during session: assign neutral arm mapping
        trial_info = {
            "seed_set_id": "unknown_session",
            "arm_order": "hybrid_first",
            "playlist_a_arm": "hybrid",
            "playlist_b_arm": "baseline",
            "created_at": datetime.now(UTC),
        }

    arm_order = trial_info["arm_order"]
    playlist_a_arm = trial_info["playlist_a_arm"]
    playlist_b_arm = trial_info["playlist_b_arm"]
    seed_set_id = trial_info["seed_set_id"]

    rating_id = str(uuid.uuid4())
    created_at = datetime.now(UTC)

    # Persist to database (with graceful fallback to in-memory store if DB is offline)
    try:
        db_rating = StudyRating(
            id=rating_id,
            session_id=payload.session_id,
            participant_id=device_hash,
            seed_set_id=seed_set_id,
            arm_order=arm_order,
            playlist_a_arm=playlist_a_arm,
            playlist_b_arm=playlist_b_arm,
            relevance_a=payload.relevance_a,
            discovery_a=payload.discovery_a,
            flow_a=payload.flow_a,
            satisfaction_a=payload.satisfaction_a,
            relevance_b=payload.relevance_b,
            discovery_b=payload.discovery_b,
            flow_b=payload.flow_b,
            satisfaction_b=payload.satisfaction_b,
            preferred_overall=payload.preferred_overall,
            feedback_text=payload.feedback_text,
            created_at=created_at,
        )
        db.add(db_rating)
        await db.commit()
    except Exception as e:
        logger.warning(
            "Failed to save study rating to DB; falling back to in-memory log: %s",
            e,
            extra={"request_id": getattr(request.state, "request_id", "-")},
        )
        try:
            await db.rollback()
        except Exception:
            pass

        _memory_ratings.append(
            {
                "id": rating_id,
                "session_id": payload.session_id,
                "participant_id": device_hash,
                "seed_set_id": seed_set_id,
                "arm_order": arm_order,
                "playlist_a_arm": playlist_a_arm,
                "playlist_b_arm": playlist_b_arm,
                "relevance_a": payload.relevance_a,
                "discovery_a": payload.discovery_a,
                "flow_a": payload.flow_a,
                "satisfaction_a": payload.satisfaction_a,
                "relevance_b": payload.relevance_b,
                "discovery_b": payload.discovery_b,
                "flow_b": payload.flow_b,
                "satisfaction_b": payload.satisfaction_b,
                "preferred_overall": payload.preferred_overall,
                "feedback_text": payload.feedback_text,
                "created_at": created_at,
            }
        )

    logger.info(
        "Recorded study rating: rating_id=%s, arm_order=%s, pref=%s",
        rating_id,
        arm_order,
        payload.preferred_overall,
    )

    return StudyRatingResponse(
        status="ok",
        message="Thank you! Your ratings have been recorded.",
        rating_id=rating_id,
    )


@router.get(
    "/export",
    summary="Export all unblinded study ratings as CSV for statistical analysis",
    description=("Protected by STUDY_ADMIN_TOKEN. Returns zero PII, only unblinded evaluations."),
)
async def export_study_ratings(
    token: str | None = Query(None, description="Admin secret token"),
    authorization: str | None = Header(None),
    x_study_admin_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    settings = get_settings()
    expected_token = settings.STUDY_ADMIN_TOKEN

    provided_token = token or x_study_admin_token
    if not provided_token and authorization:
        if authorization.startswith("Bearer "):
            provided_token = authorization.split("Bearer ", 1)[1].strip()

    if not provided_token or provided_token != expected_token:
        raise AppException(
            code="UNAUTHORIZED",
            message="Invalid or missing admin study export token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 1. Fetch ratings from database
    db_items: list[StudyRating] = []
    try:
        stmt = select(StudyRating).order_by(StudyRating.created_at.asc())
        res = await db.execute(stmt)
        db_items = list(res.scalars().all())
    except Exception as e:
        logger.warning("Could not load study ratings from DB (using in-memory): %s", e)

    # 2. Combine with memory items
    all_records: list[dict[str, Any]] = []
    seen_ids = set()

    for item in db_items:
        seen_ids.add(item.id)
        all_records.append(
            {
                "id": item.id,
                "session_id": item.session_id,
                "participant_id": item.participant_id,
                "seed_set_id": item.seed_set_id,
                "arm_order": item.arm_order,
                "playlist_a_arm": item.playlist_a_arm,
                "playlist_b_arm": item.playlist_b_arm,
                "relevance_a": item.relevance_a,
                "discovery_a": item.discovery_a,
                "flow_a": item.flow_a,
                "satisfaction_a": item.satisfaction_a,
                "relevance_b": item.relevance_b,
                "discovery_b": item.discovery_b,
                "flow_b": item.flow_b,
                "satisfaction_b": item.satisfaction_b,
                "preferred_overall": item.preferred_overall,
                "feedback_text": item.feedback_text,
                "created_at": item.created_at.isoformat() if item.created_at else "",
            }
        )

    for m_item in _memory_ratings:
        if m_item["id"] not in seen_ids:
            all_records.append(
                {
                    **m_item,
                    "created_at": (
                        m_item["created_at"].isoformat()
                        if isinstance(m_item["created_at"], datetime)
                        else str(m_item["created_at"])
                    ),
                }
            )

    # 3. Format CSV with unblinded hybrid vs baseline columns
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "rating_id",
            "session_id",
            "participant_id",
            "seed_set_id",
            "arm_order",
            "relevance_hybrid",
            "discovery_hybrid",
            "flow_hybrid",
            "satisfaction_hybrid",
            "relevance_baseline",
            "discovery_baseline",
            "flow_baseline",
            "satisfaction_baseline",
            "preferred_overall_arm",
            "feedback_text",
            "created_at",
        ]
    )

    for r in all_records:
        if r["playlist_a_arm"] == "hybrid":
            rel_h, disc_h, flow_h, sat_h = (
                r["relevance_a"],
                r["discovery_a"],
                r["flow_a"],
                r["satisfaction_a"],
            )
            rel_b, disc_b, flow_b, sat_b = (
                r["relevance_b"],
                r["discovery_b"],
                r["flow_b"],
                r["satisfaction_b"],
            )
            pref_arm = (
                "hybrid"
                if r["preferred_overall"] == "playlist_a"
                else ("baseline" if r["preferred_overall"] == "playlist_b" else "tie")
            )
        else:
            rel_h, disc_h, flow_h, sat_h = (
                r["relevance_b"],
                r["discovery_b"],
                r["flow_b"],
                r["satisfaction_b"],
            )
            rel_b, disc_b, flow_b, sat_b = (
                r["relevance_a"],
                r["discovery_a"],
                r["flow_a"],
                r["satisfaction_a"],
            )
            pref_arm = (
                "baseline"
                if r["preferred_overall"] == "playlist_a"
                else ("hybrid" if r["preferred_overall"] == "playlist_b" else "tie")
            )

        clean_feedback = (r.get("feedback_text") or "").replace("\n", " ").strip()
        writer.writerow(
            [
                r["id"],
                r["session_id"],
                r.get("participant_id") or "",
                r.get("seed_set_id") or "",
                r["arm_order"],
                rel_h,
                disc_h,
                flow_h,
                sat_h,
                rel_b,
                disc_b,
                flow_b,
                sat_b,
                pref_arm,
                clean_feedback,
                r.get("created_at") or "",
            ]
        )

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="study_ratings.csv"',
        },
    )
