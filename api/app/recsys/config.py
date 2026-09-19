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

    # Default random seed for deterministic baselines and tie-breaking
    seed: int = 42
