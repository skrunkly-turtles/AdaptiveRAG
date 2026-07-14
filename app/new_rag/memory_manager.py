"""
This file represents the agent whose sole purpose is to manage the Captain Memory, which the 
Captain will retrieve from, to make decisions and answer queries.
The memory will be updated as such:
(1) Every 10 datapoints, the window gets compressed
(2) Updates firefighter_summaries from the 10 datapoints, and also from firefighter summaries from 
    the 
"""
from models import CapMemory, FF_MEMORY
import ollama
from datetime import datetime
import json
import csv

# This is the latest data from the firefighters , for a query.
LATEST_DATA = []

client = ollama.AsyncClient()

MAX_TURNS = 6

memory = CapMemory(
    firefighter_summary={
        1: "Status: None",
        2: "Status: None",
        3: "Status: None"
    }
)

SUMMARY_PROMPT = ("""You are a precise, memory management process. Compress the new incoming interactions, denoted
                  as new_conversation into the existing master rolling history, denoted data_summary.
                  RULES:
                  - Preserve all crucial points, data anomalies, and overarching trends. 
                  - Drop all small talk, repetitive and monotone entries, or irrelevant entries. 
                  - Keep summary under 3 sentences.
                  - Learn from the old summary. This new summary will REPLACE the old summary with its important notes AND new data.

                  """)

FIREFIGHTER_PROMPT = ("""
                      [INPUT GIVEN]
                      New Conversation History: new_conversation
                      Current Firefighter Summaries: Existing ff summaries
                      Incoming Firefighter Updates: New ff summaries
                      
                      [INSTRUCTIONS]
                      Analyze the input data above.
                       Generate a single JSON object where each key is a firefighter's integer ID (e.g., 1, 2, 3)
                       mapped to their updated 2-3 sentence status summary. 
                      Do not include the input keys in your response.
""")


# Compress the conversation_history and updates the summary accordingly
async def compress_window() -> None:

    """
    Update data_summary from CapMemory when more than MAX_TURNS of conversation exists. Takes the oldest
    turns and merges them with the existing data_summary and updates data_summary, then updates data_cache to 
    the most recent MAX_TURNS of conversation.
    """

    # Logging what is happening
    print("Compressing turns!")
    try: 
        response = await client.generate(
        model='qwen2.5:14b',
        system= SUMMARY_PROMPT,
        prompt= f"""
            data_summary: {memory.data_summary} \n
            ff1_data_cache: {memory.data_cache} \n
            new_conversation: {memory.conversation[-MAX_TURNS:]}\n 
        """
    )
        # Update the memory!
        memory.data_summary = response['response']

        # Clear the cache
        if memory.data_cache and len(memory.data_cache) > 1 and 1 in memory.data_cache and len(memory.data_cache[1]) > 7:
            memory.data_cache = []

        # Update the CapMemory to pop the latest stuff only if the summarization actually worked :D
        if len(memory.conversation) >= MAX_TURNS:
            memory.conversation = memory.conversation[-MAX_TURNS:]
        memory.last_updated = datetime.now()
        
    except Exception as e:
        print(f"Compression failed uh oh :( {e}")
    

async def update_ff_summaries() -> None:
    """
    Update memory.firefighter_summaries with incoming new data.
    """

    # Concatonate the summaries from the latest query
    ff_summaries = {}
    if not LATEST_DATA:
        ff_summaries = {
        1 : "Status: None",
        2 : "Status: None",
        3 : "Status: None"
    }
    else:
        for d in LATEST_DATA:
            id = d[0]
            s = d[1]["QUERY SUMMARY"]
            ff_summaries[id] = s
    
    try:
        response = await client.generate(
        model='qwen2.5:14b',
        system= FIREFIGHTER_PROMPT,
        prompt= f"""
            new_conversation: {memory.conversation[-MAX_TURNS:]}\n 
            Existing ff summaries: {memory.firefighter_summary} \n
            New ff summaries: {ff_summaries}
        """,
        format=FF_MEMORY.model_json_schema()
        )
        try:
            response = response['response']
            memory.firefighter_summary = response
        except Exception as e:
            memory.firefighter_summary = response['response']
            print("response not in correct format.")

        # Update the memory yay!
        
        print(memory.firefighter_summary)
        LATEST_DATA[:] = response
    
    except Exception as e:
        print(f"Firefighter summary Updates failed! Caution. {e}")

async def summarize() -> None:
    """
    Summarizes both the firefighters and the window!
    """
    await update_ff_summaries(),
    await compress_window()
    await export_memory_to_csv(memory)



# Just to read what's happening:
async def export_memory_to_csv(memory_obj: CapMemory, filename: str = "memory_validation.csv"):
    """
    Exports the current state of CapMemory to a CSV file for manual validation.
    """
    # Define the headers for your validation file
    headers = ["last_updated", "data_summary", "conversation_json", "firefighter_summary_json"]
    
    try:
        with open(filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            
            # Serialize complex nested types to clean JSON strings so they don't break CSV formatting
            conversation_str = json.dumps(memory_obj.conversation, indent=2)
            ff_summary_str = json.dumps(memory_obj.firefighter_summary, indent=2)
            
            # Format the datetime cleanly
            last_updated_str = memory_obj.last_updated.strftime("%Y-%m-%d %H:%M:%S")
            
            # Write the single memory state row
            writer.writerow({
                "last_updated": last_updated_str,
                "data_summary": memory_obj.data_summary,
                "conversation_json": conversation_str,
                "firefighter_summary_json": ff_summary_str
            })
                    
    except Exception as e:
        print(f"Failed to export memory to CSV: {e}")