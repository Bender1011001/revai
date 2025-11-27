# @author The Ghidra Whisperer
# @category AI_Bridge

import json
import os
import tempfile
from ghidra.program.model.pcode import HighFunctionDBUtil
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.model.symbol import SourceType

def run():
    default_path = os.path.join(tempfile.gettempdir(), "ghidra_bridge", "renames.json")
    input_file = os.environ.get("GHIDRA_IMPORT_FILE", default_path)
    if not os.path.exists(input_file):
        print("No rename file found at: " + input_file)
        return

    with open(input_file, "r") as f:
        renames_db = json.load(f)

    program = currentProgram
    decomp = DecompInterface()
    decomp.openProgram(program)
    monitor = ConsoleTaskMonitor()

    print("Applying Consensus Renames...")

    for item in renames_db:
        addr_str = item.get("address")
        new_vars = item.get("renames", {})
        if not new_vars: continue

        addr = toAddr(addr_str)
        func = program.getFunctionManager().getFunctionAt(addr)
        if func is None: continue

        results = decomp.decompileFunction(func, 30, monitor)
        if not results.decompileCompleted(): continue
            
        high_func = results.getHighFunction()
        lsm = high_func.getLocalSymbolMap()
        
        for old_name, new_name in new_vars.items():
            if not new_name or new_name == old_name: continue

            found = False
            for sym in lsm.getSymbols():
                if sym.getName() == old_name:
                    try:
                        HighFunctionDBUtil.updateDBVariable(sym, new_name, None, SourceType.USER_DEFINED)
                        print("  [+] " + func.getName() + ": " + old_name + " -> " + new_name)
                        found = True
                        break
                    except Exception as e:
                        print("  [!] Error updating variable " + old_name + ": " + str(e))

if __name__ == "__main__":
    run()