import subprocess
import os

class CompilerJudge:
    """
    Evaluates the architectural quality of the refactored project
    by attempting to build it.
    """
    def __init__(self, project_dir: str):
        self.project_dir = project_dir

    def evaluate(self) -> float:
        """
        Run dotnet build and return a reward score.
        Success: +1.0
        Failure: -0.5
        """
        print("\n[The Judge] Assessing Architectural Integrity...")
        
        csproj_path = os.path.join(self.project_dir, "RefactoredApp.csproj")
        if not os.path.exists(csproj_path):
            print("[The Judge] Error: .csproj not found.")
            return -1.0

        try:
            # Attempt to build
            result = subprocess.run(
                ["dotnet", "build", csproj_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("[The Judge] Build SUCCESS! (+1.0 Reward)")
                return 1.0
            else:
                print("[The Judge] Build FAILED. (-0.5 Reward)")
                # Optional: Log specific errors for the agent to see next time
                # print(result.stdout) 
                return -0.5
                
        except FileNotFoundError:
            print("[The Judge] Error: 'dotnet' command not found. Is .NET SDK installed?")
            return 0.0