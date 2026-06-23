"""
This is where the LLM lives, and the "brain" of the operation exists. It must do the following:
(1) Determine if the query should retrieve (from store.py):
    (a) the pool of short-term things, 
    (b) the list of trends,
    (c) both 
(2) Respond to the query with relevant information from store.py 
(3) Automatically flag any warnings every 2 seconds either from (1) the incoming packet or (2) a dangerous change in SHORT_TERM_TREND 
"""
import os
import generator
import store
import time
import math
import json
import asyncio 
import random # This is just to make a random query
import ollama # This is my chosen LLM for now
from pydantic import BaseModel
from datetime import datetime

client = ollama.AsyncClient()

# Here are all the prompts we are using!
MAIN_PROMPT = ("""You are a highly cost-effective agent for emergency services. Your responses must be direct, 
    accurate, and completely grounded in the data retrieved. Do not guess numbers - if latency has been prioritized,
    simply say "I don't know" or give clear ballpark ranges. If there is no data, ONLY respond with: "No relevant data yet".
    """)

QUERY_TYPE_PROMPT = ("""You are a precise router. Your only job is to categorize the scope of the query into a single 
                     integer. You will output exactly one integer from this list: [-2, -1, 0, 1, 2]. Do NOT include
                     any other letters, numbers, formatting, or characters. 

                     STEP 1 — Is it a comparison question? (contains "compare", "vs", "versus", "relative to", "compared to")
                            - Comparing current/recent vs all-time/history/minimum/maximum → 0
                            - Comparing current vs recent/short-term only → -1

                    STEP 2 — If not a comparison, which time scope does it focus on?
                            -2 → Asks ONLY about right now / the last reading / the current moment.
                                Includes questions about the current clock time ("what time is it").
                                Key words: "right now", "currently", "current", "latest", "last reading", "current time", "what time".
                            -1 → Asks about the recent past (past minute). Key words: "recently", "short-term".
                            1 → Asks about all-time stats, history, or overall trends.
                                Key words: "average", "all-time", "overall", "minimum", "maximum", "range", "so far", "trend".
                            2 → Greeting, joke, opinion, or completely unrelated to sensor/vital data.
                    
                     Examples:
                     Query: "What is his heart rate right now?" -> -2 
                     Query: "What is their recent elevation average?" -> -1
                     Query: "What is her average O2 stat?" -> 1
                     Query: "How is her current elevation compared to her average elevation?" -> 0
                     Query: "What is the colour of the sky?" -> 2
                     Query: "Tell me a joke" -> 2
    """)

CRITICAL_LOG_QUESTION = ("""Given the extended context and data from SHORT_TERM_TRENDS, give a concise report in this format:
                         Concerning data point(s): the direct statistic that is critical
                         Summary: a 1-2 sentence summary and description
                         
                        Example:
                         Concerning data point(s): hr: 250bpm, temp: 100
                         Summary: Heart rate is dangerously high, possibly due to abnormally high heat. 
                    """)

# Here are the places we are logging all responses, to clear up the terminal!
CRITICAL_RESPONSES = "critical_reports.txt" # The critical reports go here
QUERY_RESPONSES = "query_report.txt" # The query full reports go here!

# The Pydantic base models are here :)
class Query(BaseModel):
    """
    A class representing the query which the Captain agent asks to the Staff agents
    """
    query: str
    urgency: float # This float must be from 0.0 to 1.0
    reason: str

class Report(BaseModel):
    """
    A class representing the response the agent gives to the querying agent
    """
    time: float # How long the response took in seconds
    response: str # The actual response
    data: list[str] # A list of data that it used
    confidence: float # A percentage of how confident the LLM was with the answer.

# We are clearing the txt files
try:
    with open(QUERY_RESPONSES, mode='w') as _file:
        _file.write('')
except Exception as e:
    print("Uh oh, we couldn't clear the query txt file :(")

try:
    with open(CRITICAL_RESPONSES, mode='w') as _file:
        _file.write('')
except Exception as e:
    print("Uh oh, we couldn't clear the critical response txt file :(")

# Log it!
def log_report(r: Report, file: str)-> None:
    """
    Appends new report to critical_report.txt
    """
    with open(file, mode='a') as f:
        f.write(f"\n Time: {str(datetime.now().isoformat())} \n Report: {r.response} \n Time taken: {r.time} | Data used: {r.data} | Confidence: {r.confidence} \n")

# Returns a Query! This is the structure of the output from the first LLM. 
def ask_query() -> Query:
    q = input("Ask a question: ")
    u = round(random.random(), 2)
    r = "this reason will be filled out later. ignore for now"

    return Query(query=q, urgency=u, reason=r)

# Chooses a question based on query.txt. This should be replaced soon with another LLM agent. 
def choose_question() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "query.txt")

    with open(path, "r", encoding='utf-8') as file:
        lines = file.read().splitlines()

        if not lines:
            raise ValueError("query.txt is empty and you are stupid :D")
        question = random.choice(lines)
    print(question)
    return question

# This just finds the confidence the LLM had in the response. This might be useful for the urgency token later
def compute_confidence(response: dict) -> float:
    """
    Return a float which is the average of confidence of each token in the LLM's response
    """
    logprobs = response.get('logprobs', [])

    if not logprobs:
        print("Uh oh, we weren't able to get confidence stats!")
        return -1.0
    try:
        raw_logs = [item['logprob'] for item in logprobs if 'logprob' in item]
        if not raw_logs:
            print("Uh oh, we weren't able to get confidence stats!")
            return -1.0
        con = [math.exp(l) for l in raw_logs]
        return round(sum(con) / len(con), 4)
    
    except (TypeError, KeyError, ValueError) as e:
        print("Uh oh, we weren't able to get confidence stats!")
        return -1.0


# Checks what kind of retrieval we should be doing!
async def type_of_query(query: str) -> int:
    """
    Return an integer based on whether the query is a short_term_trend, long_term_trend, or both. Returns -2 for 
    only the last item, -1 for a short_term only, 1 for long_term only, 0 for both, 2 for no retrieval needed
    """
    start = time.time()

    valid = {-2, -1, 0, 1, 2} # Just for validity checking
    response= await client.generate(
        model='llama3.2:3b', # Switched everything to llama 3.2:3b because why not :)
        system=QUERY_TYPE_PROMPT,
        prompt= query
    )
    r = response['response'].strip()
    end = time.time()
    
    # Value check!
    try:
        result = int(r)
        if result not in valid:
            raise ValueError(f"Unexpected value! {result}")
        print(f"Query type:{result} | Time taken: {round(end - start, 4)}")
        return result
    except (ValueError, KeyError) as e:
        print("Warning! type_of_query failed. Defaulting to 0")
        return 0 # Return both just in case


# This function is responsible for taking in the critical reports when they are created in store.py
async def seen_critical(log: store.Critical) -> Report:
    """
    Return a Report based on the critical report that was found deterministically from store.py
    """
    start = time.time() 
    l = len(store.SHORT_TERM_POOL) - 1
    last_json = store.SHORT_TERM_POOL[l].model_dump()
    # stp_json = json.dumps([p.model_dump() for p in store.SHORT_TERM_POOL], default=str)
    stt_json = json.dumps({k: v.model_dump() for k, v in store.SHORT_TERM_TRENDS.items()}, default=str)

    data = [log.value,  last_json, stt_json] # We can add stp_json to this too
    context_data = ['CRITICAL LOG', "LAST_DATA", 'SHORT_TERM_TRENDS'] # We can add 'SHORT_TERM_POOL' to this too

    response = await client.generate(
        model='llama3.2:3b',
        system=MAIN_PROMPT,
        prompt= f"""
            Context: {data} \n
            Question: {CRITICAL_LOG_QUESTION}
        """,
        logprobs= True
    )
    answer = response['response']
    end = time.time() # End the timer!
    c = compute_confidence(response)

    report = Report(time=round(end-start, 4), response=answer, data=context_data, confidence=c)
    log_report(report, CRITICAL_RESPONSES) # Log it into the txt file
    print(f"There was a critical alert! Check critical_reports for full report!")
    
    return report


# This is the big one! :)
async def response_report(query: Query)-> Report:
    start = time.time() # Start the timer, for data collection reasons
    query_type = await type_of_query(query.query)

    # Now we must run pipelines depending on the type of query we have (format this data later, maybe):
    context_data = []

    # These are the json versions of the dictionaries we had. They are easier for the LLM to read
    stp_json = json.dumps([p.model_dump() for p in store.SHORT_TERM_POOL], default=str)
    stt_json = json.dumps({k: v.model_dump() for k, v in store.SHORT_TERM_TRENDS.items()}, default=str)
    ltt_json = json.dumps({k: v.model_dump() for k, v in store.LONG_TERM_TRENDS.items()}, default=str)
    if not store.SHORT_TERM_POOL:
        last_json = {}
    else:
        l = len(store.SHORT_TERM_POOL) - 1
        last_json = store.SHORT_TERM_POOL[l].model_dump()

    data = []
    if query_type == -2:
        data.append(last_json)

        context_data.append("LAST_DATA")
    if query_type == -1:
        data.append(stp_json)
        data.append(stt_json)
        data.append(last_json)

        context_data.append("SHORT_TERM_POOL")
        context_data.append("SHORT_TERM_TRENDS")
        context_data.append("LAST_DATA")
    elif query_type == 0:
        data.append(stp_json)
        data.append(stt_json)
        data.append(ltt_json)
        data.append(last_json)

        context_data.append("SHORT_TERM_POOL")
        context_data.append("SHORT_TERM_TRENDS")
        context_data.append("LONG_TERM_TRENDS")
        context_data.append("LAST_DATA")
    elif query_type == 1:
        data.append(ltt_json)

        context_data.append("LONG_TERM_TRENDS")
    elif query_type == 2:
        data.append("No context needed")
        context_data.append('No context needed')
    
    response = await client.generate(
        model='llama3.2:3b',
        system=MAIN_PROMPT,
        prompt= f"""
            Context: {data} \n
            Question: {query.query}
        """,
        logprobs= True
    )
    answer = response['response']
    end = time.time() # End the timer!
    c = compute_confidence(response)

    report = Report(time=round(end-start, 4), response=answer, data=context_data, confidence=c)
    log_report(report, QUERY_RESPONSES)
    return report

# This makes a loop to retrieve and run a response
async def run_response():
    while True:
        n = random.random()
        if n > 0.8: # A 20% chance that a query is asked :)

            q= ask_query()
            r = await response_report(q)
            print(f"I have my answer! \n {r.response} \n \n Here are some metrics: Data Used: {r.data} | Time Taken: {r.time} | Confidence: {r.confidence}")
        
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
