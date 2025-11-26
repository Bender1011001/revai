import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Add src and project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock dependencies BEFORE importing true_maker
sys.modules["langchain_ollama"] = MagicMock()
sys.modules["langchain_core"] = MagicMock()

# Create a fake Message class for testing
class FakeMessage:
    def __init__(self, content):
        self.content = content

mock_messages = MagicMock()
mock_messages.SystemMessage = FakeMessage
mock_messages.HumanMessage = FakeMessage
sys.modules["langchain_core.messages"] = mock_messages

from true_maker import create_maker_agent, SequentialVoting, RedFlagGuard
# Import from the same path as true_maker.py to ensure class identity matches
from re_agent_project.src.agent_lightning_bridge import LightningLLMWrapper, AgentLightningClient

class TestTrueMakerIntegration(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        sys.modules["langchain_ollama"].ChatOllama.reset_mock()
        
    @patch('true_maker.ChatOllama')
    @patch('true_maker.AgentLightningClient')
    def test_create_maker_agent_wraps_llm(self, MockClient, MockChatOllama):
        # Setup
        mock_llm_instance = MockChatOllama.return_value
        mock_client_instance = MockClient.return_value
        
        # Execute
        voting_agent, config = create_maker_agent()
        
        # Verify
        self.assertIsInstance(voting_agent.llm, LightningLLMWrapper)
        self.assertEqual(voting_agent.llm._llm, mock_llm_instance)
        self.assertEqual(voting_agent.llm.client, mock_client_instance)
        self.assertEqual(voting_agent.lightning_client, mock_client_instance)

    @patch('true_maker.ChatOllama')
    @patch('true_maker.AgentLightningClient')
    def test_get_vote_logs_positive_reward(self, MockClient, MockChatOllama):
        # Setup
        mock_llm_instance = MockChatOllama.return_value
        mock_client_instance = MockClient.return_value
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = '{"var1": "new_var1"}'
        mock_llm_instance.invoke.return_value = mock_response
        
        # Create agent
        voting_agent, _ = create_maker_agent()
        
        # Execute _get_vote
        vote, is_valid, reason = voting_agent._get_vote(
            prompt="test prompt",
            system_prompt="test system",
            existing_variables=["var1"]
        )
        
        # Verify
        self.assertTrue(is_valid)
        mock_client_instance.log_trace.assert_called_once()
        call_args = mock_client_instance.log_trace.call_args[1]
        self.assertEqual(call_args['reward'], 0.1)
        self.assertEqual(call_args['action'], '{"var1": "new_var1"}')
        # State should be captured by wrapper. Since we mocked invoke, we need to check if wrapper captured it.
        # The wrapper's invoke is called, which calls mock_llm_instance.invoke.
        # The wrapper sets latest_prompt.
        # However, since we are calling _get_vote -> self.llm.invoke (which is the wrapper), 
        # the wrapper logic should run.
        
    @patch('true_maker.ChatOllama')
    @patch('true_maker.AgentLightningClient')
    def test_get_vote_logs_negative_reward_invalid_json(self, MockClient, MockChatOllama):
        # Setup
        mock_llm_instance = MockChatOllama.return_value
        mock_client_instance = MockClient.return_value
        
        # Mock LLM response (Invalid JSON)
        mock_response = MagicMock()
        mock_response.content = 'Not JSON'
        mock_llm_instance.invoke.return_value = mock_response
        
        # Create agent
        voting_agent, _ = create_maker_agent()
        
        # Execute _get_vote
        vote, is_valid, reason = voting_agent._get_vote(
            prompt="test prompt",
            system_prompt="test system",
            existing_variables=["var1"]
        )
        
        # Verify
        self.assertFalse(is_valid)
        mock_client_instance.log_trace.assert_called_once()
        call_args = mock_client_instance.log_trace.call_args[1]
        self.assertEqual(call_args['reward'], -0.5)
        self.assertEqual(call_args['metadata']['failure'], 'json_parse_error')

    @patch('true_maker.ChatOllama')
    @patch('true_maker.AgentLightningClient')
    def test_get_vote_logs_negative_reward_hallucination(self, MockClient, MockChatOllama):
        # Setup
        mock_llm_instance = MockChatOllama.return_value
        mock_client_instance = MockClient.return_value
        
        # Mock LLM response (Hallucinated variable)
        mock_response = MagicMock()
        mock_response.content = '{"hallucinated_var": "new_name"}'
        mock_llm_instance.invoke.return_value = mock_response
        
        # Create agent
        voting_agent, _ = create_maker_agent()
        
        # Execute _get_vote
        vote, is_valid, reason = voting_agent._get_vote(
            prompt="test prompt",
            system_prompt="test system",
            existing_variables=["real_var"]
        )
        
        # Verify
        self.assertFalse(is_valid)
        mock_client_instance.log_trace.assert_called_once()
        call_args = mock_client_instance.log_trace.call_args[1]
        self.assertEqual(call_args['reward'], -0.5)
        self.assertIn('hallucinated_variable', call_args['metadata']['failure'])

if __name__ == '__main__':
    unittest.main()