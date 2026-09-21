"""Unit tests for offline file export adapter (CSV, JSON/JSPF, M3U, Plain Text).

Architecture Rules:
- Must execute completely offline without any network access.
- Validates structural correctness of exported files.
"""

import csv
import io
import json

import pytest

from app.platforms.files import FileExportAdapter, _extract_track_dict


@pytest.fixture
def sample_tracks():
    return [
        {
            "id": "trk-001",
            "title": "Solaris Echoes (feat. Nova)",
            "artist_name": "Starlight Ensemble",
            "isrcs": ["USMLV2600001"],
            "year": 2024,
            "scalars": {"bpm": 124.0, "energy": 0.78},
            "duration_seconds": 210,
        },
        {
            "id": "trk-002",
            "title": "Midnight Reverie [Remastered 2023]",
            "artist_name": "Lunar Wave",
            "isrc": "USMLV2600002",
            "year": 2023,
            "scalars": {"bpm": 95.5, "energy": 0.42},
            "duration_seconds": 195,
        },
        {
            "id": "trk-003",
            "title": "Acoustic Horizon",
            "artist": "Driftwood",
            "year": 2021,
            "scalars": {"bpm": 80.0, "energy": 0.25},
        },
    ]


def test_extract_track_dict_variants(sample_tracks):
    """Ensure normalization handles varying dict schemas reliably."""
    norm1 = _extract_track_dict(sample_tracks[0])
    assert norm1["track_id"] == "trk-001"
    assert norm1["title"] == "Solaris Echoes (feat. Nova)"
    assert norm1["artist"] == "Starlight Ensemble"
    assert norm1["isrc"] == "USMLV2600001"
    assert norm1["tempo_bpm"] == 124.0
    assert norm1["energy"] == 0.78
    assert norm1["duration_seconds"] == 210

    norm2 = _extract_track_dict(sample_tracks[1])
    assert norm2["isrc"] == "USMLV2600002"

    norm3 = _extract_track_dict(sample_tracks[2])
    assert norm3["artist"] == "Driftwood"
    assert norm3["isrc"] == ""
    assert norm3["duration_seconds"] == 180  # Default fallback


def test_export_csv_structure(sample_tracks):
    """Verify CSV export is RFC 4180 compliant with required headers."""
    csv_str = FileExportAdapter.export_csv(sample_tracks, playlist_name="Cosmic Voyage")
    assert isinstance(csv_str, str)

    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)

    assert len(rows) == 3
    assert reader.fieldnames == [
        "track_id",
        "title",
        "artist",
        "isrc",
        "year",
        "tempo_bpm",
        "energy",
    ]
    assert rows[0]["track_id"] == "trk-001"
    assert rows[0]["isrc"] == "USMLV2600001"
    assert rows[0]["tempo_bpm"] == "124.0"
    assert rows[0]["energy"] == "0.780"
    assert rows[1]["track_id"] == "trk-002"
    assert rows[2]["artist"] == "Driftwood"


def test_export_json_jspf(sample_tracks):
    """Verify JSON export conforms to JSPF schema with Melovia extensions."""
    json_str = FileExportAdapter.export_json(sample_tracks, playlist_name="Deep Focus")
    data = json.loads(json_str)

    assert "playlist" in data
    playlist = data["playlist"]
    assert playlist["title"] == "Deep Focus"
    assert playlist["creator"] == "Melovia Music Discovery"
    assert len(playlist["track"]) == 3

    t1 = playlist["track"][0]
    assert t1["title"] == "Solaris Echoes (feat. Nova)"
    assert t1["creator"] == "Starlight Ensemble"
    assert t1["duration"] == 210000  # ms
    assert t1["identifier"] == ["urn:isrc:USMLV2600001"]
    assert "https://melovia.local/jspf-ext" in t1["extension"]
    assert t1["extension"]["https://melovia.local/jspf-ext"]["track_id"] == "trk-001"


def test_export_m3u(sample_tracks):
    """Verify Extended M3U export includes #EXTM3U and #EXTINF lines."""
    m3u_str = FileExportAdapter.export_m3u(sample_tracks, playlist_name="Ambient Dreams")
    lines = [line.strip() for line in m3u_str.split("\n") if line.strip()]

    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#PLAYLIST:Ambient Dreams"

    # Track 1
    assert "#EXTINF:210,Starlight Ensemble - Solaris Echoes (feat. Nova)" in lines
    assert "#EXT-X-ISRC:USMLV2600001" in lines
    assert "Starlight Ensemble - Solaris Echoes (feat. Nova).mp3" in lines


def test_export_txt(sample_tracks):
    """Verify plain text export produces clean numbered lines."""
    txt_str = FileExportAdapter.export_txt(sample_tracks, playlist_name="Quick List")
    lines = [line for line in txt_str.split("\n") if line]

    assert lines[0] == "Quick List"
    assert lines[1] == "=========="
    assert lines[2] == "1. Starlight Ensemble - Solaris Echoes (feat. Nova)"
    assert lines[3] == "2. Lunar Wave - Midnight Reverie [Remastered 2023]"
    assert lines[4] == "3. Driftwood - Acoustic Horizon"


def test_export_dispatcher(sample_tracks):
    """Test the unified FileExportAdapter.export method."""
    csv_res, mime_csv, ext_csv = FileExportAdapter.export("csv", sample_tracks)
    assert mime_csv == "text/csv; charset=utf-8"
    assert ext_csv == "csv"
    assert "track_id,title,artist" in csv_res

    json_res, mime_json, ext_json = FileExportAdapter.export("json", sample_tracks)
    assert mime_json == "application/json; charset=utf-8"
    assert ext_json == "json"

    with pytest.raises(ValueError, match="Unsupported export format"):
        FileExportAdapter.export("flac", sample_tracks)
