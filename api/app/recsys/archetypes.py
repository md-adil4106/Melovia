"""Deterministic Rule-Derived Musical Archetypes for Melovia (Phase 11).

Architecture Constraints:
- Pure Python (zero imports of FastAPI, Starlette, or SQLAlchemy).
- 100% deterministic rule matching with stable tie-breaking.
- Strictly non-evaluative copy: descriptive only, never judgmental of musical taste.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArchetypeDefinition:
    """Definition of a musical archetype with matching criteria and non-evaluative copy."""

    id: str
    name: str
    tagline: str
    description: str
    criteria_summary: str


# 9 Documented, unique musical archetypes
ARCHETYPE_CATALOG: list[ArchetypeDefinition] = [
    ArchetypeDefinition(
        id="sonic_nomad",
        name="Sonic Nomad",
        tagline="Expansive explorer of uncharted musical traditions",
        description=(
            "Your listening footprint spans wide geographic and stylistic territories, "
            "prioritizing rare and underground micro-scenes over familiar domestic genres."
        ),
        criteria_summary="High Breadth (>= 0.50) and High Rarity (>= 0.50)",
    ),
    ArchetypeDefinition(
        id="comfort_listener",
        name="Comfort Listener",
        tagline="Anchored in harmonic unity and trusted aesthetic spaces",
        description=(
            "You cultivate a cohesive, emotionally resonant sound world, returning to "
            "harmonically unified tracks that sustain a focused atmospheric mood."
        ),
        criteria_summary="High Cohesion (>= 0.55) and Focused Breadth (< 0.40)",
    ),
    ArchetypeDefinition(
        id="night_explorer",
        name="Night Explorer",
        tagline="Drawn to nocturnal atmospheres, introspective depths, and twilight textures",
        description=(
            "You gravitate toward low-tempo, introspective soundscapes characterized by "
            "minor modes, gentle melancholy, and late-night contemplation across multiple clusters."
        ),
        criteria_summary=(
            "Low Energy (< 0.45), Low Valence (< 0.45), and Moderate Breadth (>= 0.35)"
        ),
    ),
    ArchetypeDefinition(
        id="kinetic_curator",
        name="Kinetic Curator",
        tagline="Fueled by rhythmic momentum, physical energy, and syncopated propulsion",
        description=(
            "Your selections prioritize driving percussive grooves, dancefloor dynamics, "
            "and upbeat physical propulsion across electronic, funk, and modern club scenes."
        ),
        criteria_summary="High Energy (>= 0.60) and High Danceability (>= 0.50)",
    ),
    ArchetypeDefinition(
        id="time_traveler",
        name="Time Traveler",
        tagline="Traversing decades and vintage eras through a singular aesthetic lens",
        description=(
            "You move seamlessly across historical release eras, finding stylistic and emotional "
            "bridges that connect vintage recordings to contemporary avant-garde releases."
        ),
        criteria_summary="Wide Era Range (>= 0.35) with Stylistic Cohesion (>= 0.40)",
    ),
    ArchetypeDefinition(
        id="niche_devotee",
        name="Niche Devotee",
        tagline="Dedicated connoisseur of specialized underground micro-genres",
        description=(
            "You specialize in obscure and idiosyncratic artistic expressions, showing a "
            "disciplined dedication to deep catalog gems and boundary-pushing independent releases."
        ),
        criteria_summary="High Rarity (>= 0.60) with High Cohesion (>= 0.45)",
    ),
    ArchetypeDefinition(
        id="eclectic_polymath",
        name="Eclectic Polymath",
        tagline="Voracious listener connecting disparate genres through unexpected sonic bridges",
        description=(
            "You resist rigid genre boundaries, weaving together diverse clusters with a "
            "curious and open-minded appetite that finds affinity in contrasting sonic traditions."
        ),
        criteria_summary="Very High Breadth (>= 0.60)",
    ),
    ArchetypeDefinition(
        id="ambient_archivist",
        name="Ambient Archivist",
        tagline="Curator of spacious acoustic textures, organic timbres, and meditative stillness",
        description=(
            "You favor unhurried acoustic resonance, delicate organic instrumentation, "
            "and spacious audio textures that reward patient and immersive listening."
        ),
        criteria_summary="Low Energy (< 0.40) and High Acousticness (>= 0.45)",
    ),
    ArchetypeDefinition(
        id="harmony_purist",
        name="Harmony Purist",
        tagline="Attuned to tonal precision, harmonic fidelity, and structural integrity",
        description=(
            "You demand exceptional harmonic and timbral consistency across your listening, "
            "favoring tracks that share a tight, refined musical language."
        ),
        criteria_summary="Very High Cohesion (>= 0.65)",
    ),
]

FALLBACK_ARCHETYPE = ArchetypeDefinition(
    id="balanced_explorer",
    name="Balanced Explorer",
    tagline="Cultivating an equilibrium between trusted favorites and open horizons",
    description=(
        "You balance a stable core of trusted musical favorites with an open curiosity "
        "for discovering fresh sounds, navigating the catalog with measured versatility."
    ),
    criteria_summary="Balanced distribution across all taste dimensions",
)


@dataclass(frozen=True)
class ArchetypeMatchResult:
    """Result of deterministic archetype matching."""

    id: str
    name: str
    tagline: str
    description: str
    criteria_summary: str
    matched_rules: list[str]
    is_fallback: bool


def determine_archetype(
    dimensions: dict[str, Any],
    scalars: dict[str, dict[str, float]],
) -> ArchetypeMatchResult:
    """Determine user's musical archetype via deterministic rule evaluation.

    Args:
        dimensions: Dict of DimensionScore objects or values (breadth, rarity, range, cohesion).
        scalars: Dict of scalar summaries (energy, valence, danceability, acousticness).

    Returns:
        ArchetypeMatchResult with stable tie-breaking.
    """

    # Helper to extract point estimates
    def get_dim(k: str) -> float:
        obj = dimensions.get(k)
        if obj is None:
            return 0.5
        if hasattr(obj, "value"):
            return float(obj.value)
        if isinstance(obj, dict):
            return float(obj.get("value", 0.5))
        return float(obj)

    def get_scal(k: str) -> float:
        s = scalars.get(k, {})
        return float(s.get("mean", 0.5))

    breadth = get_dim("breadth")
    rarity = get_dim("rarity")
    rng_val = get_dim("range")
    cohesion = get_dim("cohesion")

    energy = get_scal("energy")
    valence = get_scal("valence")
    danceability = get_scal("danceability")
    acousticness = get_scal("acousticness")

    candidate_scores: list[tuple[float, str, ArchetypeDefinition, list[str]]] = []

    # 1. sonic_nomad: breadth >= 0.50 and rarity >= 0.50
    if breadth >= 0.50 and rarity >= 0.50:
        score = (breadth - 0.50) + (rarity - 0.50)
        rules = [f"Breadth {breadth:.2f} >= 0.50", f"Rarity {rarity:.2f} >= 0.50"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "sonic_nomad")
        candidate_scores.append((score, arch.id, arch, rules))

    # 2. comfort_listener: cohesion >= 0.55 and breadth < 0.40
    if cohesion >= 0.55 and breadth < 0.40:
        score = (cohesion - 0.55) + (0.40 - breadth)
        rules = [f"Cohesion {cohesion:.2f} >= 0.55", f"Breadth {breadth:.2f} < 0.40"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "comfort_listener")
        candidate_scores.append((score, arch.id, arch, rules))

    # 3. night_explorer: energy < 0.45 and valence < 0.45 and breadth >= 0.35
    if energy < 0.45 and valence < 0.45 and breadth >= 0.35:
        score = (0.45 - energy) + (0.45 - valence) + (breadth - 0.35)
        rules = [
            f"Energy {energy:.2f} < 0.45",
            f"Valence {valence:.2f} < 0.45",
            f"Breadth {breadth:.2f} >= 0.35",
        ]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "night_explorer")
        candidate_scores.append((score, arch.id, arch, rules))

    # 4. kinetic_curator: energy >= 0.60 and danceability >= 0.50
    if energy >= 0.60 and danceability >= 0.50:
        score = (energy - 0.60) + (danceability - 0.50)
        rules = [f"Energy {energy:.2f} >= 0.60", f"Danceability {danceability:.2f} >= 0.50"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "kinetic_curator")
        candidate_scores.append((score, arch.id, arch, rules))

    # 5. time_traveler: range >= 0.35 and cohesion >= 0.40
    if rng_val >= 0.35 and cohesion >= 0.40:
        score = (rng_val - 0.35) + (cohesion - 0.40)
        rules = [f"Era Range {rng_val:.2f} >= 0.35", f"Cohesion {cohesion:.2f} >= 0.40"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "time_traveler")
        candidate_scores.append((score, arch.id, arch, rules))

    # 6. niche_devotee: rarity >= 0.60 and cohesion >= 0.45
    if rarity >= 0.60 and cohesion >= 0.45:
        score = (rarity - 0.60) + (cohesion - 0.45)
        rules = [f"Rarity {rarity:.2f} >= 0.60", f"Cohesion {cohesion:.2f} >= 0.45"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "niche_devotee")
        candidate_scores.append((score, arch.id, arch, rules))

    # 7. eclectic_polymath: breadth >= 0.60
    if breadth >= 0.60:
        score = breadth - 0.60
        rules = [f"Breadth {breadth:.2f} >= 0.60"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "eclectic_polymath")
        candidate_scores.append((score, arch.id, arch, rules))

    # 8. ambient_archivist: energy < 0.40 and acousticness >= 0.45
    if energy < 0.40 and acousticness >= 0.45:
        score = (0.40 - energy) + (acousticness - 0.45)
        rules = [f"Energy {energy:.2f} < 0.40", f"Acousticness {acousticness:.2f} >= 0.45"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "ambient_archivist")
        candidate_scores.append((score, arch.id, arch, rules))

    # 9. harmony_purist: cohesion >= 0.65
    if cohesion >= 0.65:
        score = cohesion - 0.65
        rules = [f"Cohesion {cohesion:.2f} >= 0.65"]
        arch = next(a for a in ARCHETYPE_CATALOG if a.id == "harmony_purist")
        candidate_scores.append((score, arch.id, arch, rules))

    if not candidate_scores:
        return ArchetypeMatchResult(
            id=FALLBACK_ARCHETYPE.id,
            name=FALLBACK_ARCHETYPE.name,
            tagline=FALLBACK_ARCHETYPE.tagline,
            description=FALLBACK_ARCHETYPE.description,
            criteria_summary=FALLBACK_ARCHETYPE.criteria_summary,
            matched_rules=["Balanced taste across core dimensions"],
            is_fallback=True,
        )

    # Sort candidates by score descending, tie-breaking by archetype id alphabetically
    candidate_scores.sort(key=lambda x: (-x[0], x[1]))
    best = candidate_scores[0]
    arch_def = best[2]

    return ArchetypeMatchResult(
        id=arch_def.id,
        name=arch_def.name,
        tagline=arch_def.tagline,
        description=arch_def.description,
        criteria_summary=arch_def.criteria_summary,
        matched_rules=best[3],
        is_fallback=False,
    )
