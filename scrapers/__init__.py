from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalendarEvent:
    title: str
    start: datetime       # timezone-aware
    end: datetime         # timezone-aware
    location: str = ""
    description: str = "" # HTML allowed; Google Calendar renders it
    uid: str = ""         # deduplication key; unique per event
    timezone: str = "UTC" # IANA name matching start/end tzinfo
