"""Unit and determinism tests for playlist sequencing (Phase 10).

Verifies:
- Byte-identical determinism across repeated executions.
- Mean transition cost reduction >= 25% vs random / score order on fixtures.
- Arc adherence: correlation >= 0.60 for build and wind-down arcs.
- Hard artist non-adjacency: consecutive same-artist tracks prevented.
- Dynamic scalar auto-drop when coverage < 70%.
- Edge cases: L=1, L=2, empty list, and intent energy deltas.
"""

import numpy as np
import pytest

from app.recsys.config import RecsysConfig
from app.recsys.sequencing import (
    ArcType,
    generate_arc_target,
    sequence_playlist,
)


def _generate_mock_track_pool(n: int = 30, n_artists: int = 8, seed: int = 42) -> list[dict]:
    """Generate reproducible mock track pool with known energy gradients and artist diversity."""
    rng = np.random.default_rng(seed)
    tracks = []
    for i in range(n):
        artist_id = f"artist_{i % n_artists}"
        # Spread energy across [0.1, 0.9]
        energy = float(0.10 + 0.80 * (i / max(1, n - 1)))
        tempo = float(0.20 + 0.60 * rng.random())
        tracks.append(
            {
                "id": f"track_{i:03d}",
                "track_idx": i,
                "title": f"Track Title {i}",
                "artist_id": artist_id,
                "artist_name": f"Artist {i % n_artists}",
                "scalars": {
                    "energy_idx": energy,
                    "tempo_norm": tempo,
                },
            }
        )
    return tracks


def test_arc_target_generation_shapes_and_bounds():
    """Verify arc target functions return expected values and shapes."""
    # Length 1 edge case
    steady_1 = generate_arc_target(ArcType.STEADY, 1)
    assert len(steady_1) == 1
    assert steady_1[0] == pytest.approx(0.50)

    # Steady arc
    steady_10 = generate_arc_target(ArcType.STEADY, 10)
    assert len(steady_10) == 10
    assert np.allclose(steady_10, 0.50)

    # Build arc: strictly non-decreasing from 0.25 to 0.80
    build_10 = generate_arc_target(ArcType.BUILD, 10)
    assert len(build_10) == 10
    assert build_10[0] == pytest.approx(0.25)
    assert build_10[-1] == pytest.approx(0.80)
    assert np.all(np.diff(build_10) >= 0)

    # Wind-down arc: strictly non-increasing from 0.80 to 0.25
    wind_10 = generate_arc_target(ArcType.WIND_DOWN, 10)
    assert len(wind_10) == 10
    assert wind_10[0] == pytest.approx(0.80)
    assert wind_10[-1] == pytest.approx(0.25)
    assert np.all(np.diff(wind_10) <= 0)

    # Wave arc: starts at 0.35, peaks in middle at 0.80, returns to 0.35
    wave_11 = generate_arc_target(ArcType.WAVE, 11)
    assert len(wave_11) == 11
    assert wave_11[0] == pytest.approx(0.35)
    assert wave_11[5] == pytest.approx(0.80)
    assert wave_11[-1] == pytest.approx(0.35)

    # Intent shift
    shifted_build = generate_arc_target(ArcType.BUILD, 10, energy_delta=0.5)
    assert np.all(shifted_build >= build_10)


def test_sequencing_strict_determinism():
    """Verify sequence_playlist generates byte-identical outputs across repeated calls."""
    pool = _generate_mock_track_pool(n=25, seed=123)
    cfg = RecsysConfig()

    res1 = sequence_playlist(pool, arc=ArcType.BUILD, length=15, config=cfg)
    res2 = sequence_playlist(pool, arc=ArcType.BUILD, length=15, config=cfg)

    tracks1 = [t["id"] for t in res1.ordered_tracks]
    tracks2 = [t["id"] for t in res2.ordered_tracks]

    assert tracks1 == tracks2
    assert res1.total_cost == pytest.approx(res2.total_cost, abs=1e-8)
    assert res1.mean_transition_cost == pytest.approx(res2.mean_transition_cost, abs=1e-8)
    assert res1.arc_correlation == pytest.approx(res2.arc_correlation, abs=1e-8)


def test_arc_adherence_build_and_wind_down():
    """Verify arc correlation between target and realized energy >= 0.60 for build and wind-down."""
    pool = _generate_mock_track_pool(n=30, seed=42)
    cfg = RecsysConfig()

    # Test Build Arc
    res_build = sequence_playlist(pool, arc=ArcType.BUILD, length=20, config=cfg)
    assert res_build.arc_correlation >= 0.60, (
        f"Build arc correlation was {res_build.arc_correlation:.3f}"
    )

    # Test Wind Down Arc
    res_wind = sequence_playlist(pool, arc=ArcType.WIND_DOWN, length=20, config=cfg)
    assert res_wind.arc_correlation >= 0.60, (
        f"Wind-down arc correlation was {res_wind.arc_correlation:.3f}"
    )


def test_transition_cost_reduction_vs_baselines():
    """Verify sequenced playlist achieves >= 25% lower cost vs random and score order."""
    pool = _generate_mock_track_pool(n=30, seed=99)
    cfg = RecsysConfig()
    length = 20

    # 1. Sequenced playlist
    res_seq = sequence_playlist(pool, arc=ArcType.STEADY, length=length, config=cfg)

    # 2. Score-order baseline (original order of pool truncated to length)
    score_order_tracks = pool[:length]
    # Compute transition cost of score-order baseline
    cost_score_order = 0.0
    for i in range(length - 1):
        t1, t2 = score_order_tracks[i], score_order_tracks[i + 1]
        e1, e2 = t1["scalars"]["energy_idx"], t2["scalars"]["energy_idx"]
        temp1, temp2 = t1["scalars"]["tempo_norm"], t2["scalars"]["tempo_norm"]
        same_art = 1.0 if t1["artist_id"] == t2["artist_id"] else 0.0
        step = (
            cfg.seq_w_tempo * abs(temp1 - temp2)
            + cfg.seq_w_energy * abs(e1 - e2)
            + cfg.seq_w_artist_penalty * same_art
        )
        cost_score_order += step
    mean_cost_score_order = cost_score_order / (length - 1)

    # 3. Random-order baseline (averaged over 20 random permutations of the selected tracks)
    rng = np.random.default_rng(42)
    random_mean_costs = []
    for _ in range(20):
        perm_tracks = [res_seq.ordered_tracks[idx] for idx in rng.permutation(length)]
        cost_rnd = 0.0
        for i in range(length - 1):
            t1, t2 = perm_tracks[i], perm_tracks[i + 1]
            e1, e2 = t1["scalars"]["energy_idx"], t2["scalars"]["energy_idx"]
            temp1, temp2 = t1["scalars"]["tempo_norm"], t2["scalars"]["tempo_norm"]
            same_art = 1.0 if t1["artist_id"] == t2["artist_id"] else 0.0
            step = (
                cfg.seq_w_tempo * abs(temp1 - temp2)
                + cfg.seq_w_energy * abs(e1 - e2)
                + cfg.seq_w_artist_penalty * same_art
            )
            cost_rnd += step
        random_mean_costs.append(cost_rnd / (length - 1))

    mean_cost_random = float(np.mean(random_mean_costs))

    # Calculate reduction percentages
    reduction_vs_random = (mean_cost_random - res_seq.mean_transition_cost) / mean_cost_random
    reduction_vs_score = (
        mean_cost_score_order - res_seq.mean_transition_cost
    ) / mean_cost_score_order

    assert reduction_vs_random >= 0.25, (
        f"Reduction vs random was {reduction_vs_random * 100:.1f}%"
    )
    assert reduction_vs_score >= 0.25, (
        f"Reduction vs score order was {reduction_vs_score * 100:.1f}%"
    )


def test_artist_non_adjacency():
    """Verify that adjacent same-artist tracks are eliminated when enough artists exist."""
    # Create pool with 4 tracks from artist_A and 4 from artist_B, etc.
    tracks = []
    for i in range(20):
        art_id = f"artist_{i % 4}"
        tracks.append(
            {
                "id": f"track_{i:02d}",
                "track_idx": i,
                "artist_id": art_id,
                "scalars": {
                    "energy_idx": 0.5,
                    "tempo_norm": 0.5,
                },
            }
        )

    cfg = RecsysConfig()
    res = sequence_playlist(tracks, arc=ArcType.STEADY, length=16, config=cfg)

    adjacent_same_artist_count = sum(1 for tr in res.transitions if tr.same_artist)
    assert adjacent_same_artist_count == 0, (
        f"Found {adjacent_same_artist_count} adjacent same artist tracks"
    )


def test_low_coverage_scalar_auto_drop():
    """Verify features with coverage < 70% are automatically dropped from cost calculation."""
    pool = _generate_mock_track_pool(n=20, seed=42)
    # Erase tempo_norm on 10 out of 20 tracks (50% coverage < 70% threshold)
    for i in range(10):
        pool[i]["scalars"]["tempo_norm"] = None

    cfg = RecsysConfig()
    res = sequence_playlist(pool, arc=ArcType.BUILD, length=15, config=cfg)

    assert "tempo_norm" in res.dropped_features
    assert res.active_weights["tempo"] == 0.0
    assert "energy_idx" not in res.dropped_features
    assert res.active_weights["energy"] == cfg.seq_w_energy


def test_edge_cases_empty_single_and_bounded_length():
    """Verify edge cases: empty list, single track, L > n."""
    cfg = RecsysConfig()

    # Empty list
    res_empty = sequence_playlist([], config=cfg)
    assert len(res_empty.ordered_tracks) == 0
    assert res_empty.total_cost == 0.0

    # Single track
    single_track = [{"id": "t1", "artist_id": "a1", "scalars": {"energy_idx": 0.5}}]
    res_single = sequence_playlist(single_track, length=5, config=cfg)
    assert len(res_single.ordered_tracks) == 1
    assert len(res_single.transitions) == 0
    assert res_single.mean_transition_cost == 0.0

    # Length capped at pool size
    pool = _generate_mock_track_pool(n=10)
    res_capped = sequence_playlist(pool, length=50, config=cfg)
    assert len(res_capped.ordered_tracks) == 10
