"""
This Python file is generating the fake CSV files right now. It randomly generate and send:
(1) Heart rate
(2) Oxygen levels
(3) Elevation Level
(4) Temperature 
In the form of a dictionary

This information will be sent to store.py and demo.py
"""
import random
import csv
import time
import store
from datetime import datetime


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
HEART_RATE_RANGES = [
    (50, 190, 0.95),
    (20, 50, 0.03),
    (190, 300, 0.02)
]

OXYGEN_RANGES = [
    (95, 100, 0.91),
    (90, 95, 0.06),
    (80, 90, 0.03)
]

ELEVATION_LEVELS = [
    (-10, 10, 0.85),
    (-20, -10, 0.05),
    (10, 25, 0.06),
    (25, 50, 0.04)
]

TEMPERATURE = [
    (10, 30, 0.70),
    (30, 100, 0.1),
    (100, 500, 0.1),
    (500, 900, 0.07),
    (900, 1500, 0.03)
]

# This is the dictionary that will be returned!
def data() -> dict:
    """
    Return a dictionary with randomly generated data.
    """
    return{
        "time": datetime.now().isoformat(),
        "hr": int(weighted_list(HEART_RATE_RANGES, 0)),
        "o2": weighted_list(OXYGEN_RANGES, 2),
        "elevation": weighted_list(ELEVATION_LEVELS, 2),
        "temp": weighted_list(TEMPERATURE, 2)
    }

def start_stream():
    while True:
        new_packet = data()
        # store.process_incoming(new_packet)
        print(new_packet)
        time.sleep(2)

