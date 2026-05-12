"""
Run this once after sending any message to your bot.
It prints your chat ID so you can add it to .env and secrets.txt
"""
import requests

token = input("Paste your Telegram bot token: ").strip()
r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")

if not r.ok:
    print(f"Error: {r.text}")
    exit(1)

updates = r.json().get("result", [])
if not updates:
    print("No messages found. Send any message to your bot first, then re-run this script.")
    exit(1)

chat_id = updates[-1]["message"]["chat"]["id"]
print(f"\nTELEGRAM_TOKEN={token}")
print(f"TELEGRAM_CHAT_ID={chat_id}")
print("\nAdd both lines to your .env and secrets.txt")
