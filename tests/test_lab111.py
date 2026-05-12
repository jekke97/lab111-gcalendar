"""Tests for fragile points in scrapers/lab111.py."""

import re
import requests
from unittest.mock import MagicMock, patch

import pytest

from scrapers.lab111 import scrape


# ── minimal HTML fixtures ─────────────────────────────────────────────────────

_PROGRAMME_HTML = """
<html><body><table>
  <tr class="day0"><th>Header row — skipped by scraper</th></tr>
  <tr class="day0">
    <td><a href="https://www.lab111.nl/screening/20250112-200/">20:00</a></td>
    <td><a href="https://www.lab111.nl/films/test-film/">Test Film</a></td>
    <td><span>Lab 1</span></td>
    <td><a class="button tic" href="https://tickets.lab111.nl/event/999/">Tickets</a></td>
  </tr>
</table></body></html>
"""

_MOVIE_DETAIL_HTML = """
<html><body>
  <ul class="speelduur">1 uur 45 min</ul>
</body></html>
"""


def _resp(html: str) -> MagicMock:
    r = MagicMock()
    r.content = html.encode()
    return r


# ── tests ─────────────────────────────────────────────────────────────────────

def test_events_are_timezone_aware():
    """All returned start/end datetimes must carry tzinfo (fragile: datetime.now() base is naive)."""
    with patch("scrapers.lab111.requests.get", side_effect=[_resp(_PROGRAMME_HTML), _resp(_MOVIE_DETAIL_HTML)]):
        events = scrape(forecast_days=1)

    assert events, "expected at least one event from valid fixture HTML"
    for ev in events:
        assert ev.start.tzinfo is not None, f"start of '{ev.title}' has no tzinfo"
        assert ev.end.tzinfo is not None,   f"end of '{ev.title}' has no tzinfo"


def test_description_hrefs_are_quoted():
    """href attributes in the description must be quoted (bug: was href=url instead of href=\"url\")."""
    with patch("scrapers.lab111.requests.get", side_effect=[_resp(_PROGRAMME_HTML), _resp(_MOVIE_DETAIL_HTML)]):
        events = scrape(forecast_days=1)

    assert events
    for ev in events:
        bare = re.findall(r'href=[^"\s>]', ev.description)
        assert not bare, f"unquoted href in description: {ev.description!r}"


def test_row_with_no_urls_is_skipped():
    """A row containing no URLs raises ValueError internally and is skipped; scrape() must not crash."""
    no_url_html = """
    <html><body><table>
      <tr class="day0"><th>Header</th></tr>
      <tr class="day0"><td>20:00</td><td>Some Film</td><td><span>Lab 1</span></td></tr>
    </table></body></html>
    """
    with patch("scrapers.lab111.requests.get", return_value=_resp(no_url_html)):
        events = scrape(forecast_days=1)

    assert events == [], "row with no URLs should be skipped, not raise"


def test_row_with_broken_dom_is_skipped():
    """A row whose DOM structure doesn't match expectations is skipped; scrape() must not crash.

    Covers: positional find_all("a")[n] and str(row.find(...)).split('"')[3] failures.
    """
    broken_html = """
    <html><body><table>
      <tr class="day0"><th>Header</th></tr>
      <tr class="day0">
        <td data-a="https://www.lab111.nl/screening/1/"
            data-b="https://www.lab111.nl/films/x/">no real anchor elements here</td>
      </tr>
    </table></body></html>
    """
    with patch("scrapers.lab111.requests.get", return_value=_resp(broken_html)):
        events = scrape(forecast_days=1)

    assert events == [], "row with broken DOM should be skipped, not raise"


def test_movie_page_fetch_failure_is_skipped():
    """A network error on the per-movie detail fetch must skip that event, not crash scrape()."""
    with patch(
        "scrapers.lab111.requests.get",
        side_effect=[_resp(_PROGRAMME_HTML), requests.exceptions.ConnectionError("timeout")],
    ):
        events = scrape(forecast_days=1)

    assert events == [], "event whose detail page is unreachable should be skipped"
