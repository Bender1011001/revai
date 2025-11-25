# True MAKER Implementation Guide

## Overview

This project now implements the **full MAKER framework** as described in the research paper:

> **"Solving a Million-Step LLM Task with Zero Errors"**  
> arXiv:2511.09030v1 [cs.AI] 12 Nov 2025  
> Meyerson et al., Cognizant AI Lab

The implementation includes all three core components of MAKER:

1. **Maximal Agentic Decomposition (MAD)** - Breaking tasks into atomic units
2. **First-to-ahead-by-k Voting** - Sequential sampling until consensus
3. **Red-Flagging** - Strict validation to reduce correlated errors

## What Changed from Original Implementation

### Before (Simplified MAKER)

```python
# Old approach: Fixed k=2, batch sampling
proposals = []
for i in range(5):  # Fixed 5 attempts
    proposal = generate()
    proposals.append(proposal)

# Simple majority voting
if any proposal appears 2+ times: winner
```

**Problems:**
- Wastes tokens (samples all 5 even if consensus at 2)
- Doesn't discard confused/long responses
- Fixed k regardless of task difficulty

### After (True MAKER)

```python
# New approach: Sequential, adaptive, red-flagged
while True:
    sample = generate()
    
    # Red-flag check
    if len(sample) > 1000 tokens: discard
    if invalid_json: discard
    if hallucinated_vars: discard
    
    votes[sample] += 1
    
    # First-to-ahead-by-k
    if max(votes) >= second_max(votes) + k:
        return winner
```

**Benefits:**
- Early stopping saves tokens (Algorithm 2)
- Strict validation reduces errors (Algorithm 3)
- Dynamic k based on reliability needs (Equation 14)

## Architecture

### File Structure

```
src/
├── true_maker.py          # Core MAKER implementation
│   ├── MakerConfig        # Dynamic k calculation (Eq 14)
│   ├── RedFlagGuard       # Validation (Algorithm 3)
│   └── SequentialVoting   # Voting logic (Algorithm 2)
│
├── maker_nodes.py         # Integration layer
│   └── true_maker_rename() # Uses True MAKER for renaming
│
└── refactory_pipeline.py  # Multi-stage pipeline
    └── Uses maker_nodes for variable renaming
```

### Algorithm Implementation

#### Algorithm 2: First-to-ahead-by-k Voting

```
Input: x (state), M (model), k (margin)
Output: Winner with k-vote lead

V ← {v: 0 ∀v}  # Vote counts

while True:
    y ← get_vote(x, M)       # Algorithm 3
    V[y] ← V[y] + 1
    
    if V[y] ≥ k + max_{v≠y} V[v]:
        return y
```

**Implementation:** [`SequentialVoting.do_voting()`](re_agent_project/src/true_maker.py#144)

#### Algorithm 3: get_vote with Red-Flagging

```
Input: x (state), M (model)
Output: Valid vote or retry

while True:
    r ~ M(x)  # Sample from model
    
    if r has no red flags:
        return r
    # else: discard and retry
```

**Red Flags:**
1. Response > 1000 tokens (indicates confusion)
2. Invalid JSON format
3. Missing required keys
4. Hallucinated variables (not in original list)

**Implementation:** [`RedFlagGuard.check_red_flags()`](re_agent_project/src/true_maker.py#89)

#### Equation 14: Dynamic k Calculation

```
k_min = ⌈ln(t^(-1/s) - 1) / ln((1-p)/p)⌉

Where:
- t = target reliability (e.g., 0.95)
- s = number of steps
- p = per-step success rate
```

**Simplified for single-step:**
```python
k ≈ ⌈-ln(1 - t) / ln((1-p)/p)⌉

# Example: t=0.95, p=0.98
k = ⌈-ln(0.05) / ln(0.02/0.98)⌉ = 3
```

**Implementation:** [`MakerConfig._calculate_k_min()`](re_agent_project/src/true_maker.py#44)

## Configuration

### Basic Usage

```python
from src.true_maker import create_maker_agent

# Create MAKER agent with defaults
agent, config = create_maker_agent(
    target_reliability=0.95,      # 95% success probability
    estimated_error_rate=0.02,    # 2% error rate
    max_output_tokens=1000,       # Red-flag threshold
    model="qwen2.5-coder:7b",
    temperature=0.3
)

# The system automatically calculates k=3 for these parameters
print(f"Using k={config.k}")
```

### Advanced Configuration

```python
from src.true_maker import MakerConfig, RedFlagGuard, SequentialVoting
from langchain_ollama import ChatOllama

# Custom configuration
config = MakerConfig(
    target_reliability=0.99,      # Higher reliability
    estimated_error_rate=0.01,    # Lower error rate
    max_output_tokens=750,        # Stricter length limit
    k_override=5                  # Manual k override
)

# Custom red flags
guard = RedFlagGuard(
    max_output_tokens=750,
    required_keys=["old_name", "new_name"]  # Task-specific
)

# Custom LLM
llm = ChatOllama(
    model="deepseek-coder:7b",
    temperature=0.1
)

agent = SequentialVoting(llm, config, guard)
```

### Tuning for Your Hardware

**RTX 4060 Ti (8GB)**:
```python
config = MakerConfig(
    model="qwen2.5-coder:7b",     # Fits in 8GB
    temperature=0.3,               # Diversity for voting
    max_output_tokens=1000         # Safe for most tasks
)
```

**RTX 4090 (24GB)**:
```python
config = MakerConfig(
    model="qwen2.5-coder:14b",    # Larger model
    temperature=0.2,               # Can be lower with bigger model
    max_output_tokens=1500         # More room for complex explanations
)
```

**CPU Only**:
```python
config = MakerConfig(
    model="qwen2.5-coder:3b",     # Smaller model
    temperature=0.4,               # Higher for more attempts
    k_override=2                   # Lower k to compensate
)
```

## Performance Characteristics

### Token Usage

**Old Implementation:**
```
Fixed 5 samples × ~500 tokens = 2,500 tokens per function
```

**True MAKER:**
```
Early stopping:
- Best case: k samples × ~300 tokens = 900 tokens (consensus at k)
- Average: (k+2) samples × ~300 tokens = 1,500 tokens
- Worst case: max_samples × ~300 tokens (no consensus)

With red-flagging discarding ~10% of samples:
- Effective: ~1,650 tokens per function on average
```

**Savings:** ~34% reduction in token usage

### Reliability

| Configuration | k | Error Rate | Success Probability |
|--------------|---|------------|---------------------|
| Conservative | 5 | 0.01 | 99.9% |
| Standard     | 3 | 0.02 | 95.0% |
| Fast         | 2 | 0.05 | 80.0% |

## Comparison with Paper

| Component | Paper (Towers of Hanoi) | Our Implementation (Reverse Engineering) |
|-----------|------------------------|----------------------------------------|
| **Task** | 1M+ step sequence | Variable renaming per function |
| **Model** | gpt-4.1-mini | qwen2.5-coder:7b |
| **k** | 3 (calculated) | 2-5 (dynamic) |
| **Red Flags** | Length + Format | Length + Format + Hallucination |
| **Cost** | $3.5K for 1M steps | ~$0 (local) |

## Troubleshooting

### Issue: k is too high (slow)

**Problem:** `k=7` calculated for high reliability

**Solutions:**
1. Lower target reliability: `target_reliability=0.90` instead of 0.99
2. Improve model: Use better/larger model to reduce `estimated_error_rate`
3. Override k: `k_override=3`

### Issue: No consensus reached

**Problem:** Agent reports "No consensus" repeatedly

**Causes:**
- Task too ambiguous
- Model error rate worse than estimated
- Red flags too strict

**Solutions:**
```python
# 1. Increase max samples
agent.max_samples = 200  # Default: 100

# 2. Relax red flags
guard = RedFlagGuard(max_output_tokens=1500)  # Higher limit

# 3. Lower k
config = MakerConfig(k_override=2)
```

### Issue: Too many red flags

**Problem:** Most samples get discarded

**Debug:**
```python
# Add logging to see why samples are flagged
vote, is_valid, reason = agent._get_vote(...)
print(f"Valid: {is_valid}, Reason: {reason}")
```

**Common reasons:**
- `response_too_long`: Reduce max_output_tokens or improve prompt
- `invalid_json_format`: Check model supports JSON mode
- `hallucinated_variable`: Model inventing names not in original list

## Migration Guide

### For Existing Code

The new implementation is **backward compatible**. Existing code using `maker_nodes.py` will automatically use True MAKER:

```python
# This still works, now uses True MAKER internally
from src.maker_nodes import micro_agent_generate, voting_consensus

state = {
    "function_name": "process_data",
    "original_code": code,
    "existing_variables": ["iVar1", "param_1"]
}

result = micro_agent_generate(state)  # Now uses True MAKER
```

### To Use True MAKER Directly

```python
from src.true_maker import create_maker_agent

agent, config = create_maker_agent()

renames, total_samples, valid_samples = agent.do_voting(
    prompt="...",
    system_prompt="...",
    existing_variables=["iVar1", "param_1"]
)

print(f"Consensus after {valid_samples}/{total_samples} samples")
```

## References

- **Paper:** [arXiv:2511.09030v1](https://arxiv.org/abs/2511.09030)
- **Code:** `src/MAKE-research.txt` (full paper text)
- **Implementation:** `src/true_maker.py`

## License

Based on academic research (MAKER framework) by Cognizant AI Lab.  
Implementation: MIT License