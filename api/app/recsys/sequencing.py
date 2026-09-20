"""Playlist Sequencing module for Melovia.

Pure Python and deterministic playlist sequencing that transforms an unorganized
selection of tracks into a smooth, journey-like listening progression with predictable
arc dynamics, smooth inter-track transitions, and hard artist non-adjacency.

Architecture Constraints:
- Pure Python and NumPy (zero imports from FastAPI, Starlette, SQLAlchemy, or DB).
- Strictly deterministic tie-breaking (by alphabetical track_id and index pairs).
- Dynamic scalar auto-drop when coverage in the candidate pool is below threshold.
- Deterministic 2-opt local search with bounded iteration limit.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from app.recsys.config import RecsysConfig


class ArcType(StrEnum):
    """Supported playlist energy progression arcs."""

    STEADY = "steady"
    BUILD = "build"
    WAVE = "wave"
    WIND_DOWN = "wind_down"


@dataclass(frozen=True)
class TransitionCostItem:
    """Per-hop transition metrics between adjacent tracks."""

    from_track_id: str
    to_track_id: str
    tempo_delta: float | None
    energy_delta: float | None
    semantic_distance: float
    same_artist: bool
    cost: float


@dataclass(frozen=True)
class ArcPoint:
    """Target versus realized energy at a specific sequence position."""

    position: int
    normalized_pos: float
    target_energy: float
    realized_energy: float | None
    track_id: str


@dataclass
class PlaylistSequenceResult:
    """Complete output of deterministic playlist sequencing."""

    ordered_tracks: list[dict[str, Any]]
    transitions: list[TransitionCostItem]
    arc_points: list[ArcPoint]
    total_cost: float
    mean_transition_cost: float
    arc_correlation: float
    active_weights: dict[str, float]
    dropped_features: list[str]


def generate_arc_target(
    arc: ArcType | str,
    length: int,
    energy_delta: float = 0.0,
) -> np.ndarray:
    """Generate target energy curve for normalized playlist positions in [0, 1].

    Parameters
    ----------
    arc: ArcType or str ("steady", "build", "wave", "wind_down").
    length: Desired number of tracks in sequence (>= 1).
    energy_delta: Optional shift from conversational session steering in [-1.0, 1.0].

    Returns
    -------
    np.ndarray of shape (length,) with target energy values in [0.05, 0.95].
    """
    if length <= 0:
        return np.array([], dtype=np.float64)

    arc_str = arc.value if isinstance(arc, ArcType) else str(arc).lower()

    if length == 1:
        u = np.array([0.5], dtype=np.float64)
    else:
        u = np.linspace(0.0, 1.0, length, dtype=np.float64)

    if arc_str == ArcType.STEADY.value:
        # Flat baseline centered at 0.50
        base = np.full(length, 0.50, dtype=np.float64)
    elif arc_str == ArcType.BUILD.value:
        # Monotonically ascending ramp: 0.25 -> 0.80
        base = 0.25 + 0.55 * u
    elif arc_str == ArcType.WIND_DOWN.value:
        # Monotonically descending ramp: 0.80 -> 0.25
        base = 0.80 - 0.55 * u
    elif arc_str == ArcType.WAVE.value:
        # Sinusoidal rise and fall: 0.35 -> 0.80 -> 0.35
        base = 0.35 + 0.45 * np.sin(np.pi * u)
    else:
        # Fallback to steady
        base = np.full(length, 0.50, dtype=np.float64)

    if abs(energy_delta) > 1e-4:
        # Shift target arc based on intent delta (scaled by 0.20)
        base = base + 0.20 * float(np.clip(energy_delta, -1.0, 1.0))

    return np.clip(base, 0.05, 0.95)


def _compute_pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation coefficient between two 1D arrays."""
    if len(x) <= 1 or len(y) <= 1:
        return 0.0
    x_std = float(np.std(x))
    y_std = float(np.std(y))
    if x_std < 1e-5 or y_std < 1e-5:
        # Near-zero variance (e.g. flat steady curve); report 0.0
        return 0.0

    vx = x - np.mean(x)
    vy = y - np.mean(y)
    corr = float(np.dot(vx, vy) / (len(x) * x_std * y_std))
    return float(np.clip(corr, -1.0, 1.0))


def _extract_track_scalar(track: dict[str, Any], key: str) -> float | None:
    """Safely extract numeric scalar from track dictionary."""
    val = track.get(key)
    if val is not None:
        try:
            f = float(val)
            if not np.isnan(f):
                return f
        except (ValueError, TypeError):
            pass

    scalars = track.get("scalars")
    if isinstance(scalars, dict):
        s_val = scalars.get(key)
        if s_val is not None:
            try:
                f = float(s_val)
                if not np.isnan(f):
                    return f
            except (ValueError, TypeError):
                pass
        # Check alias if key is energy_idx
        if key == "energy_idx":
            e_val = scalars.get("energy")
            if e_val is not None:
                try:
                    f = float(e_val)
                    if not np.isnan(f):
                        return f
                except (ValueError, TypeError):
                    pass
    return None


def sequence_playlist(
    tracks: Sequence[dict[str, Any]],
    arc: ArcType | str = ArcType.BUILD,
    length: int | None = None,
    config: RecsysConfig | None = None,
    vectors_t: np.ndarray | None = None,
    energy_delta: float = 0.0,
) -> PlaylistSequenceResult:
    """Sequence a collection of candidate tracks into a coherent listening progression.

    Parameters
    ----------
    tracks: Sequence of track dictionaries. Each dict should include:
        - "id" or "track_id": canonical track UUID
        - "artist_id": canonical artist UUID
        - "scalars" (dict) or direct keys for "energy_idx" and "tempo_norm"
    arc: ArcType or string preset ("steady", "build", "wave", "wind_down").
    length: Desired sequence length. Defaults to len(tracks), capped between 1 and len(tracks).
    config: RecsysConfig with sequencing weights and 2-opt thresholds.
    vectors_t: Optional (N, dim_t) L2-normalized semantic vector array.
    energy_delta: Optional intent delta in [-1.0, 1.0].

    Returns
    -------
    PlaylistSequenceResult with ordered tracks, transitions, arc points, and flow metrics.
    """
    cfg = config or RecsysConfig()
    n_tracks = len(tracks)

    if n_tracks == 0:
        return PlaylistSequenceResult(
            ordered_tracks=[],
            transitions=[],
            arc_points=[],
            total_cost=0.0,
            mean_transition_cost=0.0,
            arc_correlation=0.0,
            active_weights={},
            dropped_features=[],
        )

    target_length = n_tracks if length is None else max(1, min(length, n_tracks))

    # 1. Extract track identifiers, artists, and scalars
    track_ids: list[str] = []
    artist_ids: list[str] = []
    tempos: list[float | None] = []
    energies: list[float | None] = []

    for t in tracks:
        tid = str(t.get("id") or t.get("track_id") or "")
        aid = str(t.get("artist_id") or "")
        track_ids.append(tid)
        artist_ids.append(aid)
        tempos.append(_extract_track_scalar(t, "tempo_norm"))
        energies.append(_extract_track_scalar(t, "energy_idx"))

    # 2. Check scalar coverage and dynamically drop low-coverage features
    valid_tempo_count = sum(1 for v in tempos if v is not None)
    valid_energy_count = sum(1 for v in energies if v is not None)

    tempo_coverage = valid_tempo_count / n_tracks
    energy_coverage = valid_energy_count / n_tracks

    dropped_features: list[str] = []
    w_tempo = cfg.seq_w_tempo
    w_energy = cfg.seq_w_energy
    w_semantic = cfg.seq_w_semantic
    w_artist = cfg.seq_w_artist_penalty
    w_arc = cfg.seq_w_arc

    if tempo_coverage < cfg.seq_min_scalar_coverage:
        w_tempo = 0.0
        dropped_features.append("tempo_norm")

    if energy_coverage < cfg.seq_min_scalar_coverage:
        w_energy = 0.0
        w_arc = 0.0
        dropped_features.append("energy_idx")

    active_weights = {
        "tempo": w_tempo,
        "energy": w_energy,
        "semantic": w_semantic,
        "artist_penalty": w_artist,
        "arc": w_arc,
    }

    # 3. Generate target arc array of length target_length
    target_arc = generate_arc_target(arc, target_length, energy_delta=energy_delta)

    # 4. Precompute semantic cosine distances if vectors_t is provided
    if vectors_t is not None and len(vectors_t) == n_tracks:
        # Cosine distance = 1.0 - clip(dot_product, -1.0, 1.0)
        dots = np.clip(np.dot(vectors_t, vectors_t.T), -1.0, 1.0)
        sem_dist_matrix = np.clip(1.0 - dots, 0.0, 2.0)
    else:
        sem_dist_matrix = np.zeros((n_tracks, n_tracks), dtype=np.float64)

    # 5. Precompute pairwise transition cost matrix C_trans (N x N)
    c_trans = np.zeros((n_tracks, n_tracks), dtype=np.float64)
    for i in range(n_tracks):
        for j in range(i + 1, n_tracks):
            # Tempo difference
            ti, tj = tempos[i], tempos[j]
            t_diff = abs(ti - tj) if (ti is not None and tj is not None) else 0.0

            # Energy difference
            ei, ej = energies[i], energies[j]
            e_diff = abs(ei - ej) if (ei is not None and ej is not None) else 0.0
            # Semantic distance
            s_dist = sem_dist_matrix[i, j]
            # Same artist penalty
            same_art = 1.0 if (artist_ids[i] and artist_ids[i] == artist_ids[j]) else 0.0

            cost = w_tempo * t_diff + w_energy * e_diff + w_semantic * s_dist + w_artist * same_art
            c_trans[i, j] = cost
            c_trans[j, i] = cost

    # 6. Precompute arc adherence penalty matrix C_arc (N x target_length)
    c_arc = np.zeros((n_tracks, target_length), dtype=np.float64)
    if w_arc > 0.0:
        for i in range(n_tracks):
            e_val = energies[i]
            if e_val is not None:
                diffs = np.abs(e_val - target_arc)
                c_arc[i, :] = w_arc * diffs

    # 7. Greedy Nearest-Neighbor Initialization
    # Step 7a: Select seed track p_0 with minimum initial arc distance C_arc[i, 0]
    # Stable tie-break by track_id
    candidates_pool = list(range(n_tracks))
    best_seed = min(
        candidates_pool,
        key=lambda idx: (c_arc[idx, 0], track_ids[idx]),
    )

    perm: list[int] = [best_seed]
    candidates_pool.remove(best_seed)

    # Step 7b: Sequentially select p_k minimizing transition cost + arc penalty
    for pos in range(1, target_length):
        prev = perm[-1]
        best_next = min(
            candidates_pool,
            key=lambda idx: (c_trans[prev, idx] + c_arc[idx, pos], track_ids[idx]),
        )
        perm.append(best_next)
        candidates_pool.remove(best_next)

    # 8. Bounded 2-Opt Local Search
    # Evaluate subsegment reversals perm[i : j + 1] to minimize total sequence cost
    max_iters = max(1, cfg.seq_max_2opt_iters)
    for _ in range(max_iters):
        best_delta = -1e-6
        best_i = -1
        best_j = -1

        for i in range(target_length - 1):
            for j in range(i + 1, target_length):
                # Calculate change in transition cost at boundaries
                delta_trans = 0.0
                if i > 0:
                    delta_trans += c_trans[perm[i - 1], perm[j]] - c_trans[perm[i - 1], perm[i]]
                if j < target_length - 1:
                    delta_trans += c_trans[perm[i], perm[j + 1]] - c_trans[perm[j], perm[j + 1]]

                # Calculate change in arc penalty across the reversed block [i, j]
                # Track at position k moves to position i + j - k
                delta_arc = 0.0
                if w_arc > 0.0:
                    for k in range(i, j + 1):
                        new_pos = i + j - k
                        delta_arc += c_arc[perm[k], new_pos] - c_arc[perm[k], k]

                move_delta = delta_trans + delta_arc
                # Stable tie-break: strictly more negative, then smallest i, smallest j
                if move_delta < best_delta:
                    best_delta = move_delta
                    best_i = i
                    best_j = j

        # Apply best improving move
        if best_i >= 0 and best_j >= 0:
            perm[best_i : best_j + 1] = perm[best_i : best_j + 1][::-1]
        else:
            # Local optimum reached
            break

    # 9. Assemble Output Structures & Flow Metrics
    ordered_tracks = [tracks[idx] for idx in perm]
    transitions: list[TransitionCostItem] = []
    total_transition_cost = 0.0

    for pos in range(target_length - 1):
        idx_a = perm[pos]
        idx_b = perm[pos + 1]
        t_a, t_b = tempos[idx_a], tempos[idx_b]
        e_a, e_b = energies[idx_a], energies[idx_b]

        t_delta = abs(t_a - t_b) if (t_a is not None and t_b is not None) else None
        e_delta = abs(e_a - e_b) if (e_a is not None and e_b is not None) else None
        s_dist = float(sem_dist_matrix[idx_a, idx_b])
        same_art = bool(artist_ids[idx_a] and artist_ids[idx_a] == artist_ids[idx_b])
        step_cost = float(c_trans[idx_a, idx_b])

        transitions.append(
            TransitionCostItem(
                from_track_id=track_ids[idx_a],
                to_track_id=track_ids[idx_b],
                tempo_delta=float(t_delta) if t_delta is not None else None,
                energy_delta=float(e_delta) if e_delta is not None else None,
                semantic_distance=s_dist,
                same_artist=same_art,
                cost=step_cost,
            )
        )
        total_transition_cost += step_cost

    mean_trans_cost = total_transition_cost / (target_length - 1) if target_length > 1 else 0.0

    arc_points: list[ArcPoint] = []
    realized_energies: list[float] = []
    total_arc_penalty = 0.0

    for pos in range(target_length):
        idx = perm[pos]
        norm_pos = float(pos / (target_length - 1)) if target_length > 1 else 0.5
        tgt = float(target_arc[pos])
        real_e = energies[idx]
        if real_e is not None:
            realized_energies.append(real_e)
            total_arc_penalty += float(c_arc[idx, pos])
        else:
            realized_energies.append(tgt)

        arc_points.append(
            ArcPoint(
                position=pos,
                normalized_pos=norm_pos,
                target_energy=tgt,
                realized_energy=float(real_e) if real_e is not None else None,
                track_id=track_ids[idx],
            )
        )

    # Compute realized arc correlation
    if len(realized_energies) == target_length:
        arc_corr = _compute_pearson_correlation(
            np.array(realized_energies, dtype=np.float64), target_arc
        )
    else:
        arc_corr = 0.0

    total_cost = total_transition_cost + total_arc_penalty

    return PlaylistSequenceResult(
        ordered_tracks=ordered_tracks,
        transitions=transitions,
        arc_points=arc_points,
        total_cost=float(total_cost),
        mean_transition_cost=float(mean_trans_cost),
        arc_correlation=float(arc_corr),
        active_weights=active_weights,
        dropped_features=dropped_features,
    )
