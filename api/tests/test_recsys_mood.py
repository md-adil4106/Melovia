"""Unit tests for recsys mood classifier and listening duration features.

Mandates:
- Pure Python & deterministic tests.
- Verify multi-lingual mood alignment (Hindi/Bollywood emotional vs. happy party).
- Verify target duration and formatting logic.
"""

import numpy as np

from app.recsys.mood import (
    MOOD_PARTY,
    MOOD_ROMANTIC,
    MOOD_SAD,
    classify_track_mood,
    detect_seed_mood_profile,
    get_mood_anchor_vector,
)
from app.routers.recommendations import _format_duration


def test_classify_sad_tracks() -> None:
    sad_samples = [
        {"title": "Channa Mereya", "artist_name": "Arijit Singh", "tags": ["bollywood", "sad"]},
        {"title": "Agar Tum Saath Ho", "artist_name": "Alka Yagnik & Arijit Singh"},
        {"title": "Bekhayali", "artist_name": "Sachet Tandon", "tags": ["heartbreak"]},
        {"title": "Jhelum", "artist_name": "Faheem Abdullah", "tags": ["soulful"]},
        {"title": "Teri Deewani", "artist_name": "B Praak", "tags": ["dard"]},
        {"title": "Someone Like You", "artist_name": "Adele", "tags": ["heartbreak", "ballad"]},
    ]

    for track in sad_samples:
        mood = classify_track_mood(track)
        assert mood == MOOD_SAD, (
            f"Expected '{track['title']}' to be classified as {MOOD_SAD}, got {mood}"
        )


def test_classify_romantic_tracks() -> None:
    romantic_samples = [
        {"title": "Tum Hi Ho", "artist_name": "Arijit Singh", "tags": ["romantic"]},
        {"title": "Kesariya", "artist_name": "Pritam", "tags": ["love"]},
        {"title": "Sajde", "artist_name": "Arijit Singh", "tags": ["bollywood"]},
        {"title": "Guzarish", "artist_name": "Javed Ali", "tags": ["romance"]},
    ]

    for track in romantic_samples:
        mood = classify_track_mood(track)
        assert mood == MOOD_ROMANTIC, (
            f"Expected '{track['title']}' to be classified as {MOOD_ROMANTIC}, got {mood}"
        )


def test_classify_party_tracks() -> None:
    party_samples = [
        {"title": "Kala Chashma", "artist_name": "Badshah", "tags": ["dance"]},
        {"title": "Kar Gayi Chull", "artist_name": "Badshah", "tags": ["party"]},
        {"title": "Badtameez Dil", "artist_name": "Benny Dayal", "tags": ["dance"]},
    ]

    for track in party_samples:
        mood = classify_track_mood(track)
        assert mood == MOOD_PARTY, (
            f"Expected '{track['title']}' to be classified as {MOOD_PARTY}, got {mood}"
        )


def test_detect_seed_mood_profile() -> None:
    seeds = [
        {"title": "Channa Mereya", "artist_name": "Arijit Singh"},
        {"title": "Kabira", "artist_name": "Arijit Singh"},
        {"title": "Agar Tum Saath Ho", "artist_name": "Arijit Singh"},
    ]
    profile = detect_seed_mood_profile(seeds)
    assert profile["dominant_mood"] == MOOD_SAD
    assert profile["is_sad"] is True
    assert profile["confidence"] >= 0.6


def test_mood_anchor_vector_determinism() -> None:
    v1 = get_mood_anchor_vector(MOOD_SAD, dim=128)
    v2 = get_mood_anchor_vector(MOOD_SAD, dim=128)
    v_party = get_mood_anchor_vector(MOOD_PARTY, dim=128)

    assert v1.shape == (128,)
    assert np.allclose(v1, v2)
    assert np.isclose(float(np.linalg.norm(v1)), 1.0)
    # Cosine similarity between sad and party should be near zero (quasi-orthogonal)
    cos_sim = float(np.dot(v1, v_party))
    assert abs(cos_sim) < 0.35, f"Expected sad and party vectors to be orthogonal, got {cos_sim}"


def test_format_duration() -> None:
    assert _format_duration(300.0) == "5 min"
    assert _format_duration(3600.0) == "1 hr"
    assert _format_duration(7200.0) == "2 hr"
    assert _format_duration(7380.0) == "2 hr 03 min"
    assert _format_duration(10800.0) == "3 hr"
