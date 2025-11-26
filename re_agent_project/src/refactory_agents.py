"""
Refactory Agents: Multi-stage AI agents for full reverse engineering.
"""
import json
import re
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
  "variables": {
    "variable_name": {
      "proposed_type": "MyStruct*",
      "confidence": 0.9,
      "reasoning": "Used with -> operator on line 5"
    }
  },
  "struct_definitions": [
    "typedef struct MyStruct { int x; int y; } MyStruct;"
  ]
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
        data = json.loads(response.content)
        
        # Support both formats (flat dict or nested with struct_definitions)
        if "variables" in data:
            proposals_dict = data["variables"]
            struct_defs = data.get("struct_definitions", [])
        else:
            proposals_dict = data
            struct_defs = []
        
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
        
        return {"type_proposals": proposals, "struct_definitions": struct_defs, "attempts": 1}
    
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

REFACTORING_PROMPT = """You are a code refactoring expert specializing in porting C code to C# / .NET 8.

Task: Transform decompiled C code into clean, readable C# source code.

Input: C code with GOTOs, cryptic labels, and poor structure.
Output: Refactored C# code with proper loops, meaningful labels, and clean structure.

Transformations to apply:
1. Replace GOTO with while/for loops where possible
2. Replace label names like LAB_001234 with meaningful names
3. Simplify nested conditions
4. Add braces for clarity
5. Preserve exact logic - do not change behavior
6. Convert C types to C# equivalents (e.g., char* -> string, int -> int, structs -> classes/structs)
7. Use standard C# naming conventions (PascalCase for methods, camelCase for locals)
8. Ensure methods are static if they don't rely on instance state (which is likely for decompiled C)

Output format:
{
  "refactored_code": "cleaned C# code here",
  "transformations": ["removed_goto_loop", "renamed_label_exit", "converted_to_csharp"]
}"""

def _safe_replace(code, target_pattern, replacement):
    """
    Safely replace target_pattern with replacement, ignoring strings and comments.
    """
    # Regex to match strings, comments, OR the target
    # 1. Strings: "..." (handling escaped quotes)
    # 2. Single-line comments: //...
    # 3. Multi-line comments: /*...*/
    # 4. The target pattern
    # Note: We use a non-capturing group for the string content to handle escaped quotes correctly.
    string_pattern = r'"(?:\\.|[^"\\])*"'
    comment_single = r'//.*?$'
    comment_multi = r'/\*.*?\*/'
    
    full_pattern = f'({string_pattern}|{comment_single}|{comment_multi})|({target_pattern})'
    
    def replace_callback(match):
        # Group 1: String or Comment (return unchanged)
        if match.group(1):
            return match.group(1)
        # Group 2: Target (return replacement)
        return replacement
        
    return re.sub(full_pattern, replace_callback, code, flags=re.DOTALL | re.MULTILINE)

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
            # Use regex for safe replacement of declarations
            # Matches "int var" with word boundaries
            target_pattern = r"\bint\s+" + re.escape(var) + r"\b"
            replacement = f"{var_type} {var}"
            code = _safe_replace(code, target_pattern, replacement)
        
        # Apply confirmed renames
        for old_name, new_name in confirmed_renames.items():
            # Use regex with word boundaries to prevent substring matching errors
            target_pattern = r"\b" + re.escape(old_name) + r"\b"
            code = _safe_replace(code, target_pattern, new_name)
        
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
    Final stage: Generate .cs files from refactored code.
    """
    module = state["module"]
    refactorings = state.get("confirmed_refactorings", [])
    
    module_name = module["module_name"]
    # Convert module_name to PascalCase for class name
    class_name = "".join(x.title() for x in module_name.replace("-", "_").split("_"))
    
    # Build C# file
    source_content = f"""// {class_name}.cs
// Auto-generated by Refactory Pipeline

using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace RefactoredApp
{{
    public static class {class_name}
    {{
"""
    
    # Add discovered struct definitions (commented out as they are likely C syntax)
    struct_defs = state.get("struct_definitions", [])
    if struct_defs:
        source_content += "        // Discovered Structs (Original C definitions)\n"
        for struct_def in struct_defs:
            source_content += f"        /*\n{struct_def}\n        */\n\n"

    # Add all refactored functions
    for refactoring in refactorings:
        source_content += f"        // Original: {refactoring['function_name']}\n"
        # Indent the code
        code = refactoring["refactored_code"]
        indented_code = "\n".join("        " + line for line in code.split("\n"))
        source_content += indented_code + "\n\n"
    
    source_content += "    }\n}\n"
    
    return {
        "final_source_files": {f"{class_name}.cs": source_content},
        "final_header_files": {},
        "current_stage": "complete"
    }