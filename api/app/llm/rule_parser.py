"""Deterministic rule-based intent parser for Melovia refinement.

Architecture & Constraints:
- Pure Python, zero network calls, zero external dependencies.
- Serves as the guaranteed deterministic fallback when LLM is disabled, times out, or fails.
- Maps natural-language keywords to validated Refinement constraints.
- Identifies and isolates unsupported requests into the 'unsupported' field.
"""

import re

from app.schemas.refinement import ArcType, KnobDeltas, Refinement, TagWeight


class RuleBasedRefinementParser:
    """Deterministic keyword and pattern parser for musical intent."""

    # Keywords mapping to scalar knob deltas
    ENERGY_LOW_KEYWORDS = {
        "less energetic",
        "not energetic",
        "low energy",
        "less energy",
        "calm",
        "calm it down",
        "chill",
        "relaxing",
        "mellow",
        "soft",
        "quieter",
        "gentle",
        "peaceful",
    }
    ENERGY_HIGH_KEYWORDS = {
        "energetic",
        "more energy",
        "high energy",
        "hype",
        "intense",
        "punchy",
        "powerful",
        "heavy",
        "drive",
        "banger",
    }

    VALENCE_HIGH_KEYWORDS = {
        "too sad",
        "happier",
        "uplifting",
        "cheerful",
        "positive",
        "joyful",
        "bright",
        "less depressing",
        "sunnier",
    }
    VALENCE_LOW_KEYWORDS = {
        "sadder",
        "melancholy",
        "melancholic",
        "darker",
        "gloomy",
        "somber",
        "depressing",
        "moody",
    }

    TEMPO_HIGH_KEYWORDS = {
        "faster",
        "speed up",
        "speed it up",
        "pick up the tempo",
        "uptempo",
        "high bpm",
        "quicker",
        "rapid",
        "speedier",
    }
    TEMPO_LOW_KEYWORDS = {
        "slower",
        "slow down",
        "slow it down",
        "downtempo",
        "low bpm",
        "chill tempo",
    }

    ACOUSTIC_LOW_KEYWORDS = {
        "less acoustic",
        "not acoustic",
        "more electronic",
        "electronic",
        "synthesizer",
        "synths",
        "digital",
    }
    ACOUSTIC_HIGH_KEYWORDS = {
        "more acoustic",
        "acoustic",
        "unplugged",
        "organic",
        "natural",
        "real instruments",
    }

    DANCE_LOW_KEYWORDS = {
        "less danceable",
        "undanceable",
        "non-danceable",
    }
    DANCE_HIGH_KEYWORDS = {
        "danceable",
        "more danceable",
        "groove",
        "groovy",
        "party",
        "club",
        "rhythmic",
    }

    NOVELTY_HIGH_KEYWORDS = {
        "less mainstream",
        "underground",
        "rare",
        "hidden gems",
        "indie",
        "deep cuts",
        "obscure",
        "more discovery",
    }
    NOVELTY_LOW_KEYWORDS = {
        "less discovery",
        "more mainstream",
        "popular",
        "hits",
        "classic hits",
        "familiar",
        "well known",
    }

    # Common tags detectable by keyword
    COMMON_TAGS = [
        "rock",
        "post-punk",
        "synthwave",
        "ambient",
        "electronic",
        "jazz",
        "metal",
        "pop",
        "folk",
        "techno",
        "lo-fi",
        "hip-hop",
        "indie-rock",
        "darkwave",
        "shoegaze",
        "industrial",
        "dream-pop",
        "classical",
        "punk",
    ]

    @classmethod
    def parse(cls, utterance: str) -> Refinement:
        """Parse natural language utterance into structured Refinement."""
        text = utterance.strip().lower()

        knobs_dict: dict[str, float] = {
            "energy": 0.0,
            "valence": 0.0,
            "tempo": 0.0,
            "acousticness": 0.0,
            "danceability": 0.0,
            "novelty": 0.0,
        }
        popularity_ceiling: float | None = None
        boost_tags: list[TagWeight] = []
        suppress_tags: list[TagWeight] = []
        arc: ArcType | None = None
        unsupported: list[str] = []

        # 1. Scalar Knobs
        if any(k in text for k in cls.ENERGY_LOW_KEYWORDS):
            knobs_dict["energy"] -= 0.5
        elif any(k in text for k in cls.ENERGY_HIGH_KEYWORDS):
            knobs_dict["energy"] += 0.5

        if any(k in text for k in cls.VALENCE_HIGH_KEYWORDS):
            knobs_dict["valence"] += 0.4
        elif any(k in text for k in cls.VALENCE_LOW_KEYWORDS):
            knobs_dict["valence"] -= 0.4

        if any(k in text for k in cls.TEMPO_HIGH_KEYWORDS):
            knobs_dict["tempo"] += 0.4
        elif any(k in text for k in cls.TEMPO_LOW_KEYWORDS):
            knobs_dict["tempo"] -= 0.4

        if any(k in text for k in cls.ACOUSTIC_LOW_KEYWORDS):
            knobs_dict["acousticness"] -= 0.5
        elif any(k in text for k in cls.ACOUSTIC_HIGH_KEYWORDS):
            knobs_dict["acousticness"] += 0.5

        if any(k in text for k in cls.DANCE_LOW_KEYWORDS):
            knobs_dict["danceability"] -= 0.5
        elif any(k in text for k in cls.DANCE_HIGH_KEYWORDS):
            knobs_dict["danceability"] += 0.5

        if any(k in text for k in cls.NOVELTY_HIGH_KEYWORDS):
            knobs_dict["novelty"] += 0.5
            popularity_ceiling = 0.40
        elif any(k in text for k in cls.NOVELTY_LOW_KEYWORDS):
            knobs_dict["novelty"] -= 0.5

        # Clamp knobs to [-1.0, 1.0]
        for k in knobs_dict:
            knobs_dict[k] = max(-1.0, min(1.0, knobs_dict[k]))

        # 2. Arcs & Thematic Intention
        if "night drive" in text:
            arc = ArcType.STEADY
            boost_tags.append(TagWeight(tag="synthwave", weight=0.8))
            knobs_dict["tempo"] = max(-1.0, min(1.0, knobs_dict["tempo"] + 0.2))
        elif "build" in text or "build up" in text or "workout" in text or "gym" in text:
            arc = ArcType.BUILD
            knobs_dict["energy"] = max(-1.0, min(1.0, knobs_dict["energy"] + 0.4))
        elif "wind down" in text or "sleep" in text or "bedtime" in text:
            arc = ArcType.WIND_DOWN
            knobs_dict["energy"] = max(-1.0, min(1.0, knobs_dict["energy"] - 0.5))
        elif "wave" in text or "rollercoaster" in text:
            arc = ArcType.WAVE

        # 3. Tags (Boost & Suppress)
        for tag in cls.COMMON_TAGS:
            # Check suppression pattern ("no rock", "without rock", "less rock")
            suppress_pattern = rf"\b(?:no|without|less|not|exclude)\s+{re.escape(tag)}\b"
            if re.search(suppress_pattern, text):
                if not any(st.tag == tag for st in suppress_tags):
                    suppress_tags.append(TagWeight(tag=tag, weight=0.8))
                continue

            # Check boost pattern ("add rock", "more rock", "with rock", or simply "rock")
            boost_pattern = rf"\b(?:add|more|with|keep|some)?\s*{re.escape(tag)}\b"
            if re.search(boost_pattern, text) and not any(bt.tag == tag for bt in boost_tags):
                # Avoid matching "rock" inside "math-rock" or "indie-rock" prematurely
                has_compound_rock = (
                    "math-rock" in text or "indie-rock" in text or "post-rock" in text
                )
                if tag == "rock" and has_compound_rock:
                    continue
                boost_tags.append(TagWeight(tag=tag, weight=0.8))

        # 4. Check for known unsupported requests
        vocal_gender_terms = (
            "female",
            "woman",
            "girl singer",
            "male vocalist",
            "guy singer",
            "vocal gender",
        )
        if any(w in text for w in vocal_gender_terms):
            unsupported.append("vocal gender filtering")

        if any(w in text for w in ("spanish", "french", "japanese", "german", "lyrics in")):
            unsupported.append("lyrics language filtering")

        if any(w in text for w in ("solo", "violin", "saxophone", "trumpet solo", "guitar solo")):
            unsupported.append("isolated solo instrument filtering")

        if any(w in text for w in ("live version", "studio version", "remastered")):
            unsupported.append("recording edition filtering")

        return Refinement(
            knobs=KnobDeltas(**knobs_dict),
            popularity_ceiling=popularity_ceiling,
            boost_tags=boost_tags[:8],
            suppress_tags=suppress_tags[:8],
            arc=arc,
            unsupported=unsupported,
            clarify=None,
        )


def parse_refinement_rule_based(utterance: str) -> Refinement:
    """Convenience functional interface for the rule-based parser."""
    return RuleBasedRefinementParser.parse(utterance)
