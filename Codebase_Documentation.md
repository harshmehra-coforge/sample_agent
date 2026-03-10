# Codebase Documentation for Sample Agent

## Overview
This document provides an overview of the codebase, explaining its structure, functionality, and how to extend it to create specific agents. It also includes details about each file and the changes required to customize the agent.

---

## Codebase Structure

### 1. **Main Components**
- **`main.py`**: Entry point for the application. Configures the agent, initializes dependencies, and sets up middleware.
- **`server.py`**: Defines the FastMCP server and its lifecycle, including MongoDB initialization and cleanup.
- **`requirements.txt`**: Lists all dependencies required for the project.

### 2. **Submodules**
- **`llm/`**: Contains custom implementations for language models.
  - `azurecustomllm.py`: Placeholder for Azure-based LLM integration.
  - `customllm.py`: Implements a REST API-based LLM wrapper.
- **`memory/`**: Handles conversation storage and state management.
  - `stm.py`: Provides asynchronous methods to store and retrieve conversation data.
- **`tools/`**: Implements tools for agent functionality.
  - `agent_chatbot.py`: Core chatbot logic, including context management.
  - `cus_agent.py`: Generates structured documents like user stories.
  - `hitl.py`: Human-in-the-loop tool for refining documents.
- **`utils/`**: Utility functions and classes.
  - `agent_prompts.py`: Contains customizable prompts for the agent.
  - `classifier.py`: Classifies user intents using the LLM.
  - `markdown2docx.py`: Converts Markdown content to Word documents.

---

## How the Code Works

### 1. **Initialization**
- The application starts with `main.py`, which sets up the agent's configuration (e.g., `AGENT_NAME`, `DEFAULT_CONTEXT_WINDOW`) and initializes MongoDB and session managers.
- Middleware is added to handle CORS and health checks.

### 2. **Server Lifecycle**
- `server.py` defines the FastMCP server, which manages the application's lifecycle. MongoDB connections are initialized during startup and closed during shutdown.

### 3. **Agent Functionality**
- Tools in the `tools/` directory define the agent's capabilities:
  - `agent_chatbot.py`: Manages conversation history and processes user inputs.
  - `cus_agent.py`: Generates structured documents based on user prompts.
  - `hitl.py`: Updates documents based on user feedback.

### 4. **Language Model Integration**
- `llm/customllm.py` provides a REST API-based wrapper for LLMs, allowing the agent to process natural language inputs.
- `llm/azurecustomllm.py` is a placeholder for Azure-based LLM integration.

### 5. **Utilities**
- `utils/agent_prompts.py`: Defines prompts for different tools.
- `utils/classifier.py`: Uses the LLM to classify user intents.
- `utils/markdown2docx.py`: Converts Markdown content to Word documents.

---

## Customization Guide

### 1. **Creating a New Agent**
To create a new agent, follow these steps:

1. **Update Prompts**:
   - Modify `utils/agent_prompts.py` to define prompts specific to your agent.
   - Example: Update `cus_agent["sys_prompt"]` to define the structure of generated documents.

2. **Add New Tools**:
   - Create a new file in the `tools/` directory.
   - Define a new tool using the `@mcp.tool()` decorator.
   - Example: Refer to `cus_agent.py` for a tool that generates user stories.

3. **Integrate Custom LLMs**:
   - Implement a new LLM wrapper in the `llm/` directory.
   - Example: Refer to `customllm.py` for a REST API-based implementation.

4. **Update Configuration**:
   - Modify `.env` to set environment variables for the new agent.
   - Example: Update `AGENT_NAME` and `AGENT_TYPE`.

### 2. **Modifying Existing Tools**
- Update the logic in `tools/` files to customize the agent's behavior.
- Example: Modify `agent_chatbot.py` to change how conversation history is managed.

### 3. **Extending Functionality**
- Add new utility functions in the `utils/` directory.
- Example: Add a new function in `utils/markdown2docx.py` to support additional document formats.

---

## File Descriptions

### 1. **`main.py`**
- Configures the agent and initializes dependencies.
- Key Components:
  - `AGENT_NAME`, `AGENT_TYPE`: Define the agent's identity.
  - `SessionHistoryManager`: Manages conversation history.

### 2. **`server.py`**
- Defines the FastMCP server and its lifecycle.
- Key Components:
  - `lifespan`: Manages MongoDB connections.

### 3. **`llm/customllm.py`**
- Implements a REST API-based LLM wrapper.
- Key Components:
  - `_call`: Sends requests to the LLM API.

### 4. **`tools/cus_agent.py`**
- Generates structured documents like user stories.
- Key Components:
  - `create_user_stories`: Processes user prompts to generate documents.

### 5. **`utils/markdown2docx.py`**
- Converts Markdown content to Word documents.
- Key Components:
  - `add_hyperlink`: Adds hyperlinks to Word documents.

---

## Code Flow

### 1. **Startup**
- The application starts with `main.py`, which initializes the agent's configuration and dependencies.
- Middleware is added to handle CORS and health checks.
- The FastMCP server is started using `server.py`.

### 2. **Request Handling**
- Incoming requests are routed to the appropriate tool in the `tools/` directory.
- Tools process the request using:
  - Conversation history from `memory/stm.py`.
  - Prompts defined in `utils/agent_prompts.py`.
  - Language model integration via `llm/customllm.py`.

### 3. **Response Generation**
- Tools generate responses or documents based on the processed input.
- Responses are returned to the user via the FastMCP server.

---

## Startup Commands

To start the application, use the following commands:

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   - Create a `.env` file based on `.env.template`.
   - Define variables such as `AGENT_NAME`, `AGENT_TYPE`, `CONTEXT_WINDOW_SIZE`, etc.

3. **Run the Server**:
   ```bash
   uvicorn main:http_app --reload
   ```

4. **Access the Application**:
   - Open your browser and navigate to `http://127.0.0.1:8000`.

---

## Conclusion
This document provides a comprehensive overview of the codebase, explaining its structure and functionality. By following the customization guide, you can extend the codebase to create specific agents tailored to your needs.