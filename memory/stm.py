from typing import Any
import os
import aiofiles
import json

async def store_conversation(conversation_id: str,state: str, message: dict[str,Any] = None , persona: dict | None = None) -> dict:
    """
    This tool stores the conversation messages in a persistent storage.
    
    Args:
        conversation_id (str): Unique identifier for the conversation.
        state (str): Current state of the conversation.
        message (dict[str, Any], optional): The message to be stored in the conversation.
        persona (dict, optional): The persona information to be stored.
        
    """
    # Here you would implement the logic to store the message in a database or file
        # dir_path = os.path.abspath(f"./../storage/{conversation_id}")
        # file_path = os.path.join(dir_path, f"{state}.json")
    dir_path = os.path.abspath(f"./storage/conversations/")
    file_path = os.path.join(dir_path, f"{conversation_id}.json")
    # print("dir_path:",dir_path)
    # print("\nfile_path:",file_path)
    
    
    existing_data = {"persona":{},"conversation":[]}
        # print("dir_path:", dir_path)
        # print("file_path:", file_path)
    if os.path.exists(file_path):
        # print("extracting data")
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()
            if content:
                existing_data = {**existing_data , **json.loads(content)}
    else:
        os.makedirs(dir_path, exist_ok=True)
    
    if message:
        # print(existing_data)
        existing_data['conversation'].append(message)
  
        # print(f"Storing message for conversation {conversation_id}: {message}.")
        # return {"status": "success", "conversation_id": conversation_id, "message": message}
    if persona:
        existing_data['persona'] = persona
    
        
    async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(existing_data, indent=4))
            
    return {"status":"success","message":"message stored successfully!"}
            
        
async def get_conversation(conversation_id: str,state: str, messages: int | None = None, persona:int = 0) -> dict[str,Any]:
    """
    This resource retrieves the conversation messages from persistent storage.

    Args:
        conversation_id (str): Unique identifier for the conversation.
        state (str): Current state of the conversation.
        messages (int | None, optional): Number of messages to retrieve. If None, retrieves the last message.
        persona (int, optional): If 1, retrieves the persona information.Default it is 0.
    Returns:
        dict[str,Any]: A dictionary containing the status, conversation ID, state, and the requested messages.
        If messages is None, returns the last message in the specified state.
    """
    
    existing_data = {"persona":{},"conversation":[]}
    # Here you would implement the logic to store the message in a database or file
        # dir_path = os.path.abspath(f"./../storage/{conversation_id}")
        # file_path = os.path.join(dir_path, f"{state}.json")
    
    dir_path = os.path.abspath(f"./storage/conversations/")
    file_path = os.path.join(dir_path, f"{conversation_id}.json")
    # print("dir_path:",dir_path)
    # print("\nfile_path:",file_path)

    if os.path.exists(file_path):
        # print("extracting data")
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()
            if content:
                existing_data = {**existing_data,**json.loads(content)}
    
    # print("content:",existing_data)

        
    # print(f"Getting messages for conversation {conversation_id}: last {messages} messages in state {state}")
    if messages:
        response = {"status": "success", "conversation_id": conversation_id, "state": state, "message": existing_data['conversation'][-int(min(len(existing_data['conversation']),messages)):] }
    else:
        response = {"status":"success","conversation_id":conversation_id,"state":state,"message":existing_data['conversation']}
        
    if persona:
        response['persona'] = existing_data['persona']
    return response


async def get_message_by_idx(conversation_id:str, msg_idx: int) -> dict[str,Any]:
    """
    This resource retrieves a specific message by its index from persistent storage.

    Args:
        conversation_id (str): Unique identifier for the conversation.
        m_idx (int): Index of the message to retrieve.

    Returns:
        dict[str, Any]: A dictionary containing the status, conversation ID, state, and the requested message.
                        If the index is out of range, returns an error message.
    """
    
    existing_data = {"persona":{},"conversation":[]}
    # Here you would implement the logic to store the message in a database or file
        # dir_path = os.path.abspath(f"./../storage/{conversation_id}")
        # file_path = os.path.join(dir_path, f"{state}.json")
    
    dir_path = os.path.abspath(f"./storage/conversations/")
    file_path = os.path.join(dir_path, f"{conversation_id}.json")
    # print("dir_path:",dir_path)
    # print("\nfile_path:",file_path)

    if os.path.exists(file_path):
        # print("extracting data")
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()
            if content:
                existing_data = {**existing_data,**json.loads(content)}
    
    # print("content:",existing_data)

        
    # print(f"Getting messages for conversation {conversation_id}: last {messages} messages in state {state}")
    if 0 <= msg_idx < len(existing_data['conversation']):
        response = {"status": "success", "conversation_id": conversation_id, "message": existing_data['conversation'][msg_idx] }
    else:
        response = {"status": "error", "message": f"Message index {msg_idx} out of range."}
        
    return response


async def store_synopsis(synopsis: dict , ishistory: bool = False) -> dict:
    """
    This tool helps you store the synopsis of a conversation

    Args:
        synopsis (dict): information about the chat conversation between the service user.
        ishistory (bool , Optional): is it a past conversation or new one.
    """
    
    dir_path = os.path.abspath(f"./storage/synopsis/")
    file_path = os.path.join(dir_path, "synopsis.json")
    
    existing_data = {"synopsis": [] }
    
    if os.path.exists(file_path):
        # print("extracting data")
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()
            if content:
                existing_data = {**existing_data , **json.loads(content)}
    else:
        os.makedirs(dir_path, exist_ok=True)
    
    if not ishistory:
        existing_data['synopsis'].append(synopsis)
    # else:
    #     # write a loop over the existing synopsis and update the matching conversation_id synopsis
    #     for idx, syn in enumerate(existing_data['synopsis']):
    #         if syn['session_id'] == synopsis['session_id']:
    #             existing_data['synopsis'][idx] = synopsis
    #             break
    
    async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(existing_data, indent=4))
    
    return {"status":"success","message":f"{synopsis} stored successfully!"}


async def get_synopsis(top_k:int = 100) -> dict[str,Any]:
    """
    This tool helps you get the synopsis of conversations.

    Args:
        top_k (int, optional): number of synopsis to be retrieved. Defaults to 100. when top_k = -1 , return all the synopsis.
    Returns:
        dict[str,Any]: reponse containing the synopsis stored for his chats.
    """
    
    existing_data = {"synopsis": [] }
    
    dir_path = os.path.abspath(f"./storage/synopsis/")
    file_path = os.path.join(dir_path, "synopsis.json")
    
    if os.path.exists(file_path):
        # print("extracting data")
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()
            if content:
                existing_data = {**existing_data , **json.loads(content)}
    
    if top_k <0:
        return {"status":"success",**existing_data}
    
    return {"status": "success", "synopsis": existing_data['synopsis'][-int(min(len(existing_data['synopsis']),top_k)):] }
        




# print(asyncio.run(get_conversation("test_conversation", "START")))
    
# test resource
# @mcp.resource("greeting://{name}")
# def get_greeting(name: str) -> str:
#     """Get a personalized greeting"""
#     return f"Hello, {name}!"
    