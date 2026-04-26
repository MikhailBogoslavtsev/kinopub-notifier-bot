# KinoPub Notifier Bot

Simple Python bot that checks KinoPub for newly added titles from the last 7 days and sends them to Telegram.

## Features

- Uses KinoPub API: `https://api.service-kp.com`
- Authenticates with `KINOPUB_TOKEN`
- Fetches recent titles (last 7 days)
- Filters by:
  - `FILTER_YEAR` (minimum year)
  - `FILTER_TYPE` (`movie`, `serial`, or `all`)
- Sends formatted Telegram messages with:
  - title
  - year
  - rating
  - short description
  - link to `kino.pub`
- Sends nothing if no matching new content is found

## Project Files

- `main.py` — bot logic
- `requirements.txt` — Python dependencies
- `.env.example` — environment variable template
- `.github/workflows/notify.yml` — scheduled GitHub Actions workflow

## Local Setup

1. Create and activate a virtual environment (optional but recommended):

   - macOS/Linux:
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`

2. Install dependencies:

   - `pip install -r requirements.txt`

3. Create your env file:

   - `cp .env.example .env`

4. Fill `.env` values:

   - `KINOPUB_TOKEN` — your KinoPub access token
   - `TELEGRAM_BOT_TOKEN` — your Telegram bot token
   - `TELEGRAM_CHAT_ID` — target chat ID
   - `FILTER_YEAR` — minimum release year (example: `2024`)
   - `FILTER_TYPE` — `movie`, `serial`, or `all`

5. Run:

   - `python main.py`

## GitHub Actions Setup

The workflow runs:

- every Monday at 09:00 UTC
- manually via **Run workflow** (`workflow_dispatch`)

Add these repository secrets in GitHub:

- `KINOPUB_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FILTER_YEAR`
- `FILTER_TYPE`

After adding secrets, workflow file `.github/workflows/notify.yml` will run automatically on schedule.