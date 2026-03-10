from server import mcp 
from main import r , os , session , session_context , user_config_manager , workflow_context_manager
# from utils.classifier import classifier
from utils.agent_prompts import cus_agent 
from llm.azurecustomllm import AzureCustomLLM
# from utils.stm_context_manager import store_messages, get_conversation
# from utils.user_story_formats import formats

from typing import Any
import logging

llm = AzureCustomLLM()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s@ %(name)s@ %(levelname)s @%(message)s"
    )

# Configuration: conversation history context window size
msgs = int(os.getenv("CONTEXT_WINDOW_SIZE", os.getenv("BA_CONTEXT_WINDOW_SIZE", "7")))


@mcp.tool()
async def create_user_stories(prompt: str , conversation_id: str , namespace:dict , file: list|None = None ,job_id:str | None = None , agent_feed:list | None = None )-> dict[str, Any]:
    """
    Creates structured documents (e.g., user stories, requirements documents) based on provided input.
    
    This tool processes high-level requirements and generates comprehensive, well-structured documents.
    Customize the output format and content structure based on your specific needs.
    
    Args:
        prompt (str): High-level requirements or input text
        conversation_id (str): Unique identifier for the conversation
        namespace (dict): Context namespace with domain-specific information
        file (list, optional): List of filenames containing additional context. Defaults to None.
        job_id (str, optional): Identifier for workflow jobs. Defaults to None.
        agent_feed (list[str], optional): Input documents for workflow processing. Defaults to None.
        
    Returns:
        dict: Dictionary containing the generated document with status and content.
    """
    
    # ----------------------------- Gather conversation history -------------------------------
    history = session.load_history(conversation_id , msgs)
        
    # System prompt - Customize this based on your document creation needs
    sys_prompt = cus_agent["sys_prompt"]
    
    # ----------------------------Curate input requirements-----------------------
    requirements = prompt
    
    if job_id:
        project_context = workflow_context_manager.curate_context(job_id,agent_feed)
    
    # ----------------------curating data from files if exists---------------------------
    
    
    try:
        input_context = None
        # Try to retrieve from Redis if available
        if r is not None:
            redis_data = await r.retrieve_data(f"{conversation_id}-session-context")
            input_context = redis_data['data'].get(f"{conversation_id}-session-context") if redis_data else None
        
        if not input_context:
            input_context = session_context.get_context(conversation_id)
            logger.debug(f"Session context loaded from MongoDB: {input_context}")
            if "Session context is empty" not in input_context.get("context",""):
                # Store in Redis if available
                if r is not None:
                    await r.store_data({f"{conversation_id}-session-context": input_context.get("context","")})
            input_context = input_context.get("context","")
    except Exception as e:
        logger.error(f"Error retrieving session context: {e}")
        input_context = "No additional context available."
        
    file_names = ','.join(file) if file else ''
    user_message = f"**High-Level Input**: {requirements}" +( f""" \n***Related Documents*** for reference:\n\n{project_context}""" if job_id else "") +(f"Files uploaded: {file_names}" if file else "") +  f"\n\nAdditional context:\n{input_context}"
    
    # Enrich requirements with context
    requirements =  llm.invoke(sys_prompt = cus_agent["context_enrichment_prompt"] , input = user_message , history = history[:-1]) 
    
    logger.debug(f"Requirements after context enrichment: {requirements}")
    
    # ---------------------- Create document from requirements ---------------------------
    full_prompt = f"""
    ***High-level requirement details***:\n{requirements}\n\n"""
    
    # format_name = story_config.get("user_story_format",str).lower()
    response = llm.invoke(sys_prompt=sys_prompt,input = full_prompt , history = history[:-1])
    # print({"response": response})
            
        
    print("user stories by claude:",response)
    
    # ------------------------------- Store user stories --------------------------------
    
    session.append_message(conversation_id, "assistant", response , job_id = job_id)
    
    return {"status":"success" , "role":"assistant", "content": response}


