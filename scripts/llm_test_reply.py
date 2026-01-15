from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.local_llm import generate_reply

prompt = """You are the customer replying to a vendor.

Write a short, polite email reply.

Goal:
- Ask them to send the invoice.
- Confirm that once received, payment will be processed today.

Tone: professional, friendly, 3–5 sentences.
Do NOT say "thank you for choosing our services".
Sign off as: Bhavyasri
"""

print("LLM Reply:\n")
print(generate_reply(prompt))
