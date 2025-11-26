"""
Refactory Pipeline: Full Auto Reverse Engineering
Orchestrates the multi-stage process from binary to clean source code.
"""
import os
import json
import concurrent.futures
import threading
from typing import List, Dict
from src.librarian import Librarian
from src.refactory_state import ModuleGroup
from src.refactory_agents import (
    type_recovery_agent, type_recovery_validator,
    refactoring_agent, refactoring_validator,
    source_code_generator
)
from src.maker_nodes import true_maker_rename
from src.inspector import inspect_module
from src.agent_lightning_bridge import AgentLightningClient
from src.compiler_judge import CompilerJudge

class RefactoryPipeline:
    """
    Main orchestrator for the full reverse engineering pipeline.
    
    Pipeline stages:
    1. Cartographer: Group functions into modules (Librarian)
    2. Type Smith: Recover types (Type Recovery Agent)
    3. Renamer: Rename variables (True MAKER)
    4. Architect: Refactor code (Refactoring Agent)
    5. Writer: Generate source files
    """
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = output_dir
        self.librarian = Librarian(min_module_size=2, max_module_size=12)
        self.file_lock = threading.Lock()
        self.lightning_client = AgentLightningClient(agent_name="Refactory_Orchestrator")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def run(self, ghidra_export_path: str, max_workers: int = 8):
        """Run the full pipeline."""
        print("=" * 60)
        print("REFACTORY PIPELINE v2.0: Full Auto Reverse Engineering")
        print(f"Parallel Processing Enabled: {max_workers} workers")
        print("=" * 60)
        
        # Stage 0: Load and group functions
        print("\n[Stage 0] The Librarian: Grouping functions into modules...")
        modules = self.librarian.group_functions(ghidra_export_path)
        
        if not modules:
            print("[ERROR] No modules generated. Check Ghidra export.")
            return
        
        # Process modules in parallel
        all_source_files = {}
        all_header_files = {}
        
        print(f"\n[+] Starting parallel processing of {len(modules)} modules...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_module = {
                executor.submit(self.process_module, module): module
                for module in modules
            }
            
            # Process results as they complete
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_module):
                module = future_to_module[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    if result:
                        all_source_files.update(result["source"])
                        all_header_files.update(result["headers"])
                    
                    print(f"[{completed_count}/{len(modules)}] Completed module: {module['module_name']}")
                    
                except Exception as exc:
                    print(f"[ERROR] Module {module['module_name']} generated an exception: {exc}")
        
        # Write all files
        self.write_output(all_source_files, all_header_files)

        # [Stage 5] The Judge
        print(f"\n[Stage 5] The Judge: Verifying correctness...")
        judge = CompilerJudge(
            project_dir=self.output_dir,
            lightning_client=self.lightning_client
        )
        final_score = judge.assess_build()
        print(f"Final Architecture Score: {final_score}")
        
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print(f"Generated {len(all_source_files)} source files")
        print(f"Output directory: {self.output_dir}")
        print("=" * 60)
    
    def process_module(self, module: ModuleGroup) -> Dict:
        """Process a single module through all stages."""
        
        # Stage 0.5: Inspector (Secrets Detection)
        module_code = "\n".join([f.get("code", "") for f in module["functions"]])
        findings = inspect_module(module_code)
        
        if findings:
            report_path = os.path.join(self.output_dir, "SECRETS_REPORT.md")
            with self.file_lock:
                with open(report_path, "a") as f:
                    f.write(f"## Module: {module['module_name']}\n")
                    for label, matches in findings.items():
                        f.write(f"- **{label}**: {', '.join(matches)}\n")
                    f.write("\n")
            print(f"[!] Secrets detected in {module['module_name']}. Logged to SECRETS_REPORT.md")

        # Initialize state
        state = {
            "module": module,
            "type_proposals": [],
            "confirmed_types": {},
            "rename_proposals": [],
            "confirmed_renames": {},
            "refactoring_proposals": [],
            "confirmed_refactorings": [],
            "final_source_files": {},
            "final_header_files": {},
            "current_stage": "type_recovery",
            "attempts": 0
        }
        
        # Stage 1: Type Recovery
        print(f"\n[Stage 1] Type Smith: Recovering types...")
        state = self._run_stage(state, type_recovery_agent, type_recovery_validator, "type_recovery")
        print(f"  Recovered {len(state['confirmed_types'])} types")
        
        # Stage 2: Variable Renaming (using True MAKER)
        print(f"\n[Stage 2] The Renamer: Renaming variables...")
        state = self._run_renaming_stage(state)
        print(f"  Renamed {len(state['confirmed_renames'])} variables")
        
        # Stage 3: Code Refactoring
        print(f"\n[Stage 3] The Architect: Refactoring code...")
        state = self._run_stage(state, refactoring_agent, refactoring_validator, "refactoring")
        print(f"  Refactored {len(state['confirmed_refactorings'])} functions")
        
        # Stage 4: Source Code Generation
        print(f"\n[Stage 4] The Writer: Generating source files...")
        state.update(source_code_generator(state))
        
        return {
            "source": state["final_source_files"],
            "headers": state["final_header_files"]
        }
    
    def _run_stage(self, state, agent_func, validator_func, stage_name):
        """Run a single pipeline stage with retry logic."""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            # Run agent
            updates = agent_func(state)
            state.update(updates)
            
            # Run validator
            validation = validator_func(state)
            state.update(validation)
            
            # Check if we got results
            if stage_name == "type_recovery" and state.get("confirmed_types"):
                break
            elif stage_name == "refactoring" and state.get("confirmed_refactorings"):
                break
        
        return state
    
    def _run_renaming_stage(self, state):
        """
        Run variable renaming using True MAKER.
        """
        module = state["module"]
        all_renames = {}
        
        for func in module["functions"]:
            # Create a mini-state for this function
            func_state = {
                "function_name": func["name"],
                "original_code": func["code"],
                "existing_variables": func["variables"],
                "proposals": [],
                "attempts": 0,
                "final_renames": None,
                "current_draft": None
            }
            
            # Run True MAKER
            result = true_maker_rename(func_state)
            
            if result.get("final_renames"):
                all_renames.update(result["final_renames"])
        
        state["confirmed_renames"] = all_renames
        return state
    
    def write_output(self, source_files: Dict[str, str], header_files: Dict[str, str]):
        """Write generated source and header files."""
        
        # Create subdirectories
        src_dir = os.path.join(self.output_dir, "src")
        # include_dir = os.path.join(self.output_dir, "include") # Not needed for C#
        
        os.makedirs(src_dir, exist_ok=True)
        # os.makedirs(include_dir, exist_ok=True)
        
        # Write source files
        for filename, content in source_files.items():
            filepath = os.path.join(src_dir, filename)
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"  [+] {filepath}")
        
        # Write header files (if any)
        if header_files:
            include_dir = os.path.join(self.output_dir, "include")
            os.makedirs(include_dir, exist_ok=True)
            for filename, content in header_files.items():
                filepath = os.path.join(include_dir, filename)
                with open(filepath, 'w') as f:
                    f.write(content)
                print(f"  [+] {filepath}")
        
        # Create a simple .csproj file
        csproj_content = self._generate_csproj()
        csproj_path = os.path.join(self.output_dir, "RefactoredApp.csproj")
        with open(csproj_path, 'w') as f:
            f.write(csproj_content)
        print(f"  [+] {csproj_path}")
    
    def _generate_csproj(self) -> str:
        """Generate a basic .csproj for the reversed project."""
        return """<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>

</Project>
"""

def main():
    """Entry point for the Refactory Pipeline."""
    import sys
    
    # Get Ghidra export path
    ghidra_export = os.environ.get(
        "GHIDRA_EXPORT_PATH",
        "/tmp/ghidra_bridge/dataset_dirty.json"
    )
    
    if not os.path.exists(ghidra_export):
        print(f"[ERROR] Ghidra export not found: {ghidra_export}")
        print("Please run export_function.py in Ghidra first.")
        sys.exit(1)
    
    # Run pipeline
    pipeline = RefactoryPipeline(output_dir="./refactored_output")
    pipeline.run(ghidra_export)

if __name__ == "__main__":
    main()