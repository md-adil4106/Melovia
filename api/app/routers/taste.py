"""Taste Profile, Archetype, Blindspots, and ListenBrainz Import API Router for Melovia (Phase 11).

Architecture & Quality Constraints:
- Non-evaluative copy: descriptive only, never judgmental of taste.
- Confidence indicator: < 8 tracks is explicitly marked "low" confidence.
- ListenBrainz: official API only (https://api.listenbrainz.org), rate-limited, opt-in.
- Signal grounding: all metrics trace to computed vector/scalar features.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeedbackEvent, Profile
from app.db.session import get_db_session
from app.errors import AppException
from app.recsys import (
    CatalogStore,
    compute_taste_profile,
    detect_blindspots,
    determine_archetype,
)
from app.routers.cookies import get_or_create_device_id, get_or_create_session_id
from app.schemas.taste import (
    ArchetypeResponse,
    BlindspotResponseItem,
    BlindspotsResponse,
    DimensionResponse,
    DominantTagItem,
    ListenBrainzImportRequest,
    ListenBrainzImportResponse,
    MusicDNASchema,
    RegionExposureItem,
    ScalarSummary,
    TasteProfileResponse,
)
from app.schemas.tracks import AudioScalars, TrackDetailResponse
from app.session.store import TokenBucketRateLimiter, global_session_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["taste", "profile"])
listenbrainz_limiter = TokenBucketRateLimiter(rate=0.5, capacity=5.0)


def _to_track_detail(idx: int, catalog: CatalogStore) -> TrackDetailResponse:
    """Helper to format a track index into a TrackDetailResponse."""
    t_dict = catalog.get_track_dict(idx)
    raw_scalars = t_dict.get("scalars")
    scalars_obj = AudioScalars(**raw_scalars) if raw_scalars else None
    return TrackDetailResponse(
        id=t_dict["id"],
        track_idx=t_dict["track_idx"],
        mbid=t_dict.get("mbid"),
        title=t_dict["title"],
        artist_id=t_dict["artist_id"],
        artist_name=t_dict["artist_name"],
        year=t_dict.get("year"),
        isrcs=t_dict.get("isrcs") or [],
        popularity_pct=float(t_dict.get("popularity_pct", 50.0)),
        has_a=bool(t_dict.get("has_a", True)),
        has_t=bool(t_dict.get("has_t", True)),
        region_id=t_dict.get("region_id"),
        scalars=scalars_obj,
        tags=t_dict.get("tags") or [],
    )


async def _gather_known_track_indices(
    request: Request,
    response: Response,
    seed_ids: list[str],
    db: AsyncSession,
    catalog: CatalogStore,
) -> tuple[list[int], list[dict[str, Any]], Any]:
    """Gather all known track indices from seeds, session feedback, and persistent profile."""
    device_id, _ = get_or_create_device_id(request, response)
    session_id = get_or_create_session_id(request, response)
    _, session_data = global_session_store.get_or_create(session_id)

    known_ids: set[str] = set()

    # 1. From request seeds
    for sid in seed_ids:
        if catalog.contains_id(sid):
            known_ids.add(sid)

    # 2. From active session
    known_ids.update(session_data.liked_track_ids)
    known_ids.update(session_data.known_track_ids)

    # 3. From persistent profile in DB (graceful fallback if degraded)
    feedback_events: list[dict[str, Any]] = []
    try:
        stmt = select(Profile).where(Profile.device_id == device_id)
        res = await db.execute(stmt)
        profile = res.scalar_one_or_none()
        if profile and profile.known_track_ids:
            known_ids.update(profile.known_track_ids)

        events_stmt = (
            select(FeedbackEvent)
            .where(FeedbackEvent.device_id == device_id)
            .order_by(FeedbackEvent.created_at.asc())
        )
        events_res = await db.execute(events_stmt)
        feedback_events = [
            {"event": ev.event, "track_id": ev.track_id} for ev in events_res.scalars()
        ]
    except Exception:
        pass

    # 4. Convert track UUIDs to catalog indices
    track_indices: list[int] = []
    for tid in known_ids:
        if catalog.contains_id(tid):
            track_indices.append(catalog.get_idx(tid))

    # Sort indices for determinism
    track_indices.sort()

    return track_indices, feedback_events, session_data.live_modes


@router.get(
    "/taste/profile",
    response_model=TasteProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute deterministic Taste Profile, Music DNA, and Archetype",
    description=(
        "Derives Breadth, Rarity, Range, Cohesion, and Adventurousness with 90% bootstrap "
        "confidence intervals, non-evaluative Music DNA, and rule-matched archetype."
    ),
)
async def get_taste_profile(
    request: Request,
    response: Response,
    seed_ids: list[str] = Query(default=[], description="Active seed track IDs"),
    db: AsyncSession = Depends(get_db_session),
) -> TasteProfileResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Catalog store is not available",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    track_indices, feedback_events, _ = await _gather_known_track_indices(
        request=request,
        response=response,
        seed_ids=seed_ids,
        db=db,
        catalog=catalog_store,
    )

    # Compute metrics
    profile_result = compute_taste_profile(
        track_indices=track_indices,
        catalog=catalog_store,
        feedback_events=feedback_events,
    )

    # Determine archetype
    archetype_match = determine_archetype(
        dimensions=profile_result.dimensions,
        scalars=profile_result.music_dna.mean_scalars,
    )

    # Format dimension responses
    dimensions_resp: dict[str, DimensionResponse | None] = {}
    for k, d in profile_result.dimensions.items():
        if d is not None:
            dimensions_resp[k] = DimensionResponse(
                name=d.name,
                key=d.key,
                value=d.value,
                percentile=d.percentile,
                ci_90=list(d.ci_90),
                description=d.description,
                definition_tooltip=d.definition_tooltip,
            )
        else:
            dimensions_resp[k] = None

    # Format Music DNA
    music_dna_resp = MusicDNASchema(
        dominant_tags=[
            DominantTagItem(tag=item["tag"], count=item["count"], share=item["share"])
            for item in profile_result.music_dna.dominant_tags
        ],
        mean_scalars={
            sname: ScalarSummary(mean=sval["mean"], min=sval["min"], max=sval["max"])
            for sname, sval in profile_result.music_dna.mean_scalars.items()
        },
        dominant_regions=[
            RegionExposureItem(
                region_id=item["region_id"],
                name=item["name"],
                genre_focus=item["genre_focus"],
                exposure=item["exposure"],
            )
            for item in profile_result.music_dna.dominant_regions
        ],
    )

    region_exposures_resp = [
        RegionExposureItem(
            region_id=item["region_id"],
            name=item["name"],
            genre_focus=item["genre_focus"],
            exposure=item["exposure"],
        )
        for item in profile_result.region_exposures
    ]

    archetype_resp = ArchetypeResponse(
        id=archetype_match.id,
        name=archetype_match.name,
        tagline=archetype_match.tagline,
        description=archetype_match.description,
        criteria_summary=archetype_match.criteria_summary,
        matched_rules=archetype_match.matched_rules,
        is_fallback=archetype_match.is_fallback,
    )

    return TasteProfileResponse(
        known_track_count=profile_result.known_track_count,
        confidence=profile_result.confidence,
        confidence_reason=profile_result.confidence_reason,
        dimensions=dimensions_resp,
        music_dna=music_dna_resp,
        archetype=archetype_resp,
        region_exposures=region_exposures_resp,
    )


@router.get(
    "/taste/blindspots",
    response_model=BlindspotsResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect unexplored musical regions adjacent to user taste",
    description=(
        "Ranks regions by adjacency * (1 - exposure) and attaches bridging folksonomy tags."
    ),
)
async def get_taste_blindspots(
    request: Request,
    response: Response,
    seed_ids: list[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db_session),
) -> BlindspotsResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Catalog store is not available",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    track_indices, _, modes = await _gather_known_track_indices(
        request=request,
        response=response,
        seed_ids=seed_ids,
        db=db,
        catalog=catalog_store,
    )

    blindspots = detect_blindspots(
        track_indices=track_indices,
        modes=modes,
        catalog=catalog_store,
    )

    # Format responses
    blindspot_items: list[BlindspotResponseItem] = []
    for b in blindspots:
        sample_tracks = [_to_track_detail(t_idx, catalog_store) for t_idx in b.sample_track_indices]
        blindspot_items.append(
            BlindspotResponseItem(
                region_id=b.region_id,
                name=b.name,
                genre_focus=b.genre_focus,
                description=b.description,
                top_tags=b.top_tags,
                exposure=b.exposure,
                adjacency_score=b.adjacency_score,
                rank_score=b.rank_score,
                bridge_tags=b.bridge_tags,
                sample_tracks=sample_tracks,
            )
        )

    return BlindspotsResponse(
        blindspots=blindspot_items,
        total_unexplored_regions=len(blindspots),
    )


@router.post(
    "/profile/import-listenbrainz",
    response_model=ListenBrainzImportResponse,
    status_code=status.HTTP_200_OK,
    summary="Import public listening history from ListenBrainz",
    description=(
        "Fetches recent public listens from the official ListenBrainz API, maps recording MBIDs "
        "to catalog tracks, and merges them into the active taste profile."
    ),
)
async def import_listenbrainz(
    request: Request,
    response: Response,
    payload: ListenBrainzImportRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ListenBrainzImportResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Catalog store is not available",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    client_ip = request.client.host if request.client else "unknown"
    if not listenbrainz_limiter.consume(client_ip):
        raise AppException(
            code="RATE_LIMITED",
            message=(
                "ListenBrainz import rate limit exceeded. "
                "Please wait a moment before importing again."
            ),
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    username = payload.username.strip()
    api_url = f"https://api.listenbrainz.org/1/user/{username}/listens?count={payload.limit}"

    total_listens = 0
    matched_track_indices: list[int] = []

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(api_url)
            if resp.status_code == 404:
                raise AppException(
                    code="USER_NOT_FOUND",
                    message=f"ListenBrainz user '{username}' was not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            if resp.status_code != 200:
                raise AppException(
                    code="UPSTREAM_ERROR",
                    message=f"ListenBrainz API returned HTTP status {resp.status_code}",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                )
            data = resp.json()
            payload_data = data.get("payload", {})
            listens = payload_data.get("listens", [])
            total_listens = len(listens)

            for item in listens:
                track_metadata = item.get("track_metadata", {})
                additional_info = track_metadata.get("additional_info", {})
                mbid = additional_info.get("recording_mbid") or track_metadata.get("recording_msid")

                matched_idx: int | None = None
                if mbid and catalog_store.contains_mbid(mbid):
                    matched_idx = catalog_store.get_idx_by_mbid(mbid)
                else:
                    # Fall back to title + artist match
                    title = track_metadata.get("track_name")
                    artist = track_metadata.get("artist_name")
                    if title:
                        matches = catalog_store.search_tracks(title, limit=3)
                        for m in matches:
                            if artist and artist.lower() in m["artist_name"].lower():
                                matched_idx = m["track_idx"]
                                break

                if matched_idx is not None and matched_idx not in matched_track_indices:
                    matched_track_indices.append(matched_idx)

    except httpx.RequestError as exc:
        logger.warning(f"ListenBrainz import network failure: {exc}")
        return ListenBrainzImportResponse(
            username=username,
            imported_count=0,
            matched_count=0,
            total_listens=0,
            matched_tracks=[],
            message="ListenBrainz service is currently unreachable. Please try again later.",
        )

    # Attach matched tracks to active session
    session_id = get_or_create_session_id(request, response)
    device_id, _ = get_or_create_device_id(request, response)
    _, session_data = global_session_store.get_or_create(session_id)

    matched_track_ids = [catalog_store.get_id(idx) for idx in matched_track_indices]
    session_data.known_track_ids.update(matched_track_ids)

    # Attach to persistent profile if present
    stmt = select(Profile).where(Profile.device_id == device_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    if profile:
        existing = set(profile.known_track_ids)
        existing.update(matched_track_ids)
        profile.known_track_ids = list(existing)
        await db.commit()

    matched_details = [_to_track_detail(idx, catalog_store) for idx in matched_track_indices]

    return ListenBrainzImportResponse(
        username=username,
        imported_count=len(matched_track_ids),
        matched_count=len(matched_track_indices),
        total_listens=total_listens,
        matched_tracks=matched_details,
        message=(
            f"Successfully imported {len(matched_track_ids)} catalog tracks "
            f"from ListenBrainz user {username}."
        ),
    )
