"""
This Python file is generating the fake CSV files right now. It randomly generate and send:
(1) Heart rate
(2) Oxygen levels
(3) Elevation Level
(4) Temperature 
In the form of a dictionary

This information will be sent to pool_maker.py
"""
import random
import pool_maker
import asyncio
from datetime import datetime
from memory_manager import memory

def weighted_list(ranges, dec):
    """
    This function will pick a range by weight, and then output a value within that range at random rounded to dec 
    number of decimal points

    Args:
    - ranges: a list of (min, max, weight) tuples
    - dec: a non-negative integer denoting the number of decimals the value can hold.
    """
    mins, maxs, weights = zip(*ranges)
    chosen_min, chosen_max = random.choices(list(zip(mins, maxs)), weights=weights)[0]
    return round(random.uniform(chosen_min, chosen_max), dec)

# These are the distributions for the random generator

# Heart Rate
HEART_RATE_RANGES = [
    (50, 190, 0.95),
    (20, 50, 0.03),
    (190, 300, 0.02)
]

# Blood oxygen
OXYGEN_RANGES = [
    (95, 100, 0.91),
    (90, 95, 0.06),
    (80, 90, 0.03)
]

# Elevation 
ELEVATION_LEVELS = [
    (-10, 10, 0.85),
    (-20, -10, 0.05),
    (10, 25, 0.06),
    (25, 50, 0.04)
]

# External Temperature
TEMPERATURE = [
    (10, 30, 0.70),
    (30, 100, 0.1),
    (100, 500, 0.1),
    (500, 900, 0.07),
    (900, 1500, 0.03)
]

# Respiratory Rates
RESPIRATION = [
    (12, 24, 0.9),
    (5, 11, 0.04),
    (25, 35, 0.03),
    (0, 4, 0.03)
]

# Heart Rate Variability
HRV = [
    (40, 110, 0.9),
    (15, 39, 0.05),
    (111, 200, 0.05)
]

# Uh internal temp yay
BODY_TEMP = [
    (36.5, 38, 0.9),
    (25, 36, 0.04),
    (38.1, 45, 0.06)
]

# The difference in the gait cadence 
GAIT_DIFF = [
    (0.0, 1.9, 0.9),
    (1.91, 2.9, 0.06),
    (3.0, 5.0, 0.04)
]
# This is the dictionary that will be returned!
def data() -> dict:
    """
    Return a dictionary with randomly generated data.
    """
    return {
        "time": datetime.now().isoformat(),
        "hr": int(weighted_list(HEART_RATE_RANGES, 0)),
        "o2": weighted_list(OXYGEN_RANGES, 2),
        "elevation": weighted_list(ELEVATION_LEVELS, 2),
        "temp": weighted_list(TEMPERATURE, 2),
        "respiration": weighted_list(RESPIRATION, 0),
        "hrv": weighted_list(HRV, 2),
        "body_temp": weighted_list(BODY_TEMP, 2),
        "gait": weighted_list(GAIT_DIFF, 2)
    }


async def start_stream():
    count = 0
    await pool_maker.clear_db()
    while True:
        p1 = data()
        p2 = data()
        p3 = data()
        # print(new_packet)
        await pool_maker.process_incoming(p1, 1)
        await pool_maker.process_incoming(p2, 2)
        await pool_maker.process_incoming(p3, 3)
        count += 1
        if count == 5:
            d = {1: p1, 2: p2, 3: p3}
            count = 0 

        await asyncio.sleep(2)

