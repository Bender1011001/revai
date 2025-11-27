import re
from typing import List, Dict

PATTERNS = {
    "AWS_KEY": r"AKIA[0-9A-Z]{16}",
    "Generic_API_Key": r"['\"][a-zA-Z0-9]{32,}['\"]",
    "IPv4": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
    "URL": r"https?://[^\s\"']+"
}

def inspect_module(module_code: str) -> Dict[str, List[str]]:
    findings = {}
    for label, pattern in PATTERNS.items():
        matches = re.findall(pattern, module_code)
        if matches:
            findings[label] = list(set(matches))
    return findings