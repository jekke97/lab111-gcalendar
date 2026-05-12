"""Tests for fragile points in gcalendar.py."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import gcalendar
from scrapers import CalendarEvent


# ── helpers ───────────────────────────────────────────────────────────────────

_WIN_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
_WIN_END   = datetime(2025, 1, 2, tzinfo=timezone.utc)


def _ev(uid: str, start: datetime = None) -> CalendarEvent:
    start = start or datetime(2025, 1, 1, 20, 0, tzinfo=timezone.utc)
    return CalendarEvent(
        title="Test Event",
        start=start,
        end=start + timedelta(hours=2),
        uid=uid,
        timezone="UTC",
    )


def _service_with_calendar(cal_name: str, cal_id: str, existing_events: list = None) -> MagicMock:
    service = MagicMock()
    service.calendarList().list().execute.return_value = {
        "items": [{"summary": cal_name, "id": cal_id}]
    }
    service.events().list().execute.return_value = {"items": existing_events or []}
    return service


# ── tests ─────────────────────────────────────────────────────────────────────

def test_calendar_list_is_paginated():
    """_get_or_create_calendar must follow nextPageToken (bug: originally fetched only page 1)."""
    page1 = [{"summary": "other-cal",  "id": "other_id"}]
    page2 = [{"summary": "target-cal", "id": "target_id"}]

    service = MagicMock()
    service.calendarList().list().execute.side_effect = [
        {"items": page1, "nextPageToken": "tok1"},
        {"items": page2},
    ]

    cal_id = gcalendar._get_or_create_calendar(service, "target-cal")
    assert cal_id == "target_id", "calendar on page 2 must be found without creating a duplicate"


def test_calendar_not_found_is_created():
    """When the calendar genuinely doesn't exist on any page, a new one is created."""
    service = MagicMock()
    service.calendarList().list().execute.return_value = {"items": []}
    # Use attribute access (not call) to set up the return value without recording a spurious call
    service.calendars.return_value.insert.return_value.execute.return_value = {"id": "brand_new_id"}

    cal_id = gcalendar._get_or_create_calendar(service, "new-cal")
    assert cal_id == "brand_new_id"
    service.calendars.return_value.insert.assert_called_once_with(body={"summary": "new-cal"})


def test_api_error_propagates_from_sync():
    """A Google API error during sync() must propagate, not be silently swallowed.

    Without retry/backoff, a 429 or network error causes the whole sync to abort.
    Propagation ensures the failure is visible in logs and workflow output.
    """
    service = _service_with_calendar("test-cal", "cal1")
    service.events().insert().execute.side_effect = Exception("429 Too Many Requests")

    with pytest.raises(Exception, match="429"):
        gcalendar.sync([_ev("uid-new")], "test-cal", service, _WIN_START, _WIN_END)


def test_event_with_same_uid_not_updated():
    """Documents limitation: sync() never calls update/patch — a changed event keeps its old data.

    An event with the same UID but a different start time will be left as-is.
    No insert, no delete, no update is made.
    """
    uid = "uid-existing"
    existing_gcal = {
        "id": "gcal_event_id",
        "description": f"<!-- uid:{uid} -->",
    }

    service = _service_with_calendar("test-cal", "cal1", existing_events=[existing_gcal])

    new_start = datetime(2025, 1, 1, 22, 0, tzinfo=timezone.utc)  # time changed
    added, removed = gcalendar.sync(
        [_ev(uid, start=new_start)], "test-cal", service, _WIN_START, _WIN_END,
    )

    assert added == 0,   "event with matching UID must not be re-inserted"
    assert removed == 0, "event with matching UID must not be deleted"
    service.events.return_value.patch.assert_not_called()
    service.events.return_value.update.assert_not_called()
