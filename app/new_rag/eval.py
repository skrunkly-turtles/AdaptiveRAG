"""
This file replaces generator.py as the data source AND doubles as the
accuracy evaluator. It streams realistic per-worker vitals to
pool_maker.process_incoming(vitals, worker_id) - same call pattern as
generator.py, one call per worker per tick - and scores what the system
says against ground truth.

KEY DESIGN PRINCIPLE:

  A rising heart rate is ambiguous at the single-worker level. It could
  be a cardiac event (INTERNAL/medical) or the room getting hot
  (EXTERNAL/environmental) - and those demand opposite responses: pull
  one person for medical care, vs. withdraw the whole team.

  Because process_incoming is called per worker, per tick (matching
  pool_maker's real interface), this file does NOT try to hand the
  system all workers at once. The cross-worker correlation has to live
  in the system's own memory (memory_manager) across those calls. What
  THIS file is responsible for is making sure ground truth is generated
  with genuine team-level correlation, so that signal actually exists to
  be picked up:
    - EXTERNAL: every worker's ambient temp/elevation rises together,
      tick after tick; HR only follows later, for everyone, as a
      secondary effect.
    - INTERNAL: exactly one worker's vitals go bad while ambient stays
      normal and the other two workers stay normal the whole time.

  Anomalies also last a REALISTIC minimum duration once triggered -
  nobody has a 10-second heart attack or a fire that clears in one tick.
  Every anomaly episode runs for at least MIN_ANOMALY_TICKS (10) ticks,
  with a randomized total duration on top of that, before it's allowed
  to resolve back to normal.
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

def record_matrix(ground_truth: list, predictions: list) -> dict:
    """
    Confusion matrix over the three team-level labels, plus a check of
    whether an INTERNAL verdict named the correct worker to pull.

    predictions[i] is expected to be the tick's aggregate system verdict:
    {"label": "normal"|"internal"|"external", "worker": <id or None>}.
    See start_stream()'s NOTE for how that's derived from three separate
    process_incoming() calls.
    """
    matrix = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    correct_worker = 0
    internal_total = 0

    for truth, pred in zip(ground_truth, predictions):
        actual = truth["label"]
        predicted = pred["label"] if pred["label"] in LABELS else NORMAL
        matrix[actual][predicted] += 1
        if actual == INTERNAL:
            internal_total += 1
            if predicted == INTERNAL and pred.get("worker") == truth["flagged_worker"]:
                correct_worker += 1

    matrix["_internal_worker_accuracy"] = (
        correct_worker / internal_total if internal_total else None
    )
    return matrix


# ---------------------------------------------------------------------------
# Main stream - replaces generator.py's start_stream()
# ---------------------------------------------------------------------------

async def start_stream():
    """
    Streams p1, p2, p3 (one per worker) to pool_maker.process_incoming
    every TICK_SECONDS, same call pattern as generator.py. In EVAL_MODE
    this also records ground truth vs. the system's verdicts and prints a
    confusion matrix + latency stats at the end; otherwise it behaves
    like generator.py and just runs forever.

    NOTE ON SCORING: process_incoming is called once per worker (its real
    signature), so there's no single "team verdict" return value handed
    back directly. This assumes each call's return includes the system's
    CURRENT best team-level read after ingesting that data point (it can
    keep using memory_manager.memory across calls to do the cross-worker
    comparison). The verdict returned by the third call in a tick - after
    all three workers' data for that tick is in - is used as that tick's
    scored prediction. If pool_maker's real return shape differs, only
    the three `pred = await pool_maker.process_incoming(...)` lines and
    the `predictions.append(...)` line need to change.
    """
    state = _init_team_state()
    ground_truth, predictions, latencies = [], [], []

    tick = 0
    while (EVAL_MODE and tick < NUM_TEST_TICKS) or not EVAL_MODE:
        step = next_team_tick(state)
        p1, p2, p3 = step["vitals"][1], step["vitals"][2], step["vitals"][3]

        start = datetime.now()
        pred1 = await pool_maker.process_incoming(p1, 1)
        pred2 = await pool_maker.process_incoming(p2, 2)
        pred3 = await pool_maker.process_incoming(p3, 3)
        latencies.append((datetime.now() - start).total_seconds())

        if EVAL_MODE:
            final = pred3 if isinstance(pred3, dict) else {}
            ground_truth.append(step)
            predictions.append({
                "label": final.get("label", NORMAL),
                "worker": final.get("worker"),
            })

        tick += 1
        await asyncio.sleep(TICK_SECONDS)

    if EVAL_MODE:
        matrix = record_matrix(ground_truth, predictions)
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0
        print("confusion matrix:", matrix)
        print(f"avg latency: {avg_latency:.3f}s, max: {max_latency:.3f}s")
        return {
            "confusion_matrix": matrix,
            "avg_latency": avg_latency,
            "max_latency": max_latency,
            "ground_truth": ground_truth,
            "predictions": predictions,
            "latencies": latencies,
        }


if __name__ == "__main__":
    asyncio.run(start_stream())