"""
This Python file sorts the data logged in generator.py into pools as defined in the data folder. 
It is all deterministic:
(1) A large raw data pool
(2) Pools specificed for each category
(3) A large file of summaries/trends/statistics. 
"""
import asyncio
import csv
import os
from models import Data, Hr, O2, Elevation, Temp

# The CSV pools for each of the data types
ALL_LOG = 'data/all_logs.csv'
SUMMARIES = 'data/summaries.csv'
ELEVATION = 'data/elevation.csv'
HR = 'data/hr.csv'
O2_LOG = 'data/o2.csv'
TEMP = 'data/temp.csv'

# Clear all the logs when we first open them!
paths = [ALL_LOG, SUMMARIES, HR, O2_LOG, ELEVATION, TEMP]

for path in paths:
    try:
        with open(path, mode='w', newline='', encoding='utf-8') as _file:
            _file.write("")
    except Exception as e:
        print(f"Uh oh, we couldn't clear the {path} file :(")

# Add the new Data packet into the csv files
async def log_all(reading: Data, file_path: str=ALL_LOG) -> None:
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)

async def log_all(reading: Data, file_path: str=SUMMARIES) -> None:
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)

async def log_hr(reading: Data, file_path: str=HR) -> None:
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)

async def log_o2(reading: Data, file_path: str=O2_LOG) -> None:
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)

async def log_el(reading: Data, file_path: str=ELEVATION) -> None:
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)

async def log_temp(reading: Data, file_path: str=TEMP) -> None:
      file_exists = os.path.exists(file_path)

      with open(file_path, mode='a', newline = '', encoding='utf-8') as file:
            fieldnames = list(reading.model_fields.keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row_data = reading.model_dump(mode='json')
            writer.writerow(row_data)


# Process the incoming logs every 2 seconds
async def process_incoming(data: dict) -> None:
    """
    Process the data and sort it into pools
    """
    # First we add the all log, and the categorical pools
    new = Data(**data)
    hr = Hr(time=new.time, hr=new.hr)
    o2 = O2(time=new.time, o2=new.o2)
    elevation = Elevation(time=new.time, elevation=new.elevation)
    temp = Temp(time=new.time, temp=new.temp)
    log_all(new)
    log_hr(hr)
    log_o2(o2)
    log_el(elevation)
    log_temp(temp)
    
    # Now we make deterministic summaries 