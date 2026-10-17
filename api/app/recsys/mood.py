"""Pure Python deterministic Mood and Sentiment Classifier for Melovia Recsys.

Architecture Constraints:
- Pure Python (no imports from FastAPI, Starlette, SQLAlchemy).
- Deterministic behavior: stable tie-breaking and seeded RNG for vector anchors.
- Independently testable.
"""

import hashlib
from typing import Any

import numpy as np
import numpy.typing as npt

# Mood category identifiers
MOOD_SAD = "sad_melancholic"
MOOD_ROMANTIC = "romantic_love"
MOOD_PARTY = "party_dance"
MOOD_CHILL = "chill_lofi"
MOOD_DEVOTIONAL = "devotional_sufi"
MOOD_RAP = "energetic_rap"
MOOD_GENERAL = "general"

ALL_MOODS = (
    MOOD_SAD,
    MOOD_ROMANTIC,
    MOOD_PARTY,
    MOOD_CHILL,
    MOOD_DEVOTIONAL,
    MOOD_RAP,
    MOOD_GENERAL,
)

# Multi-lingual keyword sets (Hindi / Urdu / Punjabi / English)
MOOD_KEYWORDS: dict[str, set[str]] = {
    MOOD_SAD: {
        "sad",
        "dard",
        "judai",
        "judaai",
        "tanha",
        "tanhai",
        "tanhaiyan",
        "aansoo",
        "aansu",
        "alvida",
        "dhokha",
        "toota",
        "tuta",
        "bikhra",
        "gham",
        "ghamgeen",
        "virah",
        "channa mereya",
        "agar tum saath ho",
        "tujhe bhula diya",
        "bekhayali",
        "pachtaoge",
        "kabira",
        "phir bhi tumko chahunga",
        "tadap",
        "bhula",
        "yaadein",
        "yaad",
        "rona",
        "roya",
        "rone",
        "dukh",
        "melancholy",
        "melancholic",
        "heartbreak",
        "breakup",
        "broken",
        "tears",
        "lonely",
        "alone",
        "sorrow",
        "pain",
        "crying",
        "emotional",
        "acoustic ballad",
        "depressing",
        "loss",
        "khat",
        "bewafa",
        "rooth",
        "tanhayee",
        "soch na sake",
        "hamari adhuri kahani",
        "muskurane",
        "ae dil hai mushkil",
        "juda",
    },
    MOOD_ROMANTIC: {
        "love",
        "pyar",
        "pyaar",
        "ishq",
        "mohabbat",
        "dil",
        "dhadkan",
        "humdum",
        "hamsafar",
        "sanam",
        "jaan",
        "jaana",
        "deewana",
        "mehboob",
        "sajde",
        "guzarish",
        "pehli nazar",
        "tum hi ho",
        "raabta",
        "kesariya",
        "apna bana le",
        "tere bina",
        "zaalima",
        "romance",
        "romantic",
        "valentine",
        "beloved",
        "together",
        "couple",
        "sweetheart",
        "tere hawaale",
        "shayad",
        "hawayein",
        " Mast Magan",
        "mast magan",
        "bol na halke",
        "ishq wala love",
    },
    MOOD_PARTY: {
        "party",
        "dance",
        "club",
        "nach",
        "naach",
        "thumka",
        "dhol",
        "bhangra",
        "dhamaka",
        "dj",
        "remix",
        "sharab",
        "daaru",
        "masti",
        "hungama",
        "jalwa",
        "groove",
        "banger",
        "celebrate",
        "disco",
        "badtameez dil",
        "kala chashma",
        "kar gayi chull",
        "gallan goodiyan",
        "saturday saturday",
        "hookah bar",
    },
    MOOD_CHILL: {
        "chill",
        "lofi",
        "lo-fi",
        "slowed",
        "reverb",
        "calm",
        "relax",
        "peace",
        "sukoon",
        "shaam",
        "raat",
        "halka",
        "coffee",
        "breeze",
        "ambient",
        "midnight",
        "soothing",
        "acoustic",
        "unplugged",
    },
    MOOD_DEVOTIONAL: {
        "sufi",
        "qawwali",
        "khuda",
        "maula",
        "rabba",
        "allah",
        "dua",
        "arziyan",
        "ibadat",
        "saiyan",
        "fakir",
        "peer",
        "dargah",
        "spiritual",
        "devotional",
        "bhajan",
        "aarti",
        "kun faya kun",
        "bhar do jholi",
        "tajdar e haram",
    },
    MOOD_RAP: {
        "rap",
        "hip hop",
        "hip-hop",
        "trap",
        "drill",
        "cypher",
        "flow",
        "bars",
        "beat",
        "desi hip hop",
        "dhh",
        "gully",
        "machayenge",
        "asli hip hop",
    },
}

# Artists strongly identified with specific mood palettes
ARTIST_MOOD_PRIORS: dict[str, str] = {
    "b praak": MOOD_SAD,
    "anuv jain": MOOD_SAD,
    "faheem abdullah": MOOD_SAD,
    "the local train": MOOD_SAD,
    "prateek kuhad": MOOD_CHILL,
    "badshah": MOOD_PARTY,
    "yo yo honey singh": MOOD_PARTY,
    "diljit dosanjh": MOOD_PARTY,
    "nusrat fateh ali khan": MOOD_DEVOTIONAL,
    "rahat fateh ali khan": MOOD_DEVOTIONAL,
    "kailash kher": MOOD_DEVOTIONAL,
    "divine": MOOD_RAP,
    "naezy": MOOD_RAP,
    "seedhe maut": MOOD_RAP,
    "krsna": MOOD_RAP,
    "emiway bantai": MOOD_RAP,
}


def get_mood_anchor_vector(mood: str, dim: int = 128) -> npt.NDArray[np.float32]:
    """Generate a deterministic, unit-normalized anchor vector for a musical mood.

    Ensures that tracks sharing the same emotional sentiment cluster tightly in
    high-dimensional semantic embedding space.
    """
    salt = "melovia_mood_anchor_v1:"
    seed_str = f"{salt}{mood.strip().lower()}"
    digest = hashlib.sha256(seed_str.encode("utf-8")).digest()
    seed_int = int.from_bytes(digest[:8], "big")
    rng = np.random.default_rng(seed_int)
    v = rng.normal(0.0, 1.0, size=dim).astype(np.float32)
    norm = float(np.linalg.norm(v))
    return (v / (norm + 1e-12)).astype(np.float32)


def classify_track_mood(track: dict[str, Any]) -> str:
    """Classify track emotional mood using title keywords, tags, artist priors, and scalars.

    Deterministic and pure Python.
    """
    title = str(track.get("title", "")).lower()
    artist = str(track.get("artist_name", "")).lower()
    tags = [str(t).lower() for t in (track.get("tags") or [])]
    tag_blob = " ".join(tags)
    full_text = f"{title} {artist} {tag_blob}"

    # 1. Check title and text against explicit keyword sets
    scores: dict[str, float] = dict.fromkeys(ALL_MOODS, 0.0)

    for mood, keywords in MOOD_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                # Strong weight for title match
                scores[mood] += 3.0
            elif kw in full_text:
                scores[mood] += 1.5

    # 2. Check artist priors
    for art_key, prior_mood in ARTIST_MOOD_PRIORS.items():
        if art_key in artist:
            scores[prior_mood] += 2.5

    # 3. Check audio scalars if available
    scalars = track.get("scalars") or {}
    valence = scalars.get("valence")
    energy = scalars.get("energy")
    acousticness = scalars.get("acousticness")

    if valence is not None and energy is not None:
        v_val = float(valence)
        e_val = float(energy)
        a_val = float(acousticness) if acousticness is not None else 0.3

        # Low valence + low/mid energy + high acousticness = sad/melancholic
        if v_val < 0.45 and e_val < 0.55:
            scores[MOOD_SAD] += 2.0
            if a_val > 0.5:
                scores[MOOD_SAD] += 1.0
        # High valence + high energy = party
        elif v_val > 0.65 and e_val > 0.70:
            scores[MOOD_PARTY] += 2.5
        # Mid valence + low energy = chill
        elif 0.35 <= v_val <= 0.65 and e_val < 0.45:
            scores[MOOD_CHILL] += 1.5

    # Pick mood with highest score if above threshold
    best_mood = MOOD_GENERAL
    best_score = 0.0
    for mood, score in scores.items():
        if score > best_score and score >= 1.5:
            best_score = score
            best_mood = mood

    return best_mood


def detect_seed_mood_profile(seed_tracks: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze a set of seed tracks to identify dominant mood, confidence, and constraints."""
    if not seed_tracks:
        return {
            "dominant_mood": MOOD_GENERAL,
            "confidence": 0.0,
            "counts": {},
            "is_sad": False,
            "is_romantic": False,
            "is_party": False,
        }

    counts: dict[str, int] = {}
    for s in seed_tracks:
        m = classify_track_mood(s)
        counts[m] = counts.get(m, 0) + 1

    # Sort moods by frequency
    sorted_moods = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_mood, top_count = sorted_moods[0]
    total_seeds = len(seed_tracks)
    confidence = float(top_count) / float(total_seeds)

    # If top mood is general but there's a specific runner up with >= 1 vote
    if top_mood == MOOD_GENERAL and len(sorted_moods) > 1 and sorted_moods[1][1] > 0:
        top_mood = sorted_moods[1][0]
        confidence = float(sorted_moods[1][1]) / float(total_seeds)

    return {
        "dominant_mood": top_mood,
        "confidence": round(confidence, 2),
        "counts": counts,
        "is_sad": top_mood == MOOD_SAD,
        "is_romantic": top_mood == MOOD_ROMANTIC,
        "is_party": top_mood == MOOD_PARTY,
    }
