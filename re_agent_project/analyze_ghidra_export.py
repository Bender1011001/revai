import json
import re
import os
from collections import defaultdict

def analyze_export(file_path):
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

    classes = defaultdict(list)
    communication_candidates = []
    data_structures = set()
    
    # Regex to extract class name from Ghidra comments
    # Example: /* Class: Lcom/quadzillapower/iQuad/AVFormatter/AVBooleanFormatter;
    class_regex = re.compile(r"Class:\s+L([^;]+);")
    
    # Keywords for communication
    comm_keywords = ["send", "recv", "write", "read", "bluetooth", "usb", "serial", "socket", "connect", "disconnect", "packet", "protocol", "command", "jni", "native"]
    
    for func in data:
        code = func.get('code', '')
        name = func.get('name', '')
        
        # Extract class name
        match = class_regex.search(code)
        if match:
            class_name = match.group(1).replace('/', '.')
            classes[class_name].append(func)
            
            # Identify potential data structures (simple data holders)
            if "Data" in class_name or "Info" in class_name or "Config" in class_name:
                data_structures.add(class_name)
        else:
            # Fallback if no class comment, maybe try to infer from function name if it looks like C++ mangled or namespaced
            # e.g. com::quadzillapower::iQuad::AVFormatter::AVBooleanFormatter::dataFromAV
            if "::" in code.split('\n')[0]: # Check first line or so
                 pass # Logic to parse C++ style names if needed, but the comment is more reliable for Java
            classes["Unknown"].append(func)

        # Check for communication logic
        code_lower = code.lower()
        if any(kw in code_lower for kw in comm_keywords) or any(kw in name.lower() for kw in comm_keywords):
            # Filter out common false positives if necessary
            communication_candidates.append({
                "name": name,
                "class": match.group(1).replace('/', '.') if match else "Unknown",
                "snippet": code[:200].replace('\n', ' ') + "..." # First 200 chars
            })

    # Generate Report
    report_lines = []
    report_lines.append("# Ghidra Export Analysis Report")
    report_lines.append(f"\nTotal Functions Analyzed: {len(data)}")
    
    report_lines.append("\n## 1. Key Data Structures")
    report_lines.append("Identified based on naming conventions (Data, Info, Config):")
    for ds in sorted(data_structures):
        report_lines.append(f"- `{ds}`")

    report_lines.append("\n## 2. Potential Communication Logic")
    report_lines.append(f"Found {len(communication_candidates)} functions with communication keywords.")
    
    # Group comm candidates by class
    comm_by_class = defaultdict(list)
    for c in communication_candidates:
        comm_by_class[c['class']].append(c['name'])
        
    for cls, methods in comm_by_class.items():
        if len(methods) > 0:
            report_lines.append(f"\n### {cls}")
            for m in list(set(methods))[:10]: # Limit to 10 methods per class to save space
                report_lines.append(f"- {m}")
            if len(set(methods)) > 10:
                report_lines.append(f"- ... and {len(set(methods)) - 10} more")

    report_lines.append("\n## 3. Class Summary")
    report_lines.append("Top 20 classes by function count:")
    sorted_classes = sorted(classes.items(), key=lambda item: len(item[1]), reverse=True)
    for cls, funcs in sorted_classes[:20]:
        report_lines.append(f"- **{cls}**: {len(funcs)} functions")

    # Write report
    output_path = "re_agent_project/ghidra_analysis_summary.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"Analysis complete. Report written to {output_path}")

if __name__ == "__main__":
    analyze_export("re_agent_project/temp_ghidra/export/dataset_dirty.json")