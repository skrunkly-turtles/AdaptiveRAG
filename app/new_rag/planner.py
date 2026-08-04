"""
This agent is responsible for making a comprehensive action report/alert to the users.
It is only activated when the Captain calls upon it :)
It tells the firefighters what they need to do next only when needed.
"""
import asyncio
import ollama
import captain
from models1 import Plan

PLAN_PROMPT = f"""You are a clear agent. 
            
"""
async def make_plan() -> str:
    """
    The readable action report that is sent to the user!
    """
    print("weeee")
    return("Weee")
