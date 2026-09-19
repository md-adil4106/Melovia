"""Coverage probe pipeline for evaluating external music metadata coverage.

Measures:
1. AcousticBrainz (AB) audio feature coverage
2. Tag / Genre coverage (recording level with artist/release fallback)
3. ISRC code presence

Enforces:
- MusicBrainz 1.0 request/second rate limit
- Descriptive User-Agent header
- Local disk caching to prevent duplicate network calls
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "MeloviaCoverageProbe/0.1.0 ( https://github.com/md-adil4106/Melovia )"

# Representative curated sample of popular recording MBIDs across diverse genres
CURATED_POPULAR_MBIDS = [
    # Rock / Pop classic & modern
    "736233d6-dd07-4221-a5d2-09859f77f3a7",  # Queen - Bohemian Rhapsody
    "12809623-64a4-4f81-ba55-9a8ff7ee20d8",  # The Beatles - Hey Jude
    "b5f09aa4-dc6e-4f76-80ce-1c4b8b60f1ee",  # Nirvana - Smells Like Teen Spirit
    "40722238-d698-4670-8cc3-1188339b3420",  # Fleetwood Mac - Dreams
    "3b683cb8-cc38-4e8c-a111-e40d04c35e3b",  # Michael Jackson - Billie Jean
    "9c748c90-09fa-474a-81a1-f3b890f84be1",  # Radiohead - Paranoid Android
    "5d7d3d78-b1fb-4899-b13c-74a004c27806",  # Pink Floyd - Comfortably Numb
    "a073f1d3-63dc-4c40-9a25-968fa3083e9b",  # David Bowie - Heroes
    "e26f3325-1033-40bf-953b-00da8fa5ebbc",  # Daft Punk - Get Lucky
    "c8a38a74-d4ef-4b47-b247-d5cb6870d4b9",  # Arctic Monkeys - Do I Wanna Know?
    # Electronic / Hip Hop / Modern
    "3f7a1eb1-995c-4f76-96db-b328a6f4ff7a",  # Aphex Twin - Windowlicker
    "85eb1a05-a864-42b7-a3f2-1d58544c9b9b",  # Burial - Archangel
    "a80397ee-b6ee-4dfc-b9ad-dc90e241775e",  # Massive Attack - Teardrop
    "d6beff87-5426-4fa2-bf4f-a0c5c4e9f50e",  # Portishead - Glory Box
    "b81a5392-7478-433a-a1b7-d1cb7fce1c6f",  # Kendrick Lamar - Alright
    "c4bc9f1c-7f55-4be4-a82f-2d6e32625907",  # Kanye West - Runaway
    "7e49221d-91b4-4e4b-9e46-51f6aa3c34a2",  # Billie Eilish - bad guy
    "296f86d6-f8d2-432d-96ce-63eb66ebfa48",  # Dua Lipa - Don't Start Now
    "153c9dd6-bc6f-4c5e-8fe5-2e63c0762319",  # The Weeknd - Blinding Lights
    "f69527f3-e5d8-4f81-a20c-7b561c28c865",  # Tame Impala - The Less I Know the Better
]


@dataclass
class ProbeMetric:
    mbid: str
    has_acousticbrainz: bool
    has_tag_or_genre: bool
    tag_count: int
    has_isrc: bool
    isrc_count: int
    artist_name: str = ""
    title: str = ""


@dataclass
class ProbeSummary:
    total_probed: int
    ab_coverage_pct: float
    tag_coverage_pct: float
    isrc_coverage_pct: float
    decision: str
    rationale: str


def fetch_json(url: str, cache_path: Path | None = None, delay: float = 1.1) -> dict[str, Any] | None:
    """Fetch JSON payload with local caching and polite rate limiting."""
    if cache_path and cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            pass

    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    time.sleep(delay)

    try:
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                return data  # type: ignore[no-any-return]
    except HTTPError as e:
        if e.code == 404:
            return None
        sys.stderr.write(f"HTTP error {e.code} fetching {url}\n")
    except URLError as e:
        sys.stderr.write(f"URL error fetching {url}: {e.reason}\n")
    except Exception as e:
        sys.stderr.write(f"Error fetching {url}: {e}\n")
    return None


def probe_single_mbid(mbid: str, cache_dir: Path, local_ab_dump: Path | None = None) -> ProbeMetric:
    """Probe an individual MBID against AB and MB."""
    # 1. AcousticBrainz probe
    has_ab = False
    if local_ab_dump and local_ab_dump.exists():
        # Check local structure: type/m/b/i/mbid-0.json
        if len(mbid) >= 4:
            sub = local_ab_dump / "high-level" / mbid[0] / mbid[1] / mbid[2] / f"{mbid}-0.json"
            if sub.exists():
                has_ab = True
    else:
        ab_cache = cache_dir / "ab" / f"{mbid}.json"
        ab_url = f"https://acousticbrainz.org/api/v1/{mbid}/high-level"
        ab_data = fetch_json(ab_url, ab_cache, delay=0.2)
        has_ab = ab_data is not None and len(ab_data) > 0

    # 2. MusicBrainz probe
    mb_cache = cache_dir / "mb" / f"{mbid}.json"
    mb_url = (
        f"https://musicbrainz.org/ws/2/recording/{mbid}"
        "?inc=tags+genres+artist-credits+releases+isrcs&fmt=json"
    )
    mb_data = fetch_json(mb_url, mb_cache, delay=1.05)

    tags: list[str] = []
    isrcs: list[str] = []
    title = ""
    artist_name = ""

    if mb_data:
        title = mb_data.get("title", "")
        credits = mb_data.get("artist-credit", [])
        if credits and isinstance(credits, list) and "name" in credits[0]:
            artist_name = credits[0]["name"]

        # Recording level tags and genres
        for t in mb_data.get("tags", []):
            tags.append(t.get("name", ""))
        for g in mb_data.get("genres", []):
            tags.append(g.get("name", ""))

        # Fallback to artist tags if empty
        if not tags:
            for artist_item in mb_data.get("artist-credit", []):
                art_obj = artist_item.get("artist", {})
                for t in art_obj.get("tags", []):
                    tags.append(t.get("name", ""))
                for g in art_obj.get("genres", []):
                    tags.append(g.get("name", ""))

        isrcs = mb_data.get("isrcs", [])

    return ProbeMetric(
        mbid=mbid,
        has_acousticbrainz=has_ab,
        has_tag_or_genre=len(tags) > 0,
        tag_count=len(tags),
        has_isrc=len(isrcs) > 0,
        isrc_count=len(isrcs),
        artist_name=artist_name,
        title=title,
    )


def run_probe(
    mbids: list[str],
    cache_dir: Path,
    local_ab_dump: Path | None = None,
) -> ProbeSummary:
    """Run coverage probe over MBID collection."""
    results: list[ProbeMetric] = []
    total = len(mbids)

    print(f"Starting coverage probe over {total} recordings...")
    for idx, mbid in enumerate(mbids, start=1):
        metric = probe_single_mbid(mbid, cache_dir, local_ab_dump)
        results.append(metric)
        if idx % 5 == 0 or idx == total:
            print(f"[{idx}/{total}] Probed {metric.artist_name} - {metric.title} (AB: {metric.has_acousticbrainz}, Tags: {metric.has_tag_or_genre}, ISRC: {metric.has_isrc})")

    ab_count = sum(1 for r in results if r.has_acousticbrainz)
    tag_count = sum(1 for r in results if r.has_tag_or_genre)
    isrc_count = sum(1 for r in results if r.has_isrc)

    ab_pct = round((ab_count / total) * 100, 2) if total > 0 else 0.0
    tag_pct = round((tag_count / total) * 100, 2) if total > 0 else 0.0
    isrc_pct = round((isrc_count / total) * 100, 2) if total > 0 else 0.0

    # Decision rule: Plan A proceeds only if AB coverage >= 40% and Tag coverage >= 70%
    if ab_pct >= 40.0 and tag_pct >= 70.0:
        decision = "PLAN_A"
        rationale = "AB coverage exceeds 40% and tag coverage exceeds 70%. Proceed with Plan A."
    else:
        decision = "PLAN_B_OR_MOCK"
        rationale = (
            f"Gate unmet (AB: {ab_pct}% vs 40% threshold, Tags: {tag_pct}% vs 70% threshold). "
            "AcousticBrainz 2022 shutdown severely impacts modern releases. Default to Plan B / Mock Catalog."
        )

    summary = ProbeSummary(
        total_probed=total,
        ab_coverage_pct=ab_pct,
        tag_coverage_pct=tag_pct,
        isrc_coverage_pct=isrc_pct,
        decision=decision,
        rationale=rationale,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe MusicBrainz and AcousticBrainz coverage")
    parser.add_argument("--input-file", type=Path, help="CSV or text file of MBIDs (one per line)")
    parser.add_argument("--sample-size", type=int, default=20, help="Number of recordings to probe")
    parser.add_argument("--ab-dump-path", type=Path, help="Path to unpacked local AcousticBrainz directory")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/probe"), help="Cache directory")
    parser.add_argument("--output-json", type=Path, help="Output summary file path")
    args = parser.parse_args()

    mbids = CURATED_POPULAR_MBIDS
    if args.input_file and args.input_file.exists():
        with open(args.input_file, "r", encoding="utf-8") as f:
            file_mbids = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            if file_mbids:
                mbids = file_mbids

    selected = mbids[: args.sample_size]
    summary = run_probe(selected, args.cache_dir, args.ab_dump_path)

    print("\n=== COVERAGE PROBE SUMMARY ===")
    print(f"Total Probed: {summary.total_probed}")
    print(f"AcousticBrainz Coverage: {summary.ab_coverage_pct}% (Threshold: 40%)")
    print(f"Tag/Genre Coverage:       {summary.tag_coverage_pct}% (Threshold: 70%)")
    print(f"ISRC Presence:            {summary.isrc_coverage_pct}%")
    print(f"Decision:                 {summary.decision}")
    print(f"Rationale:                {summary.rationale}")

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2)
        print(f"Wrote summary to {args.output_json}")


if __name__ == "__main__":
    main()
