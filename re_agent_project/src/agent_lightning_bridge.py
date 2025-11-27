import json
import time
import uuid
import os
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

@dataclass
class Trace:
    trace_id: str
    step_id: int
    state: str
    action: str
    reward: float
    next_state: str
    metadata: Dict[str, Any]

class AgentLightningClient:
    """
    Client for the Agent Lightning RL framework.
    Logs execution traces to a local file (simulating the Lightning Server).
    """
    def __init__(self, log_dir: str = "lightning_logs", agent_name: str = "default_agent"):
        self.log_dir = log_dir
        self.agent_name = agent_name
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.current_trace_id = str(uuid.uuid4())
        self.step_counter = 0
        self.traces = []
        self.lock = threading.Lock()

    def log_transition(self, state: str, action: str, reward: float, next_state: str, metadata: Dict = None):
        """Log a State-Action-Reward-State (SARS) tuple."""
        with self.lock:
            self.step_counter += 1
            trace = Trace(
                trace_id=self.current_trace_id,
                step_id=self.step_counter,
                state=state,
                action=action,
                reward=reward,
                next_state=next_state,
                metadata=metadata or {}
            )
            self.traces.append(trace)
            self._flush_to_disk()

    def _flush_to_disk(self):
        filename = os.path.join(self.log_dir, f"trace_{self.current_trace_id}.jsonl")
        with open(filename, "a") as f:
            # Convert dataclass to dict manually or use asdict
            latest = self.traces[-1]
            record = {
                "agent_name": self.agent_name,
                "trace_id": latest.trace_id,
                "step": latest.step_id,
                "state": latest.state,
                "action": latest.action,
                "reward": latest.reward,
                "next_state": latest.next_state,
                "metadata": latest.metadata,
                "timestamp": time.time()
            }
            f.write(json.dumps(record) + "\n")

class LightningLLMWrapper:
    """
    Wrapper for LangChain ChatModels that intercepts invocations
    to log actions for Agent Lightning.
    """
    def __init__(self, llm: BaseChatModel, client: AgentLightningClient):
        self._llm = llm  # Store as _llm for test compatibility
        self.llm = llm   # Keep for backward compatibility
        self.client = client

    def invoke(self, input: List[BaseMessage], **kwargs):
        # Capture State (Prompt)
        prompt_str = str(input)
        
        # Execute Action (LLM Generation)
        start_time = time.time()
        response = self._llm.invoke(input, **kwargs)
        duration = time.time() - start_time
        
        # We log the "Action" here. The "Reward" usually comes later
        # from the environment (Voting or Compiler), so we might log
        # a placeholder or use this wrapper just for prompt/response capture.
        # For this integration, the VotingAgent handles the explicit logging.
        
        return response
        
    def bind(self, **kwargs):
        # Pass through bind calls (e.g. for temperature)
        return LightningLLMWrapper(self._llm.bind(**kwargs), self.client)