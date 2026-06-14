"""
This is where the LLM lives, and the "brain" of the operation exists. It must do the following:
(1) Determine if the query should retrieve (from store.py):
    (a) the pool of short-term things, 
    (b) the list of trends,
    (c) both 
(2) Respond to the query with relevant information from store.py 
(3) Automatically flag any warnings every 2 seconds either from (1) the incoming packet or (2) a dangerous change in SHORT_TERM_TREND 
"""
import generator
import store
import time
import math
import random # This is just to make a random query
import ollama # This is my chosen LLM for now
from pydantic import BaseModel
from datetime import datetime

MAIN_PROMPT = ("""You are a highly cost-effective agent for emergency services. Your responses must be direct, 
    accurate, and completely grounded in the data retrieved. Do not guess numbers - if latency has been prioritized,
    simply say "I don't know" or give clear ballpark ranges.
    """)

QUERY_TYPE_PROMPT = ("""You are a precise router. Your only job is to categorize the scope of the query into a single 
                     integer. You will output exactly one integer from this list: [-1, 0, 1, 2]. Do NOT include
                     any other letters, numbers, formatting, or characters. 

                     Here is what each number means:
                     -1: Choose this if the query uses words such as "right now", "currently", "recently", or semantics
                        which suggest ONLY data from the short term is needed.
                     1: Choose this if the query uses words such as: "average", "all-time", and focuses on the overall
                        history, maximums, minimums, trends, or past behaviour. 
                     0: Choose this if the query references or compares short term behaviour or the present moment,
                      with overall history and the past. 
                     2: Choose this if the query is a meta-question, a greeting, a conversation, or is otherwise unrelated
                        to concrete sensor data. 
                     
                     Examples:
                     Query: "What is his heart rate right now?" -> -1 
                     Query: "What is her average O2 stat?" -> 1
                     Query: "How is her current elevation compared to her average elevation?" -> 0
                     Query: "What is the colour of the sky?" -> 2
    """)
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


# Returns a Query! This is the structure of the output from the first LLM. 
def ask_query() -> Query:
    q = choose_question()
    u = round(random.random(), 2)
    r = "this reason will be filled out later. ignore for now"

    return Query(query=q, urgency=u, reason=r)

# Chooses a question based on query.txt. This should be replaced soon with another LLM agent. 
def choose_question() -> str:
    with open("query.txt", "r") as file:
        lines = file.read().splitlines()
        question = random.choice(lines)
    return question

# This just finds the confidence the LLM had in the response. This might be useful for the urgency token later
def compute_confidence(response: dict) -> float:
    """
    Return a float which is the average of confidence of each token in the LLM's response
    """
    logprobs = response.get('prompt_eval_results') or response.get('logprobs', [])
    if not logprobs:
        print("unable to find confidence")
        return -1.0
    probs = [math.exp(logs) for logs in logprobs]
    return round(sum(probs) / len(probs), 4)


# Checks what kind of retrieval we should be doing!
def type_of_query(query: str) -> int:
    """
    Return an integer based on whether the query is a short_term_trend, long_term_trend, or both. Returns -1 for 
    a short_term only, 1 for long_term only, 0 for both, 2 for no retrieval needed
    """
    valid = {-1, 0, 1, 2} # Just for validity checking
    response=ollama.generate(
        model='phi3', # We use a tiny LLM for this task, because it should be relatively simple :)
        system=QUERY_TYPE_PROMPT,
        prompt=query
    )
    r = response['response'].strip()
    
    # Value check!
    try:
        result = int(r)
        if result not in valid:
            raise ValueError(f"Unexpected value! {result}")
        return result
    except (ValueError, KeyError) as e:
        print("Warning! type_of_query failed. Defaulting to 0")
        return 0 # Return both just in case

# This is the big one! :)
def response_report(query: Query)-> Report:
    start = time.time() # Start the timer, for data collection reasons
    query_type = type_of_query(query.query)

    # Now we must run pipelines depending on the type of query we have (format this data later, maybe):
    context_data = []
    data = []
    if query_type == -1:
        data.append(str(store.SHORT_TERM_POOL))
        data.append(str(store.SHORT_TERM_TRENDS))

        context_data.append("SHORT_TERM_POOL")
        context_data.append("SHORT_TERM_TRENDS")
    elif query_type == 0:
        data.append(str(store.SHORT_TERM_POOL))
        data.append(str(store.SHORT_TERM_TRENDS))
        data.append(str(store.LONG_TERM_TRENDS))

        context_data.append("SHORT_TERM_POOL")
        context_data.append("SHORT_TERM_TRENDS")
        context_data.append("LONG_TERM_TRENDS")
    elif query_type == 1:
        data.append(str(store.LONG_TERM_TRENDS))

        context_data.append("LONG_TERM_TRENDS")
    elif query_type == 2:
        data.append("No context needed")
        context_data.append('No context needed')
    
    response = ollama.generate(
        model='llama3.2:3b',
        system=MAIN_PROMPT,
        prompt= f"""
            Context: {data} \n
            Question: {query.query}
        """,
        logprobs=True
    )
    answer = response['response']
    end = time.time() # End the timer!
    c = compute_confidence(response)

    report = Report(time=round(end-start, 4), response=answer, data=context_data, confidence=c)
    return report


if __name__ == '__main__':
    print("Ok I'm listening!")

    while True:
        generator.start_stream() # This makes the generator make data every two seconds.

