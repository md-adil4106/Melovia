"""Pydantic schemas for 3D/2D Universe endpoints (Phase 12)."""

from pydantic import BaseModel, Field


class UniverseMetrics(BaseModel):
    """Quality metrics for the precomputed dimensional reduction layout."""

    trustworthiness_k15: float = Field(
        ..., description="Trustworthiness metric at k=15 measuring neighborhood preservation"
    )
    continuity_k15: float = Field(..., description="Continuity metric measuring rank preservation")
    method_3d: str = Field(..., description="Method used for 3D projection ('umap-3d' or 'pca-3d')")
    method_2d: str = Field(..., description="Method used for 2D fallback ('pca-2d')")
    sample_count: int = Field(..., description="Total points included in the render sample")


class UniverseRegionResponse(BaseModel):
    """Acoustic region centroid and display properties in 3D/2D space."""

    id: int = Field(..., description="Region integer identifier (0..23)")
    region_id: int = Field(default=0, description="Alias for id for web client compatibility")
    label: str = Field(..., description="Descriptive display name of the region")
    name: str = Field(default="", description="Alias for label for web client compatibility")
    genre_focus: str = Field(..., description="Musical scene or genre focus")
    description: str = Field(..., description="Non-evaluative musical character description")
    centroid_3d: list[float] = Field(
        ..., description="Region centroid in 3D space [x, y, z] in [-1.0, 1.0]"
    )
    centroid_2d: list[float] = Field(
        ..., description="Region centroid in 2D fallback space [x, y] in [-1.0, 1.0]"
    )
    color: str = Field(..., description="Hex color assigned to this region for visual consistency")
    exposure: float = Field(
        default=0.0, description="User's current exposure level to this region in [0.0, 1.0]"
    )
    top_tags: list[str] = Field(default_factory=list, description="Top descriptive tags by lift")
    track_count: int = Field(..., description="Number of tracks in this region")


class LandmarkTrack(BaseModel):
    """Famous or landmark track in a specific genre region."""

    track_id: str = Field(..., description="Track UUID")
    track_idx: int = Field(..., description="Catalog row index")
    title: str = Field(..., description="Track title")
    artist_name: str = Field(..., description="Artist name")
    popularity_pct: float = Field(..., description="Popularity percentage [0-100]")
    position_3d: list[float] = Field(..., description="[x, y, z] coordinate in 3D universe")


class GenreConstellation(BaseModel):
    """Constellation connecting famous landmark tracks within a musical genre."""

    region_id: int = Field(..., description="Region ID (0..23)")
    region_name: str = Field(..., description="Region name")
    genre_focus: str = Field(..., description="Genre focus description")
    color: str = Field(..., description="Hex color")
    landmark_tracks: list[LandmarkTrack] = Field(
        default_factory=list, description="Top famous tracks in this genre"
    )
    lines: list[list[list[float]]] = Field(
        default_factory=list,
        description="Constellation line segments connecting landmark tracks: [[[x,y,z], ...]]",
    )


class UniverseResponse(BaseModel):
    """Complete 3D and 2D catalog universe dataset for the client render sample."""

    points: list[int] = Field(
        ...,
        description=(
            "Flat Int16-quantized array: [qx_0, qy_0, qz_0, reg_0, trk_0, qx_1, ...] "
            "where qx/qy/qz are scaled by 32767 to map [-1.0, 1.0] coordinates into integers."
        ),
    )
    points_quantized: list[int] = Field(
        default_factory=list,
        description="Alias for points for web client compatibility",
    )
    track_ids: list[str] = Field(
        default_factory=list,
        description="Track IDs corresponding to the rendered sample points",
    )
    point_count: int = Field(..., description="Total number of points encoded in the points array")
    scale: float = Field(
        default=32767.0, description="Divisor used to dequantize Int16 values back to float [-1, 1]"
    )
    regions: list[UniverseRegionResponse] = Field(
        ..., description="All 24 region centroids and visual metadata"
    )
    constellations: list[GenreConstellation] = Field(
        default_factory=list,
        description="Genre constellations connecting famous landmark tracks across the cosmos",
    )
    metrics: UniverseMetrics = Field(..., description="Neighborhood preservation quality metrics")
    quality_metrics: UniverseMetrics | None = Field(
        default=None, description="Alias for metrics for web client compatibility"
    )


class UniversePlaceRequest(BaseModel):
    """Request to place dynamic vectors or tracks in 3D space without per-request UMAP."""

    track_ids: list[str] | None = Field(
        default=None, description="Optional catalog track IDs to place"
    )
    mode_vectors: list[list[float]] | None = Field(
        default=None,
        description="Optional high-dimensional taste mode vectors (128d or 256d) to place",
    )
    k: int = Field(
        default=10, ge=1, le=30, description="Number of nearest neighbors for interpolation"
    )


class PlacedUniverseItem(BaseModel):
    """Calculated 3D and 2D position for a placed query item."""

    id: str = Field(..., description="Track ID or generated mode ID")
    type: str = Field(..., description="'track' or 'taste_mode'")
    position_3d: list[float] = Field(..., description="Interpolated 3D position [x, y, z]")
    position_2d: list[float] | None = Field(
        default=None, description="Interpolated 2D position [x, y]"
    )
    nearest_track_ids: list[str] = Field(
        default_factory=list, description="Catalog tracks used for weighted interpolation"
    )
    weights: list[float] = Field(
        default_factory=list, description="Softmax interpolation weights assigned to nearest tracks"
    )
    nearest_catalog_id: str | None = Field(
        default=None, description="First nearest catalog track ID for client convenience"
    )
    confidence: float = Field(default=1.0, description="Interpolation confidence score")


class UniversePlaceResponse(BaseModel):
    """Response containing 3D/2D positions for requested items."""

    items: list[PlacedUniverseItem] = Field(
        default_factory=list, description="List of placed items"
    )
    placements: list[PlacedUniverseItem] = Field(
        default_factory=list, description="Alias for items for web client compatibility"
    )


class UniverseNeighborItem(BaseModel):
    """High-dimensional nearest neighbor item with explanation signals."""

    track_idx: int
    track_id: str
    title: str
    artist_name: str
    region_id: int | None = None
    region_name: str = ""
    similarity_combined: float = Field(
        ..., description="Combined audio + taste cosine similarity in original space"
    )
    original_cosine_sim: float = Field(
        default=0.0, description="Alias for similarity_combined for web client compatibility"
    )
    similarity_t: float = Field(..., description="Taste embedding cosine similarity")
    similarity_a: float | None = Field(
        default=None, description="Audio embedding cosine similarity if available"
    )
    shared_tags: list[str] = Field(
        default_factory=list, description="Tags shared with the target track"
    )


class UniverseNeighborsResponse(BaseModel):
    """True original-space neighbors for a 3D-selected track with distortion disclosure."""

    target_track_id: str
    track_id: str = Field(default="", description="Alias for target_track_id for web client")
    target_track_title: str
    track_title: str = Field(default="", description="Alias for target_track_title for web client")
    artist_name: str = ""
    position_3d: list[float] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0],
        description="3D coordinates of target track for client side panel",
    )
    target_region_id: int | None = None
    region_id: int = 0
    region_name: str = ""
    neighbors: list[UniverseNeighborItem] = Field(
        default_factory=list, description="Nearest neighbors computed in original vector space"
    )
    distortion_disclaimer: str = Field(
        ...,
        description=(
            "Honest disclosure explaining that 3D coordinates are non-linear approximations, "
            "and true musical recommendations are derived from high-dimensional vectors."
        ),
    )
    distortion_warning: str = Field(
        default="",
        description="Alias for distortion_disclaimer for web client",
    )
