# Hacker Dashboard - REV-AI

The **Hacker Dashboard** is the primary control center and real-time visualization interface for the REV-AI reverse engineering platform. Built with [NiceGUI](https://nicegui.io/), it provides a "hacker-style" dark mode interface to configure analysis, control execution, monitor the reverse engineering process, visualize architectural structures, and track agent consensus in real-time.

## Features

### 1. Control Panel
*   **Configuration:** Set the path to your Ghidra installation (`analyzeHeadless.bat`).
*   **Inputs:**
    *   **Target File:** Select the binary to analyze.
    *   **User Goal:** Define the specific objective (e.g., "Find the login logic").
    *   **Project Name:** Name your analysis project (auto-generated from filename).
*   **Controls:**
    *   **Start:** Begin the analysis pipeline.
    *   **Pause/Resume:** Temporarily halt execution.
    *   **Stop:** Terminate the current task.
    *   **Check Feasibility:** Run a quick calibration test to see if the LLM can handle the code complexity.

### 2. Star Map (Architectural Map)
*   **Visualizes:** The call graph and structural relationships of the target binary.
*   **Interaction:** Interactive force-directed graph where nodes represent functions/components and edges represent calls/dependencies.
*   **Tech:** ECharts force layout.

### 3. Consensus Arena
*   **Visualizes:** The voting distribution of AI models during the consensus phase.
*   **Purpose:** Quickly see which interpretation or refactoring strategy is winning among the ensemble of agents.
*   **Tech:** ECharts bar chart.

### 4. Live Loot & Logs
*   **Live Loot:** A real-time feed of "loot" found during analysis, such as secrets, API keys, vulnerabilities, or interesting strings. Items pulse to grab attention.
*   **System Logs:** A scrolling log of system events and backend agent activities.

### 5. Source Diff Viewer
*   **Visualizes:** Side-by-side comparison of the original decompiled code (e.g., C/C++) and the refactored output (e.g., C#).
*   **Purpose:** Verify the accuracy and quality of the translation.

## Installation

The dashboard requires `nicegui`.

```bash
pip install nicegui
```

## Usage

`dashboard.py` is now the main entry point for the application, replacing the legacy `launcher.py`.

To launch the dashboard:

```bash
python dashboard.py
```

The dashboard will start a local web server (default port 8080) and typically open your default browser automatically.

## Architecture

The dashboard runs on a separate thread from the main analysis pipeline and communicates via thread-safe queues:

*   **`log_queue`**: Transmits system logs.
*   **`consensus_queue`**: Updates the Consensus Arena chart.
*   **`loot_queue`**: Pushes new findings to the Live Loot feed.
*   **`graph_queue`**: Updates the Star Map nodes and links.

The UI updates every 100ms by polling these queues, ensuring a responsive experience without blocking the heavy analysis tasks.