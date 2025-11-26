# src/agent_lightning_bridge.py
import time
import json
import threading
import uuid
from typing import Dict, List, Any
from langchain_core.messages import BaseMessage

class AgentLightningClient:
    """
    Client SDK that logs 'State-Action-Reward' tuples to disk (or a remote training server).
    """
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.session_id = str(uuid.uuid4())
        self._lock = threading.Lock()
        
    def log_trace(self, state: str, action: str, reward: float, next_state: str, metadata: Dict = None):
        """
        Logs a standard RL trace: (s, a, r, s')
        """
        payload = {
            "session_id": self.session_id,
            "agent": self.agent_name,
            "timestamp": time.time(),
            "trace": {
                "state": state,       # The Prompt
                "action": action,     # The Model Output
                "reward": reward,     # The Signal (+1.0, -0.5, etc)
                "next_state": next_state,
            },
            "metadata": metadata or {}
        }
        self._log_to_disk(payload)

    def _log_to_disk(self, payload):
        with self._lock:
            with open("lightning_traces.jsonl", "a") as f:
                f.write(json.dumps(payload) + "\n")

class LightningLLMWrapper:
    """
    Proxy that wraps ChatOllama to intercept inputs/outputs for logging.
    """
    def __init__(self, wrapped_llm, client: AgentLightningClient):
        self._llm = wrapped_llm
        self.client = client
        self.latest_prompt = ""
        self.latest_response = ""

    def bind(self, **kwargs):
        """
        Support for LangChain's .bind() method to pass runtime args (like temperature).
        Returns a new wrapper around the bound LLM.
        """
        return LightningLLMWrapper(self._llm.bind(**kwargs), self.client)

    def invoke(self, input_messages: List[BaseMessage], **kwargs):
        # 1. Capture State (Prompt)
        if isinstance(input_messages, list):
            prompt_str = "\n".join([m.content for m in input_messages])
        else:
            prompt_str = str(input_messages)
        self.latest_prompt = prompt_str

        # 2. Execute Action (Call Real Model)
        response = self._llm.invoke(input_messages, **kwargs)
        
        # 3. Capture Action (Response)
        self.latest_response = response.content
        return response