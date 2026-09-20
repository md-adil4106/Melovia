"""Deterministic Mock Catalog Bundle Generator for Melovia.

Produces a versioned vector catalog bundle complying with docs/BUNDLE_SPEC.md:
- Seed: 42 (deterministic across runs)
- 3,000 tracks
- ~400 artists
- 12 planted musical regions with 128-d centroids
- Long-tail popularity distribution
- Exactly 5% missing channel a (150 tracks with has_a=False, zero vector)
- Generates all bundle files and computes sha256 checksums for manifest.json.
"""

import argparse
import hashlib
import json
from pathlib import Path
import uuid

from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

SEED = 42
TRACK_COUNT = 3000
ARTIST_COUNT = 400
DIM_T = 128
DIM_A = 128
MISSING_A_RATIO = 0.05  # Exactly 5% (150 tracks)

REGIONS_DEF: list[dict[str, Any]] = [
    {
        "region_id": 0,
        "name": "Neon Nocturne",
        "genre_focus": "Synthwave / Dark Electro",
        "description": "Driving synthesized arpeggios with nostalgic 80s aesthetics.",
        "bpm_range": (110, 130),
        "energy_mean": 0.80,
        "valence_mean": 0.65,
        "top_tags": ["synthwave", "retrowave", "electronic", "nostalgic", "cyberpunk"],
    },
    {
        "region_id": 1,
        "name": "Ethereal Drift",
        "genre_focus": "Dream Pop / Shoegaze",
        "description": "Lush, reverberant textures, washed guitars, and gentle melancholy.",
        "bpm_range": (85, 115),
        "energy_mean": 0.45,
        "valence_mean": 0.40,
        "top_tags": ["dream-pop", "shoegaze", "ethereal", "indie", "ambient-pop"],
    },
    {
        "region_id": 2,
        "name": "Cinematic Horizons",
        "genre_focus": "Post-Rock / Instrumental",
        "description": "Dynamic crescendo-driven instrumental rock exploring expansive dynamics.",
        "bpm_range": (70, 110),
        "energy_mean": 0.60,
        "valence_mean": 0.35,
        "top_tags": ["post-rock", "cinematic", "instrumental", "crescendo", "atmospheric"],
    },
    {
        "region_id": 3,
        "name": "Deep Chamber",
        "genre_focus": "Minimal Techno / Microhouse",
        "description": "Hypnotic, repetitious, sub-heavy electronic pulse designed for deep focus.",
        "bpm_range": (125, 135),
        "energy_mean": 0.75,
        "valence_mean": 0.30,
        "top_tags": ["techno", "minimal", "deep-techno", "electronic", "hypnotic"],
    },
    {
        "region_id": 4,
        "name": "Faded Cassette",
        "genre_focus": "Lo-Fi Beats / Chillhop",
        "description": "Warm tape saturation, dusty jazz piano loops, and relaxed beats.",
        "bpm_range": (75, 90),
        "energy_mean": 0.35,
        "valence_mean": 0.55,
        "top_tags": ["lo-fi", "chillhop", "hip-hop", "relaxing", "study-beats"],
    },
    {
        "region_id": 5,
        "name": "Solar Groove",
        "genre_focus": "Nu-Disco / French Touch",
        "description": "Funky compressed basslines, bright sweeping phasers, and euphoric dancefloor energy.",
        "bpm_range": (115, 128),
        "energy_mean": 0.85,
        "valence_mean": 0.80,
        "top_tags": ["nu-disco", "french-touch", "funk", "disco", "dance"],
    },
    {
        "region_id": 6,
        "name": "Sacred Timber",
        "genre_focus": "Nordic Folk / Dark Ambient",
        "description": "Traditional bowed strings, resonant frame drums, and atmospheric nature recordings.",
        "bpm_range": (60, 90),
        "energy_mean": 0.35,
        "valence_mean": 0.30,
        "top_tags": ["nordic-folk", "dark-ambient", "folk", "acoustic", "drone"],
    },
    {
        "region_id": 7,
        "name": "Analog Odyssey",
        "genre_focus": "Berlin School / Krautrock",
        "description": "Extended modular sequencer patterns, vintage Moog leads, and cosmic motorik rhythms.",
        "bpm_range": (110, 130),
        "energy_mean": 0.65,
        "valence_mean": 0.60,
        "top_tags": ["berlin-school", "krautrock", "analog", "modular", "cosmic"],
    },
    {
        "region_id": 8,
        "name": "Dusk Reverie",
        "genre_focus": "Indie Folk / Chamber Acoustic",
        "description": "Intimate fingerpicked acoustic guitars, upright bass, and delicate vocal arrangements.",
        "bpm_range": (90, 120),
        "energy_mean": 0.30,
        "valence_mean": 0.25,
        "top_tags": ["folk", "acoustic", "indie-folk", "intimate", "dark-folk"],
    },
    {
        "region_id": 9,
        "name": "Subterranean Bass",
        "genre_focus": "UK Garage / Future Garage",
        "description": "Syncopated 2-step rhythms, pitched vocal chops, and deep oceanic sub-frequencies.",
        "bpm_range": (130, 140),
        "energy_mean": 0.75,
        "valence_mean": 0.45,
        "top_tags": ["garage", "future-garage", "bass", "2-step", "dubstep"],
    },
    {
        "region_id": 10,
        "name": "Polyphonic Pulse",
        "genre_focus": "Math Rock / Midwest Emo",
        "description": "Angular guitar tapping, odd time signatures, and emotive melodic hooks.",
        "bpm_range": (115, 145),
        "energy_mean": 0.70,
        "valence_mean": 0.50,
        "top_tags": ["math-rock", "midwest-emo", "twinkle", "indie-rock", "complex"],
    },
    {
        "region_id": 11,
        "name": "Infinite Drone",
        "genre_focus": "Drone Ambient / Contemporary Classical",
        "description": "Beatless, evolving acoustic and modular soundscapes fostering stillness.",
        "bpm_range": (50, 75),
        "energy_mean": 0.15,
        "valence_mean": 0.40,
        "top_tags": ["ambient", "drone", "meditative", "soundscape", "minimalist"],
    },
    {
        "region_id": 12,
        "name": "Glitch & Resonance",
        "genre_focus": "IDM / Glitch Ambient",
        "description": "Intricate micro-percussion, warm analog distortion, and evolving generative pads.",
        "bpm_range": (95, 125),
        "energy_mean": 0.55,
        "valence_mean": 0.45,
        "top_tags": ["idm", "glitch", "ambient", "electronic", "experimental"],
    },
    {
        "region_id": 13,
        "name": "Velvet Groove",
        "genre_focus": "Neo-Soul / Acid Jazz",
        "description": "Silky electric piano chords, syncopated jazz swing, and warm basslines.",
        "bpm_range": (85, 105),
        "energy_mean": 0.55,
        "valence_mean": 0.70,
        "top_tags": ["neo-soul", "jazz", "soul", "groove", "smooth"],
    },
    {
        "region_id": 14,
        "name": "Industrial Monolith",
        "genre_focus": "Dark Techno / EBM",
        "description": "Aggressive mechanical rhythms, metallic percussion, and distortion.",
        "bpm_range": (120, 140),
        "energy_mean": 0.90,
        "valence_mean": 0.20,
        "top_tags": ["industrial", "ebm", "darkwave", "heavy", "mechanical"],
    },
    {
        "region_id": 15,
        "name": "Desert Mirage",
        "genre_focus": "Psych Rock / Desert Blues",
        "description": "Fuzzy pentatonic riffs, hypnotic hand drums, and sun-baked psychedelic reverbs.",
        "bpm_range": (105, 125),
        "energy_mean": 0.65,
        "valence_mean": 0.60,
        "top_tags": ["psychedelic", "space-rock", "desert-rock", "fuzzy", "blues"],
    },
    {
        "region_id": 16,
        "name": "Hyper-Echo",
        "genre_focus": "Dub Techno / Deep Ambient",
        "description": "Infinite tape-delay chords, cavernous reverb washes, and gentle rhythmic propulsion.",
        "bpm_range": (115, 125),
        "energy_mean": 0.50,
        "valence_mean": 0.35,
        "top_tags": ["dub-techno", "deep-ambient", "echo", "reverb", "electronic"],
    },
    {
        "region_id": 17,
        "name": "Cloud Mirage",
        "genre_focus": "Ambient Trap / Cloud Rap",
        "description": "Spacious pitched-down synth pads, skittering hi-hats, and hazy sub-bass atmospheres.",
        "bpm_range": (120, 140),
        "energy_mean": 0.45,
        "valence_mean": 0.50,
        "top_tags": ["trap", "cloud-rap", "ambient", "chill", "atmospheric"],
    },
    {
        "region_id": 18,
        "name": "Midnight Bop",
        "genre_focus": "Modal Jazz / Hard Bop",
        "description": "Acoustic upright bass walks, swinging brush drums, and expressive brass interplay.",
        "bpm_range": (110, 160),
        "energy_mean": 0.65,
        "valence_mean": 0.60,
        "top_tags": ["jazz", "hard-bop", "acoustic", "swing", "brass"],
    },
    {
        "region_id": 19,
        "name": "Static & Rust",
        "genre_focus": "Noise Pop / Post-Punk",
        "description": "Angular basslines, motorik drumming, and waves of intentional feedback.",
        "bpm_range": (125, 150),
        "energy_mean": 0.80,
        "valence_mean": 0.40,
        "top_tags": ["post-punk", "noise-rock", "indie", "raw", "motorik"],
    },
    {
        "region_id": 20,
        "name": "Baroque Twilight",
        "genre_focus": "Chamber Pop / Art Pop",
        "description": "Orchestral woodwinds, harpsichord accents, and eccentric avant-pop melodies.",
        "bpm_range": (70, 105),
        "energy_mean": 0.40,
        "valence_mean": 0.45,
        "top_tags": ["chamber-pop", "art-pop", "orchestral", "baroque", "indie"],
    },
    {
        "region_id": 21,
        "name": "Vapor Echoes",
        "genre_focus": "Vaporwave / Slushwave",
        "description": "Slowed mall-soft saxophone melodies, phaser-laden funk chops, and nostalgic dreamscapes.",
        "bpm_range": (70, 95),
        "energy_mean": 0.35,
        "valence_mean": 0.65,
        "top_tags": ["vaporwave", "slushwave", "chill", "retro", "nostalgic"],
    },
    {
        "region_id": 22,
        "name": "Galactic Bass",
        "genre_focus": "Neurofunk / Liquid Drum & Bass",
        "description": "Fast breakbeats, liquid Rhodes pads, and heavily modulated neuro bass lines.",
        "bpm_range": (170, 175),
        "energy_mean": 0.90,
        "valence_mean": 0.55,
        "top_tags": ["dnb", "neurofunk", "liquid", "bass", "fast"],
    },
    {
        "region_id": 23,
        "name": "Acoustic Solitude",
        "genre_focus": "Solo Acoustic / Primitive Guitar",
        "description": "Resonant open-tuned steel strings, alternating thumb bass, and woody room presence.",
        "bpm_range": (60, 95),
        "energy_mean": 0.25,
        "valence_mean": 0.35,
        "top_tags": ["acoustic", "guitar", "folk", "solo", "intimate"],
    },
]

ARTIST_FIRST = [
    "Solar", "Lunar", "Velvet", "Neon", "Silent", "Echo", "Subtle", "Prism",
    "Atlas", "Ghost", "Stellar", "Cosmic", "Vivid", "Static", "Silver", "Crimson",
    "Amber", "Azure", "Shadow", "Mirage", "Quantum", "Hollow", "Infinite", "Fading",
]
ARTIST_SECOND = [
    "Drift", "Tides", "Signals", "Horizon", "Collective", "Monolith", "Currents",
    "Orchestra", "Frequency", "Chamber", "Waves", "Circuit", "Echo", "Shade",
    "Pulse", "Fables", "Visions", "Theory", "Transit", "Machines", "Bloom", "Path",
]

TITLE_NOUNS = [
    "Memory", "Frequency", "Reflection", "Horizon", "Ascent", "Descent", "Silence",
    "Circuit", "Echo", "Tides", "Shadow", "Starlight", "Orbit", "Gravity", "Paradox",
    "Resonance", "Pulse", "Mirage", "Vapor", "Cascade", "Glitch", "Solitude", "Passage",
]
TITLE_MODIFIERS = [
    "Deep", "Endless", "Fading", "First", "Final", "Inner", "Lost", "Quiet",
    "Hidden", "Fractured", "Distant", "Electric", "Submerged", "Ancient", "Floating",
]


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_mock_catalog(output_dir: Path) -> dict[str, str]:
    """Generate deterministic mock catalog files in output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    # 1. Generate 400 deterministic Artists
    artists = []
    for i in range(ARTIST_COUNT):
        art_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"melovia.artist.{i}"))
        mbid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mb.artist.{i}"))
        first = ARTIST_FIRST[i % len(ARTIST_FIRST)]
        second = ARTIST_SECOND[(i // len(ARTIST_FIRST)) % len(ARTIST_SECOND)]
        suffix = f" {i // (len(ARTIST_FIRST) * len(ARTIST_SECOND)) + 1}" if i >= len(ARTIST_FIRST) * len(ARTIST_SECOND) else ""
        name = f"{first} {second}{suffix}"
        artists.append({
            "id": art_uuid,
            "name": name,
            "mbid": mbid,
        })

    # Artist popularity distribution (Zipf / Pareto for artist track counts)
    artist_weights = rng.pareto(a=1.5, size=ARTIST_COUNT) + 0.1
    artist_probs = artist_weights / np.sum(artist_weights)

    # 2. Plant 12 Region Centroids (Taste & Audio)
    region_centers_t = rng.normal(loc=0.0, scale=1.0, size=(len(REGIONS_DEF), DIM_T)).astype(np.float32)
    region_centers_t /= np.linalg.norm(region_centers_t, axis=1, keepdims=True)

    region_centers_a = rng.normal(loc=0.0, scale=1.0, size=(len(REGIONS_DEF), DIM_A)).astype(np.float32)
    region_centers_a /= np.linalg.norm(region_centers_a, axis=1, keepdims=True)

    # 3. Controlled Tag Vocabulary
    all_tags: set[str] = set()
    tag_categories: dict[str, str] = {}
    for r in REGIONS_DEF:
        for t in r["top_tags"]:
            all_tags.add(t)
            tag_categories[t] = "genre" if ("wave" in t or "rock" in t or "pop" in t or "jazz" in t or "techno" in t or "folk" in t) else "mood"

    sorted_tags = sorted(list(all_tags))
    tag_to_idx = {tag: idx for idx, tag in enumerate(sorted_tags)}
    tag_vocab = {
        "tags": sorted_tags,
        "tag_to_idx": tag_to_idx,
        "tag_categories": tag_categories,
    }

    # Save regions.json
    regions_payload = []
    for r_idx, r in enumerate(REGIONS_DEF):
        regions_payload.append({
            "region_id": r["region_id"],
            "name": r["name"],
            "genre_focus": r["genre_focus"],
            "description": r["description"],
            "center_t": [round(float(x), 6) for x in region_centers_t[r_idx]],
            "center_a": [round(float(x), 6) for x in region_centers_a[r_idx]],
            "top_tags": r["top_tags"],
        })

    regions_file = output_dir / "regions.json"
    with open(regions_file, "w", encoding="utf-8") as f:
        json.dump(regions_payload, f, indent=2)

    tag_vocab_file = output_dir / "tag_vocab.json"
    with open(tag_vocab_file, "w", encoding="utf-8") as f:
        json.dump(tag_vocab, f, indent=2)

    # 4. Generate 3,000 Tracks
    # Plant exactly 250 tracks per region
    tracks_per_region = TRACK_COUNT // len(REGIONS_DEF)
    region_assignments = np.repeat(np.arange(len(REGIONS_DEF)), tracks_per_region)
    # Shuffle assignments deterministically
    rng.shuffle(region_assignments)

    # Select artist for each track using artist_probs
    track_artist_indices = rng.choice(ARTIST_COUNT, size=TRACK_COUNT, p=artist_probs)

    # Long-tail popularity (0 to 100)
    raw_pop = rng.exponential(scale=18.0, size=TRACK_COUNT)
    popularity_pct = np.clip(raw_pop + 5.0, 1.0, 99.5).astype(np.float32)

    # Missing channel a: exactly 5% (150 tracks)
    # We choose every 20th track (indices 19, 39, ..., 2999)
    missing_a_indices = set(range(19, TRACK_COUNT, 20))
    assert len(missing_a_indices) == 150, f"Expected 150 missing a tracks, got {len(missing_a_indices)}"

    has_a_list = [i not in missing_a_indices for i in range(TRACK_COUNT)]
    has_t_list = [True] * TRACK_COUNT

    # Generate Embeddings
    vectors_t = np.zeros((TRACK_COUNT, DIM_T), dtype=np.float32)
    vectors_a = np.zeros((TRACK_COUNT, DIM_A), dtype=np.float32)

    for i in range(TRACK_COUNT):
        reg = region_assignments[i]
        # Sample taste vector around region center
        noise_t = rng.normal(loc=0.0, scale=0.04, size=DIM_T).astype(np.float32)
        vec_t = region_centers_t[reg] + noise_t
        vec_t /= np.linalg.norm(vec_t)
        vectors_t[i] = vec_t

        if has_a_list[i]:
            noise_a = rng.normal(loc=0.0, scale=0.05, size=DIM_A).astype(np.float32)
            vec_a = region_centers_a[reg] + noise_a
            vec_a /= np.linalg.norm(vec_a)
            vectors_a[i] = vec_a
        else:
            vectors_a[i] = np.zeros(DIM_A, dtype=np.float32)

    # Save vectors_t and vectors_a
    vectors_t_file = output_dir / "vectors_t.npy"
    np.save(vectors_t_file, vectors_t)

    vectors_a_file = output_dir / "vectors_a.npy"
    np.save(vectors_a_file, vectors_a)

    # 5. Generate 3D visualization coordinates via PCA of taste space
    # Center taste vectors
    centered_t = vectors_t - np.mean(vectors_t, axis=0)
    # SVD for top 3 principal components
    _, _, vt = np.linalg.svd(centered_t, full_matrices=False)
    layout3d = np.dot(centered_t, vt[:3].T).astype(np.float32)
    # Scale layout to roughly [-10, 10]
    layout3d = layout3d / (np.std(layout3d) + 1e-6) * 3.0

    layout3d_file = output_dir / "layout3d.npy"
    np.save(layout3d_file, layout3d)

    # 6. Generate Scalars (scalars.parquet)
    scalar_bpm = np.zeros(TRACK_COUNT, dtype=np.float32)
    scalar_energy = np.zeros(TRACK_COUNT, dtype=np.float32)
    scalar_valence = np.zeros(TRACK_COUNT, dtype=np.float32)
    scalar_danceability = np.zeros(TRACK_COUNT, dtype=np.float32)
    scalar_acousticness = np.zeros(TRACK_COUNT, dtype=np.float32)
    scalar_instrumentalness = np.zeros(TRACK_COUNT, dtype=np.float32)
    scalar_loudness = np.zeros(TRACK_COUNT, dtype=np.float32)

    track_rows = []

    for i in range(TRACK_COUNT):
        reg = region_assignments[i]
        reg_info = REGIONS_DEF[reg]
        art_idx = track_artist_indices[i]
        art = artists[art_idx]

        track_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"melovia.track.{i}"))
        mbid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mb.track.{i}"))
        isrc = f"USMLV26{i:05d}"
        year = int(rng.integers(1975, 2026))

        # Title generation
        mod = TITLE_MODIFIERS[rng.integers(0, len(TITLE_MODIFIERS))]
        noun = TITLE_NOUNS[rng.integers(0, len(TITLE_NOUNS))]
        title = f"{mod} {noun}"
        if i % 7 == 0:
            title += f", Pt. {(i % 3) + 1}"

        track_rows.append({
            "track_idx": i,
            "id": track_uuid,
            "mbid": mbid,
            "title": title,
            "artist_id": art["id"],
            "artist_name": art["name"],
            "year": year,
            "isrc": isrc,
            "isrcs": [isrc],
            "popularity_pct": float(popularity_pct[i]),
            "has_a": has_a_list[i],
            "has_t": has_t_list[i],
            "region_id": int(reg),
        })

        # Scalars
        min_bpm, max_bpm = reg_info["bpm_range"]
        bpm = float(rng.uniform(min_bpm, max_bpm))
        energy = float(np.clip(rng.normal(reg_info["energy_mean"], 0.12), 0.05, 0.98))
        valence = float(np.clip(rng.normal(reg_info["valence_mean"], 0.15), 0.05, 0.95))
        danceability = float(np.clip(rng.normal(0.5, 0.2), 0.05, 0.95))
        acousticness = float(np.clip(1.0 - energy + rng.normal(0.0, 0.1), 0.01, 0.99))
        instrumentalness = float(0.85 if reg in (2, 3, 6, 11) else rng.uniform(0.05, 0.70))
        loudness = float(-30.0 + (energy * 24.0) + rng.normal(0.0, 1.5))

        scalar_bpm[i] = bpm
        scalar_energy[i] = energy
        scalar_valence[i] = valence
        scalar_danceability[i] = danceability
        scalar_acousticness[i] = acousticness
        scalar_instrumentalness[i] = instrumentalness
        scalar_loudness[i] = loudness

    # Save tracks.parquet
    tracks_table = pa.Table.from_pylist(track_rows)
    tracks_file = output_dir / "tracks.parquet"
    pq.write_table(tracks_table, tracks_file)

    # Save scalars.parquet
    scalar_tempo_norm = np.clip((scalar_bpm - 50.0) / 150.0, 0.0, 1.0)
    scalars_table = pa.table({
        "track_idx": pa.array(range(TRACK_COUNT), type=pa.int64()),
        "bpm": pa.array(scalar_bpm, type=pa.float32()),
        "tempo_bpm": pa.array(scalar_bpm, type=pa.float32()),
        "tempo_norm": pa.array(scalar_tempo_norm, type=pa.float32()),
        "energy": pa.array(scalar_energy, type=pa.float32()),
        "energy_idx": pa.array(scalar_energy, type=pa.float32()),
        "valence": pa.array(scalar_valence, type=pa.float32()),
        "valence_idx": pa.array(scalar_valence, type=pa.float32()),
        "danceability": pa.array(scalar_danceability, type=pa.float32()),
        "acousticness": pa.array(scalar_acousticness, type=pa.float32()),
        "instrumentalness": pa.array(scalar_instrumentalness, type=pa.float32()),
        "loudness_db": pa.array(scalar_loudness, type=pa.float32()),
        "popularity_pct": pa.array(popularity_pct, type=pa.float32()),
    })
    scalars_file = output_dir / "scalars.parquet"
    pq.write_table(scalars_table, scalars_file)

    # 7. Compute SHA-256 for all bundle files
    bundle_files = [
        "tracks.parquet",
        "vectors_t.npy",
        "vectors_a.npy",
        "scalars.parquet",
        "tag_vocab.json",
        "regions.json",
        "layout3d.npy",
    ]

    files_hashes = {}
    for filename in bundle_files:
        filepath = output_dir / filename
        files_hashes[filename] = compute_sha256(filepath)

    # 8. Write manifest.json
    manifest = {
        "version": "v1",
        "created_at": "2026-09-19T21:20:00Z",
        "plan": "mock",
        "track_count": TRACK_COUNT,
        "dim_t": DIM_T,
        "dim_a": DIM_A,
        "files": files_hashes,
    }

    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Phase 11: Discover 24 clusters with tag lift and soft assignments
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from pipelines.build_regions import build_regions
        build_regions(output_dir, k=24)
        # Re-read files_hashes from updated manifest
        with open(manifest_file, "r", encoding="utf-8") as f:
            files_hashes = json.load(f).get("files", files_hashes)
    except Exception as e:
        print(f"Notice: build_regions post-processing skipped: {e}")

    print(f"Successfully generated mock catalog bundle at: {output_dir}")
    print(f"Tracks: {TRACK_COUNT}, Artists: {len(artists)}, Discovered Regions: 24")
    print(f"Missing channel a: {len(missing_a_indices)} tracks ({len(missing_a_indices)/TRACK_COUNT*100:.1f}%)")
    return files_hashes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Melovia deterministic mock catalog bundle.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "bundles" / "v1",
        help="Target bundle directory (default: data/bundles/v1)",
    )
    args = parser.parse_args()
    generate_mock_catalog(args.output_dir)
