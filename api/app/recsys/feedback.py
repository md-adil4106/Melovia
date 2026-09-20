"""Taste adaptation and live feedback module for Melovia.

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- Deterministic behavior with stable tie-breaking.
- Updates taste mode centroids across semantic (t) and audio (a) channels.
- Enforces drift capping and session-vs-persistent separation.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.recsys.catalog import CatalogStore
from app.recsys.config import RecsysConfig
from app.recsys.taste import Modes


@dataclass(frozen=True)
class FeedbackResult:
    """Immutable result of applying a single feedback event."""

    updated_modes: Modes
    nearest_mode_idx: int
    cosine_to_track_before: float
    cosine_to_track_after: float
    mode_shift_cos: float
    negative_track_ids: set[str]
    negative_artist_ids: set[str]
    known_track_ids: set[str]
    liked_track_ids: list[str]


def apply_feedback(
    event: str,
    track_id: str,
    modes: Modes,
    negative_track_ids: set[str],
    negative_artist_ids: set[str],
    known_track_ids: set[str],
    liked_track_ids: list[str],
    catalog: CatalogStore,
    config: RecsysConfig | None = None,
) -> FeedbackResult:
    """Apply live user feedback (like, dislike, skip, save, etc.) to taste modes.

    Mechanics:
    - Nearest mode m* in taste space receives the gradient update.
    - like / save / replay / add: moves m* toward track vector with learning rate eta (0.15).
    - dislike: moves m* away with rate -0.5 * eta, and adds track to negative_track_ids.
    - skip: weaker negative move with rate -0.125 * eta.
    - remove / remove_from_playlist: move away with rate -0.25 * eta, adds to negative_track_ids.
    - Applied to both channels ('t' and 'a') where audio features exist.
    """
    cfg = config or RecsysConfig()
    norm_event = event.strip().lower()

    if not catalog.contains_id(track_id):
        raise KeyError(f"Track ID '{track_id}' not found in catalog")

    t_idx = catalog.get_idx(track_id)
    x_t = catalog.vectors_t[t_idx]
    has_audio = bool(catalog.mask_a[t_idx])
    x_a = catalog.vectors_a[t_idx] if has_audio else None

    # 1. Identify nearest mode in semantic taste space (channel 't')
    mode_vecs_t = modes.channel_vectors["t"]
    sims_t = np.dot(mode_vecs_t, x_t)
    m_star = int(np.argmax(sims_t))
    cos_before = float(sims_t[m_star])

    # Copy channel vectors for deterministic modification
    new_vecs_t = mode_vecs_t.copy()
    new_vecs_a = modes.channel_vectors["a"].copy()
    has_mode_audio = bool(modes.has_channel.get("a", False))

    updated_negatives = set(negative_track_ids)
    updated_artist_negatives = set(negative_artist_ids)
    updated_known = set(known_track_ids)
    updated_liked = list(liked_track_ids)

    eta = cfg.feedback_eta

    # 2. Apply channel updates based on feedback event category
    if norm_event in ("like", "save", "replay", "add"):
        # Positive update toward track vector
        # T_m <- normalize((1 - eta) * T_m + eta * x)
        v_t_unnorm = (1.0 - eta) * new_vecs_t[m_star] + eta * x_t
        norm_t = float(np.linalg.norm(v_t_unnorm))
        new_vecs_t[m_star] = (v_t_unnorm / norm_t) if norm_t > 1e-12 else new_vecs_t[m_star]

        if has_mode_audio and has_audio and x_a is not None:
            v_a_unnorm = (1.0 - eta) * new_vecs_a[m_star] + eta * x_a
            norm_a = float(np.linalg.norm(v_a_unnorm))
            new_vecs_a[m_star] = (v_a_unnorm / norm_a) if norm_a > 1e-12 else new_vecs_a[m_star]

        updated_known.add(track_id)
        if track_id not in updated_liked:
            updated_liked.append(track_id)

    elif norm_event == "dislike":
        # Dislike: moves mode away and adds to negative exclusions
        # T_m <- normalize(T_m - 0.5 * eta * x)
        factor = cfg.feedback_dislike_factor * eta
        v_t_unnorm = new_vecs_t[m_star] - factor * x_t
        norm_t = float(np.linalg.norm(v_t_unnorm))
        new_vecs_t[m_star] = (v_t_unnorm / norm_t) if norm_t > 1e-12 else new_vecs_t[m_star]

        if has_mode_audio and has_audio and x_a is not None:
            v_a_unnorm = new_vecs_a[m_star] - factor * x_a
            norm_a = float(np.linalg.norm(v_a_unnorm))
            new_vecs_a[m_star] = (v_a_unnorm / norm_a) if norm_a > 1e-12 else new_vecs_a[m_star]

        updated_negatives.add(track_id)
        updated_known.add(track_id)

    elif norm_event == "skip":
        # Skip: weaker negative (0.25x dislike) without hard exclusion
        factor = cfg.feedback_skip_factor * eta
        v_t_unnorm = new_vecs_t[m_star] - factor * x_t
        norm_t = float(np.linalg.norm(v_t_unnorm))
        new_vecs_t[m_star] = (v_t_unnorm / norm_t) if norm_t > 1e-12 else new_vecs_t[m_star]

        if has_mode_audio and has_audio and x_a is not None:
            v_a_unnorm = new_vecs_a[m_star] - factor * x_a
            norm_a = float(np.linalg.norm(v_a_unnorm))
            new_vecs_a[m_star] = (v_a_unnorm / norm_a) if norm_a > 1e-12 else new_vecs_a[m_star]

        updated_known.add(track_id)

    elif norm_event in ("remove", "remove_from_playlist"):
        # Remove from playlist: dislike-lite with negative exclusion
        factor = cfg.feedback_remove_factor * eta
        v_t_unnorm = new_vecs_t[m_star] - factor * x_t
        norm_t = float(np.linalg.norm(v_t_unnorm))
        new_vecs_t[m_star] = (v_t_unnorm / norm_t) if norm_t > 1e-12 else new_vecs_t[m_star]

        if has_mode_audio and has_audio and x_a is not None:
            v_a_unnorm = new_vecs_a[m_star] - factor * x_a
            norm_a = float(np.linalg.norm(v_a_unnorm))
            new_vecs_a[m_star] = (v_a_unnorm / norm_a) if norm_a > 1e-12 else new_vecs_a[m_star]

        updated_negatives.add(track_id)
        updated_known.add(track_id)

    else:
        # Unsupported event type: leave modes unchanged, track as known
        updated_known.add(track_id)

    cos_after = float(np.dot(new_vecs_t[m_star], x_t))
    shift_cos = float(np.dot(mode_vecs_t[m_star], new_vecs_t[m_star]))

    updated_modes = Modes(
        channel_vectors={"t": new_vecs_t, "a": new_vecs_a},
        weights=modes.weights.copy(),
        member_seed_ids=[list(m) for m in modes.member_seed_ids],
        has_channel=dict(modes.has_channel),
    )

    return FeedbackResult(
        updated_modes=updated_modes,
        nearest_mode_idx=m_star,
        cosine_to_track_before=cos_before,
        cosine_to_track_after=cos_after,
        mode_shift_cos=shift_cos,
        negative_track_ids=updated_negatives,
        negative_artist_ids=updated_artist_negatives,
        known_track_ids=updated_known,
        liked_track_ids=updated_liked,
    )


def merge_modes(
    persistent_modes: Modes | None,
    session_modes: Modes,
    alpha: float = 0.30,
    max_drift: float = 0.25,
) -> Modes:
    """Merge live session taste modes into persistent profile modes with drift capping.

    Guarantees:
    - If no persistent profile exists, copies session modes directly.
    - Each persistent mode is paired with its nearest session mode.
    - Maximum Euclidean displacement from persistent mode is bounded by max_drift.
    - All merged mode vectors are strictly L2-normalized.
    """
    if persistent_modes is None:
        return Modes(
            channel_vectors={k: v.copy() for k, v in session_modes.channel_vectors.items()},
            weights=session_modes.weights.copy(),
            member_seed_ids=[list(m) for m in session_modes.member_seed_ids],
            has_channel=dict(session_modes.has_channel),
        )

    p_vecs_t = persistent_modes.channel_vectors["t"].copy()
    p_vecs_a = persistent_modes.channel_vectors["a"].copy()
    s_vecs_t = session_modes.channel_vectors["t"]
    s_vecs_a = session_modes.channel_vectors["a"]

    num_p = len(p_vecs_t)
    num_s = len(s_vecs_t)

    merged_vecs_t = np.zeros_like(p_vecs_t)
    merged_vecs_a = np.zeros_like(p_vecs_a)

    for p_idx in range(num_p):
        p_t = p_vecs_t[p_idx]
        # Find nearest session mode in taste space
        sims = np.dot(s_vecs_t, p_t)
        nearest_s = int(np.argmax(sims)) if num_s > 0 else 0
        s_t = s_vecs_t[nearest_s]

        # 1. Taste channel update with capped Euclidean drift
        # delta = alpha * (s_t - p_t)
        delta_t = alpha * (s_t - p_t)
        drift_norm_t = float(np.linalg.norm(delta_t))
        if drift_norm_t > max_drift and drift_norm_t > 1e-12:
            delta_t = delta_t * (max_drift / drift_norm_t)

        updated_p_t = p_t + delta_t
        norm_p_t = float(np.linalg.norm(updated_p_t))
        merged_vecs_t[p_idx] = (updated_p_t / norm_p_t) if norm_p_t > 1e-12 else p_t

        # 2. Audio channel update if both have active audio
        has_p_audio = bool(persistent_modes.has_channel.get("a", False))
        has_s_audio = bool(session_modes.has_channel.get("a", False))

        if has_p_audio and has_s_audio and p_idx < len(p_vecs_a) and nearest_s < len(s_vecs_a):
            p_a = p_vecs_a[p_idx]
            s_a = s_vecs_a[nearest_s]
            if float(np.linalg.norm(p_a)) > 1e-6 and float(np.linalg.norm(s_a)) > 1e-6:
                delta_a = alpha * (s_a - p_a)
                drift_norm_a = float(np.linalg.norm(delta_a))
                if drift_norm_a > max_drift and drift_norm_a > 1e-12:
                    delta_a = delta_a * (max_drift / drift_norm_a)

                updated_p_a = p_a + delta_a
                norm_p_a = float(np.linalg.norm(updated_p_a))
                merged_vecs_a[p_idx] = (updated_p_a / norm_p_a) if norm_p_a > 1e-12 else p_a
            else:
                merged_vecs_a[p_idx] = p_a
        else:
            merged_vecs_a[p_idx] = p_vecs_a[p_idx]

    # Member seed tracking: union seed IDs per mode
    merged_member_seeds = []
    for p_idx in range(num_p):
        p_seeds = (
            set(persistent_modes.member_seed_ids[p_idx])
            if p_idx < len(persistent_modes.member_seed_ids)
            else set()
        )
        sims = np.dot(s_vecs_t, p_vecs_t[p_idx])
        nearest_s = int(np.argmax(sims)) if num_s > 0 else 0
        s_seeds = (
            set(session_modes.member_seed_ids[nearest_s])
            if nearest_s < len(session_modes.member_seed_ids)
            else set()
        )
        merged_member_seeds.append(sorted(p_seeds | s_seeds))

    return Modes(
        channel_vectors={"t": merged_vecs_t, "a": merged_vecs_a},
        weights=persistent_modes.weights.copy(),
        member_seed_ids=merged_member_seeds,
        has_channel={
            "t": True,
            "a": bool(persistent_modes.has_channel.get("a", False)),
        },
    )


def modes_to_dict(modes: Modes) -> dict[str, Any]:
    """Serialize Modes to JSON-compatible dictionary."""
    return {
        "channel_vectors": {k: v.tolist() for k, v in modes.channel_vectors.items()},
        "weights": modes.weights.tolist(),
        "member_seed_ids": modes.member_seed_ids,
        "has_channel": {k: bool(v) for k, v in modes.has_channel.items()},
    }


def modes_from_dict(data: dict[str, Any]) -> Modes:
    """Deserialize Modes from JSON-compatible dictionary."""
    return Modes(
        channel_vectors={
            k: np.array(v, dtype=np.float32) for k, v in data["channel_vectors"].items()
        },
        weights=np.array(data["weights"], dtype=np.float32),
        member_seed_ids=list(data.get("member_seed_ids", [])),
        has_channel={
            k: bool(v) for k, v in data.get("has_channel", {"t": True, "a": False}).items()
        },
    )
