"""Unit tests for catalog cleaner, noise filtering, and deduplication."""

import sys
from pathlib import Path

# Ensure root is on path for pipelines import
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from pipelines.cleaner import (  # noqa: E402
    RawRecording,
    canonical_match_key,
    compute_popularity_percentiles,
    deduplicate_recordings,
    is_noise_variant,
    normalize_text,
)


def test_normalize_text() -> None:
    """Test unicode stripping, NFC/NFKD normalization, and whitespace collapse."""
    assert normalize_text("  Björk  \t") == "Bjork"
    assert normalize_text("Beyoncé   Knowles") == "Beyonce Knowles"
    assert normalize_text("Sigur  \n  Rós") == "Sigur Ros"
    assert normalize_text("") == ""


def test_canonical_match_key() -> None:
    """Test title and artist canonical matching keys."""
    t1, a1 = canonical_match_key("Bohemian Rhapsody!", "Queen")
    t2, a2 = canonical_match_key("  bohemian rhapsody  ", "queen.")
    assert (t1, a1) == (t2, a2)
    assert t1 == "bohemian rhapsody"
    assert a1 == "queen"


def test_is_noise_variant_live() -> None:
    """Test detection of live variants."""
    assert is_noise_variant("Bohemian Rhapsody (Live at Wembley '86)") is True
    assert is_noise_variant("Comfortably Numb - Live") is True
    assert is_noise_variant("Heroes [Recorded Live in Berlin]") is True
    assert is_noise_variant("Paranoid Android (in concert)") is True
    # Studio track should pass
    assert is_noise_variant("Bohemian Rhapsody") is False
    assert is_noise_variant("Live to Tell") is False  # Word live in regular title


def test_is_noise_variant_remixes_and_others() -> None:
    """Test detection of remix, karaoke, video, and instrumental versions."""
    assert is_noise_variant("Smells Like Teen Spirit (Dirty Funker Remix)") is True
    assert is_noise_variant("Get Lucky (Club Mix)") is True
    assert is_noise_variant("Billie Jean (VIP Mix)") is True
    assert is_noise_variant("Hey Jude (Karaoke Version)") is True
    assert is_noise_variant("Dreams (Instrumental Version)") is True
    assert is_noise_variant("Billie Jean (Official Music Video)") is True
    assert is_noise_variant("Alright (Lyric Video)") is True

    # MusicBrainz disambiguation flag
    assert is_noise_variant("Dreams", disambiguation="live version") is True
    assert is_noise_variant("Dreams", disambiguation="remix") is True

    # Secondary types
    assert is_noise_variant("Dreams", secondary_types=["Live"]) is True
    assert is_noise_variant("Dreams", secondary_types=["Remix"]) is True

    # Clean titles
    assert is_noise_variant("Dreams") is False
    assert is_noise_variant("Heroes") is False


def test_deduplicate_recordings_by_mbid_isrc_and_title() -> None:
    """Test multi-pass deduplication, preserving earliest year and richest tags."""
    recs = [
        # Track 1
        RawRecording(
            mbid="mbid-1",
            title="Bohemian Rhapsody",
            artist_name="Queen",
            year=1975,
            isrcs=["ISRC001"],
            tags=[{"name": "rock", "weight": 1.0, "source": "recording"}],
            listen_count=1000,
        ),
        # Duplicate 1: same MBID, later remaster year, extra tag
        RawRecording(
            mbid="mbid-1",
            title="Bohemian Rhapsody",
            artist_name="Queen",
            year=2011,
            isrcs=["ISRC001"],
            tags=[{"name": "classic rock", "weight": 1.0, "source": "recording"}],
            listen_count=1500,
        ),
        # Duplicate 2: different MBID, same ISRC
        RawRecording(
            mbid="mbid-2",
            title="Bohemian Rhapsody",
            artist_name="Queen",
            year=1980,
            isrcs=["ISRC001"],
            tags=[{"name": "progressive rock", "weight": 1.0, "source": "recording"}],
            listen_count=800,
        ),
        # Duplicate 3: different MBID, no ISRC, same title and artist
        RawRecording(
            mbid="mbid-3",
            title="Bohemian Rhapsody!",
            artist_name="Queen",
            year=1995,
            isrcs=[],
            tags=[],
            listen_count=500,
        ),
        # Noise variant: should be dropped
        RawRecording(
            mbid="mbid-4",
            title="Bohemian Rhapsody (Live at Wembley)",
            artist_name="Queen",
            year=1986,
            listen_count=900,
        ),
        # Distinct Track 2
        RawRecording(
            mbid="mbid-5",
            title="Hey Jude",
            artist_name="The Beatles",
            year=1968,
            isrcs=["ISRC002"],
            tags=[{"name": "rock", "weight": 1.0, "source": "recording"}],
            listen_count=2000,
        ),
    ]

    deduped = deduplicate_recordings(recs)
    assert len(deduped) == 2

    queen_track = next(r for r in deduped if "Bohemian" in r.title)
    assert queen_track.year == 1975  # Earliest year preserved
    assert queen_track.listen_count == 1500  # Highest listen count preserved
    # Tags merged
    tag_names = {t["name"] for t in queen_track.tags}
    assert "rock" in tag_names
    assert "classic rock" in tag_names
    assert "progressive rock" in tag_names


def test_compute_popularity_percentiles() -> None:
    """Test log-percentile popularity scaling."""
    recs = [
        RawRecording(mbid="m1", title="T1", artist_name="A1", listen_count=100),
        RawRecording(mbid="m2", title="T2", artist_name="A2", listen_count=10000),
        RawRecording(mbid="m3", title="T3", artist_name="A3", listen_count=1000000),
    ]

    pop_map = compute_popularity_percentiles(recs)
    assert len(pop_map) == 3
    assert pop_map["m1"] == 1.0  # Lowest
    assert pop_map["m3"] == 99.5  # Highest
    assert pop_map["m1"] < pop_map["m2"] < pop_map["m3"]
