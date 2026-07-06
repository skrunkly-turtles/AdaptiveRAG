"""
This file represents the Captain, which oversees all the firefighters. It is responsible for:
(1) Maintaining a memory and a cache of conversation and top-level summaries of the firefighters
(2) Reading the query and delivering response
(3) Sending the query to the correct firefighters, determining TIME, and urgency.
"""

import asyncio
from models import Time, Query, CapDecision, CapMemory, Answer
import generator
import ollama
import random

client = ollama.AsyncClient()
memory = CapMemory(
    firefighter_summary={
        "ff1": "Status: None",
        "ff2": "Status: None"
    }
)

# The maximum number of raw messages to keep in the context prompt
MAX_TURNS = 6

# This is the system prompt
SYS_PROMPT = (""" You are a concise agent. 
              
              """)

SUMMARY_PROMPT = ("""sum
                  
                  """)

# Compress the conversation_history and updates the summary accordingly
async def compress_window(self) -> None:
    """
    Update data_summary from CapMemory when more than MAX_TURNS of conversation exists. Takes the oldest
    turns and merges them with the existing data_summary and updates data_summary, then updates data_cache to 
    the most recent MAX_TURNS of conversation.
    """
    # Logging what is happening
    print("Compressing turns!")
    try: 
        response = await client.generate(
        model='llama3.2:3b',
        system= SUMMARY_PROMPT,
        prompt= f"""
            Context: {data} \n
            Question: {query.query}
        """,
        logprobs= True
    )
    except Exception as e:
        print("Compression failed uh oh :(")
    raise NotImplementedError

# Answers the query given all the data
async def answer(q: str) -> str:
    """
    Return the answer yay!
    """
    print("Pouring water down the drain...")
    await client.generate(
        model='llama3.2:3b',
        system=SYS_PROMPT,
        prompt= f"""
            Context: {data} \n
            Question: {query.query}
        """,
        logprobs= True
    )
    raise NotImplementedError

async def response_report(q: str) -> str:
    """
    Just runs answer() and compress_window() together
    """
    await asyncio.gather(
        answer(q),
        compress_window()
    )

# This makes a loop to retrieve and run a response
async def run_response():
    while True:
        r = await response_report(input("Ask a question: \n"))
        print(f"I have my answer! \n {r} \n")
        
        await asyncio.sleep(5) # Wait every five seconds

# Wraps the two asyncio 
async def main():
    await asyncio.gather(
        generator.record_runs(), # This makes the generator make data every two seconds.
        run_response(),
    )

if __name__ == '__main__':
    print("Hi, my name is Jesslyn. I'm listening!")
    asyncio.run(main())
