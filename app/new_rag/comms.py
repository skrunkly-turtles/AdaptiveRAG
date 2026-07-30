"""
I keep using circular functions and this python file will ensure that I stop doing that. 
This is the common  python file for all the functions that need to go both ways :)
"""
import asyncio

# Captain -> specific firefighter (adjustments)
adjust_queues: dict[int, asyncio.Queue] = {}

# Firefighter -> Captain (warnings/reports)
warning_queue: asyncio.Queue = asyncio.Queue()

def get_adjust_queue(ff_id: int) -> asyncio.Queue:
    if ff_id not in adjust_queues:
        adjust_queues[ff_id] = asyncio.Queue()
    return adjust_queues[ff_id]