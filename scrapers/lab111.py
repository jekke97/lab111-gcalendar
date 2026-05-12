"""Lab111 cinema programme scraper."""

import re
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from scrapers import CalendarEvent

_URL = "https://www.lab111.nl/programma/listview/"
_TZ  = "Europe/Amsterdam"
_AMS = ZoneInfo(_TZ)


def scrape(forecast_days: int = 14) -> list[CalendarEvent]:
    today   = datetime.now()
    soup    = BeautifulSoup(requests.get(_URL, timeout=15).content, "lxml")
    events: list[CalendarEvent] = []
    skipped = 0

    for day in range(forecast_days):
        for row in soup.find_all("tr", class_=f"day{day}")[1:]:
            try:
                urls = re.findall(r'https?://[^\s]+"', str(row))
                if len(urls) < 2:
                    raise ValueError(f"expected 2 URLs, found {len(urls)}")

                movie_url  = urls[1][:-1]
                ticket_url = str(row.find("a", class_="button tic")).split('"')[3]
                name       = row.find_all("a")[1].text
                s_time     = row.find_all("a")[0].text
                lab        = row.find("span").text
                info_url   = row.find_all("a")[1]["href"]

                dur_text = BeautifulSoup(
                    requests.get(movie_url, timeout=10).content, "lxml"
                ).find_all("ul", class_="speelduur")[0].text
                dur_h, dur_m = [int(x) for x in re.findall(r"\d+", dur_text)]

                sh, sm = [int(x) for x in s_time.split(":")]
                start  = (datetime(today.year, today.month, today.day, sh, sm)
                          + timedelta(days=day)).replace(tzinfo=_AMS)
                end    = start + timedelta(hours=dur_h, minutes=dur_m)

                events.append(CalendarEvent(
                    title       = name,
                    start       = start,
                    end         = end,
                    location    = lab,
                    description = f'<a href="{ticket_url}">Ticket</a>\n<a href="{info_url}">Description</a>',
                    uid         = ticket_url,
                    timezone    = _TZ,
                ))
            except Exception as e:
                print(f"  Skipping entry on day {day}: {e}")
                skipped += 1

        print(f"Day {day + 1} scraped.")

    print(f"Scraped {len(events)} events ({skipped} skipped).")
    return events
