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
| `TELEGRAM_BOT_TOKEN` | Optional. Telegram bot token (from [@BotFather](https://t.me/BotFather)). When set with `TELEGRAM_CHAT_ID`, you get a Telegram message when tickets are available. | — |
| `TELEGRAM_CHAT_ID` | Optional. Your Telegram chat ID (e.g. from [@userinfobot](https://t.me/userinfobot)). Used with `TELEGRAM_BOT_TOKEN` for notifications. | — |

### Telegram notifications (optional)

1. In Telegram, open [@BotFather](https://t.me/BotFather), send `/newbot`, and follow the prompts. Copy the **bot token** (e.g. `123456789:ABCdefGHI...`).
2. Get your **chat ID**: message [@userinfobot](https://t.me/userinfobot) and it will reply with your ID (a number).
3. In `.env`, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. When tickets are available, the app will send you a message with the movie, date, showtimes (if any), and the BookMyShow URL.

## Run

```bash
python -m src.main
```

The app will:

- Run one check immediately, then repeat every `CRON_INTERVAL_MINUTES`.
- Log whether tickets are available for the movie on the target date, and the BookMyShow URL when relevant.
- If `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set, send you a Telegram message when tickets become available.
- Keep running until you stop it with Ctrl+C (graceful shutdown).

## Project layout

- `src/main.py` – Entry point: loads config, starts the scheduler, runs the check job.
- `src/config.py` – Loads and validates settings from `.env`.
- `src/bms_crawler.py` – Playwright-based crawler: search movie, resolve event ID, open buytickets page for the date, parse availability.
- `src/telegram_notify.py` – Sends a message via the Telegram Bot API when tickets are available.

## Notes

- BookMyShow has no public API; this uses browser automation (Playwright) to search and open pages. The site may change structure over time; selectors might need updates.
- Use a reasonable interval (e.g. 1 minute) to avoid overloading the site. Read-only checks only; no booking is performed.
- You are responsible for complying with BookMyShow’s terms of service.
