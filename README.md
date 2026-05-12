# lab111-gcalendar

Automatically scrapes the [Lab111](https://www.lab111.nl/programma/listview/) cinema programme and syncs it to a dedicated Google Calendar. Runs nightly via GitHub Actions and sends a Telegram notification on success or failure.

---

## How it works

1. Scrapes the Lab111 listing page for the next N days (default: 14)
2. For each screening, fetches the individual film page to get the duration
3. Compares scraped screenings against existing Google Calendar events, using the ticket URL as a unique key
4. Adds new screenings, removes cancelled ones, leaves unchanged ones alone
5. Sends a Telegram message reporting what happened (or what went wrong)

---

## Project structure

```
lab111_calendar.py   — main script (scrape + sync)
get_token.py         — one-time OAuth setup: gets a refresh token and writes .env
get_chat_id.py       — one-time Telegram setup: finds your chat ID
clear_calendar.py    — utility: deletes events in a date window from the lab111 calendar
requirements.txt     — Python dependencies
.github/workflows/
  lab111.yml         — GitHub Actions workflow (runs nightly at midnight)
.env                 — local credentials (gitignored, never commit this)
secrets.txt          — local plaintext backup of credentials (gitignored)
```

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd lab111-gcalendar

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Requires Python 3.10 or later (`zoneinfo` is a standard library module from 3.9+, but 3.10+ is recommended).

---

### 2. Google Cloud Console — create credentials

This is the most involved part. You need a **CLIENT_ID** and **CLIENT_SECRET** from Google.

#### 2a. Create a project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown (top left) → **New Project**
3. Name it anything (e.g. `lab111-calendar`) and click **Create**
4. Make sure your new project is selected in the dropdown

#### 2b. Enable the Google Calendar API

1. In the left sidebar: **APIs & Services → Library**
2. Search for **Google Calendar API**
3. Click it → **Enable**

#### 2c. Configure the OAuth consent screen

This is required before you can create credentials.

1. **APIs & Services → OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in:
   - App name: anything (e.g. `lab111-calendar`)
   - User support email: your email
   - Developer contact email: your email
4. Click **Save and Continue** through the remaining steps (Scopes, Test users, Summary) — defaults are fine
5. On the **Test users** page, add your own Google account email. This is required while the app is in "testing" mode, which is permanently fine for personal use.

> **Why this matters:** Google won't let an unverified app request calendar access unless your account is listed as a test user. Skipping this step causes an "Access blocked" error during the OAuth flow.

#### 2d. Create OAuth 2.0 credentials

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Desktop app**
3. Name: anything (e.g. `lab111-local`)
4. Click **Create**
5. Copy the **Client ID** and **Client Secret** that appear — you'll need them in the next step

> **Note:** Google no longer lets you view the client secret after closing the dialog. If you lose it, go back to Credentials, click the pencil icon next to your client, and click **Add new secret**.

---

### 3. Get an OAuth refresh token

Run the setup script:

```bash
python get_token.py
```

It will:
1. Ask you to paste your **Client ID** and **Client Secret**
2. Open a browser tab → log in with your Google account → click **Allow**
3. Write a `.env` file with `CLIENT_ID`, `CLIENT_SECRET`, and `REFRESH_TOKEN`

> **Common issue — "Google hasn't verified this app":** Click **Advanced → Go to [app name] (unsafe)**. This is expected for personal/test-mode apps and is safe since you created the app yourself.

> **Common issue — browser doesn't open:** The script uses `localhost` as the redirect URI. If you're on a headless server, you'll need to copy the URL from the terminal and open it manually.

The `.env` file is gitignored and stays local. Never commit it.

---

### 4. Telegram notifications (optional)

If you skip this, the script runs fine — it just won't send any messages.

#### 4a. Create a bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a display name and a username (must end in `bot`, e.g. `lab111cal_bot`)
4. Copy the **token** BotFather gives you (looks like `7123456789:AAFabc...`)

#### 4b. Get your chat ID

1. In Telegram, find your new bot and send it any message (e.g. "hi")
2. Run:

```bash
python get_chat_id.py
```

3. Paste your bot token when prompted — it prints your `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`

#### 4c. Add to .env

Open `.env` and add:

```
TELEGRAM_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=<your chat id>
```

> **Common issue — "No messages found":** You must send a message to the bot *before* running `get_chat_id.py`. The Telegram API only returns a chat ID after the first message.

---

### 5. Final .env file

Your `.env` should look like this:

```
CLIENT_ID=<from Google Cloud Console>
CLIENT_SECRET=<from Google Cloud Console>
REFRESH_TOKEN=<written by get_token.py>
TELEGRAM_TOKEN=<from BotFather>
TELEGRAM_CHAT_ID=<from get_chat_id.py>
```

The script loads this file automatically at startup. The `TELEGRAM_*` lines are optional.

---

## Running locally

```bash
source venv/bin/activate
python lab111_calendar.py
```

You'll be prompted:

```
Days to forecast [default 14]:
```

Press Enter to use the default, or type a number. The script then scrapes, syncs, and sends a Telegram notification.

---

## GitHub Actions — automated nightly run

The workflow in `.github/workflows/lab111.yml` runs every night at midnight UTC and on every push to `main`.

To enable it, add your credentials as GitHub repository secrets:

1. Go to your repo on GitHub → **Settings → Secrets and variables → Actions**
2. Click **New repository secret** for each of the following:

| Secret name | Value |
|---|---|
| `REFRESH_TOKEN` | from your `.env` |
| `CLIENT_ID` | from your `.env` |
| `CLIENT_SECRET` | from your `.env` |
| `TELEGRAM_TOKEN` | from your `.env` (optional) |
| `TELEGRAM_CHAT_ID` | from your `.env` (optional) |

The workflow uses the default forecast of 14 days (no interactive prompt in CI).

> **Important:** The `REFRESH_TOKEN` does not expire as long as the script runs at least once every 6 months. If Google revokes it (e.g. you change your Google password, or the OAuth client goes unused for 6 months), re-run `get_token.py` locally to get a new one and update the GitHub secret.

---

## Utility scripts

### Clear the calendar

Deletes all events between yesterday and the end of next month from the `lab111` calendar. Useful for a clean resync.

```bash
python clear_calendar.py
```

The script shows you exactly what it found and asks you to type `lab111` before deleting anything. It will abort if it cannot find exactly one calendar named `lab111`.

---

## Troubleshooting

**"Unable to get new access token"**
Your refresh token is invalid or expired. Re-run `get_token.py` to get a new one.

**"Access blocked: This app's request is invalid"**
Your Google account is not listed as a test user on the OAuth consent screen. Go to **APIs & Services → OAuth consent screen → Test users** and add your email.

**Events keep getting duplicated**
The deduplication logic matches events by ticket URL. If the ticket URL in the calendar description was corrupted (e.g. from a previous version of the script), run `clear_calendar.py` to wipe the window and let the next run rebuild it cleanly.

**"No messages found" in get_chat_id.py**
You need to send at least one message to your bot in Telegram before the API returns a chat ID.

**Telegram message not arriving**
Check that `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are both set in `.env`. Confirm the bot token is correct by visiting `https://api.telegram.org/bot<TOKEN>/getMe` in a browser — it should return your bot's info as JSON.
