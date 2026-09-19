"""Master Feature & Embedding Pipeline for Melovia.

Produces an immutable, versioned vector catalog bundle complying with docs/BUNDLE_SPEC.md:
- Semantic taste vectors (t): Text template -> sentence-transformers (or deterministic hash embedder) -> L2 normalized
- Audio descriptor vectors (a): AcousticBrainz features -> per-source z-score standardization -> robust clipping [-4, 4] -> PCA (>=90% variance, <=64 dim) -> L2 normalized
- Missing audio invariant: Tracks without audio have has_a=False, zero vector row, and CatalogStore.mask_a[i]=False
- Interpretable scalars (scalars.parquet): tempo_norm, danceability, acousticness, energy_idx, valence_idx, era, popularity_pct
- Controlled tag vocabulary (tag_vocab.json): Top ~300 tags with synonyms merged, categories, IDF, and tag facet_vectors
- Planted/discovered cluster regions (regions.json): 12 musical regions with dual-channel centroids
- 3D Layout (layout3d.npy): Taste space projection for Three.js client visualization
- Checksum manifest (manifest.json): SHA-256 hashes of all bundle artifacts and build metadata
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import uuid

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# Add repo root and api to path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "api"))
sys.path.insert(0, str(repo_root))

SEED = 42
DEFAULT_VERSION = "v1"
DEFAULT_OUTPUT_DIR = repo_root / "data" / "bundles" / DEFAULT_VERSION
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_CACHE_DIR = repo_root / "data" / "cache" / "models"

# Controlled tag synonym mapping
SYNONYM_MAP: dict[str, str] = {
    "hiphop": "hip-hop",
    "rap": "hip-hop",
    "hip hop": "hip-hop",
    "synthpop": "synth-pop",
    "synth pop": "synth-pop",
    "postrock": "post-rock",
    "post rock": "post-rock",
    "lofi": "lo-fi",
    "lo-fi hip hop": "lo-fi",
    "chillhop": "lo-fi",
    "classic-rock": "classic rock",
    "classicrock": "classic rock",
    "rnb": "r&b",
    "r & b": "r&b",
    "edm": "electronic",
    "ambient electronic": "ambient",
    "drone ambient": "ambient",
    "darkwave": "dark wave",
    "modern classical": "neo-classical",
    "contemporary classical": "neo-classical",
    "indierock": "indie rock",
    "dreampop": "dream pop",
    "space rock": "psychedelic",
}

# Tag category heuristics
TAG_CATEGORIES: dict[str, str] = {
    # Genres
    "rock": "genre", "pop": "genre", "electronic": "genre", "hip-hop": "genre",
    "techno": "genre", "ambient": "genre", "folk": "genre", "jazz": "genre",
    "synth-pop": "genre", "post-rock": "genre", "dream pop": "genre", "indie rock": "genre",
    "metal": "genre", "neo-classical": "genre", "disco": "genre", "funk": "genre",
    "industrial": "genre", "lo-fi": "genre", "shoegaze": "genre", "psychedelic": "genre",
    "grunge": "genre", "punk": "genre", "soul": "genre", "r&b": "genre", "house": "genre",
    # Moods
    "relaxing": "mood", "energetic": "mood", "melancholy": "mood", "happy": "mood",
    "dark": "mood", "dreamy": "mood", "atmospheric": "mood", "meditative": "mood",
    "hypnotic": "mood", "aggressive": "mood", "chill": "mood", "nostalgic": "mood",
    "peaceful": "mood", "intimate": "mood", "cinematic": "mood", "uplifting": "mood",
    # Instruments
    "guitar": "instrument", "piano": "instrument", "strings": "instrument",
    "synth": "instrument", "drums": "instrument", "bass": "instrument", "acoustic": "instrument",
    # Eras
    "60s": "era", "70s": "era", "80s": "era", "90s": "era", "2000s": "era", "2010s": "era", "2020s": "era",
    # Vocals
    "instrumental": "vocal", "vocal": "vocal", "female vocal": "vocal", "male vocal": "vocal",
    # Scenes
    "club": "scene", "soundtrack": "scene", "underground": "scene", "crescendo": "scene",
}


def compute_sha256(filepath: Path) -> str:
    """Compute hex SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def svd_flip(u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ensure deterministic signs for SVD eigenvectors."""
    max_abs_cols = np.argmax(np.abs(u), axis=0)
    signs = np.sign(u[max_abs_cols, range(u.shape[1])])
    signs[signs == 0] = 1.0
    u *= signs
    v *= signs[:, np.newaxis]
    return u, v


def canonicalize_tag(tag: str) -> str:
    """Clean and map tag through synonym table."""
    cleaned = tag.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return SYNONYM_MAP.get(cleaned, cleaned)


def build_text_template(
    title: str,
    artist_name: str,
    year: int | None,
    tags: list[dict[str, Any]],
) -> str:
    """Build standardized semantic text template from track metadata."""
    genre_tags: list[str] = []
    other_tags: list[str] = []
    artist_tags: list[str] = []

    # Sort tags descending by weight
    sorted_tags = sorted(tags, key=lambda t: float(t.get("weight", 1.0)), reverse=True)

    for item in sorted_tags:
        tname = canonicalize_tag(item.get("name", ""))
        if not tname:
            continue
        source = item.get("source", "")
        category = TAG_CATEGORIES.get(tname, "other")

        if source == "artist_fallback":
            artist_tags.append(tname)
        elif category == "genre":
            genre_tags.append(tname)
        else:
            other_tags.append(tname)

    era_str = f"{year}" if year else "unknown"

    parts = []
    if genre_tags:
        parts.append(f"genres: {', '.join(genre_tags[:4])}")
    if other_tags:
        parts.append(f"tags: {', '.join(other_tags[:6])}")
    if era_str != "unknown":
        parts.append(f"era: {era_str}")
    if artist_tags:
        parts.append(f"artist tags: {', '.join(artist_tags[:3])}")

    if not parts:
        return f"title: {title}; artist: {artist_name}; era: {era_str}"

    return "; ".join(parts)


def compute_deterministic_text_embeddings(
    texts: list[str],
    dim: int = 128,
    seed: int = SEED,
) -> np.ndarray:
    """Fallback deterministic feature embedder using word n-grams and hashing.
    
    Used when sentence-transformers is unavailable or in fast offline test mode.
    Guarantees 100% determinism, unit norm, and semantic clustering of shared tokens.
    """
    rng = np.random.default_rng(seed)
    n = len(texts)
    vectors = np.zeros((n, dim), dtype=np.float32)

    # Random projection matrix for hashing word hashes
    proj = rng.normal(0.0, 1.0, size=(2048, dim)).astype(np.float32)

    for i, txt in enumerate(texts):
        words = re.findall(r"\b\w+\b", txt.lower())
        if not words:
            # Fallback pseudo-random unit vector
            v = rng.normal(0.0, 1.0, size=dim).astype(np.float32)
            vectors[i] = v / np.linalg.norm(v)
            continue

        vec = np.zeros(dim, dtype=np.float32)
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16) % 2048
            weight = 1.5 if ("rock" in w or "wave" in w or "techno" in w or "pop" in w) else 1.0
            vec += proj[h] * weight

        norm = np.linalg.norm(vec)
        vectors[i] = vec / (norm + 1e-12)

    return vectors


def compute_sentence_transformer_embeddings(
    texts: list[str],
    dim: int = 128,
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = 128,
) -> np.ndarray:
    """Compute semantic text embeddings using SentenceTransformer and PCA reduction."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError:
        print("[WARNING] sentence-transformers not installed; falling back to deterministic hashing embedder.")
        return compute_deterministic_text_embeddings(texts, dim=dim)

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(MODEL_CACHE_DIR)

    print(f"Loading SentenceTransformer model '{model_name}'...")
    model = SentenceTransformer(model_name, cache_folder=str(MODEL_CACHE_DIR))

    print(f"Encoding {len(texts)} texts in batches of {batch_size}...")
    raw_embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=False,
    )
    raw_embeddings = np.asarray(raw_embeddings, dtype=np.float32)

    # If raw dimension matches target dim, simply L2-normalize
    if raw_embeddings.shape[1] == dim:
        norms = np.linalg.norm(raw_embeddings, axis=1, keepdims=True)
        return raw_embeddings / np.maximum(norms, 1e-12)

    # Otherwise project to dim using PCA
    print(f"Reducing semantic embeddings from {raw_embeddings.shape[1]} to {dim} dimensions via PCA...")
    centered = raw_embeddings - np.mean(raw_embeddings, axis=0, keepdims=True)
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    u, vt = svd_flip(u, vt)
    projected = np.dot(centered, vt[:dim].T).astype(np.float32)

    # L2 normalize
    norms = np.linalg.norm(projected, axis=1, keepdims=True)
    return projected / np.maximum(norms, 1e-12)


def extract_raw_audio_features(scalars: dict[str, Any] | None) -> list[float] | None:
    """Extract standard raw numeric features from scalar dictionary for Channel a."""
    if not scalars:
        return None

    bpm = scalars.get("bpm") or scalars.get("tempo_bpm")
    energy = scalars.get("energy")
    valence = scalars.get("valence")
    danceability = scalars.get("danceability")
    acousticness = scalars.get("acousticness")
    instrumentalness = scalars.get("instrumentalness")
    loudness = scalars.get("loudness_db")

    if bpm is None and energy is None and danceability is None:
        return None

    # Defaults for missing individual sub-attributes
    f_bpm = float(np.clip(float(bpm) if bpm is not None else 115.0, 40.0, 240.0))
    f_energy = float(energy) if energy is not None else 0.50
    f_valence = float(valence) if valence is not None else 0.50
    f_dance = float(danceability) if danceability is not None else 0.50
    f_acoustic = float(acousticness) if acousticness is not None else (1.0 - f_energy)
    f_inst = float(instrumentalness) if instrumentalness is not None else 0.20
    f_loudness = float(np.clip(float(loudness) if loudness is not None else -12.0, -40.0, 0.0))

    return [f_bpm, f_energy, f_valence, f_dance, f_acoustic, f_inst, f_loudness]


def build_audio_channel(
    raw_feature_matrix: list[list[float] | None],
    variance_threshold: float = 0.90,
    max_dim: int = 64,
) -> tuple[np.ndarray, np.ndarray, int, float]:
    """Standardize, clip outliers, and PCA-reduce audio features.
    
    Returns:
    - vectors_a: (N, dim_a) float32 array
    - has_a_mask: (N,) bool array
    - dim_a: int
    - explained_variance: float
    """
    n_tracks = len(raw_feature_matrix)
    valid_indices = [i for i, feat in enumerate(raw_feature_matrix) if feat is not None]
    has_a_mask = np.zeros(n_tracks, dtype=bool)
    has_a_mask[valid_indices] = True

    if not valid_indices:
        # No audio features available at all
        dim_a = 8
        return np.zeros((n_tracks, dim_a), dtype=np.float32), has_a_mask, dim_a, 0.0

    X_valid = np.array([raw_feature_matrix[i] for i in valid_indices], dtype=np.float32)

    # 1. Per-source z-score standardization
    mean_vec = np.mean(X_valid, axis=0, keepdims=True)
    std_vec = np.std(X_valid, axis=0, keepdims=True)
    std_vec[std_vec < 1e-6] = 1.0

    Z = (X_valid - mean_vec) / std_vec

    # 2. Robust outlier clipping at [-4.0, 4.0]
    Z_clipped = np.clip(Z, -4.0, 4.0)

    # 3. PCA via SVD
    centered = Z_clipped - np.mean(Z_clipped, axis=0, keepdims=True)
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    u, vt = svd_flip(u, vt)

    # Variance explained
    var_explained = (s ** 2) / np.sum(s ** 2)
    cumsum_var = np.cumsum(var_explained)

    # Determine K dimensions retaining >= variance_threshold
    k = 1
    for idx, cv in enumerate(cumsum_var):
        if cv >= variance_threshold:
            k = idx + 1
            break
    k = min(k, max_dim, centered.shape[1])
    total_retained_var = float(cumsum_var[k - 1])

    # Project valid tracks
    A_valid = np.dot(centered, vt[:k].T).astype(np.float32)

    # L2-normalize valid rows
    norms = np.linalg.norm(A_valid, axis=1, keepdims=True)
    A_valid_norm = A_valid / np.maximum(norms, 1e-12)

    # Build full N x k matrix with zero rows for missing audio
    vectors_a = np.zeros((n_tracks, k), dtype=np.float32)
    for row_idx, orig_idx in enumerate(valid_indices):
        vectors_a[orig_idx] = A_valid_norm[row_idx]

    return vectors_a, has_a_mask, k, total_retained_var


def compute_interpretable_scalars(
    tracks: list[dict[str, Any]],
) -> dict[str, list[Any]]:
    """Compute normalized and proxy scalars conforming to docs/ML_DESIGN.md."""
    n = len(tracks)
    tempo_norm = np.zeros(n, dtype=np.float32)
    danceability = np.zeros(n, dtype=np.float32)
    acousticness = np.zeros(n, dtype=np.float32)
    energy_idx = np.zeros(n, dtype=np.float32)
    valence_idx = np.zeros(n, dtype=np.float32)
    era = np.zeros(n, dtype=np.int32)
    popularity_pct = np.zeros(n, dtype=np.float32)

    # Backward compatibility fields
    bpm_list = np.zeros(n, dtype=np.float32)
    loudness_list = np.zeros(n, dtype=np.float32)
    instrumentalness_list = np.zeros(n, dtype=np.float32)

    for i, t in enumerate(tracks):
        sc = t.get("scalars") or {}
        year = t.get("year") or 2000
        pop = float(t.get("popularity_pct", 50.0))

        raw_bpm = sc.get("bpm") or sc.get("tempo_bpm")
        f_bpm = float(raw_bpm) if raw_bpm is not None else 115.0
        f_energy = float(sc.get("energy", 0.50))
        f_valence = float(sc.get("valence", 0.50))
        f_dance = float(sc.get("danceability", 0.50))
        f_acoustic = float(sc.get("acousticness", 1.0 - f_energy))
        f_inst = float(sc.get("instrumentalness", 0.20))
        f_loud = float(sc.get("loudness_db", -12.0))

        # 1. tempo_norm: [0.0, 1.0]
        t_norm = np.clip((f_bpm - 50.0) / 150.0, 0.0, 1.0)

        # 2. loudness_norm: [0.0, 1.0] from [-30, 0] dB
        loud_norm = np.clip((f_loud + 30.0) / 30.0, 0.0, 1.0)

        # 3. energy_idx proxy:
        # energy_idx = 0.45 * energy + 0.35 * danceability + 0.20 * loudness_norm
        e_idx = np.clip(0.45 * f_energy + 0.35 * f_dance + 0.20 * loud_norm, 0.0, 1.0)

        # 4. valence_idx proxy:
        # valence_idx = 0.50 * valence + 0.25 * danceability + 0.25 * (1.0 - acousticness)
        v_idx = np.clip(0.50 * f_valence + 0.25 * f_dance + 0.25 * (1.0 - f_acoustic), 0.0, 1.0)

        tempo_norm[i] = float(t_norm)
        danceability[i] = float(f_dance)
        acousticness[i] = float(f_acoustic)
        energy_idx[i] = float(e_idx)
        valence_idx[i] = float(v_idx)
        era[i] = int(year)
        popularity_pct[i] = float(pop)

        bpm_list[i] = float(f_bpm)
        loudness_list[i] = float(f_loud)
        instrumentalness_list[i] = float(f_inst)

    return {
        "track_idx": list(range(n)),
        "tempo_norm": tempo_norm.tolist(),
        "danceability": danceability.tolist(),
        "acousticness": acousticness.tolist(),
        "energy_idx": energy_idx.tolist(),
        "valence_idx": valence_idx.tolist(),
        "era": era.tolist(),
        "popularity_pct": popularity_pct.tolist(),
        "bpm": bpm_list.tolist(),
        "tempo_bpm": bpm_list.tolist(),
        "energy": energy_idx.tolist(),
        "valence": valence_idx.tolist(),
        "loudness_db": loudness_list.tolist(),
        "instrumentalness": instrumentalness_list.tolist(),
    }


def build_tag_vocabulary(
    tracks: list[dict[str, Any]],
    vectors_t: np.ndarray,
    top_k: int = 300,
) -> dict[str, Any]:
    """Extract top tags, merge synonyms, compute IDF, and calculate facet vectors."""
    n_tracks = len(tracks)
    tag_counts: dict[str, int] = {}
    tag_track_indices: dict[str, list[int]] = {}

    for i, t in enumerate(tracks):
        raw_tags = t.get("tags") or []
        seen_tags_for_track: set[str] = set()
        for item in raw_tags:
            tname = canonicalize_tag(item.get("name", ""))
            if tname and len(tname) > 1 and tname not in seen_tags_for_track:
                seen_tags_for_track.add(tname)
                tag_counts[tname] = tag_counts.get(tname, 0) + 1
                if tname not in tag_track_indices:
                    tag_track_indices[tname] = []
                tag_track_indices[tname].append(i)

    # Sort tags by frequency
    sorted_tag_tuples = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)
    selected_tags = [t for t, count in sorted_tag_tuples[:top_k]]

    tag_to_idx = {tag: idx for idx, tag in enumerate(selected_tags)}
    tag_categories: dict[str, str] = {}
    tag_df: dict[str, int] = {}
    tag_idf: dict[str, float] = {}
    facet_vectors: dict[str, list[float]] = {}

    for tag in selected_tags:
        df = tag_counts[tag]
        tag_df[tag] = df
        tag_idf[tag] = round(math.log(n_tracks / (1.0 + df)) + 1.0, 4)
        tag_categories[tag] = TAG_CATEGORIES.get(tag, "genre" if "rock" in tag or "pop" in tag or "wave" in tag else "mood")

        # Compute facet vector (mean t-vector across carrying tracks)
        indices = tag_track_indices[tag]
        if indices:
            sub_vectors = vectors_t[indices]
            mean_vec = np.mean(sub_vectors, axis=0)
            norm = np.linalg.norm(mean_vec)
            if norm > 1e-12:
                mean_vec /= norm
            facet_vectors[tag] = [round(float(x), 6) for x in mean_vec]
        else:
            facet_vectors[tag] = [0.0] * vectors_t.shape[1]

    return {
        "tags": selected_tags,
        "tag_to_idx": tag_to_idx,
        "tag_categories": tag_categories,
        "tag_df": tag_df,
        "tag_idf": tag_idf,
        "facet_vectors": facet_vectors,
    }


def build_regions(
    vectors_t: np.ndarray,
    vectors_a: np.ndarray,
    tracks: list[dict[str, Any]],
    n_regions: int = 12,
    seed: int = SEED,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """Form 12 musical regions with centroids and assign each track to a region."""
    n_tracks = len(tracks)
    dim_t = vectors_t.shape[1]
    dim_a = vectors_a.shape[1]

    # Deterministic k-means clustering in taste space
    rng = np.random.default_rng(seed)
    # Pick 12 deterministic diverse initial seeds
    initial_indices = rng.choice(n_tracks, size=n_regions, replace=False)
    centers_t = vectors_t[initial_indices].copy()

    region_assignments = np.zeros(n_tracks, dtype=np.int32)

    # 10 iterations of spherical k-means
    for _ in range(10):
        # Assign to nearest cosine center
        similarities = np.dot(vectors_t, centers_t.T)
        region_assignments = np.argmax(similarities, axis=1).astype(np.int32)

        # Update centers
        for r in range(n_regions):
            mask = region_assignments == r
            if np.any(mask):
                new_c = np.mean(vectors_t[mask], axis=0)
                norm = np.linalg.norm(new_c)
                if norm > 1e-12:
                    centers_t[r] = new_c / norm

    # Region audio centers and top tags
    regions_payload = []
    names = [
        "Neon Nocturne", "Ethereal Dream Pop", "Post-Rock Horizons",
        "Cerebral Techno", "Lo-Fi Midnight", "Acoustic Folk Noir",
        "Ambient Solitude", "Nu-Jazz Fusion", "Dark Industrial",
        "Math Rock Resonance", "Psychedelic Mirage", "Neo-Classical Echoes",
    ]
    focuses = [
        "Synthwave / Dark Electro", "Dream Pop / Shoegaze", "Post-Rock / Cinematic",
        "Minimal / Deep Techno", "Lo-Fi Hip Hop / Chillhop", "Dark Folk / Indie Acoustic",
        "Drone / Ambient", "Nu-Jazz / Broken Beat", "Industrial / EBM",
        "Math Rock / Midwest Emo", "Neo-Psychedelia / Space Rock", "Contemporary Classical",
    ]
    descriptions = [
        "Driving synthesized arpeggios with nostalgic 80s aesthetics.",
        "Lush, reverberant textures, washed guitars, and gentle melancholy.",
        "Dynamic crescendo-driven instrumental rock exploring expansive dynamics.",
        "Hypnotic, repetitious, sub-heavy electronic pulse designed for deep focus.",
        "Warm tape saturation, dusty jazz piano loops, and relaxed beats.",
        "Intimate fingerpicked guitars, raw acoustics, and brooding storytelling.",
        "Beatless, evolving acoustic and modular soundscapes fostering stillness.",
        "Complex syncopation, warm rhodes keyboards, and contemporary groove.",
        "Aggressive mechanical rhythms, metallic percussion, and distortion.",
        "Angular guitar tapping, odd time signatures, and emotive melodic hooks.",
        "Swirling phasers, motorik grooves, and cosmic analog synthesis.",
        "Felted piano, intimate string quartets, and subtle tape delay treatments.",
    ]

    for r in range(n_regions):
        mask = region_assignments == r
        # Center in audio space
        if np.any(mask):
            sub_a = vectors_a[mask]
            center_a = np.mean(sub_a, axis=0)
            norm_a = np.linalg.norm(center_a)
            if norm_a > 1e-12:
                center_a /= norm_a
        else:
            center_a = np.zeros(dim_a, dtype=np.float32)

        # Top tags in region
        reg_tag_counts: dict[str, int] = {}
        for idx in np.where(mask)[0]:
            for tag_item in tracks[idx].get("tags", []):
                tname = canonicalize_tag(tag_item.get("name", ""))
                if tname:
                    reg_tag_counts[tname] = reg_tag_counts.get(tname, 0) + 1
        top_tags = [t for t, _ in sorted(reg_tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]]

        regions_payload.append({
            "region_id": r,
            "name": names[r % len(names)],
            "genre_focus": focuses[r % len(focuses)],
            "description": descriptions[r % len(descriptions)],
            "center_t": [round(float(x), 6) for x in centers_t[r]],
            "center_a": [round(float(x), 6) for x in center_a],
            "top_tags": top_tags or ["music"],
        })

    return regions_payload, region_assignments


def build_3d_layout(vectors_t: np.ndarray, seed: int = SEED) -> np.ndarray:
    """Project taste space down to 3 dimensions for Three.js client visualization."""
    centered = vectors_t - np.mean(vectors_t, axis=0, keepdims=True)
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    u, vt = svd_flip(u, vt)
    layout = np.dot(centered, vt[:3].T).astype(np.float32)

    # Scale to [-10.0, 10.0]
    std = float(np.std(layout))
    if std > 1e-6:
        layout = (layout / std) * 3.0
    return layout


def compute_catalog_input_hash(tracks: list[dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 hash of raw input tracks."""
    hasher = hashlib.sha256()
    for t in tracks:
        row_str = f"{t.get('id')}|{t.get('mbid')}|{t.get('title')}|{t.get('artist_name')}|{t.get('year')}|{json.dumps(t.get('tags'), sort_keys=True)}|{json.dumps(t.get('scalars'), sort_keys=True)}"
        hasher.update(row_str.encode("utf-8"))
    return hasher.hexdigest()


def check_existing_bundle_intact(
    output_dir: Path,
    expected_input_hash: str,
) -> bool:
    """Check if bundle exists, is valid, and matches input hash."""
    manifest_file = output_dir / "manifest.json"
    if not manifest_file.exists():
        return False

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        if manifest.get("source_hash") != expected_input_hash:
            return False

        files = manifest.get("files", {})
        for rel_name, expected_sha in files.items():
            fpath = output_dir / rel_name
            if not fpath.exists():
                return False
            if compute_sha256(fpath).lower() != expected_sha.lower():
                return False
        return True
    except Exception:
        return False


def load_staging_tracks_from_db(db_url: str | None = None) -> list[dict[str, Any]]:
    """Load all staging tracks from database ordered deterministically."""
    import asyncio

    if db_url:
        os.environ["DATABASE_URL"] = db_url
    elif "DATABASE_URL" not in os.environ:
        sqlite_db = repo_root / "melovia.db"
        if sqlite_db.exists():
            os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{sqlite_db.as_posix()}"

    from sqlalchemy import select
    from app.db import StagingTrack
    from app.db.session import async_session_factory

    async def _fetch() -> list[dict[str, Any]]:
        async with async_session_factory() as session:
            stmt = select(StagingTrack).order_by(StagingTrack.title, StagingTrack.artist_name, StagingTrack.id)
            result = await session.execute(stmt)
            tracks_orm = result.scalars().all()

            records: list[dict[str, Any]] = []
            for tr in tracks_orm:
                records.append({
                    "id": tr.id,
                    "mbid": tr.mbid,
                    "title": tr.title,
                    "artist_name": tr.artist_name,
                    "artist_mbid": tr.artist_mbid,
                    "year": tr.year,
                    "isrcs": tr.isrcs,
                    "popularity_pct": tr.popularity_pct,
                    "has_a": tr.has_a,
                    "has_t": tr.has_t,
                    "tags": tr.tags,
                    "scalars": tr.scalars,
                    "source": tr.source,
                })
            return records

    return asyncio.run(_fetch())


def build_bundle(
    catalog_source: str = "real",
    version: str = DEFAULT_VERSION,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    embedder_choice: str = "sentence-transformers",
    dim_t: int = 128,
    variance_threshold: float = 0.90,
    force: bool = False,
) -> dict[str, Any]:
    """Execute complete feature engineering and bundle creation pipeline."""
    start_time = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Melovia Feature & Embedding Pipeline (Catalog: {catalog_source}, Version: {version}) ===")

    # 1. Load Tracks
    if catalog_source == "mock":
        from fixtures.make_mock_catalog import generate_mock_catalog
        print(f"Generating mock catalog in {output_dir}...")
        hashes = generate_mock_catalog(output_dir)
        return {"status": "success", "catalog": "mock", "files": hashes}

    print("Loading tracks from database staging_tracks table...")
    tracks = load_staging_tracks_from_db()
    if not tracks:
        raise ValueError("staging_tracks table is empty! Please run `make ingest-sample` first.")

    n_tracks = len(tracks)
    print(f"Loaded {n_tracks} tracks from staging catalog.")

    # 2. Incremental check
    input_hash = compute_catalog_input_hash(tracks)
    if not force and check_existing_bundle_intact(output_dir, input_hash):
        print(f"[INFO] Catalog input hash ({input_hash[:12]}) matches existing bundle manifest at {output_dir}.")
        print("[INFO] Bundle is completely intact; skipping rebuild. (Use --force to rebuild).")
        with open(output_dir / "manifest.json", "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        return {"status": "skipped", "reason": "unmodified", "manifest": manifest_data}

    # 3. Channel t: Semantic Text Embeddings
    print("Building text representations for Channel t...")
    texts = [
        build_text_template(
            title=t["title"],
            artist_name=t["artist_name"],
            year=t.get("year"),
            tags=t.get("tags") or [],
        )
        for t in tracks
    ]

    if embedder_choice == "sentence-transformers":
        vectors_t = compute_sentence_transformer_embeddings(texts, dim=dim_t)
    else:
        vectors_t = compute_deterministic_text_embeddings(texts, dim=dim_t)

    # Invariants verification for Channel t
    assert not np.isnan(vectors_t).any(), "Channel t vectors contain NaNs!"
    norms_t = np.linalg.norm(vectors_t, axis=1)
    assert np.allclose(norms_t, 1.0, atol=1e-4), "Channel t vectors must be unit-normalized!"
    print(f"Channel t complete: shape {vectors_t.shape}, unit normalized.")

    # 4. Channel a: Audio Descriptors
    print("Extracting and standardizing audio features for Channel a...")
    raw_audio = [extract_raw_audio_features(t.get("scalars")) for t in tracks]
    vectors_a, has_a_mask, dim_a, explained_var = build_audio_channel(
        raw_audio,
        variance_threshold=variance_threshold,
        max_dim=64,
    )

    # Invariants verification for Channel a
    assert not np.isnan(vectors_a).any(), "Channel a vectors contain NaNs!"
    for i in range(n_tracks):
        if has_a_mask[i]:
            norm_val = np.linalg.norm(vectors_a[i])
            assert abs(norm_val - 1.0) < 1e-4, f"Valid audio row {i} norm is {norm_val} != 1.0"
        else:
            assert np.all(vectors_a[i] == 0.0), f"Missing audio row {i} must be all zeros!"
    print(f"Channel a complete: shape {vectors_a.shape}, retained variance {explained_var*100:.2f}%, audio coverage {np.mean(has_a_mask)*100:.1f}%.")

    # 5. Interpretable Scalars
    print("Computing interpretable scalars and proxy indices...")
    scalars_dict = compute_interpretable_scalars(tracks)

    # 6. Tag Vocabulary with Facet Vectors
    print("Building controlled tag vocabulary with IDF and facet vectors...")
    tag_vocab = build_tag_vocabulary(tracks, vectors_t, top_k=300)

    # 7. Cluster Regions
    print("Discovering cluster regions and dual-channel centroids...")
    regions_payload, region_assignments = build_regions(vectors_t, vectors_a, tracks, n_regions=12)

    # 8. 3D Layout
    print("Projecting 3D visualization layout...")
    layout3d = build_3d_layout(vectors_t)

    # 9. Build tracks.parquet
    print("Writing tracks.parquet...")
    track_rows: list[dict[str, Any]] = []
    for i, t in enumerate(tracks):
        art_mbid = t.get("artist_mbid") or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"art.{t['artist_name']}"))
        isrcs_val = t.get("isrcs") or []
        track_tags_list = [canonicalize_tag(item.get("name", "")) for item in (t.get("tags") or []) if item.get("name")]
        track_rows.append({
            "track_idx": i,
            "id": t["id"],
            "mbid": t.get("mbid"),
            "title": t["title"],
            "artist_id": art_mbid,
            "artist_name": t["artist_name"],
            "year": t.get("year"),
            "isrc": isrcs_val[0] if isrcs_val else "",
            "isrcs": isrcs_val,
            "popularity_pct": float(t.get("popularity_pct", 50.0)),
            "has_a": bool(has_a_mask[i]),
            "has_t": True,
            "region_id": int(region_assignments[i]),
            "tags": track_tags_list,
        })

    tracks_table = pa.Table.from_pylist(track_rows)
    pq.write_table(tracks_table, output_dir / "tracks.parquet")

    # 10. Write arrays and JSON files
    np.save(output_dir / "vectors_t.npy", vectors_t.astype(np.float32))
    np.save(output_dir / "vectors_a.npy", vectors_a.astype(np.float32))
    np.save(output_dir / "layout3d.npy", layout3d.astype(np.float32))

    scalars_table = pa.table({k: pa.array(v) for k, v in scalars_dict.items()})
    pq.write_table(scalars_table, output_dir / "scalars.parquet")

    with open(output_dir / "tag_vocab.json", "w", encoding="utf-8") as f:
        json.dump(tag_vocab, f, indent=2)

    with open(output_dir / "regions.json", "w", encoding="utf-8") as f:
        json.dump(regions_payload, f, indent=2)

    # 11. Manifest Checksums
    bundle_files = [
        "tracks.parquet",
        "vectors_t.npy",
        "vectors_a.npy",
        "scalars.parquet",
        "tag_vocab.json",
        "regions.json",
        "layout3d.npy",
    ]

    files_hashes: dict[str, str] = {}
    for filename in bundle_files:
        filepath = output_dir / filename
        files_hashes[filename] = compute_sha256(filepath)

    manifest_data = {
        "version": version,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "plan": catalog_source,
        "track_count": n_tracks,
        "dim_t": dim_t,
        "dim_a": dim_a,
        "pca_variance_ratio": round(explained_var, 4),
        "source_hash": input_hash,
        "files": files_hashes,
    }

    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    duration = time.perf_counter() - start_time
    print(f"=== Successfully built bundle '{version}' at {output_dir} in {duration:.2f}s ===")
    print(f"Tracks: {n_tracks} | dim_t: {dim_t} | dim_a: {dim_a} (var={explained_var*100:.1f}%) | tags: {len(tag_vocab['tags'])}")

    return {
        "status": "success",
        "version": version,
        "track_count": n_tracks,
        "dim_t": dim_t,
        "dim_a": dim_a,
        "duration": duration,
        "manifest": manifest_data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Melovia feature vectors and versioned bundle.")
    parser.add_argument("--catalog", choices=["real", "mock"], default="real", help="Catalog source (default: real)")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Bundle version identifier (default: v1)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--embedder", choices=["sentence-transformers", "hash"], default="sentence-transformers", help="Channel t embedder")
    parser.add_argument("--dim-t", type=int, default=128, help="Channel t vector dimension (default 128)")
    parser.add_argument("--variance-threshold", type=float, default=0.90, help="PCA minimum explained variance (default 0.90)")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if input checksum matches")
    args = parser.parse_args()

    build_bundle(
        catalog_source=args.catalog,
        version=args.version,
        output_dir=args.output_dir,
        embedder_choice=args.embedder,
        dim_t=args.dim_t,
        variance_threshold=args.variance_threshold,
        force=args.force,
    )


if __name__ == "__main__":
    main()
