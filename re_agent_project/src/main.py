"""
Refactory Pipeline Entry Point
Orchestrates the entire reverse engineering process:
1. Ghidra Headless Analysis & Export
2. Refactory Pipeline Execution
"""
import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from src.refactory_pipeline import RefactoryPipeline

def run_ghidra_export(ghidra_path: str, apk_path: str, project_dir: str, script_path: str, output_json: str, limit: int = 100):
    """
    Runs Ghidra in headless mode to analyze the APK and export function data.
    """
    print(f"\n[+] Starting Ghidra Headless Analysis...")
    print(f"    Ghidra Path: {ghidra_path}")
    print(f"    APK Path: {apk_path}")
    print(f"    Export Limit: {limit}")
    
    # Ensure paths are absolute
    ghidra_path = os.path.abspath(ghidra_path)
    apk_path = os.path.abspath(apk_path)
    project_dir = os.path.abspath(project_dir)
    script_path = os.path.abspath(script_path)
    output_json = os.path.abspath(output_json)
    
    # Ghidra headless executable
    analyze_headless = os.path.join(ghidra_path, "support", "analyzeHeadless.bat")
    if not os.path.exists(analyze_headless):
        raise FileNotFoundError(f"Ghidra headless executable not found at: {analyze_headless}")

    # Create project directory if it doesn't exist
    if not os.path.exists(project_dir):
        os.makedirs(project_dir)

    # Set environment variable for the export script
    os.environ["GHIDRA_EXPORT_DIR"] = os.path.dirname(output_json)
    os.environ["GHIDRA_EXPORT_LIMIT"] = str(limit)

    # Construct command
    # analyzeHeadless <project_location> <project_name> -import <file_to_import> -postScript <script_name>
    cmd = [
        analyze_headless,
        project_dir,
        "RefactoryProject",
        "-import", apk_path,
        "-postScript", script_path,
        "-deleteProject", # Clean up after analysis
        "-overwrite" # Overwrite if exists
    ]

    print(f"    Executing: {' '.join(cmd)}")
    
    try:
        # Run Ghidra
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("    Ghidra analysis complete.")
        # print(result.stdout) # Uncomment for debug
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Ghidra analysis failed with code {e.returncode}")
        print(e.stdout)
        print(e.stderr)
        sys.exit(1)

    if not os.path.exists(output_json):
        print(f"[ERROR] Export file was not created: {output_json}")
        sys.exit(1)
        
    print(f"    Export successful: {output_json}")

def main_pipeline_wrapper(target_file: str, ghidra_path: str, output_dir: str = "./refactored_output", limit: int = 100, export_only: bool = False):
    """
    Wrapper for the main pipeline logic to be called by GUI or other scripts.
    """
    # Validate Ghidra path
    if not ghidra_path or not os.path.exists(ghidra_path):
        raise ValueError(f"Invalid Ghidra path provided: {ghidra_path}")

    # Setup paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ghidra_scripts_dir = os.path.join(base_dir, "ghidra_scripts")
    export_script = os.path.join(ghidra_scripts_dir, "export_function.py")
    
    # Temp directories
    temp_dir = os.path.join(base_dir, "temp_ghidra")
    ghidra_project_dir = os.path.join(temp_dir, "project")
    ghidra_export_dir = os.path.join(temp_dir, "export")
    export_json = os.path.join(ghidra_export_dir, "dataset_dirty.json")
    
    # Clean temp dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(ghidra_export_dir)
    
    # 1. Run Ghidra Export
    run_ghidra_export(
        ghidra_path=ghidra_path,
        apk_path=target_file,
        project_dir=ghidra_project_dir,
        script_path=export_script,
        output_json=export_json,
        limit=limit
    )
    
    if export_only:
        print(f"\n[+] Export only mode enabled. Skipping Refactory Pipeline.")
        print(f"    Exported data available at: {export_json}")
        return

    # 2. Run Refactory Pipeline
    print(f"\n[+] Starting Refactory Pipeline...")
    from src.refactory_pipeline import RefactoryPipeline
    pipeline = RefactoryPipeline(output_dir=output_dir)
    pipeline.run(export_json)

def main():
    parser = argparse.ArgumentParser(description="Refactory Pipeline Orchestrator")
    parser.add_argument("--ghidra_path", required=True, help="Path to Ghidra installation directory")
    parser.add_argument("--file", help="Path to the target file (APK)")
    parser.add_argument("--output_dir", default="./refactored_output", help="Directory for generated source code")
    parser.add_argument("--export_only", action="store_true", help="Only run Ghidra export, skip refactoring pipeline")
    parser.add_argument("--limit", type=int, default=100, help="Limit number of functions to export")
    
    args = parser.parse_args()
    
    main_pipeline_wrapper(
        target_file=args.file,
        ghidra_path=args.ghidra_path,
        output_dir=args.output_dir,
        limit=args.limit,
        export_only=args.export_only
    )

if __name__ == "__main__":
    main()