"""
The Librarian: Groups functions into logical modules based on call graph proximity.
"""
import json
from typing import List, Dict, Set
from collections import defaultdict
from src.refactory_state import FunctionUnit, ModuleGroup

class Librarian:
    """
    Groups functions into modules using call graph clustering.
    Functions that call each other frequently are grouped together.
    """
    
    def __init__(self, min_module_size: int = 3, max_module_size: int = 15):
        self.min_module_size = min_module_size
        self.max_module_size = max_module_size
    
    def load_functions(self, json_path: str) -> List[FunctionUnit]:
        """Load function data from Ghidra export."""
        with open(json_path, 'r') as f:
            return json.load(f)
    
    def build_call_graph(self, functions: List[FunctionUnit]) -> Dict[str, Set[str]]:
        """Build adjacency list of function calls."""
        graph = defaultdict(set)
        addr_to_name = {f["address"]: f["name"] for f in functions}
        
        for func in functions:
            func_name = func["name"]
            for call in func["calls"]:
                called_name = call.get("name")
                if called_name and called_name in addr_to_name.values():
                    graph[func_name].add(called_name)
                    # Make it bidirectional for clustering
                    graph[called_name].add(func_name)
        
        return graph
    
    def cluster_functions(self, functions: List[FunctionUnit]) -> List[ModuleGroup]:
        """
        Cluster functions into modules using connected components.
        Each module becomes a separate source file.
        """
        call_graph = self.build_call_graph(functions)
        visited = set()
        modules = []
        
        # Create function lookup
        func_map = {f["name"]: f for f in functions}
        
        def dfs(func_name: str, cluster: Set[str]):
            """Depth-first search to find connected components."""
            if func_name in visited or len(cluster) >= self.max_module_size:
                return
            visited.add(func_name)
            cluster.add(func_name)
            
            for neighbor in call_graph.get(func_name, []):
                if neighbor not in visited:
                    dfs(neighbor, cluster)
        
        # Find all connected components
        for func in functions:
            if func["name"] not in visited:
                cluster = set()
                dfs(func["name"], cluster)
                
                if len(cluster) >= self.min_module_size:
                    # Create module from cluster
                    module_functions = [func_map[name] for name in cluster if name in func_map]
                    module_name = self._generate_module_name(module_functions)
                    
                    modules.append({
                        "module_name": module_name,
                        "functions": module_functions,
                        "shared_types": self._extract_shared_types(module_functions)
                    })
        
        # Handle orphan functions (put them in a "utilities" module)
        orphans = [f for f in functions if f["name"] not in visited]
        if orphans:
            modules.append({
                "module_name": "utilities",
                "functions": orphans,
                "shared_types": []
            })
        
        return modules
    
    def _generate_module_name(self, functions: List[FunctionUnit]) -> str:
        """Generate a meaningful module name based on function names."""
        # Look for common prefixes or keywords
        names = [f["name"] for f in functions]
        
        # Common reverse engineering patterns
        keywords = {
            "auth": "authentication",
            "net": "network",
            "file": "filesystem",
            "crypto": "cryptography",
            "init": "initialization",
            "parse": "parser",
            "verify": "verification",
            "process": "processor",
            "handle": "handler"
        }
        
        for keyword, module_name in keywords.items():
            if any(keyword in name.lower() for name in names):
                return module_name
        
        # Fallback: use the most common prefix
        if names:
            prefix = self._find_common_prefix(names)
            if len(prefix) > 3:
                return prefix.lower().rstrip('_')
        
        # Last resort: use first function name
        return names[0].lower().replace("fun_", "module_") if names else "unknown"
    
    def _find_common_prefix(self, strings: List[str]) -> str:
        """Find the longest common prefix among strings."""
        if not strings:
            return ""
        
        prefix = strings[0]
        for s in strings[1:]:
            while not s.startswith(prefix):
                prefix = prefix[:-1]
                if not prefix:
                    return ""
        return prefix
    
    def _extract_shared_types(self, functions: List[FunctionUnit]) -> List[str]:
        """Extract custom types that appear in multiple functions."""
        type_usage = defaultdict(int)
        
        for func in functions:
            for var_type in func.get("var_types", {}).values():
                # Filter out primitive types
                if var_type not in ["int", "char", "void", "long", "short", "float", "double", "byte"]:
                    type_usage[var_type] += 1
        
        # Return types used by at least 2 functions
        return [t for t, count in type_usage.items() if count >= 2]
    
    def group_functions(self, json_path: str) -> List[ModuleGroup]:
        """Main entry point: Load and group functions."""
        functions = self.load_functions(json_path)
        modules = self.cluster_functions(functions)
        
        print(f"[Librarian] Grouped {len(functions)} functions into {len(modules)} modules:")
        for module in modules:
            print(f"  - {module['module_name']}: {len(module['functions'])} functions")
        
        return modules