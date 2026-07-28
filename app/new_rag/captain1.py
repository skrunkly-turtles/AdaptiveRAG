"""
This is just a temporary thing to sort through the Captain file right now. Agentically, it should do the following:
(1) Read every general summary from the Firefighters, and determines if there are any uses for the 
(2) Sends out to the planner when there are actions that needs to be taken
(3) Updates the Memory Manager every cycle
(4) Changes the cycle as needed in terms of timing, or anything
"""
import asyncio
from models1 import Analysis, Adjust, CACHE_CAP
import generator
import ollama
from firefighters import ff1, ff2, ff3
from datetime import datetime
from typing import Any
from memory_manager import summarize, memory, LATEST_DATA
from planner import make_plan

# The amount of time for each cycle
CYCLE = 10

FIREFIGHTER_NAMES = {1: ff1, 2: ff2, 3: ff3}

THRESHOLD = ["NORMAL", "WARNING", "ALERT"]

CYCLE_GUARDRAILS = {
    "min": 4,
    "max": 45,
    "min_warn": 8
}

# Hehe all the prompts!

WARN_PROMPT = f"""You are a highly precise analytical agent. 
                Given the reports from each firefighter in the prompt, return a JSON file EXACTLY as {Analysis}.
                [INPUTS]
                Current State: A description of the summary of the current environment
                Past Warnings: A dictionary of past warnings that must be taken into consideration
                Firefighter Summaries: A dictionary of firefighter IDs mapped to a description of their states

                [OUTPUTS in JSON Schema]
                threshold: the general state is in {THRESHOLD}, where "NORMAL" indicates minimal to no concerns in the environment, "WARNING" 
                            indicates possible unstable conditions, and "ALERT" indicates that immedate action must be taken by the firefighters.
                description: A description of 1-3 sentences outlining why this threshold was chosen. 
                adjust_ffs: Indicates the firefighters that need a prompt adjustment, depending on some possible alerts.
                
                INSERT EXAMPLE HERE PLEASE
                """

ADJUST_FFS = f"""You are a precise routing agent.
                Given the firefighter_reports, data_summary, and the current warning, return a JSON file EXACTLY as {Adjust}.
                [INPUTS]
                Firefighter: The ID of the firefighter the JSON file is sent to.
                Firefighter Summaries: A dictionary of the summaries from ALL the firefighters
                Current_Det: A dictionary of the current data categories mapped to their deterministic triggers

                [OUTPUT JSON SCHEMA]
                ff_id: The ID of the firefighter. It MUST match the ID in the input
                attention: a list of data that the firefighter should pay more attention to.
                det_numbers: A dictionary of data categories mapped to the NEW values of deterministic triggers. ONLY include 
                            a given category IF its trigger value needs changing. 
            """


client = ollama.AsyncClient()

# This adjusts the firefighter parameters as needed
async def adjust_ffs(analysis: Analysis) -> None:
    """
    This adjusts all the firefighters as needed
    """
    for ff in analysis.adjust_ffs:
        response = await client.generate(
            model = 'qwen2.5:14b',
            system = ADJUST_FFS,
            prompt = f"""
                    Firefighter ID: {ff} \n
                    Current Warning: {analysis.threshold} \n
                    Firefighter Summaries: {memory.firefighter_summary}
                    """
        )
        r = Adjust.model_validate_json(response['response'])

        # SENDING TO THE FIREFIGHTER. I've decided that the new function is called adjust
        FIREFIGHTER_NAMES[r.ff_id].adjust(r)
        

# What's up with this cycle? 
async def is_warning() -> None:
    """
    Assesses the state of the environment depending on the reports from the firefighters. 
    If necessary will call one or several of the following: Planner, det_cycle, and adjust_ffs. 
    """
    response = await client.generate(
        model='qwen2.5:14b',
        system = WARN_PROMPT,
        prompt=f"""Current State: {memory.data_summary} \n
                    Past Warnings: {memory.data_cache} \n
                    Firefighter Summaries: {memory.firefighter_summary} \n
        """,
    )
    r = Analysis.model_validate_json(response['response'])

    # Now we need to call all the actions depending on what the main model has decided.
    if r.adjust_ffs:
        await adjust_ffs(r)
    if r.threshold == "ALERT":
        # AHAHHA CALL THE PLANNER OKAY?
        make_plan(r)
        
    await update_cache(r)
    await det_cycle(r)


# Just updates the cache yay
async def update_cache(analysis: Analysis) -> None:
    """
    Updates memory.data_cache according to the most recent summaries recorded.
    """
    new_data = (analysis.threshold, analysis.desc)
    memory.data_cache.insert(0, new_data)

    if len(memory.data_cache) > CACHE_CAP:
        memory.data_cache.pop()

# Deterministicly changes the cycle that monitors the whole thing yay
async def det_cycle(analysis: Analysis) -> None:
    """
    Adjusts the general CYCLE timeline deterministically depending on the quality of the analysis that was done!
    This is the cycle that determines how often we need a general summary.
    """
    if analysis.threshold == "ALERT":
        global CYCLE 
        CYCLE = max(CYCLE_GUARDRAILS["min"], CYCLE - 10)
    elif analysis.threshold == "WARNING":
        CYCLE = max(CYCLE_GUARDRAILS["min_warn"], int(CYCLE * 0.8))

    
# This is the cycle that loops around and around...
async def monitor() -> None:
    """
    This is where we just...do stuff!
    """
    while True:
        await asyncio.sleep(CYCLE)
        await summarize()
        await is_warning()


async def main():
    await asyncio.gather(
        generator.start_stream(), # This makes the generator make data every two seconds.
        monitor(),
    )


if __name__ == '__main__':
    print("Evaluating the environment!")
    asyncio.run(main())
