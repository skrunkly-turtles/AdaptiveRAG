"""
This is where the LLM lives, and the "brain" of the operation exists. It must do the following:
(1) Determine if the query should retrieve (from store.py):
    (a) the pool of short-term things, 
    (b) the list of trends,
    (c) both 
(2) Respond to the query with relevant information from store.py 
(3) Automatically deterministically flag anything from the new incoming packet from generator.py
"""
import generator
import store
import ollama # This is my chosen LLM for now
from pydantic import BaseModel
from datetime import datetime

