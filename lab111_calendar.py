print("Loading libraries...")
import re
import os
import sys
import time
import traceback
import requests
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Load .env if present
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

print("Acquiring secrets...")
LAB111_URL       = "https://www.lab111.nl/programma/listview/"
DEFAULT_FORECAST = 14
REFRESH_TOKEN    = os.environ.get("REFRESH_TOKEN", "")
CLIENT_ID        = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET    = os.environ.get("CLIENT_SECRET", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
print("Secrets acquired.")


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        print(f"Telegram notification failed: {e}")


def get_new_access_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "grant_type":    "refresh_token",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
    })
    return r.json()["access_token"] if r.ok else None


def get_credentials():
    access_token = get_new_access_token()
    if not access_token:
        print("Unable to get new access token.")
        exit(-1)
    return Credentials(access_token)


def check_lab(calendars):
    return any(cal["summary"] == "lab111" for cal in calendars["items"])


def create_event(show, today):
    tz               = ZoneInfo("Europe/Amsterdam").key
    start_h, start_m = [int(x) for x in show["s_time"].split(":")]
    dur_h, dur_m     = [int(x) for x in re.findall(r"\d+", show["duration"])]
    start_time       = datetime(today.year, today.month, today.day, start_h, start_m) + timedelta(days=show["day"])
    end_time         = start_time + timedelta(hours=dur_h, minutes=dur_m)

    return {
        "summary":     show["name"],
        "location":    show["lab"],
        "description": f"<a href={show['ticket']}>Ticket</a>\n<a href={show['info']}>Description</a>",
        "start":       {"dateTime": start_time.isoformat(), "timeZone": tz},
        "end":         {"dateTime": end_time.isoformat(),   "timeZone": tz},
    }


def main():
    # Interactive prompt locally; use default in CI (no TTY)
    if sys.stdin.isatty():
        raw      = input(f"Days to forecast [default {DEFAULT_FORECAST}]: ").strip()
        forecast = int(raw) if raw.isdigit() else DEFAULT_FORECAST
    else:
        forecast = DEFAULT_FORECAST
    print(f"Forecasting {forecast} days.")

    print("Acquiring credentials...")
    service = build("calendar", "v3", credentials=get_credentials())
    print("Credentials acquired.")
    today = datetime.now()

    # Scraping
    soup     = BeautifulSoup(requests.get(LAB111_URL).content, "lxml")
    program  = []
    skipped  = 0
    print("Scraping...")
    for day in range(forecast):
        for movie in soup.find_all("tr", class_=f"day{day}")[1:]:
            try:
                urls = re.findall(r'https?://[^\s]+"', str(movie))
                if len(urls) < 2:
                    raise ValueError(f"expected 2 URLs in row, found {len(urls)}")
                movie_url = urls[1][:-1]
                program.append({
                    "s_time":   movie.find_all("a")[0].text,
                    "duration": BeautifulSoup(requests.get(movie_url).content, "lxml").find_all("ul", class_="speelduur")[0].text,
                    "name":     movie.find_all("a")[1].text,
                    "day":      day,
                    "lab":      movie.find("span").text,
                    "ticket":   str(movie.find("a", class_="button tic")).split('"')[3],
                    "info":     movie.find_all("a")[1]["href"],
                })
            except Exception as e:
                print(f"  Skipping entry on day {day}: {e}")
                skipped += 1
        print(f"Day {day + 1} scraped.")
    print("Scraping done.")

    # Create calendar if needed
    calendars = service.calendarList().list().execute()
    if not check_lab(calendars):
        created     = service.calendars().insert(body={"summary": "lab111", "timeZone": "Europe/Amsterdam"}).execute()
        calendar_id = created["id"]
        print("Calendar created.")
    else:
        calendar_id = next(c["id"] for c in calendars["items"] if c["summary"] == "lab111")
        print("Calendar already exists.")

    # Fetch existing events in the forecast window; key them by ticket URL.
    # Use start of today (Amsterdam time) as timeMin so past events from today
    # are included and not duplicated on re-runs.
    amsterdam  = ZoneInfo("Europe/Amsterdam")
    day_start  = datetime.now(amsterdam).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end    = day_start + timedelta(days=forecast)

    existing = {}  # ticket_url -> event_id
    page_token = None
    while True:
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            pageToken=page_token,
        ).execute()
        for event in events["items"]:
            match = re.search(r"<a href=([^\s>]+)>Ticket</a>", event.get("description", ""))
            if match:
                existing[match.group(1)] = event["id"]
        page_token = events.get("nextPageToken")
        if not page_token:
            break
    print(f"Found {len(existing)} existing events in calendar.")

    program_tickets  = {show["ticket"] for show in program}
    existing_tickets = set(existing)

    # Delete events that were cancelled (in calendar but no longer on the website)
    removed = existing_tickets - program_tickets
    for ticket_url in removed:
        service.events().delete(calendarId=calendar_id, eventId=existing[ticket_url]).execute()
        time.sleep(0.3)
    if removed:
        print(f"Removed {len(removed)} cancelled events.")

    # Add only new events (not already in calendar)
    to_add = [show for show in program if show["ticket"] not in existing_tickets]
    print(f"Adding {len(to_add)} new events ({len(program) - len(to_add)} already exist)...")
    for show in to_add:
        service.events().insert(calendarId=calendar_id, body=create_event(show, today)).execute()
        time.sleep(0.3)
    print("Done!")

    return len(to_add), len(removed), skipped


if __name__ == "__main__":
    try:
        added, removed, skipped = main()
        send_telegram(
            f"✅ lab111 calendar updated\n"
            f"New events added: {added}\n"
            f"Cancelled events removed: {removed}\n"
            f"Entries skipped: {skipped}\n"
            f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    except Exception:
        send_telegram(
            f"❌ lab111 calendar crashed\n\n"
            f"{traceback.format_exc()}"
        )
        raise
