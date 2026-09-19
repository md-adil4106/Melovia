"""AcousticBrainz audio feature ingestion module."""

import json
from pathlib import Path
from typing import Any


def extract_acousticbrainz_scalars(data: dict[str, Any]) -> dict[str, Any]:
    """Extract standard audio scalars from AcousticBrainz highlevel/lowlevel JSON."""
    highlevel = data.get("highlevel", {})
    rhythm = data.get("rhythm", {})
    lowlevel = data.get("lowlevel", {})

    # Extract BPM / tempo
    bpm: float | None = None
    if "bpm" in rhythm:
        try:
            bpm = round(float(rhythm["bpm"]), 1)
        except (ValueError, TypeError):
            pass

    # Extract probability scores for acoustic descriptors
    danceability: float | None = None
    if "danceable" in highlevel:
        danceability = float(highlevel["danceable"].get("probability", 0.5))

    energy: float | None = None
    if "mood_party" in highlevel:
        energy = float(highlevel["mood_party"].get("probability", 0.5))
    elif "mood_relaxed" in highlevel:
        energy = round(1.0 - float(highlevel["mood_relaxed"].get("probability", 0.5)), 2)

    valence: float | None = None
    if "mood_happy" in highlevel:
        valence = float(highlevel["mood_happy"].get("probability", 0.5))
    elif "mood_sad" in highlevel:
        valence = round(1.0 - float(highlevel["mood_sad"].get("probability", 0.5)), 2)

    acousticness: float | None = None
    if "mood_acoustic" in highlevel:
        acousticness = float(highlevel["mood_acoustic"].get("probability", 0.5))

    instrumentalness: float | None = None
    if "voice_instrumental" in highlevel:
        is_instrumental = highlevel["voice_instrumental"].get("value") == "instrumental"
        prob = float(highlevel["voice_instrumental"].get("probability", 0.5))
        instrumentalness = prob if is_instrumental else round(1.0 - prob, 2)

    loudness_db: float | None = None
    if "average_loudness" in lowlevel:
        try:
            loudness_db = round(float(lowlevel["average_loudness"]), 2)
        except (ValueError, TypeError):
            pass

    return {
        "bpm": bpm,
        "tempo_bpm": bpm,
        "danceability": danceability,
        "energy": energy,
        "valence": valence,
        "acousticness": acousticness,
        "instrumentalness": instrumentalness,
        "loudness_db": loudness_db,
    }


def parse_acousticbrainz_dump(file_path: Path) -> dict[str, dict[str, Any]]:
    """Parse AcousticBrainz dump into mapping of recording_mbid -> audio_scalars."""
    features: dict[str, dict[str, Any]] = {}
    if not file_path.exists():
        return features

    with open(file_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        f.seek(0)

        if first_line.startswith("["):
            data = json.load(f)
            for item in data:
                mbid = item.get("mbid") or item.get("recording_mbid")
                if mbid:
                    features[mbid] = extract_acousticbrainz_scalars(item)
        else:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    mbid = item.get("mbid") or item.get("recording_mbid")
                    if mbid:
                        features[mbid] = extract_acousticbrainz_scalars(item)
                except json.JSONDecodeError:
                    continue

    return features
