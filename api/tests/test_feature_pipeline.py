"""Unit and Integration Tests for Melovia Feature & Embedding Pipeline (Phase 3)."""

import sys
from pathlib import Path
from typing import Any

# Ensure root is on path for pipelines import
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from pipelines.build_features import (  # noqa: E402
    build_audio_channel,
    build_bundle,
    build_tag_vocabulary,
    build_text_template,
    canonicalize_tag,
    compute_deterministic_text_embeddings,
    compute_interpretable_scalars,
    extract_raw_audio_features,
)

from app.recsys.catalog import CatalogStore  # noqa: E402


@pytest.fixture
def sample_test_tracks() -> list[dict[str, Any]]:
    """Provide a deterministic fixture of 30 test tracks."""
    tracks: list[dict[str, Any]] = []
    genres = ["electronic", "synthwave", "ambient", "indie rock", "post-rock", "hip-hop"]
    for i in range(30):
        g = genres[i % len(genres)]
        has_audio = i % 5 != 0  # 20% missing audio
        scalars = None
        if has_audio:
            energy = 0.2 + (i % 8) * 0.1
            dance = 0.3 + (i % 7) * 0.1
            bpm = 80.0 + (i * 3.5)
            scalars = {
                "bpm": bpm,
                "tempo_bpm": bpm,
                "energy": energy,
                "valence": 0.4 + (i % 6) * 0.1,
                "danceability": dance,
                "acousticness": 1.0 - energy,
                "instrumentalness": 0.8 if "ambient" in g else 0.2,
                "loudness_db": -20.0 + (energy * 15.0),
            }

        tags = [
            {"name": g, "weight": 1.0, "source": "recording"},
            {
                "name": "melancholy" if i % 2 == 0 else "energetic",
                "weight": 0.8,
                "source": "recording",
            },
            {
                "name": "synthpop" if i % 3 == 0 else "guitar",
                "weight": 0.6,
                "source": "artist_fallback",
            },
        ]

        tracks.append(
            {
                "id": f"track-uuid-{i:03d}",
                "mbid": f"mbid-{i:03d}",
                "title": f"Test Song {i}",
                "artist_name": f"Test Artist {i % 5}",
                "artist_mbid": f"artist-mbid-{i % 5}",
                "year": 1980 + (i * 2),
                "isrcs": [f"USMLV26{i:05d}"],
                "popularity_pct": float(10.0 + i * 2.5),
                "has_a": has_audio,
                "has_t": True,
                "tags": tags,
                "scalars": scalars,
            }
        )
    return tracks


def test_canonicalize_tags_and_synonyms() -> None:
    """Verify that synonyms are merged to canonical representations."""
    assert canonicalize_tag("synthpop") == "synth-pop"
    assert canonicalize_tag("Synth Pop") == "synth-pop"
    assert canonicalize_tag("hiphop") == "hip-hop"
    assert canonicalize_tag("rap") == "hip-hop"
    assert canonicalize_tag("lofi") == "lo-fi"
    assert canonicalize_tag("classic-rock") == "classic rock"
    assert canonicalize_tag("unknown-genre") == "unknown-genre"


def test_build_text_template() -> None:
    """Verify semantic text template formatting and tag ordering."""
    tags = [
        {"name": "guitar", "weight": 0.5, "source": "recording"},
        {"name": "rock", "weight": 1.0, "source": "recording"},
        {"name": "70s", "weight": 0.7, "source": "recording"},
        {"name": "classic rock", "weight": 0.9, "source": "artist_fallback"},
    ]
    template = build_text_template("Bohemian Rhapsody", "Queen", 1975, tags)
    assert "genres: rock" in template
    assert "era: 1975" in template
    assert "artist tags: classic rock" in template


def test_deterministic_text_embeddings_invariants(
    sample_test_tracks: list[dict[str, Any]],
) -> None:
    """Verify that fallback text embeddings are deterministic and unit-normalized."""
    texts = [
        build_text_template(t["title"], t["artist_name"], t["year"], t["tags"])
        for t in sample_test_tracks
    ]

    vecs1 = compute_deterministic_text_embeddings(texts, dim=128, seed=42)
    vecs2 = compute_deterministic_text_embeddings(texts, dim=128, seed=42)

    # Determinism
    np.testing.assert_array_equal(vecs1, vecs2)
    assert vecs1.shape == (30, 128)

    # Unit norms
    norms = np.linalg.norm(vecs1, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    # No NaNs
    assert not np.isnan(vecs1).any()


def test_audio_channel_pca_and_missing_invariant(
    sample_test_tracks: list[dict[str, Any]],
) -> None:
    """Verify audio channel standardization, PCA variance retention, and missing-channel mask."""
    raw_audio = [extract_raw_audio_features(t.get("scalars")) for t in sample_test_tracks]
    vectors_a, has_a_mask, dim_a, explained_var = build_audio_channel(
        raw_audio,
        variance_threshold=0.90,
        max_dim=64,
    )

    assert dim_a <= 64
    assert explained_var >= 0.90
    assert vectors_a.shape == (30, dim_a)

    # Valid audio rows: unit norm
    for idx, valid in enumerate(has_a_mask):
        if valid:
            norm = np.linalg.norm(vectors_a[idx])
            assert abs(norm - 1.0) < 1e-4, f"Row {idx} has invalid norm {norm}"
        else:
            # Missing audio invariant: strictly all zeros
            assert np.all(vectors_a[idx] == 0.0), f"Row {idx} should be all zeros"


def test_interpretable_scalars_and_proxies(
    sample_test_tracks: list[dict[str, Any]],
) -> None:
    """Verify scalar calculations, ranges, and proxy naming (*_idx)."""
    scalars = compute_interpretable_scalars(sample_test_tracks)

    assert "tempo_norm" in scalars
    assert "danceability" in scalars
    assert "acousticness" in scalars
    assert "energy_idx" in scalars  # Documented proxy
    assert "valence_idx" in scalars  # Documented proxy
    assert "popularity_pct" in scalars
    assert "era" in scalars

    for k in ["tempo_norm", "danceability", "acousticness", "energy_idx", "valence_idx"]:
        arr = np.array(scalars[k])
        assert not np.isnan(arr).any()
        assert np.all(arr >= 0.0) and np.all(arr <= 1.0), f"{k} out of [0, 1] range: {arr}"

    pop = np.array(scalars["popularity_pct"])
    assert np.all(pop >= 0.0) and np.all(pop <= 100.0)


def test_tag_vocabulary_and_facet_vectors(
    sample_test_tracks: list[dict[str, Any]],
) -> None:
    """Verify tag vocabulary compilation, IDF calculation, and facet vectors."""
    texts = [
        build_text_template(t["title"], t["artist_name"], t["year"], t["tags"])
        for t in sample_test_tracks
    ]
    vecs_t = compute_deterministic_text_embeddings(texts, dim=128)

    vocab = build_tag_vocabulary(sample_test_tracks, vecs_t, top_k=50)

    assert "tags" in vocab
    assert "tag_to_idx" in vocab
    assert "tag_categories" in vocab
    assert "tag_df" in vocab
    assert "tag_idf" in vocab
    assert "facet_vectors" in vocab

    # Check synonym was canonicalized in vocab
    assert "synthpop" not in vocab["tags"]
    if "synth-pop" in vocab["tags"]:
        assert vocab["tag_categories"]["synth-pop"] == "genre"

    # Check facet vectors are unit-normalized
    for tag, fvec in vocab["facet_vectors"].items():
        arr = np.array(fvec, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0.0:
            assert abs(norm - 1.0) < 1e-4, f"Facet vector for '{tag}' norm {norm} != 1.0"


def test_bundle_determinism(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sample_test_tracks: list[dict[str, Any]],
) -> None:
    """Verify that building bundle twice with identical input yields identical SHA-256 hashes."""
    monkeypatch.setattr(
        "pipelines.build_features.load_staging_tracks_from_db",
        lambda *args, **kwargs: sample_test_tracks,
    )

    dir1 = tmp_path / "bundle_run_1"
    dir2 = tmp_path / "bundle_run_2"

    res1 = build_bundle(
        catalog_source="real",
        version="test_v1",
        output_dir=dir1,
        embedder_choice="hash",
        force=True,
    )
    res2 = build_bundle(
        catalog_source="real",
        version="test_v1",
        output_dir=dir2,
        embedder_choice="hash",
        force=True,
    )

    manifest1 = res1["manifest"]
    manifest2 = res2["manifest"]

    assert manifest1["source_hash"] == manifest2["source_hash"]
    for filename in manifest1["files"]:
        assert manifest1["files"][filename] == manifest2["files"][filename], (
            f"Hash mismatch for {filename}"
        )


def test_catalog_store_loading_and_invariants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sample_test_tracks: list[dict[str, Any]],
) -> None:
    """Verify that CatalogStore loads generated bundle and provides required lookups."""
    monkeypatch.setattr(
        "pipelines.build_features.load_staging_tracks_from_db",
        lambda *args, **kwargs: sample_test_tracks,
    )
    bundle_dir = tmp_path / "bundle_test"

    build_bundle(
        catalog_source="real",
        version="v1",
        output_dir=bundle_dir,
        embedder_choice="hash",
        force=True,
    )

    store = CatalogStore.load(bundle_dir)
    assert store.track_count == len(sample_test_tracks)
    assert store.vectors_t.shape == (len(sample_test_tracks), 128)
    assert store.scalars is not None
    assert "energy_idx" in store.scalars
    assert "valence_idx" in store.scalars

    # Index lookups
    tid = sample_test_tracks[0]["id"]
    idx = store.get_idx(tid)
    assert idx == 0
    assert store.get_id(0) == tid

    # Search
    results = store.search_tracks("Test Song", limit=5)
    assert len(results) > 0
    assert "scalars" in results[0]
    assert "energy_idx" in results[0]["scalars"]
