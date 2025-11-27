import os
import sys
import subprocess
import argparse
import shutil
import time  # Added for delays if needed
import threading
from typing import Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.target_identifier import generate_search_terms

def run_ghidra_export(ghidra_path: str, apk_path: str, project_dir: str, script_path: str, output_json: str, user_goal: str, limit: int = 100, stop_event: Optional[threading.Event] = None):
    print(f"\n[+] Starting Ghidra Headless Analysis...")
    
    # --- STEP 1: AI TARGET IDENTIFICATION ---
    keywords = generate_search_terms(user_goal)
    keyword_string = ",".join(keywords)
    
    # Ensure paths are absolute
    ghidra_path = os.path.abspath(ghidra_path)
    apk_path = os.path.abspath(apk_path)
    project_dir = os.path.abspath(project_dir)
    script_path = os.path.abspath(script_path)
    output_json = os.path.abspath(output_json)
    
    analyze_headless = os.path.join(ghidra_path, "support", "analyzeHeadless.bat")

    # Set environment variables for the Ghidra script
    os.environ["GHIDRA_EXPORT_DIR"] = os.path.dirname(output_json)
    os.environ["GHIDRA_EXPORT_LIMIT"] = str(limit)
    os.environ["GHIDRA_SEARCH_KEYWORDS"] = keyword_string # <--- SENT TO GHIDRA

    cmd = [
        analyze_headless,
        project_dir,
        "RefactoryProject",
        "-import", apk_path,
        "-postScript", script_path,
        "-deleteProject",
        "-overwrite"
    ]

    print(f"    Executing Ghidra with keywords: {keywords}")
    
    # --- STEP 2: STREAMING EXECUTION ---
    # We use Popen + poll() to print output in real-time
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        bufsize=1, 
        universal_newlines=True
    )

    # Read output line by line and print it (GUI will capture this)
    while True:
        if stop_event and stop_event.is_set():
            print("[-] Ghidra analysis stopped by user.")
            if os.name == 'nt':
                # Windows: Kill process tree
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                process.terminate()
            break

        # Use a non-blocking read approach or just standard readline which blocks until newline
        # Since bufsize=1 (line buffered), this should be fine for streaming unless Ghidra hangs without newline
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                break
            continue
            
        print(f"Ghidra: {line.strip()}")

    if stop_event and stop_event.is_set():
        return

    if process.returncode != 0:
        print(f"[ERROR] Ghidra analysis failed with code {process.returncode}")
        sys.exit(1)

    if not os.path.exists(output_json):
        print(f"[ERROR] Export file was not created: {output_json}")
        sys.exit(1)

def main_pipeline_wrapper(target_file: str, ghidra_path: str, user_goal: str, output_dir: str = "./refactored_output", limit: int = 100, export_only: bool = False, stop_event: Optional[threading.Event] = None, pause_event: Optional[threading.Event] = None):
    # Setup paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ghidra_scripts_dir = os.path.join(base_dir, "ghidra_scripts")
    export_script = os.path.join(ghidra_scripts_dir, "export_function.py")
    
    # Ensure output directory exists
    output_dir = os.path.abspath(output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define project-specific paths
    ghidra_project_dir = os.path.join(output_dir, "ghidra_project")
    ghidra_export_dir = os.path.join(output_dir, "ghidra_export")
    export_json = os.path.join(ghidra_export_dir, "dataset_dirty.json")
    refactored_output_dir = os.path.join(output_dir, "refactored_code")
    
    # Clean/Create directories
    # Note: We might NOT want to delete the project if we want to resume, but for now let's keep it clean or handle it in run_ghidra_export
    if not os.path.exists(ghidra_export_dir):
        os.makedirs(ghidra_export_dir)
    # If it exists, we don't delete it to avoid losing data if export fails.
    # run_ghidra_export will overwrite the specific json file.
    
    # We don't delete ghidra_project_dir here because run_ghidra_export handles the project creation/overwriting via flags
    
    # Ensure the project directory exists for Ghidra
    if not os.path.exists(ghidra_project_dir):
        os.makedirs(ghidra_project_dir)

    run_ghidra_export(
        ghidra_path=ghidra_path,
        apk_path=target_file,
        project_dir=ghidra_project_dir,
        script_path=export_script,
        output_json=export_json,
        user_goal=user_goal,
        limit=limit,
        stop_event=stop_event
    )
    
    if stop_event and stop_event.is_set():
        return

    if export_only:
        return

    print(f"\n[+] Starting Refactory Pipeline...")
    from src.refactory_pipeline import RefactoryPipeline
    # Pass the specific refactored output subfolder
    pipeline = RefactoryPipeline(output_dir=refactored_output_dir)
    pipeline.run(export_json, stop_event=stop_event, pause_event=pause_event)