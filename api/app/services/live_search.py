"""Live Public Music Search Service using iTunes Search and JioSaavn APIs.

Provides free, public, real-time access to commercial, independent, and regional music releases
(Western, Bollywood, Punjabi Hip-Hop, Indie, International) with zero authentication keys required.
"""

import asyncio
import base64
import html
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
from Crypto.Cipher import DES

from app.recsys.mood import (
    MOOD_PARTY,
    MOOD_SAD,
    classify_track_mood,
    detect_seed_mood_profile,
)

logger = logging.getLogger(__name__)

# JioSaavn media encryption DES key (fixed standard 8-byte key)
JIOSAAVN_DES_KEY = b"38346591"


def decrypt_jiosaavn_media_url(encrypted_url: str | None) -> str | None:
    """Decrypt JioSaavn DES-ECB encrypted media URL and upgrade to high bitrate."""
    if not encrypted_url:
        return None
    try:
        cipher = DES.new(JIOSAAVN_DES_KEY, DES.MODE_ECB)
        decrypted = cipher.decrypt(base64.b64decode(encrypted_url))
        pad_len = decrypted[-1]
        raw_url = decrypted[:-pad_len].decode("utf-8")
        # Upgrade standard 96kbps streams to 160kbps if applicable
        if "_96.mp4" in raw_url:
            return raw_url.replace("_96.mp4", "_160.mp4")
        return raw_url
    except Exception as exc:
        logger.debug("Failed to decrypt JioSaavn media URL: %s", exc)
        return None

# Genre-to-heuristic scalars mapping for dynamic tracks
GENRE_SCALARS: dict[str, dict[str, float]] = {
    "hip-hop/rap": {
        "bpm": 130.0,
        "energy": 0.75,
        "valence": 0.55,
        "danceability": 0.80,
        "acousticness": 0.15,
    },
    "rap": {
        "bpm": 130.0,
        "energy": 0.75,
        "valence": 0.55,
        "danceability": 0.80,
        "acousticness": 0.15,
    },
    "hip-hop": {
        "bpm": 130.0,
        "energy": 0.75,
        "valence": 0.55,
        "danceability": 0.80,
        "acousticness": 0.15,
    },
    "pop": {
        "bpm": 120.0,
        "energy": 0.70,
        "valence": 0.65,
        "danceability": 0.75,
        "acousticness": 0.20,
    },
    "r&b/soul": {
        "bpm": 105.0,
        "energy": 0.55,
        "valence": 0.55,
        "danceability": 0.65,
        "acousticness": 0.35,
    },
    "rock": {
        "bpm": 125.0,
        "energy": 0.80,
        "valence": 0.50,
        "danceability": 0.55,
        "acousticness": 0.15,
    },
    "alternative": {
        "bpm": 120.0,
        "energy": 0.70,
        "valence": 0.45,
        "danceability": 0.60,
        "acousticness": 0.25,
    },
    "electronic": {
        "bpm": 128.0,
        "energy": 0.85,
        "valence": 0.60,
        "danceability": 0.80,
        "acousticness": 0.10,
    },
    "dance": {
        "bpm": 128.0,
        "energy": 0.85,
        "valence": 0.65,
        "danceability": 0.85,
        "acousticness": 0.08,
    },
    "indie": {
        "bpm": 115.0,
        "energy": 0.60,
        "valence": 0.45,
        "danceability": 0.55,
        "acousticness": 0.40,
    },
    "ambient": {
        "bpm": 70.0,
        "energy": 0.20,
        "valence": 0.35,
        "danceability": 0.25,
        "acousticness": 0.80,
    },
    "classical": {
        "bpm": 80.0,
        "energy": 0.30,
        "valence": 0.30,
        "danceability": 0.20,
        "acousticness": 0.90,
    },
    "jazz": {
        "bpm": 110.0,
        "energy": 0.50,
        "valence": 0.55,
        "danceability": 0.60,
        "acousticness": 0.65,
    },
    "country": {
        "bpm": 115.0,
        "energy": 0.65,
        "valence": 0.60,
        "danceability": 0.60,
        "acousticness": 0.45,
    },
    "latin": {
        "bpm": 115.0,
        "energy": 0.80,
        "valence": 0.75,
        "danceability": 0.85,
        "acousticness": 0.25,
    },
    "bollywood": {
        "bpm": 95.0,
        "energy": 0.55,
        "valence": 0.60,
        "danceability": 0.60,
        "acousticness": 0.45,
    },
    "indian-pop": {
        "bpm": 100.0,
        "energy": 0.60,
        "valence": 0.65,
        "danceability": 0.65,
        "acousticness": 0.40,
    },
    "indian": {
        "bpm": 95.0,
        "energy": 0.55,
        "valence": 0.60,
        "danceability": 0.60,
        "acousticness": 0.50,
    },
    "k-pop": {
        "bpm": 125.0,
        "energy": 0.85,
        "valence": 0.70,
        "danceability": 0.85,
        "acousticness": 0.12,
    },
    "punjabi": {
        "bpm": 128.0,
        "energy": 0.82,
        "valence": 0.70,
        "danceability": 0.85,
        "acousticness": 0.18,
    },
    "punjabi-pop": {
        "bpm": 126.0,
        "energy": 0.80,
        "valence": 0.72,
        "danceability": 0.85,
        "acousticness": 0.20,
    },
    "punjabi-hip-hop": {
        "bpm": 132.0,
        "energy": 0.84,
        "valence": 0.65,
        "danceability": 0.84,
        "acousticness": 0.14,
    },
    "bhangra": {
        "bpm": 130.0,
        "energy": 0.88,
        "valence": 0.80,
        "danceability": 0.88,
        "acousticness": 0.15,
    },
}

# Regional and cultural artist rosters for bulletproof cross-market classification
PUNJABI_ARTISTS: frozenset[str] = frozenset(
    {
        "karan aujla",
        "sidhu moose wala",
        "diljit dosanjh",
        "ap dhillon",
        "shubh",
        "sukha",
        "baggh-e smg",
        "big kay smg",
        "farmaan smg",
        "jxggi",
        "dishant",
        "sickboi",
        "jerry",
        "tegi pannu",
        "chani nattan",
        "inderpal moga",
        "ikky",
        "mxrci",
        "gurinder gill",
        "shinda kahlon",
        "arjan dhillon",
        "amrit maan",
        "prem dhillon",
        "jordan sandhu",
        "amrinder gill",
        "garry sandhu",
        "b praak",
        "jaani",
        "wazir patar",
        "raf-saperra",
        "jasmine sandlas",
        "nimrat khaira",
        "sunanda sharma",
        "kulwinder billa",
        "tarsem jassar",
        "mankirt aulakh",
        "jass manak",
        "gurnam bhullar",
        "prabh gill",
        "gippy grewal",
        "babbu maan",
        "gurdas maan",
        "bohemia",
        "imran khan",
        "prophec",
        "mickey singh",
        "pav dharia",
        "intense",
        "deep jandu",
        "snappy",
        "byg byrd",
        "sunny malton",
        "the kidd",
        "proof",
        "tru-skool",
        "hustinder",
        "cheema y",
        "gur sidhu",
        "nirvair pannu",
        "korala maan",
        "r nait",
        "gulab sidhu",
        "varinder brar",
        "chetan",
        "shree brar",
        "parmish verma",
        "dilpreet dhillon",
        "kulbir jhinjer",
        "ammy virk",
        "hardy sandhu",
        "harrdy sandhu",
        "guru randhawa",
        "jassi gill",
        "yo yo honey singh",
        "badshah",
        "raftaar",
        "kr$na",
        "seedhe maut",
        "divine",
        "emiway bantai",
    }
)

BOLLYWOOD_ARTISTS: frozenset[str] = frozenset(
    {
        "arijit singh",
        "pritam",
        "shreya ghoshal",
        "atif aslam",
        "mohit chauhan",
        "kk",
        "sonu nigam",
        "javed ali",
        "faheem abdullah",
        "huzaif nazar",
        "navjot ahuja",
        "anuv jain",
        "prateek kuhad",
        "jasleen royal",
        "the local train",
        "when chai met toast",
        "armaan malik",
        "darshan raval",
        "jubin nautiyal",
        "sachin-jigar",
        "vishal-shekhar",
        "a.r. rahman",
        "ar rahman",
        "amit trivedi",
        "shankar mahadevan",
        "kailash kher",
        "sunidhi chauhan",
        "alka yagnik",
        "udit narayan",
        "kumar sanu",
        "lucky ali",
        "mithoon",
    }
)

KPOP_ARTISTS: frozenset[str] = frozenset(
    {
        "bts",
        "blackpink",
        "newjeans",
        "stray kids",
        "twice",
        "le sserafim",
        "ive",
        "aespa",
        "illit",
        "seventeen",
        "txt",
        "enhypen",
        "jungkook",
        "jimin",
        "agust d",
        "suga",
        "jennie",
        "rose",
        "lisa",
    }
)

LATIN_ARTISTS: frozenset[str] = frozenset(
    {
        "bad bunny",
        "peso pluma",
        "karol g",
        "j balvin",
        "rauw alejandro",
        "feid",
        "tainy",
        "maluma",
        "ozuna",
        "anuel aa",
        "daddy yankee",
        "junior h",
        "natanael cano",
        "fuerza regida",
    }
)

# Collaborative and stylistic peer graph modeled after Spotify/YouTube Music co-listening graphs
ARTIST_COLLABORATOR_GRAPH: dict[str, list[str]] = {
    # Punjabi & Desi Hip-Hop / Pop Ecosystem
    "karan aujla": [
        "Diljit Dosanjh",
        "Sidhu Moose Wala",
        "AP Dhillon",
        "Shubh",
        "Sukha",
        "Ikky",
        "Mxrci",
        "Gurinder Gill",
        "Arjan Dhillon",
        "Amrit Maan",
        "Prem Dhillon",
        "Jerry",
        "Tegi Pannu",
        "Wazir Patar",
        "Baggh-e SMG",
    ],
    "sidhu moose wala": [
        "Karan Aujla",
        "Amrit Maan",
        "Prem Dhillon",
        "Sunny Malton",
        "Byg Byrd",
        "The Kidd",
        "Diljit Dosanjh",
        "Wazir Patar",
        "Jordan Sandhu",
        "Raja Kumari",
        "Stefflon Don",
    ],
    "diljit dosanjh": [
        "Karan Aujla",
        "AP Dhillon",
        "Amrinder Gill",
        "Garry Sandhu",
        "Badshah",
        "Yo Yo Honey Singh",
        "Sidhu Moose Wala",
        "Nimrat Khaira",
        "Intense",
        "Tru-Skool",
        "Ikky",
    ],
    "ap dhillon": [
        "Gurinder Gill",
        "Shinda Kahlon",
        "Gminxr",
        "Karan Aujla",
        "Diljit Dosanjh",
        "Shubh",
        "Sukha",
        "Ikky",
        "Jerry",
    ],
    "shubh": [
        "AP Dhillon",
        "Karan Aujla",
        "Sukha",
        "Gurinder Gill",
        "Ikky",
        "Chani Nattan",
        "Tegi Pannu",
        "Diljit Dosanjh",
    ],
    "sukha": [
        "Chani Nattan",
        "Inderpal Moga",
        "Shubh",
        "Karan Aujla",
        "AP Dhillon",
        "Tegi Pannu",
        "Baggh-e SMG",
        "Jxggi",
        "SickBoi",
    ],
    "baggh-e smg": [
        "Big Kay Smg",
        "Farmaan SMG",
        "Mxrci",
        "Karan Aujla",
        "Sukha",
        "Jerry",
        "Tegi Pannu",
        "Jxggi",
        "Wazir Patar",
    ],
    "big kay smg": [
        "Baggh-e SMG",
        "Farmaan SMG",
        "Mxrci",
        "Karan Aujla",
        "Sukha",
        "Jerry",
    ],
    "farmaan smg": [
        "Baggh-e SMG",
        "Big Kay Smg",
        "Mxrci",
        "Karan Aujla",
        "Sukha",
    ],
    "jxggi": [
        "Dishant",
        "SickBoi",
        "Sukha",
        "Baggh-e SMG",
        "Chani Nattan",
        "Tegi Pannu",
        "Karan Aujla",
    ],
    "dishant": [
        "Jxggi",
        "SickBoi",
        "Sukha",
        "Baggh-e SMG",
    ],
    "sickboi": [
        "Jxggi",
        "Dishant",
        "Sukha",
        "Baggh-e SMG",
        "Chani Nattan",
    ],
    "arjan dhillon": [
        "Karan Aujla",
        "Nimrat Khaira",
        "Mxrci",
        "Amrit Maan",
        "Diljit Dosanjh",
        "Hustinder",
    ],
    "amrit maan": [
        "Sidhu Moose Wala",
        "Karan Aujla",
        "Diljit Dosanjh",
        "Gur Sidhu",
        "Jordan Sandhu",
    ],
    "prem dhillon": [
        "Sidhu Moose Wala",
        "The Kidd",
        "Karan Aujla",
        "Snappy",
        "Tegi Pannu",
    ],
    "tegi pannu": [
        "Sukha",
        "Chani Nattan",
        "Karan Aujla",
        "Jerry",
        "Baggh-e SMG",
        "Manners",
    ],
    "chani nattan": [
        "Inderpal Moga",
        "Sukha",
        "Shubh",
        "Karan Aujla",
        "Tegi Pannu",
    ],
    "wazir patar": [
        "Sidhu Moose Wala",
        "Roop Bhullar",
        "Karan Aujla",
        "Signature By Wazir",
    ],
    "jerry": [
        "Karan Aujla",
        "Devenderpal Singh",
        "Mxrci",
        "Sukha",
        "Baggh-e SMG",
    ],
    "gurinder gill": [
        "AP Dhillon",
        "Shinda Kahlon",
        "Gminxr",
        "Karan Aujla",
        "Shubh",
    ],
    "ikky": [
        "Karan Aujla",
        "Diljit Dosanjh",
        "Shubh",
        "Badshah",
        "Sikander Kahlon",
    ],
    "mxrci": [
        "Karan Aujla",
        "Arjan Dhillon",
        "Baggh-e SMG",
        "Jerry",
        "Diljit Dosanjh",
    ],
    # Bollywood / Indian Romantic, Indie & Filmi
    "faheem abdullah": [
        "Huzaif Nazar",
        "Rather Hashim",
        "Hyder Dar",
        "Anuv Jain",
        "Babil Khan",
        "Arijit Singh",
        "Mohit Chauhan",
    ],
    "huzaif nazar": [
        "Faheem Abdullah",
        "Rather Hashim",
        "Hyder Dar",
        "Anuv Jain",
    ],
    "navjot ahuja": [
        "Faheem Abdullah",
        "Anuv Jain",
        "Jasleen Royal",
        "Prateek Kuhad",
    ],
    "arijit singh": [
        "Pritam",
        "Shreya Ghoshal",
        "Jasleen Royal",
        "Mohit Chauhan",
        "Atif Aslam",
        "Mithoon",
        "A.R. Rahman",
        "Anirudh Ravichander",
    ],
    "pritam": [
        "Arijit Singh",
        "Mohit Chauhan",
        "KK",
        "Atif Aslam",
        "Shreya Ghoshal",
        "Sunidhi Chauhan",
    ],
    "atif aslam": [
        "Pritam",
        "Mithoon",
        "Sachin-Jigar",
        "Shreya Ghoshal",
        "Arijit Singh",
        "Mohit Chauhan",
    ],
    "mohit chauhan": [
        "Pritam",
        "A.R. Rahman",
        "Lucky Ali",
        "KK",
        "Arijit Singh",
        "Atif Aslam",
    ],
    "javed ali": [
        "Sonu Nigam",
        "A.R. Rahman",
        "Pritam",
        "Kailash Kher",
        "Shreya Ghoshal",
    ],
    "sonu nigam": [
        "Javed Ali",
        "Udit Narayan",
        "Alka Yagnik",
        "Shreya Ghoshal",
        "A.R. Rahman",
        "Shaan",
    ],
    "kk": [
        "Pritam",
        "Mohit Chauhan",
        "Shaan",
        "Arijit Singh",
        "Emraan Hashmi hits",
    ],
    "shreya ghoshal": [
        "Arijit Singh",
        "Sonu Nigam",
        "Atif Aslam",
        "Pritam",
        "A.R. Rahman",
    ],
    "jasleen royal": [
        "Arijit Singh",
        "Prateek Kuhad",
        "Anuv Jain",
        "Babil Khan",
    ],
    "anuv jain": [
        "Jasleen Royal",
        "Prateek Kuhad",
        "Faheem Abdullah",
        "Babil Khan",
        "The Local Train",
    ],
    "prateek kuhad": [
        "Anuv Jain",
        "Jasleen Royal",
        "When Chai Met Toast",
        "The Local Train",
    ],
    # Hip-Hop / Melodic Trap / Rap
    "travis scott": [
        "Don Toliver",
        "Metro Boomin",
        "Future",
        "21 Savage",
        "Quavo",
        "Playboi Carti",
        "Sheck Wes",
    ],
    "don toliver": [
        "Travis Scott",
        "Metro Boomin",
        "Future",
        "Gunna",
        "Kali Uchis",
        "Lil Yachty",
    ],
    "gunna": [
        "Future",
        "Young Thug",
        "Lil Baby",
        "Metro Boomin",
        "Don Toliver",
        "21 Savage",
    ],
    "future": [
        "Metro Boomin",
        "Drake",
        "Gunna",
        "Travis Scott",
        "21 Savage",
        "Young Thug",
    ],
    "metro boomin": [
        "Future",
        "21 Savage",
        "Travis Scott",
        "Don Toliver",
        "Young Thug",
        "Drake",
    ],
    "21 savage": [
        "Metro Boomin",
        "Drake",
        "J. Cole",
        "Future",
        "Travis Scott",
        "Young Nudy",
    ],
    "playboi carti": [
        "Ken Carson",
        "Destroy Lonely",
        "Travis Scott",
        "Lil Uzi Vert",
        "Yeat",
    ],
    "lil baby": [
        "Gunna",
        "Future",
        "Lil Durk",
        "21 Savage",
        "Drake",
        "Metro Boomin",
    ],
    "drake": [
        "21 Savage",
        "Future",
        "Travis Scott",
        "PARTYNEXTDOOR",
        "Lil Wayne",
    ],
    "kendrick lamar": [
        "Baby Keem",
        "SZA",
        "Jay Rock",
        "ScHoolboy Q",
        "J. Cole",
    ],
    "j. cole": [
        "Kendrick Lamar",
        "Bas",
        "JID",
        "Drake",
        "21 Savage",
    ],
    # Western Pop
    "the weeknd": [
        "Daft Punk",
        "Lana Del Rey",
        "Post Malone",
        "Playboi Carti",
        "Future",
    ],
    "billie eilish": [
        "Finneas",
        "Olivia Rodrigo",
        "Phoebe Bridgers",
        "Lorde",
        "Clairo",
    ],
    "olivia rodrigo": [
        "Billie Eilish",
        "Taylor Swift",
        "Conan Gray",
        "Sabrina Carpenter",
        "Chappell Roan",
    ],
    "taylor swift": [
        "Phoebe Bridgers",
        "Lana Del Rey",
        "Sabrina Carpenter",
        "Gracie Abrams",
    ],
    "dua lipa": [
        "Calvin Harris",
        "Elton John",
        "Miley Cyrus",
        "The Weeknd",
        "Ava Max",
    ],
    "post malone": [
        "Swae Lee",
        "The Weeknd",
        "Morgan Wallen",
        "Noah Kahan",
        "21 Savage",
    ],
    # R&B / Soul
    "sza": [
        "Kendrick Lamar",
        "Frank Ocean",
        "Summer Walker",
        "Brent Faiyaz",
        "Jhené Aiko",
    ],
    "frank ocean": [
        "Tyler, The Creator",
        "Daniel Caesar",
        "Brent Faiyaz",
        "SZA",
        "Steve Lacy",
    ],
    "daniel caesar": [
        "H.E.R.",
        "Kali Uchis",
        "Frank Ocean",
        "Giveon",
        "Omar Apollo",
    ],
    # Rock / Alternative
    "arctic monkeys": [
        "The Strokes",
        "The Last Shadow Puppets",
        "Miles Kane",
        "Tame Impala",
        "Fontaines D.C.",
    ],
    "the strokes": [
        "Arctic Monkeys",
        "The Voidz",
        "Franz Ferdinand",
        "Interpol",
    ],
    "tame impala": [
        "MGMT",
        "Unknown Mortal Orchestra",
        "Pond",
        "Mac DeMarco",
        "Gorillaz",
    ],
    # K-Pop
    "bts": ["Jimin", "Jung Kook", "V", "Agust D", "TXT", "SEVENTEEN"],
    "newjeans": ["ILLIT", "LE SSERAFIM", "IVE", "aespa", "TWICE"],
    "blackpink": ["Jennie", "ROSÉ", "LISA", "aespa", "TWICE"],
    # Latin / Reggaeton
    "bad bunny": [
        "Rauw Alejandro",
        "J Balvin",
        "Tainy",
        "Chencho Corleone",
        "Feid",
        "Mora",
    ],
    "peso pluma": ["Junior H", "Natanael Cano", "Eslabon Armado", "Fuerza Regida"],
}


def classify_genre_and_culture(
    primary_genre: str,
    tags: list[str] | None = None,
    artist_name: str | None = None,
    language: str | None = None,
    title: str | None = None,
) -> str:
    """Classify genre, artist, and cultural market into a coherent domain.

    Supports Punjabi Hip-Hop/Pop, Bollywood/Desi, K-Pop, Latin, Hip-Hop, R&B, Rock,
    Western Pop, and Electronic.
    """
    # 1. First check explicit language tag
    if language:
        lang_clean = language.strip().lower()
        if lang_clean == "punjabi":
            return "punjabi"
        if lang_clean in (
            "hindi",
            "tamil",
            "telugu",
            "malayalam",
            "kannada",
            "bhojpuri",
            "haryanvi",
            "marathi",
            "bengali",
            "urdu",
        ):
            return "bollywood_desi"
        if lang_clean in ("korean", "ko"):
            return "kpop"
        if lang_clean in ("spanish", "es"):
            return "latin"

    # 2. Check artist against known regional knowledge graphs
    if artist_name:
        art_clean = artist_name.strip().lower()
        art_tokens = set(art_clean.replace(",", " ").replace("&", " ").replace("-", " ").split())

        def _matches_artist(roster: frozenset[str]) -> bool:
            for a in roster:
                if len(a) <= 3:
                    if a in art_tokens or a == art_clean:
                        return True
                else:
                    if a in art_clean:
                        return True
            return False

        if _matches_artist(PUNJABI_ARTISTS):
            return "punjabi"
        if _matches_artist(BOLLYWOOD_ARTISTS):
            return "bollywood_desi"
        if _matches_artist(KPOP_ARTISTS):
            return "kpop"
        if _matches_artist(LATIN_ARTISTS):
            return "latin"

    text = (primary_genre or "").lower().replace("-", " ")
    if tags:
        text += " " + " ".join(str(t).lower().replace("-", " ") for t in tags)
    if title:
        text += " " + str(title).lower().replace("-", " ")

    # 3. Punjabi / Bhangra / Desi Hip-Hop
    if any(
        term in text
        for term in (
            "punjabi",
            "bhangra",
            "desi hip hop",
            "dhh",
            "malwa",
            "punjabi pop",
            "punjabi hip hop",
            "sidhu",
            "aujla",
            "dhillon",
            "shubh",
            "sukha",
        )
    ):
        return "punjabi"

    # 4. Bollywood / Desi / Indian
    if any(
        term in text
        for term in (
            "bollywood",
            "indian pop",
            "indian",
            "filmi",
            "sufi",
            "ghazal",
            "hindi",
            "tamil",
            "telugu",
            "malayalam",
            "bengali",
            "desi",
            "qawwali",
        )
    ):
        return "bollywood_desi"

    # 5. K-Pop
    if "k pop" in text or "kpop" in text or "korean" in text:
        return "kpop"

    # 6. Latin
    if any(
        term in text
        for term in ("latin", "reggaeton", "urbano", "salsa", "bachata", "cumbia", "corridos")
    ):
        return "latin"

    # 7. Hip-Hop / Rap
    if any(term in text for term in ("hip hop", "rap", "trap", "drill", "cloud rap")):
        return "hiphop"

    # 8. R&B / Soul
    if any(term in text for term in ("r&b", "soul", "neo soul", "funk")):
        return "rnb"

    # 9. Rock / Alternative
    if any(
        term in text for term in ("rock", "metal", "punk", "alternative", "grunge", "indie rock")
    ):
        return "rock"

    # 10. Western Pop
    if any(
        term in text for term in ("pop", "dance", "synth pop", "disco", "electro pop", "teen pop")
    ):
        return "western_pop"

    # 11. Electronic / Dance
    if any(
        term in text
        for term in ("electronic", "edm", "house", "techno", "trance", "dnb", "dubstep")
    ):
        return "electronic"

    return "general"


class LiveSearchService:
    """Asynchronous client for querying public music releases."""

    SEARCH_URL = "https://itunes.apple.com/search"
    LOOKUP_URL = "https://itunes.apple.com/lookup"

    def __init__(self, cache_ttl_seconds: int = 600) -> None:
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._query_cache: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}
        self._track_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}

    def _clean_cache(self) -> None:
        now = datetime.now()
        if len(self._query_cache) > 200:
            self._query_cache = {
                k: v for k, v in self._query_cache.items() if now - v[0] < self.cache_ttl
            }
        if len(self._track_cache) > 500:
            self._track_cache = {
                k: v for k, v in self._track_cache.items() if now - v[0] < self.cache_ttl
            }

    @staticmethod
    def _detect_country(query: str) -> str:
        q_lower = query.lower()
        if any(
            term in q_lower
            for term in (
                "khat",
                "sajde",
                "guzarish",
                "arijit",
                "pritam",
                "rahman",
                "javed ali",
                "faheem",
                "atif",
                "mohit chauhan",
                "navjot",
                "bollywood",
                "hindi",
                "punjabi",
                "sonu nigam",
                "shreya ghoshal",
                "anuv jain",
                "prateek kuhad",
                "jasleen royal",
                "kk",
                "armaan malik",
                "darshan raval",
                "jubin nautiyal",
                "diljit",
                "sidhu",
                "ap dhillon",
                "badshah",
                "honey singh",
                "desi",
                "sufi",
                "karan aujla",
                "shubh",
                "sukha",
                "aujla",
                "baggh",
                "smg",
                "jxggi",
                "wazir",
                "tegi pannu",
                "b praak",
                "jaani",
                "amrit maan",
                "prem dhillon",
                "arjan dhillon",
            )
        ):
            return "IN"
        if any(term in q_lower for term in ("bts", "blackpink", "newjeans", "stray kids", "twice")):
            return "KR"
        if any(term in q_lower for term in ("bad bunny", "peso pluma", "karol g", "reggaeton")):
            return "MX"
        return "US"

    @staticmethod
    def _normalize_itunes_track(item: dict[str, Any]) -> dict[str, Any] | None:
        track_id = item.get("trackId")
        title = item.get("trackName")
        artist = item.get("artistName")
        if not track_id or not title or not artist:
            return None

        artist_str = str(artist)
        title_str = str(title)
        artist_lower = artist_str.lower()
        title_lower = title_str.lower()
        if any(
            bad in artist_lower or bad in title_lower
            for bad in ("karaoke", "tribute", "backing track", "royalty free")
        ):
            return None

        # Determine release year
        year: int | None = None
        release_date = item.get("releaseDate")
        if release_date and isinstance(release_date, str) and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
            except ValueError:
                year = None

        primary_genre = (item.get("primaryGenreName") or "Music").strip()
        genre_key = primary_genre.lower().replace(" ", "-")

        # Tags extraction (using recognized vocabulary terms)
        tags = [primary_genre.lower()]
        if "/" in primary_genre:
            for part in primary_genre.split("/"):
                tags.append(part.strip().lower())

        culture = classify_genre_and_culture(
            primary_genre=primary_genre,
            tags=tags,
            artist_name=artist_str,
            title=title_str,
        )
        if culture == "punjabi":
            tags.extend(["punjabi", "desi", "bhangra", "punjabi-hip-hop", "punjabi-pop", "dance"])
            genre_key = "punjabi"
        elif culture == "bollywood_desi":
            tags.extend(["bollywood", "indian-pop", "acoustic", "melodic", "soul"])
            genre_key = "bollywood"
        elif culture == "hiphop":
            tags.extend(["hip-hop", "trap", "cloud-rap", "bass"])
            genre_key = "hip-hop"
        elif culture == "kpop":
            tags.extend(["k-pop", "dance", "electronic", "groove"])
            genre_key = "k-pop"
        elif culture == "latin":
            tags.extend(["latin", "dance", "groove"])
            genre_key = "latin"
        elif culture == "western_pop":
            tags.extend(["pop", "dance", "electronic", "groove"])
            genre_key = "pop"
        elif culture == "rock":
            tags.extend(["rock", "guitar", "raw", "alternative"])
            genre_key = "rock"
        elif culture == "rnb":
            tags.extend(["soul", "neo-soul", "groove", "smooth"])
            genre_key = "r&b/soul"

        # Determine audio scalars proxy
        scalars_preset = GENRE_SCALARS.get(genre_key, GENRE_SCALARS.get("pop", {}))
        base_bpm = float(scalars_preset.get("bpm", 120.0))
        base_energy = float(scalars_preset.get("energy", 0.60))
        base_valence = float(scalars_preset.get("valence", 0.50))
        base_dance = float(scalars_preset.get("danceability", 0.65))
        base_acoustic = float(scalars_preset.get("acousticness", 0.25))

        if any(
            w in title_lower
            for w in ("acoustic", "unplugged", "piano", "reprise", "ballad", "slowed", "lullaby")
        ):
            base_acoustic = min(0.95, base_acoustic + 0.40)
            base_energy = max(0.20, base_energy - 0.25)
            base_bpm = max(68.0, base_bpm - 25.0)
            base_dance = max(0.25, base_dance - 0.20)
        elif any(
            w in title_lower for w in ("remix", "club", "party", "dance", "dj", "drill", "bass")
        ):
            base_acoustic = max(0.02, base_acoustic - 0.20)
            base_energy = min(0.98, base_energy + 0.25)
            base_bpm = min(150.0, base_bpm + 20.0)
            base_dance = min(0.95, base_dance + 0.20)
        elif any(
            w in title_lower for w in ("lo-fi", "chill", "relax", "midnight", "late night", "sad")
        ):
            base_acoustic = min(0.85, base_acoustic + 0.30)
            base_energy = max(0.25, base_energy - 0.25)
            base_valence = max(0.25, base_valence - 0.20)
            base_bpm = max(72.0, base_bpm - 18.0)

        # Extract track duration in milliseconds
        track_time_ms = item.get("trackTimeMillis")
        duration_ms = int(track_time_ms) if track_time_ms is not None else 210000
        duration_sec = round(duration_ms / 1000.0, 1)

        scalars = {
            "bpm": base_bpm,
            "tempo_bpm": base_bpm,
            "energy": base_energy,
            "valence": base_valence,
            "danceability": base_dance,
            "acousticness": base_acoustic,
            "instrumentalness": 0.05,
            "loudness_db": -8.0,
            "duration_ms": duration_ms,
            "duration_sec": duration_sec,
        }

        canonical_id = f"ext:itunes:{track_id}"
        artist_seed_str = f"itunes.artist.{item.get('artistId', artist)}"
        artist_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, artist_seed_str))

        return {
            "id": canonical_id,
            "track_idx": -1,
            "mbid": None,
            "title": str(title),
            "artist_id": artist_id,
            "artist_name": str(artist),
            "album_name": item.get("collectionName"),
            "year": year,
            "isrcs": [],
            "popularity_pct": 75.0,
            "has_a": False,
            "has_t": True,
            "region_id": None,
            "scalars": scalars,
            "tags": sorted(set(tags)),
            "culture": culture,
            "artwork_url": item.get("artworkUrl100") or item.get("artworkUrl60"),
            "preview_url": item.get("previewUrl"),
            "duration_ms": duration_ms,
            "duration_sec": duration_sec,
            "source": "itunes_live",
        }

    @staticmethod
    def _normalize_jiosaavn_track(item: dict[str, Any]) -> dict[str, Any] | None:
        """Parse, decrypt, and normalize JioSaavn raw item into Melovia schema."""
        track_id = item.get("id")
        title_raw = item.get("title")
        if not track_id or not title_raw:
            return None

        title = html.unescape(str(title_raw)).strip()
        more = item.get("more_info") or {}
        amap = more.get("artistMap") or {}
        pa_list = [
            html.unescape(a.get("name"))
            for a in amap.get("primary_artists", [])
            if a.get("name")
        ]
        if not pa_list:
            sub = html.unescape(item.get("subtitle") or "").strip()
            if " - " in sub:
                pa_list = [p.strip() for p in sub.split(" - ")[0].split(",") if p.strip()]
            elif sub:
                pa_list = [sub]
        if not pa_list:
            singers = more.get("singers")
            if singers:
                pa_list = [s.strip() for s in str(singers).split(",") if s.strip()]

        artist_str = ", ".join(pa_list) if pa_list else "Unknown Artist"
        album_str = html.unescape(more.get("album") or "").strip() or None

        title_lower = title.lower()
        artist_lower = artist_str.lower()
        if any(
            bad in artist_lower or bad in title_lower
            for bad in ("karaoke", "tribute", "backing track", "royalty free")
        ):
            return None

        # Year
        year: int | None = None
        year_raw = item.get("year")
        if year_raw and str(year_raw).isdigit():
            year = int(year_raw)

        # Image (upgrade from 150x150 to 500x500 for crisp visual presentation)
        img = item.get("image") or ""
        if img:
            img = img.replace("150x150.jpg", "500x500.jpg").replace("50x50.jpg", "500x500.jpg")

        # Media preview URL decryption
        encrypted_media = more.get("encrypted_media_url")
        preview_url = decrypt_jiosaavn_media_url(encrypted_media)

        # Duration
        dur_raw = more.get("duration")
        dur_sec = float(dur_raw) if dur_raw is not None else 210.0
        dur_ms = int(dur_sec * 1000)

        language = (item.get("language") or "").lower().strip()
        primary_genre = "punjabi" if language == "punjabi" else (language or "Indian")

        tags = [language] if language else []
        if language == "punjabi":
            tags.extend(["punjabi", "desi", "bhangra", "punjabi-hip-hop", "punjabi-pop"])
        elif language in ("hindi", "bollywood"):
            tags.extend(["bollywood", "hindi", "indian-pop"])

        culture = classify_genre_and_culture(
            primary_genre=primary_genre,
            tags=tags,
            artist_name=artist_str,
            language=language,
            title=title,
        )

        genre_key = (
            "punjabi"
            if culture == "punjabi"
            else ("bollywood" if culture == "bollywood_desi" else "pop")
        )
        scalars_preset = GENRE_SCALARS.get(genre_key, GENRE_SCALARS.get("pop", {}))
        base_bpm = float(scalars_preset.get("bpm", 128.0))
        base_energy = float(scalars_preset.get("energy", 0.80))
        base_valence = float(scalars_preset.get("valence", 0.70))
        base_dance = float(scalars_preset.get("danceability", 0.85))
        base_acoustic = float(scalars_preset.get("acousticness", 0.18))

        if any(w in title_lower for w in ("acoustic", "unplugged", "piano", "sad", "slowed")):
            base_acoustic = min(0.95, base_acoustic + 0.35)
            base_energy = max(0.20, base_energy - 0.25)
            base_bpm = max(70.0, base_bpm - 20.0)
        elif any(w in title_lower for w in ("remix", "party", "club", "dance", "bass", "dhamaka")):
            base_energy = min(0.98, base_energy + 0.20)
            base_dance = min(0.98, base_dance + 0.15)
            base_bpm = min(150.0, base_bpm + 15.0)

        scalars = {
            "bpm": base_bpm,
            "tempo_bpm": base_bpm,
            "energy": base_energy,
            "valence": base_valence,
            "danceability": base_dance,
            "acousticness": base_acoustic,
            "instrumentalness": 0.05,
            "loudness_db": -7.0,
            "duration_ms": dur_ms,
            "duration_sec": dur_sec,
        }

        canonical_id = f"ext:saavn:{track_id}"
        artist_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"saavn.artist.{artist_str}"))

        return {
            "id": canonical_id,
            "track_idx": -1,
            "mbid": None,
            "title": title,
            "artist_id": artist_id,
            "artist_name": artist_str,
            "album_name": album_str,
            "year": year,
            "isrcs": [],
            "popularity_pct": 80.0,
            "has_a": False,
            "has_t": True,
            "region_id": None,
            "scalars": scalars,
            "tags": sorted(set(tags)),
            "culture": culture,
            "artwork_url": img or None,
            "preview_url": preview_url,
            "duration_ms": dur_ms,
            "duration_sec": dur_sec,
            "source": "jiosaavn_live",
        }

    async def search_itunes(
        self,
        query: str,
        limit: int = 15,
        country: str = "US",
    ) -> list[dict[str, Any]]:
        """Search iTunes Store API for songs."""
        q_clean = query.strip()
        if len(q_clean) < 2:
            return []

        cache_key = f"itunes:{q_clean.lower()}:{limit}:{country}"
        now = datetime.now()
        if cache_key in self._query_cache:
            ts, cached_res = self._query_cache[cache_key]
            if now - ts < self.cache_ttl:
                return cached_res

        self._clean_cache()
        params: dict[str, str | int] = {
            "term": q_clean,
            "entity": "song",
            "limit": limit,
            "media": "music",
            "country": country,
        }

        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                resp = await client.get(self.SEARCH_URL, params=params)
                if resp.status_code == 200:
                    raw_results = resp.json().get("results", [])
                else:
                    raw_results = []

                normalized: list[dict[str, Any]] = []
                for item in raw_results:
                    parsed = self._normalize_itunes_track(item)
                    if parsed:
                        normalized.append(parsed)
                        self._track_cache[parsed["id"]] = (now, parsed)

                self._query_cache[cache_key] = (now, normalized)
                return normalized
        except Exception as exc:
            logger.debug("iTunes search failed for '%s': %s", q_clean, exc)
            return []

    async def search_jiosaavn(
        self,
        query: str,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """Search JioSaavn API for songs (comprehensive coverage for Indian/Punjabi/Pop music)."""
        q_clean = query.strip()
        if len(q_clean) < 2:
            return []

        cache_key = f"saavn:{q_clean.lower()}:{limit}"
        now = datetime.now()
        if cache_key in self._query_cache:
            ts, cached_res = self._query_cache[cache_key]
            if now - ts < self.cache_ttl:
                return cached_res

        self._clean_cache()
        params: dict[str, str | int] = {
            "__call": "search.getResults",
            "q": q_clean,
            "_format": "json",
            "_marker": "0",
            "api_version": "4",
            "ctx": "web6dot0",
            "n": limit,
            "p": 1,
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=4.0, headers=headers, follow_redirects=True
            ) as client:
                resp = await client.get("https://www.jiosaavn.com/api.php", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_results = data.get("results", [])
                else:
                    raw_results = []

                normalized: list[dict[str, Any]] = []
                for item in raw_results:
                    parsed = self._normalize_jiosaavn_track(item)
                    if parsed:
                        normalized.append(parsed)
                        self._track_cache[parsed["id"]] = (now, parsed)

                self._query_cache[cache_key] = (now, normalized)
                return normalized
        except Exception as exc:
            logger.debug("JioSaavn search failed for '%s': %s", q_clean, exc)
            return []

    async def search_tracks(
        self,
        query: str,
        limit: int = 20,
        country: str | None = None,
    ) -> list[dict[str, Any]]:
        """Multi-source concurrent search combining JioSaavn and iTunes.

        Provides global and regional coverage with high-priority exact title matching.
        """
        q_clean = query.strip()
        if len(q_clean) < 2:
            return []

        target_country = country or self._detect_country(q_clean)
        cache_key = f"multi:{q_clean.lower()}:{limit}:{target_country}"
        now = datetime.now()
        if cache_key in self._query_cache:
            ts, cached_res = self._query_cache[cache_key]
            if now - ts < self.cache_ttl:
                return cached_res

        # Query JioSaavn and iTunes in parallel
        saavn_task = self.search_jiosaavn(q_clean, limit=limit)
        itunes_task = self.search_itunes(q_clean, limit=limit, country=target_country)
        tasks = [saavn_task, itunes_task]

        # If searching Indian storefront or Indian artist, also check iTunes US as fallback
        if target_country == "IN":
            tasks.append(self.search_itunes(q_clean, limit=limit, country="US"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        saavn_tracks = results[0] if len(results) > 0 and isinstance(results[0], list) else []
        itunes_tracks = results[1] if len(results) > 1 and isinstance(results[1], list) else []
        itunes_us = results[2] if len(results) > 2 and isinstance(results[2], list) else []

        all_candidates: list[dict[str, Any]] = saavn_tracks + itunes_tracks + itunes_us

        # Rank candidates by relevance to query
        q_norm = q_clean.lower().strip()

        def match_priority(t: dict[str, Any]) -> int:
            t_title = str(t.get("title", "")).lower().strip()
            t_artist = str(t.get("artist_name", "")).lower().strip()
            if t_title == q_norm:
                return 0
            if t_artist == q_norm:
                return 1
            if t_title.startswith(q_norm):
                return 2
            if q_norm in t_title:
                return 3
            if q_norm in t_artist:
                return 4
            return 5

        all_candidates.sort(key=match_priority)

        seen_keys: set[tuple[str, str]] = set()
        seen_ids: set[str] = set()
        merged: list[dict[str, Any]] = []

        for t in all_candidates:
            tid = str(t["id"])
            t_key = (
                str(t.get("title", "")).lower().strip(),
                str(t.get("artist_name", "")).lower().strip(),
            )
            if tid not in seen_ids and t_key not in seen_keys:
                seen_ids.add(tid)
                seen_keys.add(t_key)
                merged.append(t)
                if len(merged) >= limit:
                    break

        self._query_cache[cache_key] = (now, merged)
        return merged

    async def get_jiosaavn_track_by_id(self, saavn_id: str) -> dict[str, Any] | None:
        """Lookup JioSaavn track by raw saavn id or canonical ext:saavn:{id}."""
        sid = saavn_id.split("ext:saavn:")[-1]
        canonical_id = f"ext:saavn:{sid}"
        now = datetime.now()
        if canonical_id in self._track_cache:
            ts, track = self._track_cache[canonical_id]
            if now - ts < self.cache_ttl:
                return track

        params: dict[str, str] = {
            "__call": "song.getDetails",
            "pids": sid,
            "_format": "json",
            "_marker": "0",
            "api_version": "4",
            "ctx": "web6dot0",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=4.0, headers=headers, follow_redirects=True
            ) as client:
                resp = await client.get("https://www.jiosaavn.com/api.php", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    songs = data.get("songs") or []
                    if not songs and sid in data:
                        songs = [data[sid]]
                    if songs:
                        parsed = self._normalize_jiosaavn_track(songs[0])
                        if parsed:
                            self._track_cache[canonical_id] = (now, parsed)
                            return parsed
        except Exception as exc:
            logger.debug("Failed to lookup JioSaavn track %s: %s", sid, exc)
            return None
        return None

    async def get_itunes_track_by_id(self, itunes_id: str) -> dict[str, Any] | None:
        """Lookup iTunes track by raw trackId or canonical ext:itunes:{trackId}."""
        track_id = itunes_id.split("ext:itunes:")[-1]
        canonical_id = f"ext:itunes:{track_id}"
        now = datetime.now()
        if canonical_id in self._track_cache:
            ts, track = self._track_cache[canonical_id]
            if now - ts < self.cache_ttl:
                return track

        lookup_params: dict[str, str] = {"id": str(track_id)}
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                for country in ("IN", "US"):
                    lookup_params["country"] = country
                    response = await client.get(self.LOOKUP_URL, params=lookup_params)
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])
                        if results:
                            parsed = self._normalize_itunes_track(results[0])
                            if parsed:
                                self._track_cache[canonical_id] = (now, parsed)
                                return parsed
        except Exception as exc:
            logger.debug("Failed to lookup iTunes track %s: %s", itunes_id, exc)
            return None
        return None

    async def get_track_by_id(self, ext_id: str) -> dict[str, Any] | None:
        """Lookup external track across all supported sources."""
        now = datetime.now()
        if ext_id in self._track_cache:
            ts, track = self._track_cache[ext_id]
            if now - ts < self.cache_ttl:
                return track

        if ext_id.startswith("ext:saavn:"):
            return await self.get_jiosaavn_track_by_id(ext_id)
        if ext_id.startswith("ext:itunes:"):
            return await self.get_itunes_track_by_id(ext_id)
        return None

    async def fetch_candidates_for_seeds(
        self,
        seed_tracks: list[dict[str, Any]],
        limit_per_query: int = 15,
    ) -> list[dict[str, Any]]:
        """Retrieve real candidate tracks matching seeds, peer graph, and genre vibes."""
        candidates: list[dict[str, Any]] = []
        seen_ids = {str(s.get("id")) for s in seed_tracks}
        seen_keys = {
            (
                str(s.get("title", "")).lower().strip(),
                str(s.get("artist_name", "")).lower().strip(),
            )
            for s in seed_tracks
        }

        # 1. Gather distinct artists, genres, and cultures from seeds
        seed_artists: list[str] = []
        seed_cultures: set[str] = set()

        for s in seed_tracks:
            art = s.get("artist_name")
            if art and str(art) not in seed_artists:
                seed_artists.append(str(art))

            genre = str(s.get("genre") or s.get("primaryGenreName") or "")
            tags = list(s.get("tags") or [])
            title = str(s.get("title") or "")
            culture = s.get("culture") or classify_genre_and_culture(
                genre, tags, artist_name=art, title=title
            )
            seed_cultures.add(culture)

        # Detect dominant mood of the seeds
        mood_profile = detect_seed_mood_profile(seed_tracks)
        dominant_mood = mood_profile["dominant_mood"]

        # Determine primary market country based on seed cultures
        is_desi = "punjabi" in seed_cultures or "bollywood_desi" in seed_cultures
        primary_country = "IN" if is_desi else "US"
        if "kpop" in seed_cultures:
            primary_country = "KR"
        elif "latin" in seed_cultures:
            primary_country = "MX"

        # 2. Extract collaborator and peer artists from collaborative knowledge graph
        graph_peers: list[str] = []
        for art in seed_artists:
            art_lower = art.lower().strip()
            for g_key, peers in ARTIST_COLLABORATOR_GRAPH.items():
                if g_key in art_lower or art_lower in g_key:
                    for p in peers:
                        if p not in graph_peers:
                            graph_peers.append(p)

        # 3. Formulate multi-source search queries:
        # A. Seed Artist Radio (core artist catalog)
        search_queries = list(seed_artists)
        # B. Direct Collaborators & Co-listening Peers
        search_queries.extend(graph_peers)

        # 4. Add mood- and culture-specific peer discovery query terms
        if "punjabi" in seed_cultures:
            if dominant_mood == MOOD_PARTY:
                search_queries.extend(
                    [
                        "punjabi party hits",
                        "punjabi dance hits",
                        "Diljit Dosanjh party",
                        "Karan Aujla party",
                        "Sukha party",
                        "bhangra party hits",
                        "latest punjabi party",
                    ]
                )
                for art in seed_artists:
                    search_queries.append(f"{art} party")
                    search_queries.append(f"{art} dance")
            elif dominant_mood == MOOD_SAD:
                search_queries.extend(
                    [
                        "punjabi sad songs",
                        "B Praak sad hits",
                        "Sidhu Moose Wala sad",
                        "Karan Aujla sad",
                        "punjabi emotional songs",
                    ]
                )
                for art in seed_artists:
                    search_queries.append(f"{art} sad")
                    search_queries.append(f"{art} emotional")
            else:
                search_queries.extend(
                    [
                        "latest punjabi hits",
                        "punjabi top 50",
                        "punjabi hip hop",
                        "trending punjabi",
                        "Diljit Dosanjh hits",
                        "Karan Aujla hits",
                        "Sidhu Moose Wala hits",
                        "AP Dhillon hits",
                        "Shubh hits",
                        "Sukha hits",
                        "Arjan Dhillon hits",
                        "Tegi Pannu hits",
                        "Baggh-e SMG hits",
                    ]
                )
                for art in seed_artists:
                    search_queries.append(f"{art} hits")
        elif "bollywood_desi" in seed_cultures:
            if dominant_mood == MOOD_SAD:
                search_queries.extend(
                    [
                        "Arijit Singh sad hits",
                        "KK sad songs",
                        "Atif Aslam sad songs",
                        "Mohit Chauhan sad songs",
                        "B Praak sad songs",
                        "Anuv Jain hits",
                        "Faheem Abdullah",
                        "The Local Train",
                        "Prateek Kuhad heartbreak",
                        "bollywood sad songs",
                        "hindi heartbreak songs",
                        "Mustafa Zahid sad",
                        "Pritam sad hits",
                        "hindi melancholic songs",
                        "soulful hindi songs",
                    ]
                )
                for art in seed_artists:
                    search_queries.append(f"{art} sad")
                    search_queries.append(f"{art} emotional")
            elif dominant_mood == MOOD_PARTY:
                search_queries.extend(
                    [
                        "bollywood party hits",
                        "hindi dance club songs",
                        "punjabi party songs",
                        "Badshah dance hits",
                        "Yo Yo Honey Singh party",
                        "Diljit Dosanjh party",
                    ]
                )
                for art in seed_artists:
                    search_queries.append(f"{art} party")
                    search_queries.append(f"{art} dance")
            else:
                search_queries.extend(
                    [
                        "Arijit Singh romantic",
                        "Pritam romantic hits",
                        "Mohit Chauhan romantic",
                        "Atif Aslam romantic",
                        "Faheem Abdullah hits",
                        "Anuv Jain hits",
                        "bollywood romantic hits",
                        "hindi romcom songs",
                        "Jasleen Royal romantic",
                        "KK romantic hits",
                        "Javed Ali romantic hits",
                        "Sonu Nigam romantic hits",
                    ]
                )
                for art in seed_artists:
                    search_queries.append(f"{art} romantic")
        elif "hiphop" in seed_cultures:
            if dominant_mood == MOOD_SAD:
                search_queries.extend(
                    [
                        "Juice WRLD",
                        "XXXTentacion",
                        "Lil Peep",
                        "Rod Wave",
                        "sad rap melodic",
                        "melodic emotional trap",
                    ]
                )
            else:
                search_queries.extend(
                    [
                        "Travis Scott",
                        "Metro Boomin",
                        "Future",
                        "21 Savage",
                        "Gunna",
                        "Lil Baby",
                        "Playboi Carti",
                        "Drake",
                        "Kendrick Lamar",
                    ]
                )
        elif "rock" in seed_cultures:
            search_queries.extend(
                [
                    "Arctic Monkeys",
                    "The Strokes",
                    "Tame Impala",
                    "Nirvana",
                    "Radiohead",
                ]
            )
        elif "western_pop" in seed_cultures:
            search_queries.extend(
                [
                    "The Weeknd",
                    "Dua Lipa",
                    "Billie Eilish",
                    "Olivia Rodrigo",
                    "Taylor Swift",
                    "Post Malone",
                    "Ariana Grande",
                ]
            )
        elif "rnb" in seed_cultures:
            search_queries.extend(
                [
                    "SZA",
                    "Frank Ocean",
                    "Brent Faiyaz",
                    "Daniel Caesar",
                    "Giveon",
                ]
            )
        elif "kpop" in seed_cultures:
            search_queries.extend(
                [
                    "BTS",
                    "NewJeans",
                    "BLACKPINK",
                    "Stray Kids",
                    "LE SSERAFIM",
                    "TWICE",
                ]
            )
        elif "latin" in seed_cultures:
            search_queries.extend(
                [
                    "Bad Bunny",
                    "J Balvin",
                    "Rauw Alejandro",
                    "Karol G",
                    "Feid",
                    "Peso Pluma",
                ]
            )

        # Deduplicate search queries while preserving order
        unique_queries: list[str] = []
        seen_q: set[str] = set()
        for q in search_queries:
            q_clean = q.strip().lower()
            if q_clean not in seen_q:
                seen_q.add(q_clean)
                unique_queries.append(q)

        # Concurrently execute candidate searches across top queries in parallel
        batch_queries = unique_queries[:20]
        search_tasks = [
            self.search_tracks(q, limit=limit_per_query, country=primary_country)
            for q in batch_queries
        ]
        batch_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        for query_res in batch_results:
            if not isinstance(query_res, list):
                continue
            for r in query_res:
                r_culture = r.get("culture") or classify_genre_and_culture(
                    str(r.get("primaryGenreName") or ""),
                    r.get("tags"),
                    artist_name=str(r.get("artist_name") or ""),
                    title=str(r.get("title") or ""),
                )

                # 1. Cultural boundary guard:
                # When seeds are Punjabi, strictly enforce Punjabi/Desi tracks
                if "punjabi" in seed_cultures:
                    if r_culture not in ("punjabi", "bollywood_desi"):
                        r_blob = (
                            f"{str(r.get('title', ''))} {str(r.get('artist_name', ''))}"
                        ).lower()
                        if not any(
                            k in r_blob
                            for k in (
                                "singh",
                                "kaur",
                                "dhillon",
                                "aujla",
                                "dosanjh",
                                "sukha",
                                "shubh",
                                "maan",
                                "pannu",
                                "smg",
                                "jxggi",
                                "b praak",
                                "sidhu",
                                "punjabi",
                                "desi",
                            )
                        ):
                            continue
                elif "bollywood_desi" in seed_cultures:
                    if r_culture not in ("bollywood_desi", "punjabi"):
                        r_blob = (
                            f"{str(r.get('title', ''))} {str(r.get('artist_name', ''))}"
                        ).lower()
                        if not any(
                            k in r_blob
                            for k in (
                                "singh",
                                "shreya",
                                "pritam",
                                "kumar",
                                "ali",
                                "khan",
                                "jain",
                                "nigam",
                                "malik",
                                "raval",
                                "nautiyal",
                                "kaur",
                                "dhillon",
                                "b praak",
                                "local train",
                                "kuhad",
                            )
                        ):
                            continue
                elif "hiphop" in seed_cultures and r_culture in (
                    "bollywood_desi",
                    "kpop",
                    "punjabi",
                ):
                    continue

                # 2. Strict mood boundary guard
                if dominant_mood == MOOD_SAD:
                    cand_mood = classify_track_mood(r)
                    if cand_mood == MOOD_PARTY:
                        continue
                    r_title = str(r.get("title", "")).lower()
                    if any(
                        bad in r_title
                        for bad in (
                            "party",
                            "remix",
                            "club mix",
                            "dj mix",
                            "dhamaka",
                            "bhangra dance",
                            "celebration",
                        )
                    ):
                        continue
                elif dominant_mood == MOOD_PARTY:
                    cand_mood = classify_track_mood(r)
                    if cand_mood == MOOD_SAD:
                        continue

                rid = str(r.get("id"))
                r_key = (
                    str(r.get("title", "")).lower().strip(),
                    str(r.get("artist_name", "")).lower().strip(),
                )
                if rid not in seen_ids and r_key not in seen_keys:
                    seen_ids.add(rid)
                    seen_keys.add(r_key)
                    candidates.append(r)

        return candidates


# Global singleton service
live_search_service = LiveSearchService()
