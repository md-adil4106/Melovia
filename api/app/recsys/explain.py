"""Explainability Engine for Melovia recommendations.

Generates human-readable, signal-true explanations backed strictly by numeric
ranking signals. Every explanation sentence maps to at least one named signal
key and threshold.

Architecture Constraints:
- Pure Python (zero imports from FastAPI, Starlette, or SQLAlchemy).
- Deterministic evaluation and tie-breaking.
- Explicitly labels proxy scalars (*_idx) as approximate.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExplanationReason:
    """An individual signal-grounded reason explaining why a track was recommended."""

    id: str
    text: str
    signal_keys: list[str]
    evidence: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


class ExplanationBuilder:
    """Rule-based engine mapping ranking signals and discovery context to explanations."""

    # Controlled rule definitions
    RULE_SHARED_TAGS = "RULE_SHARED_TAGS"
    RULE_ENERGY_MATCH = "RULE_ENERGY_MATCH"
    RULE_VALENCE_MATCH = "RULE_VALENCE_MATCH"
    RULE_NEW_ARTIST = "RULE_NEW_ARTIST"
    RULE_FAMILIAR_ARTIST = "RULE_FAMILIAR_ARTIST"
    RULE_HIGH_NOVELTY = "RULE_HIGH_NOVELTY"
    RULE_LOW_NOVELTY = "RULE_LOW_NOVELTY"
    RULE_LESSER_KNOWN = "RULE_LESSER_KNOWN"
    RULE_MAINSTREAM = "RULE_MAINSTREAM"
    RULE_SEMANTIC_MATCH = "RULE_SEMANTIC_MATCH"
    RULE_ACOUSTIC_MATCH = "RULE_ACOUSTIC_MATCH"
    RULE_REGION_ALIGNMENT = "RULE_REGION_ALIGNMENT"
    RULE_SESSION_REFINEMENT = "RULE_SESSION_REFINEMENT"

    @classmethod
    def explain(
        cls,
        signals: dict[str, Any],
        track_meta: dict[str, Any],
        seed_meta: dict[str, Any] | None = None,
        discovery: float = 0.35,
        max_reasons: int = 4,
    ) -> list[ExplanationReason]:
        """Evaluate rule table against signals and return top 3-4 salience-weighted reasons."""
        matched_reasons: list[ExplanationReason] = []
        d = max(0.0, min(1.0, float(discovery)))

        seed_title = (
            seed_meta.get("title")
            if seed_meta
            else signals.get("nearest_seed_title") or "your seeds"
        )
        artist_name = track_meta.get("artist_name", "this artist")

        # -------------------------------------------------------------------------
        # Rule 1: Shared Tags
        # -------------------------------------------------------------------------
        raw_shared_tags = signals.get("shared_tags", [])
        if raw_shared_tags:
            tag_names: list[str] = []
            tag_weights: list[float] = []
            for item in raw_shared_tags:
                if isinstance(item, dict):
                    tag_names.append(item.get("tag", ""))
                    tag_weights.append(float(item.get("weight", 1.0)))
                elif isinstance(item, str):
                    tag_names.append(item)
                    tag_weights.append(1.0)
                elif hasattr(item, "tag"):
                    tag_names.append(item.tag)
                    tag_weights.append(float(getattr(item, "weight", 1.0)))

            tag_names = [t for t in tag_names if t]
            if tag_names:
                display_tags = tag_names[:3]
                if len(display_tags) == 1:
                    tag_str = display_tags[0]
                elif len(display_tags) == 2:
                    tag_str = f"{display_tags[0]} and {display_tags[1]}"
                else:
                    tag_str = f"{display_tags[0]}, {display_tags[1]}, and {display_tags[2]}"

                weight_val = sum(tag_weights[:3]) * (1.2 - 0.4 * d)
                matched_reasons.append(
                    ExplanationReason(
                        id=cls.RULE_SHARED_TAGS,
                        text=f"Shares {tag_str} with {seed_title}.",
                        signal_keys=["shared_tags", "nearest_seed_id"],
                        evidence={"shared_tags": display_tags, "nearest_seed_title": seed_title},
                        weight=round(weight_val, 4),
                    )
                )

        # -------------------------------------------------------------------------
        # Rule 2: Approximate Energy Match (|Δenergy_idx| < 0.12)
        # -------------------------------------------------------------------------
        scalar_deltas = signals.get("scalar_deltas", {})
        if "energy_idx" in scalar_deltas:
            d_energy = abs(float(scalar_deltas["energy_idx"]))
            if d_energy <= 0.12:
                # Proxy scalar: explicit (approx.) qualification
                pct_closeness = int(round((1.0 - d_energy) * 100))
                w_energy = (1.0 - d_energy) * (1.0 - 0.3 * d)
                matched_reasons.append(
                    ExplanationReason(
                        id=cls.RULE_ENERGY_MATCH,
                        text=(
                            f"Close to your preferred energy range "
                            f"({pct_closeness}% match) (approx.)."
                        ),
                        signal_keys=["scalar_deltas", "nearest_seed_id"],
                        evidence={"delta_energy_idx": round(d_energy, 4)},
                        weight=round(w_energy, 4),
                    )
                )

        # -------------------------------------------------------------------------
        # Rule 3: Approximate Valence Match (|Δvalence_idx| < 0.12)
        # -------------------------------------------------------------------------
        if "valence_idx" in scalar_deltas:
            d_valence = abs(float(scalar_deltas["valence_idx"]))
            if d_valence <= 0.12:
                # Proxy scalar: explicit (approx.) qualification
                pct_closeness = int(round((1.0 - d_valence) * 100))
                w_valence = (1.0 - d_valence) * (0.9 - 0.2 * d)
                matched_reasons.append(
                    ExplanationReason(
                        id=cls.RULE_VALENCE_MATCH,
                        text=(
                            f"Matches the emotional mood of your seeds "
                            f"({pct_closeness}% match) (approx.)."
                        ),
                        signal_keys=["scalar_deltas", "nearest_seed_id"],
                        evidence={"delta_valence_idx": round(d_valence, 4)},
                        weight=round(w_valence, 4),
                    )
                )

        # -------------------------------------------------------------------------
        # Rule 4 / 5: Artist Novelty vs Familiarity
        # -------------------------------------------------------------------------
        artist_new = bool(signals.get("artist_new", True))
        if artist_new:
            # Salience scales up when discovery level is higher
            w_art = 0.8 + 0.8 * d
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_NEW_ARTIST,
                    text=f"Introduces {artist_name}, a new artist for your listening profile.",
                    signal_keys=["artist_new"],
                    evidence={"artist_name": artist_name, "artist_new": True},
                    weight=round(w_art, 4),
                )
            )
        else:
            # Salience scales up when familiarity level is higher
            w_art = 1.6 * (1.0 - d)
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_FAMILIAR_ARTIST,
                    text=f"Features {artist_name}, an artist from your seed selections.",
                    signal_keys=["artist_new"],
                    evidence={"artist_name": artist_name, "artist_new": False},
                    weight=round(w_art, 4),
                )
            )

        # -------------------------------------------------------------------------
        # Rule 6 / 7: Novelty (Upper Quartile vs Lower Quartile)
        # -------------------------------------------------------------------------
        novelty_score = float(signals.get("novelty", 0.0))
        if novelty_score >= 0.55:
            w_nov = (novelty_score) * (0.8 + 1.0 * d)
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_HIGH_NOVELTY,
                    text="Expands into a less familiar sound within this genre space.",
                    signal_keys=["novelty"],
                    evidence={"novelty": round(novelty_score, 4)},
                    weight=round(w_nov, 4),
                )
            )
        elif novelty_score <= 0.25:
            w_fam = (1.0 - novelty_score) * (1.5 * (1.0 - d))
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_LOW_NOVELTY,
                    text="Solidifies familiar territory with core stylistic anchors.",
                    signal_keys=["novelty", "familiarity"],
                    evidence={
                        "novelty": round(novelty_score, 4),
                        "familiarity": round(1.0 - novelty_score, 4),
                    },
                    weight=round(w_fam, 4),
                )
            )

        # -------------------------------------------------------------------------
        # Rule 8 / 9: Popularity Band
        # -------------------------------------------------------------------------
        pop_pct = float(signals.get("popularity_pct", 50.0))
        if pop_pct <= 35.0:
            w_pop = (1.0 - pop_pct / 100.0) * (0.6 + 0.9 * d)
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_LESSER_KNOWN,
                    text=f"Lesser-known underground track ({round(pop_pct)}% popularity).",
                    signal_keys=["popularity_pct"],
                    evidence={"popularity_pct": round(pop_pct, 1)},
                    weight=round(w_pop, 4),
                )
            )
        elif pop_pct >= 75.0:
            w_pop = (pop_pct / 100.0) * (1.2 * (1.0 - d))
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_MAINSTREAM,
                    text=f"Well-known catalog benchmark track ({round(pop_pct)}% popularity).",
                    signal_keys=["popularity_pct"],
                    evidence={"popularity_pct": round(pop_pct, 1)},
                    weight=round(w_pop, 4),
                )
            )

        # -------------------------------------------------------------------------
        # Rule 10: Semantic Similarity (Channel t)
        # -------------------------------------------------------------------------
        pct_t = float(signals.get("pct_t", signals.get("percentile_t", 0.0)))
        sim_t = float(signals.get("sim_t", signals.get("raw_sim_t", 0.0)))
        if pct_t >= 0.80 or sim_t >= 0.70:
            w_sem = pct_t * (1.3 - 0.4 * d)
            pct_int = int(round(pct_t * 100))
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_SEMANTIC_MATCH,
                    text=f"Strong stylistic match with {seed_title} ({pct_int}% match).",
                    signal_keys=["pct_t", "sim_t", "nearest_seed_id"],
                    evidence={"pct_t": round(pct_t, 4), "sim_t": round(sim_t, 4)},
                    weight=round(w_sem, 4),
                )
            )

        # -------------------------------------------------------------------------
        # Rule 11: Acoustic Similarity (Channel a)
        # -------------------------------------------------------------------------
        pct_a = signals.get("pct_a", signals.get("percentile_a"))
        sim_a = signals.get("sim_a", signals.get("raw_sim_a"))
        if pct_a is not None and float(pct_a) >= 0.70:
            pct_a_float = float(pct_a)
            sim_a_float = float(sim_a) if sim_a is not None else 0.0
            w_ac = pct_a_float * 1.1
            pct_int = int(round(pct_a_float * 100))
            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_ACOUSTIC_MATCH,
                    text=(
                        f"Shares similar acoustic and rhythmic texture with your seeds "
                        f"({pct_int}% acoustic match)."
                    ),
                    signal_keys=["pct_a", "sim_a"],
                    evidence={"pct_a": round(pct_a_float, 4), "sim_a": round(sim_a_float, 4)},
                    weight=round(w_ac, 4),
                )
            )

        # -------------------------------------------------------------------------
        # Rule 12: Region Alignment / Exploration
        # -------------------------------------------------------------------------
        region_label = signals.get("region_label")
        region_id = signals.get("region_id")
        if region_label:
            if d > 0.5:
                w_reg = 0.8 + 0.5 * d
                reg_text = f"Explores the {region_label} aesthetic cluster."
            else:
                w_reg = 1.0 * (1.0 - d)
                reg_text = f"Anchored in the {region_label} soundscape."

            matched_reasons.append(
                ExplanationReason(
                    id=cls.RULE_REGION_ALIGNMENT,
                    text=reg_text,
                    signal_keys=["region_id", "region_label"],
                    evidence={"region_id": region_id, "region_label": region_label},
                    weight=round(w_reg, 4),
                )
            )

        # -------------------------------------------------------------------------
        # Rule 13: Session Refinement Steering
        # -------------------------------------------------------------------------
        session_facets = signals.get("session_facets_matched", [])
        if session_facets:
            facet_labels: list[str] = []
            has_proxy = False
            for f_item in session_facets:
                if isinstance(f_item, dict):
                    f_name = f_item.get("facet", "")
                    f_type = f_item.get("type", "")
                    f_detail = f_item.get("detail", "")
                    if f_name:
                        if f_type == "knob":
                            facet_labels.append(f"{f_name} ({f_detail})")
                            has_proxy = True
                        elif f_type == "boost_tag":
                            facet_labels.append(f"+{f_name}")
                        elif f_type == "suppress_tag":
                            facet_labels.append(f"no {f_name}")
                        else:
                            facet_labels.append(str(f_name))

            if facet_labels:
                top_facets = facet_labels[:3]
                facets_str = ", ".join(top_facets)
                approx_str = " (approx.)" if has_proxy else ""
                ref_text = f"Steered by session context matching {facets_str}{approx_str}."
                matched_reasons.append(
                    ExplanationReason(
                        id=cls.RULE_SESSION_REFINEMENT,
                        text=ref_text,
                        signal_keys=["session_facets_matched"],
                        evidence={"matched_facets": top_facets},
                        weight=1.6,
                    )
                )

        # Sort reasons by weight descending, breaking ties stably by rule id
        matched_reasons.sort(key=lambda r: (-r.weight, r.id))

        # Return top N reasons (clamped to max_reasons)
        return matched_reasons[:max_reasons]
