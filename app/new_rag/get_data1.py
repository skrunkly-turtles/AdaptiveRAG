"""
Deterministic per-window summaries for each firefighter, sent to worker agents.

Changes from the original:
- No more module-level LAST_TIME global. `since` is now a required argument.
  The caller (your polling loop) owns per-ff timing, not this module. This
  removes the ff1/ff2/ff3 desync bug that depended on call order, and makes
  the function callable identically twice on identical input -- which Test 6
  (consistency) needs to even be well-defined.
- The arithmetic is split into compute_stats(), a pure function with no DB,
  no clock, no globals. get_data() is now a thin wrapper: fetch rows, hand
  the raw list to compute_stats(), filter down to each metric's declared keys.
  compute_stats() is what Test 1 and Test 5 call directly.
- missing_frac / n are now real numbers, computed against the true row count
  in the window (a separate COUNT(*) query), not silently dropped.
"""
import aiosqlite
import statistics
from datetime import datetime

DB1_PATH = 'data/vitals.db'
DB2_PATH = 'data/vitals2.db'
DB3_PATH = 'data/vitals3.db'

FF_DB = {1: DB1_PATH, 2: DB2_PATH, 3: DB3_PATH}

FILES = {
    "ELEVATION": 'elevation',
    "HR": 'hr',
    "O2": 'o2',
    "TEMP": 'temp',
    "RESPIRATION": 'respiration',
    "HRV": 'hrv',
    "BODY_TEMP": 'body_temp',
    "GAIT": 'gait',
}

# Which stats each metric reports. compute_stats() always computes everything;
# get_data() filters down to this set per metric, so the output shape is
# unchanged from before.
FORMAT = {
    "ELEVATION": {"min", "max", "range", "mean"},
    "HR": {"min", "max", "range", "mean", "median", "variance", "diff"},
    "O2": {"min", "max", "range", "mean", "median", "variance", "diff"},
    "TEMP": {"min", "max", "range", "mean", "median", "diff"},
    "RESPIRATION": {"min", "max", "range", "mean", "median", "variance", "diff"},
    "HRV": {"min", "max", "range", "mean", "median", "variance", "diff"},
    "BODY_TEMP": {"min", "max", "range", "mean", "median", "diff"},
    "GAIT": {"min", "max", "range", "mean", "median", "variance", "diff"},
}


def compute_stats(values: list, expected_n: int | None = None) -> dict:
    """
    Pure digest computation. No I/O, no globals, no clock -- this is the
    function Tests 1, 5, and 6 call directly with hand-built lists.

    values:      readings for this metric in the window (None entries allowed
                 and treated as missing).
    expected_n:  total rows in the window (across all metrics), used to compute
                 missing_frac. Defaults to len(values) if not given, i.e.
                 "nothing outside this list was possible."
    """
    present = [v for v in values if v is not None]
    n = len(present)
    total = expected_n if expected_n is not None else len(values)
    missing_frac = round(1 - (n / total), 3) if total else 0.0

    if n == 0:
        return {
            "n": 0, "missing_frac": missing_frac,
            "min": None, "max": None, "range": None,
            "mean": None, "median": None, "variance": None, "diff": None,
        }

    mn, mx = min(present), max(present)
    result = {
        "n": n,
        "missing_frac": missing_frac,
        "min": mn,
        "max": mx,
        "range": round(mx - mn, 2),
        "mean": round(statistics.mean(present), 2),
        "median": round(statistics.median(present), 2),
        "diff": round(present[-1] - present[0], 2),
    }
    result["variance"] = round(statistics.stdev(present), 2) if n > 1 else 0.0
    return result


async def get_data(ff: int, since: datetime) -> dict[str, dict[str, int | float | None]]:
    """
    Fetch this firefighter's readings since `since` and return per-metric
    digests. `since` is required -- the caller decides the window, this
    function has no memory of its own between calls.
    """
    since_str = since.isoformat() if isinstance(since, datetime) else str(since)
    db_path = FF_DB[ff]
    result = {}

    async with aiosqlite.connect(db_path) as db:
        # Total rows in the window, regardless of which columns are NULL --
        # this is the denominator for missing_frac.
        async with db.execute(
            "SELECT COUNT(*) FROM all_logs WHERE time >= ?", (since_str,)
        ) as cursor:
            row = await cursor.fetchone()
            total_rows = row[0] if row else 0

        for metric, col in FILES.items():
            query = f"""
                SELECT {col} FROM all_logs
                WHERE time >= ? AND {col} IS NOT NULL
                ORDER BY time ASC
            """
            async with db.execute(query, (since_str,)) as cursor:
                rows = await cursor.fetchall()

            values = [r[0] for r in rows]
            stats = compute_stats(values, expected_n=total_rows)
            result[metric] = {k: stats.get(k) for k in FORMAT[metric]}

    return result