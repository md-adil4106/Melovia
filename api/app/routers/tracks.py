"""Track search and metadata retrieval endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import StagingTrack
from app.db.session import get_db_session
from app.errors import AppException, NotFoundError
from app.recsys.catalog import CatalogStore
from app.schemas.tracks import AudioScalars, TrackDetailResponse, TrackSearchResponse
from app.session.store import TokenBucketRateLimiter

router = APIRouter(prefix="/tracks", tags=["Tracks"])
search_rate_limiter = TokenBucketRateLimiter(rate=2.0, capacity=20.0)


def get_catalog_store(request: Request) -> CatalogStore:
    """Dependency to retrieve active CatalogStore from application state."""
    store = getattr(request.app.state, "catalog_store", None)
    if not isinstance(store, CatalogStore):
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted or available",
            status_code=503,
        )
    return store


def _build_track_detail(raw_dict: dict[str, Any], store: CatalogStore) -> TrackDetailResponse:
    raw_scalars = raw_dict.get("scalars")
    scalars: AudioScalars | None = None
    if raw_scalars and isinstance(raw_scalars, dict):
        scalars = AudioScalars(
            bpm=float(raw_scalars["bpm"]) if "bpm" in raw_scalars else None,
            tempo_bpm=float(raw_scalars["tempo_bpm"]) if "tempo_bpm" in raw_scalars else None,
            energy=float(raw_scalars["energy"]) if "energy" in raw_scalars else None,
            valence=float(raw_scalars["valence"]) if "valence" in raw_scalars else None,
            danceability=float(raw_scalars["danceability"])
            if "danceability" in raw_scalars
            else None,
            acousticness=float(raw_scalars["acousticness"])
            if "acousticness" in raw_scalars
            else None,
            instrumentalness=float(raw_scalars["instrumentalness"])
            if "instrumentalness" in raw_scalars
            else None,
            loudness_db=float(raw_scalars["loudness_db"]) if "loudness_db" in raw_scalars else None,
        )

    # Resolve tags: from raw_dict or region top_tags if region_id is available
    tags: list[str] = list(raw_dict.get("tags") or [])
    region_id = raw_dict.get("region_id")
    if not tags and region_id is not None and store.regions:
        for r in store.regions:
            if r.get("region_id") == region_id:
                tags = list(r.get("top_tags", []))
                break

    isrcs: list[str] = []
    if "isrcs" in raw_dict and isinstance(raw_dict["isrcs"], (list, tuple)):
        isrcs = [str(x) for x in raw_dict["isrcs"]]
    elif "isrc" in raw_dict and raw_dict["isrc"]:
        isrcs = [str(raw_dict["isrc"])]

    return TrackDetailResponse(
        id=str(raw_dict["id"]),
        track_idx=int(raw_dict["track_idx"]),
        mbid=str(raw_dict["mbid"]) if raw_dict.get("mbid") else None,
        title=str(raw_dict["title"]),
        artist_id=str(raw_dict["artist_id"]),
        artist_name=str(raw_dict["artist_name"]),
        year=int(raw_dict["year"]) if raw_dict.get("year") is not None else None,
        isrcs=isrcs,
        popularity_pct=float(raw_dict.get("popularity_pct", 50.0)),
        has_a=bool(raw_dict.get("has_a", True)),
        has_t=bool(raw_dict.get("has_t", True)),
        region_id=int(region_id) if region_id is not None else None,
        scalars=scalars,
        tags=tags,
        artwork_url=raw_dict.get("artwork_url"),
        preview_url=raw_dict.get("preview_url"),
        album_name=raw_dict.get("album_name"),
    )


def _build_staging_track_detail(st: StagingTrack) -> TrackDetailResponse:
    scalars: AudioScalars | None = None
    if st.scalars and isinstance(st.scalars, dict):
        scalars = AudioScalars(
            bpm=float(st.scalars["bpm"]) if "bpm" in st.scalars else None,
            tempo_bpm=float(st.scalars["tempo_bpm"]) if "tempo_bpm" in st.scalars else None,
            energy=float(st.scalars["energy"]) if "energy" in st.scalars else None,
            valence=float(st.scalars["valence"]) if "valence" in st.scalars else None,
            danceability=float(st.scalars["danceability"])
            if "danceability" in st.scalars
            else None,
            acousticness=float(st.scalars["acousticness"])
            if "acousticness" in st.scalars
            else None,
            instrumentalness=float(st.scalars["instrumentalness"])
            if "instrumentalness" in st.scalars
            else None,
            loudness_db=float(st.scalars["loudness_db"]) if "loudness_db" in st.scalars else None,
        )

    tag_names: list[str] = []
    if st.tags and isinstance(st.tags, list):
        for t in st.tags:
            if isinstance(t, dict) and "name" in t:
                tag_names.append(str(t["name"]))
            elif isinstance(t, str):
                tag_names.append(t)

    artist_id = st.artist_mbid or str(
        uuid.uuid5(uuid.NAMESPACE_DNS, f"melovia.art.{st.artist_name}")
    )

    return TrackDetailResponse(
        id=st.id,
        track_idx=-1,
        mbid=st.mbid,
        title=st.title,
        artist_id=artist_id,
        artist_name=st.artist_name,
        year=st.year,
        isrcs=list(st.isrcs) if isinstance(st.isrcs, list) else [],
        popularity_pct=st.popularity_pct,
        has_a=st.has_a,
        has_t=st.has_t,
        region_id=None,
        scalars=scalars,
        tags=tag_names,
    )


@router.get(
    "/search",
    response_model=TrackSearchResponse,
    summary="Search Catalog Tracks",
    description=(
        "Case-insensitive prefix and substring matching across vector catalog and staging tables."
    ),
)
async def search_tracks(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100, description="Search query string"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    store: CatalogStore = Depends(get_catalog_store),
    session: AsyncSession = Depends(get_db_session),
) -> TrackSearchResponse:
    # Rate limiting: token bucket per client IP and device
    client_ip = request.client.host if request.client else "unknown"
    device_id = request.cookies.get("melovia_device_id", "anon")
    rate_key = f"search:{client_ip}:{device_id}"
    if not search_rate_limiter.consume(rate_key):
        raise AppException(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many search requests. Please slow down.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 1. Search in-memory store
    bundle_results = store.search_tracks(q, limit=limit)
    items: list[TrackDetailResponse] = [_build_track_detail(item, store) for item in bundle_results]

    # 2. Search database staging_tracks
    db_items: list[TrackDetailResponse] = []
    try:
        q_lower = q.strip().lower()
        stmt = (
            select(StagingTrack)
            .where(
                or_(
                    func.lower(StagingTrack.title).contains(q_lower),
                    func.lower(StagingTrack.artist_name).contains(q_lower),
                )
            )
            .order_by(StagingTrack.popularity_pct.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        for row in res.scalars():
            db_items.append(_build_staging_track_detail(row))
    except Exception:
        pass

    # 3. Search live public music releases (iTunes Search API)
    live_items: list[TrackDetailResponse] = []
    if len(q.strip()) >= 2:
        from app.services.live_search import live_search_service

        try:
            live_tracks = await live_search_service.search_tracks(q.strip(), limit=limit)
            for raw_live in live_tracks:
                store.register_dynamic_track(raw_live)
                live_items.append(_build_track_detail(raw_live, store))
        except Exception:
            pass

    # 4. Merge and deduplicate by canonical (title, artist)
    # Curated DB tracks take precedence, enriched with live artwork/preview if available
    db_lookup = {(t.title.lower().strip(), t.artist_name.lower().strip()): t for t in db_items}
    for live_item in live_items:
        key = (live_item.title.lower().strip(), live_item.artist_name.lower().strip())
        if key in db_lookup:
            dbt = db_lookup[key]
            if not dbt.artwork_url and live_item.artwork_url:
                dbt.artwork_url = live_item.artwork_url
            if not dbt.preview_url and live_item.preview_url:
                dbt.preview_url = live_item.preview_url

    seen_keys: set[tuple[str, str]] = set()
    merged: list[TrackDetailResponse] = []

    for t in db_items + live_items + items:
        key = (t.title.lower().strip(), t.artist_name.lower().strip())
        if key not in seen_keys:
            seen_keys.add(key)
            merged.append(t)
            if len(merged) >= limit:
                break

    return TrackSearchResponse(
        query=q,
        total=len(merged),
        limit=limit,
        items=merged,
    )


@router.get(
    "/{id}",
    response_model=TrackDetailResponse,
    summary="Get Track Details",
    description=(
        "Retrieve complete metadata, audio scalars, tags, and channel status for a single track."
    ),
)
async def get_track(
    id: str,
    store: CatalogStore = Depends(get_catalog_store),
    session: AsyncSession = Depends(get_db_session),
) -> TrackDetailResponse:
    # 1. Try store first (includes dynamic registered tracks)
    if store.contains_id(id):
        raw_track = store.get_track_dict(id)
        return _build_track_detail(raw_track, store)

    # 2. Try live lookup if external ID
    if id.startswith("ext:itunes:"):
        from app.services.live_search import live_search_service

        try:
            live_track = await live_search_service.get_track_by_id(id)
            if live_track:
                store.register_dynamic_track(live_track)
                return _build_track_detail(live_track, store)
        except Exception:
            pass

    # 3. Try database staging_tracks by id or mbid
    try:
        stmt = select(StagingTrack).where(or_(StagingTrack.id == id, StagingTrack.mbid == id))
        res = await session.execute(stmt)
        st = res.scalar_one_or_none()
        if st:
            return _build_staging_track_detail(st)
    except Exception:
        pass

    raise NotFoundError(f"Track with ID '{id}' was not found in catalog")
