from typing import Optional
from llm.azurecustomllm import AzureCustomLLM
from utils.agent_prompts import intent_identifier

llm_classifier = AzureCustomLLM()
 
async def classifier(user_prompt: str , history : Optional[list|None] = None , file: list[str] = [] , job_id:str = None)-> str:
    """
    Classifies the user prompt based on the system prompt.
    
    Args:
        user_prompt (str): The user prompt to classify.
        history (list|None = None): history of conversations.
        file (list[str], optional): List of filenames containing additional context. Defaults to [].
        
    Returns:
        str: The classification result.
    """
    
    try:
        sys_prompt = intent_identifier["sys_prompt"](True if job_id else False)
        # print(f"workflow job classifier :{True if job_id else False}\n\n{sys_prompt}")
        
        # Use the LLM to classify the user prompt
        classification = llm_classifier.invoke(input = user_prompt , sys_prompt = sys_prompt , history = history + [{"role":"user","content":f"Shared files includes:{file}"}])
    except Exception as e:
        raise     
    
    return classification