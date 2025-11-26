import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import os
import json
import sys

# Import main pipeline wrapper
from re_agent_project.src.main import main_pipeline_wrapper
from re_agent_project.src.calibration import measure_model_difficulty

CONFIG_FILE = "config.json"

# --- 1. LOGGING REDIRECTOR CLASS ---
class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        # Update GUI in a thread-safe way
        self.widget.after(0, self._write, str)

    def _write(self, str):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, str, (self.tag,))
        self.widget.see(tk.END)
        self.widget.configure(state='disabled')

    def flush(self):
        pass

# --- GLOBAL EVENTS ---
stop_event = threading.Event()
pause_event = threading.Event()
pause_event.set() # Initially running (not paused)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"ghidra_path": ""}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def select_ghidra():
    path = filedialog.askopenfilename(
        title="Select analyzeHeadless Executable",
        filetypes=[("Ghidra Headless", "analyzeHeadless.bat"), ("All Files", "*.*")]
    )
    if path:
        if not path.lower().endswith("analyzeheadless.bat"):
            messagebox.showerror("Invalid File", "Please select 'analyzeHeadless.bat'")
            return
        ghidra_root = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        config = load_config()
        config["ghidra_path"] = ghidra_root
        save_config(config)
        messagebox.showinfo("Config Saved", f"Ghidra path set to:\n{ghidra_root}")

def check_feasibility():
    # 1. Select dataset
    file_path = filedialog.askopenfilename(
        title="Select dataset_dirty.json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    if not file_path:
        return

    # Reset events
    stop_event.clear()
    pause_event.set()
    update_control_buttons(running=True)

    def run_calibration():
        try:
            print(f"--- Feasibility Check Started ---")
            print(f"Loading: {file_path}")
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Select samples
            import random
            samples = random.sample(data, min(len(data), 5))
            print(f"Selected {len(samples)} samples for calibration.")
            
            # Default system prompt
            system_prompt = """You are an expert Reverse Engineer.
Your goal is to rename variables in the provided decompiled code to make it more readable.
Output ONLY a JSON object mapping old variable names to new, descriptive names.
Do not include any explanation or markdown formatting."""

            model_name = "qwen2.5-coder:3b" # Default
            
            p, feasible = measure_model_difficulty(model_name, samples, system_prompt, stop_event=stop_event)
            
            if stop_event.is_set():
                print("\n[!] Calibration stopped.")
            else:
                print(f"\nResults:")
                print(f"Success Rate (p): {p:.2f}")
                print(f"Feasible: {feasible}")
                
                if not feasible:
                    print("Warning: Task too difficult for this model (p <= 0.5).")
                else:
                    print("Success: Model is capable of this task.")
                
            print("---------------------------------")
            
        except Exception as e:
            print(f"\n[ERROR] Calibration failed: {str(e)}")
        finally:
            update_control_buttons(running=False)

    threading.Thread(target=run_calibration, daemon=True).start()

def run_analysis(file_path, user_goal, output_dir):
    config = load_config()
    ghidra_path = config.get("ghidra_path")
    
    if not ghidra_path:
        print("Error: Ghidra path not configured.\n")
        update_control_buttons(running=False)
        return

    print(f"--- Analysis Started ---")
    print(f"Target: {file_path}")
    print(f"Goal: {user_goal}")
    print(f"Project Dir: {output_dir}")
    print(f"------------------------\n")
    
    try:
        main_pipeline_wrapper(
            file_path,
            ghidra_path=ghidra_path,
            user_goal=user_goal,
            output_dir=output_dir,
            stop_event=stop_event,
            pause_event=pause_event
        )
        if stop_event.is_set():
            print("\n[!] Pipeline stopped by user.")
        else:
            print("\n--- Pipeline Complete ---")
    except Exception as e:
        print(f"\n[FATAL ERROR]: {str(e)}")
    finally:
        update_control_buttons(running=False)

def on_drop(event):
    file_path = event.data.strip('{}')
    user_goal = goal_entry.get().strip()
    project_name = proj_entry.get().strip()
    
    if not user_goal:
        messagebox.showwarning("Missing Info", "Please describe your goal first (e.g., 'Find the login logic')")
        return

    # Auto-generate project name if empty
    if not project_name:
        base_name = os.path.basename(file_path)
        project_name = os.path.splitext(base_name)[0] + "_analysis"
        # Update the entry to show the generated name
        proj_entry.delete(0, tk.END)
        proj_entry.insert(0, project_name)
    
    # Define output directory
    output_dir = os.path.join("projects", project_name)

    # Clear log
    log_window.configure(state='normal')
    log_window.delete(1.0, tk.END)
    log_window.configure(state='disabled')
    
    # Reset events
    stop_event.clear()
    pause_event.set()
    update_control_buttons(running=True)

    threading.Thread(target=run_analysis, args=(file_path, user_goal, output_dir), daemon=True).start()

def toggle_pause():
    if pause_event.is_set():
        pause_event.clear()
        btn_pause.config(text="Resume")
        print("\n[!] Paused...")
    else:
        pause_event.set()
        btn_pause.config(text="Pause")
        print("\n[>] Resumed...")

def stop_execution():
    if messagebox.askyesno("Stop", "Are you sure you want to stop the current task?"):
        stop_event.set()
        # Also ensure we are not paused so threads can wake up and stop
        pause_event.set()
        btn_pause.config(text="Pause")
        print("\n[!] Stopping... please wait for threads to exit.")

def update_control_buttons(running):
    if running:
        btn_pause.config(state=tk.NORMAL, text="Pause")
        btn_stop.config(state=tk.NORMAL)
        btn_feasibility.config(state=tk.DISABLED)
        # Disable drag and drop? Not easily possible with TkinterDnD but we can ignore drops
    else:
        btn_pause.config(state=tk.DISABLED, text="Pause")
        btn_stop.config(state=tk.DISABLED)
        btn_feasibility.config(state=tk.NORMAL)

# --- GUI SETUP ---
root = TkinterDnD.Tk()
root.title("RevAI - Intelligent Reverse Engineering")
root.geometry("800x600")

# Top Frame for Config
frame_top = tk.Frame(root)
frame_top.pack(fill=tk.X, padx=10, pady=5)

btn_config = tk.Button(frame_top, text="Configure Ghidra Path", command=select_ghidra)
btn_config.pack(side=tk.LEFT)

btn_feasibility = tk.Button(frame_top, text="Check Feasibility", command=check_feasibility)
btn_feasibility.pack(side=tk.LEFT, padx=5)

# Control Buttons
btn_pause = tk.Button(frame_top, text="Pause", command=toggle_pause, state=tk.DISABLED)
btn_pause.pack(side=tk.LEFT, padx=5)

btn_stop = tk.Button(frame_top, text="Stop", command=stop_execution, state=tk.DISABLED, bg="#ffcccc")
btn_stop.pack(side=tk.LEFT, padx=5)

# Middle Frame for User Goal
frame_mid = tk.Frame(root)
frame_mid.pack(fill=tk.X, padx=10, pady=5)

lbl_goal = tk.Label(frame_mid, text="Goal / Target Description:")
lbl_goal.pack(anchor=tk.W)

goal_entry = tk.Entry(frame_mid)
goal_entry.pack(fill=tk.X, pady=2)
goal_entry.insert(0, "e.g. Find the bluetooth communication protocol")

# Frame for Project Name
frame_proj = tk.Frame(root)
frame_proj.pack(fill=tk.X, padx=10, pady=5)

lbl_proj = tk.Label(frame_proj, text="Project Name (Optional):")
lbl_proj.pack(anchor=tk.W)

proj_entry = tk.Entry(frame_proj)
proj_entry.pack(fill=tk.X, pady=2)

lbl_drop = tk.Label(root, text="[ Drag and Drop Binary Here to Start ]", font=("Arial", 12, "bold"), bg="#e1e1e1", height=2)
lbl_drop.pack(fill=tk.X, padx=10, pady=10)

# Bottom Frame for Logs
log_window = scrolledtext.ScrolledText(root, height=20)
log_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
log_window.configure(state='disabled') # Read-only

# Redirect stdout/stderr to the log window
sys.stdout = TextRedirector(log_window, "stdout")
sys.stderr = TextRedirector(log_window, "stderr")

root.drop_target_register(DND_FILES)
root.dnd_bind('<<Drop>>', on_drop)

try:
    root.mainloop()
except KeyboardInterrupt:
    root.quit()