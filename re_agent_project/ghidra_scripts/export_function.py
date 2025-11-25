# @author The Ghidra Whisperer
# @category AI_Bridge

import json
import os
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

def run():
    # CONFIGURATION: Set via env var or default to /tmp
    output_dir = os.environ.get("GHIDRA_EXPORT_DIR", "/tmp/ghidra_bridge")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    program = currentProgram
    decomp = DecompInterface()
    decomp.openProgram(program)
    monitor = ConsoleTaskMonitor()
    
    func_manager = program.getFunctionManager()
    functions = func_manager.getFunctions(True)
    
    export_data = []
    
    # SAFETY LIMIT: Process first 50 functions to test hardware loop
    # Remove this limit in production
    count = 0
    limit = 50

    print("Starting Atomic Decomposition...")

    for func in functions:
        if count >= limit:
            break
            
        # Skip tiny functions (thunks/wrappers)
        if func.getBody().getNumAddresses() < 10:
            continue

        results = decomp.decompileFunction(func, 30, monitor)
        
        if results.decompileCompleted():
            code = results.getDecompiledFunction().getC()
            entry_point = func.getEntryPoint().toString()
            name = func.getName()
            
            # Extract variables for the "Red Flag" validator
            vars_list = []
            high_func = results.getHighFunction()
            if high_func:
                lsm = high_func.getLocalSymbolMap()
                symbols = lsm.getSymbols()
                for sym in symbols:
                    vars_list.append(sym.getName())

            # Filter out functions that are already named well or too small
            if len(code) > 50: 
                export_data.append({
                    "address": entry_point,
                    "name": name,
                    "code": code,
                    "variables": vars_list
                })
                count += 1
                print("Exported atomic unit: " + name)

    output_file = os.path.join(output_dir, "dataset_dirty.json")
    with open(output_file, "w") as f:
        json.dump(export_data, f, indent=2)
    
    print("Decomposition Complete. Data saved to: " + output_file)

if __name__ == "__main__":
    run()