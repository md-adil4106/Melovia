"""Unit tests for Melovia Explainability Engine (ExplanationBuilder).

Tests cover:
1. Positive and negative activation for every rule in the rule table.
2. Invariant: every explanation sentence maps to >= 1 named signal key in RecSignals.
3. Invariant: proxy-based scalars (*_idx) are explicitly qualified as (approx.).
4. Dynamic salience: explanations change between familiarity (d=0.0) and discovery (d=1.0).
5. Robustness over 200 random/mock recommendations.
"""

from typing import Any

from app.recsys.explain import ExplanationBuilder
from app.schemas.signals import RecSignals

# ============================================================================
# Individual Rule Positive & Negative Tests
# ============================================================================


def test_rule_shared_tags_positive_and_negative() -> None:
    track_meta = {"title": "Nightcall", "artist_name": "Kavinsky"}
    seed_meta = {"title": "Pacific Coast", "artist_name": "Timecop1983"}

    # Positive: shared tags present
    signals_pos = {
        "shared_tags": [{"tag": "synthwave", "weight": 1.5}, {"tag": "retrowave", "weight": 1.2}],
        "nearest_seed_id": "seed-123",
        "nearest_seed_title": "Pacific Coast",
    }
    reasons_pos = ExplanationBuilder.explain(signals_pos, track_meta, seed_meta, discovery=0.35)
    shared_tag_reasons = [r for r in reasons_pos if r.id == ExplanationBuilder.RULE_SHARED_TAGS]
    assert len(shared_tag_reasons) == 1
    assert "synthwave and retrowave" in shared_tag_reasons[0].text
    assert "Pacific Coast" in shared_tag_reasons[0].text
    assert "shared_tags" in shared_tag_reasons[0].signal_keys

    # Negative: empty shared tags
    signals_neg = {
        "shared_tags": [],
        "nearest_seed_id": "seed-123",
    }
    reasons_neg = ExplanationBuilder.explain(signals_neg, track_meta, seed_meta, discovery=0.35)
    assert not any(r.id == ExplanationBuilder.RULE_SHARED_TAGS for r in reasons_neg)


def test_rule_energy_match_positive_and_negative() -> None:
    track_meta = {"title": "Track A", "artist_name": "Artist A"}

    # Positive: |delta| <= 0.12
    signals_pos = {
        "scalar_deltas": {"energy_idx": 0.05},
        "nearest_seed_id": "seed-123",
    }
    reasons_pos = ExplanationBuilder.explain(signals_pos, track_meta, discovery=0.35)
    energy_reasons = [r for r in reasons_pos if r.id == ExplanationBuilder.RULE_ENERGY_MATCH]
    assert len(energy_reasons) == 1
    assert "preferred energy range" in energy_reasons[0].text
    assert "(approx.)" in energy_reasons[0].text
    assert "scalar_deltas" in energy_reasons[0].signal_keys

    # Negative: |delta| > 0.12
    signals_neg = {
        "scalar_deltas": {"energy_idx": 0.35},
        "nearest_seed_id": "seed-123",
    }
    reasons_neg = ExplanationBuilder.explain(signals_neg, track_meta, discovery=0.35)
    assert not any(r.id == ExplanationBuilder.RULE_ENERGY_MATCH for r in reasons_neg)


def test_rule_valence_match_positive_and_negative() -> None:
    track_meta = {"title": "Track A", "artist_name": "Artist A"}

    # Positive: |delta| <= 0.12
    signals_pos = {
        "scalar_deltas": {"valence_idx": -0.04},
        "nearest_seed_id": "seed-123",
    }
    reasons_pos = ExplanationBuilder.explain(signals_pos, track_meta, discovery=0.35)
    val_reasons = [r for r in reasons_pos if r.id == ExplanationBuilder.RULE_VALENCE_MATCH]
    assert len(val_reasons) == 1
    assert "emotional mood" in val_reasons[0].text
    assert "(approx.)" in val_reasons[0].text
    assert "scalar_deltas" in val_reasons[0].signal_keys

    # Negative: |delta| > 0.12
    signals_neg = {
        "scalar_deltas": {"valence_idx": 0.40},
        "nearest_seed_id": "seed-123",
    }
    reasons_neg = ExplanationBuilder.explain(signals_neg, track_meta, discovery=0.35)
    assert not any(r.id == ExplanationBuilder.RULE_VALENCE_MATCH for r in reasons_neg)


def test_rule_artist_new_vs_familiar() -> None:
    track_meta = {"title": "Song X", "artist_name": "Solar Fields"}

    # New artist
    signals_new = {"artist_new": True, "nearest_seed_id": "seed-1"}
    reasons_new = ExplanationBuilder.explain(signals_new, track_meta, discovery=0.75)
    assert any(r.id == ExplanationBuilder.RULE_NEW_ARTIST for r in reasons_new)
    assert not any(r.id == ExplanationBuilder.RULE_FAMILIAR_ARTIST for r in reasons_new)

    # Familiar artist
    signals_fam = {"artist_new": False, "nearest_seed_id": "seed-1"}
    reasons_fam = ExplanationBuilder.explain(signals_fam, track_meta, discovery=0.10)
    assert any(r.id == ExplanationBuilder.RULE_FAMILIAR_ARTIST for r in reasons_fam)
    assert not any(r.id == ExplanationBuilder.RULE_NEW_ARTIST for r in reasons_fam)


def test_rule_novelty_high_vs_low() -> None:
    track_meta = {"title": "Song Y", "artist_name": "Artist Y"}

    # High novelty >= 0.55
    signals_high = {"novelty": 0.85, "nearest_seed_id": "seed-1"}
    reasons_high = ExplanationBuilder.explain(signals_high, track_meta, discovery=0.80)
    assert any(r.id == ExplanationBuilder.RULE_HIGH_NOVELTY for r in reasons_high)
    assert not any(r.id == ExplanationBuilder.RULE_LOW_NOVELTY for r in reasons_high)

    # Low novelty <= 0.25
    signals_low = {"novelty": 0.10, "nearest_seed_id": "seed-1"}
    reasons_low = ExplanationBuilder.explain(signals_low, track_meta, discovery=0.10)
    assert any(r.id == ExplanationBuilder.RULE_LOW_NOVELTY for r in reasons_low)
    assert not any(r.id == ExplanationBuilder.RULE_HIGH_NOVELTY for r in reasons_low)

    # Mid novelty (0.40): neither triggers
    signals_mid = {"novelty": 0.40, "nearest_seed_id": "seed-1"}
    reasons_mid = ExplanationBuilder.explain(signals_mid, track_meta, discovery=0.50)
    novelty_rules = (ExplanationBuilder.RULE_HIGH_NOVELTY, ExplanationBuilder.RULE_LOW_NOVELTY)
    assert not any(r.id in novelty_rules for r in reasons_mid)


def test_rule_popularity_bands() -> None:
    track_meta = {"title": "Song Z", "artist_name": "Artist Z"}

    # Underground / Lesser known <= 35
    signals_low_pop = {"popularity_pct": 20.0, "nearest_seed_id": "seed-1"}
    reasons_low_pop = ExplanationBuilder.explain(signals_low_pop, track_meta, discovery=0.70)
    assert any(r.id == ExplanationBuilder.RULE_LESSER_KNOWN for r in reasons_low_pop)
    assert not any(r.id == ExplanationBuilder.RULE_MAINSTREAM for r in reasons_low_pop)

    # Mainstream >= 75
    signals_high_pop = {"popularity_pct": 90.0, "nearest_seed_id": "seed-1"}
    reasons_high_pop = ExplanationBuilder.explain(signals_high_pop, track_meta, discovery=0.10)
    assert any(r.id == ExplanationBuilder.RULE_MAINSTREAM for r in reasons_high_pop)
    assert not any(r.id == ExplanationBuilder.RULE_LESSER_KNOWN for r in reasons_high_pop)


def test_rule_semantic_and_acoustic_matches() -> None:
    track_meta = {"title": "Song W", "artist_name": "Artist W"}

    # Semantic match
    signals_sem = {"pct_t": 0.95, "sim_t": 0.88, "nearest_seed_id": "seed-1"}
    reasons_sem = ExplanationBuilder.explain(signals_sem, track_meta, discovery=0.35)
    assert any(r.id == ExplanationBuilder.RULE_SEMANTIC_MATCH for r in reasons_sem)

    # Acoustic match
    signals_ac = {"pct_a": 0.85, "sim_a": 0.72, "nearest_seed_id": "seed-1"}
    reasons_ac = ExplanationBuilder.explain(signals_ac, track_meta, discovery=0.35)
    assert any(r.id == ExplanationBuilder.RULE_ACOUSTIC_MATCH for r in reasons_ac)

    # Low acoustic match (< 0.70)
    signals_ac_low = {"pct_a": 0.40, "sim_a": 0.30, "nearest_seed_id": "seed-1"}
    reasons_ac_low = ExplanationBuilder.explain(signals_ac_low, track_meta, discovery=0.35)
    assert not any(r.id == ExplanationBuilder.RULE_ACOUSTIC_MATCH for r in reasons_ac_low)


def test_rule_region_alignment() -> None:
    track_meta = {"title": "Song R", "artist_name": "Artist R"}

    # With region label
    signals_reg = {"region_id": 1, "region_label": "Neon Nocturne", "nearest_seed_id": "seed-1"}
    reasons_reg = ExplanationBuilder.explain(signals_reg, track_meta, discovery=0.35)
    reg_reasons = [r for r in reasons_reg if r.id == ExplanationBuilder.RULE_REGION_ALIGNMENT]
    assert len(reg_reasons) == 1
    assert "Neon Nocturne" in reg_reasons[0].text
    assert "region_label" in reg_reasons[0].signal_keys

    # Without region label
    signals_no_reg = {"region_id": None, "region_label": None, "nearest_seed_id": "seed-1"}
    reasons_no_reg = ExplanationBuilder.explain(signals_no_reg, track_meta, discovery=0.35)
    assert not any(r.id == ExplanationBuilder.RULE_REGION_ALIGNMENT for r in reasons_no_reg)


# ============================================================================
# Invariant and Sensitivity Tests
# ============================================================================


def test_no_sentence_without_backing_signal_invariant() -> None:
    """INVARIANT TEST: Every explanation sentence maps to >= 1 named signal key in RecSignals."""
    valid_recsignal_fields = set(RecSignals.model_fields.keys())
    # Add allowed aliases
    valid_recsignal_fields.update({"raw_sim_t", "raw_sim_a", "percentile_t", "percentile_a"})

    import random

    rng = random.Random(42)

    for _ in range(200):
        # Generate varied simulated signals
        d_val = rng.random()
        pop = rng.uniform(5.0, 95.0)
        nov = rng.uniform(0.0, 1.0)
        pct_t = rng.uniform(0.1, 0.99)
        has_a = rng.choice([True, False])
        pct_a = rng.uniform(0.1, 0.99) if has_a else None

        shared = [{"tag": "synthwave", "weight": 1.0}] if rng.random() > 0.4 else []
        deltas: dict[str, float] = {}
        if rng.random() > 0.3:
            deltas["energy_idx"] = rng.uniform(-0.3, 0.3)
        if rng.random() > 0.3:
            deltas["valence_idx"] = rng.uniform(-0.3, 0.3)

        reg_label = rng.choice(["Synthwave", "Post-Rock", None])

        mock_signals: dict[str, Any] = {
            "sim_t": round(pct_t * 0.9, 4),
            "pct_t": round(pct_t, 4),
            "sim_a": round(pct_a * 0.8, 4) if pct_a else None,
            "pct_a": round(pct_a, 4) if pct_a else None,
            "shared_tags": shared,
            "scalar_deltas": deltas,
            "nearest_seed_id": "seed-test",
            "nearest_seed_title": "Seed Title",
            "nearest_seed_artist": "Seed Artist",
            "novelty": round(nov, 4),
            "familiarity": round(1.0 - nov, 4),
            "artist_new": rng.choice([True, False]),
            "popularity_pct": round(pop, 1),
            "region_id": 1 if reg_label else None,
            "region_label": reg_label,
            "mmr_penalty": 0.05,
            "discovery_value": round(d_val, 2),
        }

        track_meta = {"title": "Candidate Track", "artist_name": "Candidate Artist"}
        seed_meta = {"title": "Seed Title", "artist_name": "Seed Artist"}

        reasons = ExplanationBuilder.explain(
            signals=mock_signals,
            track_meta=track_meta,
            seed_meta=seed_meta,
            discovery=d_val,
        )

        for reason in reasons:
            # 1. Non-empty sentence
            assert len(reason.text.strip()) > 0
            # 2. Maps to >= 1 named signal key
            assert len(reason.signal_keys) >= 1, f"Sentence '{reason.text}' has no backing signals!"
            # 3. Every signal key must be a valid field on RecSignals
            for k in reason.signal_keys:
                assert k in valid_recsignal_fields, f"Signal key '{k}' not defined on RecSignals!"


def test_explanation_changes_with_discovery_slider() -> None:
    """Test that reasons and their salience order change when moving from d=0.0 to d=1.0."""
    track_meta = {"title": "Neon Horizon", "artist_name": "Gunship"}
    seed_meta = {"title": "Tech Noir", "artist_name": "Gunship"}

    # Track with both familiar aspects (familiar artist) and novelty aspects
    signals: dict[str, Any] = {
        "shared_tags": [{"tag": "synthwave", "weight": 1.0}],
        "scalar_deltas": {"energy_idx": 0.05},
        "nearest_seed_id": "seed-123",
        "nearest_seed_title": "Tech Noir",
        "novelty": 0.70,
        "artist_new": False,
        "popularity_pct": 30.0,
        "pct_t": 0.88,
        "sim_t": 0.85,
        "region_id": 0,
        "region_label": "Neon Nocturne",
    }

    # At d = 0.0 (maximum familiarity): familiar artist, semantic similarity dominate
    reasons_d0 = ExplanationBuilder.explain(signals, track_meta, seed_meta, discovery=0.0)
    reasons_d0_ids = [r.id for r in reasons_d0]
    assert ExplanationBuilder.RULE_FAMILIAR_ARTIST in reasons_d0_ids[:2]

    # At d = 1.0 (maximum discovery): high novelty and lesser known underground gem dominate
    reasons_d1 = ExplanationBuilder.explain(signals, track_meta, seed_meta, discovery=1.0)
    reasons_d1_ids = [r.id for r in reasons_d1]
    assert ExplanationBuilder.RULE_HIGH_NOVELTY in reasons_d1_ids[:2]

    # The order or presence of top reasons must change between d=0 and d=1
    assert reasons_d0_ids != reasons_d1_ids


def test_proxy_scalar_approximate_label_invariant() -> None:
    """Proxy scalars (energy_idx, valence_idx) must contain '(approx.)' in their explanation."""
    track_meta = {"title": "Track", "artist_name": "Artist"}
    signals = {
        "scalar_deltas": {"energy_idx": 0.02, "valence_idx": -0.01},
        "nearest_seed_id": "seed-123",
    }
    reasons = ExplanationBuilder.explain(signals, track_meta, discovery=0.35)
    proxy_reasons = [
        r
        for r in reasons
        if r.id in (ExplanationBuilder.RULE_ENERGY_MATCH, ExplanationBuilder.RULE_VALENCE_MATCH)
    ]
    assert len(proxy_reasons) >= 1
    for r in proxy_reasons:
        assert "(approx.)" in r.text
