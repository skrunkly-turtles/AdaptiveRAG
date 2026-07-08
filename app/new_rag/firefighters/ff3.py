"""
This file represents the firefighter. It is responsible for:
(1) Inputting the query, urgency and TIME token
(2) Validating the time token, and generating the other information for a Report
"""
import math
import json
import asyncio
from models import Query, Report
from get_data import get_data
from pydantic import RootModel, Field
import ollama
from typing import Any, Annotated

# Firefighter ID :D
FF_ID = 3
# Window weights for the mathematical formula we used! We can tweak this as needed. 
WINDOW_WEIGHTS = {'point': 1, 'short': 5, 'long': 30}

# We need an upper limit on the total amount of data retrieved. 
# This the max number of chunks x num_pools
MAX_CHUNKS = 300

# Chunk possibilities for the agent to choose from
class Relevance(RootModel[dict[str, Annotated[float, Field(ge=0.0, le=1.0)]]]):
    """The valid pydantic model schema for Ollama structuring."""
    pass

CHUNKS = [3, 10, 20, 40, 60, 100]
RES = [1, 3, 5, 10, 15, 25, 40]

# The list of data pools it can choose from
POOLS = ["ALL_LOG", "ELEVATION", "HR", "O2", "TEMP", "SUMMARIES"]

client = ollama.AsyncClient()

#TODO: make system prompt
POOL_PROMPT = (f""" You are a routing agent. 
              Given the query and the notes in the prompt, ONLY return a dictionary of 
              which data pools in {POOLS} are helpful to answer the question, mapped to a float in the list: [0.3, 0.5, 0.7, 1]
              where 0.3 indicates peripheral usefulness, and 1 indicates vital to the query. 
              Follow the json schema EXACTLY and return nothing else.       
""")

SYS_PROMPT = (f""" You are a precise agent. Given the data the key words to pay attention to, answer the 
        query and give a short and comprehensive summary of the data provided. 
""")
# Determine the chunk size, and the resolution through a deterministic formula. This can be up for debate.
# Note that output size will be: chunks x num_data, with it spanning (chunks x res x 2 seconds ) time
async def determine_chunks(q: Query, num_data: int) -> tuple[int, int]:
    """
    Return a tuple representing the number of chunks needed per pool, and the resolution. 
    These values are deterministically found by the urgency of query, window in query, 
    and the number of data pools which are required.
    """
    # The number of chunks is largely dependent on the urgency. By default, we want more accuracy and more chunks:
    
    # If the window is point though, we don't need that many chunks anyway!
    if q.window == 'point':
        c = math.floor(10 * (1- 0.7 * q.urgency))
        r = 1
        return (c, r)
    else:
        w = WINDOW_WEIGHTS[q.window]

        # Ok now we want the lower the urgency, the more data! Because we would prioritize accuracy over speed
        t_budget = math.floor(MAX_CHUNKS * (1 - 0.7 * q.urgency))

        # Now we plan the number of chunks accordingly. Note the max function so that each chunk has at LEAST 3 data points
        c = max(3, t_budget // num_data)

        # Resolution is gonna be denser with urgency (and 'short') but looser with less-urgent (and 'long')
        r = max(1, math.floor(w * (1 - 0.6 * q.urgency)))

        return (c, r)

# Determines which pools should have information retrieved from it with an AI agent AND deterministic 
# equations regarding urgency.
async def det_pools(q: Query) -> list:
    """
    Return a list of relevant pools to make the Report depending on (1) the Query, and then (2) the Urgency
    """
    # (1) We find the relevant pools and create a dictionary of their name mapped to a float between 0 and 1 
    # regarding how relevant they are
    response = await client.generate(
        model='llama3.2:3b',
        system=POOL_PROMPT,
        prompt= q.query,
        logprobs= True,
        format=Relevance.model_json_schema()
    )
    r = response['response']
    
    # (2) Now we use the urgency score and the relevance score to decide which pools to actually draw from:
    if q.urgency > 0.7:
        score = 1
    elif q.urgency >= 0.5:
        score = 0.4
    else:
        score = 0
    
    l = []
    m = ("SUMMARIES", 0.0)
    
    # Load into a JSON file:
    try:
        r = json.loads(r)
    except (json.JSONDecodeError, TypeError):
        print("Warning: Failed to parse LLM response into JSON. Using fallback pool.")
        return ["SUMMARIES"]
    
    for p in r:
        # Quick validity check. Don't add pools that don't exist:
        if p not in POOLS:
            print(f"The type of pool does NOT exist: {p}")
        else:
            if r[p] > m[1]:
                m = (p, r[p])
            if r[p] > score:
                l.append(p)
    
    if not l:
        return [m[0]]
    else:
        return l            

# This is the Report that is sent to the pools 
async def make_report(q: Query) -> Report:
    """
    Return a Report to be sent to get_data
    """
    # First we determine pools:
    pools = await det_pools(q)
    num_data = len(pools)

    # Then we send the pools to get chunks!
    size = await determine_chunks(q, num_data)

    # Then we make the Report:
    report = Report(
        time=q.time,
        data=pools,
        chunks=size[0],
        resolution=size[1]
    )

    return report

# KNOWING THAT THE CAPTAIN NEEDS TO READ THIS RETURN THING FOR MULTIPLE FIREFIGHTERS, 
# HOW SHOULD WE STRUCTURE THE RETURN? A JSON FILE?
async def read_pools(r: Report, q: Query) -> tuple[int, dict[str, list[Any]]]:
    """
    Return the firefighter ID in the first index, and a dictionary of all the information in the second index.
    Example: 
    (1, {
      "QUERY SUMMARY": [a few lines of summary answering the query and the data],
      "SUMMARIES": [ ... ],
      "HEART_RATE_POOL": [ ... ],
      "OXYGEN_POOL": [ ... ]
    })
    """
    d = await get_data(r, FF_ID)
    response = await client.generate(
        model='llama3.2:3b',
        system=SYS_PROMPT,
        prompt= f"Question and Notes: {q.query} \n Data: {d}",
        logprobs= True,
    )
    d["QUERY SUMMARY"] = [response['response']]

    return (FF_ID, d)

async def main(q: Query) -> tuple[int, dict[str, list[Any]]]:
    """
    Return the final list of stuff
    """
    report = await make_report(q)
    answer = await read_pools(report, q)
    
    return answer
