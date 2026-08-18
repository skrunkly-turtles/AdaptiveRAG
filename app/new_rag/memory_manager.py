"""
This file represents the agent whose sole purpose is to manage the Captain Memory, which the 
Captain will retrieve from, to make decisions and answer queries.
The memory will be updated as such:
(1) Every 10 datapoints, the window gets compressed
(2) Updates firefighter_summaries from the 10 datapoints, and also from firefighter summaries from 
    the 
"""
from models1 import CapMemory
import ollama
import json
import csv

# This is the latest data from the firefighters , for a query.
LATEST_DATA = []

client = ollama.AsyncClient()

MAX_TURNS = 10

memory = CapMemory(
    firefighter_summary={
        1: "Status: None",
        2: "Status: None",
        3: "Status: None",
        4:"Status: None",
        5: "Status: None",
        6: "Status: None"
    }
)

SUMMARY_PROMPT = ("""You are a precise, memory management process. Read the current environment data and past trends to
                    compress the environment into a concise description of what is happening.
                  RULES:
                  - Preserve all crucial points, data anomalies, and overarching trends. 
                  - Drop all small talk, repetitive and monotone entries, or irrelevant entries. 
                  - Keep summary under 3 sentences.
                  - Learn from the old summary. This new summary will REPLACE the old summary with its important notes AND new data.
                  """)

# Compress the conversation_history and updates the summary accordingly
async def compress_window() -> None:

    """
    Update data_summary from CapMemory when more than MAX_TURNS of conversation exists. Takes the oldest
    turns and merges them with the existing data_summary and updates data_summary, then updates data_cache to 
    the most recent MAX_TURNS of conversation.
    """

    # Logging what is happening
    try: 
        response = await client.generate(
        model='qwen2.5:14b',
        system= SUMMARY_PROMPT,
        prompt= f"""
            data_summary: {memory.data_summary} \n
            past warnings: {memory.data_cache} \n
            firefighter_summaries: {memory.firefighter_summary}\n 
        """
    )
        # Update the memory!
        memory.data_summary = response['response']
        print(memory.firefighter_summary)
        # print(f"MEMORY SUMMARY: \n {memory.data_summary}")
    except Exception as e:
        print(f"Compression failed uh oh :( {e}")
    


async def summarize() -> None:
    """
    Summarizes both the firefighters and the window!
    """
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
            ff_summary_str = json.dumps(memory_obj.firefighter_summary, indent=2)
            
            # Format the datetime cleanly
            last_updated_str = memory_obj.last_updated.strftime("%Y-%m-%d %H:%M:%S")
            
            # Write the single memory state row
            writer.writerow({
                "last_updated": last_updated_str,
                "data_summary": memory_obj.data_summary,
                "firefighter_summary_json": ff_summary_str
            })
                    
    except Exception as e:
        print(f"Failed to export memory to CSV: {e}")