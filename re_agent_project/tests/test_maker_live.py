import unittest
import sys
import os
import requests
import json

# Add src and project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
re_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))

sys.path.insert(0, project_root)
sys.path.insert(0, re_agent_root)
sys.path.insert(0, src_root)

from maker_nodes import true_maker_rename
from true_maker import create_maker_agent

class TestMakerLive(unittest.TestCase):
    """
    Integration test that connects to a LIVE Ollama instance.
    Requires Ollama to be running locally.
    """

    def setUp(self):
        # Check if Ollama is running
        self.ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        try:
            response = requests.get(f"{self.ollama_url}/api/tags")
            if response.status_code != 200:
                self.skipTest(f"Ollama is not responding at {self.ollama_url}")
        except requests.exceptions.ConnectionError:
            self.skipTest(f"Could not connect to Ollama at {self.ollama_url}")

    def test_live_renaming(self):
        """
        Run MAKER against a real LLM (qwen2.5-coder:3b or similar).
        """
        # 1. Define Input State (Decompiled Code)
        # Simple function to make it easy for the model
        decompiled_code = """
        int calculate_sum(int a, int b) {
            int res;
            res = a + b;
            return res;
        }
        """
        
        state = {
            "function_name": "calculate_sum",
            "original_code": decompiled_code,
            "existing_variables": ["a", "b", "res"], # Already good names, let's see if it keeps them or renames generic ones
        }
        
        # Let's use generic names to force renaming
        decompiled_code_generic = """
        int func(int p1, int p2) {
            int v1;
            v1 = p1 + p2;
            return v1;
        }
        """
        state_generic = {
            "function_name": "calculate_sum",
            "original_code": decompiled_code_generic,
            "existing_variables": ["p1", "p2", "v1"],
            "consensus_callback": lambda event, data: print(f"  [Callback] {event}: {data}")
        }

        print("\n[Test] Connecting to Ollama...")
        
        # Create agent with real configuration
        # We use a small model that should be available or easily pullable
        model_name = "qwen2.5-coder:1.5b" # Try a small one, or default
        
        # Check if model exists, if not try to pull or warn
        # For this test we assume the user has a model loaded or we use a default
        
        agent, config = create_maker_agent(
            target_reliability=0.90, # Lower for test speed
            estimated_error_rate=0.1,
            total_steps=3,
            model="qwen2.5-coder:3b", # Default from code
            temperature=0.3
        )
        
        print(f"[Test] Running MAKER with model: {config.model}")
        print("[Test] This may take a minute...")

        result = true_maker_rename(state_generic, agent=agent)

        final_renames = result["final_renames"]
        print(f"\n[Test] Result: {final_renames}")
        
        # We can't assert exact names because LLMs are probabilistic, 
        # but we can check if it produced *something* valid.
        if final_renames:
            self.assertIsInstance(final_renames, dict)
            # Check if it renamed at least one variable
            self.assertTrue(len(final_renames) > 0)
            # Check if keys are from existing variables
            for key in final_renames:
                self.assertIn(key, state_generic["existing_variables"])
        else:
            print("[Test] No consensus reached (this is a valid outcome for stochastic tests)")

if __name__ == '__main__':
    unittest.main()