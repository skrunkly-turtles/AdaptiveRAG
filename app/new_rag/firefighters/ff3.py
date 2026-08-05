"""
This is the temporary firefighter file that is going to help me LOl
The new firefighters will need to do the following:
(1) Read and dynamically adjust the system prompts 
(2) Retrieve information as needed
(3) 
"""
import generator
from datetime import datetime
import sqlite3
import asyncio
import math
import json
from models1 import Adjust, Warn, Data
import ollama
from typing import Any, Annotated
from get_data1 import get_data
from memory_manager import memory
from comms import warning_queue

# This should be EXACTLY what captain1 says
CYCLE = 10

TRENDLINE = {
    "time": [],
    "hr": [],
    "o2": [],
    "elevation":[],
    "temp": [],
    "respiration": [],
    "hrv": [],
    "body_temp": [],
    "gait": []
}
# The live data in an SQL file
DB1_PATH = 'data/vitals3.db'

client = ollama.AsyncClient()
# The ID of the firefighter yay
FF_ID = 3

# Data we should especially attend to
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

SYS_PROMPT = f""" You are an analytical agent. 
                    Given the summaries from the past cycle, the cache of summaries from the past history, 
                    write a general report of the state and wellbeing of the worker. Keep in mind the deterministic
                    warnings, which indicate the normal ranges for each cateogory. 

                    You MUST keep your summary LESS THAN 4 sentences.
            """

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
            raise ValueError (f"{w} not a category of data bruh")
        DET_WARNINGS[w] = params.det_numbers[w]
    

async def check_data():
    """
    reads the data by the LLM depending on the det_warnings, the attend_to
    """
    print("getting data")
    global TRENDLINE

    curr_data = await get_data(FF_ID)

    tl_data = {c: curr_data[c]["mean"] for c in curr_data}

    await trendline(tl_data)

    response = await client.generate(model='qwen2.5:14b',
            system = SYS_PROMPT,
            prompt=f"""Deterministic warnings: {DET_WARNINGS} \n
                        Pay special attention to: {ATTEND_TO} \n 
                        Current Data: {curr_data} \n 
                        Trendline: {TRENDLINE}
            """,
        )
    print(response['response'])
    memory.firefighter_summary[FF_ID] = response['response']
    return response['response']


# This is a fat thing to read live data yay
async def read_live_data() -> None:
    """
    Reads new live vitals entries as they arrive for deterministic warning checks.
    """
    # Open as Read-Only via URI URI + add timeout to prevent locking conflicts
    conn = sqlite3.connect(
        f"file:{DB1_PATH}?mode=ro", 
        uri=True, 
        timeout=10.0,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row

    # 1. Initialize last_processed_id to the current highest rowid
    # (or set to 0 if you want to read past data on startup)
    def get_max_rowid():
        row = conn.execute("SELECT MAX(rowid) FROM all_logs").fetchone()
        return row[0] if row and row[0] else 0

    last_processed_id = await asyncio.to_thread(get_max_rowid)

    try:
        while True:
            # 2. Fetch all rows added SINCE the last processed rowid
            def fetch_new_rows():
                return conn.execute(
                    "SELECT rowid, * FROM all_logs WHERE rowid > ? ORDER BY rowid ASC",
                    (last_processed_id,)
                ).fetchall()

            rows = await asyncio.to_thread(fetch_new_rows)

            # 3. Process each new row once
            for row in rows:
                Data.model_validate(dict(row))
                last_processed_id = row["rowid"]

                # Now we run deterministic warnings!
                await check_det_warn(dict(row))

            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass
    finally:
        conn.close()

# The functions that deal with the deterministic warnings
async def check_det_warn(data:dict) -> Any:
    """
    Checks for deterministic alerts. Will send a warning to send_alert if needed
    """
    all_warns = {}
    desc = ""
    vitals = {k:v for k, v in data.items() if k in DET_WARNINGS}
    for d, v in vitals.items():
        if d not in DET_WARNINGS:
            raise ValueError(f"how is this even possible that {d} is here?")
        # Check lower bound
        if data[d] < DET_WARNINGS[d][0]:
            all_warns[d] = data[d]
            if desc:
                desc += "and "
            desc += f"{d} is too low with value of {data[d]} "
            
        # Check upper bound
        if data[d] > DET_WARNINGS[d][1]:
            all_warns[d] = data[d]
            if desc:
                desc += "and "
            desc += f"{d} is too high, with value of {data[d]}"

    # OK NOW WE CALL THE WARNING PEOPLE IN THE CAPTAIN THROUGH COMMS.
    if all_warns:
        new_warning = Warn(type=all_warns, warn=desc)

        await warning_queue.put((FF_ID, new_warning))


async def check_trend_warn(data:dict) -> Any:
    """
    Checks the deterministics trends? NOT SURE YET HEHE
    """
    raise NotImplementedError


# This function creates the general trendline that the firefighter will have cached
async def trendline(data: dict) -> None:
    """
    Makes a trendline based on the mean of the data collected every cycle for each category of data.
    These trendlines will be outputted as a JSON in the following formatted dictionary:
    
    {
        "time": [timestamp, timestamp1, timestamp2],
        <category name>: [value, value1, value2],
        <category name>: [value, value1, value2]
    }
    """
    global TRENDLINE

    TRENDLINE["time"].append(datetime.now().isoformat())
    for d, a in data.items():
        key = d.lower()
        if key in TRENDLINE:
            TRENDLINE[key].append(a)

    # Compress the TRENDLINE to half when it is too long ya 
    if len(TRENDLINE['time']) > 15:
        for d, a in data.items():
            key = d.lower()
            curr = 0
            i = 0
            while curr < len(a):
                if key == 'time' and curr % 2 == 1:
                    TRENDLINE[key][i] == TRENDLINE[key][curr]
                    curr += 2
                    i += 1
                elif key != 'time' and curr % 2 == 0:
                    temp = TRENDLINE[key][curr]
                    curr += 1
                elif key != 'time' and curr % 2 == 1:
                    new_val = round(temp + TRENDLINE[key][curr]/ 2 , 2)
                    TRENDLINE[key][i] == new_val
                    i += 1
                    curr += 1


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