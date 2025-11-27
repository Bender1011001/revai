import random
import statistics
import threading
import os
from typing import List, Optional
from .refactory_state import ModuleGroup
from .true_maker import RedFlagGuard
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

def measure_model_difficulty(
    model_name: str,
    test_samples: List[dict],
    system_prompt: str,
    temperature: float = 0.3,
    stop_event: Optional[threading.Event] = None
):
    """
    Estimates 'p' (Probability of Success) for the MAKER framework.
    Returns:
        p_score: Estimated success rate (0.0 to 1.0)
        is_feasible: Boolean (is p > 0.5?)
    """
    llm = ChatOllama(
        model=model_name,
        temperature=temperature,
        format="json",
        base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )
    guard = RedFlagGuard(max_output_tokens=1000)
    
    success_count = 0
    total_samples = len(test_samples)
    
    print(f"[-] Calibrating {model_name} on {total_samples} samples...")

    for i, sample in enumerate(test_samples):
        if stop_event and stop_event.is_set():
            print("[-] Calibration stopped by user.")
            break

        # Construct prompt (reuse logic from your maker_nodes.py)
        prompt = f"Function: {sample['name']}\nCode:\n{sample['code']}"
        
        try:
            # Single-shot attempt
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            # 1. Check Red Flags (Did it output valid JSON? Is it too long?)
            # If the model is confused/hallucinating, this will fail.
            # This corresponds to 'v' in the paper (Equation 19).
            is_valid, reason = guard.check_red_flags(response.content, None) # You'd parse JSON first normally
            
            if is_valid:
                # 2. Validator Check (Did it produce usable results?)
                # In reverse engineering, "Correctness" is hard, but "Validity" is checkable.
                # Example: Did it actually rename variables? Did it assume variables that exist?
                # You can reuse your 'refactory_agents.py' validators here.
                if verify_logic_sanity(response.content, sample['variables']):
                    success_count += 1
                else:
                    print(f"    [x] Sample {i} failed logic check")
            else:
                print(f"    [x] Sample {i} red-flagged: {reason}")
                
        except Exception as e:
            print(f"    [!] Error on sample {i}: {e}")

    # Calculate p
    p = success_count / total_samples if total_samples > 0 else 0.0
    
    # Check MAKER feasibility threshold (Section 3.2)
    # The paper proves that if p <= 0.5, voting converges to the WRONG answer.
    is_feasible = p > 0.5
    
    return p, is_feasible

def verify_logic_sanity(response_json, existing_vars):
    """
    A heuristic checker since we don't have ground truth.
    Checks if the model is hallucinating variables.
    """
    try:
        import json
        data = json.loads(response_json)
        # Check if keys are actually in the existing variables
        for old_name in data.keys():
            if old_name not in existing_vars:
                return False # Hallucination = Failure
        return True
    except:
        return False