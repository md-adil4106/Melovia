"""Tests for in-memory session store, rate limiting, and persistent profile isolation.

Tests cover:
1. Session isolation: multiple sessions maintain separate independent contexts.
2. Reversible constraint undo: removing a constraint replays remaining constraints cleanly.
3. Reset: clears session context.
4. Token-bucket rate limiting enforcement.
5. Invariant: persistent database profile table (ProfilePlaceholder) remains untouched.
6. API endpoint integration (/refine, DELETE /refine/{id}, POST /refine/session/reset).
"""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import pytest  # noqa: E402
from fixtures.make_mock_catalog import generate_mock_catalog  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from app.recsys import CatalogStore  # noqa: E402
from app.schemas.refinement import KnobDeltas, Refinement, TagWeight  # noqa: E402
from app.session.store import SessionStore, TokenBucketRateLimiter  # noqa: E402


def test_session_isolation() -> None:
    """Ensure session contexts are strictly isolated by session_id."""
    store = SessionStore()

    # Session 1: Adds energy
    ref1 = Refinement(knobs=KnobDeltas(energy=0.6))
    store.apply_refinement("session-1", ref1, "more energetic")

    # Session 2: Adds valence (mood)
    ref2 = Refinement(knobs=KnobDeltas(valence=0.5))
    store.apply_refinement("session-2", ref2, "happier")

    s1 = store.get("session-1")
    s2 = store.get("session-2")

    assert s1 is not None and s2 is not None
    assert s1.context.knobs["energy"] == 0.6
    assert s1.context.knobs["valence"] == 0.0

    assert s2.context.knobs["energy"] == 0.0
    assert s2.context.knobs["valence"] == 0.5


def test_reversible_constraint_undo() -> None:
    """Ensure removing a constraint cleanly replays remaining constraints."""
    store = SessionStore()

    # Add energy constraint
    store.apply_refinement(
        "session-undo", Refinement(knobs=KnobDeltas(energy=0.5)), "more energetic"
    )
    # Add rock boost tag constraint
    chips = store.apply_refinement(
        "session-undo",
        Refinement(boost_tags=[TagWeight(tag="rock", weight=0.8)]),
        "add rock",
    )

    s = store.get("session-undo")
    assert s is not None
    assert len(s.constraints) == 2
    assert s.context.knobs["energy"] == 0.5
    assert "rock" in s.context.boost_tags

    # Find the rock constraint ID
    rock_chip = next(c for c in chips if c.type == "boost_tag")
    removed = store.remove_constraint("session-undo", rock_chip.id)
    assert removed

    # After removal, rock is gone, but energy remains
    s_after = store.get("session-undo")
    assert s_after is not None
    assert len(s_after.constraints) == 1
    assert s_after.context.knobs["energy"] == 0.5
    assert "rock" not in s_after.context.boost_tags


def test_session_reset() -> None:
    """Ensure reset clears all applied constraints and context."""
    store = SessionStore()
    store.apply_refinement("session-reset", Refinement(knobs=KnobDeltas(energy=0.8)), "high energy")

    store.reset("session-reset")
    s = store.get("session-reset")
    assert s is not None
    assert len(s.constraints) == 0
    assert s.context.is_empty()


def test_token_bucket_rate_limiter() -> None:
    """Ensure token bucket permits burst capacity and throttles once depleted."""
    limiter = TokenBucketRateLimiter(rate=1.0, capacity=3.0)

    key = "test-client"
    # First 3 tokens consumed immediately (burst capacity = 3)
    assert limiter.consume(key)
    assert limiter.consume(key)
    assert limiter.consume(key)

    # 4th token within the same second is rejected
    assert not limiter.consume(key)


def test_persistent_profile_remains_untouched() -> None:
    """Verify that ProfilePlaceholder table is completely unreferenced by session steering."""
    # Ensure ProfilePlaceholder table definition has not been imported or wired to SessionStore
    import inspect

    import app.session.store as store_mod

    source = inspect.getsource(store_mod)
    assert "ProfilePlaceholder" not in source
    assert "profiles" not in source
    assert "SQLAlchemy" not in source


@pytest.fixture(scope="module")
def mock_catalog(tmp_path_factory: pytest.TempPathFactory) -> CatalogStore:
    bdir = tmp_path_factory.mktemp("bundle_refine_api")
    generate_mock_catalog(bdir)
    return CatalogStore.load(bdir)


@pytest.mark.asyncio
async def test_refine_api_flow(mock_catalog: CatalogStore) -> None:
    """Test full HTTP flow: recommendations -> refine -> delete constraint -> reset."""
    app.state.catalog_store = mock_catalog
    seeds = mock_catalog.track_ids[:3]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create recommendations
        rec_res = await client.post(
            "/recommendations",
            json={"seed_track_ids": seeds, "n": 30, "discovery": 0.35},
        )
        assert rec_res.status_code == 200
        cand_set_id = rec_res.json()["candidate_set_id"]

        # 2. Refine with "more energetic"
        ref_res = await client.post(
            "/refine",
            json={"candidate_set_id": cand_set_id, "utterance": "more energetic"},
        )
        assert ref_res.status_code == 200
        data = ref_res.json()
        assert data["session_id"].startswith("sess_")
        assert len(data["applied"]) >= 1
        assert any(c["type"] == "knob" for c in data["applied"])
        assert len(data["items"]) > 0

        constraint_id = data["applied"][0]["id"]
        session_id = data["session_id"]
        client.cookies.set("melovia_session_id", session_id)

        # 3. Undo constraint via DELETE /refine/{id}
        del_res = await client.delete(
            f"/refine/{constraint_id}?candidate_set_id={cand_set_id}",
        )
        assert del_res.status_code == 200
        del_data = del_res.json()
        assert not any(c["id"] == constraint_id for c in del_data["applied"])

        # 4. Reset session context
        reset_res = await client.post(
            "/refine/session/reset",
        )
        assert reset_res.status_code == 200
        assert reset_res.json()["status"] == "ok"
