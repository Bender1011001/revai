import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Add src and project root to path
# We need 're_agent_project' to be importable, and 'src' to be importable if the code uses 'from src...'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
re_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))

sys.path.insert(0, project_root)
sys.path.insert(0, re_agent_root)
sys.path.insert(0, src_root)

# Mock dependencies BEFORE importing true_maker
# We need to mock the specific submodules that are imported
mock_langchain_core = MagicMock()
sys.modules["langchain_core"] = mock_langchain_core
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain_core.language_models"] = MagicMock()
sys.modules["langchain_ollama"] = MagicMock()

# Create a fake Message class for testing
class FakeMessage:
    def __init__(self, content):
        self.content = content

# Setup specific mocks for messages
mock_messages = sys.modules["langchain_core.messages"]
mock_messages.SystemMessage = FakeMessage
mock_messages.HumanMessage = FakeMessage

from maker_nodes import true_maker_rename
from true_maker import create_maker_agent

class TestMakerGroundTruth(unittest.TestCase):
    """
    Test MAKER against a known ground truth to verify accuracy.
    """

    def setUp(self):
        # Reset mocks
        sys.modules["langchain_ollama"].ChatOllama.reset_mock()

    @patch('true_maker.ChatOllama')
    @patch('true_maker.AgentLightningClient')
    def test_ground_truth_comparison(self, MockClient, MockChatOllama):
        """
        Simulate a full run on a function and compare against ground truth.
        """
        # 1. Define Ground Truth
        ground_truth_renames = {
            "iVar1": "width",
            "iVar2": "height",
            "iVar3": "area"
        }

        # 2. Define Input State (Decompiled Code)
        decompiled_code = """
        int calculate_rect(int iVar1, int iVar2) {
            int iVar3;
            iVar3 = iVar1 * iVar2;
            return iVar3;
        }
        """
        
        state = {
            "function_name": "calculate_rect",
            "original_code": decompiled_code,
            "existing_variables": ["iVar1", "iVar2", "iVar3"],
            "consensus_callback": MagicMock()
        }

        # 3. Mock LLM Behavior
        # We need the LLM to return the correct rename for each variable when prompted
        mock_llm_instance = MockChatOllama.return_value
        
        def side_effect(messages):
            # Extract the prompt to see which variable is being asked about
            prompt_content = messages[1].content
            
            if "Rename ONLY the variable 'iVar1'" in prompt_content:
                return FakeMessage('{"iVar1": "width"}')
            elif "Rename ONLY the variable 'iVar2'" in prompt_content:
                return FakeMessage('{"iVar2": "height"}')
            elif "Rename ONLY the variable 'iVar3'" in prompt_content:
                return FakeMessage('{"iVar3": "area"}')
            else:
                return FakeMessage('{}')

        mock_llm_instance.invoke.side_effect = side_effect

        # 4. Run MAKER
        # We use a low k to speed up the test, but the logic remains the same
        # Note: true_maker_rename creates its own agent internally if not provided.
        # We want to control the agent creation to inject our mock, but true_maker_rename
        # instantiates a NEW agent if one isn't passed.
        # Ideally, we should pass a pre-configured agent with our mock LLM.
        
        # Create a mock agent with our mocked LLM
        agent, config = create_maker_agent(
            target_reliability=0.95,
            estimated_error_rate=0.01,
            total_steps=3
        )
        # Manually override k for test speed/determinism if needed
        config.k = 2
        # Inject the mock LLM into the agent (since create_maker_agent creates a new one)
        # The agent wraps the LLM, so we need to access the wrapper's internal LLM or mock the wrapper
        # But since we mocked ChatOllama at the module level, create_maker_agent used that mock class.
        # So agent.llm._llm IS mock_llm_instance.
        
        result = true_maker_rename(state, agent=agent)

        # 5. Compare Results
        final_renames = result["final_renames"]
        
        print("\n--- Ground Truth Comparison ---")
        print(f"Expected: {ground_truth_renames}")
        print(f"Actual:   {final_renames}")
        
        self.assertIsNotNone(final_renames)
        self.assertEqual(final_renames, ground_truth_renames)
        
        # Calculate Accuracy
        correct = 0
        for var, name in ground_truth_renames.items():
            if final_renames.get(var) == name:
                correct += 1
        accuracy = correct / len(ground_truth_renames)
        print(f"Accuracy: {accuracy * 100:.2f}%")
        
        self.assertEqual(accuracy, 1.0, "MAKER failed to achieve 100% accuracy on ground truth test")

if __name__ == '__main__':
    unittest.main()