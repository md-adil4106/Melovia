"""Refinement schema for conversational music discovery steering.

Architecture & Security Constraints:
- Pydantic v2 with strict validation and extra='forbid'.
- Enforces numeric bounds on all knob deltas [-1.0, 1.0].
- Tags are constrained to the controlled catalog vocabulary at runtime.
- Unsupported musical aspects (e.g. vocal gender, lyrics language) are isolated into 'unsupported'.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ArcType(StrEnum):
    """Playlist energy/tempo progression arcs."""

    STEADY = "steady"
    BUILD = "build"
    WAVE = "wave"
    WIND_DOWN = "wind_down"


class KnobDeltas(BaseModel):
    """Interpretable scalar target deltas in [-1.0, 1.0]."""

    model_config = ConfigDict(extra="forbid", strict=True)

    energy: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Shift in acoustic intensity/energy"
    )
    valence: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Shift in emotional positivity/mood"
    )
    tempo: float = Field(default=0.0, ge=-1.0, le=1.0, description="Shift in musical tempo/pace")
    acousticness: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Shift toward acoustic vs electronic"
    )
    danceability: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Shift in rhythmic regularity/danceability"
    )
    novelty: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Shift in exploration vs familiarity"
    )

    def has_active_knobs(self) -> bool:
        """Return True if any knob has a non-zero shift."""
        return any(
            abs(val) > 0.001
            for val in (
                self.energy,
                self.valence,
                self.tempo,
                self.acousticness,
                self.danceability,
                self.novelty,
            )
        )


class TagWeight(BaseModel):
    """Weighted tag facet to boost or suppress."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tag: str = Field(..., min_length=1, max_length=64, description="Canonical tag string")
    weight: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Relative strength of boost/suppress"
    )


class Refinement(BaseModel):
    """Structured musical intent extracted from user conversational utterance."""

    model_config = ConfigDict(extra="forbid", strict=True)

    knobs: KnobDeltas = Field(default_factory=KnobDeltas)
    popularity_ceiling: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Upper bound for track popularity percentile (0.0=underground, 1.0=any)",
    )
    boost_tags: list[TagWeight] = Field(
        default_factory=list,
        max_length=8,
        description="Controlled tags to steer recommendations toward",
    )
    suppress_tags: list[TagWeight] = Field(
        default_factory=list,
        max_length=8,
        description="Controlled tags to steer recommendations away from",
    )
    arc: ArcType | None = Field(
        default=None,
        description="Playlist energy progression arc",
    )
    unsupported: list[str] = Field(
        default_factory=list,
        description="Requested concepts the engine cannot currently fulfill",
    )
    clarify: str | None = Field(
        default=None,
        max_length=200,
        description="Clarification or guidance question for the user (max 200 chars)",
    )


def filter_unsupported_tags(
    refinement: Refinement,
    valid_tags: set[str],
) -> Refinement:
    """Filter out tags not present in catalog vocabulary, moving them to unsupported."""
    retained_boost: list[TagWeight] = []
    retained_suppress: list[TagWeight] = []
    unsupported_items: list[str] = list(refinement.unsupported)

    for item in refinement.boost_tags:
        cleaned_tag = item.tag.strip().lower()
        if cleaned_tag in valid_tags:
            retained_boost.append(TagWeight(tag=cleaned_tag, weight=item.weight))
        else:
            unsupported_items.append(f"tag '{item.tag}' (not in catalog vocabulary)")

    for item in refinement.suppress_tags:
        cleaned_tag = item.tag.strip().lower()
        if cleaned_tag in valid_tags:
            retained_suppress.append(TagWeight(tag=cleaned_tag, weight=item.weight))
        else:
            unsupported_items.append(f"tag '{item.tag}' (not in catalog vocabulary)")

    return Refinement(
        knobs=refinement.knobs,
        popularity_ceiling=refinement.popularity_ceiling,
        boost_tags=retained_boost,
        suppress_tags=retained_suppress,
        arc=refinement.arc,
        unsupported=unsupported_items,
        clarify=refinement.clarify,
    )
