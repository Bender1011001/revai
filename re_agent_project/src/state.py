from typing import List, Dict, Optional, Annotated
from typing_extensions import TypedDict
import operator

class RenameProposal(TypedDict):
    """A single attempt by the Micro-Agent to rename variables."""
    renames: Dict[str, str]
    score: float  # 1.0 = Valid Syntax, 0.0 = Red Flagged
    is_valid: bool

class AgentState(TypedDict):
    # --- INPUTS ---
    function_name: str
    original_code: str
    existing_variables: List[str]
    
    # --- INTERNAL STATE ---
    # 'operator.add' allows us to append proposals rather than overwrite them
    proposals: Annotated[List[RenameProposal], operator.add] 
    attempts: int
    
    # --- OUTPUT ---
    final_renames: Optional[Dict[str, str]]