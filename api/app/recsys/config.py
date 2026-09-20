"""Configuration and hyperparameter constants for the Melovia recommendation system.

Architecture Constraints:
- Pure Python (zero imports of FastAPI, Starlette, SQLAlchemy, or external web frameworks).
- All algorithm hyperparameters and thresholds reside here (no magic numbers elsewhere).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecsysConfig:
    """Immutable hyperparameters for taste aggregation, candidate retrieval, and scoring."""

    # Temperature parameter for smooth max (log-sum-exp) mode pooling
    tau: float = 8.0

    # Candidate retrieval depth per mode per channel
    k_candidates: int = 500

    # Multi-channel relevance weights (w_t + w_a = 1.0)
    weight_t: float = 0.60
    weight_a: float = 0.40

    # Seed constraints
    min_seeds: int = 1
    max_seeds: int = 10

    # Output list sizing
    default_n: int = 30
    max_n: int = 50

    # Taste mode clustering
    k_medoids_threshold_seeds: int = 6  # Use k-medoids if len(seeds) >= 6
    k_medoids_max_k: int = 3  # Maximum distinct modes when clustering
    silhouette_min_threshold: float = 0.05

    # Cache TTL for candidate pools (30 minutes in seconds)
    ttl_seconds: int = 1800

    # Discovery Control (Familiarity <-> Discovery) Reranking
    discovery_default: float = 0.35
    discovery_u_weight: float = 0.6  # U_i = (1 - 0.6*d)*R_i + 0.6*d*D_i
    novelty_mu_base: float = 0.15  # mu(d) = 0.15 + 0.5*d
    novelty_mu_slope: float = 0.5
    novelty_sigma: float = 0.15  # N_i = exp(-(nov - mu)^2 / (2 * 0.15^2))
    discovery_w_novelty: float = 0.5  # D_i = 0.5*N_i + 0.3*A_i + 0.2*(1 - P_i)
    discovery_w_artist: float = 0.3
    discovery_w_popularity: float = 0.2
    relevance_floor_base: float = 0.6  # floor = 0.6 - 0.3*d
    relevance_floor_slope: float = 0.3
    mmr_lambda_base: float = 1.0  # lambda = 1.0 - 0.5*d
    mmr_lambda_slope: float = 0.5
    sim_weight_t: float = 0.6  # sim = 0.6*cos_t + 0.3*cos_a + 0.1*[same_artist]
    sim_weight_a: float = 0.3
    sim_weight_artist: float = 0.1
    artist_cap_default: int = 2  # Max 2 tracks per artist for d < 0.7
    artist_cap_discovery: int = 1  # Max 1 track per artist for d >= 0.7
    artist_cap_threshold_d: float = 0.7

    # Default random seed for deterministic baselines and tie-breaking
    seed: int = 42

    # Feedback & Taste Adaptation (Phase 9)
    feedback_eta: float = 0.15  # Learning rate for positive feedback (like/save/replay/add)
    feedback_dislike_factor: float = 0.50  # Negative multiplier for dislike (-0.5 * eta)
    feedback_skip_factor: float = 0.125  # Weak negative multiplier for skip (-0.125 * eta)
    feedback_remove_factor: float = 0.25  # Milder negative multiplier for remove (-0.25 * eta)
    merge_alpha: float = 0.30  # Weight for merging session modes into persistent profile
    max_merge_drift: float = 0.25  # Maximum Euclidean drift cap during persistent merge

    # Playlist Sequencing (Phase 10)
    seq_w_tempo: float = 0.25  # Weight for tempo difference
    seq_w_energy: float = 0.35  # Weight for energy difference
    seq_w_semantic: float = 0.30  # Weight for semantic cosine distance (1 - cos_t)
    seq_w_artist_penalty: float = 5.0  # High penalty for adjacent same artist
    seq_w_arc: float = 0.40  # Weight for arc adherence penalty
    seq_max_2opt_iters: int = 150  # Maximum 2-opt search passes
    seq_min_scalar_coverage: float = 0.70  # Minimum scalar coverage to include in cost

    # Ablation and Feature Switches for Evaluation
    use_audio: bool = True
    use_mmr: bool = True
    popularity_correction: bool = True
    use_context: bool = False  # Architecture placeholder
    use_feedback: bool = False  # Feedback ablation switch

