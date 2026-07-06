"""
This is where all the pydantic models live!
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Any


# Debating on whether to use this class or not. It uses more tokens than I might need
class Answer(BaseModel): 
    """
    The formatted answer from the Captain to the user
    """
    time: datetime
    answer: str # The answer yay
    confidence: float

class ReportList(BaseModel):
    """
    The 
    """


class Report(BaseModel):
    """
    The report that is sent from the firefighter to get_data
    """
    time: datetime
    data: list # The list of the names of the CSV files we need
    chunks: int # How many chunks we need
    resolution: int # How large of a gap we need in between the chunks (i.e. resolution = 2 means every other point for <chunks> times)

class Query(BaseModel):
    """
    The query that is sent from the Captain to the Firefighter
    """
    query: str
    urgency: float 
    time: datetime

class Data(BaseModel):
    """
    All the data that is sent from the generator!
    """
    time: datetime
    hr: int
    o2: float
    elevation: float
    temp: float

class Hr(BaseModel):
    """
    The Heart Rate data packet
    """
    time: datetime
    hr: int

class O2(BaseModel):
    """
    The O2 data packet
    """
    time: datetime
    o2: float

class Elevation(BaseModel):
    """
    The Elevation data packet
    """
    time: datetime
    elevation: float

class Temp(BaseModel):
    """
    The temperature data packet
    """
    time: datetime
    temp: float

class CapDecision(BaseModel):
    """
    The decision schema used by the captain containing all its decisions 
    """
    time: datetime
    firefighters: list # The list of firefighters needed
    data: list[Report] # A list of length firefighters, with each item is the Report corresponding to that ff.
    urgency: float

class CapMemory(BaseModel):
    """
    The context window containg the information that is continually updated by the incoming data, which can be
    accessed by the Captain to respond to user queries, and send Querys to the Firefighters
    """
    last_updated: datetime
    conversation: list[dict[str, str]] = [] # The memory of the most recent conversation so far with MAX_TURNS
    data_summary: str = "No prior history yet. See cache." # The summary of what has happened so far!
    data_cache: dict[str, list[Any]] = {} # Data summary!
    firefighter_summary: dict[str, str] = {} # A light summary of what each firefighter is doing/looking like :D

