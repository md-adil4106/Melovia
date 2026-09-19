"""Seed Database with Melovia Mock Catalog Bundle.

Reads the vector catalog bundle from data/bundles/v1/ and populates
relational tables:
- catalog_versions
- artists
- tracks
- tags
- track_tags
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure api is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Artist,
    Base,
    CatalogVersion,
    Tag,
    Track,
    TrackTag,
    engine,
)
from app.db.session import async_session_factory


async def seed_from_bundle(bundle_dir: Path, session: AsyncSession) -> None:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest.json at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    version = manifest["version"]
    plan = manifest.get("plan", "mock")
    track_count = manifest["track_count"]

    # 1. Check or insert CatalogVersion
    existing_cv = await session.get(CatalogVersion, version)
    if not existing_cv:
        cv = CatalogVersion(
            version=version,
            checksum=manifest["files"].get("tracks.parquet", "unknown"),
            plan=plan,
            track_count=track_count,
            meta=manifest,
        )
        session.add(cv)

    # 2. Load tag vocabulary and insert Tags
    tag_vocab_path = bundle_dir / "tag_vocab.json"
    tag_name_to_model: dict[str, Tag] = {}
    if tag_vocab_path.exists():
        with open(tag_vocab_path, "r", encoding="utf-8") as f:
            tag_vocab = json.load(f)

        tags_list = tag_vocab.get("tags", [])
        categories = tag_vocab.get("tag_categories", {})

        # Query existing tags
        result = await session.execute(select(Tag))
        for existing_t in result.scalars():
            tag_name_to_model[existing_t.name] = existing_t

        for tag_name in tags_list:
            if tag_name not in tag_name_to_model:
                new_tag = Tag(name=tag_name, category=categories.get(tag_name, "general"))
                session.add(new_tag)
                tag_name_to_model[tag_name] = new_tag

        await session.flush()

    # 3. Load regions.json to know region top_tags
    regions_path = bundle_dir / "regions.json"
    region_tags_map: dict[int, list[str]] = {}
    if regions_path.exists():
        with open(regions_path, "r", encoding="utf-8") as f:
            regions_data = json.load(f)
        for r in regions_data:
            region_tags_map[r["region_id"]] = r.get("top_tags", [])

    # 4. Load tracks.parquet
    tracks_file = bundle_dir / "tracks.parquet"
    table = pq.read_table(tracks_file)
    tracks_dict = table.to_pydict()

    # Query existing artists
    result = await session.execute(select(Artist.id))
    existing_artist_ids = set(result.scalars())

    artist_batch: dict[str, Artist] = {}
    n = len(tracks_dict["id"])

    for i in range(n):
        art_id = tracks_dict["artist_id"][i]
        art_name = tracks_dict["artist_name"][i]
        if art_id not in existing_artist_ids and art_id not in artist_batch:
            artist_batch[art_id] = Artist(
                id=art_id,
                name=art_name,
                mbid=None,
            )

    if artist_batch:
        session.add_all(list(artist_batch.values()))
        await session.flush()

    # 5. Insert Tracks and TrackTags
    result = await session.execute(select(Track.id))
    existing_track_ids = set(result.scalars())

    new_tracks = []
    track_tags = []

    for i in range(n):
        trk_id = tracks_dict["id"][i]
        if trk_id in existing_track_ids:
            continue

        trk = Track(
            id=trk_id,
            mbid=tracks_dict.get("mbid", [None] * n)[i],
            title=tracks_dict["title"][i],
            artist_id=tracks_dict["artist_id"][i],
            year=int(tracks_dict["year"][i]) if tracks_dict["year"][i] else None,
            isrcs=[tracks_dict["isrc"][i]] if "isrc" in tracks_dict else [],
            source="mock",
            popularity_pct=float(tracks_dict["popularity_pct"][i]),
            has_a=bool(tracks_dict["has_a"][i]),
            has_t=bool(tracks_dict["has_t"][i]),
            track_idx=int(tracks_dict["track_idx"][i]),
        )
        new_tracks.append(trk)

        # Attach region tags
        reg_id = int(tracks_dict.get("region_id", [0] * n)[i])
        tags_for_region = region_tags_map.get(reg_id, [])
        for rank, tname in enumerate(tags_for_region[:4]):
            tag_model = tag_name_to_model.get(tname)
            if tag_model:
                weight = round(1.0 - (rank * 0.15), 2)
                track_tags.append(
                    TrackTag(
                        track_id=trk_id,
                        tag_id=tag_model.id,
                        weight=weight,
                    )
                )

    if new_tracks:
        session.add_all(new_tracks)
        await session.flush()

    if track_tags:
        session.add_all(track_tags)

    await session.commit()
    print(f"Seeded {len(artist_batch)} artists, {len(new_tracks)} tracks, {len(track_tags)} track tags into DB.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed database from Melovia catalog bundle.")
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "bundles" / "v1",
        help="Path to catalog bundle directory",
    )
    args = parser.parse_args()

    # Create tables if not present (for sqlite or quick setup)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await seed_from_bundle(args.bundle_dir, session)


if __name__ == "__main__":
    asyncio.run(main())
