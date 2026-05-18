"""Dutch Pauper League 2026 calendar + biweekly FNM."""

from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from scrapers import CalendarEvent

_TZ = "Europe/Amsterdam"

# (year, month, day, hour, minute, title, location)
_DPL_2026 = [
    (2026,  6,  4, 20, 0, "DPL Online Series #3",      "MTGO"),
    (2026,  6,  6, 10, 0, "DPL - 3° Leg – 2026",       "Pondok"),
    (2026,  7,  2, 20, 0, "DPL Online Series #4",      "MTGO"),
    (2026,  7,  4, 10, 0, "DPL - 4° Leg – 2026",       "Pondok"),
    (2026,  8,  6, 20, 0, "DPL Online Series #5",      "MTGO"),
    (2026,  8,  8, 10, 0, "DPL - 5° Leg – 2026",       "Pondok"),
    (2026,  9,  3, 20, 0, "DPL Online Series #6",      "MTGO"),
    (2026,  9,  5, 10, 0, "DPL - 6° Leg – 2026",       "Pondok"),
    (2026, 10,  1, 20, 0, "DPL Online Series #7",      "MTGO"),
    (2026, 10,  3, 10, 0, "DPL - 7° Leg – 2026",       "Pondok"),
    (2026, 11,  5, 20, 0, "DPL Online Series #8",      "MTGO"),
    (2026, 11,  7, 10, 0, "DPL - 8° Leg – 2026",       "Pondok"),
    (2026, 12, 12, 10, 0, "DPL - Invitational - 2026", "Amsterdam"),
]


def _fnm_events(tz: str, now: datetime) -> list[CalendarEvent]:
    """Biweekly FNM starting 2026-05-22, 19:30–23:30."""
    local = ZoneInfo(tz)
    events = []
    d = date(2026, 5, 22)
    while d <= date(2026, 12, 31):
        start = datetime(d.year, d.month, d.day, 19, 30, tzinfo=local)
        if start >= now:
            events.append(CalendarEvent(
                title="FNM",
                start=start,
                end=start + timedelta(hours=4),
                uid=f"fnm:{d.isoformat()}",
                timezone=tz,
            ))
        d += timedelta(weeks=2)
    return events


def scrape(tz: str = _TZ) -> list[CalendarEvent]:
    """Return all future DPL 2026 and FNM events."""
    local = ZoneInfo(tz)
    now = datetime.now(local)
    events = []
    for year, month, day, hour, minute, title, location in _DPL_2026:
        start = datetime(year, month, day, hour, minute, tzinfo=local)
        if start < now:
            continue
        duration = timedelta(hours=4) if location == "MTGO" else timedelta(hours=8)
        uid = f"dpl:{year:04d}{month:02d}{day:02d}T{hour:02d}{minute:02d}"
        events.append(CalendarEvent(
            title=title,
            start=start,
            end=start + duration,
            location=location,
            description='<a href="https://dutchpauperleague.nl">dutchpauperleague.nl</a>',
            uid=uid,
            timezone=tz,
        ))
    return events + _fnm_events(tz, now)
