"""
Refactory Agents: Multi-stage AI agents for full reverse engineering.
"""
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from src.refactory_state import RefactoryState, TypeProposal, RefactoringProposal

# Configuration
MAX_ATTEMPTS = 3
VOTE_THRESHOLD = 2

llm = ChatOllama(
    model="qwen2.5-coder:7b",
    temperature=0.3,
    format="json",
    base_url="http://localhost:11434"
)

# ==================== STAGE 1: TYPE RECOVERY ====================

TYPE_RECOVERY_PROMPT = """You are a reverse engineering expert specializing in type recovery.

Task: Analyze the decompiled C code and recover the correct types for variables.

Input: Pseudo-C code where variables may have incorrect types (e.g., int used as pointer).
Output: JSON map of variable names to their recovered types.

Rules:
1. Look for pointer arithmetic, dereferencing, or struct access patterns
2. If a variable is used with ->, it's likely a pointer
3. If a variable is used in array indexing, check if it's a pointer or array
4. Suggest concrete struct names when you see field access patterns
5. Only output JSON. No commentary.

Output format:
{
  "variable_name": {
    "proposed_type": "MyStruct*",
    "confidence": 0.9,
    "reasoning": "Used with -> operator on line 5"
  }
}"""

def type_recovery_agent(state: RefactoryState):
    """
    Stage 1: Recover types for variables in the module.
    """
    module = state["module"]
    
    # Combine all function code for context
    combined_code = ""
    all_vars = set()
    
    for func in module["functions"]:
        combined_code += f"\n// Function: {func['name']}\n"
        combined_code += func["code"] + "\n"
        all_vars.update(func["variables"])
    
    # Truncate if too large
    if len(combined_code) > 10000:
        combined_code = combined_code[:10000] + "\n...[TRUNCATED]"
    
    msg = f"Module: {module['module_name']}\nVariables: {', '.join(all_vars)}\n\nCode:\n{combined_code}"
    
    try:
        response = llm.invoke([
            SystemMessage(content=TYPE_RECOVERY_PROMPT),
            HumanMessage(content=msg)
        ])
        proposals_dict = json.loads(response.content)
        
        # Convert to TypeProposal format
        proposals = []
        for var_name, info in proposals_dict.items():
            if var_name in all_vars:
                proposals.append({
                    "variable": var_name,
                    "original_type": "unknown",
                    "proposed_type": info.get("proposed_type", "int"),
                    "confidence": info.get("confidence", 0.5),
                    "reasoning": info.get("reasoning", "")
                })
        
        return {"type_proposals": proposals, "attempts": 1}
    
    except Exception as e:
        print(f"[Type Recovery] Error: {e}")
        return {"type_proposals": [], "attempts": 1}

def type_recovery_validator(state: RefactoryState):
    """
    Validate type recovery proposals and commit high-confidence ones.
    """
    proposals = state.get("type_proposals", [])
    confirmed_types = state.get("confirmed_types", {})
    
    # Filter by confidence threshold
    for proposal in proposals:
        if proposal["confidence"] >= 0.7:
            confirmed_types[proposal["variable"]] = proposal["proposed_type"]
    
    return {"confirmed_types": confirmed_types}

# ==================== STAGE 2: REFACTORING ====================

REFACTORING_PROMPT = """You are a code refactoring expert.

Task: Transform decompiled C code into clean, readable source code.

Input: C code with GOTOs, cryptic labels, and poor structure.
Output: Refactored code with proper loops, meaningful labels, and clean structure.

Transformations to apply:
1. Replace GOTO with while/for loops where possible
2. Replace label names like LAB_001234 with meaningful names
3. Simplify nested conditions
4. Add braces for clarity
5. Preserve exact logic - do not change behavior

Output format:
{
  "refactored_code": "cleaned C code here",
  "transformations": ["removed_goto_loop", "renamed_label_exit"]
}"""

def refactoring_agent(state: RefactoryState):
    """
    Stage 3: Refactor functions into clean code.
    """
    module = state["module"]
    confirmed_types = state.get("confirmed_types", {})
    confirmed_renames = state.get("confirmed_renames", {})
    
    proposals = []
    
    for func in module["functions"]:
        code = func["code"]
        
        # Apply confirmed type changes
        for var, var_type in confirmed_types.items():
            # Simple replacement - in production, use proper AST manipulation
            code = code.replace(f"int {var}", f"{var_type} {var}")
        
        # Apply confirmed renames
        for old_name, new_name in confirmed_renames.items():
            code = code.replace(old_name, new_name)
        
        # Truncate if too large
        if len(code) > 8000:
            code = code[:8000] + "\n...[TRUNCATED]"
        
        msg = f"Function: {func['name']}\n\nCode:\n{code}"
        
        try:
            response = llm.invoke([
                SystemMessage(content=REFACTORING_PROMPT),
                HumanMessage(content=msg)
            ])
            result = json.loads(response.content)
            
            proposals.append({
                "function_name": func["name"],
                "original_code": func["code"],
                "refactored_code": result.get("refactored_code", code),
                "transformations": result.get("transformations", []),
                "is_valid": True
            })
        
        except Exception as e:
            print(f"[Refactoring] Error on {func['name']}: {e}")
            proposals.append({
                "function_name": func["name"],
                "original_code": func["code"],
                "refactored_code": func["code"],  # Fallback to original
                "transformations": [],
                "is_valid": False
            })
    
    return {"refactoring_proposals": proposals, "attempts": 1}

def refactoring_validator(state: RefactoryState):
    """
    Validate refactored code (basic syntax check).
    """
    proposals = state.get("refactoring_proposals", [])
    confirmed = []
    
    for proposal in proposals:
        # Basic validation: check for balanced braces
        code = proposal["refactored_code"]
        if code.count("{") == code.count("}") and code.count("(") == code.count(")"):
            confirmed.append(proposal)
        else:
            # Reject malformed code
            print(f"[Refactoring] Rejected {proposal['function_name']}: unbalanced braces/parens")
    
    return {"confirmed_refactorings": confirmed}

# ==================== STAGE 4: SOURCE CODE GENERATION ====================

def source_code_generator(state: RefactoryState):
    """
    Final stage: Generate .c and .h files from refactored code.
    """
    module = state["module"]
    refactorings = state.get("confirmed_refactorings", [])
    
    module_name = module["module_name"]
    
    # Build header file
    header_content = f"""// {module_name}.h
// Auto-generated by Refactory Pipeline

#ifndef {module_name.upper()}_H
#define {module_name.upper()}_H

#include <stdint.h>
#include <stdlib.h>

"""
    
    # Add function declarations
    for refactoring in refactorings:
        # Extract function signature from code
        code_lines = refactoring["refactored_code"].split("\n")
        for line in code_lines:
            if "{" in line and "(" in line:
                signature = line.split("{")[0].strip()
                header_content += f"{signature};\n"
                break
    
    header_content += f"\n#endif // {module_name.upper()}_H\n"
    
    # Build source file
    source_content = f"""// {module_name}.c
// Auto-generated by Refactory Pipeline

#include "{module_name}.h"

"""
    
    # Add all refactored functions
    for refactoring in refactorings:
        source_content += f"\n// {refactoring['function_name']}\n"
        source_content += refactoring["refactored_code"] + "\n\n"
    
    return {
        "final_source_files": {f"{module_name}.c": source_content},
        "final_header_files": {f"{module_name}.h": header_content},
        "current_stage": "complete"
    }