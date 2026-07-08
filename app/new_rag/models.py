"""
This is where all the pydantic models live!
"""

from pydantic import BaseModel, Field, field_validator, RootModel
from datetime import datetime
from typing import Any, Dict

# A dict of the firefighters ID and their names, for validation
FIREFIGHTER_NAMES = [1, 2, 3]

# A list of the valid entries for CapDecision.window
WINDOW = ['point', 'short', 'long']


# Debating on whether to use this class or not. It uses more tokens than I might need
class Answer(BaseModel): 
    """
    The formatted answer from the Captain to the user
    """
    time: datetime
    answer: str # The answer yay
    confidence: float


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
    window: str
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
    window: str
    firefighters: list[int] # A list of relevant firefighter IDs
    urgency: float

    # The following validate everything :D

    @field_validator('firefighters')
    @classmethod
    def check_exists(cls, v: list[int]) -> list[int]:
        for f in v:
            if int(f) not in FIREFIGHTER_NAMES:
                raise ValueError(f"This firefighter doesn't exist: {f}")
        return v
    
    @field_validator('urgency')
    @classmethod
    def check_range(cls, v:float) -> float:
        if v > 1 or v < 0:
            raise ValueError(f"the urgency value is invalid: {v}")
        return v
    
    @field_validator('window')
    @classmethod
    def check_window(cls, v:str) -> str:
        if v not in WINDOW:
            raise ValueError(f"The window type is invalid: {v}")
        return v

class CapMemory(BaseModel):
    """
    The context window containg the information that is continually updated by the incoming data, which can be
    accessed by the Captain to respond to user queries, and send Querys to the Firefighters
    """
    last_updated: datetime = Field(default_factory=datetime.now)
    conversation: list[dict[str, str]] = [] # The memory of the most recent conversation so far with MAX_TURNS
    data_summary: str = "No prior history yet. See cache." # The summary of what has happened so far!
    firefighter_summary: dict[int, str] = {} # A light summary of what each firefighter is doing/looking like :D

class FF_MEMORY(RootModel[Dict[str, str]]):   
    @field_validator('root', mode='after')
    @classmethod
    def validate_keys_are_allowed_ints(cls, v: Dict[str, str]) -> Dict[str, str]:
        for key in v.keys():
            try:
                int_key = int(key)
            except ValueError:
                raise ValueError(f"Key '{key}' must be a valid integer string.")
            if int_key not in FIREFIGHTER_NAMES:
                raise ValueError(f"Key {int_key} is not allowed. Must be one of {FIREFIGHTER_NAMES}")
        return v
    # Helper property to get the true {int: str} dictionary in Python
    @property
    def as_int_dict(self) -> Dict[int, str]:
        return {int(k): v for k, v in self.root.items()}