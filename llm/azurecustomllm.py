from langchain_core.language_models import LLM
import requests
from pydantic import PrivateAttr
from typing import List, Optional
from dotenv import load_dotenv
import os
from openai import BadRequestError
from langchain_openai import AzureChatOpenAI
from langchain.messages import HumanMessage, SystemMessage, AIMessage

load_dotenv()


# class CustomLLM(LLM):
#     """Custom LLM wrapper for LangChain using a REST API."""
#     model:str = os.getenv('model')
#     endpoint_url: str = os.getenv('endpoint_url')
#     headers: dict = {
#         "Content-Type": "application/json", 
#         "X-API-KEY": os.getenv('api_key')
#     }
#     temperature: float = 0.7
#     top_p: float = 1.0
#     max_tokens: int = 2000
#     # stream: bool = False
#     stop: Optional[List[str]] = None
    

#     def _call(self,input:str, stop: Optional[List[str]] = None,sys_prompt:Optional[str] = None , history:Optional[list[str]|None]= None) -> str:
#         messages = []
#         if sys_prompt:
#             messages.append({"role": "system", "content": sys_prompt})
#         if history:
#             messages = messages+history
#         messages.append({"role": "user", "content": input})

#         payload = {
#             "model": self.model,
#             "messages": messages,
#             "temperature": self.temperature,
#             "top_p": self.top_p,
#             "max_tokens": self.max_tokens,
#         }
#         if stop:
#             payload["stop"] = stop

#         response = requests.post(self.endpoint_url, headers=self.headers, json=payload)
#         response.raise_for_status()
#         data = response.json()

#         return data['choices'][0]['message']['content']

#     @property
#     def _llm_type(self) -> str:
#         return "custom-llm"


#Custom LLM class for Langchain using Azure OpenAI
class ContentFilterError(Exception):
    """Raised when Azure OpenAI content management policy is triggered."""
    pass

class AzureCustomLLM(LLM):
    """Custom LLM wrapper for Langchain using Azure OpenAI."""

    _llm: AzureChatOpenAI = PrivateAttr()
    stop: Optional[List[str]] = None

    def __init__(self, temperature: float = 0.7, top_p: float = 0.9, max_tokens: int = 7000, stream: bool = False, stop: Optional[List[str]] = None):
        super().__init__()
        self._llm = AzureChatOpenAI(
            azure_endpoint = os.getenv("AZURE_OPENAI_LLM_MODEL_API_BASE"),
            api_key = os.getenv("AZURE_OPENAI_LLM_MODEL_API_KEY"),
            azure_deployment= os.getenv("AZURE_OPENAI_LLM_MODEL_LLM_MODEL"),
            api_version = os.getenv("AZURE_OPENAI_LLM_MODEL_API_VERSION"),
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=stream,
            stop = stop
        )


    def _call(self, input: str, stop: Optional[List[str]] = None, sys_prompt: Optional[str] = None, history: Optional[List[str]] = None) -> str:
        messages = [{"role": "system", "content": sys_prompt or "You are a helpful AI assistant."}]
        # if history:
        #     for i in range(0, len(history), 2):
        #         messages.append({"role": "user", "content": history[i]})
        #         if i + 1 < len(history):
        #             messages.append({"role": "assistant", "content": history[i + 1]})
        # messages.append({"role": "user", "content": inputs})
        
        # formatted_history = []
        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
                    
        messages.append(HumanMessage(content = input))


        try:
            response = self._llm.invoke(messages)
            return response.content
        except BadRequestError as e:
            # Handle Azure OpenAI content filter error
            raise ContentFilterError("Sorry, your request triggered Azure OpenAI's content management policy. Please modify your prompt and try again.") from e
        except requests.exceptions.RequestException as e:
            print(f"Error during Azure OpenAI API call: {e}")
            raise

    @property
    def _llm_type(self) -> str:
        return "azure_openai_custom_llm"


# llm = AzureCustomLLM()
# print(llm.invoke([{"role":"user","content":"hello"}]))