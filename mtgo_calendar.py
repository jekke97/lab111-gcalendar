"""MTGO Pauper schedule → Google Calendar sync."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import igor
igor.load_env()

from scrapers.mtgo import scrape

TZ = "Europe/Rome"


DEFAULT_FORECAST = 14


def main() -> None:
    events    = scrape(days=DEFAULT_FORECAST, tz=TZ)
    local     = ZoneInfo(TZ)
    win_start = datetime.now(local).replace(hour=0, minute=0, second=0, microsecond=0)
    win_end   = win_start + timedelta(days=DEFAULT_FORECAST)

    igor.run(
        events, "MTG Tournaments", win_start, win_end,
        message=lambda a, r: f"*MTGO Pauper* — {a} added, {r} removed. They stir, master.\n— Eye-gor",
    )


if __name__ == "__main__":
    with igor.notify_on_error("MTGO"):
        main()
