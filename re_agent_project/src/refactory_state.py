from typing import List, Dict, Optional, Annotated
from typing_extensions import TypedDict
import operator

class FunctionUnit(TypedDict):
    """A single function extracted from the binary."""
    address: str
    name: str
    code: str
    variables: List[str]
    var_types: Dict[str, str]
    calls: List[Dict[str, str]]  # Functions this function calls
    param_count: int
    return_type: str

class ModuleGroup(TypedDict):
    """A group of related functions that will become a single source file."""
    module_name: str  # e.g., "auth_module", "network_module"
    functions: List[FunctionUnit]
    shared_types: List[str]  # Custom types used across functions

class TypeProposal(TypedDict):
    """A proposed type recovery for variables."""
    variable: str
    original_type: str
    proposed_type: str
    confidence: float
    reasoning: str

class RefactoringProposal(TypedDict):
    """A proposed refactoring transformation."""
    function_name: str
    original_code: str
    refactored_code: str
    transformations: List[str]  # e.g., ["removed_goto", "added_loop"]
    is_valid: bool

class RefactoryState(TypedDict):
    """State for the multi-stage Refactory pipeline."""
    # Input
    module: ModuleGroup
    
    # Stage 1: Type Recovery
    type_proposals: Annotated[List[TypeProposal], operator.add]
    confirmed_types: Dict[str, str]  # variable -> type mapping
    struct_definitions: List[str]  # Discovered struct definitions
    
    # Stage 2: Renaming (reusing existing MAKER logic)
    rename_proposals: Annotated[List[Dict[str, str]], operator.add]
    confirmed_renames: Dict[str, str]
    
    # Stage 3: Refactoring
    refactoring_proposals: Annotated[List[RefactoringProposal], operator.add]
    confirmed_refactorings: List[RefactoringProposal]
    
    # Output
    final_source_files: Dict[str, str]  # filename -> source code
    final_header_files: Dict[str, str]  # filename -> header code
    
    # Processing
    current_stage: str  # "type_recovery", "renaming", "refactoring", "complete"
    attempts: int