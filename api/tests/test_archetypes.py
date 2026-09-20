"""Unit tests for Rule-Derived Musical Archetypes (Phase 11).

Acceptance Gates:
- Archetype matching is deterministic: same inputs -> identical archetype.
- All documented archetypes can be matched.
- Non-evaluative copy check: no value judgments (good/bad/better/superior/guilty pleasure).
"""

from app.recsys import ARCHETYPE_CATALOG, determine_archetype


def test_archetype_determinism() -> None:
    """Same input dimensions and scalars must yield identical archetype and matched rules."""
    dims = {"breadth": 0.55, "rarity": 0.55, "range": 0.20, "cohesion": 0.35}
    scals = {"energy": {"mean": 0.5}, "valence": {"mean": 0.5}}

    res1 = determine_archetype(dims, scals)
    res2 = determine_archetype(dims, scals)

    assert res1.id == res2.id
    assert res1.name == res2.name
    assert res1.matched_rules == res2.matched_rules
    assert res1.id == "sonic_nomad"


def test_all_archetypes_reachable() -> None:
    """Every archetype in ARCHETYPE_CATALOG must have valid triggering inputs."""
    test_cases = [
        ("sonic_nomad", {"breadth": 0.55, "rarity": 0.55}, {}),
        ("comfort_listener", {"cohesion": 0.65, "breadth": 0.25}, {}),
        (
            "night_explorer",
            {"breadth": 0.40},
            {"energy": {"mean": 0.30}, "valence": {"mean": 0.30}},
        ),
        ("kinetic_curator", {}, {"energy": {"mean": 0.70}, "danceability": {"mean": 0.60}}),
        ("time_traveler", {"range": 0.45, "cohesion": 0.45}, {}),
        ("niche_devotee", {"rarity": 0.70, "cohesion": 0.50}, {}),
        ("eclectic_polymath", {"breadth": 0.75}, {}),
        ("ambient_archivist", {}, {"energy": {"mean": 0.25}, "acousticness": {"mean": 0.60}}),
        ("harmony_purist", {"cohesion": 0.75, "breadth": 0.45}, {}),
    ]

    matched_ids: set[str] = set()
    for expected_id, d_override, s_override in test_cases:
        # Default baseline
        dims = {"breadth": 0.30, "rarity": 0.30, "range": 0.15, "cohesion": 0.30}
        scals = {
            "energy": {"mean": 0.50},
            "valence": {"mean": 0.50},
            "danceability": {"mean": 0.40},
            "acousticness": {"mean": 0.30},
        }
        dims.update(d_override)
        scals.update(s_override)

        res = determine_archetype(dims, scals)
        matched_ids.add(res.id)
        assert res.id == expected_id, f"Expected {expected_id}, got {res.id}"

    # All 9 catalog archetypes were triggered
    catalog_ids = {a.id for a in ARCHETYPE_CATALOG}
    assert catalog_ids.issubset(matched_ids)


def test_non_evaluative_copy_audit() -> None:
    """No copy may use evaluative, judgmental, or hierarchical terms."""
    forbidden_terms = [
        "good taste",
        "bad taste",
        "better than",
        "superior",
        "inferior",
        "guilty pleasure",
        "basic",
        "refined taste",
        "lazy",
        "sophisticated",
        "primitive",
    ]

    for arch in ARCHETYPE_CATALOG:
        full_text = f"{arch.name} {arch.tagline} {arch.description} {arch.criteria_summary}".lower()
        for forbidden in forbidden_terms:
            assert forbidden not in full_text, (
                f"Archetype '{arch.id}' contains forbidden phrase: '{forbidden}'"
            )
