"""Offline file export adapter supporting CSV, JSON (JSPF), M3U, and Plain Text formats.

Architecture Rules:
- Lives in api/app/platforms/files.py.
- Operates 100% offline with zero external network dependencies.
- No platform types leak into recsys.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any


def _extract_track_dict(track: Any) -> dict[str, Any]:
    """Normalize various track representations into a standardized dict."""
    if hasattr(track, "model_dump"):
        d = track.model_dump()
        # If it's a RecommendedTrackItem, extract the nested track
        if "track" in d and isinstance(d["track"], dict):
            inner = d["track"]
            return {
                "track_id": inner.get("id", ""),
                "title": inner.get("title", ""),
                "artist": inner.get("artist_name", ""),
                "isrc": inner.get("isrcs", [""])[0] if inner.get("isrcs") else "",
                "year": inner.get("year"),
                "tempo_bpm": inner.get("scalars", {}).get("bpm") if inner.get("scalars") else None,
                "energy": inner.get("scalars", {}).get("energy") if inner.get("scalars") else None,
                "duration_seconds": 180,
            }
        return {
            "track_id": d.get("id", ""),
            "title": d.get("title", ""),
            "artist": d.get("artist_name", d.get("artist", "")),
            "isrc": d.get("isrcs", [d.get("isrc", "")])[0]
            if isinstance(d.get("isrcs"), list) and d.get("isrcs")
            else d.get("isrc", ""),
            "year": d.get("year"),
            "tempo_bpm": d.get("scalars", {}).get("bpm") if d.get("scalars") else None,
            "energy": d.get("scalars", {}).get("energy") if d.get("scalars") else None,
            "duration_seconds": d.get("duration_seconds", 180),
        }
    elif isinstance(track, dict):
        if "track" in track and isinstance(track["track"], dict):
            inner = track["track"]
            return {
                "track_id": inner.get("id", ""),
                "title": inner.get("title", ""),
                "artist": inner.get("artist_name", inner.get("artist", "")),
                "isrc": (
                    inner.get("isrcs", [""])[0] if inner.get("isrcs") else inner.get("isrc", "")
                ),
                "year": inner.get("year"),
                "tempo_bpm": inner.get("scalars", {}).get("bpm")
                if inner.get("scalars")
                else inner.get("tempo_bpm"),
                "energy": inner.get("scalars", {}).get("energy")
                if inner.get("scalars")
                else inner.get("energy"),
                "duration_seconds": inner.get("duration_seconds", 180),
            }
        isrc_val = track.get("isrc", "")
        if not isrc_val and isinstance(track.get("isrcs"), list) and track["isrcs"]:
            isrc_val = track["isrcs"][0]
        return {
            "track_id": track.get("id", track.get("track_id", "")),
            "title": track.get("title", ""),
            "artist": track.get("artist_name", track.get("artist", "")),
            "isrc": isrc_val,
            "year": track.get("year"),
            "tempo_bpm": track.get("scalars", {}).get("bpm")
            if track.get("scalars")
            else track.get("tempo_bpm"),
            "energy": track.get("scalars", {}).get("energy")
            if track.get("scalars")
            else track.get("energy"),
            "duration_seconds": track.get("duration_seconds", 180),
        }
    else:
        return {
            "track_id": str(getattr(track, "id", "")),
            "title": str(getattr(track, "title", "")),
            "artist": str(getattr(track, "artist_name", getattr(track, "artist", ""))),
            "isrc": "",
            "year": getattr(track, "year", None),
            "tempo_bpm": getattr(track, "tempo_bpm", None),
            "energy": getattr(track, "energy", None),
            "duration_seconds": 180,
        }


class FileExportAdapter:
    """Offline file exporter for playlist export in various standard formats."""

    @staticmethod
    def export_csv(tracks: list[Any], playlist_name: str = "Melovia Playlist") -> str:
        """Export tracks as RFC 4180 CSV string."""
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["track_id", "title", "artist", "isrc", "year", "tempo_bpm", "energy"])

        for t in tracks:
            norm = _extract_track_dict(t)
            writer.writerow(
                [
                    norm["track_id"],
                    norm["title"],
                    norm["artist"],
                    norm["isrc"] or "",
                    norm["year"] if norm["year"] is not None else "",
                    f"{norm['tempo_bpm']:.1f}" if norm["tempo_bpm"] is not None else "",
                    f"{norm['energy']:.3f}" if norm["energy"] is not None else "",
                ]
            )
        return output.getvalue()

    @staticmethod
    def export_json(tracks: list[Any], playlist_name: str = "Melovia Playlist") -> str:
        """Export tracks as JSPF-compatible (JSON Shareable Playlist Format) JSON string."""
        jspf_tracks = []
        for t in tracks:
            norm = _extract_track_dict(t)
            duration_ms = norm["duration_seconds"] * 1000 if norm.get("duration_seconds") else None
            track_entry: dict[str, Any] = {
                "title": norm["title"],
                "creator": norm["artist"],
                "duration": duration_ms,
            }
            if norm["isrc"]:
                track_entry["identifier"] = [f"urn:isrc:{norm['isrc']}"]
            # Melovia extension metadata
            track_entry["extension"] = {
                "https://melovia.local/jspf-ext": {
                    "track_id": norm["track_id"],
                    "year": norm["year"],
                    "tempo_bpm": norm["tempo_bpm"],
                    "energy": norm["energy"],
                }
            }
            jspf_tracks.append(track_entry)

        playlist_doc = {
            "playlist": {
                "title": playlist_name,
                "creator": "Melovia Music Discovery",
                "date": datetime.now(UTC).isoformat(),
                "track": jspf_tracks,
            }
        }
        return json.dumps(playlist_doc, indent=2, ensure_ascii=False)

    @staticmethod
    def export_m3u(tracks: list[Any], playlist_name: str = "Melovia Playlist") -> str:
        """Export tracks as Extended M3U (#EXTM3U) format."""
        lines = ["#EXTM3U", f"#PLAYLIST:{playlist_name}"]
        for t in tracks:
            norm = _extract_track_dict(t)
            duration = int(norm.get("duration_seconds") or 180)
            artist = norm["artist"] or "Unknown Artist"
            title = norm["title"] or "Unknown Title"
            lines.append(f"#EXTINF:{duration},{artist} - {title}")
            if norm["isrc"]:
                lines.append(f"#EXT-X-ISRC:{norm['isrc']}")
            # Use safe filename/URI representation
            safe_title = f"{artist} - {title}".replace("/", "-")
            lines.append(f"{safe_title}.mp3")
        return "\n".join(lines) + "\n"

    @staticmethod
    def export_txt(tracks: list[Any], playlist_name: str = "Melovia Playlist") -> str:
        """Export tracks as plain text lines (Artist - Title)."""
        lines = [f"{playlist_name}", "=" * len(playlist_name), ""]
        for idx, t in enumerate(tracks, 1):
            norm = _extract_track_dict(t)
            artist = norm["artist"] or "Unknown Artist"
            title = norm["title"] or "Unknown Title"
            lines.append(f"{idx}. {artist} - {title}")
        return "\n".join(lines) + "\n"

    @classmethod
    def export(
        cls, format_type: str, tracks: list[Any], playlist_name: str = "Melovia Playlist"
    ) -> tuple[str, str, str]:
        """Export tracks to specified format.

        Returns: (content_string, mime_type, file_extension)
        """
        fmt = format_type.lower().strip()
        if fmt == "csv":
            return cls.export_csv(tracks, playlist_name), "text/csv; charset=utf-8", "csv"
        elif fmt == "json":
            return cls.export_json(tracks, playlist_name), "application/json; charset=utf-8", "json"
        elif fmt in ("m3u", "m3u8"):
            return cls.export_m3u(tracks, playlist_name), "audio/x-mpegurl; charset=utf-8", "m3u8"
        elif fmt in ("txt", "text"):
            return cls.export_txt(tracks, playlist_name), "text/plain; charset=utf-8", "txt"
        else:
            raise ValueError(
                f"Unsupported export format: {format_type}. Must be csv, json, m3u, or txt."
            )
