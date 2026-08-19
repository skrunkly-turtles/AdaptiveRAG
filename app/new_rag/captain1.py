"""
This is just a temporary thing to sort through the Captain file right now. Agentically, it should do the following:
(1) Read every general summary from the Firefighters, and determines if there are any uses for the 
(2) Sends out to the planner when there are actions that needs to be taken
(3) Updates the Memory Manager every cycle
(4) Changes the cycle as needed in terms of timing, or anything
"""
import json
import time
import pool_maker
import math
import asyncio
from models1 import Analysis, Adjust, CACHE_CAP
import generator
import ollama
from firefighters import ff1, ff2, ff3, ff4, ff5, ff6
from memory_manager import summarize, memory
from planner import make_plan
from comms import warning_queue
from eval import get_results, start_stream
from get_data1 import get_data

# Key words 

# JSON Schemas
# The max amount of tokens allowed to generate in a response
MAX_TOKENS = 300

# The amount of time for each cycle
CYCLE = 10

FIREFIGHTER_NAMES = {1: ff1, 2: ff2, 3: ff3, 4:ff4, 5:ff5, 6:ff6}

THRESHOLD = ["NORMAL", "WARNING", "ALERT"]

TYPE = {"none", "internal", "external"}
CYCLE_GUARDRAILS = {
    "min": 4,
    "max": 45,
    "min_warn": 8
}

# Hehe all the prompts!

WARN_PROMPT = f"""You are a highly precise English-only analytical agent. 
                Given the reports from each firefighter in the prompt, determine if the state of the emergency (IF IT 
                EXISTS AT ALL) is internal (a bodily harm concerning only one agent) or external (an environmental danger, 
                where all firefighters should be alerted). Return a JSON file formatted exactly like [EXAMPLES OUTPUT] but with the 
                outputs as outlined in [OUTPUTS in JSON Schema]. Use all the summaries from all firefighters, cross referencing 
                their data to create a comprehensive analysis of the environment.
                [INPUTS]
                Current State: A description of the summary of the current environment
                Past Warnings: A dictionary of past warnings that must be taken into consideration
                Firefighter Summaries: A dictionary of firefighter IDs mapped to a description of their states

                [OUTPUTS in JSON Schema]
                threshold: the general state is in {THRESHOLD}, where "NORMAL" indicates minimal to no concerns in the environment, "WARNING" 
                            indicates possible unstable conditions, and "ALERT" indicates that immedate action must be taken by the firefighters.
                type: the type of concern, if any, in {TYPE}, where "internal" describes a bodily concern (such as a heart attack or fever), 
                    "external" describes an environmental concern (such as a fire), and "none" MUST correspond ONLY and ALWAYS to "NORMAL" threshold.
                confidence: a float describing how sure you are of this condition from 1 - 99. 
                desc: A description of 1 sentence outlining why this threshold was chosen. Make sure to explicitly quote data given. 
                adjust_ffs: Indicates the firefighters that need a prompt adjustment, depending on some possible alerts.
                
                [HOW TO DISTINGUISH INTERNAL FROM EXTERNAL]
                Do not classify based on a single firefighter's heart rate alone - an elevated heart rate by itself is ambiguous and can mean either. Instead:
                - Check ambient readings (temperature, elevation) across ALL firefighters. If ambient temperature or elevation is rising or abnormal for MULTIPLE
                  firefighters at the same time, this is EXTERNAL, even if only one or two firefighters' heart rates have caught up so far - environmental effects on
                  vitals lag behind the environmental change itself.
                - If ambient readings are normal for every firefighter and only ONE firefighter's vitals (heart rate, oxygen, body temp, gait) are abnormal while
                  the others are normal, this is INTERNAL.
                - Weight cross-firefighter correlation over any single firefighter's numbers.

                [EXAMPLE OUTPUT]
                {{"threshold": "WARNING", "type": "internal", "confidence": 87.0, "desc": "Firefighter 2 is reporting rising body temperature readings that exceed baseline at 38 degrees.", "adjust_ffs": [2]}}

                [EXAMPLE OUTPUT - NO ADJUSTMENT NEEDED]
                {{"threshold": "NORMAL", "type": "none", "confidence": 76.4, "desc": "All readings are within normal range.", "adjust_ffs": []}}

                [EXAMPLE OUTPUT - EXTERNAL WARNING]
                {{"threshold": "ALERT", "type": "external", "confidence": 50.3, "desc": "All heart rate (mean 110bpm, mean 106bpm, mean 120bpm) and outer temperature spikes (40, 45, 39 degrees) consistently outside of normal readings, which likely means an external factor.", "adjust_ffs": [1, 2, 3]}}
                """

ADJUST_FFS = f"""You are a precise routing agent.
                Given the firefighter_reports, data_summary, and the current warning, return a JSON file EXACTLY as {json.dumps(Adjust.model_json_schema(), indent=2)}.
                [INPUTS]
                Firefighter ID: The ID of the firefighter the JSON file is sent to.
                Current Warning: The most recent analysis of the general environment 
                Current Deterministic Guardrails: A dictionary of the current data categories mapped to their deterministic triggers
                Firefighter Summaries: A dictionary of the summaries from ALL the firefighters

                [OUTPUT JSON SCHEMA]
                ff_id: The ID of the firefighter. It MUST match the ID in the input
                attention: a list of data that the firefighter should pay more attention to.
                det_numbers: A dictionary of data categories mapped to the NEW values of deterministic triggers. ONLY include 
                            a given category IF its trigger value needs changing. 
            """

DET_WARN = f"""You are a concise English-only agent who has received a deterministic flag which requires urgent attention. 
                Assess the current warning and return ONLY and EXACTLY the JSON: {json.dumps(Analysis.model_json_schema(), indent=2)} format. 

                [INPUTS]
                Firefighter in Danger: The ID of the firefighter that has sent the alert
                Critical Data: A dictionary of the category of data mapped to the value that triggered the warning
                Firefighter Summaries: A description of what is happening to each firefighter
                Environment Summary: The overall description of the environment. 

                [OUTPUTS IN JSON SCHEMA]
                 threshold: the general state is in {THRESHOLD}, where "NORMAL" indicates minimal to no concerns in the environment, "WARNING" 
                            indicates possible unstable conditions, and "ALERT" indicates that immedate action must be taken by the firefighters.
                type: the type of concern, if any, in {TYPE}, where "internal" describes a bodily concern (such as a heart attack or fever), 
                    "external" describes an environmental concern (such as a fire), and "none" MUST correspond ONLY and ALWAYS to "NORMAL" threshold.
                confidence: a float describing how sure you are of this condition from 1 - 100. 
                desc: A description of 1 sentence outlining why this threshold was chosen. 
                adjust_ffs: Indicates the firefighters that need a prompt adjustment, depending on some possible alerts.

                [EXAMPLE OUTPUT]
                {{"threshold": "WARNING", "type": "internal", "confidence": 87.0, "desc": "Firefighter 2 is reporting rising body temperature readings that exceed baseline.", "adjust_ffs": [2]}}

                [EXAMPLE OUTPUT - NO ADJUSTMENT NEEDED]
                {{"threshold": "NORMAL", "type": "none", "confidence": 76.4, "desc": "All readings are within normal range.", "adjust_ffs": []}}

                [EXAMPLE OUTPUT - EXTERNAL WARNING]
                {{"threshold": "ALERT", "type": "external", "confidence": 50.3, "desc": "All heart rate and outer temperature spikes consistently outside of normal readings, which likely means an external factor.", "adjust_ffs": [1, 2, 3]}}
"""

client = ollama.AsyncClient()

# This adjusts the firefighter parameters as needed
async def adjust_ffs(analysis: Analysis) -> None:
    """
    This adjusts all the firefighters as needed
    """
    # for ff in analysis.adjust_ffs:
        
    for ff in analysis.adjust_ffs:
        try:
            start_time = time.perf_counter()
            response = await client.generate(
                model = 'qwen2.5:14b',
                system = ADJUST_FFS,
                prompt = f"""
                        Firefighter ID: {ff} \n
                        Current Warning: {analysis.threshold} \n
                        Current Deterministic Guardrails: {FIREFIGHTER_NAMES[ff].DET_WARNINGS}
                        Firefighter Summaries: {memory.firefighter_summary}
                        """,
                format="json",
                options={
                    # 'num_predict': MAX_TOKENS,
                    'temperature': 0.2 # A tighter temp means that it rambles less
                }
            )
            duration = round((time.perf_counter() - start_time), 2)
            r = Adjust.model_validate_json(response['response'])
        except Exception as e:
            print(f"adjust_ffs has failed for ff{ff}: {e}")
            continue
        print(f"adjusting {ff} took {duration} time")
        # print(r)
        # SENDING TO THE FIREFIGHTER. I've decided that the new function is called adjust
        await FIREFIGHTER_NAMES[r.ff_id].adjust(r, CYCLE)

# When we receive deterministic warnings from the firefighters, this function is called. 

async def receive_warn() -> None:
    """
    This function wakes up only when there is a deterministic trigger from the firefighters. 
    It will assess the situation similar to is_warning() and make changes accordingly.
    """
    # Ok when it is called, it needs to first get the ID and the corresponding warning from the firefighter
    while True:
        ff_id, warning = await warning_queue.get()
        try:
            start_time = time.perf_counter()
            response = await asyncio.wait_for(
                client.generate(
                    model='qwen2.5:14b',
                    system = DET_WARN,
                    prompt = f"""
                            Firefighter in Danger: {ff_id} \n
                            Critical Data: {warning.type} \n
                            Firefighter Summaries: {memory.firefighter_summary} \n
                            Environment Summary: {memory.data_summary}
                            """,
                    options={
                        'num_predict': MAX_TOKENS,
                        'temperature': 0.2 # A tighter temp means that it rambles less
                    },
                    format="json"
                ),
                timeout=25 # The max amount that they await for
            )
            duration = round((time.perf_counter() - start_time), 2) + max(memory.firefighter_durations)
            r = Analysis.model_validate_json(response['response'])
            print(f"received warning:    {r.desc} type: {r.type} \n ")
            await det_cycle(r)
            if r.adjust_ffs != []:
                    await adjust_ffs(r)
            if r.threshold == "ALERT":
                    # AHAHHA CALL THE PLANNER OKAY?
                    await make_plan(r)

            await update_cache(r)
            await get_results(r.type, r.confidence, duration, r.adjust_ffs)

        # If something doesn't work...
        except asyncio.TimeoutError:
            print(f"receive_warn timed out for ff {ff_id}")
        except Exception as e:
            print(f"receive_warn failed to process warning for ff {ff_id}: {e}")


# What's up with this cycle? 
async def is_warning() -> None:
    """
    Assesses the state of the environment depending on the reports from the firefighters. 
    If necessary will call one or several of the following: Planner, det_cycle, and adjust_ffs. 
    """
    try:
        start_time = time.perf_counter()
        response = await client.generate(
            model='qwen2.5:14b',
            system = WARN_PROMPT,
            prompt=f"""Current State: {memory.data_summary} \n
                        Past Warnings: {memory.data_cache} \n
                        Firefighter Summaries: {memory.firefighter_summary} \n
            """,
            format="json",
            options={
                'num_predict': MAX_TOKENS,
                'temperature': 0.2 # A tighter temp means that it rambles less
            }
        )
        duration = round((time.perf_counter() - start_time), 2)
        r = Analysis.model_validate_json(response['response'])
        print(f" regular check:        {r.desc} type: {r.type}")
    # In case something goes wrong
    except asyncio.TimeoutError:
        print(f"is_warning timed out")
        return
    except Exception as e:
        print(f"is_warning failed: {e}")
        return
    # print(f"regular cycle checks: {r}")
    await det_cycle(r)

    # Now we need to call all the actions depending on what the main model has decided.
    if r.adjust_ffs:
        await adjust_ffs(r)
    if r.threshold == "ALERT":
        # AHAHHA CALL THE PLANNER OKAY?
        await make_plan(r)

    await update_cache(r)

    await get_results(r.type, r.confidence, duration, r.adjust_ffs)


# Just updates the cache yay
async def update_cache(analysis: Analysis) -> None:
    """
    Updates memory.data_cache according to the most r   ecent summaries recorded.
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
    global CYCLE
    if analysis.threshold == "ALERT": 
        CYCLE = max(CYCLE_GUARDRAILS["min"], CYCLE - 10)
    elif analysis.threshold == "WARNING":
        CYCLE = max(CYCLE_GUARDRAILS["min_warn"], int(CYCLE * 0.8))
    elif analysis.threshold == "NORMAL":
        CYCLE = min(CYCLE_GUARDRAILS["max"], math.ceil(CYCLE * 1.1))

    
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
    await pool_maker.clear_db()
    await pool_maker.init_db()

    background = [
        asyncio.create_task(ff1.main()),
        asyncio.create_task(ff2.main()),
        asyncio.create_task(ff3.main()),
        asyncio.create_task(ff4.main()),
        asyncio.create_task(ff5.main()),
        asyncio.create_task(monitor()),
        asyncio.create_task(ff6.main()),
        asyncio.create_task(receive_warn()),
    ]

    result = await start_stream()  # only this one is expected to finish

    for t in background:
        t.cancel()
    await asyncio.gather(*background, return_exceptions=True)

    return result

if __name__ == '__main__':
    asyncio.run(main())
