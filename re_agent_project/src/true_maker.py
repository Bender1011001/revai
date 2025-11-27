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
import os
from typing import Dict, Any, Optional, Tuple
from collections import defaultdict
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from src.agent_lightning_bridge import AgentLightningClient, LightningLLMWrapper


class MakerConfig:
    """
    Configuration for MAKER framework with dynamic k calculation.
    Based on Equation 14 from the paper.
    """
    
    def __init__(
        self,
        model: str = "qwen2.5-coder:3b",
        temperature: float = 0.3,
        target_reliability: float = 0.95,
        estimated_error_rate: float = 0.01,
        max_output_tokens: int = 1000,
        k_override: Optional[int] = None,
        total_steps: int = 1
    ):
        """
        Args:
            model: LLM model name
            temperature: Sampling temperature
            target_reliability: Target probability t for full task success (0 < t < 1)
            estimated_error_rate: Estimated per-step error rate (0 < p < 0.5)
            max_output_tokens: Maximum allowed output length (red flag threshold)
            k_override: If set, override calculated k value
            total_steps: Total number of steps (s) in the task
        """
        self.model = model
        self.temperature = temperature
        self.target_reliability = target_reliability
        self.total_steps = max(1, total_steps)
        
        # Clamp estimated_error_rate to ensure p (1 - error_rate) is in safe range [0.51, 0.99]
        # This prevents ZeroDivisionError (p=0.5) and log(0) (p=1.0) in k calculation
        if estimated_error_rate < 0.01:
            self.estimated_error_rate = 0.01
        elif estimated_error_rate > 0.49:
            self.estimated_error_rate = 0.49
        else:
            self.estimated_error_rate = estimated_error_rate

        self.max_output_tokens = max_output_tokens
        self.k_override = k_override
        
        # Calculate k based on Equation 14
        # k_min = ln(t^(-1/s) - 1) / ln((1-p)/p)
        if k_override is not None:
            self.k = k_override
        else:
            self.k = self._calculate_k_min()
    
    def _calculate_k_min(self) -> int:
        """
        Calculate minimum k for desired reliability.
        Based on Equation 14 from paper:
        k_min = ln(t^(-m/s) - 1) / ln((1-p)/p)
        Assuming m=1 (Maximal Decomposition)
        """
        p = 1 - self.estimated_error_rate  # Success rate
        t = self.target_reliability
        s = self.total_steps
        
        if p <= 0.5:
            # Model is too unreliable for voting to work
            raise ValueError(
                f"Model success rate ({p:.3f}) must be > 0.5 for voting to converge"
            )
        
        try:
            # Calculate term: t^(-1/s) - 1
            # Note: t < 1, so t^(-1/s) > 1, so term > 0
            term1 = math.pow(t, -1.0/s) - 1
            
            if term1 <= 0:
                # Should not happen for t < 1, but safety check
                return 3
                
            # Calculate term: (1-p)/p
            # Note: p > 0.5, so (1-p)/p < 1, so ln(term2) < 0
            term2 = (1 - p) / p
            
            numerator = math.log(term1)
            denominator = math.log(term2)
            
            # Both numerator and denominator are negative, result is positive
            k_min = math.ceil(numerator / denominator)
            
        except (ValueError, ZeroDivisionError, OverflowError):
            # Fallback to conservative estimate
            k_min = 3
        
        # Ensure k is at least 2 (need majority)
        return max(2, k_min)

    def calibrate(self, sample_data: list):
        """
        Calibrate the estimated error rate based on sample data.
        Updates self.estimated_error_rate and recalculates k.
        
        Args:
            sample_data: List of sample dictionaries
            
        Returns:
            (p, is_feasible) tuple
        """
        from src.calibration import measure_model_difficulty
        
        # Default system prompt for calibration if not provided
        system_prompt = """You are an expert Reverse Engineer.
Your goal is to rename variables in the provided decompiled code to make it more readable.
Output ONLY a JSON object mapping old variable names to new, descriptive names.
Do not include any explanation or markdown formatting."""
        
        p, is_feasible = measure_model_difficulty(
            self.model,
            sample_data,
            system_prompt,
            temperature=self.temperature
        )
        
        # Update estimated error rate (1 - p)
        # Clamp to safe range [0.01, 0.49]
        new_error_rate = 1.0 - p
        if new_error_rate < 0.01:
            new_error_rate = 0.01
        elif new_error_rate > 0.49:
            new_error_rate = 0.49
            
        self.estimated_error_rate = new_error_rate
        
        # Recalculate k if not overridden
        if self.k_override is None:
            self.k = self._calculate_k_min()
            
        return p, is_feasible


class RedFlagGuard:
    """
    Implements Algorithm 3: get_vote with red-flagging.
    Discards samples that show signs of unreliability.
    """
    
    def __init__(
        self,
        max_output_tokens: int = 1000
    ):
        """
        Args:
            max_output_tokens: Maximum allowed output length
        """
        self.max_output_tokens = max_output_tokens
    
    def check_red_flags(
        self,
        response: str,
        parsed_data: Optional[Dict] = None,
        required_keys: Optional[list] = None
    ) -> Tuple[bool, str]:
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
        if required_keys:
            missing_keys = [k for k in required_keys if k not in parsed_data]
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
        llm,  # Can be ChatOllama or LightningLLMWrapper
        config: MakerConfig,
        red_flag_guard: RedFlagGuard,
        lightning_client: Optional[AgentLightningClient] = None
    ):
        # Initialize Lightning Client
        self.lightning = lightning_client if lightning_client else AgentLightningClient()
        
        # Check if LLM is already wrapped, if not wrap it
        if isinstance(llm, LightningLLMWrapper):
            self.llm = llm
        else:
            self.llm = LightningLLMWrapper(llm, self.lightning)
        
        self.config = config
        self.guard = red_flag_guard
        self.max_samples = 100  # Safety limit
    
    def do_voting(
        self,
        prompt: str,
        system_prompt: str,
        existing_variables: list,
        required_keys: Optional[list] = None,
        callback: Optional[callable] = None
    ) -> Tuple[Optional[Dict[str, str]], int, int]:
        """
        Implements Algorithm 2: First-to-ahead-by-k voting.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            existing_variables: List of valid variable names (for hallucination check)
            required_keys: Optional list of keys that must be present in output
            callback: Optional callback for real-time updates
        
        Returns:
            (winner_renames, total_samples, valid_samples) tuple
        """
        vote_counts = defaultdict(int)  # Maps JSON string -> count
        sample_count = 0
        valid_count = 0
        
        while sample_count < self.max_samples:
            # Temperature Decay: Force deterministic output if stuck
            current_temp = None
            if sample_count > 20:
                current_temp = 0.0

            # Algorithm 3: get_vote with red-flagging
            vote, is_valid, reason = self._get_vote(
                prompt,
                system_prompt,
                existing_variables,
                required_keys=required_keys,
                temperature_override=current_temp
            )
            
            sample_count += 1
            
            if not is_valid:
                # Discard flagged sample, continue sampling
                continue
            
            valid_count += 1
            
            # Serialize vote for comparison
            vote_key = json.dumps(vote, sort_keys=True)
            vote_counts[vote_key] += 1
            
            # Notify dashboard if callback provided
            if callback:
                # callback signature varies, handle both formats
                try:
                    # Try new format (event, data)
                    callback("CONSENSUS_UPDATE", {
                        "categories": list(vote_counts.keys()),
                        "values": list(vote_counts.values())
                    })
                except TypeError:
                    # Fall back to old format (just data)
                    callback({
                        "categories": list(vote_counts.keys()),
                        "values": list(vote_counts.values())
                    })
            
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
        existing_variables: list,
        required_keys: Optional[list] = None,
        temperature_override: Optional[float] = None
    ) -> Tuple[Dict[str, str], bool, str]:
        """
        Implements Algorithm 3: get_vote with red-flagging.
        
        Returns:
            (vote_data, is_valid, reason) tuple
        """
        try:
            # Sample from LLM
            llm_to_use = self.llm
            if temperature_override is not None:
                # Recreate LLM with new temperature to avoid bind() issues with langchain_ollama
                # which might pass temperature as a top-level arg causing errors
                new_llm = ChatOllama(
                    model=self.config.model,
                    temperature=temperature_override,
                    format="json",
                    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434")
                )
                llm_to_use = LightningLLMWrapper(new_llm, self.lightning)

            response = llm_to_use.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            response_text = response.content
            
            # Clean markdown code blocks
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            cleaned_text = cleaned_text.strip()

            # Validation Pipeline
            parsed_data = {}
            is_valid = False
            reason = "unknown"
            
            # 1. Parse JSON
            try:
                parsed_data = json.loads(cleaned_text)
                is_valid = True
                reason = "valid"
            except json.JSONDecodeError:
                is_valid = False
                reason = "json_parse_error"
            
            # 2. Red Flag Check (if valid so far)
            if is_valid:
                is_valid, reason = self.guard.check_red_flags(response_text, parsed_data, required_keys)
            
            # 3. Hallucination Check (if valid so far)
            if is_valid and isinstance(parsed_data, dict):
                for var_name in parsed_data.keys():
                    if var_name not in existing_variables:
                        is_valid = False
                        reason = f"hallucinated_variable: {var_name}"
                        break
            
            # 4. Laziness Check (if valid so far)
            clean_renames = {}
            if is_valid:
                # Remove identity mappings (var -> var)
                clean_renames = {
                    k: v for k, v in parsed_data.items()
                    if k != v and isinstance(v, str)
                }
            
            # CALCULATE REWARD
            reward = 0.0
            
            if not is_valid:
                reward = -0.5  # Penalty for red flags (invalid JSON, too long, hallucinations)
                
                # Log Failure Trace
                self.lightning.log_transition(
                    state=prompt,
                    action=response_text,
                    reward=reward,
                    next_state="TERMINAL_FAILURE",
                    metadata={"reason": reason}
                )
                return {}, False, reason
            
            # If valid:
            reward = 0.1   # Small reward for valid syntax
            
            # Log Success Trace
            self.lightning.log_transition(
                state=prompt,
                action=response_text,
                reward=reward,
                next_state="VOTING_POOL",
                metadata={"parsed": parsed_data}
            )
            
            return clean_renames, True, "valid"
            
        except Exception as e:
            # Log the exception for debugging purposes
            print(f"[True MAKER] Error in _get_vote: {e}")
            return {}, False, f"exception: {str(e)}"


def create_maker_agent(
    target_reliability: float = 0.95,
    estimated_error_rate: float = 0.01,
    max_output_tokens: int = 1000,
    model: str = "qwen2.5-coder:3b",
    temperature: float = 0.3,
    total_steps: int = 1,
    client: Optional[AgentLightningClient] = None
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
        max_output_tokens=max_output_tokens,
        total_steps=total_steps
    )
    
    # Create LLM
    base_llm = ChatOllama(
        model=config.model,
        temperature=config.temperature,
        format="json",
        base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )

    # Wrap LLM with Lightning
    if client is None:
        client = AgentLightningClient()
        
    wrapped_llm = LightningLLMWrapper(base_llm, client)
    
    # Create red flag guard
    guard = RedFlagGuard(
        max_output_tokens=config.max_output_tokens
    )
    
    # Create voting agent
    voting_agent = SequentialVoting(wrapped_llm, config, guard, lightning_client=client)
    voting_agent.lightning_client = client  # Attach client for reward logging
    
    print(f"[MAKER] Initialized with k={config.k} (reliability={target_reliability}, error_rate={estimated_error_rate})")
    
    return voting_agent, config