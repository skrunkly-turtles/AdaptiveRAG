"""
This is the file that is going to evaluate the accuracy of the model. It will do the following:
(1) Generate data in distinct routes: normal, internal anomaly (i.e. heart attack, stroke, limp), external anomaly(i.e. fire)
(2) Feed this data to the llm every 2 seconds. I should be able to induce an internal anomaly and see how the system reacts
(3) It will record what the system says, and evaluate whether it is correct or not. From this evaluation, it will create a confusion matrix
(4) Record the latency of each response as an additional benchmark.
"""
import asyncio
import random
from pool_maker import process_incoming
from firefighters import ff1, ff2, ff3

NUM_TESTS = 100

# The previous value, for data()
PREV = (0, 0)

# How long the value was the same at that tuple for, for data()
TIME = 0

async def data() -> tuple:
    """
    Random generates a tuple of information about a single timeframe of data that was generated.
    The first value is the type of data that was generated; 1 = normal, 2 = internal anomaly, 3 = external anomaly.
    The second value is the subtype of data that was generated, specified to the type of data as stated above.
    The third is a dictionary of the data that was generated for that value. 
    """
    global PREV
    global TIME

    i = random.choices([1, 2, 3], weights=[20, 5, 2], k=1)[0]

    if i == 2:
        j = random.choices([1, 2, 3, 4, 5, 6, 7])
        if (i, j) == PREV:
            TIME += 1
        else:
            TIME = 0
        k = internal_bad(j, TIME)
        PREV = (i, j)
        return (i, j, k)

    if i == 3:
        j = random.choices([1, 2, 3, 4])
        if(i, j) == PREV:
            TIME += 1
        else:
            TIME = 0
        k = external_bad(j, TIME)
        PREV = (i, j)
        return (i, j, k)

    PREV = (i, j)
    k = normal()
    return (i, 0, k)


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

    if type == 7:
        norm["respiration"] = int(random.uniform(26, 40))
        norm["hr"] = int(random.uniform(100, 150))

    return norm


async def external_bad(type: int, time: int) -> dict:
    """
    Returns a dict of external anomaly vital signs where the type will be classified as such:
    1 = high elevation
    2 = low elevation
    3 = fire or very high heat
    4 = cold or very low temperature
    """
    norm = normal()
    if type == 1:
        if time > 1:
            norm["elevation"] *= round(random.uniform(1, 1.1), 2)
            norm["respiration"] *= round(random.uniform(1, 1.1), 2)
            return norm
        norm["elevation"] = round(random.uniform(15, 25), 2)

    if type == 2:
        if time > 1:
            norm["elevation"] *= round(random.uniform(0.9, 1), 2)
            return norm
        norm["elevation"] = round(random.uniform(-13, 0)) 

    if type == 3:
        if time < 3:
            norm["temp"] = round(random.uniform(40, 100), 2)
        if time > 2:
            norm["temp"] *= round(random.uniform(1, 1.1))
        if time > 5:
            norm["hr"] = int(random.uniform(100, 200))
            norm["respiration"] = int(random.uniform(15, 25))

    if type == 4:
        if time < 3:
            norm["temp"] = round(random.uniform(-25, -10), 2)
        if time > 2:
            norm["temp"] *= round(random.uniform(1, 1.05), 2)

    return norm

async def record_matrix(p1: list, p2: list) -> dict:
    """
    Return a confusion matrix of what a specific firefighter got right where p1 is the list of the type of 
    data that was generated, and p2 is the type of data that the LLM flagged. 
    """
    raise NotImplementedError


async def run_stream(p1, p2, p3) -> dict:
    """
    Return a dictionary of what each LLM decided the state of the place environment was
    """
    f1 = []
    f2 = []
    f3 = []

    # The counter for seconds
    i = 0
    while i < NUM_TESTS:
        d1 = data()
        d2 = data()
        d3 = data()
        f1.append(d1[0])
        f2.append(d2[0])
        f3.append(d3[0])

        await process_incoming(d1[2], 1)
        await process_incoming(d2[2], 2)
        await process_incoming(d3[2], 3)

        i += 1
        asyncio.sleep(2)

    record_matrix()
    

if __name__ == "__main__":
    asyncio.run(run_stream())