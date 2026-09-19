"""Integration tests for catalog ingestion, fixture parsing, and idempotency."""

from pathlib import Path

import pytest
from pipelines.ingest_acousticbrainz import parse_acousticbrainz_dump
from pipelines.ingest_catalog import run_ingestion
from pipelines.ingest_listenbrainz import parse_listenbrainz_dump
from pipelines.ingest_musicbrainz import parse_musicbrainz_dump
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import StagingTrack

repo_root = Path(__file__).resolve().parent.parent.parent
dumps_dir = repo_root / "fixtures" / "dumps"


def test_parse_sample_musicbrainz_dump() -> None:
    """Parse tiny sample MusicBrainz fixture dump and verify records."""
    mb_file = dumps_dir / "sample_musicbrainz.jsonl"
    recs = parse_musicbrainz_dump(mb_file)
    assert len(recs) == 13

    # Check Bohemian Rhapsody
    bohemian = next(r for r in recs if r.title == "Bohemian Rhapsody")
    assert bohemian.artist_name == "Queen"
    assert bohemian.year == 1975
    assert "GBUM71029607" in bohemian.isrcs
    assert any(t["name"] == "rock" for t in bohemian.tags)


def test_parse_sample_listenbrainz_dump() -> None:
    """Parse tiny sample ListenBrainz fixture dump and verify stats."""
    lb_file = dumps_dir / "sample_listenbrainz.jsonl"
    stats = parse_listenbrainz_dump(lb_file)
    assert len(stats) >= 6
    assert stats["736233d6-dd07-4221-a5d2-09859f77f3a7"] == 1200000


def test_parse_sample_acousticbrainz_dump() -> None:
    """Parse tiny sample AcousticBrainz fixture dump and verify scalars."""
    ab_file = dumps_dir / "sample_acousticbrainz.jsonl"
    features = parse_acousticbrainz_dump(ab_file)
    assert len(features) >= 6
    bohemian_feats = features["736233d6-dd07-4221-a5d2-09859f77f3a7"]
    assert bohemian_feats["bpm"] == 72.0
    assert bohemian_feats["danceability"] is not None


@pytest.mark.asyncio
async def test_ingestion_idempotency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-running ingestion twice must produce identical row counts and 0 duplicates."""
    db_file = tmp_path / "idempotency_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    # Monkeypatch engine and session factory
    monkeypatch.setattr("pipelines.ingest_catalog.engine", test_engine)
    monkeypatch.setattr("pipelines.ingest_catalog.async_session_factory", test_session_factory)

    checkpoint_file = tmp_path / "checkpoint.json"

    # Run 1: Ingest 50 tracks
    res1 = await run_ingestion(
        target_count=50,
        batch_size=20,
        checkpoint_file=checkpoint_file,
        resume=False,
    )
    assert res1["processed_count"] == 50

    async with test_session_factory() as session:
        count_res1 = await session.execute(select(func.count(StagingTrack.id)))
        total_rows_1 = count_res1.scalar_one()

    # Run 2: Re-run ingestion of same 50 tracks (with resume=True and idempotency)
    await run_ingestion(
        target_count=50,
        batch_size=20,
        checkpoint_file=checkpoint_file,
        resume=True,
    )

    async with test_session_factory() as session:
        count_res2 = await session.execute(select(func.count(StagingTrack.id)))
        total_rows_2 = count_res2.scalar_one()

    assert total_rows_1 == total_rows_2 == 50, "Row count must remain identical after re-running"


@pytest.mark.asyncio
async def test_ingestion_checkpoint_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interrupted ingestion must resume from saved checkpoint."""
    db_file = tmp_path / "resume_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    test_engine = create_async_engine(db_url)
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    monkeypatch.setattr("pipelines.ingest_catalog.engine", test_engine)
    monkeypatch.setattr("pipelines.ingest_catalog.async_session_factory", test_session_factory)

    checkpoint_file = tmp_path / "resume_checkpoint.json"

    # Step 1: Run with 20 items
    await run_ingestion(
        target_count=20,
        batch_size=10,
        checkpoint_file=checkpoint_file,
        resume=False,
    )

    assert checkpoint_file.exists()

    # Step 2: Resume with target 40 items
    res = await run_ingestion(
        target_count=40,
        batch_size=10,
        checkpoint_file=checkpoint_file,
        resume=True,
    )

    assert res["processed_count"] == 40
    async with test_session_factory() as session:
        count_res = await session.execute(select(func.count(StagingTrack.id)))
        assert count_res.scalar_one() == 40
