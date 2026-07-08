"""
This file represents the Captain, which oversees all the firefighters. It is responsible for:
(1) Maintaining a memory and a cache of conversation and top-level summaries of the firefighters
(2) Reading the query and delivering response
(3) Sending the query to the correct firefighters, determining TIME, and urgency.
"""

import asyncio
from models import Query, CapDecision, WINDOW
import generator
import ollama
from firefighters import ff1, ff2, ff3
from datetime import datetime
from typing import Any
from memory_manager import summarize, memory, LATEST_DATA

FIREFIGHTER_NAMES = {1: ff1, 2: ff2, 3: ff3}

client = ollama.AsyncClient()

# The max number of tokens that can be used in the summary!
MAX_SUMMARY = 2000


SYS_PROMPT = (f""" You are a precise agent. 
""")

# This is the routing prompt to route the agents

ROUTE_PROMPT = (f""" You are a concise agent. Given the query from the user, the firefighters summary, and the data summary,
              return a response ONLY and EXACTLY as the json format {CapDecision} is. 
              
              CRITICAL RULES: 
              (1) Use the query, the data summar, and firefighters summary provided in the prompt.
              (2) Return ONLY the json schema outlined.
              (3) The list of words each ID is mapped to in firefighters MUST BE verbs or nous found in the query. 
                    If all words are important to the firefighter, map their ID to an empty list.
              (4) If you are extremely unsure, return exactly this fallback JSON:
                {{
                    "time": "{datetime.now()}",
                    "window": "long",
                    "firefighters": {{1: [], 2:[], 3:[]}},
                    "urgency": 0.5
                }}

              Here is what each attribute means:
              
              time: ISO 8601 string (YYYY-MM-DD HH:MM:SS). If no time is mentioned, provide the best logical guess based on the current system time.
              window: A string in {WINDOW} where 'point' is ONLY the data at <time>, 'short' is a SHORT window
                     of time around <time>, and 'long' requires a longer context window.
             firefighters: A list of integers corresponding to firefighter IDs in {FIREFIGHTER_NAMES} ONLY which are 
             relevant to the data. IF THE FIREFIGHTER IS NOT RELEVANT TO THE DATA, DO NOT INCLUDE THEM IN THE LIST
             urgency: A float between 0 and 1 where 0 is NOT CRITICAL at all, and 1 necessitates immediate action.
              
             Example:
             Query: What is the current heart rate of ff1 and ff2?
                    {{
                    "time": "2026-07-08T16:41:28.354+00:00",
                    "window": "point",
                    "firefighters": {[1, 2]},
                    "urgency": 0.5
                }}
              """)


# (1) Parse the Query and send it to the correct firefighters
async def route_ff(q:str) -> CapDecision:
    """
    Return a CapDecision outlining the firefighters which need to be deployed, and a quick note for them.
    """
    response = await client.generate(
        model='qwen3:14b',
        system=ROUTE_PROMPT,
        prompt= f"""
            Query: {q},
            Context: {memory.data_summary},
            Firefighters' Summary: {memory.firefighter_summary}
        """,
        logprobs= True,
        format=CapDecision.model_json_schema()
    )
    print(response['response'])
    r = CapDecision.model_validate_json(response['response'])
    return r
    
# Responsible for sending the data from the firefighters to the answer LLM
async def send_stuff(d: CapDecision, q: str) -> list[tuple[int, dict[str, list[Any]]]]:
    """
    Return the summarized data from firefighters and sends information to the firefighters
    """
    data = []
    for f in d.firefighters:
        qu = Query(
            query= f"{q}",
            window=d.window,
            urgency=d.urgency,
            time=d.time
        )
        data.append(FIREFIGHTER_NAMES[int(f)].main(qu))
        
    return await asyncio.gather(*data)

# Answers the query given all the data
async def answer(q: str) -> str:
    """
    Return the answer yay!
    """
    print("Pouring water down the drain...")
    relevant_ffs = await route_ff(q)
    LATEST_DATA[:] = await send_stuff(relevant_ffs, q)

    # INSERT THE MEMORY TOO
    response = await client.generate(
        model='llama3.2:3b',
        system=SYS_PROMPT,
        prompt= f"""
            Query: {q} \n
            Data: {LATEST_DATA} \n
        """,
        logprobs= True
    )
    return response['response']


async def response_report(q: str) -> str:
    """
    Just runs answer() and summarizes the CapMemory together
    """
    await summarize()
    result = await answer(q)

    return result

# This makes a loop to retrieve and run a response
async def run_response():
    while True:
        # Offload the typing question so that data does not stop generating:
        q = await asyncio.to_thread(input, "Ask a question: \n")
        # Check for empty:
        if not q.strip():
            continue

        # Check if they wanna stop:
        if q.lower() in ("exit", "quit"):
            print("Okay, bye!")
            break

        r = await response_report(q)
        print(f"I have my answer! \n {r} \n")
        await asyncio.sleep(5) # Wait every five seconds

# Wraps the two asyncio 
async def main():
    await asyncio.gather(
        generator.start_stream(), # This makes the generator make data every two seconds.
        run_response(),
    )

if __name__ == '__main__':
    print("Hi, my name is Jesslyn. I'm listening!")
    asyncio.run(main())
