"""One Sarvam call to check the key works. Run from backend/: .venv/Scripts/python.exe scripts/sarvam_check.py"""

import os

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
reply = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Say hello in Odia, Hindi and English, one line each."}],
)
print(reply.choices[0].message.content)
