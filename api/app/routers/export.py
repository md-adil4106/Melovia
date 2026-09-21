"""FastAPI router for file and streaming platform export.

Architecture Rules:
- Lives in api/app/routers/export.py.
- Validates all input using Pydantic schemas in app/schemas/export.py.
- Pure recsys has zero knowledge of this layer.
- Never logs or persists tokens beyond in-memory session store.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.errors import NotFoundError
from app.platforms.files import FileExportAdapter
from app.platforms.matching import MatchStatus, TrackMatcher
from app.platforms.registry import list_supported_platforms
from app.platforms.spotify import (
    SpotifyAdapter,
    generate_code_challenge,
    generate_code_verifier,
)
from app.routers.cookies import get_or_create_session_id
from app.schemas.export import (
    ExportJobResponse,
    FileExportRequest,
    PlatformExportRequest,
    SpotifyAuthUrlResponse,
    SpotifyStatusResponse,
    TrackExportItem,
)
from app.session.store import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])
export_rate_limiter = TokenBucketRateLimiter(rate=0.5, capacity=10.0)

# In-memory storage for Spotify sessions and async jobs (ephemeral, not written to disk)
SPOTIFY_SESSIONS: dict[str, dict[str, Any]] = {}
STATE_TO_SESSION: dict[str, str] = {}
EXPORT_JOBS: dict[str, ExportJobResponse] = {}


def _resolve_tracks(
    request: Request,
    track_ids: list[str] | None,
    explicit_tracks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Resolve track objects from catalog store or use explicit items."""
    if explicit_tracks:
        return explicit_tracks

    if not track_ids:
        return []

    store = getattr(request.app.state, "catalog_store", None)
    results: list[dict[str, Any]] = []

    for tid in track_ids:
        if store:
            track = store.lookup_id(tid)
            if track:
                isrc = track.isrcs[0] if track.isrcs else ""
                scalars = track.scalars.model_dump() if track.scalars else {}
                results.append(
                    {
                        "track_id": track.id,
                        "id": track.id,
                        "title": track.title,
                        "artist": track.artist_name,
                        "artist_name": track.artist_name,
                        "isrc": isrc,
                        "year": track.year,
                        "scalars": scalars,
                        "tempo_bpm": scalars.get("bpm"),
                        "energy": scalars.get("energy"),
                    }
                )
                continue
        # Fallback if catalog not loaded or track not found
        results.append(
            {
                "track_id": tid,
                "id": tid,
                "title": f"Track {tid[:8]}",
                "artist": "Unknown Artist",
            }
        )

    return results


@router.get("/platforms", summary="List supported export targets")
async def get_platforms() -> list[dict[str, Any]]:
    """Return all supported export targets (files, Spotify, etc.)."""
    return list_supported_platforms()


@router.post("/file", summary="Export playlist to offline file format")
async def export_file(
    payload: FileExportRequest,
    request: Request,
) -> Response:
    """Generate and download a playlist file in CSV, JSON (JSPF), M3U, or TXT format."""
    client_ip = request.client.host if request.client else "unknown"
    session_id = request.cookies.get("melovia_session_id", "anon")
    if not export_rate_limiter.consume(f"export:{client_ip}:{session_id}"):
        raise HTTPException(
            status_code=429,
            detail="Too many export requests. Please wait a moment.",
        )

    tracks = _resolve_tracks(request, payload.track_ids, payload.tracks)
    if not tracks:
        raise HTTPException(status_code=400, detail="No tracks provided for file export.")

    chars = [c for c in payload.playlist_name if c.isalnum() or c in (" ", "-", "_")]
    safe_title = "".join(chars).strip().replace(" ", "_") or "melovia_playlist"

    content, mime_type, ext = FileExportAdapter.export(
        payload.format, tracks, payload.playlist_name
    )

    filename = f"{safe_title}.{ext}"
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get(
    "/spotify/auth-url",
    response_model=SpotifyAuthUrlResponse,
    summary="Get Spotify PKCE authorization URL",
)
async def get_spotify_auth_url(
    request: Request,
    response: Response,
) -> SpotifyAuthUrlResponse:
    """Generate PKCE credentials and Spotify login URL."""
    settings = get_settings()
    client_id = settings.PLATFORM.spotify_client_id or settings.PLATFORM.client_id
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="Spotify Client ID is not configured. Set SPOTIFY_CLIENT_ID in environment.",
        )

    session_id = get_or_create_session_id(request, response)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = uuid.uuid4().hex

    # Store in memory session store
    SPOTIFY_SESSIONS[session_id] = {
        "code_verifier": code_verifier,
        "state": state,
        "created_at": time.time(),
    }
    STATE_TO_SESSION[state] = session_id

    adapter = SpotifyAdapter()
    auth_url = adapter.get_authorization_url(state=state, code_challenge=code_challenge)

    logger.info(
        "Generated Spotify OAuth PKCE auth URL for session", extra={"stage": "spotify_auth_url"}
    )
    return SpotifyAuthUrlResponse(auth_url=auth_url, session_id=session_id, state=state)


@router.get("/spotify/callback", summary="Spotify OAuth redirect callback")
async def spotify_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    """Handle OAuth redirect from Spotify, exchange PKCE code for token."""
    if error:
        logger.warning("Spotify authorization denied or failed: %s", error)
        html = f"""
        <html><body>
        <h3>Spotify authorization cancelled or failed: {error}</h3>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{ type: 'SPOTIFY_AUTH_ERROR', error: '{error}' }}, '*');
                setTimeout(() => window.close(), 1500);
            }} else {{
                setTimeout(() => window.location.href = '/', 2000);
            }}
        </script>
        </body></html>
        """
        return HTMLResponse(content=html, status_code=400)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing required code or state parameter.")

    session_id = STATE_TO_SESSION.get(state)
    session_data = SPOTIFY_SESSIONS.get(session_id) if session_id else None

    if not session_data or session_data.get("state") != state:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state parameter.")

    # Enforce single-use state parameter (prevent replay attacks)
    STATE_TO_SESSION.pop(state, None)
    session_data["state"] = None

    code_verifier = session_data.get("code_verifier", "")
    adapter = SpotifyAdapter()
    token_resp = await adapter.authenticate(code=code, code_verifier=code_verifier)

    if "access_token" not in token_resp:
        err_msg = token_resp.get("error", "Token exchange failed.")
        logger.error("Failed Spotify token exchange: %s", err_msg)
        return HTMLResponse(
            content=(
                f"<html><body><h3>Failed to authenticate with Spotify: {err_msg}</h3></body></html>"
            ),
            status_code=400,
        )

    access_token = token_resp["access_token"]
    refresh_token = token_resp.get("refresh_token")
    expires_in = token_resp.get("expires_in", 3600)

    # Fetch user profile
    user_info = await adapter.get_current_user(access_token)

    session_data["access_token"] = access_token
    if refresh_token:
        session_data["refresh_token"] = refresh_token
    session_data["expires_at"] = time.time() + expires_in
    session_data["user_id"] = user_info.get("id", "me")
    session_data["display_name"] = user_info.get("display_name")
    ext_urls = user_info.get("external_urls", {})
    session_data["profile_url"] = ext_urls.get("spotify") if ext_urls else None

    logger.info("Successfully connected Spotify user", extra={"stage": "spotify_auth_success"})

    # PostMessage to parent window if opened as popup, or redirect to frontend
    body_style = (
        "font-family: sans-serif; text-align: center; padding-top: 50px; "
        "background: #121212; color: #fff;"
    )
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Spotify Connected</title></head>
    <body style="{body_style}">
      <h2>Connected to Spotify!</h2>
      <p>This window will close automatically...</p>
      <script>
        if (window.opener) {{
          window.opener.postMessage({{ type: 'SPOTIFY_AUTH_SUCCESS' }}, '*');
          window.close();
        }} else {{
          window.location.href = '/';
        }}
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get(
    "/spotify/status",
    response_model=SpotifyStatusResponse,
    summary="Check Spotify connection status",
)
async def get_spotify_status(
    request: Request,
    response: Response,
) -> SpotifyStatusResponse:
    """Return whether Spotify is connected for the active session."""
    session_id = get_or_create_session_id(request, response)
    session_data = SPOTIFY_SESSIONS.get(session_id)

    if not session_data or not session_data.get("access_token"):
        return SpotifyStatusResponse(connected=False)

    # Check if expired and refresh if possible
    expires_at = session_data.get("expires_at", 0)
    if time.time() >= expires_at - 60 and session_data.get("refresh_token"):
        adapter = SpotifyAdapter()
        refresh_resp = await adapter.refresh_token(session_data["refresh_token"])
        if "access_token" in refresh_resp:
            session_data["access_token"] = refresh_resp["access_token"]
            session_data["expires_at"] = time.time() + refresh_resp.get("expires_in", 3600)
        else:
            # Refresh failed
            SPOTIFY_SESSIONS.pop(session_id, None)
            return SpotifyStatusResponse(connected=False)

    return SpotifyStatusResponse(
        connected=True,
        display_name=session_data.get("display_name"),
        user_id=session_data.get("user_id"),
        profile_url=session_data.get("profile_url"),
    )


@router.post("/spotify/disconnect", summary="Disconnect Spotify session")
async def disconnect_spotify(
    request: Request,
    response: Response,
) -> dict[str, bool]:
    """Clear active Spotify credentials for session."""
    session_id = get_or_create_session_id(request, response)
    SPOTIFY_SESSIONS.pop(session_id, None)
    return {"success": True}


@router.post(
    "/playlist",
    response_model=ExportJobResponse,
    summary="Export playlist to streaming platform",
)
async def export_playlist(
    payload: PlatformExportRequest,
    request: Request,
    response: Response,
) -> ExportJobResponse:
    """Export tracks to Spotify with matching and status tracking."""
    session_id = get_or_create_session_id(request, response)
    client_ip = request.client.host if request.client else "unknown"
    if not export_rate_limiter.consume(f"export:{client_ip}:{session_id}"):
        raise HTTPException(
            status_code=429,
            detail="Too many export requests. Please wait a moment.",
        )

    session_data = SPOTIFY_SESSIONS.get(session_id)

    if not session_data or not session_data.get("access_token"):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Connect your account first.",
        )

    tracks = _resolve_tracks(request, payload.track_ids, payload.tracks)
    if not tracks:
        raise HTTPException(status_code=400, detail="No tracks provided for platform export.")

    job_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    adapter = SpotifyAdapter()
    matcher = TrackMatcher(adapter)
    access_token = session_data["access_token"]
    user_id = session_data.get("user_id", "me")

    # 1. Match catalog tracks against platform
    match_results = await matcher.match_batch(tracks)

    items: list[TrackExportItem] = []
    uris_to_add: list[str] = []
    matched_count = 0
    ambiguous_count = 0
    unmatched_count = 0

    for mr in match_results:
        st_val = mr.status.value
        if mr.status == MatchStatus.MATCHED:
            matched_count += 1
            if mr.platform_uri:
                uris_to_add.append(mr.platform_uri)
        elif mr.status == MatchStatus.AMBIGUOUS:
            ambiguous_count += 1
        else:
            unmatched_count += 1

        status_literal = cast(
            Literal["matched", "ambiguous", "unmatched", "added", "failed"], st_val
        )
        items.append(
            TrackExportItem(
                catalog_track_id=mr.catalog_track_id,
                title=mr.catalog_title,
                artist=mr.catalog_artist,
                isrc=mr.catalog_isrc,
                status=status_literal,
                confidence=mr.confidence,
                platform_uri=mr.platform_uri,
                platform_title=mr.platform_title,
                platform_artist=mr.platform_artist,
                match_strategy=mr.match_strategy,
            )
        )

    # 2. Create playlist on Spotify
    playlist_res = await adapter.create_playlist(
        user_id=user_id,
        name=payload.playlist_name,
        track_ids=uris_to_add,
        access_token=access_token,
        description=payload.playlist_description,
    )

    if "error" in playlist_res:
        job = ExportJobResponse(
            job_id=job_id,
            status="failed",
            platform="spotify",
            playlist_name=payload.playlist_name,
            total_tracks=len(tracks),
            matched_count=matched_count,
            ambiguous_count=ambiguous_count,
            unmatched_count=unmatched_count,
            tracks=items,
            error=playlist_res.get("error"),
            created_at=created_at,
        )
        EXPORT_JOBS[job_id] = job
        return job

    playlist_id = playlist_res.get("id")
    playlist_url = (
        playlist_res.get("external_urls", {}).get("spotify")
        if playlist_res.get("external_urls")
        else f"https://open.spotify.com/playlist/{playlist_id}"
    )

    job = ExportJobResponse(
        job_id=job_id,
        status="completed",
        platform="spotify",
        playlist_name=payload.playlist_name,
        playlist_id=playlist_id,
        playlist_url=playlist_url,
        total_tracks=len(tracks),
        matched_count=matched_count,
        ambiguous_count=ambiguous_count,
        unmatched_count=unmatched_count,
        tracks=items,
        created_at=created_at,
    )
    EXPORT_JOBS[job_id] = job

    logger.info(
        "Completed Spotify export job %s: %d matched, %d unmatched",
        job_id,
        matched_count,
        unmatched_count,
        extra={"stage": "export_job_completed"},
    )
    return job


@router.get("/jobs/{job_id}", response_model=ExportJobResponse, summary="Get export job status")
async def get_export_job(job_id: str) -> ExportJobResponse:
    """Retrieve details and per-track matching results for an export job."""
    if job_id not in EXPORT_JOBS:
        raise NotFoundError(f"Export job not found: {job_id}")
    return EXPORT_JOBS[job_id]


@router.get("/jobs/{job_id}/unmatched", summary="Download unmatched tracks from an export job")
async def download_unmatched_tracks(job_id: str) -> Response:
    """Download unmatched tracks from an export job as a CSV list."""
    if job_id not in EXPORT_JOBS:
        raise NotFoundError(f"Export job not found: {job_id}")

    job = EXPORT_JOBS[job_id]
    unmatched_tracks = [
        {"id": t.catalog_track_id, "title": t.title, "artist": t.artist, "isrc": t.isrc}
        for t in job.tracks
        if t.status in ("unmatched", "ambiguous")
    ]

    csv_content = FileExportAdapter.export_csv(
        unmatched_tracks, playlist_name=f"{job.playlist_name} - Unmatched"
    )
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="unmatched_{job_id[:8]}.csv"',
            "Cache-Control": "no-cache",
        },
    )
