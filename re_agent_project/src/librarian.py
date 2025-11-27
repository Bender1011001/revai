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
        
        # Find all connected components
        hard_limit = int(self.max_module_size * 1.5)
        
        for func in functions:
            if func["name"] not in visited:
                cluster = set()
                # Iterative DFS to avoid recursion depth issues
                stack = [func["name"]]
                
                while stack:
                    current_func = stack.pop()
                    
                    if current_func in visited:
                        continue
                    
                    if len(cluster) >= hard_limit:
                        break
                    
                    visited.add(current_func)
                    cluster.add(current_func)
                    
                    for neighbor in call_graph.get(current_func, []):
                        if neighbor not in visited:
                            stack.append(neighbor)
                
                if len(cluster) >= self.min_module_size:
                    # Create module from cluster
                    module_functions = [func_map[name] for name in cluster if name in func_map]
                    module_name = self._generate_module_name(module_functions)
                    
                    modules.append({
                        "module_name": module_name,
                        "functions": module_functions,
                        "shared_types": self._extract_shared_types(module_functions)
                    })
        
        # Collect all functions that made it into a module
        grouped_function_names = set()
        for m in modules:
            for f in m["functions"]:
                grouped_function_names.add(f["name"])

        # Handle orphan functions (put them in a "utilities" module)
        orphans = [f for f in functions if f["name"] not in grouped_function_names]
        if orphans:
            # Split large utilities module into smaller chunks
            chunk_size = self.max_module_size
            for i in range(0, len(orphans), chunk_size):
                chunk = orphans[i:i + chunk_size]
                modules.append({
                    "module_name": f"utilities_{i//chunk_size + 1}",
                    "functions": chunk,
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
                # Expanded list to cover more C/C++ primitives and common typedefs
                PRIMITIVE_TYPES = {
                    "int", "char", "void", "long", "short", "float", "double", "byte",
                    "bool", "boolean", "size_t", "ssize_t",
                    "uint8_t", "int8_t", "uint16_t", "int16_t",
                    "uint32_t", "int32_t", "uint64_t", "int64_t",
                    "unsigned int", "unsigned long", "unsigned char", "unsigned short",
                    "signed int", "signed long", "signed char", "signed short",
                    "long long", "unsigned long long",
                    "wchar_t", "char16_t", "char32_t",
                    "__int8", "__int16", "__int32", "__int64",
                    "undefined", "undefined1", "undefined2", "undefined4", "undefined8"
                }
                
                if var_type not in PRIMITIVE_TYPES:
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

    def get_visualization_data(self, functions: List[FunctionUnit]) -> Dict:
        """
        Convert call graph into ECharts format for visualization.
        
        Args:
            functions: List of function units
            
        Returns:
            Dict with 'nodes' and 'links' for ECharts
        """
        graph = self.build_call_graph(functions)
        
        # Create nodes
        # symbolSize based on complexity (param count as proxy)
        nodes = []
        for f in functions:
            param_count = len(f.get("variables", []))  # Use variable count as proxy for complexity
            nodes.append({
                "name": f["name"],
                "symbolSize": max(5, min(50, param_count * 2)),
                "value": param_count,
                "category": 0  # Default category
            })
            
        # Create links
        links = []
        for src, targets in graph.items():
            for tgt in targets:
                links.append({
                    "source": src,
                    "target": tgt
                })
                
        return {"nodes": nodes, "links": links}