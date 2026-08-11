"""
This file replaces generator.py as the data source AND doubles as the
accuracy evaluator. It streams realistic per-worker vitals to
pool_maker.process_incoming(vitals, worker_id) - same call pattern as
generator.py, one call per worker per tick.

Scoring is NOT done by reading process_incoming's return value. The
captain (captain1.py) is the one deciding the team-level verdict each
cycle, and it reports that verdict back by calling get_results(type,
conf, time) below, once per cycle, as the stream runs. So this file's
job is: (a) generate ground truth with real cross-worker correlation,
(b) send it to pool_maker, (c) let the captain fill in PREDICTION_TYPE /
PREDICTION_CONFIDENCE / LATENCY via get_results as it goes, and (d) once
the stream ends, line those up against ground truth and score them.

KEY DESIGN PRINCIPLE:

  A rising heart rate is ambiguous at the single-worker level. It could be a cardiac event (INTERNAL/medical) 
  or the room getting hot (EXTERNAL/environmental) - and those demand opposite responses: pull one person for medical care, vs. withdraw the whole team.

    - EXTERNAL: every worker's ambient temp/elevation rises together,
      tick after tick; HR only follows later, for everyone, as a
      secondary effect.
    - INTERNAL: exactly one worker's vitals go bad while ambient stays
      normal and the other two workers stay normal the whole time.
"""

import random
import asyncio
from datetime import datetime
import pool_maker
from memory_manager import memory

# Config
# ---------------------------------------------------------------------------

NUM_WORKERS = 3
TICK_SECONDS = 2
MIN_ANOMALY_TICKS = 10   # an anomaly, once triggered, lasts AT LEAST this long
MAX_ANOMALY_TICKS = 20   # and at most this long, picked at random per episode

EVAL_MODE = True         # True: run NUM_TEST_TICKS ticks and score results.
NUM_TEST_TICKS = 200     # False (generator mode): stream forever, like generator.py.

# Filled in by get_results(), called from captain1.py once per cycle as
# the stream runs - NOT by this file. Index i in each of these three
# lists is assumed to correspond to tick i's ground truth, i.e. the
# captain calls get_results() exactly once per tick, in order.
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

# Tight, healthy-only ranges used specifically for anomaly scenarios, so an
# INTERNAL event doesn't accidentally roll a hot ambient temp from the
# heavy tail of TEMPERATURE, or an EXTERNAL event doesn't accidentally roll
# a wild HR from the heavy tail of HEART_RATE_RANGES. Ground truth needs to
# be unambiguous for scoring to mean anything.
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
    """Like baseline_vitals(), but clamped to the healthy band only - used
    as the starting point for anomaly scenarios and for every worker who
    is NOT part of the current anomaly, so ground truth stays unambiguous."""
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


# ---------------------------------------------------------------------------
# Anomaly generators
# ---------------------------------------------------------------------------

def internal_bad(subtype: int) -> dict:
    """
    One worker's vitals for a MEDICAL anomaly. Ambient fields (temp,
    elevation) stay in the healthy band on purpose - that's what makes it
    distinguishable from an environmental event.
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
    One worker's vitals for an ENVIRONMENTAL anomaly at a given elapsed
    tick count. Called with the SAME subtype/elapsed for every worker in
    the same tick, so ambient fields move together for everyone. HR only
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


# ---------------------------------------------------------------------------
# Team state machine - this is what enforces the >=10 tick minimum duration
# ---------------------------------------------------------------------------

def _init_team_state() -> dict:
    return {wid: {"kind": NORMAL, "subtype": 0, "elapsed": 0, "duration": 0}
            for wid in range(1, NUM_WORKERS + 1)}


def _start_episode(state: dict):
    """Rolls whether a new anomaly episode starts, and for how long it
    will run. Duration is randomized but always >= MIN_ANOMALY_TICKS."""
    roll = random.choices([NORMAL, INTERNAL, EXTERNAL], weights=[20, 5, 2], k=1)[0]
    duration = random.randint(MIN_ANOMALY_TICKS, MAX_ANOMALY_TICKS)

    if roll == INTERNAL:
        wid = random.choice(list(state.keys()))
        state[wid] = {"kind": INTERNAL, "subtype": random.randint(1, 7),
                      "elapsed": 0, "duration": duration}
    elif roll == EXTERNAL:
        subtype = random.randint(1, 4)
        for w in state:
            state[w] = {"kind": EXTERNAL, "subtype": subtype,
                        "elapsed": 0, "duration": duration}


def next_team_tick(state: dict) -> dict:
    """
    Advances the whole team by one tick and returns:
      {"vitals": {worker_id: vitals_dict}, "label": NORMAL/INTERNAL/EXTERNAL,
       "flagged_worker": worker_id or None, "subtype": int or None}

    An anomaly, once started, is NOT allowed to resolve before it has run
    for `duration` ticks (>= MIN_ANOMALY_TICKS) - that's what makes the
    scenario realistic instead of flickering on and off every couple of
    seconds.
    """
    active = [wid for wid, s in state.items() if s["kind"] != NORMAL]
    if not active:
        _start_episode(state)

    vitals = {}
    label = NORMAL
    flagged_worker = None
    subtype_out = None

    for wid, s in state.items():
        if s["kind"] == NORMAL:
            vitals[wid] = baseline_vitals()
            continue

        s["elapsed"] += 1
        if s["kind"] == INTERNAL:
            vitals[wid] = internal_bad(s["subtype"])
            label = INTERNAL
            flagged_worker = wid
            subtype_out = s["subtype"]
        else:  # EXTERNAL
            vitals[wid] = external_bad(s["subtype"], s["elapsed"])
            label = EXTERNAL
            subtype_out = s["subtype"]

        if s["elapsed"] >= s["duration"]:
            state[wid] = {"kind": NORMAL, "subtype": 0, "elapsed": 0, "duration": 0}

    return {"vitals": vitals, "label": label, "flagged_worker": flagged_worker, "subtype": subtype_out}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def record_matrix(ground_truth: list, predicted_types: list) -> dict:
    """
    Confusion matrix over the three team-level labels, built from the
    captain's own reported verdicts (PREDICTION_TYPE, via get_results),
    not from anything this file inferred itself.

    ground_truth[i] is a step dict from next_team_tick().
    predicted_types[i] is the string the captain passed to get_results()
    for that same cycle - "normal" / "internal" / "external".

    NOTE: get_results() doesn't take a worker id, only a type/confidence/
    latency, so this can't currently check whether the captain named the
    *correct* worker for an INTERNAL event - only whether it got the
    normal/internal/external classification right. If captain1.py starts
    passing a worker id too, that check can be added back here.
    """
    n = min(len(ground_truth), len(predicted_types))
    if len(ground_truth) != len(predicted_types):
        print(f"warning: ground_truth has {len(ground_truth)} ticks but "
              f"PREDICTION_TYPE has {len(predicted_types)} entries - "
              f"get_results() wasn't called exactly once per tick. "
              f"Scoring only the first {n} aligned entries.")

    matrix = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    for truth, predicted in zip(ground_truth[:n], predicted_types[:n]):
        actual = truth["label"]
        predicted = predicted if predicted in LABELS else NORMAL
        matrix[actual][predicted] += 1

    return matrix

# ---------------------------------------------------------------------------
# Main stream - replaces generator.py's start_stream()
# ---------------------------------------------------------------------------

async def start_stream():
    """
    Streams p1, p2, p3 (one per worker) to pool_maker.process_incoming
    every TICK_SECONDS, same call pattern as generator.py.

    This function does NOT capture or time the system's verdict itself -
    the captain (captain1.py) watches the stream and calls get_results()
    once per cycle as it goes, filling PREDICTION_TYPE /
    PREDICTION_CONFIDENCE / LATENCY on its own. All this loop does is
    keep a parallel list of ground truth so the two can be lined up and
    scored once the stream ends.
    """
    state = _init_team_state()
    ground_truth = []

    tick = 0
    while (EVAL_MODE and tick < NUM_TEST_TICKS) or not EVAL_MODE:
        step = next_team_tick(state)
        p1, p2, p3 = step["vitals"][1], step["vitals"][2], step["vitals"][3]

        await pool_maker.process_incoming(p1, 1)
        await pool_maker.process_incoming(p2, 2)
        await pool_maker.process_incoming(p3, 3)

        if EVAL_MODE:
            ground_truth.append(step["label"])

        tick += 1
        await asyncio.sleep(TICK_SECONDS)

        # matrix = record_matrix(ground_truth, PREDICTION_TYPE)
    avg_latency = sum(LATENCY) / len(LATENCY) if LATENCY else 0.0
    max_latency = max(LATENCY) if LATENCY else 0.0
    avg_conf = sum(PREDICTION_CONFIDENCE) / len(PREDICTION_CONFIDENCE) if PREDICTION_CONFIDENCE else 0.0
    a =  {
        "avg_latency": avg_latency,
        "max_latency": max_latency,
        "avg_confidence": avg_conf,
        "ground_truth": ground_truth,
        "predictions": list(PREDICTION_TYPE),
        "confidences": list(PREDICTION_CONFIDENCE),
        "latencies": list(LATENCY),
    }
    print(a)
    return a


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