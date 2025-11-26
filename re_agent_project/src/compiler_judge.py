# src/compiler_judge.py
import subprocess
import os
from .agent_lightning_bridge import AgentLightningClient

class CompilerJudge:
    def __init__(self, project_dir: str, lightning_client: AgentLightningClient):
        self.project_dir = project_dir
        self.client = lightning_client

    def assess_build(self) -> float:
        """Runs 'dotnet build' and calculates the reward."""
        print("\n[The Judge] Running compilation check...")
        
        try:
            # Run compilation
            result = subprocess.run(
                ["dotnet", "build"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            stdout = result.stdout
            
            if result.returncode == 0:
                print("  [✓] BUILD SUCCESS. Reward: +1.0")
                self._log(1.0, "build_success", stdout)
                return 1.0
            else:
                # Syntax Error Penalty
                print(f"  [!] BUILD FAILED. Reward: -0.5")
                self._log(-0.5, "syntax_errors", stdout)
                return -0.5

        except Exception as e:
            print(f"  [!] Build System Error: {e}")
            return 0.0

    def _log(self, reward, label, logs):
        self.client.log_trace(
            state="COMPILATION_PHASE",
            action="dotnet build",
            reward=reward,
            next_state="TERMINAL",
            metadata={"outcome": label, "logs": logs[:500]}
        )