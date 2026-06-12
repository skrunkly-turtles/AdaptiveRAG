"""
This Python file holds two types of data: 
(1) A pool of short term cached packets from the past 60 seconds,
(2) A list of the long-term trends for each category
It is responsible for taking the data from generator.py and storing it properly in the pool and the list
"""
from pydantic import BaseModel
from datetime import datetime
import generator
import csv
import os

SHORT_TERM_POOL = [] # This is an ordered list of dictionaries of data from the past 60 seconds
LONG_TERM_TRENDS = {} # This is a dictionary of all the trends from each category
CRITICAL_CSV = "critical_readings_log.csv" #A running csv file that will track all the critical logs

class Critical(BaseModel):
      """
      A class to represent a csv file record of all the critical, deterministic readings
      """
      time: datetime
      metric: str
      value: float
      severity: str
      description: str

def log_critical(reading: Critical, file_path: str=CRITICAL_CSV) -> None:
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)

# This class validates the types that are incoming so we don't have any bad data
class Sensor(BaseModel):
    """
    A class to represent a given sensor data retrieved from generator.py
    """
    time: datetime
    hr: int
    o2: float
    elevation: float
    temp: float

# This is where we process the data!
def process_incoming(data:dict) -> None:
        """
        Validates the data that comes in from generator.py
        """
        # Validate the data
        packet = Sensor(**data)

        # Add to the short term pool
        SHORT_TERM_POOL.append(packet)
        
        # Deterministic alerts!
        if packet.hr < 20:
              alarm = Critical(
                    time=packet.time,
                    metric='hr',
                    value=packet.hr,
                    severity='HIGH',
                    description= f"dead"
                )