# Track BMS – BookMyShow ticket availability crawler

A Python app that runs on a schedule (default: every 1 minute), crawls [BookMyShow](https://in.bookmyshow.com), searches for a given movie, and checks whether tickets are available for a specific date in a chosen city. It runs until you stop it and logs when tickets are available or not.

## Requirements

- Python 3.10+
- Chromium (installed via Playwright)

## Setup

1. **Clone and enter the project**
   ```bash
   cd track-bms
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set the variables as needed (see below).

## Configuration (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `CRON_INTERVAL_MINUTES` | Minutes between each check (minimum 1). | `1` |
| `BMS_CITY` | BookMyShow city slug (e.g. `mumbai`, `delhi-ncr`, `bengaluru`). | `bengaluru` |
| `MOVIE_NAME` | Movie name to search on BookMyShow. | `Dhurandhar The Revenge` |
| `TARGET_DATE` | Date to check for availability in `YYYY-MM-DD` format. | `2026-03-19` |
| `BMS_EVENT_ID` | Optional. Event ID from the movie’s buytickets URL (e.g. `ET00478890`). If set, the crawler skips search and opens the buytickets page directly. | — |
| `BMS_MOVIE_SLUG` | Optional. Movie slug for the URL when using `BMS_EVENT_ID` (e.g. `dhurandhar-the-revenge`). If omitted but `BMS_EVENT_ID` is set, derived from `MOVIE_NAME`. | — |
| `SLACK_WEBHOOK_URL` | Optional. Slack Incoming Webhook URL. When set, the app posts to that channel when tickets are available. | — |

### Slack notifications (optional)

1. In Slack: **Apps** → **Incoming Webhooks** (or create one at [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)). Add to your workspace and pick the channel (e.g. a private channel or #general).
2. Copy the **Webhook URL** (e.g. `https://hooks.slack.com/services/T00/B00/xxx`).
3. In `.env`, set `SLACK_WEBHOOK_URL` to that URL. When tickets are available, the app will post a message with the movie, date, showtimes (if any), and a link to BookMyShow.

## Run

```bash
python -m src.main
```

The app will:

- Run one check immediately, then repeat every `CRON_INTERVAL_MINUTES`.
- Log whether tickets are available for the movie on the target date, and the BookMyShow URL when relevant.
- If `SLACK_WEBHOOK_URL` is set, post a message to that Slack channel when tickets become available.
- Keep running until you stop it with Ctrl+C (graceful shutdown).

## Project layout

- `src/main.py` – Entry point: loads config, starts the scheduler, runs the check job.
- `src/config.py` – Loads and validates settings from `.env`.
- `src/bms_crawler.py` – Playwright-based crawler: search movie, resolve event ID, open buytickets page for the date, parse availability.
- `src/slack_notify.py` – Sends a message to Slack via an Incoming Webhook when tickets are available.

## Notes

- BookMyShow has no public API; this uses browser automation (Playwright) to search and open pages. The site may change structure over time; selectors might need updates.
- Use a reasonable interval (e.g. 1 minute) to avoid overloading the site. Read-only checks only; no booking is performed.
- You are responsible for complying with BookMyShow’s terms of service.
