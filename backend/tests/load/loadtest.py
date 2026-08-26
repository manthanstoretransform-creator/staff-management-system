"""
Backend load test: simulate N concurrent Monitra users against the API.

WHY THIS EXISTS
---------------
The desktop soak (desktop/tests/soak/) proved ONE client survives the operation
rate 200 users would generate. It says nothing about whether the backend
survives 200 clients. This harness answers that separately, and honestly.

WHAT IT MEASURES
----------------
  * throughput (requests/second, completed operations/second)
  * latency percentiles per endpoint (p50 / p95 / p99 / max)
  * error rate, broken down by HTTP status and by exception class
  * PostgreSQL connection count sampled from pg_stat_activity during the run
  * where it breaks first (the summary ranks endpoints by p95 and by error rate)

TWO SAFETY RULES, BOTH DELIBERATE
---------------------------------
1. It never calls POST /auth/login. That endpoint proxies credentials to an
   external WordPress provider (settings.EXTERNAL_AUTH_BASE_URL). Driving it at
   200 concurrent would be a denial-of-service against a third party's server.
   Instead we mint the same JWT the backend would issue, locally, using
   app.core.security.create_access_token. The token is identical from
   get_current_user's point of view, so every authenticated code path is
   exercised for real -- only the external round trip is skipped.

2. It refuses to run against a host that looks like production unless you pass
   --i-understand-this-is-production. Load tests write real rows.

USAGE
-----
    # 1. Point at a local server (safest; start it first):
    uvicorn app.main:app --port 8000 --workers 4

    # 2. Discover real user/project/task ids to drive traffic with:
    python tests/load/loadtest.py --discover

    # 3. Run:
    python tests/load/loadtest.py --users 200 --duration 120 \
        --base-url http://127.0.0.1:8000

Run it against a staging deployment that mirrors production topology to get a
number you can actually trust; localhost measures the application, not the
serverless + pooler behaviour that will decide the real answer.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

try:
    import httpx
except ImportError:  # pragma: no cover - guarded for a clearer message
    sys.exit("httpx is required: pip install httpx")


PRODUCTION_HINTS = ("vercel.app", "https://", "api.monitra", "prod")


# --------------------------------------------------------------------------
# Result collection
# --------------------------------------------------------------------------

@dataclass
class Sample:
    endpoint: str
    status: int
    duration_ms: float
    error: Optional[str] = None


@dataclass
class Results:
    samples: List[Sample] = field(default_factory=list)
    started_at: float = 0.0
    ended_at: float = 0.0
    db_connection_samples: List[Tuple[float, int, int]] = field(default_factory=list)

    def add(self, sample: Sample) -> None:
        self.samples.append(sample)

    @property
    def wall_seconds(self) -> float:
        return max(1e-9, self.ended_at - self.started_at)


def percentile(values: List[float], pct: float) -> float:
    """Nearest-rank percentile. Deliberately not interpolated -- for latency we
    want a value that an actual request really experienced."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, int(round(pct / 100.0 * len(ordered))))
    return ordered[min(rank, len(ordered)) - 1]


# --------------------------------------------------------------------------
# Auth: mint tokens locally, never touch the external provider
# --------------------------------------------------------------------------

def mint_token(user_id: int, minutes: int = 120) -> str:
    from app.core.security import create_access_token

    return create_access_token({"user_id": user_id}, expires_delta=timedelta(minutes=minutes))


# --------------------------------------------------------------------------
# Fixture discovery -- read real ids straight from the database
# --------------------------------------------------------------------------

def discover_fixtures(limit_users: int = 200) -> Dict[str, Any]:
    """Read ids of real, active rows so generated traffic hits populated code
    paths rather than 404 handlers (which are misleadingly fast)."""
    from sqlalchemy import text

    from app.core.database import get_engine

    engine = get_engine()
    out: Dict[str, Any] = {"users": [], "projects": [], "tasks": []}
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id FROM users WHERE is_active = true ORDER BY id LIMIT :n"),
            {"n": limit_users},
        ).fetchall()
        out["users"] = [r[0] for r in rows]

        rows = conn.execute(text("SELECT id FROM projects ORDER BY id LIMIT 50")).fetchall()
        out["projects"] = [r[0] for r in rows]

        if out["projects"]:
            rows = conn.execute(
                text("SELECT id, project_id FROM tasks ORDER BY id LIMIT 200")
            ).fetchall()
            out["tasks"] = [{"id": r[0], "project_id": r[1]} for r in rows]
    return out


async def sample_db_connections(results: Results, interval: float, stop: asyncio.Event) -> None:
    """Sample pg_stat_activity while load is running.

    This is the measurement that answers the pool_size=5 / max_overflow=10
    question: how many connections does the backend actually hold open, and how
    close does it get to the server's max_connections.
    """
    from sqlalchemy import text

    from app.core.database import get_engine

    try:
        engine = get_engine()
    except Exception as exc:  # noqa: BLE001 - reported, never fatal
        print(f"  (db sampling unavailable: {exc})")
        return

    while not stop.is_set():
        try:
            with engine.connect() as conn:
                total = conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                ).scalar_one()
                active = conn.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND state = 'active'"
                    )
                ).scalar_one()
            results.db_connection_samples.append((time.monotonic(), int(total), int(active)))
        except Exception:  # noqa: BLE001 - sampling must never kill the run
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


# --------------------------------------------------------------------------
# The simulated user
# --------------------------------------------------------------------------

class VirtualUser:
    """One desktop client's realistic traffic pattern.

    Weights mirror what the desktop actually does: it polls far more often than
    it mutates, and every timer start is eventually followed by a stop.
    """

    def __init__(self, client: httpx.AsyncClient, user_id: int,
                 fixtures: Dict[str, Any], results: Results, think_time: float):
        self.client = client
        self.user_id = user_id
        self.fixtures = fixtures
        self.results = results
        self.think_time = think_time
        self.headers = {"Authorization": f"Bearer {mint_token(user_id)}"}
        self.open_entry_id: Optional[int] = None

    async def _call(self, method: str, path: str, label: str,
                    **kwargs: Any) -> Optional[httpx.Response]:
        start = time.perf_counter()
        try:
            response = await self.client.request(
                method, path, headers=self.headers, **kwargs
            )
        except Exception as exc:  # noqa: BLE001 - connection errors ARE the result
            self.results.add(Sample(label, 0, (time.perf_counter() - start) * 1000,
                                    error=type(exc).__name__))
            return None
        self.results.add(Sample(label, response.status_code,
                                (time.perf_counter() - start) * 1000))
        return response

    async def run(self, stop: asyncio.Event) -> None:
        # Stagger arrivals so 200 users do not issue their first request on the
        # same tick -- a thundering herd measures the herd, not the server.
        await asyncio.sleep(random.random() * self.think_time)
        while not stop.is_set():
            try:
                await self.one_iteration()
            except Exception as exc:  # noqa: BLE001
                self.results.add(Sample("__scenario__", 0, 0.0, error=type(exc).__name__))
            await asyncio.sleep(self.think_time * (0.5 + random.random()))

    async def one_iteration(self) -> None:
        roll = random.random()
        if roll < 0.30:
            await self._call("GET", "/projects", "GET /projects")
        elif roll < 0.55:
            project = self._random_project()
            if project is not None:
                await self._call("GET", f"/projects/{project}/tasks",
                                 "GET /projects/{id}/tasks")
        elif roll < 0.65:
            await self._call("GET", "/auth/me", "GET /auth/me")
        elif roll < 0.75:
            await self._call("GET", "/time-entries", "GET /time-entries",
                             params={"limit": 20})
        elif roll < 0.90:
            await self._timer_cycle()
        else:
            await self._app_usage_batch()

    def _random_project(self) -> Optional[int]:
        projects = self.fixtures.get("projects") or []
        return random.choice(projects) if projects else None

    def _random_task(self) -> Optional[Dict[str, Any]]:
        tasks = self.fixtures.get("tasks") or []
        return random.choice(tasks) if tasks else None

    async def _timer_cycle(self) -> None:
        """Start a timer, then stop it. Never leaves an entry open at exit --
        an orphaned running entry would poison later runs."""
        if self.open_entry_id is not None:
            response = await self._call(
                "POST", f"/time-entries/{self.open_entry_id}/stop",
                "POST /time-entries/{id}/stop",
                json={"description": "load test"},  # TimeEntryStop schema
            )
            if response is not None and response.status_code < 500:
                self.open_entry_id = None
            return

        task = self._random_task()
        if task is None:
            return
        response = await self._call(
            "POST", "/time-entries/start", "POST /time-entries/start",
            json={  # TimeEntryStart: the server stamps start_time itself
                "project_id": task["project_id"],
                "task_id": task["id"],
                "is_billable": True,
            },
        )
        if response is not None and response.status_code in (200, 201):
            try:
                self.open_entry_id = response.json().get("id")
            except Exception:  # noqa: BLE001
                self.open_entry_id = None

    async def _app_usage_batch(self) -> None:
        if self.open_entry_id is None:
            return
        now = datetime.now(timezone.utc)
        payload = {  # AppUsageBatchCreate: {"records": [AppUsageCreate, ...]}
            "records": [
                {
                    "application_name": random.choice(
                        ["Code.exe", "chrome.exe", "slack.exe", "Teams.exe"]
                    ),
                    "window_title": "load-test",
                    "duration_seconds": 60,
                    "recorded_at": (now - timedelta(seconds=60 * index)).isoformat(),
                }
                for index in range(5)
            ]
        }
        await self._call(
            "POST", f"/time-entries/{self.open_entry_id}/app-usage/batch",
            "POST /time-entries/{id}/app-usage/batch", json=payload,
        )

    async def cleanup(self) -> None:
        if self.open_entry_id is not None:
            try:
                await self.client.post(
                    f"/time-entries/{self.open_entry_id}/stop",
                    headers=self.headers,
                    json={"description": "load test cleanup"},
                )
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

async def run_load(args: argparse.Namespace, fixtures: Dict[str, Any]) -> Results:
    results = Results()
    user_pool: List[int] = fixtures.get("users") or []
    if not user_pool:
        sys.exit("No users discovered. Run with --discover first, or seed the database.")

    # Reuse ids cyclically if fewer real users exist than virtual users.
    assigned = [user_pool[i % len(user_pool)] for i in range(args.users)]
    if len(user_pool) < args.users:
        print(f"  NOTE: only {len(user_pool)} real users; ids reused to reach "
              f"{args.users} concurrent clients. Per-user row contention will be "
              f"higher than production.")

    limits = httpx.Limits(max_connections=args.users * 2,
                          max_keepalive_connections=args.users)
    timeout = httpx.Timeout(connect=10.0, read=args.request_timeout,
                            write=10.0, pool=30.0)

    stop = asyncio.Event()
    async with httpx.AsyncClient(base_url=args.base_url, limits=limits,
                                 timeout=timeout) as client:
        users = [VirtualUser(client, uid, fixtures, results, args.think_time)
                 for uid in assigned]

        sampler = None
        if args.sample_db:
            sampler = asyncio.create_task(sample_db_connections(results, 2.0, stop))

        print(f"  ramping {args.users} users over {args.ramp}s, "
              f"holding for {args.duration}s...")
        results.started_at = time.monotonic()

        tasks = []
        ramp_delay = args.ramp / max(1, args.users)
        for index, user in enumerate(users):
            tasks.append(asyncio.create_task(_delayed_start(user, index * ramp_delay, stop)))

        await asyncio.sleep(args.ramp + args.duration)
        stop.set()
        results.ended_at = time.monotonic()

        await asyncio.gather(*tasks, return_exceptions=True)
        if sampler is not None:
            await sampler
        print("  draining open time entries...")
        await asyncio.gather(*(u.cleanup() for u in users), return_exceptions=True)

    return results


async def _delayed_start(user: VirtualUser, delay: float, stop: asyncio.Event) -> None:
    await asyncio.sleep(delay)
    if not stop.is_set():
        await user.run(stop)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def report(results: Results, args: argparse.Namespace) -> bool:
    by_endpoint: Dict[str, List[Sample]] = defaultdict(list)
    for sample in results.samples:
        by_endpoint[sample.endpoint].append(sample)

    total = len(results.samples)
    if total == 0:
        print("\nNo requests recorded -- is the server running at "
              f"{args.base_url}?")
        return False

    errors = [s for s in results.samples if s.error or s.status >= 400]
    error_rate = len(errors) / total * 100.0
    rps = total / results.wall_seconds

    print("\n" + "=" * 78)
    print(f"BACKEND LOAD TEST  |  {args.users} concurrent users  |  {args.base_url}")
    print("=" * 78)
    print(f"duration      {results.wall_seconds:.1f}s")
    print(f"requests      {total}  ({rps:.1f} req/s)")
    print(f"errors        {len(errors)}  ({error_rate:.2f}%)")

    print("\nPER-ENDPOINT LATENCY (ms)")
    print(f"{'endpoint':<42}{'n':>7}{'p50':>8}{'p95':>9}{'p99':>9}{'max':>9}{'err%':>7}")
    print("-" * 78)
    rows = []
    for endpoint, samples in sorted(by_endpoint.items()):
        durations = [s.duration_ms for s in samples if not s.error]
        endpoint_errors = [s for s in samples if s.error or s.status >= 400]
        err_pct = len(endpoint_errors) / len(samples) * 100.0
        p95 = percentile(durations, 95)
        rows.append((endpoint, p95, err_pct))
        print(f"{endpoint:<42}{len(samples):>7}"
              f"{percentile(durations, 50):>8.0f}{p95:>9.0f}"
              f"{percentile(durations, 99):>9.0f}"
              f"{(max(durations) if durations else 0):>9.0f}{err_pct:>7.1f}")

    status_counts = Counter(s.status for s in results.samples if not s.error)
    exception_counts = Counter(s.error for s in results.samples if s.error)
    print("\nSTATUS CODES   " + ", ".join(
        f"{code}: {count}" for code, count in sorted(status_counts.items())))
    if exception_counts:
        print("EXCEPTIONS     " + ", ".join(
            f"{name}: {count}" for name, count in exception_counts.most_common()))

    if results.db_connection_samples:
        totals = [t for _, t, _ in results.db_connection_samples]
        actives = [a for _, _, a in results.db_connection_samples]
        print(f"\nDB CONNECTIONS total min/mean/max "
              f"{min(totals)}/{statistics.mean(totals):.1f}/{max(totals)}   "
              f"active max {max(actives)}")

    print("\nBOTTLENECKS (slowest by p95)")
    for endpoint, p95, err_pct in sorted(rows, key=lambda r: -r[1])[:3]:
        print(f"  {endpoint:<42} p95 {p95:>7.0f}ms   errors {err_pct:.1f}%")

    passed = error_rate <= args.max_error_rate and \
        percentile([s.duration_ms for s in results.samples if not s.error], 95) <= args.max_p95_ms
    print("\n" + ("PASS" if passed else "FAIL") +
          f": error rate {error_rate:.2f}% (limit {args.max_error_rate}%), "
          f"overall p95 "
          f"{percentile([s.duration_ms for s in results.samples if not s.error], 95):.0f}ms "
          f"(limit {args.max_p95_ms}ms)")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump({
                "users": args.users,
                "base_url": args.base_url,
                "duration_s": results.wall_seconds,
                "requests": total,
                "rps": rps,
                "error_rate_pct": error_rate,
                "endpoints": {
                    endpoint: {
                        "n": len(samples),
                        "p50": percentile([s.duration_ms for s in samples if not s.error], 50),
                        "p95": percentile([s.duration_ms for s in samples if not s.error], 95),
                        "p99": percentile([s.duration_ms for s in samples if not s.error], 99),
                    } for endpoint, samples in by_endpoint.items()
                },
                "db_connections_max": max(
                    (t for _, t, _ in results.db_connection_samples), default=None),
                "passed": passed,
            }, handle, indent=2)
        print(f"\nwrote {args.json_out}")
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=200)
    parser.add_argument("--duration", type=int, default=120,
                        help="seconds to hold at full concurrency")
    parser.add_argument("--ramp", type=int, default=30,
                        help="seconds to ramp users in")
    parser.add_argument("--think-time", type=float, default=3.0,
                        help="mean seconds a client waits between operations")
    parser.add_argument("--request-timeout", type=float, default=30.0)
    parser.add_argument("--max-error-rate", type=float, default=1.0)
    parser.add_argument("--max-p95-ms", type=float, default=1500.0)
    parser.add_argument("--sample-db", action="store_true",
                        help="sample pg_stat_activity during the run")
    parser.add_argument("--discover", action="store_true",
                        help="print discoverable fixture ids and exit")
    parser.add_argument("--fixtures", help="path to a JSON fixtures file")
    parser.add_argument("--json-out", help="write machine-readable results here")
    parser.add_argument("--i-understand-this-is-production", action="store_true")
    args = parser.parse_args()

    if args.discover:
        found = discover_fixtures()
        print(json.dumps({k: (v[:10] if isinstance(v, list) else v)
                          for k, v in found.items()}, indent=2))
        print(f"\nusers={len(found['users'])} projects={len(found['projects'])} "
              f"tasks={len(found['tasks'])}")
        return 0

    looks_production = any(hint in args.base_url for hint in PRODUCTION_HINTS)
    if looks_production and not args.i_understand_this_is_production:
        print(f"REFUSING: {args.base_url} looks like a deployed environment.\n"
              "A load test writes real rows and consumes real database "
              "connections.\nRe-run with --i-understand-this-is-production if "
              "that is genuinely what you want.")
        return 2

    if args.fixtures:
        with open(args.fixtures, encoding="utf-8") as handle:
            fixtures = json.load(handle)
    else:
        print("discovering fixtures from the database...")
        fixtures = discover_fixtures()
        print(f"  users={len(fixtures['users'])} projects={len(fixtures['projects'])} "
              f"tasks={len(fixtures['tasks'])}")

    results = asyncio.run(run_load(args, fixtures))
    return 0 if report(results, args) else 1


if __name__ == "__main__":
    raise SystemExit(main())
