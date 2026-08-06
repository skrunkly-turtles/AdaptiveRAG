"""
This agent is responsible for making a comprehensive action report/alert to the users.
It is only activated when the Captain calls upon it :)
It tells the firefighters what they need to do next only when needed.
"""
import ollama
from memory_manager import memory
from models1 import Plan, Analysis

client = ollama.AsyncClient()

PLAN_PROMPT = f"""You are a clear and grounded agent focusing on creating a readable action plan for the firefighters.
            [INPUTS]
            desc: A short description of what is happening in the environment that has caused this alert to be raised
            adjust_ffs: The firefighters that are involved in this alert. Your action plan should focus on moving or 
            tailoring the actions to these designated firefighters.
            ff_summary: a general summary of the state of each firefighter
            general_summary: A summary of what the general state of the environment is. 

            [OUTPUT
            warning: A 2 - 3 sentence of what the general warning is
            action: A specific action plan, no more than 7 sentences, of what should be done. Remember to be specific by 
            identifying which firefighters should do what. 
            data: a list of  any supporting data that was provided. DO NOT make up data or assume anything.

            Notes:
            - Remember that your target audience is the human firefighter squad
            - Your actions should be time-sensitive. 

"""
async def make_plan(r: Analysis) -> str:
    """
    The readable action report that is sent to the user!
    """
    try:
        response = await client.generate(
                        model = 'qwen2.5:14b',
                        system = PLAN_PROMPT,
                        prompt = f"""
                                desc: {r.desc}\n 
                                adjust_ffs: {r.adjust_ffs} \n
                                ff_summary: {memory.firefighter_summary}\n
                                general_summary: {memory.data_summary}
                                """,
                        format="json",
                        options={
                            'temperature': 0.2 # A tighter temp means that it rambles less
                        }
        )
        plan = Plan.model_validate_json(response['response'])
        print(plan)
    except Exception as e:
        print(f"plan failed to generate: {e}")
        return
    
    return(plan)
