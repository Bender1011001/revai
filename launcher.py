import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import sys
import os
import json

# Ensure src is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 're_agent_project'))
from src.main import main_pipeline_wrapper

CONFIG_FILE = "config.json"

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
    path = filedialog.askdirectory(title="Select Ghidra Installation Directory")
    if path:
        config = load_config()
        config["ghidra_path"] = path
        save_config(config)
        messagebox.showinfo("Config Saved", f"Ghidra path set to:\n{path}")

def run_analysis(file_path, log_window):
    config = load_config()
    ghidra_path = config.get("ghidra_path")
    
    if not ghidra_path:
        log_window.insert(tk.END, "Error: Ghidra path not configured. Please click 'Configure Ghidra Path'.\n")
        return

    log_window.insert(tk.END, f"Analyzing: {file_path}...\n")
    try:
        # Call the wrapper function
        main_pipeline_wrapper(file_path, ghidra_path=ghidra_path)
        log_window.insert(tk.END, f"Analysis Complete for {file_path}\n")
    except Exception as e:
        log_window.insert(tk.END, f"Error: {str(e)}\n")

def on_drop(event):
    file_path = event.data.strip('{}')
    log_window.insert(tk.END, f"Dropped file: {file_path}\n")
    threading.Thread(target=run_analysis, args=(file_path, log_window)).start()

root = TkinterDnD.Tk()
root.title("Universal Refactory")
root.geometry("600x450")

btn_config = tk.Button(root, text="Configure Ghidra Path", command=select_ghidra)
btn_config.pack(pady=5)

label = tk.Label(root, text="Drag and Drop Binary here")
label.pack(pady=10)

log_window = tk.Text(root, height=15, width=70)
log_window.pack(pady=10)

root.drop_target_register(DND_FILES)
root.dnd_bind('<<Drop>>', on_drop)

root.mainloop()