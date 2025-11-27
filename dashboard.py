import queue
import threading
import datetime
from nicegui import ui

# --- Data Queues ---
# These queues will be populated by the backend analysis threads
log_queue = queue.Queue()
consensus_queue = queue.Queue()
loot_queue = queue.Queue()
graph_queue = queue.Queue()

# --- Theme Configuration ---
THEME_BG = '#111111'
THEME_ACCENT = '#00FF00'
THEME_TEXT = '#E0E0E0'
THEME_BORDER = '#004400'

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
            ui.icon('terminal', color='green').classes('text-2xl animate-pulse')
            ui.label('SYSTEM ONLINE').classes('text-xs text-green-800')

    # --- Main Grid Layout ---
    with ui.grid(columns=3).classes('w-full h-[calc(100vh-4rem)] gap-1 p-1'):
        
        # 1. Star Map (Left Column)
        with ui.card().classes('col-span-1 h-full bg-black border border-green-900 rounded-none p-0 flex flex-col'):
            with ui.row().classes('w-full bg-green-900/20 p-2 border-b border-green-900'):
                ui.icon('hub', color='green').classes('mr-2')
                ui.label('ARCHITECTURAL MAP').classes('text-sm font-bold text-green-400')
            
            # Star Map Implementation
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
                    
                    # Consensus Arena Implementation
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

# --- Main Entry Point ---
if __name__ in {"__main__", "__mp_main__"}:
    create_dashboard()
    ui.run(title='REV-AI', dark=True, reload=False, port=8080)