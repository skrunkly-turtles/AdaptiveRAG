"""
This is the eval file yay
"""
import csv
import numpy as np
import random
import asyncio
from datetime import datetime
import pool_maker


NUM_WORKERS = 5
TICK_SECONDS = 2
ANOMALY_TICKS = 5        # every anomaly episode (internal or external) lasts EXACTLY this many ticks

EVAL_MODE = True         # True: run NUM_TEST_TICKS ticks and score results.
NUM_TEST_TICKS = 200     # False (generator mode): stream forever, like generator.py.

PREDICTION_TYPE = []
PREDICTION_CONFIDENCE = []
LATENCY = []
FFS = []

NORMAL = "normal"
INTERNAL = "internal"
EXTERNAL = "external"
LABELS = [NORMAL, INTERNAL, EXTERNAL]

INTERNAL_SUBTYPES = {
    1: "heart_attack", 2: "stroke", 3: "fever", 4: "limp",
    5: "o2_drop", 6: "not_breathing", 7: "hyperventilation",
}
EXTERNAL_SUBTYPES = {
    1: "high_elevation", 2: "low_elevation", 3: "fire_heat", 4: "cold",
}


def weighted_list(ranges, dec):
    """
    Picks a (min, max) range by weight, then returns a random value inside
    it rounded to `dec` decimal places.
    ranges: list of (min, max, weight) tuples.
    """
    mins, maxs, weights = zip(*ranges)
    chosen_min, chosen_max = random.choices(list(zip(mins, maxs)), weights=weights)[0]
    return round(random.uniform(chosen_min, chosen_max), dec)


HEART_RATE_RANGES = [(50, 190, 0.95), (20, 50, 0.03), (190, 300, 0.02)]
OXYGEN_RANGES = [(95, 100, 0.91), (90, 95, 0.06), (80, 90, 0.03)]
ELEVATION_LEVELS = [(-10, 10, 0.85), (-20, -10, 0.05), (10, 25, 0.06), (25, 50, 0.04)]
TEMPERATURE = [(10, 30, 0.70), (30, 100, 0.1), (100, 500, 0.1), (500, 900, 0.07), (900, 1500, 0.03)]
RESPIRATION = [(12, 24, 0.9), (5, 11, 0.04), (25, 35, 0.03), (0, 4, 0.03)]
HRV = [(40, 110, 0.9), (15, 39, 0.05), (111, 200, 0.05)]
BODY_TEMP = [(36.5, 38, 0.9), (25, 36, 0.04), (38.1, 45, 0.06)]
GAIT_DIFF = [(0.0, 1.9, 0.9), (1.91, 2.9, 0.06), (3.0, 5.0, 0.04)]


_HEALTHY_HR = (55, 95)
_HEALTHY_O2 = (96, 100)
_HEALTHY_ELEV = (-5, 10)
_HEALTHY_TEMP = (12, 26)
_HEALTHY_RESP = (12, 20)


def baseline_vitals() -> dict:
    """A fully healthy, normal-range reading for one worker at one tick."""
    return {
        "time": datetime.now().isoformat(),
        "hr": int(weighted_list(HEART_RATE_RANGES, 0)),
        "o2": weighted_list(OXYGEN_RANGES, 2),
        "elevation": weighted_list(ELEVATION_LEVELS, 2),
        "temp": weighted_list(TEMPERATURE, 2),
        "respiration": weighted_list(RESPIRATION, 0),
        "hrv": weighted_list(HRV, 2),
        "body_temp": weighted_list(BODY_TEMP, 2),
        "gait": weighted_list(GAIT_DIFF, 2),
    }


def healthy_vitals() -> dict:
    """This is the health yum"""
    return {
        "time": datetime.now().isoformat(),
        "hr": int(round(random.uniform(*_HEALTHY_HR))),
        "o2": round(random.uniform(*_HEALTHY_O2), 2),
        "elevation": round(random.uniform(*_HEALTHY_ELEV), 2),
        "temp": round(random.uniform(*_HEALTHY_TEMP), 2),
        "respiration": int(round(random.uniform(*_HEALTHY_RESP))),
        "hrv": round(random.uniform(50, 110)),
        "body_temp": round(random.uniform(36.5, 37.1), 2),
        "gait": round(random.uniform(0, 1.4), 2),
    }


def internal_bad(subtype: int) -> dict:
    """
   One worker's internal vitals goes wack, the subtye as defined somewhere above.
    """
    v = healthy_vitals()
    if subtype in (1, 2):  # heart attack / stroke
        v["hr"] = int(round(random.uniform(110, 170)))
        v["respiration"] = int(round(random.uniform(25, 35)))
        v["o2"] = round(random.uniform(85, 95), 2)
        v["hrv"] = round(random.uniform(10, 40))
        if subtype == 2:
            v["gait"] = round(random.uniform(3, 7), 2)
    elif subtype == 3:  # fever
        v["body_temp"] = round(random.uniform(38, 40), 2)
        v["hr"] = int(round(random.uniform(100, 160)))
    elif subtype == 4:  # limp
        v["gait"] = round(random.uniform(3, 7), 2)
        v["respiration"] = int(round(random.uniform(20, 30)))
    elif subtype == 5:  # o2 drop
        v["o2"] = round(random.uniform(80, 90), 2)
        v["hr"] = int(round(random.uniform(100, 160)))
        v["respiration"] = int(round(random.uniform(20, 30)))
    elif subtype == 6:  # not breathing
        v["respiration"] = 0
        v["o2"] = round(random.uniform(75, 88), 2)
    elif subtype == 7:  # hyperventilation
        v["respiration"] = int(round(random.uniform(26, 40)))
        v["hr"] = int(round(random.uniform(100, 150)))
    return v


def external_bad(subtype: int, elapsed: int) -> dict:
    """
    Calls for ambient fields move together for everyone. HR only
    rises later, as a secondary heat-stress effect - never as the first
    or only signal.
    """
    v = healthy_vitals()
    if subtype == 1:  # high elevation
        v["elevation"] = round(random.uniform(15, 25) * (1 + 0.02 * elapsed), 2)
        v["respiration"] = int(round(v["respiration"] * (1 + 0.02 * elapsed)))
    elif subtype == 2:  # low elevation
        v["elevation"] = round(random.uniform(-13, 0) * (1 - 0.02 * elapsed), 2)
    elif subtype == 3:  # fire / heat
        v["temp"] = round(random.uniform(40, 100) * (1 + 0.02 * elapsed), 2)
        if elapsed > 4:
            v["hr"] = int(round(random.uniform(100, 140)))
        if elapsed > 8:
            v["hr"] = int(round(random.uniform(140, 200)))
            v["respiration"] = int(round(random.uniform(20, 30)))
    elif subtype == 4:  # cold
        v["temp"] = round(random.uniform(-25, -10) * (1 + 0.01 * elapsed), 2)
    return v



def _roll_segment() -> dict:
    """Picks the next ANOMALY_TICKS-tick segment. INTERNAL picks one random
    worker to be affected; EXTERNAL affects all workers; NORMAL affects
    none. Whichever kind is picked, it always lasts exactly ANOMALY_TICKS
    ticks - same fixed length as everything else. """
    roll = random.choices([NORMAL, INTERNAL, EXTERNAL], weights=[20, 5, 2], k=1)[0]
    if roll == INTERNAL:
        return {"kind": INTERNAL, "subtype": random.randint(1, 7),
                "worker": random.randint(1, NUM_WORKERS), "elapsed": 0}
    if roll == EXTERNAL:
        return {"kind": EXTERNAL, "subtype": random.randint(1, 4),
                "worker": None, "elapsed": 0}
    return {"kind": NORMAL, "subtype": 0, "worker": None, "elapsed": 0}


def _init_segment() -> dict:
    """Starts 'used up' so the very first call to next_team_tick() rolls a
    fresh segment immediately."""
    return {"kind": NORMAL, "subtype": 0, "worker": None, "elapsed": ANOMALY_TICKS}


def next_team_tick(segment: dict) -> tuple:
    """
    Advances by one tick within the current fixed-length segment, rolling
    a brand new segment every ANOMALY_TICKS ticks (NORMAL included).

    Returns (step, segment) where:
      step = {"vitals": {worker_id: vitals_dict}, "label": NORMAL/INTERNAL/EXTERNAL,
              "flagged_worker": worker_id or None, "subtype": int or None}
      segment = the segment to pass onto the next call.
    """
    if segment["elapsed"] >= ANOMALY_TICKS:
        segment = _roll_segment()

    vitals = {}
    for wid in range(1, NUM_WORKERS + 1):
        if segment["kind"] == NORMAL:
            vitals[wid] = baseline_vitals()
        elif segment["kind"] == INTERNAL:
            vitals[wid] = internal_bad(segment["subtype"]) if wid == segment["worker"] else healthy_vitals()
        else: 
            vitals[wid] = external_bad(segment["subtype"], segment["elapsed"] + 1)

    segment["elapsed"] += 1

    step = {
        "vitals": vitals,
        "label": segment["kind"],
        "flagged_worker": segment["worker"] if segment["kind"] == INTERNAL else None,
        "subtype": segment["subtype"] if segment["kind"] != NORMAL else None,
    }
    return step, segment


def record_matrix(ground_truth: list, predicted_types: list) -> dict:
    """
    Confusion matrix over the three team-level labels, built from the
    captain's own reported verdicts (PREDICTION_TYPE, via get_results),
    not from anything this file inferred itself.
    """
    n = min(len(ground_truth), len(predicted_types))
    if len(ground_truth) != len(predicted_types):
        print(f"ground truth and predicted not the same length...")

    matrix = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    for truth, predicted in zip(ground_truth[:n], predicted_types[:n]):
        actual = truth["label"]
        predicted = predicted if predicted in LABELS else NORMAL
        matrix[actual][predicted] += 1

    return matrix


async def start_stream():
    """
    Streams to all the firefighters yay. At the end, it will produce a nice matrix of all the
    information of that session.
    """
    segment = _init_segment()
    
    ground_truth = []

    tick = 0
    while (EVAL_MODE and tick < NUM_TEST_TICKS) or not EVAL_MODE:
        step, segment = next_team_tick(segment)
        p = []
        for s in range(1, len(step["vitals"]) + 1):
            d = step["vitals"][s]
            await pool_maker.process_incoming(d, s)

        if EVAL_MODE and tick % 5 == 0:
            ground_truth.append(step["label"])

        tick += 1
        await asyncio.sleep(TICK_SECONDS)

        # matrix = record_matrix(ground_truth, PREDICTION_TYPE)
    await asyncio.sleep(10000) # This is to help all the calls get logged before we summarize 

    avg_latency = sum(LATENCY) / len(LATENCY) if LATENCY else 0.0
    percentile_latency = np.percentile(LATENCY, 95)
    max_latency = max(LATENCY) if LATENCY else 0.0
    avg_conf = sum(PREDICTION_CONFIDENCE) / len(PREDICTION_CONFIDENCE) if PREDICTION_CONFIDENCE else 0.0
    a =  {
        "avg_latency": avg_latency,
        "95th percentile latency": percentile_latency,
        "max_latency": max_latency,
        "avg_confidence": avg_conf,
        "ground_truth": ground_truth,
        "predictions": list(PREDICTION_TYPE),
        "confidences": list(PREDICTION_CONFIDENCE),
        "latencies": list(LATENCY),
    }
    write_csv(a)
    print(a)
    print(len(ground_truth))
    print(len(PREDICTION_TYPE))
    return a


def write_csv(data: dict):
    """Just clears the CSV output file every time eval is called.
    """
    with open('output.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(data)
        writer.writerow({})

async def get_results(type: str, conf: float, time: float, ff: list):
    """
    The nice function that records all the responses, called by
    captain1.py after every CYCLE.
    """
    global PREDICTION_CONFIDENCE, PREDICTION_TYPE, LATENCY
    PREDICTION_CONFIDENCE.append(conf)
    PREDICTION_TYPE.append(type)
    LATENCY.append(time)
    FFS.append(ff)


if __name__ == "__main__":
    asyncio.run(start_stream())