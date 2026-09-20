"""Anonymous device and session cookie helpers for Melovia."""

import hashlib
import uuid

from fastapi import Request, Response


def get_or_create_device_id(request: Request, response: Response) -> tuple[str, str]:
    """Extract or create anonymous device UUID with httpOnly, SameSite=Lax cookie."""
    raw_id = request.cookies.get("melovia_device_id")
    if not raw_id or len(raw_id) > 64:
        raw_id = str(uuid.uuid4())
        response.set_cookie(
            key="melovia_device_id",
            value=raw_id,
            httponly=True,
            samesite="lax",
            max_age=365 * 24 * 3600,
            secure=False,
        )

    # Invariant: device_id is never logged in plain text
    device_hash = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:8]
    return raw_id, device_hash


def get_or_create_session_id(request: Request, response: Response) -> str:
    """Extract or create session UUID with cookie."""
    sess_id = request.cookies.get("melovia_session_id")
    if not sess_id or len(sess_id) > 64:
        sess_id = f"sess_{uuid.uuid4().hex[:12]}"
        response.set_cookie(
            key="melovia_session_id",
            value=sess_id,
            httponly=True,
            samesite="lax",
            max_age=2 * 3600,
            secure=False,
        )
    return sess_id
