from server import mcp
from typing import Any
from memory.stm import get_message_by_idx as gmidx , store_conversation as stm_sc , get_conversation as stm_gc , get_synopsis as stm_gs , store_synopsis as stm_ss
from utils.session_history_manager import SessionHistoryManager , SessionContextManager
import logging
from main import session , session_context

logger = logging.getLogger("stm_tool")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s @ %(name)s @ %(levelname)s @%(message)s"
    )

@mcp.tool()
async def store_conversation(conversation_id: str, message: dict[str, Any] = None, file = None ) -> dict:
    """
    This tool stores the conversation messages in a persistent storage.
    
    Args:
        conversation_id (str): Unique identifier for the conversation.
        message (dict[str, Any], optional): The message to be stored. Defaults to None.
        file (optional): The file details uploaded by the user. Defaults to None.
    """
    try:
        session.append_message(conversation_id , message['role'], message['content'] , file = file)
        return {"status":"success","message":"message stored successfully!"}
    except Exception as e:
        logger.info(f"Error in storing message for {conversation_id}:",e)
        return {"status":"error","message":"Error in storing message"}


@mcp.tool()
async def get_conversation(conversation_id: str, limit: int | None = None) -> dict[str, Any]:
    """
    This resource retrieves the conversation messages from persistent storage.

    Args:
        conversation_id (str): Unique identifier for the conversation.
        limit (int | None, optional): Number of messages to retrieve. If None, retrieves all messages. Defaults to None.

    Returns:
        dict[str, Any]: The conversation messages and optionally persona information.
    """
    try:
        history = session.load_history(conversation_id , limit = limit)
        
        return {"status":"success","conversation_id":conversation_id,"message":history}
    except Exception as e:
        logger.info(f"Error in fetching message for {conversation_id}:",e)
        return {"status":"error","message":"Error in fetching message"}
    
@mcp.tool()
async def get_message_by_idx(conversation_id: str, msg_idx: int) -> dict[str, Any]:
    """ 
    This tool retrieves a specific message by its index from persistent storage.

    Args:
        conversation_id (str): Unique identifier for the conversation.
        msg_idx (int): Index of the message to retrieve.

    Returns:
        dict[str, Any]: A dictionary containing the status, conversation ID, state, and the requested message.
                        If the index is out of range, returns an error message.
    """
    try:
        return await gmidx(conversation_id=conversation_id, msg_idx=msg_idx)
    except Exception as e:
        logger.info(f"Error in fetching message index {msg_idx} for {conversation_id}:",e)
        return {"status":"error","message":"Error in fetching message by index"}

@mcp.tool()
async def edit_synopsis(conversation_id: str , title: str) -> dict:
    """
    This tool helps update the title(synopsis) for a chat conversation 
    
    Args:
        conversation_id (str): Unique identifier for the conversation.
        title (str): The updated title for the conversation.
    """
    try:
        session_context.set_context(conversation_id , {"title":title})
        return {"status":"success","message":"title updated successfully!"}
    except Exception as e:
        print(f"Error in updating title for {conversation_id}:",e)
        return {"status":"error","message":"Error in updating title"}
    
 
@mcp.tool()
async def get_synopsis(top_k:int = 100) -> dict[str, Any]:
    """
    This resource retrieves the top_k synopsis from persistent storage.

    Args:
        top_k (int,optional): top_k number of synopsis of conversations. 
    Returns:
        dict[str, Any]: The synopsis.
    """
    try:
        sessions = session.get_recent_sessions(limit=top_k)
        all_synopsis = []
        for sess in sessions:
            # if title exists then use it else use last user message as synopsis
            session_context_info = session_context.get_context(sess)
            sess_history = session.load_history(sess , limit = 2)
            
            if session_context_info.get("status") == "success" and session_context_info.get("title",None):
                all_synopsis.append({"session_id": sess, "synopsis": session_context_info.get("title"), "timestamp": sess_history[0]['timestamp']})
                continue
            
            if sess_history and len(sess_history) > 0:
                all_synopsis.append({"session_id": sess, "synopsis": sess_history[0]['content'] , "timestamp": sess_history[0]['timestamp']})
        
        return {"status": "success", "synopsis": all_synopsis} 
    except Exception as e:
        logger.info(f"Error in fetching synopsis:",e)
        return {"status":"error","message":"Error in fetching synopsis"}

@mcp.tool()
async def delete_conversation(conversation_id: str) -> dict[str, Any]:
    """
    This tool deletes a conversation from persistent storage.

    Args:
        conversation_id (str): Unique identifier for the conversation.

    Returns:
        dict[str, Any]: A dictionary containing the status and a message indicating the result of the deletion.
    """
    try:
        session_context.delete_context(conversation_id)
        session.delete_session(conversation_id)
        return {"status": "success", "message": f"Conversation {conversation_id} deleted successfully."}
    except Exception as e:
        logger.info(f"Error in deleting conversation {conversation_id}:",e)
        return {"status": "error", "message": str(e)}
