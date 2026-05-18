"""
Deletes events from a chosen calendar between yesterday and end of next month.
Usage: python clear_calendar.py [lab111|pauper]
       If no argument is given, you are prompted to choose.
"""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import requests

# Load .env
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

CALENDARS = {
    "lab111":  "lab111",
    "pauper":  "Pauper Tournaments",
}

REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN", "")
CLIENT_ID     = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")


def get_access_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "grant_type":    "refresh_token",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
    })
    if not r.ok:
        print("Failed to get access token.")
        sys.exit(1)
    return r.json()["access_token"]


def pick_calendar() -> tuple[str, str]:
    """Return (shortname, full calendar name). Reads from argv or prompts."""
    if len(sys.argv) > 1:
        key = sys.argv[1].lower()
    else:
        print("Which calendar do you want to clear?")
        for k, v in CALENDARS.items():
            print(f"  {k} → {v}")
        key = input("Enter choice: ").strip().lower()

    if key not in CALENDARS:
        print(f'Unknown calendar "{key}". Valid options: {", ".join(CALENDARS)}')
        sys.exit(1)
    return key, CALENDARS[key]


# ── main ──────────────────────────────────────────────────────────────────────

shortname, calendar_name = pick_calendar()

tz    = ZoneInfo("Europe/Amsterdam")
today = datetime.now(tz)

time_min = (today - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
next_next_month = today.month + 2
next_next_year  = today.year + (next_next_month - 1) // 12
next_next_month = (next_next_month - 1) % 12 + 1
time_max = today.replace(year=next_next_year, month=next_next_month, day=1,
                         hour=0, minute=0, second=0, microsecond=0)

service = build("calendar", "v3", credentials=Credentials(get_access_token()))

all_calendars = service.calendarList().list().execute()["items"]
matches = [c for c in all_calendars if c["summary"] == calendar_name]

if len(matches) == 0:
    print(f'No calendar named "{calendar_name}" found. Aborting.')
    sys.exit(1)
if len(matches) > 1:
    print(f'Multiple calendars named "{calendar_name}" found. Aborting.')
    sys.exit(1)

calendar_id = matches[0]["id"]

print(f'\nTarget calendar : "{calendar_name}"')
print(f"Calendar ID     : {calendar_id}")
print(f"Deleting from   : {time_min.strftime('%Y-%m-%d')} to {(time_max - timedelta(days=1)).strftime('%Y-%m-%d')}")
print()

print("Counting events...")
total = 0
page_token = None
while True:
    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        pageToken=page_token,
    ).execute()
    total += len(resp["items"])
    page_token = resp.get("nextPageToken")
    if not page_token:
        break

if total == 0:
    print("No events found in that range.")
    sys.exit(0)

print(f"Found {total} event(s) to delete.")
print()
confirm = input(f'Type "{shortname}" to confirm deletion: ').strip()
if confirm != shortname:
    print("Confirmation did not match. Aborting.")
    sys.exit(1)

print("Deleting...")
deleted = 0
while True:
    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
    ).execute()
    if not resp["items"]:
        break
    for event in resp["items"]:
        service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
        deleted += 1
        print(f"  Deleted {deleted}/{total}: {event.get('summary', '(no title)')}")
        time.sleep(0.1)

print(f'\nDone. {deleted} event(s) deleted from "{calendar_name}".')
