"""Track search and metadata retrieval endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.errors import AppException, NotFoundError
from app.recsys.catalog import CatalogStore
from app.schemas.tracks import AudioScalars, TrackDetailResponse, TrackSearchResponse

router = APIRouter(prefix="/tracks", tags=["Tracks"])


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

    # Resolve tags: from region top_tags if region_id is available
    tags: list[str] = []
    region_id = raw_dict.get("region_id")
    if region_id is not None and store.regions:
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
    )


@router.get(
    "/search",
    response_model=TrackSearchResponse,
    summary="Search Catalog Tracks",
    description="Case-insensitive prefix and substring matching on track titles and artist names.",
)
async def search_tracks(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    store: CatalogStore = Depends(get_catalog_store),
) -> TrackSearchResponse:
    results = store.search_tracks(q, limit=limit)
    items = [_build_track_detail(item, store) for item in results]
    return TrackSearchResponse(
        query=q,
        total=len(items),
        limit=limit,
        items=items,
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
) -> TrackDetailResponse:
    if not store.contains_id(id):
        raise NotFoundError(f"Track with ID '{id}' was not found in catalog")

    raw_track = store.get_track_dict(id)
    return _build_track_detail(raw_track, store)
