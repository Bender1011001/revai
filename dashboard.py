import queue
import threading
import datetime
import os
import json
import sys
import tkinter as tk
from tkinter import filedialog
from nicegui import ui, app
import httpx
import asyncio

# Import backend logic
try:
    from re_agent_project.src.main import main_pipeline_wrapper
    from re_agent_project.src.calibration import measure_model_difficulty
except ImportError:
    # Fallback for when running from a different directory context
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from re_agent_project.src.main import main_pipeline_wrapper
    from re_agent_project.src.calibration import measure_model_difficulty

# --- Data Queues ---
log_queue = queue.Queue()
consensus_queue = queue.Queue()
loot_queue = queue.Queue()
graph_queue = queue.Queue()
diff_queue = queue.Queue()

# --- Theme Configuration ---
THEME_BG = '#111111'
THEME_ACCENT = '#00FF00'
THEME_TEXT = '#E0E0E0'
THEME_BORDER = '#004400'

CONFIG_FILE = "config.json"

# --- Helper Classes ---

class StreamToQueue:
    """Redirects stdout/stderr to a queue."""
    def __init__(self, queue_obj, original_stream=None):
        self.queue_obj = queue_obj
        self.original_stream = original_stream

    def write(self, message):
        if message.strip():
            self.queue_obj.put(message.strip())
        if self.original_stream:
            self.original_stream.write(message)
            self.original_stream.flush()

    def flush(self):
        if self.original_stream:
            self.original_stream.flush()

    def isatty(self):
        if self.original_stream:
            return self.original_stream.isatty()
        return False

class ProjectManager:
    """Manages project state persistence."""
    PROJECTS_DIR = "projects"

    @staticmethod
    def save_project_state(project_name, state):
        if not project_name:
            return
        
        project_dir = os.path.join(ProjectManager.PROJECTS_DIR, project_name)
        os.makedirs(project_dir, exist_ok=True)
        
        state_file = os.path.join(project_dir, "project_state.json")
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=4)
            # print(f"[Project] Saved state to {state_file}")
        except Exception as e:
            print(f"[Project] Error saving state: {e}")

    @staticmethod
    def load_project_state(project_name):
        project_dir = os.path.join(ProjectManager.PROJECTS_DIR, project_name)
        state_file = os.path.join(project_dir, "project_state.json")
        
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Project] Error loading state: {e}")
        
        # Fallback for existing projects without state file
        if os.path.exists(project_dir) and os.path.isdir(project_dir):
            return {
                'target_path': '', # Unknown
                'user_goal': '',   # Unknown
                'timestamp': datetime.datetime.now().isoformat()
            }
            
        return None

    @staticmethod
    def list_projects():
        if not os.path.exists(ProjectManager.PROJECTS_DIR):
            return []
        return [d for d in os.listdir(ProjectManager.PROJECTS_DIR)
                if os.path.isdir(os.path.join(ProjectManager.PROJECTS_DIR, d))]

class ConfigManager:
    """Manages loading and saving of configuration."""
    @staticmethod
    def load_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"[Config] Error loading config: {e}")
        return {"ghidra_path": ""}

    @staticmethod
    def save_config(config):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)

    @staticmethod
    def set_environment_config(config):
        """Set environment variables from config for downstream agents."""
        ENV_MAP = {
            "ollama_url": "OLLAMA_HOST",
            "ollama_model": "OLLAMA_MODEL",
            "openai_api_key": "OPENAI_API_KEY",
            "openai_model": "OPENAI_MODEL",
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "anthropic_model": "ANTHROPIC_MODEL",
            "groq_api_key": "GROQ_API_KEY",
            "groq_model": "GROQ_MODEL",
            "lightning_url": "LIGHTNING_URL",
            "lightning_token": "LIGHTNING_TOKEN",
        }
        
        for config_key, env_key in ENV_MAP.items():
            if config_key in config and config[config_key]:
                os.environ[env_key] = str(config[config_key])
                print(f"[Config] Set {env_key} from config.")

class AnalysisManager:
    """Manages the analysis thread and state."""
    def __init__(self):
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set() # Initially running
        self.is_running = False

    def start_analysis(self, file_path, user_goal, project_name):
        if self.is_running:
            return
        
        self.stop_event.clear()
        self.pause_event.set()
        self.is_running = True
        
        # Define output directory
        output_dir = os.path.join("projects", project_name)
        
        def run():
            try:
                config = ConfigManager.load_config()
                ghidra_path = config.get("ghidra_path")
                max_workers = config.get("max_workers", 4)
                
                if not ghidra_path:
                    print("Error: Ghidra path not configured.")
                    return

                ConfigManager.set_environment_config(config)
                
                print(f"--- Analysis Started ---")
                print(f"Target: {file_path}")
                print(f"Goal: {user_goal}")
                print(f"Project Dir: {output_dir}")
                
                # Define callbacks for data queues
                def on_loot(item):
                    loot_queue.put(item)
                
                def on_consensus(data):
                    consensus_queue.put(data)
                
                def on_graph(data):
                    graph_queue.put(data)

                def on_diff(data):
                    diff_queue.put(data)

                main_pipeline_wrapper(
                    file_path,
                    ghidra_path=ghidra_path,
                    user_goal=user_goal,
                    output_dir=output_dir,
                    stop_event=self.stop_event,
                    pause_event=self.pause_event,
                    loot_callback=on_loot,
                    consensus_callback=on_consensus,
                    graph_callback=on_graph,
                    diff_callback=on_diff,
                    max_workers=max_workers
                )
                
                if self.stop_event.is_set():
                    print("\n[!] Pipeline stopped by user.")
                else:
                    print("\n--- Pipeline Complete ---")
            except Exception as e:
                print(f"\n[FATAL ERROR]: {str(e)}")
            finally:
                self.is_running = False
                # We'll update UI state via polling in the main loop if needed, 
                # or rely on the user to see the "Complete" message.

        threading.Thread(target=run, daemon=True).start()

    def start_feasibility_check(self, project_name=None):
        if self.is_running:
            return

        file_path = None
        
        # Try to find dataset_dirty.json in the current project if provided
        if project_name:
            project_dir = os.path.join("projects", project_name)
            potential_path = os.path.join(project_dir, "ghidra_export", "dataset_dirty.json")
            if os.path.exists(potential_path):
                file_path = potential_path
                print(f"[Feasibility] Using project file: {file_path}")

        # Fallback to file dialog if not found or no project
        if not file_path:
            # Use tkinter for file dialog (hidden root)
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            file_path = filedialog.askopenfilename(
                title="Select dataset_dirty.json",
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
            )
            root.destroy()

        if not file_path:
            return

        self.stop_event.clear()
        self.pause_event.set()
        self.is_running = True

        def run():
            try:
                print(f"--- Feasibility Check Started ---")
                print(f"Loading: {file_path}")
                
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                import random
                samples = random.sample(data, min(len(data), 5))
                print(f"Selected {len(samples)} samples for calibration.")
                
                system_prompt = """You are an expert Reverse Engineer.
Your goal is to rename variables in the provided decompiled code to make it more readable.
Output ONLY a JSON object mapping old variable names to new, descriptive names.
Do not include any explanation or markdown formatting."""

                config = ConfigManager.load_config()
                model_name = config.get("ollama_model", "qwen2.5-coder:3b")
                
                p, feasible = measure_model_difficulty(model_name, samples, system_prompt, stop_event=self.stop_event)
                
                if self.stop_event.is_set():
                    print("\n[!] Calibration stopped.")
                else:
                    print(f"\nResults:")
                    print(f"Success Rate (p): {p:.2f}")
                    print(f"Feasible: {feasible}")
                    
                    if not feasible:
                        print("Warning: Task too difficult for this model (p <= 0.5).")
                    else:
                        print("Success: Model is capable of this task.")
                
            except Exception as e:
                print(f"\n[ERROR] Calibration failed: {str(e)}")
            finally:
                self.is_running = False

        threading.Thread(target=run, daemon=True).start()

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            print("\n[!] Paused...")
            return True # Paused
        else:
            self.pause_event.set()
            print("\n[>] Resumed...")
            return False # Resumed

    def stop(self):
        self.stop_event.set()
        self.pause_event.set() # Ensure threads wake up to exit
        print("\n[!] Stopping... please wait for threads to exit.")
        self.is_running = False

# Global Analysis Manager
analysis_manager = AnalysisManager()

# Redirect stdout/stderr
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = StreamToQueue(log_queue, original_stdout)
sys.stderr = StreamToQueue(log_queue, original_stderr)


def create_dashboard():
    """
    Initializes the Hacker Dashboard UI layout and update logic.
    """
    # Apply Global Styles
    ui.colors(primary=THEME_ACCENT, secondary=THEME_ACCENT, accent=THEME_ACCENT, dark=THEME_BG)
    ui.query('body').style(f'background-color: {THEME_BG}; color: {THEME_TEXT}; font-family: "Courier New", monospace;')

    # --- Header ---
    with ui.header().classes('items-center justify-between bg-black border-b border-green-900 h-16 px-4'):
        ui.label('PROJECT REV-AI // TARGET: [CONNECTED]').classes('text-xl font-bold text-green-500 tracking-widest')
        with ui.row().classes('items-center gap-4'):
            status_icon = ui.icon('terminal', color='green').classes('text-2xl animate-pulse')
            status_label = ui.label('SYSTEM ONLINE').classes('text-xs text-green-800')

    # --- Main Grid Layout ---
    with ui.grid(columns=3).classes('w-full h-[calc(100vh-4rem)] gap-1 p-1'):
        
        # 1. Control Panel & Star Map (Left Column)
        with ui.column().classes('col-span-1 h-full gap-1'):
            
            # Control Panel
            with ui.card().classes('w-full bg-black border border-green-900 rounded-none p-0 flex flex-col'):
                with ui.row().classes('w-full bg-green-900/20 p-2 border-b border-green-900'):
                    ui.icon('settings', color='green').classes('mr-2')
                    ui.label('CONTROL PANEL').classes('text-sm font-bold text-green-400')
                
                with ui.column().classes('p-4 gap-2 w-full'):
                    # Ghidra Config
                    def select_ghidra():
                        root = tk.Tk()
                        root.withdraw()
                        root.attributes('-topmost', True)
                        path = filedialog.askopenfilename(
                            title="Select analyzeHeadless Executable",
                            filetypes=[("Ghidra Headless", "analyzeHeadless.bat"), ("All Files", "*.*")]
                        )
                        root.destroy()
                        if path:
                            if not path.lower().endswith("analyzeheadless.bat"):
                                ui.notify("Invalid File: Please select 'analyzeHeadless.bat'", type='negative')
                                return
                            ghidra_root = os.path.dirname(os.path.dirname(os.path.abspath(path)))
                            config = ConfigManager.load_config()
                            config["ghidra_path"] = ghidra_root
                            ConfigManager.save_config(config)
                            ui.notify(f"Ghidra path set to: {ghidra_root}", type='positive')

                    ui.button('CONFIGURE GHIDRA PATH', on_click=select_ghidra).classes('w-full border border-green-500 text-green-500 bg-transparent hover:bg-green-900/50')

                    # Worker Count
                    worker_input = ui.number(label='WORKER THREADS', value=4, min=1, max=32).classes('w-full').props('input-class="text-green-400" label-color="green"')
                    
                    def on_worker_change(e):
                        config = ConfigManager.load_config()
                        config["max_workers"] = int(e.value)
                        ConfigManager.save_config(config)
                        ui.notify(f"Worker count set to: {int(e.value)}", type='positive')
                    
                    worker_input.on('change', on_worker_change)
                    
                    # Load saved worker count
                    config = ConfigManager.load_config()
                    worker_input.value = config.get("max_workers", 4)

                    # Ollama Model Selection
                    model_select = ui.select(options=[], label='OLLAMA MODEL').classes('w-full').props('input-class="text-green-400" label-color="green"')
                    
                    async def update_models():
                        try:
                            async with httpx.AsyncClient() as client:
                                resp = await client.get("http://localhost:11434/api/tags", timeout=2.0)
                                if resp.status_code == 200:
                                    models = [m['name'] for m in resp.json().get('models', [])]
                                    model_select.options = models
                                    
                                    # Load saved model or default
                                    config = ConfigManager.load_config()
                                    saved_model = config.get("ollama_model")
                                    if saved_model and saved_model in models:
                                        model_select.value = saved_model
                                    elif models:
                                        model_select.value = models[0]
                                        
                                    ui.notify("Models updated", type='positive')
                                else:
                                    ui.notify("Failed to fetch models", type='negative')
                        except Exception as e:
                            ui.notify(f"Ollama error: {e}", type='negative')

                    def on_model_change(e):
                        config = ConfigManager.load_config()
                        config["ollama_model"] = e.value
                        ConfigManager.save_config(config)
                        ui.notify(f"Model set to: {e.value}", type='positive')

                    model_select.on('update:model-value', on_model_change)
                    
                    with ui.row().classes('w-full gap-2'):
                        ui.button('REFRESH MODELS', on_click=update_models).classes('flex-1 border border-blue-500 text-blue-500 bg-transparent hover:bg-blue-900/50')
                        
                        def show_available_models():
                            # This would ideally fetch from ollama.com/library or similar if possible, 
                            # but for now we can just show a list of popular models or link to the site.
                            # Since we can't easily scrape the library without a backend proxy or similar,
                            # we'll just show a dialog with common models to copy-paste for `ollama pull`.
                            common_models = [
                                "qwen2.5-coder:7b", "qwen2.5-coder:3b", "llama3:8b", "mistral", "gemma:7b", "deepseek-coder:6.7b"
                            ]
                            with ui.dialog() as dialog, ui.card().classes('bg-black border border-green-500'):
                                ui.label('POPULAR MODELS (Run "ollama pull <name>" in terminal)').classes('text-green-500 font-bold mb-2')
                                for m in common_models:
                                    with ui.row().classes('items-center justify-between w-full'):
                                        ui.label(m).classes('text-green-400')
                                        ui.button(icon='content_copy', on_click=lambda x=m: [ui.clipboard.write(x), ui.notify(f"Copied {x}")]).props('flat round color=green')
                                ui.button('CLOSE', on_click=dialog.close).classes('w-full mt-2 border border-red-500 text-red-500')
                            dialog.open()

                        ui.button('AVAILABLE MODELS', on_click=show_available_models).classes('flex-1 border border-purple-500 text-purple-500 bg-transparent hover:bg-purple-900/50')

                    # Project Management
                    def load_project(name):
                        state = ProjectManager.load_project_state(name)
                        if state:
                            target_input.value = state.get('target_path', '')
                            goal_input.value = state.get('user_goal', '')
                            project_name_input.value = name
                            ui.notify(f"Loaded project: {name}", type='positive')
                        else:
                            ui.notify(f"Could not load project: {name}", type='negative')

                    def show_load_dialog():
                        projects = ProjectManager.list_projects()
                        if not projects:
                            ui.notify("No projects found.", type='warning')
                            return
                        
                        with ui.dialog() as dialog, ui.card().classes('bg-black border border-green-500'):
                            ui.label('SELECT PROJECT').classes('text-green-500 font-bold mb-2')
                            for p in projects:
                                ui.button(p, on_click=lambda n=p: [load_project(n), dialog.close()]).classes('w-full mb-1 bg-green-900/20 text-green-400 hover:bg-green-900/50')
                            ui.button('CANCEL', on_click=dialog.close).classes('w-full mt-2 border border-red-500 text-red-500')
                        dialog.open()

                    ui.button('LOAD PROJECT', on_click=show_load_dialog).classes('w-full border border-yellow-500 text-yellow-500 bg-transparent hover:bg-yellow-900/50 mb-2')

                    # Inputs
                    target_input = ui.input(label='TARGET FILE PATH').classes('w-full').props('input-class="text-green-400" label-color="green"')
                    
                    def browse_target():
                        root = tk.Tk()
                        root.withdraw()
                        root.attributes('-topmost', True)
                        path = filedialog.askopenfilename(title="Select Target Binary")
                        root.destroy()
                        if path:
                            target_input.value = path
                            # Auto-generate project name
                            base_name = os.path.basename(path)
                            project_name_input.value = os.path.splitext(base_name)[0] + "_analysis"
                            auto_save()

                    ui.button('BROWSE TARGET', on_click=browse_target).classes('w-full border border-green-500 text-green-500 bg-transparent hover:bg-green-900/50')
                    
                    goal_input = ui.input(label='USER GOAL').classes('w-full').props('input-class="text-green-400" label-color="green"')
                    goal_input.value = "e.g. Find the login logic"
                    
                    project_name_input = ui.input(label='PROJECT NAME').classes('w-full').props('input-class="text-green-400" label-color="green"')

                    # Auto-save Logic
                    def auto_save():
                        if project_name_input.value:
                            state = {
                                'target_path': target_input.value,
                                'user_goal': goal_input.value,
                                'timestamp': datetime.datetime.now().isoformat()
                            }
                            ProjectManager.save_project_state(project_name_input.value, state)
                    
                    # Trigger auto-save on input changes (debounced via timer in main loop or explicit events)
                    target_input.on('change', auto_save)
                    goal_input.on('change', auto_save)
                    project_name_input.on('change', auto_save)

                    # Action Buttons
                    with ui.row().classes('w-full gap-2'):
                        def start_click():
                            if not target_input.value or not goal_input.value or not project_name_input.value:
                                ui.notify("Please fill in all fields", type='warning')
                                return
                            analysis_manager.start_analysis(target_input.value, goal_input.value, project_name_input.value)
                            ui.notify("Analysis Started", type='positive')

                        ui.button('START', on_click=start_click).classes('flex-1 bg-green-700 text-black hover:bg-green-600')
                        
                        def pause_click():
                            is_paused = analysis_manager.toggle_pause()
                            pause_btn.text = 'RESUME' if is_paused else 'PAUSE'
                        
                        pause_btn = ui.button('PAUSE', on_click=pause_click).classes('flex-1 border border-yellow-500 text-yellow-500 bg-transparent hover:bg-yellow-900/50')
                        
                        def stop_click():
                            analysis_manager.stop()
                            ui.notify("Stopping execution...", type='warning')
                        
                        ui.button('STOP', on_click=stop_click).classes('flex-1 border border-red-500 text-red-500 bg-transparent hover:bg-red-900/50')

                    ui.button('CHECK FEASIBILITY', on_click=lambda: analysis_manager.start_feasibility_check(project_name_input.value)).classes('w-full border border-blue-500 text-blue-500 bg-transparent hover:bg-blue-900/50 mt-2')

            # Star Map
            with ui.card().classes('w-full flex-1 bg-black border border-green-900 rounded-none p-0 flex flex-col'):
                with ui.row().classes('w-full bg-green-900/20 p-2 border-b border-green-900'):
                    ui.icon('hub', color='green').classes('mr-2')
                    ui.label('ARCHITECTURAL MAP').classes('text-sm font-bold text-green-400')
                
                star_map_options = {
                    'backgroundColor': 'transparent',
                    'tooltip': {},
                    'series': [
                        {
                            'type': 'graph',
                            'layout': 'force',
                            'symbolSize': 10,
                            'roam': True,
                            'label': {'show': True, 'color': THEME_TEXT},
                            'edgeSymbol': ['circle', 'arrow'],
                            'edgeSymbolSize': [4, 10],
                            'data': [],
                            'links': [],
                            'lineStyle': {'opacity': 0.9, 'width': 2, 'curveness': 0, 'color': THEME_ACCENT},
                            'itemStyle': {'color': THEME_ACCENT},
                            'force': {'repulsion': 100}
                        }
                    ]
                }
                star_map = ui.echart(options=star_map_options).classes('w-full h-full')

        # 2. Center & Right Column Container
        with ui.column().classes('col-span-2 h-full gap-1'):
            
            # Top Row: Consensus Arena & Live Loot
            with ui.grid(columns=2).classes('w-full h-1/2 gap-1'):
                
                # Consensus Arena (Top Center)
                with ui.card().classes('h-full bg-black border border-green-900 rounded-none p-0 flex flex-col'):
                    with ui.row().classes('w-full bg-green-900/20 p-2 border-b border-green-900'):
                        ui.icon('poll', color='green').classes('mr-2')
                        ui.label('CONSENSUS ARENA').classes('text-sm font-bold text-green-400')
                    
                    consensus_options = {
                        'backgroundColor': 'transparent',
                        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}},
                        'grid': {'left': '3%', 'right': '4%', 'bottom': '3%', 'containLabel': True},
                        'xAxis': {'type': 'category', 'data': [], 'axisLine': {'lineStyle': {'color': THEME_TEXT}}, 'axisLabel': {'color': THEME_TEXT}},
                        'yAxis': {'type': 'value', 'axisLine': {'lineStyle': {'color': THEME_TEXT}}, 'axisLabel': {'color': THEME_TEXT}, 'splitLine': {'lineStyle': {'color': '#333'}}},
                        'series': [{'data': [], 'type': 'bar', 'itemStyle': {'color': THEME_ACCENT}}]
                    }
                    consensus_chart = ui.echart(options=consensus_options).classes('w-full h-full')

                # Live Loot (Top Right)
                with ui.card().classes('h-full bg-black border border-green-900 rounded-none p-0 flex flex-col'):
                    with ui.row().classes('w-full bg-green-900/20 p-2 border-b border-green-900'):
                        ui.icon('inventory_2', color='green').classes('mr-2')
                        ui.label('LIVE LOOT & LOGS').classes('text-sm font-bold text-green-400')
                    
                    with ui.column().classes('w-full h-full gap-0'):
                        # Scrollable Container for Findings
                        loot_container = ui.scroll_area().classes('w-full h-1/2 p-2 border-b border-green-900 bg-black text-xs font-mono')
                        with loot_container:
                            ui.label('> SYSTEM INITIALIZED').classes('text-green-700 mb-1')
                        
                        # Log Container
                        log_container = ui.log().classes('w-full h-1/2 p-2 bg-black text-xs font-mono text-gray-500')

            # 3. Diff Viewer (Bottom Row)
            with ui.card().classes('w-full h-1/2 bg-black border border-green-900 rounded-none p-0 flex flex-col'):
                with ui.row().classes('w-full bg-green-900/20 p-2 border-b border-green-900 justify-between'):
                    with ui.row():
                        ui.icon('code', color='green').classes('mr-2')
                        ui.label('SOURCE DIFF').classes('text-sm font-bold text-green-400')
                    ui.label('C vs C#').classes('text-xs text-green-800')

                with ui.grid(columns=2).classes('w-full h-full gap-0'):
                    # Left: Original C
                    with ui.column().classes('h-full border-r border-green-900 p-2 overflow-auto'):
                        ui.label('// Original Decompilation').classes('text-gray-500 mb-2')
                        ui.code('void func_001() {\n  int iVar1;\n  // ...\n}', language='c').classes('w-full bg-transparent')
                    
                    # Right: Refactored C#
                    with ui.column().classes('h-full p-2 overflow-auto'):
                        ui.label('// Refactored Output').classes('text-green-500 mb-2')
                        ui.code('public void ProcessData() {\n  int status;\n  // ...\n}', language='csharp').classes('w-full bg-transparent')

    # --- Update Logic ---
    def update_ui():
        """Polls queues and updates UI elements."""
        # 1. Process Loot Queue
        while not loot_queue.empty():
            try:
                item = loot_queue.get_nowait()
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                with loot_container:
                    ui.label(f"[{timestamp}] {item}").classes('text-yellow-400 text-xs animate-pulse font-mono')
                loot_container.scroll_to(percent=1.0) # Auto-scroll to bottom
            except queue.Empty:
                break
        
        # 2. Process Log Queue
        while not log_queue.empty():
            try:
                log_msg = log_queue.get_nowait()
                log_container.push(f"> {log_msg}")
            except queue.Empty:
                break

        # 3. Process Consensus Queue
        if not consensus_queue.empty():
            try:
                # Drain queue to get latest
                data = None
                while not consensus_queue.empty():
                    data = consensus_queue.get_nowait()
                
                if data:
                    consensus_chart.options['xAxis']['data'] = data.get('categories', [])
                    consensus_chart.options['series'][0]['data'] = data.get('values', [])
                    consensus_chart.update()
            except queue.Empty:
                pass

        # 4. Process Graph Queue
        if not graph_queue.empty():
            try:
                # Drain queue to get latest
                data = None
                while not graph_queue.empty():
                    data = graph_queue.get_nowait()
                
                if data:
                    star_map.options['series'][0]['data'] = data.get('nodes', [])
                    star_map.options['series'][0]['links'] = data.get('links', [])
                    star_map.update()
            except queue.Empty:
                pass

    # Start the update loop (runs every 100ms)
    ui.timer(0.1, update_ui)

    # --- Startup Checks ---
    async def check_ollama():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://localhost:11434/api/tags", timeout=2.0)
                if resp.status_code == 200:
                    log_queue.put("Ollama connection established.")
                    status_label.text = 'SYSTEM ONLINE'
                    status_label.classes(remove='text-red-800', add='text-green-800')
                    status_icon.props(remove='color=red', add='color=green')
                    
                    # Initial model fetch
                    await update_models()
                else:
                    raise Exception(f"Status {resp.status_code}")
        except Exception as e:
            log_queue.put(f"WARNING: Ollama not reachable: {e}")
            status_label.text = 'OLLAMA OFFLINE'
            status_label.classes(remove='text-green-800', add='text-red-800')
            status_icon.props(remove='color=green', add='color=red')
            ui.notify("Ollama is not running! Please start Ollama.", type='negative', close_button=True, multi_line=True)

    ui.timer(0.1, check_ollama, once=True)

# --- Main Entry Point ---
if __name__ in {"__main__", "__mp_main__"}:
    create_dashboard()
    ui.run(title='REV-AI', dark=True, reload=False, port=8081)