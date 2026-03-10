import os
import json
import logging
import re
from server import mcp
from main import r , session , session_context , user_config_manager
from typing import Any
from utils.stmhttp_client import MCPClient
from llm.azurecustomllm import AzureCustomLLM
from utils.agent_prompts import intent_identifier
# from utils.user_story_formats import formats
from utils.classifier import classifier
from fastmcp.server.dependencies import get_http_headers


llm = AzureCustomLLM()
server_url = os.getenv("AGENT_SERVER_URL", os.getenv("BA_URL"))  # Backward compatible
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s @ %(name)s @ %(levelname)s @%(message)s"
    )

# Configuration: conversation history context window size
msgs = int(os.getenv("CONTEXT_WINDOW_SIZE", os.getenv("BA_CONTEXT_WINDOW_SIZE", "7")))


# ----------------------- OUT-OF-SCOPE CLEANER (Final Guard) -----------------------
def _remove_out_of_scope_sections(text: str) -> str:
    """
    Remove any 'Out of Scope' section irrespective of formatting variations.

    Start triggers (any one):
      - '## Out of Scope' / '### Out-of-Scope' (markdown headings)
      - '**Out of Scope:**' (bold label)
      - 'Out of Scope:' (plain label)

    Stop triggers (first encountered after start):
      - Next markdown heading starting with '#'
      - Horizontal rule line like '---' (allow spaces)
      - Another bold label '**Something:**'
      - (fallback) a blank line followed by a non-list line

    Also performs a regex safety pass for paragraph-style Out-of-Scope.
    """
    if not isinstance(text, str):
        return text

    s = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = s.split("\n")
    out = []
    skipping = False

    # Bold label like "**In Scope:**" or "**Assumptions:**"
    BOLD_LABEL_RE = re.compile(r"^\s*\*\*[^*]+?:\s*\*\*\s*$|^\s*\*\*[^*]+?:\s*$", re.IGNORECASE)

    def is_out_of_scope_start(line: str) -> bool:
        l = (line or "").strip()
        if not l:
            return False
        # Markdown heading variants
        if re.match(r"^#{1,6}\s*Out[\s\u00A0\-_]*of[\s\u00A0\-_]*Scope\s*:?$", l, flags=re.IGNORECASE):
            return True
        # Bold label variants
        if re.match(r"^\*{0,2}\s*Out[\s\u00A0\-_]*of[\s\u00A0\-_]*Scope\s*\*{0,2}\s*:?\s*$", l, flags=re.IGNORECASE):
            return True
        # Plain label
        if re.match(r"^Out[\s\u00A0\-_]*of[\s\u00A0\-_]*Scope\s*:?\s*$", l, flags=re.IGNORECASE):
            return True
        return False

    def is_section_boundary(line: str) -> bool:
        l = (line or "").strip()
        if not l:
            return False
        # Next markdown heading
        if re.match(r"^#{1,6}\s", l):
            return True
        # Horizontal rule (allow spaces)
        if re.match(r"^\s*-{3,}\s*$", l):
            return True
        # Another bold section label
        if BOLD_LABEL_RE.match(l):
            return True
        return False

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not skipping and is_out_of_scope_start(line):
            # Enter skipping mode; drop start line and following content until boundary
            skipping = True
            i += 1

            # Skip all contiguous list items/paragraphs until a boundary
            while i < n:
                nxt = lines[i]
                if is_section_boundary(nxt):
                    break
                # Fallback: if we see a blank line then a non-list/non-quote/non-code line, consider boundary
                if nxt.strip() == "":
                    # Peek next non-empty
                    j = i + 1
                    while j < n and lines[j].strip() == "":
                        j += 1
                    if j < n:
                        nxt2 = lines[j].lstrip()
                        if not (nxt2.startswith("-") or nxt2.startswith("*") or nxt2.startswith(">") or nxt2.startswith("```")):
                            i = j  # stop at the next paragraph start
                            break
                i += 1

            # If boundary is a horizontal rule, skip it too to avoid leaving a dangling '---'
            if i < n and re.match(r"^\s*-{3,}\s*$", lines[i].strip()):
                i += 1

            skipping = False
            continue

        out.append(line)
        i += 1

    cleaned = "\n".join(out)

    # --- SAFETY PASS (regex): remove paragraph-style Out of Scope blocks that didn't get caught above ---
    # 1) Bold label variant + content until next heading/bold label/HR or end
    cleaned = re.sub(
        r"(?msi)^\s*\*\*\s*Out[\s\u00A0\-_]*of[\s\u00A0\-_]*Scope\s*:\s*\*?\*?\s*[\r\n]+.*?(?=^\s*#{1,6}\s|^\s*\*\*[^*]+?:\s*\*?\*?\s*$|^\s*-{3,}\s*$|\Z)",
        "",
        cleaned
    )
    # 2) Plain label variant + bullet list
    cleaned = re.sub(
        r"(?msi)^\s*Out[\s\u00A0\-_]*of[\s\u00A0\-_]*Scope\s*:\s*[\r\n]+(?:\s*[-*].*[\r\n]+)+",
        "",
        cleaned
    )
    # 3) Tidy blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    return cleaned
# -------------------------------------------------------------------------------


@mcp.tool()
async def create_session()-> dict:
    """Create a new session and return the session ID."""
    conversation_id = session.create_session()
    return {"status":"success","session_id":conversation_id}

@mcp.tool()
async def handle_message(user_message: str ,conversation_id: str ,  namespace:dict ,job_id:str | None = None , agent_feed:list | None = None, file: list[str] | None = None)-> dict[str, Any]:
    """
    Main message handler for the agent. Routes messages to appropriate tools based on intent classification.
    
    This is the primary entry point for user interactions. It:
    - Classifies user intent
    - Routes to specialized tools (document creation, updates, general queries)
    - Manages conversation context and history
    
    Arguments:
        user_message (str): The message from the user.
        conversation_id (str): Unique identifier for the conversation.
        namespace (dict): Context namespace with domain-specific information.
        job_id (str, optional): Unique identifier for workflow jobs.
        agent_feed (list, optional): List of feeding documents for workflow.
        file (list, optional): List of filenames containing additional context. Defaults to None.
        
    Returns:
        dict: Dictionary containing the agent's response with status, role, and content.
    """

    # ---------------------------fetching http request headers ---------------------------
    headers = get_http_headers()
    

    # ------------------------- loading conversation history -------------------------
    history = session.load_history(conversation_id , msgs)
    
    # ------------------------- Extracting user preferences from persistent store ------------------
    try:
        user_config = None
        # Try to retrieve from Redis if available
        if r is not None:
            redis_data = await r.retrieve_data(f"{conversation_id}-config")
            user_config = redis_data['data'].get(f"{conversation_id}-config") if redis_data else None
        
        if not user_config:
            user_config = user_config_manager.get_config()
            
            # Set default configuration if not present
            if "output_style" not in user_config or "output_format" not in user_config:
                user_config = {"output_style":"brief" , "output_format":"markdown"}
                user_config_manager.set_config(user_config)
            
            # Store in Redis if available
            if r is not None:
                await r.store_data({f"{conversation_id}-config": json.dumps(user_config)})
                
            logger.debug(f"User config loaded from MongoDB: {user_config}")
        else:
            user_config = json.loads(user_config)
            
            # Ensure required config fields exist
            if "output_style" not in user_config or "output_format" not in user_config:
                user_config = user_config_manager.get_config()
                
                if "output_style" not in user_config or "output_format" not in user_config:
                    user_config = {"output_style":"brief" , "output_format":"markdown"}
                    user_config_manager.set_config(user_config)
            
            # Store in Redis if available
            if r is not None:
                await r.store_data({f"{conversation_id}-config": json.dumps(user_config)})
            
    except Exception as e:
        logger.error(f"Error retrieving user configuration: {e}")
        return {"status": "error", "message": "Failed to fetch user configuration", "details": str(e)}
            
    logger.debug(f"User configuration: {user_config}")
    
    output_style = user_config.get("output_style", "brief").lower()
    output_format = user_config.get("output_format", "markdown").lower()
    logger.debug(f"Output preferences - Style: {output_style}, Format: {output_format}")
    
    # -------------------------- append user message -------------------------------
    
    workflow_kwargs = {}
    if job_id:
        workflow_kwargs["job_id"]= job_id
        workflow_kwargs["agent_feed"] = agent_feed
    
    if file:
        session.append_message(conversation_id, "user", user_message , file = file , job_id = job_id)
    else:
        session.append_message(conversation_id, "user", user_message , job_id = job_id)
    
    # --------------------------- identify intent ------------------------------------
    try:
        intent = await classifier(user_message , history = history , file = file , job_id = job_id)
    except Exception as e:
        logger.error(f"Error in intent classification: {str(e)}")
        return {"status": "error", "message": str(e)}
    
    print("intent:",intent)
    
    # ---------------------------- Intent-based routing --------------------------------------
    # Route to document creation tool
    if "create document" in intent.lower() or "create brd" in intent.lower():
        
        logger.info(f"[Agent] Routing to document creation tool for conversation_id={conversation_id}")
        print(f"[Agent] Document creation requested for conversation_id={conversation_id}")

        client = MCPClient()
        try:
            await client.connect_to_streamable_http_server(server_url,headers={'Authorization': headers.get("authorization") or headers.get("Authorization") or ""})
            arguments = {   "prompt": user_message,
                            "conversation_id": conversation_id,
                            "namespace": namespace,
                            **workflow_kwargs
                        }
            if file:
                arguments["file"] = file
            
            response = await client.session.call_tool("create_user_stories", arguments=arguments)

            # --- Post-processing: Clean up response content ---
            sc = getattr(response, "structuredContent", None)
            if sc is None and isinstance(response, dict) and "structuredContent" in response:
                sc = response["structuredContent"]

            if isinstance(sc, dict) and "content" in sc and isinstance(sc["content"], str):
                original = sc["content"]
                cleaned = _remove_out_of_scope_sections(original)
                try:
                    if ("Out of Scope" in original) and ("Out of Scope" not in cleaned):
                        logger.info("Post-processing: removed 'Out of Scope' sections from document creation response.")
                    elif "Out of Scope" in cleaned:
                        logger.warning("Post-processing: 'Out of Scope' sections still present after cleaning.")
                except Exception:
                    pass
                sc["content"] = cleaned
                return sc

            # Fallback: try to clean embedded JSON text if present
            try:
                txt = getattr(response, "content", None)
                if isinstance(txt, list) and txt and isinstance(txt[0], dict) and "text" in txt[0]:
                    maybe_json = txt[0]["text"]
                    try:
                        obj = json.loads(maybe_json)
                        if isinstance(obj, dict) and "content" in obj and isinstance(obj["content"], str):
                            obj["content"] = _remove_out_of_scope_sections(obj["content"])
                            txt[0]["text"] = json.dumps(obj)
                            # Return structuredContent if present, else reconstructed dict
                            if hasattr(response, "structuredContent"):
                                return response.structuredContent
                            else:
                                return {"status":"success","role":"assistant","content": obj.get("content","")}
                    except Exception:
                        pass
            except Exception:
                pass

            # Default behavior if shapes are unexpected
            return response.structuredContent
        
        except Exception as e:
            logger.error(f"Error in document creation: {e}")
            return {"status":"error","message": str(e)}
        finally: 
            if client:
                await client.cleanup()
    
    # Route to document update tool            
    elif any(s in intent.lower() for s in  ["update document", "update brd" , 'human feedback']):
        
        logger.info(f"[Agent] Routing to document update tool for conversation_id={conversation_id}")
        print(f"[Agent] Document update requested for conversation_id={conversation_id}")

        try:
            client = MCPClient()
            # Store intent in Redis if available
            if r is not None:
                await r.store_data({f"{conversation_id}-intent": intent})
            await client.connect_to_streamable_http_server(server_url,headers={'Authorization': headers.get("authorization") or headers.get("Authorization") or ""})
            
            arguments = {   "prompt": user_message,
                            "conversation_id": conversation_id,
                            "namespace": namespace,
                            **workflow_kwargs
                        }
            
            if file:
                arguments["file"] = file
            
            # call the aitl_reviewer tool with the response, state, and uuid
            tool_name = "hitl"
            response = await client.session.call_tool(
                name=tool_name, 
                arguments=arguments
            )

            # --- Final guard for HITL updates as well ---
            sc = getattr(response, "structuredContent", None)
            if sc is None and isinstance(response, dict) and "structuredContent" in response:
                sc = response["structuredContent"]

            if isinstance(sc, dict) and "content" in sc and isinstance(sc["content"], str):
                original = sc["content"]
                cleaned = _remove_out_of_scope_sections(original)
                try:
                    if ("Out of Scope" in original) and ("Out of Scope" not in cleaned):
                        logger.info("Post-processing: removed 'Out of Scope' sections from document update response.")
                    elif "Out of Scope" in cleaned:
                        logger.warning("Post-processing: 'Out of Scope' sections still present after cleaning.")
                except Exception:
                    pass
                sc["content"] = cleaned
                return sc

            # Fallback
            return response.structuredContent
        
        except Exception as e:
            logger.error(f"Error in document update processing: {e}")
            return {"status":"error","message": str(e)}
            
        finally:
            if client:
                await client.cleanup()
    
    # Route to external system query (e.g., JIRA)
    elif "external query" in intent.lower() or "jiraquery" in intent.lower():
        
        print(f"[BA-Agent] TOOL CALLED: jira_agent for conversation_id={conversation_id}")
        logger.info(f"[BA-Agent] TOOL CALLED: jira_agent for conversation_id={conversation_id}")

        try:
            client = MCPClient()
            # Store intent in Redis if available
            if r is not None:
                await r.store_data({f"{conversation_id}-intent": intent})
            await client.connect_to_streamable_http_server(server_url,headers={'Authorization': headers.get("authorization") or headers.get("Authorization") or ""})
            
            arguments = {   
                            "conversation_id": conversation_id,
                            **workflow_kwargs
                        }
            
            # call the jira_agent tool 
            tool_name = "jira_agent"
            response = await client.session.call_tool(
                name=tool_name, 
                arguments=arguments
            )
            
            return response.structuredContent
        
        except Exception as e:
            logger.error(f"Error in external system query: {e}")
            return {"status":"error","message": str(e)}

        finally:
            if client:
                await client.cleanup()
    
    # ------------------------- General Query Handler (fallback for other intents) ----------------
    
    enriched_message = user_message
    
    logger.info(f"[Agent] Handling general query for conversation_id={conversation_id}")
    print(f"[Agent] General query being processed for conversation_id={conversation_id}")

    
    # ----------------------curating data from files if exists--------------------------------
    
    try:
        input_context = None
        # Try to retrieve from Redis if available
        if r is not None:
            redis_data = await r.retrieve_data(f"{conversation_id}-session-context")
            input_context = redis_data['data'].get(f"{conversation_id}-session-context") if redis_data else None
        
        if not input_context:
            input_context = session_context.get_context(conversation_id)
            print("mongo session context:",input_context)
            if "Session context is empty" not in input_context.get("context",""):
                # Store in Redis if available
                if r is not None:
                    await r.store_data({f"{conversation_id}-session-context": input_context.get("context","")})
            input_context = input_context.get("context","")
    except Exception as e:
        logger.error(f"Error retrieving session context: {e}")
        input_context = "No additional context available."
    
    file_names = ','.join(file) if file else ''
    enriched_message =  llm.invoke(
        sys_prompt = intent_identifier["context_enrichment_prompt"], 
        input = enriched_message + (f"files uploaded related to the current message from user are: {file_names}" if file else "") +  f"\n\nAdditional context from the user (if any):\n{input_context}",
        history = history
    )

    logger.debug(f"Message after context enrichment: {enriched_message}")
    
    # -------------------------------------------- Getting response from LLM --------------------------------------
    # General Assistant Prompt - Customize this for your specific agent type
    general_assistant_prompt = """
You are a senior Business Analyst with over 10 years of experience across enterprise software delivery, digital transformation, and product development.

Your role is to:
- Elicit, analyse, and clarify business requirements from stakeholders
- Guide users in articulating their needs in terms of business objectives, functional requirements, non-functional requirements, and acceptance criteria
- Help structure thinking into formal BA artefacts: Business Requirements Documents (BRDs), process flows, user stories, and traceability matrices
- Apply established BA frameworks (BABOK, Agile BA, use-case modelling) where appropriate
- Identify ambiguities, gaps, and unstated assumptions in requirements
- Ask focused, structured clarifying questions to uncover the full scope of a problem

When responding:
- Use precise BA terminology: stakeholders, business objectives, acceptance criteria, functional/non-functional requirements, business rules, process flows, traceability, gap analysis
- Be analytical and structured — organise your responses clearly
- Ask 2–3 targeted clarifying questions when requirements are vague or incomplete
- Offer to help formalise discussions into structured documentation (BRD, user stories, process flows)
- Reference BA best practices and industry standards where relevant
- Maintain context from the conversation history to ensure continuity
- Keep responses concise, professional, and oriented toward actionable outcomes

Your goal is to help stakeholders produce clear, complete, and traceable business requirements that can be confidently handed to a development team.
    """
    
    response = llm.invoke(
        sys_prompt = general_assistant_prompt,
        input = enriched_message, 
        history = [{"role":"user","content":f"User preferences:\n * Output_style: {output_style}\n * Output_format: {output_format}"}]+history
    )
    
    session.append_message(conversation_id, "assistant", response , job_id = job_id)
    
    return {"status":"success" , "role":"assistant", "content": response}