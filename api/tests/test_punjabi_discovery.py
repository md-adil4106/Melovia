"""Unit and integration tests for Punjabi music search and recommendation quality."""

import pytest

from app.services.live_search import (
    classify_genre_and_culture,
    decrypt_jiosaavn_media_url,
    live_search_service,
)


def test_punjabi_culture_classification() -> None:
    """Punjabi artists must be classified as 'punjabi' culture regardless of iTunes genre tags."""
    # Karan Aujla often tagged as 'Hip-Hop/Rap' by iTunes/Apple Music
    assert (
        classify_genre_and_culture("Hip-Hop/Rap", ["hip-hop/rap"], artist_name="Karan Aujla")
        == "punjabi"
    )
    assert (
        classify_genre_and_culture("Rap", ["rap", "desi"], artist_name="Sidhu Moose Wala")
        == "punjabi"
    )
    assert (
        classify_genre_and_culture("Pop", ["pop"], artist_name="Diljit Dosanjh")
        == "punjabi"
    )
    assert (
        classify_genre_and_culture("", [], artist_name="Baggh-e SMG, Big Kay Smg, Farmaan SMG")
        == "punjabi"
    )
    assert (
        classify_genre_and_culture("", [], artist_name="Jxggi, Dishant, SickBoi")
        == "punjabi"
    )
    assert (
        classify_genre_and_culture("Hip-Hop", [], artist_name="Sukha")
        == "punjabi"
    )

    # Western hip-hop artists must remain 'hiphop'
    assert (
        classify_genre_and_culture("Hip-Hop/Rap", ["hip-hop"], artist_name="Travis Scott")
        == "hiphop"
    )
    assert (
        classify_genre_and_culture("Hip-Hop/Rap", ["rap"], artist_name="Drake")
        == "hiphop"
    )
    assert (
        classify_genre_and_culture("Hip-Hop/Rap", ["trap"], artist_name="Gunna")
        == "hiphop"
    )

    # Bollywood / Filmi artists remain 'bollywood_desi'
    assert (
        classify_genre_and_culture("Bollywood", ["hindi"], artist_name="Arijit Singh")
        == "bollywood_desi"
    )


def test_jiosaavn_des_decryption() -> None:
    """Test JioSaavn DES-ECB media URL decryption."""
    # Real encrypted media URL payload for EX-FILES
    enc_media = (
        "ID2ieOjCrwfgWvL5sXl4B1ImC5QfbsDyXpvr3fldh227OUjN7VffRSQoRyB9y9RYN0/h6/HQihpX3+eHnCqfRxw7tS9a8Gtq"
    )
    decrypted = decrypt_jiosaavn_media_url(enc_media)
    assert decrypted is not None
    assert decrypted.startswith("https://aac.saavncdn.com/")
    assert decrypted.endswith(".mp4")
    # Verify stream upgrade from 96k to 160k
    assert "_160.mp4" in decrypted

    # Invalid input handling
    assert decrypt_jiosaavn_media_url(None) is None
    assert decrypt_jiosaavn_media_url("") is None
    assert decrypt_jiosaavn_media_url("invalid_payload") is None


@pytest.mark.asyncio
async def test_search_punjabi_tracks_ex_files_and_iykyk() -> None:
    """Searching for 'EX-FILES' and 'IYKYK' must return the modern Punjabi releases as #1 hits."""
    # Test EX-FILES
    ex_results = await live_search_service.search_tracks("EX-FILES", limit=5)
    assert len(ex_results) > 0
    top_ex = ex_results[0]
    assert "ex-files" in top_ex["title"].lower()
    assert "baggh-e smg" in top_ex["artist_name"].lower()
    assert top_ex["culture"] == "punjabi"
    assert top_ex["preview_url"] is not None
    assert top_ex["artwork_url"] is not None

    # Test IYKYK
    iykyk_results = await live_search_service.search_tracks("IYKYK", limit=5)
    assert len(iykyk_results) > 0
    top_iykyk = iykyk_results[0]
    assert "iykyk" in top_iykyk["title"].lower()
    assert "jxggi" in top_iykyk["artist_name"].lower()
    assert top_iykyk["culture"] == "punjabi"
    assert top_iykyk["preview_url"] is not None
    assert top_iykyk["artwork_url"] is not None


@pytest.mark.asyncio
async def test_punjabi_seed_recommendations_exclude_western_hiphop() -> None:
    """When Punjabi seeds are provided, candidate generation must strictly isolate Punjabi music."""
    seed_tracks = [
        {
            "id": "ext:saavn:test1",
            "title": "5-7",
            "artist_name": "Karan Aujla",
            "genre": "Hip-Hop/Rap",
            "tags": ["punjabi"],
            "culture": "punjabi",
            "scalars": {"energy": 0.82, "valence": 0.70, "danceability": 0.85},
        },
        {
            "id": "ext:saavn:test2",
            "title": "Ashke",
            "artist_name": "Karan Aujla",
            "genre": "Hip-Hop/Rap",
            "tags": ["punjabi"],
            "culture": "punjabi",
            "scalars": {"energy": 0.82, "valence": 0.70, "danceability": 0.85},
        },
    ]

    candidates = await live_search_service.fetch_candidates_for_seeds(
        seed_tracks, limit_per_query=5
    )
    assert len(candidates) > 0

    # Ensure zero American hip-hop artists in Punjabi recommendations
    forbidden_artists = {
        "travis scott",
        "drake",
        "gunna",
        "lil baby",
        "kendrick lamar",
        "future",
        "21 savage",
    }
    for cand in candidates:
        art_lower = cand["artist_name"].lower()
        for f in forbidden_artists:
            msg = f"Forbidden artist {f} leaked into Punjabi recommendations: {cand['title']}"
            assert f not in art_lower, msg
        assert cand["culture"] in ("punjabi", "bollywood_desi")
