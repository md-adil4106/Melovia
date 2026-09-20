"""Discovery Control (Familiarity <-> Discovery) Reranking module for Melovia.

Architecture Constraints:
- Pure Python and NumPy (zero imports of FastAPI, Starlette, or SQLAlchemy).
- Strictly deterministic tie-breaking by track_id.
- Dynamic audio channel renormalization when audio is missing.
- Emits comprehensive explainability signals: novelty, artist_new, popularity_pct,
  mmr_penalty, relevance, utility, and familiarity.
"""

from collections import defaultdict
from typing import Any

import numpy as np

from app.recsys.candidates import CandidatePool
from app.recsys.catalog import CatalogStore
from app.recsys.config import RecsysConfig
from app.recsys.scoring import ScoredItem, ScoredList


def rerank_candidates(
    pool: CandidatePool,
    scored_list: ScoredList,
    catalog: CatalogStore,
    discovery: float = 0.35,
    n: int = 30,
    config: RecsysConfig | None = None,
) -> ScoredList:
    """Rerank candidates using the Discovery Control (Familiarity <-> Discovery) algorithm.

    Algorithm:
    1. Extract known seeds K. Compute novelty nov_i = 1 - max_{j in K} cos(x_i^t, x_j^t).
    2. A_i = 1[artist_i not in known artists].
    3. P_i = popularity_pct / 100.0.
    4. mu(d) = 0.15 + 0.5 * d.
    5. N_i = exp(-(nov_i - mu)^2 / (2 * 0.15^2)).
    6. D_i = 0.5 * N_i + 0.3 * A_i + 0.2 * (1 - P_i).
    7. U_i = (1 - 0.6 * d) * R_i + 0.6 * d * D_i.
    8. Relevance floor: drop candidates where R_i < 0.6 - 0.3 * d.
    9. MMR selection:
       argmax_{i} [lambda * U_i - (1 - lambda) * max_{j in S} sim(i, j)]
       where lambda = 1 - 0.5 * d,
       sim(i, j) = 0.6 * cos_t + 0.3 * cos_a (if both have audio) + 0.1 * [same artist],
       hard artist cap = 2 (1 when d >= 0.7),
       tie-break by track_id.
    """
    cfg = config or RecsysConfig()
    p_size = pool.size

    if p_size == 0 or len(scored_list.items) == 0:
        return ScoredList(items=[], total_candidates=0)

    # Clamp discovery parameter to [0.0, 1.0]
    d = float(np.clip(discovery, 0.0, 1.0))
    target_n = max(1, min(n, p_size))

    track_indices = pool.track_indices  # shape (P,)
    modes = pool.modes

    # 1. Identify known seeds K and known artists
    all_seed_ids: list[str] = [sid for m_seeds in modes.member_seed_ids for sid in m_seeds]
    seed_indices = [catalog.get_idx(sid) for sid in all_seed_ids if catalog.contains_id(sid)]

    artist_col = catalog._tracks_metadata.get("artist_id", [])
    known_artists: set[str] = set()
    for s_idx in seed_indices:
        if artist_col and s_idx < len(artist_col):
            art_id = str(artist_col[s_idx])
            if art_id:
                known_artists.add(art_id)

    # Semantic taste vectors of seeds (shape: (K, dim_t))
    if seed_indices:
        seed_vecs_t = catalog.vectors_t[seed_indices]
    else:
        seed_vecs_t = np.empty((0, 128), dtype=np.float32)

    # 2. Candidate semantic vectors & Novelty computation
    cand_vecs_t = catalog.vectors_t[track_indices]  # (P, dim_t)
    if seed_vecs_t.shape[0] > 0:
        sims_to_seeds = np.dot(cand_vecs_t, seed_vecs_t.T)  # (P, K)
        max_seed_sim = np.max(sims_to_seeds, axis=1)  # (P,)
        nov = 1.0 - max_seed_sim
    else:
        nov = np.ones(p_size, dtype=np.float32)

    # 3. Artist newness A_i in {0, 1}
    a_new = np.zeros(p_size, dtype=np.float32)
    for i in range(p_size):
        t_idx = int(track_indices[i])
        art_id = str(artist_col[t_idx]) if artist_col and t_idx < len(artist_col) else ""
        if art_id and art_id not in known_artists:
            a_new[i] = 1.0

    # 4. Normalized popularity P_i in [0.0, 1.0]
    pop_col = catalog._tracks_metadata.get("popularity_pct", [])
    pop_norm = np.zeros(p_size, dtype=np.float32)
    pop_raw = np.zeros(p_size, dtype=np.float32)
    for i in range(p_size):
        t_idx = int(track_indices[i])
        raw_p = float(pop_col[t_idx]) if pop_col and t_idx < len(pop_col) else 50.0
        pop_raw[i] = raw_p
        pop_norm[i] = float(np.clip(raw_p / 100.0, 0.0, 1.0))

    # 5. Gaussian target novelty score N_i
    mu = cfg.novelty_mu_base + cfg.novelty_mu_slope * d
    sigma_sq = cfg.novelty_sigma**2
    n_score = np.exp(-((nov - mu) ** 2) / (2.0 * sigma_sq)).astype(np.float32)

    # 6. Discovery score D_i
    d_score = (
        cfg.discovery_w_novelty * n_score
        + cfg.discovery_w_artist * a_new
        + cfg.discovery_w_popularity * (1.0 - pop_norm)
    ).astype(np.float32)

    # 7. Map base relevance scores R_i from scored_list
    idx_to_relevance = {item.track_idx: item.score for item in scored_list.items}
    relevance = np.array(
        [idx_to_relevance.get(int(idx), 0.0) for idx in track_indices],
        dtype=np.float32,
    )

    # 8. Unadjusted Utility U_i
    u_weight = cfg.discovery_u_weight * d
    utility = ((1.0 - u_weight) * relevance + u_weight * d_score).astype(np.float32)

    # 9. Relevance floor filtering
    relevance_floor = cfg.relevance_floor_base - cfg.relevance_floor_slope * d
    surviving_mask = relevance >= relevance_floor

    # Safety fallback: ensure at least target_n candidates survive
    if np.sum(surviving_mask) < target_n:
        # If strict floor leaves fewer than target_n, keep top candidates by utility
        top_utility_order = np.argsort(-utility)
        surviving_mask[top_utility_order[:target_n]] = True

    surviving_indices = np.where(surviving_mask)[0]
    if len(surviving_indices) == 0:
        surviving_indices = np.arange(p_size)

    # 10. MMR Selection with Hard Artist Cap
    artist_cap = (
        cfg.artist_cap_discovery if d >= cfg.artist_cap_threshold_d else cfg.artist_cap_default
    )
    mmr_lambda = cfg.mmr_lambda_base - cfg.mmr_lambda_slope * d

    # Pre-extract vector representations and metadata for surviving pool
    surv_track_indices = track_indices[surviving_indices]
    surv_utility = utility[surviving_indices]
    surv_relevance = relevance[surviving_indices]
    surv_nov = nov[surviving_indices]
    surv_a_new = a_new[surviving_indices]
    surv_pop_raw = pop_raw[surviving_indices]
    surv_d_score = d_score[surviving_indices]

    surv_vecs_t = catalog.vectors_t[surv_track_indices]  # (S_pool, dim_t)

    # Audio vectors and masks
    has_audio_catalog = catalog.mask_a
    surv_mask_a = has_audio_catalog[surv_track_indices]
    surv_vecs_a = (
        catalog.vectors_a[surv_track_indices]
        if modes.has_channel.get("a", False)
        else np.empty((len(surviving_indices), 0), dtype=np.float32)
    )

    surv_artist_ids: list[str] = [
        str(artist_col[int(idx)]) if artist_col and int(idx) < len(artist_col) else ""
        for idx in surv_track_indices
    ]
    surv_track_ids: list[str] = [catalog.get_id(int(idx)) for idx in surv_track_indices]

    s_pool_size = len(surviving_indices)
    selected_in_s: list[int] = []
    selected_artists_count: dict[str, int] = defaultdict(int)

    # max_sim_to_s: maximum similarity of each surviving candidate to any item in S
    max_sim_to_s = np.zeros(s_pool_size, dtype=np.float32)
    in_selected = np.zeros(s_pool_size, dtype=bool)

    # Cached MMR penalties for explainability
    mmr_penalties = np.zeros(s_pool_size, dtype=np.float32)

    # Pre-compute weights
    w_sim_t = cfg.sim_weight_t
    w_sim_a = cfg.sim_weight_a
    w_sim_artist = cfg.sim_weight_artist
    # Renormalized semantic weight when audio is absent
    w_sim_t_no_audio = w_sim_t + w_sim_a  # 0.6 + 0.3 = 0.9

    for _ in range(min(target_n, s_pool_size)):
        best_candidate_idx = -1
        best_mmr_score = -float("inf")
        best_tie_break = ""

        # Evaluate all available candidates
        for c in range(s_pool_size):
            if in_selected[c]:
                continue

            art_id = surv_artist_ids[c]
            if art_id and selected_artists_count[art_id] >= artist_cap:
                continue

            if len(selected_in_s) == 0:
                score_c = float(mmr_lambda * surv_utility[c])
            else:
                score_c = float(
                    mmr_lambda * surv_utility[c] - (1.0 - mmr_lambda) * max_sim_to_s[c]
                )

            t_id = surv_track_ids[c]

            # Compare with current best using (score, -track_id) for deterministic tie-breaking
            if score_c > best_mmr_score:
                best_mmr_score = score_c
                best_candidate_idx = c
                best_tie_break = t_id
            elif abs(score_c - best_mmr_score) < 1e-9:
                if best_candidate_idx == -1 or t_id < best_tie_break:
                    best_mmr_score = score_c
                    best_candidate_idx = c
                    best_tie_break = t_id

        if best_candidate_idx == -1:
            # All remaining candidates violate artist cap or pool is exhausted
            break

        # Select best candidate
        c_star = best_candidate_idx
        selected_in_s.append(c_star)
        in_selected[c_star] = True
        art_star = surv_artist_ids[c_star]
        if art_star:
            selected_artists_count[art_star] += 1

        mmr_penalties[c_star] = max_sim_to_s[c_star]

        # Update max_sim_to_s for remaining candidates with respect to c_star
        vec_t_star = surv_vecs_t[c_star]
        has_a_star = surv_mask_a[c_star]
        vec_a_star = surv_vecs_a[c_star] if has_a_star and surv_vecs_a.shape[1] > 0 else None

        # Dot products with c_star across all surviving candidates in channel t
        sim_t_all = np.dot(surv_vecs_t, vec_t_star)

        # Dot products in channel a if both have audio
        if has_a_star and vec_a_star is not None:
            sim_a_all = np.dot(surv_vecs_a, vec_a_star)
        else:
            sim_a_all = np.zeros(s_pool_size, dtype=np.float32)

        for c in range(s_pool_size):
            if in_selected[c]:
                continue

            # Check artist equality
            same_artist = 1.0 if (art_star and surv_artist_ids[c] == art_star) else 0.0

            if has_a_star and surv_mask_a[c]:
                pair_sim = (
                    w_sim_t * sim_t_all[c]
                    + w_sim_a * sim_a_all[c]
                    + w_sim_artist * same_artist
                )
            else:
                pair_sim = w_sim_t_no_audio * sim_t_all[c] + w_sim_artist * same_artist

            if pair_sim > max_sim_to_s[c]:
                max_sim_to_s[c] = float(pair_sim)

    # 11. Build final ScoredItem list
    reranked_items: list[ScoredItem] = []
    for c in selected_in_s:
        t_idx = int(surv_track_indices[c])
        t_id = surv_track_ids[c]

        # Look up existing signals from base scoring if available
        base_item = next((it for it in scored_list.items if it.track_idx == t_idx), None)
        signals: dict[str, Any] = dict(base_item.signals) if base_item and base_item.signals else {}

        # Add Discovery Control explainability signals
        signals.update(
            {
                "novelty": round(float(surv_nov[c]), 4),
                "familiarity": round(float(1.0 - surv_nov[c]), 4),
                "artist_new": bool(surv_a_new[c] == 1.0),
                "popularity_pct": round(float(surv_pop_raw[c]), 2),
                "mmr_penalty": round(float(mmr_penalties[c]), 4),
                "relevance": round(float(surv_relevance[c]), 4),
                "utility": round(float(surv_utility[c]), 4),
                "discovery_score": round(float(surv_d_score[c]), 4),
                "discovery_d": round(d, 3),
            }
        )

        reranked_items.append(
            ScoredItem(
                track_idx=t_idx,
                track_id=t_id,
                score=round(float(surv_utility[c]), 5),
                signals=signals,
            )
        )

    return ScoredList(items=reranked_items, total_candidates=p_size)
