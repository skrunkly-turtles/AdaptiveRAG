"""
This is the file that is going to evaluate the accuracy of the model. It will do the following:
(1) Generate data in distinct routes: normal, internal anomaly (i.e. heart attack, stroke, limp), external anomaly(i.e. fire)
(2) Feed this data to the llm every 2 seconds. I should be able to induce an internal anomaly and see how the system reacts
(3) It will record what the system says, and evaluate whether it is correct or not. From this evaluation, it will create a confusion matrix
(4) Record the latency of each response as an additional benchmark.
"""
import asyncio
import random

NUM_TESTS = 100

async def data() -> list:
    """
    Random generate a series of data streams where 1 = normal, 2 = internal anomaly, 3 = external anomaly
    """
    raise NotImplementedError


# The Three Types of Streams yay

async def normal() -> dict:
    """
    Returns a dictionary of normal vital signs
    """
    hr = int(round(random.uniform(50, 100), 0))
    o2 = round(random.uniform(95, 100), 2)
    elevation = round(random.uniform(-5, 10), 2)
    temp = round(random.uniform(15, 25), 2)
    respiration = int(round(random.uniform()), 0)
    hrv = round(random.uniform(50, 110))
    body_temp = round(random.uniform(36.5, 37.1, 2))
    gait = round(random.uniform(0, 1.4, 2))
    return (
        {
            "hr": hr,
            "o2": o2,
            "elevation": elevation,
            "temp": temp,
            "respiration": respiration,
            "hrv": hrv,
            "body_temp": body_temp,
            "gait": gait
        }
    )


async def internal_bad(type: int, time: int) -> dict:
    """
    Returns a dict of internal anomaly vital signs where the type will be classified as such:
    1 = heart attack 
    2 = stroke
    3 = fever
    4 = limp
    5 = o2 stats down
    6 = not breathing 
    7 = hyperventilation
    """
    norm = normal()
    if type == 1 or type == 2:
        norm["hr"] = int(round(random.uniform(60, 130)))
        norm["respiration"] = int(random.uniform(25, 35))
        norm["o2"] = round(random.uniform(85, 95), 2)
        if type == 2:
            norm["body_temp"] = round(random.uniform(37, 38), 2)
        return norm
    if type == 3:
        norm["body_temp"] = round(random.uniform(38, 40), 2)
        norm["hr"] = int(random.uniform(60, 160))
    if type == 4:
        norm["gait"] = round(random.uniform(3, 7), 2)
        norm["respiration"] = int(random.uniform(20, 30))
    if type == 5:
        norm["o2"] = round(random.uniform(85, 93), 2)
        norm["hr"] = int(random.uniform(80, 150))
        norm["respiration"] = int(random.uniform(20, 30))
    if type == 6:
        norm["respiration"] = 0
        norm["o2"] = round(random.uniform(85, 93), 2)
    
    raise NotImplementedError

async def external_bad(type: int) -> dict:
    """
    Returns a dict of external anomaly vital signs where the type will be classified as such:
    1 = high elevation
    2 = low elevatino
    3 = fire or very high heat
    4 = cold or very low temperature
    """
    raise NotImplementedError


# This is where the con

async def write_data() -> None:
    """
    This is where it decides the type of data and also 
    """
async def record_matrix(p1: list, p2: list, p3: list) -> dict:
    """
    Return a dictionary of the confusion matrix that the LLM got right.
    """
    raise NotImplementedError

async def start_stream() -> None:
    """
    This is the main stream that is going to be sending the data to the 
    """
    p1 = data()
    p2 = data()
    p3 = data()
    record_matrix(p1, p2, p3)

if __name__ == "__main__":
    asyncio.run(start_stream())