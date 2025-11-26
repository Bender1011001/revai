import unittest
import math
import sys
import os
from unittest.mock import MagicMock

# Mock missing dependencies
sys.modules["langchain_ollama"] = MagicMock()
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from true_maker import MakerConfig

class TestMakerConfig(unittest.TestCase):
    def test_clamping_error_rate(self):
        # Test lower bound clamping
        config_low = MakerConfig(estimated_error_rate=0.0001)
        self.assertEqual(config_low.estimated_error_rate, 0.01)
        
        # Test upper bound clamping
        config_high = MakerConfig(estimated_error_rate=0.6)
        self.assertEqual(config_high.estimated_error_rate, 0.49)
        
        # Test valid range
        config_valid = MakerConfig(estimated_error_rate=0.2)
        self.assertEqual(config_valid.estimated_error_rate, 0.2)

    def test_k_calculation_valid(self):
        # p = 0.99 (error_rate = 0.01)
        # epsilon = 0.05 (target_reliability = 0.95)
        # k ≈ -ln(0.05) / ln(0.99/0.01) ≈ 2.99 / 4.59 ≈ 0.65 -> ceil -> 1 -> max(2, 1) -> 2
        config = MakerConfig(target_reliability=0.95, estimated_error_rate=0.01)
        self.assertTrue(config.k >= 2)
        
        # p = 0.6 (error_rate = 0.4)
        # epsilon = 0.05
        # k ≈ -ln(0.05) / ln(0.6/0.4) ≈ 2.99 / 0.405 ≈ 7.38 -> ceil -> 8
        config_unreliable = MakerConfig(target_reliability=0.95, estimated_error_rate=0.4)
        self.assertTrue(config_unreliable.k >= 7)

    def test_edge_cases(self):
        # Test exactly 0.5 (should be clamped to 0.49)
        config_mid = MakerConfig(estimated_error_rate=0.5)
        self.assertEqual(config_mid.estimated_error_rate, 0.49)
        # p = 0.51
        # k should be large because p is close to 0.5
        self.assertTrue(config_mid.k > 10)

        # Test 0.0 (should be clamped to 0.01)
        config_zero = MakerConfig(estimated_error_rate=0.0)
        self.assertEqual(config_zero.estimated_error_rate, 0.01)

if __name__ == '__main__':
    unittest.main()