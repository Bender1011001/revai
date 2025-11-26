import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import os
import json

# Import main pipeline wrapper
from re_agent_project.src.main import main_pipeline_wrapper

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
    path = filedialog.askopenfilename(
        title="Select analyzeHeadless Executable",
        filetypes=[("Ghidra Headless", "analyzeHeadless.bat"), ("All Files", "*.*")]
    )
    if path:
        # Verify it's the correct file
        if not path.lower().endswith("analyzeheadless.bat"):
            messagebox.showerror("Invalid File", "Please select the 'analyzeHeadless.bat' file located in the 'support' directory of your Ghidra installation.")
            return

        # Derive the installation directory from the executable path
        # Expected path: <ghidra_root>/support/analyzeHeadless.bat
        ghidra_root = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        
        config = load_config()
        config["ghidra_path"] = ghidra_root
        save_config(config)
        messagebox.showinfo("Config Saved", f"Ghidra path set to:\n{ghidra_root}\n(Derived from selected executable)")

def run_analysis(file_path, log_window):
    config = load_config()
    ghidra_path = config.get("ghidra_path")
    
    def log(msg):
        log_window.after(0, lambda: log_window.insert(tk.END, msg))
        log_window.after(0, lambda: log_window.see(tk.END))

    if not ghidra_path:
        log("Error: Ghidra path not configured. Please click 'Configure Ghidra Path'.\n")
        return

    log(f"Analyzing: {file_path}...\n")
    try:
        # Call the wrapper function
        main_pipeline_wrapper(file_path, ghidra_path=ghidra_path)
        log(f"Analysis Complete for {file_path}\n")
    except Exception as e:
        log(f"Error: {str(e)}\n")

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

try:
    root.mainloop()
except KeyboardInterrupt:
    print("Application interrupted by user")
    root.quit()