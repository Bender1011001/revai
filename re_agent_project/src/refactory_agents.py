"""
Refactory Agents: Multi-stage AI agents for full reverse engineering.
"""
import json
import os
import re
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from src.refactory_state import RefactoryState, TypeProposal, RefactoringProposal

# Configuration
MAX_ATTEMPTS = 3
VOTE_THRESHOLD = 2

# Initialize LLM with error handling for missing environment variables
try:
    llm = ChatOllama(
        model="qwen2.5-coder:7b",
        temperature=0.3,
        format="json",
        base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )
except Exception as e:
    print(f"[Refactory Agents] Warning: Failed to initialize ChatOllama: {e}")
    llm = None

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
    
    if not llm:
        print("[Type Recovery] Error: LLM not initialized")
        return {"type_proposals": [], "attempts": 1}

    try:
        response = llm.invoke([
            SystemMessage(content=TYPE_RECOVERY_PROMPT),
            HumanMessage(content=msg)
        ])
        
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            print("[Type Recovery] Error: Invalid JSON response")
            return {"type_proposals": [], "attempts": 1}
        
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

REFACTORING_PROMPT = """You are a code refactoring expert specializing in porting decompiled code to C# / .NET 8.

Task: Analyze the decompiled code and refactor it into clean, readable C# source code.

First, determine if the source is **Dalvik/Java** (high-level) or **x86/PE** (low-level C).
*   If **Java**: Refactor to standard C# classes.
*   If **x86**: Refactor to C# `unsafe` blocks or `IntPtr` logic to preserve memory manipulation fidelity.

Input: Decompiled code with GOTOs, cryptic labels, and poor structure.
Output: Refactored C# code with proper loops, meaningful labels, and clean structure.

Transformations to apply:
1. Replace GOTO with while/for loops where possible
2. Replace label names like LAB_001234 with meaningful names
3. Simplify nested conditions
4. Add braces for clarity
5. Preserve exact logic - do not change behavior
6. Convert types to C# equivalents based on source architecture
7. Use standard C# naming conventions (PascalCase for methods, camelCase for locals)
8. Ensure methods are static if they don't rely on instance state

Output format:
{
  "refactored_code": "cleaned C# code here",
  "transformations": ["removed_goto_loop", "renamed_label_exit", "converted_to_csharp"]
}"""

def _safe_replace(code, target, replacement, context_next=None):
    """
    Safely replace target identifier with replacement, ignoring strings and comments.
    If context_next is provided, only replaces target if followed by context_next.
    Handles C-style pointer syntax by consuming '*' and whitespace between type and var.
    """
    # Regex patterns for C/C++ syntax
    pat_comment_multi = r'/\*[\s\S]*?\*/'
    pat_comment_single = r'//.*'
    pat_string = r'"(?:\\.|[^"\\])*"'
    pat_char = r"'(?:\\.|[^'\\])*'"
    
    # Combined pattern to skip
    pat_skip = f'{pat_comment_multi}|{pat_comment_single}|{pat_string}|{pat_char}'
    
    if context_next:
        # Regex pattern that matches:
        # Word boundary \b
        # The old_type (escaped)
        # Optional whitespace \s*
        # Zero or more asterisks \*
        # Optional whitespace \s*
        # The var_name (escaped)
        # Word boundary \b
        pattern_target = (
            r'\b' + re.escape(target) +
            r'\s*\**\s*' +
            re.escape(context_next) +
            r'\b'
        )
        # Replace the entire matched sequence with new_type + " " + var_name
        replacement_text = f"{replacement} {context_next}"
    else:
        # Simple rename
        pattern_target = r'\b' + re.escape(target) + r'\b'
        replacement_text = replacement
        
    # Compile regex with named groups
    # We match SKIP patterns first, then our TARGET pattern
    regex = re.compile(f'({pat_skip})|(?P<MATCH>{pattern_target})', re.MULTILINE)
    
    def replacer(match):
        if match.group('MATCH'):
            return replacement_text
        else:
            # Return the skipped content (comment/string) as is
            return match.group(0)
            
    return regex.sub(replacer, code)

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
            # Replace "int var" -> "var_type var"
            # We replace "int" with "var_type" ONLY if followed by "var"
            code = _safe_replace(code, "int", var_type, context_next=var)
        
        # Apply confirmed renames
        for old_name, new_name in confirmed_renames.items():
            code = _safe_replace(code, old_name, new_name)
        
        # Truncate if too large
        if len(code) > 8000:
            code = code[:8000] + "\n...[TRUNCATED]"
        
        msg = f"Function: {func['name']}\n\nCode:\n{code}"
        
        if not llm:
            print(f"[Refactoring] Error on {func['name']}: LLM not initialized")
            proposals.append({
                "function_name": func["name"],
                "original_code": func["code"],
                "refactored_code": "// [WARNING] REFACTORING FAILED (LLM Error). ORIGINAL CODE BELOW:\n" + func["code"],
                "transformations": [],
                "is_valid": False
            })
            continue

        try:
            response = llm.invoke([
                SystemMessage(content=REFACTORING_PROMPT),
                HumanMessage(content=msg)
            ])
            
            try:
                result = json.loads(response.content)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON response from LLM")

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
                "refactored_code": "// [WARNING] REFACTORING FAILED. ORIGINAL CODE BELOW:\n" + func["code"],  # Fallback to original with warning
                "transformations": [],
                "is_valid": False
            })
    
    return {"refactoring_proposals": proposals, "attempts": 1}

def refactoring_validator(state: RefactoryState):
    proposals = state.get("refactoring_proposals", [])
    confirmed = []
    
    for proposal in proposals:
        code = proposal["refactored_code"]
        
        # GARBAGE CHECK: Unbalanced braces = garbage
        if code.count("{") != code.count("}"):
            print(f"[Refactoring] REJECTED {proposal['function_name']}: Unbalanced braces (-1.0)")
            # In a full implementation, you'd log this -1.0 to the client here
        else:
            confirmed.append(proposal)

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