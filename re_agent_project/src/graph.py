from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.maker_nodes import micro_agent_generate, red_flag_guard, voting_consensus, MAX_ATTEMPTS

def should_continue(state: AgentState):
    """
    Determines if we loop back to the Micro-Agent or finish.
    """
    # 1. Consensus Reached? -> End
    if state.get("final_renames"):
        return "end"
    
    # 2. Max Attempts Reached? -> End (Fail)
    if state["attempts"] >= MAX_ATTEMPTS:
        return "end"
        
    # 3. Else -> Loop back to generate another proposal
    return "generate"

# --- GRAPH DEFINITION ---
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("generate", micro_agent_generate)
workflow.add_node("red_flag", red_flag_guard)
workflow.add_node("vote", voting_consensus)

# Define Edges
workflow.set_entry_point("generate")
workflow.add_edge("generate", "red_flag")
workflow.add_edge("red_flag", "vote")

# Cyclic Conditional Edge
workflow.add_conditional_edges(
    "vote",
    should_continue,
    {
        "end": END,
        "generate": "generate"
    }
)

app = workflow.compile()