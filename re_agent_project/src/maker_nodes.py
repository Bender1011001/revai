import json
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, RenameProposal

# --- MAKER CONFIGURATION ---
MAX_ATTEMPTS = 5       # Maximum parallel attempts (sequential on 4060)
VOTE_THRESHOLD_K = 2   # Need 2 matching agents to form consensus

# --- MODEL SETUP ---
# Optimized for 4060 Ti 8GB: Local, Quantized, Code-Specialized
llm = ChatOllama(
    model="qwen2.5-coder:7b",
    temperature=0.4,  # Non-zero to generate diverse proposals for voting
    format="json",    # Enforce structured output
    base_url="http://localhost:11434"
)

SYSTEM_PROMPT = """You are a Reverse Engineering Expert.
Your Task: Rename generic variables (iVar1, uVar2, param_1) to semantic names based on code logic.
- Input: Generic C code.
- Output: A JSON map: {"old_name": "new_name"}.
- Constraint 1: Do NOT invent variables. Only rename existing ones.
- Constraint 2: Output JSON ONLY. No commentary.
- Constraint 3: If you cannot determine a name, leave it out."""

def micro_agent_generate(state: AgentState):
    """
    The Worker Node.
    """
    code = state["original_code"]
    # Truncate if massive to save context window
    if len(code) > 12000:
        code = code[:12000] + "\n...[TRUNCATED]"

    vars_list = ", ".join(state["existing_variables"])
    
    msg = f"Function: {state['function_name']}\nVariables Available: {vars_list}\n\nCode:\n{code}"
    
    try:
        # Invoke Local LLM
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=msg)
        ])
        content = json.loads(response.content)
    except Exception:
        # If JSON parse fails, we treat it as a Red Flagged attempt
        return {"proposals": [{"renames": {}, "is_valid": False, "score": 0.0}], "attempts": 1}

    # Basic Type Check
    if not isinstance(content, dict):
        return {"proposals": [{"renames": {}, "is_valid": False, "score": 0.0}], "attempts": 1}

    return {"proposals": [{"renames": content, "is_valid": True, "score": 1.0}], "attempts": 1}

def red_flag_guard(state: AgentState):
    """
    The Red-Flagger Node.
    Filters out hallucinations before they reach the voting booth.
    """
    latest_proposal = state["proposals"][-1]
    
    if not latest_proposal["is_valid"]:
        return {} # Already dead

    renames = latest_proposal["renames"]
    valid_vars = state["existing_variables"]
    
    # 1. Hallucination Check
    # If the agent tries to rename "iVar99" but "iVar99" isn't in the function, RED FLAG.
    # We discard the entire proposal to prevent poisoning the consensus.
    keys = list(renames.keys())
    if any(k not in valid_vars for k in keys):
        # Mark the last proposal invalid (in memory modification)
        state["proposals"][-1]["is_valid"] = False
        state["proposals"][-1]["score"] = 0.0
        
    # 2. Laziness Check
    # If new name == old name, remove it from map
    clean_renames = {k: v for k, v in renames.items() if k != v}
    state["proposals"][-1]["renames"] = clean_renames

    return {} # No state schema update needed, purely validation logic

def voting_consensus(state: AgentState):
    """
    The Consensus Node.
    Implements "First-to-ahead-by-k" voting.
    """
    valid_proposals = [p["renames"] for p in state["proposals"] if p["is_valid"] and p["renames"]]
    
    if not valid_proposals:
        return {"final_renames": None}

    # Count votes for specific renaming MAPS
    # We strictly require the entire map to match for simplicity, 
    # or you can vote on individual variables. Here we vote on the set.
    counts = {}
    for p in valid_proposals:
        # Serialize to make hashable
        p_str = json.dumps(p, sort_keys=True)
        counts[p_str] = counts.get(p_str, 0) + 1

    # Check for winner
    for p_str, count in counts.items():
        if count >= VOTE_THRESHOLD_K:
            return {"final_renames": json.loads(p_str)}
            
    return {"final_renames": None}