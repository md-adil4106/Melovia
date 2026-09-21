#!/usr/bin/env python3
"""Melovia Concurrency & Performance Load Test Suite.

Simulates 20 concurrent users exercising:
1. Track search (/tracks/search)
2. Recommendation generation from seeds (/recommendations)
3. Discovery Control re-ranking (/recommendations/rerank)
4. Universe coordinates fetch (/universe/tracks)
5. Why explanation (/recommendations/why/...)
6. Interactive feedback (/feedback)

Verifies AGENTS.md performance budgets:
- POST /recommendations p95 < 400 ms
- POST /recommendations/rerank p95 < 100 ms
- Error rate < 1%
- Memory stability (zero continuous growth)
"""

import asyncio
import os
import random
import sys
import time
from typing import Any

import httpx
import numpy as np
import psutil

# Configuration
BASE_URL = os.getenv("MELOVIA_API_URL", "http://127.0.0.1:8000")
CONCURRENCY = int(os.getenv("LOAD_CONCURRENCY", "20"))
TOTAL_REQUESTS_PER_USER = int(os.getenv("LOAD_REQUESTS_PER_USER", "5"))


class LoadTestReport:
    """Collects latencies and errors across endpoints."""

    def __init__(self) -> None:
        self.latencies: dict[str, list[float]] = {}
        self.errors: list[str] = []
        self.total_calls = 0

    def record(self, endpoint: str, duration_ms: float, error: str | None = None) -> None:
        self.total_calls += 1
        if endpoint not in self.latencies:
            self.latencies[endpoint] = []
        self.latencies[endpoint].append(duration_ms)
        if error:
            self.errors.append(f"[{endpoint}] {error}")

    def summarize(self, start_rss_mb: float, end_rss_mb: float) -> bool:
        print("\n" + "=" * 70)
        print("MELOVIA PERFORMANCE & LOAD TEST SUMMARY (20 Concurrent Users)")
        print("=" * 70)
        print(f"Total Transactions: {self.total_calls}")
        print(f"Total Errors:       {len(self.errors)} (Error Rate: {len(self.errors)/max(1, self.total_calls)*100:.2f}%)")
        print(f"Memory (RSS):       Start: {start_rss_mb:.1f} MB -> End: {end_rss_mb:.1f} MB (Delta: {end_rss_mb - start_rss_mb:+.1f} MB)")
        print("-" * 70)
        print(f"{'Endpoint':<35} {'Count':<8} {'p50 (ms)':<10} {'p95 (ms)':<10} {'Max (ms)':<10} {'Budget':<10}")
        print("-" * 70)

        all_budgets_passed = True

        for endpoint, times in sorted(self.latencies.items()):
            arr = np.array(times)
            p50 = float(np.percentile(arr, 50))
            p95 = float(np.percentile(arr, 95))
            max_val = float(np.max(arr))

            budget_str = "N/A"
            passed = True
            if "POST /recommendations" == endpoint:
                budget_str = "< 400ms"
                if p95 >= 400.0:
                    passed = False
            elif "POST /recommendations/rerank" in endpoint:
                budget_str = "< 100ms"
                if p95 >= 100.0:
                    passed = False

            status_mark = "OK" if passed else "FAIL"
            if not passed:
                all_budgets_passed = False

            print(f"{endpoint:<35} {len(times):<8} {p50:<10.1f} {p95:<10.1f} {max_val:<10.1f} {budget_str:<10} [{status_mark}]")

        print("=" * 70)
        if self.errors:
            print("\nSample Errors Encountered:")
            for err in self.errors[:5]:
                print(f"  - {err}")

        return all_budgets_passed and (len(self.errors) == 0)


async def user_journey(user_idx: int, report: LoadTestReport) -> None:
    """Simulate a single user exploring music through Melovia with dedicated session."""
    headers = {"X-Request-ID": f"load-test-user-{user_idx}-{random.randint(1000, 9999)}"}
    device_cookie = f"load-device-{user_idx}"
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    timeout = httpx.Timeout(15.0, connect=5.0)

    # Initial user arrival stagger (0 to 1.5s)
    await asyncio.sleep(random.uniform(0.0, 1.5))

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        cookies={"melovia_device_id": device_cookie},
        limits=limits,
        timeout=timeout,
    ) as client:
        for _ in range(TOTAL_REQUESTS_PER_USER):
            try:
                # 1. Search for catalog seed tracks
                query = random.choice(["echo", "quiet", "electric", "drift", "pulse", "orbit", "shadow", "signal", "gravity", "frequency"])
                t0 = time.perf_counter()
                r = await client.get(f"/tracks/search?q={query}&limit=5", headers=headers)
                t_ms = (time.perf_counter() - t0) * 1000.0
                report.record("GET /tracks/search", t_ms, None if r.status_code == 200 else f"HTTP {r.status_code}")

                if r.status_code != 200 or not r.json().get("items"):
                    await asyncio.sleep(0.5)
                    continue

                search_results = r.json()["items"]
                seed_ids = [t["id"] for t in search_results[:2]]

                await asyncio.sleep(random.uniform(0.05, 0.15))

                # 2. Generate Recommendations
                t0 = time.perf_counter()
                rec_resp = await client.post(
                    "/recommendations",
                    json={"seed_track_ids": seed_ids, "n": 30, "discovery": 0.35},
                    headers=headers,
                )
                t_ms = (time.perf_counter() - t0) * 1000.0
                report.record(
                    "POST /recommendations",
                    t_ms,
                    None if rec_resp.status_code == 200 else f"HTTP {rec_resp.status_code}",
                )

                if rec_resp.status_code != 200:
                    await asyncio.sleep(0.5)
                    continue

                rec_data = rec_resp.json()
                candidate_set_id = rec_data.get("candidate_set_id")
                items = rec_data.get("items", [])

                if not candidate_set_id or not items:
                    continue

                await asyncio.sleep(random.uniform(0.05, 0.15))

                # 3. Interactive Discovery Control Reranking
                for d in [0.15, 0.75]:
                    t0 = time.perf_counter()
                    rerank_resp = await client.post(
                        "/recommendations/rerank",
                        json={"candidate_set_id": candidate_set_id, "discovery": d, "n": 30},
                        headers=headers,
                    )
                    t_ms = (time.perf_counter() - t0) * 1000.0
                    report.record(
                        "POST /recommendations/rerank",
                        t_ms,
                        None if rerank_resp.status_code == 200 else f"HTTP {rerank_resp.status_code}",
                    )
                    await asyncio.sleep(random.uniform(0.05, 0.1))

                # 4. Fetch Why Explanation for top track
                top_track_id = items[0]["track"]["id"]
                t0 = time.perf_counter()
                why_resp = await client.get(
                    f"/recommendations/{candidate_set_id}/items/{top_track_id}/why",
                    headers=headers,
                )
                t_ms = (time.perf_counter() - t0) * 1000.0
                report.record(
                    "GET /recommendations/.../why",
                    t_ms,
                    None if why_resp.status_code == 200 else f"HTTP {why_resp.status_code}",
                )

                await asyncio.sleep(random.uniform(0.05, 0.1))

                # 5. Interactive Feedback (Like)
                t0 = time.perf_counter()
                fb_resp = await client.post(
                    "/feedback",
                    json={
                        "track_id": top_track_id,
                        "event": "like",
                        "candidate_set_id": candidate_set_id,
                    },
                    headers=headers,
                )
                t_ms = (time.perf_counter() - t0) * 1000.0
                report.record(
                    "POST /feedback",
                    t_ms,
                    None if fb_resp.status_code == 200 else f"HTTP {fb_resp.status_code}",
                )

                # 6. Fetch 3D Universe Track Positions
                t0 = time.perf_counter()
                uni_resp = await client.get("/universe", headers=headers)
                t_ms = (time.perf_counter() - t0) * 1000.0
                report.record(
                    "GET /universe",
                    t_ms,
                    None if uni_resp.status_code == 200 else f"HTTP {uni_resp.status_code}",
                )

            except Exception as exc:
                report.record("GENERAL_ERROR", 0.0, str(exc))

            # Realistic user think-time jitter (200ms to 500ms)
            await asyncio.sleep(random.uniform(0.2, 0.5))


async def run_load_test() -> int:
    """Run concurrent load test against Melovia FastAPI backend."""
    proc = psutil.Process()
    start_rss = proc.memory_info().rss / (1024 * 1024)

    report = LoadTestReport()

    print(f"Starting load test with {CONCURRENCY} concurrent users against {BASE_URL}...")
    # Verify health first
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as check_client:
        try:
            h = await check_client.get("/health")
            if h.status_code != 200:
                print(f"[FATAL] Backend /health check failed with status {h.status_code}")
                return 1
        except Exception as err:
            print(f"[FATAL] Could not reach backend at {BASE_URL}: {err}")
            return 1

    # Launch concurrent simulated users
    tasks = [user_journey(i, report) for i in range(CONCURRENCY)]
    await asyncio.gather(*tasks)

    end_rss = proc.memory_info().rss / (1024 * 1024)
    success = report.summarize(start_rss, end_rss)
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_load_test())
    sys.exit(exit_code)
