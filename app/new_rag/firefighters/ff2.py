"""
This is the temporary firefighter file that is going to help me LOl
The new firefighters will need to do the following:
(1) Read and dynamically adjust the system prompts 
(2) Retrieve information as needed
(3) 
"""
from datetime import datetime
import sqlite3
import asyncio
import math
import json
from models1 import Adjust, Warn, Data
import ollama
from typing import Any
from get_data1 import get_data
from memory_manager import memory
from comms import warning_queue

CYCLE = 10

TRENDLINE = {
    "time": [],
    "hr": [],
    "o2": [],
    "elevation": [],
    "temp": [],
    "respiration": [],
    "hrv": [],
    "body_temp": [],
    "gait": []
}

DB1_PATH = 'data/vitals2.db'
client = ollama.AsyncClient()
FF_ID = 2

ATTEND_TO = []

DET_WARNINGS = {
    "hr": [40, 230],
    "o2": [93, 100],
    "temp": [10, 30],
    "respiration": [12, 25],
    "hrv": [40, 200],
    "body_temp": [36.7, 37.2],
    "gait": [0, 1.5]
}

SYS_PROMPT = f""" You are an analytical agent for {FF_ID}. Make sure you identify whose agent you are.
                    The data you receive is in the context of a fire rescue, with your worker being a firefighter.
                    Given the summaries from the past cycle, the cache of summaries from the past history, 
                    write a general report of the state and wellbeing of the worker. Keep in mind the deterministic
                    warnings, which indicate the normal ranges for each cateogory. 

                    You MUST keep your summary LESS THAN 4 sentences.
            """

# Tracks this worker's own last-read time. Only ever touched by this module
# for this one ff, so (unlike the old get_data1.py global) there's no
# cross-firefighter desync risk. check_data() still lets you override it
# explicitly for tests.
LAST_CHECK = datetime.now()


async def adjust(params: Adjust, cycle: int) -> None:
    """
    Adjust the prompt for the firefighter before it goes to scan the dataset.
    """
    global CYCLE
    CYCLE = cycle

    global ATTEND_TO
    ATTEND_TO = params.attention

    global DET_WARNINGS
    for w in params.det_numbers:
        if w not in DET_WARNINGS:
            raise ValueError(f"{w} not a category of data bruh")
        DET_WARNINGS[w] = params.det_numbers[w]


async def check_data(since: datetime | None = None) -> str:
    """
    Reads the data by the LLM depending on the det_warnings, the attend_to.

    since: optional override for the window start. Defaults to this worker's
    own LAST_CHECK. Passing it explicitly lets tests call this with a fixed
    window instead of depending on wall-clock state.
    """
    global TRENDLINE, LAST_CHECK

    window_start = since if since is not None else LAST_CHECK
    curr_data = await get_data(FF_ID, window_start)
    LAST_CHECK = datetime.now()

    tl_data = {c: curr_data[c]["mean"] for c in curr_data}

    await trendline(tl_data)

    response = await client.generate(model='qwen2.5:14b',
            system=SYS_PROMPT,
            prompt=f"""Deterministic warnings: {DET_WARNINGS} \n
                        Pay special attention to: {ATTEND_TO} \n 
                        Current Data: {curr_data} \n 
                        Trendline: {TRENDLINE}
            """,
        )
    print(response['response'])
    memory.firefighter_summary[FF_ID] = response['response']
    return response['response']


async def read_live_data() -> None:
    """
    Reads new live vitals entries as they arrive for deterministic warning checks.
    """
    conn = sqlite3.connect(
        f"file:{DB1_PATH}?mode=ro",
        uri=True,
        timeout=10.0,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row

    def get_max_rowid():
        row = conn.execute("SELECT MAX(rowid) FROM all_logs").fetchone()
        return row[0] if row and row[0] else 0

    last_processed_id = await asyncio.to_thread(get_max_rowid)

    try:
        while True:
            def fetch_new_rows():
                return conn.execute(
                    "SELECT rowid, * FROM all_logs WHERE rowid > ? ORDER BY rowid ASC",
                    (last_processed_id,)
                ).fetchall()

            rows = await asyncio.to_thread(fetch_new_rows)

            for row in rows:
                Data.model_validate(dict(row))
                last_processed_id = row["rowid"]
                await check_det_warn(dict(row))

            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass
    finally:
        conn.close()


def evaluate_guards(reading: dict, thresholds: dict) -> dict:
    """
    Pure guard predicate: given one reading and the threshold table, return
    which fields are out of bounds and why. No I/O, no queue -- this is what
    Test 2 calls directly with a hand-built stream to check exact-row firing.

    reading:    dict of metric -> value (e.g. one row from all_logs)
    thresholds: dict of metric -> [low, high]

    Returns {} if nothing fired, otherwise {"warnings": {metric: value, ...},
    "desc": "<human-readable description>"}.
    """
    all_warns = {}
    desc = ""
    vitals = {k: v for k, v in reading.items() if k in thresholds}

    for d, v in vitals.items():
        if v is None:
            continue
        lo, hi = thresholds[d]
        if v < lo:
            all_warns[d] = v
            desc += ("and " if desc else "") + f"{d} is too low with value of {v} "
        elif v > hi:
            all_warns[d] = v
            desc += ("and " if desc else "") + f"{d} is too high, with value of {v}"

    if not all_warns:
        return {}
    return {"warnings": all_warns, "desc": desc}


async def check_det_warn(data: dict) -> Any:
    """
    Checks for deterministic alerts and pushes to warning_queue if any fired.
    Thin wrapper around evaluate_guards() -- keep new guard logic in that
    pure function, not here.
    """
    result = evaluate_guards(data, DET_WARNINGS)
    if result:
        new_warning = Warn(type=result["warnings"], warn=result["desc"])
        await warning_queue.put((FF_ID, new_warning))


async def check_trend_warn(data: dict) -> Any:
    """
    Checks the deterministics trends? NOT SURE YET HEHE
    """
    raise NotImplementedError


async def trendline(data: dict) -> None:
    """
    Makes a trendline based on the mean of the data collected every cycle for
    each category of data. Compresses TRENDLINE to half its length (pairwise
    averaging values, keeping every other timestamp) once it exceeds 15
    entries, so it doesn't grow unbounded.
    """
    global TRENDLINE

    TRENDLINE["time"].append(datetime.now().isoformat())
    for d, a in data.items():
        key = d.lower()
        if key in TRENDLINE:
            TRENDLINE[key].append(a)

    if len(TRENDLINE['time']) > 15:
        for key, values in TRENDLINE.items():
            compressed = []
            i = 0
            while i < len(values):
                if key == 'time':
                    compressed.append(values[i])  # keep every other timestamp
                    i += 2
                else:
                    if i + 1 < len(values):
                        compressed.append(round((values[i] + values[i + 1]) / 2, 2))
                        i += 2
                    else:
                        compressed.append(values[i])  # odd one out, keep as-is
                        i += 1
            TRENDLINE[key] = compressed


async def summaries() -> None:
    """
    Checks the data every CYCLE that is chosen
    """
    while True:
        await asyncio.sleep(CYCLE)
        await check_data()


async def main() -> None:
    """
    Runs the checking for deterministic alerts and also to make general summaries at the same time
    """
    print("hi")
    await asyncio.gather(
        read_live_data(),
        summaries(),
    )

if __name__ == "__main__":
    asyncio.run(main())