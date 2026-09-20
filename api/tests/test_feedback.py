"""Unit and determinism tests for Melovia feedback adaptation and mode merging."""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import numpy as np  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402

from app.recsys import (  # noqa: E402
    CatalogStore,
    apply_feedback,
    build_modes,
    merge_modes,
    modes_from_dict,
    modes_to_dict,
)


def test_feedback_like_direction(tmp_path: Path) -> None:
    """Like moves the nearest mode toward the track vector (cosine similarity increases)."""
    generate_mock_catalog(tmp_path)
    store = CatalogStore.load(tmp_path)

    seeds = store.track_ids[:3]
    initial_modes = build_modes(seeds, store)

    target_track_id = store.track_ids[10]

    fb_result = apply_feedback(
        event="like",
        track_id=target_track_id,
        modes=initial_modes,
        negative_track_ids=set(),
        negative_artist_ids=set(),
        known_track_ids=set(),
        liked_track_ids=[],
        catalog=store,
    )

    # 1. Cosine similarity to the target track must increase
    assert fb_result.cosine_to_track_after > fb_result.cosine_to_track_before, (
        f"Expected cosine increase on like: before={fb_result.cosine_to_track_before}, "
        f"after={fb_result.cosine_to_track_after}"
    )

    # 2. Track must be marked known and liked
    assert target_track_id in fb_result.known_track_ids
    assert target_track_id in fb_result.liked_track_ids
    assert target_track_id not in fb_result.negative_track_ids

    # 3. Norm invariant: updated mode must remain unit norm
    m_star = fb_result.nearest_mode_idx
    updated_v_t = fb_result.updated_modes.channel_vectors["t"][m_star]
    np.testing.assert_allclose(np.linalg.norm(updated_v_t), 1.0, atol=1e-4)


def test_feedback_dislike_direction_and_exclusion(tmp_path: Path) -> None:
    """Dislike moves the nearest mode away and adds the track to negative exclusions."""
    generate_mock_catalog(tmp_path)
    store = CatalogStore.load(tmp_path)

    seeds = store.track_ids[:3]
    initial_modes = build_modes(seeds, store)

    target_track_id = store.track_ids[15]

    fb_result = apply_feedback(
        event="dislike",
        track_id=target_track_id,
        modes=initial_modes,
        negative_track_ids=set(),
        negative_artist_ids=set(),
        known_track_ids=set(),
        liked_track_ids=[],
        catalog=store,
    )

    # 1. Cosine similarity to the target track must decrease
    assert fb_result.cosine_to_track_after < fb_result.cosine_to_track_before, (
        f"Expected cosine decrease on dislike: before={fb_result.cosine_to_track_before}, "
        f"after={fb_result.cosine_to_track_after}"
    )

    # 2. Track must be added to negative exclusions
    assert target_track_id in fb_result.negative_track_ids
    assert target_track_id in fb_result.known_track_ids
    assert target_track_id not in fb_result.liked_track_ids


def test_feedback_skip_weaker_than_dislike(tmp_path: Path) -> None:
    """Skip shifts mode away from track, but with 0.25x the magnitude of dislike."""
    generate_mock_catalog(tmp_path)
    store = CatalogStore.load(tmp_path)

    seeds = store.track_ids[:3]
    initial_modes = build_modes(seeds, store)

    target_track_id = store.track_ids[20]

    res_skip = apply_feedback(
        event="skip",
        track_id=target_track_id,
        modes=initial_modes,
        negative_track_ids=set(),
        negative_artist_ids=set(),
        known_track_ids=set(),
        liked_track_ids=[],
        catalog=store,
    )

    res_dislike = apply_feedback(
        event="dislike",
        track_id=target_track_id,
        modes=initial_modes,
        negative_track_ids=set(),
        negative_artist_ids=set(),
        known_track_ids=set(),
        liked_track_ids=[],
        catalog=store,
    )

    # Both decrease cosine
    assert res_skip.cosine_to_track_after < res_skip.cosine_to_track_before
    assert res_dislike.cosine_to_track_after < res_dislike.cosine_to_track_before

    # The drop for skip must be less severe than dislike
    drop_skip = res_skip.cosine_to_track_before - res_skip.cosine_to_track_after
    drop_dislike = res_dislike.cosine_to_track_before - res_dislike.cosine_to_track_after
    assert drop_skip < drop_dislike, (
        f"Expected drop_skip ({drop_skip}) < drop_dislike ({drop_dislike})"
    )

    # Skip does not hard-exclude
    assert target_track_id not in res_skip.negative_track_ids


def test_merge_modes_drift_cap(tmp_path: Path) -> None:
    """Merging divergent session modes caps Euclidean drift at max_drift."""
    generate_mock_catalog(tmp_path)
    store = CatalogStore.load(tmp_path)

    seeds_a = store.track_ids[:3]
    seeds_b = store.track_ids[50:53]

    modes_pers = build_modes(seeds_a, store)
    modes_sess = build_modes(seeds_b, store)

    max_drift = 0.20
    merged = merge_modes(
        persistent_modes=modes_pers,
        session_modes=modes_sess,
        alpha=0.90,  # high alpha to induce large desired shift
        max_drift=max_drift,
    )

    # For each mode, measure displacement
    for m_idx in range(modes_pers.num_modes):
        p_vec = modes_pers.channel_vectors["t"][m_idx]
        m_vec = merged.channel_vectors["t"][m_idx]
        drift = float(np.linalg.norm(m_vec - p_vec))
        assert drift <= max_drift + 1e-4, f"Drift {drift} exceeded max_drift {max_drift}"
        np.testing.assert_allclose(np.linalg.norm(m_vec), 1.0, atol=1e-4)


def test_modes_serialization_roundtrip(tmp_path: Path) -> None:
    """Modes JSON serialization round-trip is lossless and deterministic."""
    generate_mock_catalog(tmp_path)
    store = CatalogStore.load(tmp_path)

    seeds = store.track_ids[:4]
    modes = build_modes(seeds, store)

    d = modes_to_dict(modes)
    restored = modes_from_dict(d)

    assert restored.num_modes == modes.num_modes
    assert restored.member_seed_ids == modes.member_seed_ids
    assert restored.has_channel == modes.has_channel
    np.testing.assert_allclose(restored.channel_vectors["t"], modes.channel_vectors["t"], atol=1e-6)
    np.testing.assert_allclose(restored.channel_vectors["a"], modes.channel_vectors["a"], atol=1e-6)
    np.testing.assert_allclose(restored.weights, modes.weights, atol=1e-6)
