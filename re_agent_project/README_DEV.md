# Reverse Engineering MAKER Agent - Deployment

## Prerequisites
1.  **Ollama**: Must be installed and running.
    * `ollama pull qwen2.5-coder:7b`
    * `ollama serve`
2.  **Python Environment**:
    * `pip install -r requirements.txt`
3.  **Ghidra**: Ensure `analyzeHeadless` is in your PATH.

## Workflow

### Step 1: The Surgical Decomposition
Extract atomic units from the binary using Ghidra Headless.
```bash
<GHIDRA_INSTALL>/support/analyzeHeadless <PROJECT_PATH> <PROJECT_NAME> -process <BINARY.exe> -postScript ghidra_scripts/export_function.py
```

*Output:* `/tmp/ghidra_bridge/dataset_dirty.json`

### Step 2: The MAKER Loop

Run the Agentic loop. This will query the LLM, red-flag hallucinations, and vote on the best renames.

```bash
python src/main.py
```

*Output:* `/tmp/ghidra_bridge/renames.json`

### Step 3: Integration

Apply the consensus-approved names back to Ghidra.

```bash
<GHIDRA_INSTALL>/support/analyzeHeadless <PROJECT_PATH> <PROJECT_NAME> -process <BINARY.exe> -postScript ghidra_scripts/import_renames.py
```

## Hardware Notes (RTX 4060 Ti)

  * **Context Window:** The code is configured for \~8k context. If you encounter Out Of Memory (OOM) errors, open `src/maker_nodes.py` and increase the truncation aggressiveness (reduce `12000` characters to `8000`).
  * **Concurrency:** The graph runs nodes sequentially. Do not try to parallelize the "Micro-Agent" generation, or you will OOM the GPU.