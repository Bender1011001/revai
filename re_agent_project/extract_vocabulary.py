import json
import re
import os

def extract_vocabulary(file_path):
    print(f"Loading {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {file_path}")
        return

    print(f"Loaded {len(data)} functions.")

    command_map = {}
    sensor_map = {}

    # Regex for Command IDs (e.g., sendCmd(123, ...))
    # Looking for calls to sendCmd with an integer first argument
    # This is tricky in Ghidra export JSON as it contains decompiled C code or assembly
    # We'll look for patterns like "sendCmd(0x..." or "sendCmd(1..."
    cmd_regex = re.compile(r"sendCmd\s*\(\s*(0x[0-9a-fA-F]+|\d+)")
    
    # Regex for Sensor Multipliers/Offsets
    # Looking for assignments or calculations involving floats near sensor names
    # This is heuristic. We'll look for "Boost" or "EGT" and nearby float constants.
    sensor_keywords = ["Boost", "EGT", "RPM", "Coolant", "Throttle", "Load", "Voltage", "Fuel"]
    float_regex = re.compile(r"(\d+\.\d+)")

    for func in data:
        code = func.get('code', '')
        name = func.get('name', '')
        
        # Search for Command IDs
        for match in cmd_regex.finditer(code):
            cmd_id = match.group(1)
            # Try to find context for what this command does
            # e.g., look for string literals nearby
            context_match = re.search(r'"([^"]+)"', code)
            context = context_match.group(1) if context_match else "Unknown"
            
            if cmd_id not in command_map:
                command_map[cmd_id] = set()
            command_map[cmd_id].add(f"{name} ({context})")

        # Search for Sensor Multipliers
        for sensor in sensor_keywords:
            if sensor in code:
                # Look for floats in the same function
                floats = float_regex.findall(code)
                if floats:
                    if sensor not in sensor_map:
                        sensor_map[sensor] = set()
                    for f in floats:
                        sensor_map[sensor].add(f)

    print("\n--- Command Map Candidates ---")
    for cmd, contexts in command_map.items():
        print(f"Command ID: {cmd}")
        for ctx in contexts:
            print(f"  - Context: {ctx}")

    print("\n--- Sensor Map Candidates ---")
    for sensor, values in sensor_map.items():
        print(f"Sensor: {sensor}")
        print(f"  - Potential Multipliers/Offsets: {', '.join(values)}")

if __name__ == "__main__":
    extract_vocabulary("re_agent_project/temp_ghidra/export/dataset_dirty.json")