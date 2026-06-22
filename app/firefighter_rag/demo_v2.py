"""
VERSION TWO OF DEMO.PY (TO BE TESTED). 
Edits: This version has a more flexible retrieval method, allowing the LLM to dynamically decide with both
(1) More types of data pools, and (2) How many of the data pools it wishes to retrieve from.


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

# The new QUERY_TYPE_PROMPT
def build_query_type_prompt() -> str:
    context = store.get_context()
    for l in context: # DOuble check haha
        print(l)

    return f"""You are a precise router. Select ONLY the integers which correspond to data needed to answer the query. Prioritize options with 
                        lowest sizes while still maintaining high confidence. 

                     Here is what each number which can be added to QueryType items means:
                     0: (All the data from all categories from the past 60 seconds) | Size: {context[0]}
                     1: (min, max, avg, num items summaries for EACH category ONLY from the past 60 seconds) | Size: {context[1]}
                     2: (min, max, avg, total items summaries for EACH category from ALL TIME) | Size: {context[2]}
                     3: (CATEGORICAL_CONGLOMERATE['hr'], a list of ALL data from Heart Rate) | Size: {context[3]}
                     4: (CATEGORICAL_CONGLOMERATE['o2'], a list of ALL data from Oxygen) | Size: {context[4]}
                     5: (CATEGORICAL_CONGLOMERATE['temp'], a list of ALL data from Temperature) | Size: {context[5]}
                     6: (CATEGORICAL_CONGLOMERATE['elevation'], a list of ALL data from Elevation) | Size: {context[6]}
                     7: (A dictionary of ONLY the most recent data.) | Size: {context[7]}
                     
                     Examples:
                     Query: "What is his heart rate right now?" -> [7]
                     Query: "What is their recent elevation average compared to their elevation average of all time?" -> [1, 2]
                     Query: "What is her average O2 stat?" -> [2]
                     """

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

# This is just a list, but in a json file for ollama to output in this format.
list_schema = {
    "type": "array",
    "items":{
        "type": "integer",
        "minimum": 0,
        "maximum": 7,
    },
    "uniqueItems": True
}

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
async def type_of_query(query: str) -> list:
    """
    Return an integer based on whether the query is a short_term_trend, long_term_trend, or both. Returns -2 for 
    only the last item, -1 for a short_term only, 1 for long_term only, 0 for both, 2 for no retrieval needed
    """
    start = time.time()

    valid = {0, 1, 2, 3, 4, 5, 6, 7} # Just for validity checking
    response= await client.generate(
        model='llama3.2:3b', # Switched everything to llama 3.2:3b because why not :)
        system= build_query_type_prompt(),
        prompt=f""" Identify and return the minimum required data, given the Size of each data, to answer {query} with high confidence """,
        format= list_schema
    )
    r = response['response'].strip()
    end = time.time()
    
    # Value check!
    try:
        result = json.loads(r)
        if any(i not in valid for i in result):
            raise ValueError(f"Unexpected value! {result}")
        print(f"Data needed:{result} | Time taken: {round(end - start, 4)}")
        return result
    except (ValueError, KeyError) as e:
        print("Warning! type_of_query failed. Defaulting to 0")
        return [1] 


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

    data = [log.description,  last_json, stt_json] # We can add stp_json to this too
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
    hr_json = json.dumps(store.CATEGORICAL_CONGLOMERATE['hr'], default=str)
    o2_json = json.dumps(store.CATEGORICAL_CONGLOMERATE['o2'], default=str)
    temp_json = json.dumps(store.CATEGORICAL_CONGLOMERATE['temp'], default=str)
    el_json = json.dumps(store.CATEGORICAL_CONGLOMERATE['elevation'], default=str)
    l = len(store.SHORT_TERM_POOL) - 1
    last_json = store.SHORT_TERM_POOL[l].model_dump()

    # Now we put all the json files and match them to a number from query_type
    collection = {0: stp_json, 1: stt_json, 2:ltt_json, 3: hr_json, 4:o2_json, 5:temp_json, 6:el_json, 7:last_json}
    data = []
    
    for i in query_type:
        data.append(collection[i])
    
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
