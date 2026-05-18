# Igor the Scraper

A modular calendar-sync bot with an Eye-gor personality. Scrapes event sources, syncs them to Google Calendar, and reports back via Telegram. Runs nightly via GitHub Actions.

Currently ships two scrapers:

| Scraper | Source | Calendar |
|---|---|---|
| **Lab111** | [lab111.nl](https://www.lab111.nl/programma/listview/) cinema programme | `lab111` |
| **Pauper Tournaments** | [mtgoupdate.com](https://mtgoupdate.com) + hardcoded DPL/FNM | `Pauper Tournaments` |

The **Pauper Tournaments** calendar combines three sources into one view:
- **MTGO** — online Pauper events (Prelims, Challenges) from mtgoupdate.com, rolling 60-day window
- **DPL** — Dutch Pauper League 2026 paper legs and online series at Pondok (Amsterdam) and on MTGO
- **FNM** — biweekly Friday Night Magic at 2 Klaveren (Amsterdam), 19:30–23:30

---

## How it works

Each scraper produces a list of `CalendarEvent` objects. The orchestrator (`igor.py`) hands them to `gcalendar.py`, which diffs them against the existing Google Calendar window and adds/removes as needed. A short Telegram message follows.

```
scrapers/lab111.py  ─┐
scrapers/mtgo.py    ─┤─→ igor.run() → gcalendar.sync() → Google Calendar
scrapers/dpl.py     ─┤
                     └─→ telegram.send() → Telegram
```

Deduplication is UID-based: every event carries a unique key embedded in its Google Calendar description as `<!-- uid:... -->`. On each sync, existing events are fetched, their UIDs extracted, and only the diff (new additions, cancellations) is applied. Nothing is touched twice.

---

## Project structure

```
igor.py                  — orchestrator: run(), notify_on_error(), load_env()
gcalendar.py             — Google Calendar integration (get_service, sync)
telegram.py              — Telegram notification wrapper
scrapers/
  __init__.py            — CalendarEvent dataclass
  lab111.py              — Lab111 cinema scraper
  mtgo.py                — MTGO Pauper schedule scraper (mtgoupdate.com)
  dpl.py                 — Dutch Pauper League 2026 + biweekly FNM (hardcoded)
lab111_calendar.py       — entry point: Lab111 → Google Calendar
pauper_calendar.py       — entry point: MTGO + DPL + FNM → "Pauper Tournaments"
tests/
  test_lab111.py         — tests for lab111 scraper fragile points
  test_gcalendar.py      — tests for gcalendar fragile points
get_token.py             — one-time OAuth setup: gets a refresh token and writes .env
get_chat_id.py           — one-time Telegram setup: finds your chat ID
clear_calendar.py        — utility: deletes events in a date window (lab111 or pauper)
requirements.txt         — Python dependencies
.github/workflows/
  lab111.yml             — combined scraper workflow (runs both scrapers nightly)
  tests.yml              — test workflow (runs on every push)
.env                     — local credentials (gitignored, never commit this)
```

---

## Adding a new scraper

1. Create `scrapers/yourname.py` with a `scrape()` function that returns `list[CalendarEvent]`
2. Create `yourname_calendar.py` as an entry point (copy `pauper_calendar.py` as a template)
3. Add a job to `.github/workflows/lab111.yml`

The `CalendarEvent` dataclass lives in `scrapers/__init__.py`. Set `uid` to something that uniquely identifies each occurrence — timestamp + event name is a reliable choice.

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd igor-the-scraper

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Requires Python 3.10+.

---

### 2. Google Cloud Console — create credentials

#### 2a. Create a project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown (top left) → **New Project**
3. Name it anything (e.g. `igor-scraper`) and click **Create**
4. Make sure your new project is selected

#### 2b. Enable the Google Calendar API

1. **APIs & Services → Library**
2. Search for **Google Calendar API** → **Enable**

#### 2c. Configure the OAuth consent screen

1. **APIs & Services → OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in app name, support email, developer contact email
4. Click **Save and Continue** through all steps — defaults are fine
5. On the **Test users** page, add your own Google account email

> **Why this matters:** Google won't let an unverified app request calendar access unless your account is listed as a test user. Skipping this step causes "Access blocked" during the OAuth flow.

#### 2d. Create OAuth 2.0 credentials

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Desktop app**
3. Click **Create**
4. Copy the **Client ID** and **Client Secret**

> If you lose the client secret, go back to Credentials → pencil icon → **Add new secret**.

---

### 3. Get an OAuth refresh token

```bash
python get_token.py
```

It will ask for your Client ID and Client Secret, open a browser for the OAuth flow, and write a `.env` file with `CLIENT_ID`, `CLIENT_SECRET`, and `REFRESH_TOKEN`.

> **"Google hasn't verified this app":** click **Advanced → Go to [app name] (unsafe)**. Expected for personal apps.

---

### 4. Telegram notifications (optional)

If you skip this, everything runs fine — no messages are sent.

#### 4a. Create a bot

1. Open Telegram → search **@BotFather** → send `/newbot`
2. Follow the prompts, copy the token BotFather gives you

#### 4b. Get your chat ID

1. Send any message to your new bot in Telegram
2. Run `python get_chat_id.py` and paste your token

#### 4c. Add to .env

```
TELEGRAM_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=<your chat id>
```

---

### 5. Final .env file

```
CLIENT_ID=<from Google Cloud Console>
CLIENT_SECRET=<from Google Cloud Console>
REFRESH_TOKEN=<written by get_token.py>
TELEGRAM_TOKEN=<from BotFather>
TELEGRAM_CHAT_ID=<from get_chat_id.py>
```

The `TELEGRAM_*` lines are optional.

---

## Running locally

**Lab111** (interactive — prompts for forecast window):
```bash
python lab111_calendar.py
```

**Pauper Tournaments** (syncs MTGO 60-day window + all DPL/FNM, no prompt):
```bash
python pauper_calendar.py
```

Both scripts load `.env` automatically, sync to Google Calendar, and send a Telegram message.

---

## GitHub Actions

Two workflows run automatically:

### `scrapers` (lab111.yml)

Triggers on push to `main`, every night at midnight UTC, and manually via `workflow_dispatch`.

Runs two parallel jobs — `lab111` and `pauper` — each on its own runner. If one fails, the other still runs and sends its own Telegram notification. Each job sends one short message:

- `*Lab111* — {n} added, {n} removed. What hump? — Eye-gor`
- `*Pauper Tournaments* — {n} added, {n} removed. They stir, master. — Eye-gor`

On error, `notify_on_error` catches the exception, sends a Telegram error report with a truncated traceback, and re-raises so the workflow job fails visibly.

### `tests` (tests.yml)

Triggers on every push. Runs `pytest tests/ -v` — no credentials needed, everything is mocked.

---

### Secrets required

Add these under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `REFRESH_TOKEN` | from `.env` |
| `CLIENT_ID` | from `.env` |
| `CLIENT_SECRET` | from `.env` |
| `TELEGRAM_TOKEN` | from `.env` (optional) |
| `TELEGRAM_CHAT_ID` | from `.env` (optional) |

> The refresh token does not expire as long as the script runs at least once every 6 months. If Google revokes it, re-run `get_token.py` and update the secret.

---

## Tests

```bash
pip install pytest
pytest tests/ -v
```

The test suite covers the fragile points in both scrapers and the calendar sync layer — no network calls, no credentials needed:

| Test | What it guards |
|---|---|
| `test_events_are_timezone_aware` | `datetime.now()` base is naive; all events must carry tzinfo |
| `test_description_hrefs_are_quoted` | href attributes must be `href="url"`, not `href=url` |
| `test_row_with_no_urls_is_skipped` | missing URLs in a row → ValueError → skip, no crash |
| `test_row_with_broken_dom_is_skipped` | unexpected DOM structure → skip, no crash |
| `test_movie_page_fetch_failure_is_skipped` | per-movie HTTP failure → skip, no crash |
| `test_calendar_list_is_paginated` | calendar on page 2 of the list must be found |
| `test_calendar_not_found_is_created` | missing calendar is created automatically |
| `test_api_error_propagates_from_sync` | Google API errors must not be silently swallowed |
| `test_event_with_same_uid_not_updated` | documents that sync adds/removes but never updates |

---

## Utility scripts

### Clear a calendar

```bash
python clear_calendar.py [lab111|pauper]
```

Deletes all events between yesterday and the end of next month from the chosen calendar. Useful for a clean resync. Shows what it found and asks you to confirm by typing the calendar name before deleting.

---

## Troubleshooting

**"Unable to get new access token"**
Your refresh token is invalid or expired. Re-run `get_token.py`.

**"Access blocked: This app's request is invalid"**
Your Google account is not listed as a test user. Go to **APIs & Services → OAuth consent screen → Test users** and add your email.

**Events keep getting duplicated**
The deduplication logic relies on UIDs embedded in event descriptions. If descriptions were corrupted by an older version of the script, run `clear_calendar.py` to wipe the window and let the next run rebuild cleanly.

**"No messages found" in get_chat_id.py**
Send at least one message to your bot in Telegram before running the script.

**Telegram message not arriving**
Confirm both `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are set. Verify the token is valid by opening `https://api.telegram.org/bot<TOKEN>/getMe` in a browser.
