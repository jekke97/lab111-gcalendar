"""MTGO Pauper + Dutch Pauper League → Google Calendar sync."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import igor
igor.load_env()

from scrapers.mtgo import scrape as scrape_mtgo
from scrapers.dpl  import scrape as scrape_dpl

TZ = "Europe/Rome"
DEFAULT_FORECAST = 60


def main() -> None:
    local     = ZoneInfo(TZ)
    win_start = datetime.now(local).replace(hour=0, minute=0, second=0, microsecond=0)
    # Wide enough to cover all hardcoded DPL 2026 events
    win_end   = datetime(2026, 12, 31, 23, 59, 59, tzinfo=local)

    events = scrape_mtgo(days=DEFAULT_FORECAST, tz=TZ) + scrape_dpl(tz=TZ)

    igor.run(
        events, "Pauper Tournaments", win_start, win_end,
        message=lambda a, r: f"*Pauper Tournaments* — {a} added, {r} removed. They stir, master.\n— Eye-gor",
    )


if __name__ == "__main__":
    with igor.notify_on_error("Pauper Tournaments"):
        main()
