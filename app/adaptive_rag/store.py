"""
This Python file holds two types of data: 
(1) A pool of short term cached packets from the past 60 seconds,
(2) A list of the long-term trends for each category
It is responsible for taking the data from generator.py and storing it properly in the pool and the list
"""
from pydantic import BaseModel
from datetime import datetime
import asyncio
import generator
import demo
import csv
import os

SHORT_TERM_POOL = [] # This is a list of Sensors of data from the past 60 seconds
LONG_TERM_TRENDS = {} # This is a dictionary of all the Trends from each category of all time
SHORT_TERM_TRENDS = {} # This is a dictionary of all the Trends from each category only from the SHORT_TERM_POOL
CRITICAL_CSV = "critical_readings_log.csv" #A running csv file that will track all the critical logs

# This is just the model that holds critical information for CRITICAL_CSV
class Critical(BaseModel):
      """
      A class to represent a csv file record of all the critical, deterministic readings
      """
      time: datetime
      metric: str
      value: float
      severity: str
      description: str

# Clears the CSV file once!
try:
    with open(CRITICAL_CSV, mode='w', newline='', encoding='utf-8') as _file:
        _writer= csv.DictWriter(_file, fieldnames=list(Critical.model_fields.keys()))
except Exception as e:
    print("Uh oh, we couldn't clear the csv file :(")

# This method just adds a new reading to the csv
async def log_critical(reading: Critical, file_path: str=CRITICAL_CSV) -> None:
      asyncio.create_task(demo.seen_critical(reading)) # Alerts the LLM that we have logged a new critical alert
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)

# This class validates the data being updated in both LONG_TERM_TRENDS and SHORT_TERM_TRENDS dictionary
class Trend(BaseModel):
     """
     A class to represent the long term trends for a given category of data.
     """
     model_config = {"frozen": False}
     min: float
     max: float
     avg: float
     total: int


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
async def process_incoming(data:dict) -> None:
    """
    Validates the data that comes in from generator.py
    """
    # Validate the data
    packet = Sensor(**data)
    generator.record_runs(packet) # To log into the temporary log 
    
    # Deterministic alerts!
    if packet.hr < 20 or packet.hr > 240:
        recent = round(SHORT_TERM_TRENDS['hr'].avg, 4) if 'hr' in SHORT_TERM_TRENDS else ""
        alarm = Critical(
            time=packet.time,
            metric='hr',
            value=packet.hr,
            severity='HIGH',
            description= f"Heart rate is abnormal, at {packet.hr} bpm when recent average has been {recent}"
        )
        await log_critical(alarm)
    
    if packet.o2 < 95 and packet.o2 > 90:
        recent = round(SHORT_TERM_TRENDS['o2'].avg, 4) if 'o2' in SHORT_TERM_TRENDS else ""
        alarm = Critical(
            time = packet.time,
            metric = 'o2',
            value = packet.o2,
            severity='MEDIUM',
            description=f"O2 stats are low, at {packet.o2} when recent average has been {recent}"
        )
        await log_critical(alarm)

    if packet.o2 < 90:
        recent = round(SHORT_TERM_TRENDS['o2'].avg, 4) if 'o2' in SHORT_TERM_TRENDS else ""
        alarm = Critical(
            time = packet.time,
            metric = 'o2',
            value = packet.o2,
            severity='HIGH',
            description=f"O2 stats are dangerously low, at {packet.o2} when recent average has been {recent}"
        )
        await log_critical(alarm)
    
    if packet.temp > 40 and packet.temp < 100:
        alarm = Critical(
            time = packet.time,
            metric = 'temp',
            value = packet.temp,
            severity = 'MEDIUM',
            description=f"Temperature is a little high, at {packet.temp}"
        )
        await log_critical(alarm)
    
    if packet.temp > 100:
        alarm = Critical(
            time = packet.time,
            metric = 'temp',
            value = packet.temp,
            severity = 'HIGH',
            description=f"temperature is extremely high, at {packet.temp}"
        )
        await log_critical(alarm)

    # We also want to add to the short term pool, and take away from the oldest value
    if len(SHORT_TERM_POOL) > 30:
        SHORT_TERM_POOL.pop(0)
    SHORT_TERM_POOL.append(packet)

    # We are adding to, and updating, the long term trends and short term trend
    longtrends(packet)
    shorttrends()
    

def longtrends(packet: Sensor) -> None:
    """
    Modify LONG_TERM_TRENDS with the new updated packet.
    """
    if "hr" not in LONG_TERM_TRENDS: # This means this is the first package ever!
        hr_packet = Trend(min=packet.hr, max=packet.hr, avg=float(packet.hr), total=1)
        o2_packet = Trend(min=packet.o2, max=packet.o2, avg=float(packet.o2), total=1)
        el_packet = Trend(min=packet.elevation, max=packet.elevation, avg=float(packet.elevation), total=1)
        temp_packet = Trend(min=packet.temp, max=packet.temp, avg=float(packet.temp), total=1)

        LONG_TERM_TRENDS['hr'] = hr_packet
        LONG_TERM_TRENDS['o2'] = o2_packet
        LONG_TERM_TRENDS['elevation'] = el_packet
        LONG_TERM_TRENDS['temp'] = temp_packet

    else:
        # First we verify the max and mins with the current packet
        if packet.hr < LONG_TERM_TRENDS['hr'].min:
            LONG_TERM_TRENDS['hr'].min = packet.hr
        if packet.hr > LONG_TERM_TRENDS['hr'].max:
            LONG_TERM_TRENDS['hr'].max = packet.hr
        
        if packet.o2 < LONG_TERM_TRENDS['o2'].min:
            LONG_TERM_TRENDS['o2'].min = packet.o2
        if packet.o2 > LONG_TERM_TRENDS['o2'].max:
            LONG_TERM_TRENDS['o2'].max = packet.o2
        
        if packet.temp < LONG_TERM_TRENDS['temp'].min:
            LONG_TERM_TRENDS['temp'].min = packet.temp
        if packet.temp > LONG_TERM_TRENDS['temp'].max:
            LONG_TERM_TRENDS['temp'].max = packet.temp

        if packet.elevation < LONG_TERM_TRENDS['elevation'].min:
            LONG_TERM_TRENDS['elevation'].min = packet.elevation
        if packet.elevation > LONG_TERM_TRENDS['elevation'].max:
            LONG_TERM_TRENDS['elevation'].max = packet.elevation

         # We add one to the count
        for x in LONG_TERM_TRENDS:
            LONG_TERM_TRENDS[x].total += 1

        # We now update the averages!
        LONG_TERM_TRENDS['hr'].avg = LONG_TERM_TRENDS['hr'].avg + (packet.hr - LONG_TERM_TRENDS['hr'].avg)/LONG_TERM_TRENDS['hr'].total
        LONG_TERM_TRENDS['o2'].avg = LONG_TERM_TRENDS['o2'].avg + (packet.o2 - LONG_TERM_TRENDS['o2'].avg)/LONG_TERM_TRENDS['o2'].total
        LONG_TERM_TRENDS['elevation'].avg = LONG_TERM_TRENDS['elevation'].avg + (packet.elevation - LONG_TERM_TRENDS['elevation'].avg)/LONG_TERM_TRENDS['elevation'].total
        LONG_TERM_TRENDS['temp'].avg = LONG_TERM_TRENDS['temp'].avg + (packet.temp - LONG_TERM_TRENDS['temp'].avg)/LONG_TERM_TRENDS['temp'].total

def shorttrends()-> None:
    """
    Modify SHORT_TERM_TRENDS with the new incoming packet
    """

    if len(SHORT_TERM_POOL) > 0:
        n = SHORT_TERM_POOL[0]
        SHORT_TERM_TRENDS['hr'] = Trend(min=n.hr, max=n.hr, avg=n.hr, total=1)
        SHORT_TERM_TRENDS['o2'] = Trend(min=n.o2, max=n.o2, avg=n.o2, total=1)
        SHORT_TERM_TRENDS['temp'] = Trend(min=n.temp, max=n.temp, avg=n.temp, total=1)
        SHORT_TERM_TRENDS['elevation'] = Trend(min=n.elevation, max=n.elevation, avg=n.elevation, total=1)
        # For ease of naming
        hr = SHORT_TERM_TRENDS['hr']
        o2 = SHORT_TERM_TRENDS['o2']
        temp = SHORT_TERM_TRENDS['temp']
        el = SHORT_TERM_TRENDS['elevation']

        hr.total, o2.total, el.total, temp.total = len(SHORT_TERM_POOL), len(SHORT_TERM_POOL), len(SHORT_TERM_POOL), len(SHORT_TERM_POOL)
            
        hr_count = 0
        o2_count = 0
        temp_count = 0
        el_count = 0
        for i in SHORT_TERM_POOL:
            if i.hr < hr.min:
                hr.min = i.hr
            if i.hr > hr.max:
                hr.max = i.hr
            
            if i.o2 < o2.min:
                o2.min = i.o2
            if i.o2 > o2.max:
                o2.max = i.o2
            
            if i.temp < temp.min:
                temp.min = i.temp
            if i.temp > temp.max:
                temp.max = i.temp
            
            if i.elevation < el.min:
                el.min = i.elevation
            if i.elevation > el.max:
                el.max = i.elevation
            
            hr_count += i.hr
            o2_count += i.o2
            temp_count += i.temp
            el_count += i.elevation
        
        hr.avg = hr_count/hr.total
        o2.avg = o2_count/o2.total
        temp.avg = temp_count/temp.total
        el.avg = el_count/el.total
            