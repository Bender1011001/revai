import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), 're_agent_project'))
from src.main import main_pipeline_wrapper

def run_analysis(file_path, log_window):
    log_window.insert(tk.END, f"Analyzing: {file_path}...\n")
    try:
        # Call the wrapper function
        main_pipeline_wrapper(file_path)
        log_window.insert(tk.END, f"Analysis Complete for {file_path}\n")
    except Exception as e:
        log_window.insert(tk.END, f"Error: {str(e)}\n")

def on_drop(event):
    file_path = event.data.strip('{}')
    log_window.insert(tk.END, f"Dropped file: {file_path}\n")
    threading.Thread(target=run_analysis, args=(file_path, log_window)).start()

root = TkinterDnD.Tk()
root.title("Universal Refactory")
root.geometry("600x400")

label = tk.Label(root, text="Drag and Drop APK or EXE here")
label.pack(pady=20)

log_window = tk.Text(root, height=15, width=70)
log_window.pack(pady=10)

root.drop_target_register(DND_FILES)
root.dnd_bind('<<Drop>>', on_drop)

root.mainloop()