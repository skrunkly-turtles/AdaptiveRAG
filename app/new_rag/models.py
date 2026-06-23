"""
This is where all the pydantic models live!
"""

from pydantic import BaseModel
from datetime import datetime

class Time(BaseModel):
    """
    The TIME token that reprsents when the data should be pulled from, and how large the window should be
    """
    time: str
    window: str

class Report(BaseModel):
    """
    The report that is sent from the firefighter to get_data
    """
    time: datetime
    data: list
    chunks: int
    resolution: int

class Query(BaseModel):
    """
    The query that is sent from the Captain to the Firefighter
    """
    query: str
    urgency: float 
    time: Time

