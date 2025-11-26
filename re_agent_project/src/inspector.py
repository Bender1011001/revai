import re
from typing import List, Dict

PATTERNS = {
    "AWS_KEY": r"AKIA[0-9A-Z]{16}",
    "Generic_API_Key": r"['\"][a-zA-Z0-9]{32,}['\"]",
    "IPv4": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "URL": r"https?://[^\s\"']+"
}

def inspect_module(module_code: str) -> Dict[str, List[str]]:
    findings = {}
    for label, pattern in PATTERNS.items():
        matches = re.findall(pattern, module_code)
        if matches:
            findings[label] = list(set(matches))
    return findings