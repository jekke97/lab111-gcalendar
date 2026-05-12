"""
Deletes events from the lab111 calendar between yesterday and end of next month.
Exits immediately if the lab111 calendar cannot be identified unambiguously.
"""
import os
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

CALENDAR_NAME = "lab111"
REFRESH_TOKEN = os.environ.get("REFRESH_TOKEN", "")
CLIENT_ID     = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")

amsterdam = ZoneInfo("Europe/Amsterdam")
today     = datetime.now(amsterdam)

# yesterday at 00:00
time_min = (today - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

# first day of the month after next (= exclusive end of next month)
next_next_month = today.month + 2
next_next_year  = today.year + (next_next_month - 1) // 12
next_next_month = (next_next_month - 1) % 12 + 1
time_max = today.replace(year=next_next_year, month=next_next_month, day=1,
                         hour=0, minute=0, second=0, microsecond=0)


def get_access_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "grant_type":    "refresh_token",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
    })
    if not r.ok:
        print("Failed to get access token.")
        exit(1)
    return r.json()["access_token"]


service = build("calendar", "v3", credentials=Credentials(get_access_token()))

# Find the lab111 calendar — must match exactly one calendar by name
all_calendars = service.calendarList().list().execute()["items"]
matches = [c for c in all_calendars if c["summary"] == CALENDAR_NAME]

if len(matches) == 0:
    print(f'No calendar named "{CALENDAR_NAME}" found. Aborting.')
    exit(1)
if len(matches) > 1:
    print(f'Multiple calendars named "{CALENDAR_NAME}" found. Aborting.')
    exit(1)

target        = matches[0]
calendar_id   = target["id"]
calendar_name = target["summary"]

print(f'\nTarget calendar : "{calendar_name}"')
print(f"Calendar ID     : {calendar_id}")
print(f"Deleting from   : {time_min.strftime('%Y-%m-%d')} to {(time_max - timedelta(days=1)).strftime('%Y-%m-%d')}")
print()

# Count events in the window first
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
    exit(0)

print(f"Found {total} event(s) to delete.")
print()
confirm = input(f'Type "{CALENDAR_NAME}" to confirm deletion: ').strip()
if confirm != CALENDAR_NAME:
    print("Confirmation did not match. Aborting.")
    exit(1)

# Delete events in the window
print("Deleting...")
deleted = 0
page_token = None
while True:
    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        pageToken=page_token,
    ).execute()
    if not resp["items"]:
        break
    for event in resp["items"]:
        service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
        deleted += 1
        print(f"  Deleted {deleted}/{total}: {event.get('summary', '(no title)')}")
        time.sleep(0.1)
    # Don't use nextPageToken — re-fetch after deletions to avoid stale pages

print(f'\nDone. {deleted} event(s) deleted from "{calendar_name}".')
