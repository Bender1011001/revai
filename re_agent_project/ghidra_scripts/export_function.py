# @author The Ghidra Whisperer
# @category AI_Bridge
# REFACTORY v2.0: Enhanced Export with Call Graph and Type Information

import json
import os
import tempfile
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.model.symbol import RefType

def run():
    # CONFIGURATION
    default_dir = os.path.join(tempfile.gettempdir(), "ghidra_bridge")
    output_dir = os.environ.get("GHIDRA_EXPORT_DIR", default_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    program = currentProgram
    decomp = DecompInterface()
    decomp.openProgram(program)
    monitor = ConsoleTaskMonitor()
    
    func_manager = program.getFunctionManager()
    functions = func_manager.getFunctions(True)
    
    export_data = []
    call_graph = {}  # Maps function address to list of called function addresses
    
    # Limit for testing
    count = 0
    limit = int(os.environ.get("GHIDRA_EXPORT_LIMIT", 50))

    # Load dynamic keywords from Environment
    keywords_str = os.environ.get("GHIDRA_SEARCH_KEYWORDS", "")
    INTERESTING_STRINGS = [k.strip() for k in keywords_str.split(",")] if keywords_str else []
    
    # Fallback defaults if AI failed or empty
    if not INTERESTING_STRINGS:
        INTERESTING_STRINGS = ["MainActivity", "onCreate"]

    print("Targeting Functions containing: " + str(INTERESTING_STRINGS))
    print("Starting Enhanced Atomic Decomposition...")

    for func in functions:
        if count >= limit: break
        if func.getBody().getNumAddresses() < 6: continue

        # --- FILTERING LOGIC START ---
        # Get the full namespace path (e.g., "android::support::v4::app")
        ns = func.getParentNamespace()
        ns_name = ns.getName(True) if ns else ""

        if not ns_name:
            ns_name = "Global_Functions"

        # New Generic Filter Logic
        IGNORE_NAMESPACES = [
            # Removed "androidx", "kotlin", "android", "java", "google" to allow Android/Java API calls
            "std", "msvcrt", "kernel32", "user32", "ntdll"     # Windows/C++ Standard
        ]
        # Check if any ignored namespace is in the current namespace name (case-insensitive)
        if any(lib in ns_name.lower() for lib in IGNORE_NAMESPACES):
            continue
        # --- FILTERING LOGIC END ---

        # Check if function name matches ANY keyword
        is_important = False
        for kw in INTERESTING_STRINGS:
            if kw.lower() in func.getName().lower():
                is_important = True
                break
            # Check namespace/class name too
            if ns_name and kw.lower() in ns_name.lower():
                is_important = True
                break
        
        if not is_important:
            continue

        results = decomp.decompileFunction(func, 30, monitor)
        
        if results.decompileCompleted():
            code = results.getDecompiledFunction().getC()
            entry_point = func.getEntryPoint().toString()
            name = func.getName()
            
            # Extract variables with type information
            vars_list = []
            var_types = {}
            high_func = results.getHighFunction()
            if high_func:
                lsm = high_func.getLocalSymbolMap()
                symbols = lsm.getSymbols()
                for sym in symbols:
                    var_name = sym.getName()
                    vars_list.append(var_name)
                    # Get data type if available
                    data_type = sym.getDataType()
                    if data_type:
                        var_types[var_name] = data_type.getName()

            # Extract call graph information
            called_functions = []
            for ref in func.getSymbol().getReferences():
                ref_type = ref.getReferenceType()
                if ref_type.isCall():
                    to_addr = ref.getToAddress()
                    called_func = func_manager.getFunctionAt(to_addr)
                    if called_func:
                        called_functions.append({
                            "address": to_addr.toString(),
                            "name": called_func.getName()
                        })

            if len(code) > 50: 
                export_data.append({
                    "address": entry_point,
                    "name": name,
                    "code": code,
                    "variables": vars_list,
                    "var_types": var_types,
                    "calls": called_functions,
                    "param_count": func.getParameterCount(),
                    "return_type": func.getReturnType().getName() if func.getReturnType() else "void"
                })
                count += 1
                print("Exported: " + name + " (calls " + str(len(called_functions)) + " functions)")

    # Save main dataset
    output_file = os.path.join(output_dir, "dataset_dirty.json")
    with open(output_file, "w") as f:
        json.dump(export_data, f, indent=2)
    
    print("Enhanced decomposition complete. Data saved to: " + output_file)

if __name__ == "__main__":
    run()