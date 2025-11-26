import json
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# Reuse the LLM configuration
llm = ChatOllama(
    model="qwen2.5-coder:7b",
    temperature=0.3,
    format="json",
    base_url="http://localhost:11434"
)

PROMPT = """You are a reverse engineering strategist.
Task: Convert a high-level user goal into technical search terms for code analysis.

Input: User Goal (e.g., "Find how it talks to the bluetooth chip")
Output: JSON list of technical keywords, class names, or function substrings to look for.

Rules:
1. Include standard library terms (e.g., for Bluetooth: "BluetoothAdapter", "GATT", "RFCOMM").
2. Include common verb prefixes (e.g., "connect", "send", "receive").
3. Include specific hex constants if relevant (e.g. for CRC: "0xEDB88320").

Output Format:
{
  "keywords": ["Bluetooth", "GATT", "UUID", "00001101", "writeCharacteristic"]
}"""

def generate_search_terms(user_goal: str):
    print(f"[*] AI Agent analyzing goal: '{user_goal}'...")
    try:
        response = llm.invoke([
            SystemMessage(content=PROMPT),
            HumanMessage(content=user_goal)
        ])
        data = json.loads(response.content)
        keywords = data.get("keywords", [])
        print(f"[*] Generated Search Strategy: {keywords}")
        return keywords
    except Exception as e:
        print(f"[!] Error generating keywords: {e}")
        # Fallback to simple tokenization
        return user_goal.split()