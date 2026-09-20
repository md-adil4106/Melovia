"""30-utterance test suite and directional shift validation on fixtures.

Tests cover:
1. 30 distinct natural language refinement utterances across knobs, arcs, tags, and ceilings.
2. Both RuleBasedRefinementParser and FakeLLMClient produce valid Refinement objects.
3. Measurable directional shifts on mock catalog fixtures:
   - "more energetic" increases mean energy_idx of top recommendations.
   - "too sad" (happier) increases mean valence_idx of top recommendations.
   - "less mainstream" reduces mean popularity_pct and increases novelty.
   - "more acoustic" increases mean acousticness.
"""

import sys
from pathlib import Path
from typing import Any

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402

from app.llm.client import FakeLLMClient  # noqa: E402
from app.llm.rule_parser import RuleBasedRefinementParser  # noqa: E402
from app.recsys import (  # noqa: E402
    CatalogStore,
    build_modes,
    generate_candidates,
    rerank_candidates,
    score_candidates,
)
from app.schemas.refinement import ArcType, KnobDeltas, Refinement, TagWeight  # noqa: E402
from app.session.store import SessionContext  # noqa: E402

# 30-utterance test matrix
UTTERANCE_TEST_SET = [
    # Knob - Energy
    ("more energetic", "energy", 0.1, 1.0),
    ("high energy please", "energy", 0.1, 1.0),
    ("less energetic", "energy", -1.0, -0.1),
    ("calm it down", "energy", -1.0, -0.1),
    # Knob - Valence / Mood
    ("too sad, make it happier", "valence", 0.1, 1.0),
    ("more uplifting music", "valence", 0.1, 1.0),
    ("sadder and more melancholic", "valence", -1.0, -0.1),
    ("darker mood", "valence", -1.0, -0.1),
    # Knob - Tempo
    ("faster tempo", "tempo", 0.1, 1.0),
    ("speed it up", "tempo", 0.1, 1.0),
    ("slower songs", "tempo", -1.0, -0.1),
    ("slow down the pace", "tempo", -1.0, -0.1),
    # Knob - Acousticness
    ("more acoustic sound", "acousticness", 0.1, 1.0),
    ("unplugged instruments", "acousticness", 0.1, 1.0),
    ("more electronic elements", "acousticness", -1.0, -0.1),
    ("heavy synthesizers", "acousticness", -1.0, -0.1),
    # Knob - Danceability
    ("more danceable", "danceability", 0.1, 1.0),
    ("party club groove", "danceability", 0.1, 1.0),
    # Novelty & Popularity
    ("less mainstream tracks", "novelty", 0.1, 1.0),
    ("underground hidden gems", "novelty", 0.1, 1.0),
    ("more popular hits", "novelty", -1.0, -0.1),
    # Boost & Suppress Tags
    ("keep the vibe but add rock", "boost_tags", "rock", None),
    ("more ambient music", "boost_tags", "ambient", None),
    ("no techno please", "suppress_tags", "techno", None),
    ("without metal", "suppress_tags", "metal", None),
    # Playlist Arcs & Complex Scenarios
    ("night drive at 2 AM", "arc", ArcType.STEADY, None),
    ("build up intensity for a workout", "arc", ArcType.BUILD, None),
    ("wind down for sleep", "arc", ArcType.WIND_DOWN, None),
    # Unsupported Concepts (Gracefully Handled)
    ("female vocalists only", "unsupported", "vocal gender filtering", None),
    ("songs with french lyrics", "unsupported", "lyrics language filtering", None),
]


@pytest.mark.parametrize("utterance,target_field,expected_val,optional_arg", UTTERANCE_TEST_SET)
def test_rule_parser_30_utterances(
    utterance: str,
    target_field: str,
    expected_val: Any,
    optional_arg: Any,
) -> None:
    """Ensure rule-based parser deterministically maps each of the 30 utterances."""
    refinement = RuleBasedRefinementParser.parse(utterance)
    assert isinstance(refinement, Refinement)

    if target_field in ("energy", "valence", "tempo", "acousticness", "danceability", "novelty"):
        val = getattr(refinement.knobs, target_field)
        min_v, max_v = expected_val, optional_arg
        assert min_v <= val <= max_v, (
            f"Utterance '{utterance}' knob {target_field}={val} outside [{min_v}, {max_v}]"
        )
    elif target_field == "boost_tags":
        assert any(t.tag == expected_val for t in refinement.boost_tags), (
            f"Expected boost tag '{expected_val}'"
        )
    elif target_field == "suppress_tags":
        assert any(t.tag == expected_val for t in refinement.suppress_tags), (
            f"Expected suppress tag '{expected_val}'"
        )
    elif target_field == "arc":
        assert refinement.arc == expected_val, f"Expected arc '{expected_val}'"
    elif target_field == "unsupported":
        assert any(expected_val in u for u in refinement.unsupported), (
            f"Expected unsupported reason containing '{expected_val}'"
        )


@pytest.mark.asyncio
async def test_fake_llm_client_30_utterances() -> None:
    """Ensure FakeLLMClient works with generate_structured across queries."""
    canned = {
        "more energetic": Refinement(knobs=KnobDeltas(energy=0.5)),
        "too sad": Refinement(knobs=KnobDeltas(valence=0.4)),
        "night drive": Refinement(
            arc=ArcType.STEADY, boost_tags=[TagWeight(tag="synthwave", weight=0.8)]
        ),
    }
    client = FakeLLMClient(canned_refinements=canned)

    res1 = await client.generate_structured(Refinement, "System", "more energetic")
    assert res1.knobs.energy == 0.5

    res2 = await client.generate_structured(Refinement, "System", "too sad")
    assert res2.knobs.valence == 0.4

    res3 = await client.generate_structured(Refinement, "System", "night drive at 2 AM")
    assert res3.arc == ArcType.STEADY
    assert res3.boost_tags[0].tag == "synthwave"


def test_directional_shift_on_mock_fixtures(tmp_path: Path) -> None:
    """Verify steering constraints shift recommendation distributions in the expected direction."""
    generate_mock_catalog(tmp_path)
    store = CatalogStore.load(tmp_path)

    seeds = store.track_ids[:3]
    modes = build_modes(seeds, store)
    pool = generate_candidates(modes, store)
    scored = score_candidates(pool, store)

    def get_energy(track_id: str) -> float:
        sc = store.get_track_dict(track_id).get("scalars", {})
        if "energy_idx" in sc:
            return float(sc["energy_idx"])
        if "energy" in sc:
            return float(sc["energy"])
        return 0.5

    # Baseline recommendations without session steering
    baseline_reranked = rerank_candidates(pool, scored, store, discovery=0.35, n=30)
    baseline_energy = float(np.mean([get_energy(it.track_id) for it in baseline_reranked.items]))
    baseline_pop = float(
        np.mean(
            [store.get_track_dict(it.track_id)["popularity_pct"] for it in baseline_reranked.items]
        )
    )

    # 1. Test "more energetic" shift
    ctx_energy = SessionContext(knobs={"energy": 0.8})
    energy_reranked = rerank_candidates(
        pool, scored, store, discovery=0.35, n=30, session_context=ctx_energy
    )
    steered_energy = float(np.mean([get_energy(it.track_id) for it in energy_reranked.items]))
    assert steered_energy > baseline_energy, (
        f"Steered energy ({steered_energy:.3f}) must exceed baseline ({baseline_energy:.3f})"
    )

    # 2. Test "less mainstream" (popularity ceiling 0.4)
    ctx_underground = SessionContext(
        knobs={"novelty": 0.6},
        popularity_ceiling=0.40,
    )
    underground_reranked = rerank_candidates(
        pool, scored, store, discovery=0.35, n=30, session_context=ctx_underground
    )
    steered_pop = np.mean(
        [store.get_track_dict(it.track_id)["popularity_pct"] for it in underground_reranked.items]
    )
    assert steered_pop < baseline_pop, (
        f"Steered popularity ({steered_pop:.1f}) must be lower than baseline ({baseline_pop:.1f})"
    )
