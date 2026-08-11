from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal

# A dict of the firefighters ID and their names, for validation
FIREFIGHTER_NAMES = [1, 2, 3]

THRESHOLD = ["NORMAL", "WARNING", "ALERT"]

CACHE_CAP = 10

# Models for the pool maker

class Data(BaseModel):
    """
    All the data that is sent from the generator!
    """
    time: datetime
    hr: int
    o2: float
    elevation: float
    temp: float
    respiration: int
    hrv: float
    body_temp: float
    gait: float

# Models for the get_data 

class Report(BaseModel):
    """
    The report that is sent from the firefighter to get_data
    """
    time: datetime
    data: list # The list of the names of the CSV files we need
    chunks: int # How many chunks we need
    resolution: int # How large of a gap we need in between the chunks (i.e. resolution = 2 means every other point for <chunks> times)

# Models for the Captain


# The loop that determines if action needs to be taken after every summary
class Analysis(BaseModel):
    """
    The report that is evaluated every time a report or summary from the firefighters come in.
    """
    threshold: Literal["NORMAL", "WARNING", "ALERT"]
    type : Literal["none", "internal", "external"]
    confidence: float = Field(..., ge=0.0, lt=100.0)
    desc: str= "" # A short description of why this threshold was chosen
    adjust_ffs: list[int]= [] # A list of all the firefighters that need their prompts adjusted!
    @field_validator("adjust_ffs", mode="before")
    @classmethod
    def coerce_empty_dict(cls, v):
        if v == {}:
            return []
        return v 

class Adjust(BaseModel):
    """
    If the Captain has deemed these firefighters in need of a change, then this is where we do that!
    """
    ff_id: int # The ID of the firefighter yay
    attention: list[str] = [] # Specific aspects the firefighter should pay attention to
    det_numbers: dict[str, list[int|float]] = {} # A dictionary of the deterministic triggers that need changing. 

class Alert(BaseModel):
    """
    The report sent from the Captain to the Planner when there is action that needs to be taken
    """
    time: datetime # When this report was created
    type: str # The type of warning it is
    # PLEASE FINISH THIS AUGH

# Models for Memory Manager

class CapMemory(BaseModel):
    """
    The full memory manager!
    """
    last_updated: datetime = Field(default_factory=datetime.now)
    data_cache: list[tuple[str, str]] = [] # A list of the past warning threshold mapped to a description of what it was about
    data_summary: str = "" # A short description of the current state of the environment 
    firefighter_summary: dict[int, str] = {} # A description of each firefighter, mapped from their id.

# Models for Planner

class Plan(BaseModel):
    """
    The formatted plan that is sent to the users
    """
    warning: str # The short description of what is happenin
    action: str # Detailed description of what each firefighter should do
    data: list[str] # A list of supporting data!

# Models for the Firefighters

class Warn(BaseModel):
    """
    The formatted warning sent from the firefighter to the Captain when a deterministic warning is raised
    """
    type: dict[str, int|float] # The name of the data that is raised mapped to the data value
    warn: str # A short description of what is wrong
