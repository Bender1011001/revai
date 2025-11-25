import os
import json
from src.graph import app

def main():
    # 1. Load Data
    DATA_PATH = os.environ.get("GHIDRA_EXPORT_PATH", "/tmp/ghidra_bridge/dataset_dirty.json")
    
    if not os.path.exists(DATA_PATH):
        print(f"CRITICAL: Data file not found at {DATA_PATH}")
        print("Please run 'export_function.py' inside Ghidra first.")
        return

    with open(DATA_PATH, 'r') as f:
        functions = json.load(f)

    results = []
    total = len(functions)
    print(f"--- Starting MAKER Loop on {total} Atomic Units ---")

    # 2. Atomic Processing Loop
    for idx, func in enumerate(functions):
        print(f"[{idx+1}/{total}] Processing: {func['name']}")
        
        initial_state = {
            "function_name": func["name"],
            "original_code": func["code"],
            "existing_variables": func["variables"],
            "proposals": [],
            "attempts": 0,
            "final_renames": None
        }

        # Run the LangGraph Cycle
        try:
            final_state = app.invoke(initial_state)
            renames = final_state.get("final_renames")
            
            if renames:
                print(f"  [+] Consensus Reached! {len(renames)} vars renamed.")
                results.append({
                    "address": func["address"],
                    "renames": renames
                })
            else:
                print("  [-] No Consensus. Skipping.")
                
        except Exception as e:
            print(f"  [!] Error in graph execution: {e}")

    # 3. Save Results
    output_path = os.path.join(os.path.dirname(DATA_PATH), "renames.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[SUCCESS] Pipeline finished. Results saved to {output_path}")
    print("Run 'import_renames.py' in Ghidra to apply changes.")

if __name__ == "__main__":
    main()