"""
This is the deterministic pool which creates deterministic summaries for the firefighter for the given window
(since the last cycle). It will also read the deterministic summaries and flag for the deterministic warnings as they come in
I THINK :D
"""
import aiosqlite
from typing import Any
from datetime import datetime
import copy
import statistics

# This indexes the last time that was taken
LAST_TIME = datetime.now()

DB1_PATH = 'data/vitals.db'
DB2_PATH = 'data/vitals2.db'
DB3_PATH = 'data/vitals3.db'

FF_DB = {1: DB1_PATH, 2: DB2_PATH, 3: DB3_PATH}

# The CSV pools for each of the data types
FILES = {
    "ALL_LOG": '*',
    "ELEVATION": 'elevation',
    "HR":'hr',
    "O2": 'o2',
    "TEMP" :'temp',
    "RESPIRATION": 'respiration',
    "HRV": 'hrv',
    "BODY_TEMP": 'body_temp',
    "GAIT": 'gait'
}

# THIS IS WHAT THE GET_DATA WILL OUTPUT ON EVERY SINGLE THING
FORMAT = {
    "ELEVATION": {"min": None, "max": None, "range": None, "mean": None},
    "HR": {"min": None, "max": None, "range": None, "mean": None, "median": None, "variance": None, "diff": None},
    "O2": {"min": None, "max": None, "range": None, "mean": None, "median": None, "variance": None, "diff": None},
    "TEMP": {"min": None, "max": None, "range": None, "mean": None, "median": None, "diff": None},
    "RESPIRATION": {"min": None, "max": None, "range": None, "mean": None, "median": None, "variance": None, "diff": None},
    "HRV": {"min": None, "max": None, "range": None, "mean": None, "median": None, "variance": None, "diff": None},
    "BODY_TEMP": {"min": None, "max": None, "range": None, "mean": None, "median": None, "diff": None},
    "GAIT": {"min": None, "max": None, "range": None, "mean": None, "median": None, "variance": None, "diff": None}
}

async def get_data(ff: int) -> dict[str, dict[str, int|float]]:
    """
    Takes all the data from the last cycle and creates all the deterministic summaries for each category of variable. 
    """
    global LAST_TIME
    l = LAST_TIME.isoformat() if isinstance(LAST_TIME, datetime) else str(LAST_TIME)

    DB_PATH = FF_DB[ff]
    result = copy.deepcopy(FORMAT)

    async with aiosqlite.connect(DB_PATH) as db:
        for f, col in FILES.items():
            if f not in result:
                continue

            query = f"""
                SELECT {col} FROM all_logs
                WHERE time >= ? AND {col} IS NOT NULL
                ORDER BY time ASC
            """
            async with db.execute(query, (l)) as cursor:
                rows = await cursor.fetchall()

            values = [r[0] for r in rows]
            if not values:
                continue # No data in cycle?
            mn, mx = min(values), max(values)
            stats = result[f]

            # Filling in all the values in the inner dictionary for each value
            stats["min"] = mn
            stats["max"] = mx
            stats["range"] = mx - mn
            stats["mean"] = statistics.mean(values)
            if "median" in stats:
                stats["median"] = statistics.median(values)
            if "variance" in stats:
                stats["variance"] = statistics.stdev(values)
            if "diff" in stats:
                stats["diff"] = values[len(values) - 1] - values[0]

        # Update the LAST_TIME variable
        LAST_TIME = datetime.now()
        return result

