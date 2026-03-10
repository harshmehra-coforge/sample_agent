from server import mcp
from main import r , os , session , session_context , user_config_manager , workflow_context_manager
from typing import Any
from utils.classifier import classifier
from utils.agent_prompts import hitl_agent
from llm.azurecustomllm import AzureCustomLLM
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s@ %(name)s@ %(levelname)s @%(message)s"
    )

# Configuration: conversation history context window size
msgs = int(os.getenv("CONTEXT_WINDOW_SIZE", os.getenv("BA_CONTEXT_WINDOW_SIZE", "7")))

llm = AzureCustomLLM()


@mcp.tool()
async def hitl(prompt: str, conversation_id: str ,namespace : dict, file: list|None = None ,job_id:str | None = None , agent_feed:list | None = None)-> dict[str,Any]:
    """
    Human-in-the-loop document update tool. Processes user feedback to refine and update documents.
    
    This tool handles two scenarios:
    1. Updating AI-generated documents based on user feedback
    2. Improving user-provided documents with edits and enhancements
    
    Args:
        prompt (str): User feedback or update instructions
        conversation_id (str): Unique identifier for the conversation
        namespace (dict): Context namespace with domain-specific information
        file (list, optional): List of filenames containing additional context. Defaults to None.
        job_id (str, optional): Identifier for workflow jobs. Defaults to None.
        agent_feed (list[str], optional): Input documents for workflow processing. Defaults to None.
        
    Returns:
        dict: Dictionary containing the updated document with status and content.
    """
    
    # ------------------------ Extract update/correction prompt ---------------------------------
    corrector_prompt = hitl_agent["feedback_corrector"]
    
    # ------------------------- Retrieve cached intent -----------------------------------------
    try:
        cache_data = None
        intent = ""
        # Try to retrieve from Redis if available
        if r is not None:
            redis_data = await r.retrieve_data(f"{conversation_id}-intent")
            cache_data = redis_data['data'] if redis_data else None
            logger.debug(f"Intent cache retrieved: {cache_data}")
            intent = cache_data.get(f"{conversation_id}-intent", "") if cache_data else ""
        
        if not intent:
            intent = "update document"
    except Exception as e:
        logger.error(f"Error retrieving intent: {e}")
        intent = "update document"
        
    #-------------------------- curating file upload & project context -------------------------------
        
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
            
        if job_id:
            project_context = workflow_context_manager.curate_context(job_id,agent_feed)
    except Exception as e:
        logger.error(f"Error retrieving session context: {e}")
        input_context = "No additional context available."
    
    # -------------------------------- Extract conversation history ---------------------------------------------
    logger.debug(f"Processing intent: {intent}")
    
    try:
        history = session.load_history(conversation_id , limit = msgs)
        if "Update" in intent:
            history = history[:-1]
        else:   
            history = history[:-1] 
        file_names = ','.join(file) if file else ''
        prompt = llm.invoke(
            sys_prompt = hitl_agent["context_enrichment_prompt"],
            input = prompt + (f""" ***Related Documents*** for reference:\n\n{project_context}\n\n""" if job_id else "") +(f"Files uploaded: {file_names}" if file else "") + f"\n\nAdditional context:\n{input_context}",
            history = history
        )
    except Exception as e:
        logger.error(f"Error loading conversation history: {e}")
        return {"status": "error", "message": "Failed to load conversation history", "details": str(e)}
        
    
    # ---------------------------------- Process user feedback -------------------------------
    user_feedback = prompt
    
    logger.debug(f"User feedback: {user_feedback[:200]}...")  # Log first 200 chars
    
    # ---------------------------------- Update document based on feedback -----------------------------------
        
    full_feedback = f"""
        The feedback to update the business requirement document (BRD) is : {user_feedback}
    """
    response = llm.invoke(input = full_feedback , sys_prompt = corrector_prompt ,history = history)
    
    print("hitl updated business requirement document (BRD):",response)
    
    session.append_message(conversation_id, "assistant", response,job_id = job_id)
    
    return {"status":"success" , "role":"assistant", "content": response}

        

