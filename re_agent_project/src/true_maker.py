"""
True MAKER Framework Implementation
Based on arXiv:2511.09030v1 - "Solving a Million-Step LLM Task with Zero Errors"

Implements:
- Algorithm 2: do_voting (First-to-ahead-by-k voting)
- Algorithm 3: get_vote (Red-flagging)
- Equation 14: k_min calculation
"""
import json
import math
from typing import Dict, Any, Optional, Tuple
from collections import defaultdict
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage


class MakerConfig:
    """
    Configuration for MAKER framework with dynamic k calculation.
    Based on Equation 14 from the paper.
    """
    
    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        temperature: float = 0.3,
        target_reliability: float = 0.95,
        estimated_error_rate: float = 0.01,
        max_output_tokens: int = 1000,
        k_override: Optional[int] = None
    ):
        """
        Args:
            model: LLM model name
            temperature: Sampling temperature
            target_reliability: Target probability t for full task success (0 < t < 1)
            estimated_error_rate: Estimated per-step error rate (0 < p < 0.5)
            max_output_tokens: Maximum allowed output length (red flag threshold)
            k_override: If set, override calculated k value
        """
        self.model = model
        self.temperature = temperature
        self.target_reliability = target_reliability
        self.estimated_error_rate = estimated_error_rate
        self.max_output_tokens = max_output_tokens
        self.k_override = k_override
        
        # Calculate k based on Equation 14
        # k_min = ln(t^(-1/s) - 1) / ln((1-p)/p)
        # For simplicity, we use a conservative approximation
        # k ≈ ln(1/epsilon) / ln(p/(1-p))
        # where epsilon = 1 - target_reliability
        if k_override is not None:
            self.k = k_override
        else:
            self.k = self._calculate_k_min()
    
    def _calculate_k_min(self) -> int:
        """
        Calculate minimum k for desired reliability.
        Based on Equation 14 from paper (simplified).
        """
        p = 1 - self.estimated_error_rate  # Success rate
        epsilon = 1 - self.target_reliability
        
        if p <= 0.5:
            # Model is too unreliable for voting to work
            raise ValueError(
                f"Model success rate ({p:.3f}) must be > 0.5 for voting to converge"
            )
        
        # Simplified k calculation
        # k ≈ -ln(epsilon) / ln((1-p)/p)
        try:
            k_min = math.ceil(-math.log(epsilon) / math.log((1-p)/p))
        except (ValueError, ZeroDivisionError):
            # Fallback to conservative estimate
            k_min = 3
        
        # Ensure k is at least 2 (need majority)
        return max(2, k_min)


class RedFlagGuard:
    """
    Implements Algorithm 3: get_vote with red-flagging.
    Discards samples that show signs of unreliability.
    """
    
    def __init__(
        self,
        max_output_tokens: int = 1000,
        required_keys: Optional[list] = None
    ):
        """
        Args:
            max_output_tokens: Maximum allowed output length
            required_keys: Required keys in JSON output
        """
        self.max_output_tokens = max_output_tokens
        self.required_keys = required_keys or []
    
    def check_red_flags(self, response: str, parsed_data: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Check if response has red flags.
        
        Returns:
            (is_valid, reason) tuple
        """
        # Red Flag 1: Overly long response (indicates confusion)
        # Paper shows error rate spikes after ~750 tokens
        token_estimate = len(response.split())  # Rough estimate
        if token_estimate > self.max_output_tokens:
            return False, f"response_too_long ({token_estimate} tokens > {self.max_output_tokens})"
        
        # Red Flag 2: Invalid JSON format
        if parsed_data is None:
            return False, "invalid_json_format"
        
        # Red Flag 3: Missing required keys
        if self.required_keys:
            missing_keys = [k for k in self.required_keys if k not in parsed_data]
            if missing_keys:
                return False, f"missing_keys: {missing_keys}"
        
        # Red Flag 4: Empty response
        if not parsed_data:
            return False, "empty_response"
        
        return True, "valid"


class SequentialVoting:
    """
    Implements Algorithm 2: do_voting (First-to-ahead-by-k).
    
    Continues sampling until one candidate is ahead by k votes.
    """
    
    def __init__(
        self,
        llm: ChatOllama,
        config: MakerConfig,
        red_flag_guard: RedFlagGuard
    ):
        self.llm = llm
        self.config = config
        self.guard = red_flag_guard
        self.max_samples = 100  # Safety limit
    
    def do_voting(
        self,
        prompt: str,
        system_prompt: str,
        existing_variables: list
    ) -> Tuple[Optional[Dict[str, str]], int, int]:
        """
        Implements Algorithm 2: First-to-ahead-by-k voting.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            existing_variables: List of valid variable names (for hallucination check)
        
        Returns:
            (winner_renames, total_samples, valid_samples) tuple
        """
        vote_counts = defaultdict(int)  # Maps JSON string -> count
        sample_count = 0
        valid_count = 0
        
        while sample_count < self.max_samples:
            # Algorithm 3: get_vote with red-flagging
            vote, is_valid, reason = self._get_vote(
                prompt, system_prompt, existing_variables
            )
            
            sample_count += 1
            
            if not is_valid:
                # Discard flagged sample, continue sampling
                continue
            
            valid_count += 1
            
            # Serialize vote for comparison
            vote_key = json.dumps(vote, sort_keys=True)
            vote_counts[vote_key] += 1
            
            # Check if we have a winner (Algorithm 2 line 6)
            # if V[y] = k + max_{v≠y} V[v]
            max_count = max(vote_counts.values())
            second_max = 0
            
            for key, count in vote_counts.items():
                if count < max_count:
                    second_max = max(second_max, count)
            
            # Winner condition: max_count >= second_max + k
            if max_count >= second_max + self.config.k:
                # Found winner
                winner_key = max(vote_counts, key=vote_counts.get)
                winner = json.loads(winner_key)
                return winner, sample_count, valid_count
        
        # Max samples reached without consensus
        # Return most voted option (best effort)
        if vote_counts:
            winner_key = max(vote_counts, key=vote_counts.get)
            winner = json.loads(winner_key)
            return winner, sample_count, valid_count
        
        # No valid samples at all
        return None, sample_count, valid_count
    
    def _get_vote(
        self,
        prompt: str,
        system_prompt: str,
        existing_variables: list
    ) -> Tuple[Dict[str, str], bool, str]:
        """
        Implements Algorithm 3: get_vote with red-flagging.
        
        Returns:
            (vote_data, is_valid, reason) tuple
        """
        try:
            # Sample from LLM
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            response_text = response.content
            
            # Try to parse JSON
            try:
                parsed_data = json.loads(response_text)
            except json.JSONDecodeError:
                return {}, False, "json_parse_error"
            
            # Red Flag Check
            is_valid, reason = self.guard.check_red_flags(response_text, parsed_data)
            
            if not is_valid:
                return {}, False, reason
            
            # Hallucination Check (from existing MAKER)
            # Ensure we're not inventing variables
            if isinstance(parsed_data, dict):
                for var_name in parsed_data.keys():
                    if var_name not in existing_variables:
                        return {}, False, f"hallucinated_variable: {var_name}"
            
            # Laziness Check
            # Remove identity mappings (var -> var)
            clean_renames = {
                k: v for k, v in parsed_data.items()
                if k != v and isinstance(v, str)
            }
            
            return clean_renames, True, "valid"
            
        except Exception as e:
            return {}, False, f"exception: {str(e)}"


def create_maker_agent(
    target_reliability: float = 0.95,
    estimated_error_rate: float = 0.01,
    max_output_tokens: int = 1000,
    model: str = "qwen2.5-coder:7b",
    temperature: float = 0.3
) -> Tuple[SequentialVoting, MakerConfig]:
    """
    Factory function to create a True MAKER agent.
    
    Returns:
        (voting_agent, config) tuple
    """
    # Create config with dynamic k calculation
    config = MakerConfig(
        model=model,
        temperature=temperature,
        target_reliability=target_reliability,
        estimated_error_rate=estimated_error_rate,
        max_output_tokens=max_output_tokens
    )
    
    # Create LLM
    llm = ChatOllama(
        model=config.model,
        temperature=config.temperature,
        format="json",
        base_url="http://localhost:11434"
    )
    
    # Create red flag guard
    guard = RedFlagGuard(
        max_output_tokens=config.max_output_tokens,
        required_keys=[]  # Will be set per task
    )
    
    # Create voting agent
    voting_agent = SequentialVoting(llm, config, guard)
    
    print(f"[MAKER] Initialized with k={config.k} (reliability={target_reliability}, error_rate={estimated_error_rate})")
    
    return voting_agent, config