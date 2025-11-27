"""
MAKER Framework Integration
Uses True MAKER (arXiv:2511.09030v1) implementation from true_maker.py

This module provides backward compatibility while using the proper
First-to-ahead-by-k voting and red-flagging from the paper.
"""
import json
from src.refactory_state import RefactoryState as AgentState
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

# No global state - agents are instantiated locally per function call


def true_maker_rename(state: AgentState, agent=None) -> dict:
    """
    Use True MAKER framework for variable renaming.

    This implements the full MAKER algorithm:
    - Maximal Agentic Decomposition (MAD): One agent per variable
    - Sequential voting (Algorithm 2)
    - Red-flagging (Algorithm 3)
    - Dynamic k calculation (Equation 14)

    Thread-safe: Creates a new agent instance per call to avoid race conditions.

    Returns updated state with final_renames.
    """
    vars_to_rename = state["existing_variables"]
    total_steps = len(vars_to_rename)
    
    if total_steps == 0:
        return {"final_renames": {}}

    # Create a new agent instance locally for thread safety if not provided
    if agent is None:
        agent, config = create_maker_agent(
            target_reliability=DEFAULT_TARGET_RELIABILITY,
            estimated_error_rate=DEFAULT_ERROR_RATE,
            max_output_tokens=DEFAULT_MAX_TOKENS,
            model="qwen2.5-coder:7b",
            temperature=0.3,
            total_steps=total_steps  # Pass total steps for correct k calculation
        )
    else:
        config = agent.config

    code = state["original_code"]
    # Increased limit to avoid cutting off context for larger functions
    # Modern LLMs can handle larger contexts (e.g. 32k, 128k)
    if len(code) > 32000:
        keep_size = 16000
        code = code[:keep_size] + "\n...[TRUNCATED]...\n" + code[-keep_size:]

    print(f"  [MAKER] Processing {state['function_name']} with {total_steps} variables (k={config.k})")
    
    final_renames = {}
    total_samples_all = 0
    
    # Maximal Decomposition: Iterate through each variable
    for i, var_name in enumerate(vars_to_rename):
        # Focused prompt for single variable
        prompt = (
            f"Function: {state['function_name']}\n"
            f"Code:\n{code}\n\n"
            f"Task: Rename ONLY the variable '{var_name}'.\n"
            f"If it needs renaming, return: {{\" {var_name} \": \"new_name\"}}\n"
            f"If it should stay as is, return: {{\" {var_name} \": \"{var_name}\"}}\n"
            f"Do not rename any other variables."
        )

        # Run True MAKER voting for this single step
        renames, total_samples, valid_samples = agent.do_voting(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            existing_variables=state["existing_variables"],
            required_keys=[var_name],  # Enforce that this variable is in output
            callback=state.get("consensus_callback")
        )
        
        total_samples_all += total_samples
        
        if renames and var_name in renames:
            new_name = renames[var_name]
            if new_name != var_name:
                final_renames[var_name] = new_name
                print(f"    [{i+1}/{total_steps}] {var_name} -> {new_name} (k={config.k})")
            else:
                print(f"    [{i+1}/{total_steps}] {var_name} -> (unchanged)")
        else:
            print(f"    [{i+1}/{total_steps}] {var_name} -> (failed to converge)")

    print(f"  [MAKER] Completed {state['function_name']}: {total_samples_all} total samples")

    if final_renames:
        print(f"    ✓ Consensus: {len(final_renames)} variables renamed")
        return {"final_renames": final_renames}
    else:
        print(f"    ✗ No renames generated")
        return {"final_renames": None}


# Legacy compatibility functions
# These maintain the old API but use True MAKER internally

def micro_agent_generate(state: AgentState):
    """
    DEPRECATED: Use true_maker_rename instead.
    Maintained for backward compatibility with existing code.
    """
    # This now calls the True MAKER implementation (thread-safe)
    return true_maker_rename(state)


def red_flag_guard(state: AgentState):
    """
    DEPRECATED: Red-flagging is now built into True MAKER.
    This is a no-op for backward compatibility.
    """
    # Ensure we return a valid state update even if empty
    return {}


def voting_consensus(state: AgentState):
    """
    DEPRECATED: Voting is now built into True MAKER.
    This is a no-op for backward compatibility.
    """
    # Ensure we return a valid state update even if empty
    return {}