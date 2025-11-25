"""
MAKER Framework Integration
Uses True MAKER (arXiv:2511.09030v1) implementation from true_maker.py

This module provides backward compatibility while using the proper
First-to-ahead-by-k voting and red-flagging from the paper.
"""
import json
from src.state import AgentState
from src.true_maker import create_maker_agent

# Default MAKER configuration
# These can be tuned based on the specific task
DEFAULT_TARGET_RELIABILITY = 0.95  # 95% success probability
DEFAULT_ERROR_RATE = 0.02  # 2% estimated per-step error rate
DEFAULT_MAX_TOKENS = 1000  # Maximum output length before red-flagging

SYSTEM_PROMPT = """You are a Reverse Engineering Expert.
Your Task: Rename generic variables (iVar1, uVar2, param_1) to semantic names based on code logic.
- Input: Generic C code.
- Output: A JSON map: {"old_name": "new_name"}.
- Constraint 1: Do NOT invent variables. Only rename existing ones.
- Constraint 2: Output JSON ONLY. No commentary.
- Constraint 3: If you cannot determine a meaningful name, leave it out."""

# Global MAKER agent (initialized on first use)
_maker_agent = None
_maker_config = None


def get_maker_agent():
    """Get or create the global MAKER agent."""
    global _maker_agent, _maker_config
    
    if _maker_agent is None:
        _maker_agent, _maker_config = create_maker_agent(
            target_reliability=DEFAULT_TARGET_RELIABILITY,
            estimated_error_rate=DEFAULT_ERROR_RATE,
            max_output_tokens=DEFAULT_MAX_TOKENS,
            model="qwen2.5-coder:7b",
            temperature=0.3
        )
    
    return _maker_agent, _maker_config


def true_maker_rename(state: AgentState) -> dict:
    """
    Use True MAKER framework for variable renaming.
    
    This implements the full MAKER algorithm:
    - Sequential voting (Algorithm 2)
    - Red-flagging (Algorithm 3)
    - Dynamic k calculation (Equation 14)
    
    Returns updated state with final_renames.
    """
    agent, config = get_maker_agent()
    
    code = state["original_code"]
    if len(code) > 12000:
        keep_size = 6000
        code = code[:keep_size] + "\n...[TRUNCATED]...\n" + code[-keep_size:]
    
    vars_list = ", ".join(state["existing_variables"])
    prompt = f"Function: {state['function_name']}\nVariables: {vars_list}\n\nCode:\n{code}"
    
    # Run True MAKER voting
    renames, total_samples, valid_samples = agent.do_voting(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        existing_variables=state["existing_variables"]
    )
    
    print(f"  [MAKER] {state['function_name']}: {total_samples} samples ({valid_samples} valid), k={config.k}")
    
    if renames:
        print(f"    ✓ Consensus: {len(renames)} variables renamed")
        return {"final_renames": renames}
    else:
        print(f"    ✗ No consensus reached")
        return {"final_renames": None}


# Legacy compatibility functions
# These maintain the old API but use True MAKER internally

def micro_agent_generate(state: AgentState):
    """
    DEPRECATED: Use true_maker_rename instead.
    Maintained for backward compatibility with existing code.
    """
    # This now calls the True MAKER implementation
    return true_maker_rename(state)


def red_flag_guard(state: AgentState):
    """
    DEPRECATED: Red-flagging is now built into True MAKER.
    This is a no-op for backward compatibility.
    """
    return {}


def voting_consensus(state: AgentState):
    """
    DEPRECATED: Voting is now built into True MAKER.
    This is a no-op for backward compatibility.
    """
    return {}