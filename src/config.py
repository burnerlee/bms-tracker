"""Load and validate configuration from .env."""

import os
import re
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

DEFAULT_INTERVAL_MINUTES = 1
DEFAULT_CITY = "bengaluru"
DEFAULT_MOVIE_NAME = "Dhurandhar The Revenge"
DEFAULT_TARGET_DATE = "2026-03-19"


def get_cron_interval_minutes() -> int:
    raw = os.getenv("CRON_INTERVAL_MINUTES", str(DEFAULT_INTERVAL_MINUTES))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(
            f"CRON_INTERVAL_MINUTES must be an integer, got: {raw!r}"
        ) from None
    if value < 1:
        raise ValueError(
            f"CRON_INTERVAL_MINUTES must be at least 1, got: {value}"
        )
    return value


def get_bms_city() -> str:
    value = os.getenv("BMS_CITY", DEFAULT_CITY).strip()
    if not value:
        raise ValueError("BMS_CITY must be non-empty")
    return value


def get_movie_name() -> str:
    value = os.getenv("MOVIE_NAME", DEFAULT_MOVIE_NAME).strip()
    if not value:
        raise ValueError("MOVIE_NAME must be non-empty")
    return value


def get_bms_event_id() -> str | None:
    """Optional: skip search and use this event ID (e.g. ET00478890)."""
    value = os.getenv("BMS_EVENT_ID", "").strip()
    return value or None


def get_bms_movie_slug() -> str | None:
    """Optional: movie slug for URL when using BMS_EVENT_ID (e.g. dhurandhar-the-revenge)."""
    value = os.getenv("BMS_MOVIE_SLUG", "").strip()
    return value or None


def get_slack_webhook_url() -> str | None:
    """Optional: Slack Incoming Webhook URL for availability notifications."""
    value = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    return value or None


def get_preferred_theatre_substrings() -> list[str]:
    """
    Substrings to match in theatre names (case-insensitive). Notifications are sent
    only when at least one theatre contains one of these. Comma-separated in env.
    Default: Koramangala, Vega City.
    """
    raw = os.getenv(
        "PREFERRED_THEATRE_SUBSTRINGS",
        "Koramangala,Vega City",
    ).strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def get_preferred_show_types() -> list[str]:
    """
    Show types (IMAX, GOLD, 2D, etc.) to filter notifications. When set, we only
    notify if at least one preferred theatre has at least one of these (substring
    match, case-insensitive). Comma-separated in env. Empty = no filter.
    """
    raw = os.getenv("PREFERRED_SHOW_TYPES", "").strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def get_target_date_str() -> str:
    """Return TARGET_DATE as YYYY-MM-DD for display."""
    raw = os.getenv("TARGET_DATE", DEFAULT_TARGET_DATE).strip()
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"TARGET_DATE must be YYYY-MM-DD, got: {raw!r}"
        ) from None
    return raw


def get_target_date_yyyymmdd() -> str:
    """Return TARGET_DATE as YYYYMMDD for BookMyShow URLs."""
    raw = os.getenv("TARGET_DATE", DEFAULT_TARGET_DATE).strip()
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"TARGET_DATE must be YYYY-MM-DD, got: {raw!r}"
        ) from None
    return parsed.strftime("%Y%m%d")


def _movie_name_to_slug(name: str) -> str:
    """Convert movie name to BMS-style slug (e.g. 'Dhurandhar The Revenge' -> 'dhurandhar-the-revenge')."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-") or "movie"


def load_config() -> dict:
    """Load and validate all config; raise on error."""
    event_id = get_bms_event_id()
    movie_slug = get_bms_movie_slug()
    movie_name = get_movie_name()
    if event_id and not movie_slug:
        movie_slug = _movie_name_to_slug(movie_name)
    return {
        "cron_interval_minutes": get_cron_interval_minutes(),
        "bms_city": get_bms_city(),
        "movie_name": movie_name,
        "target_date_str": get_target_date_str(),
        "target_date_yyyymmdd": get_target_date_yyyymmdd(),
        "bms_event_id": event_id,
        "bms_movie_slug": movie_slug,
        "slack_webhook_url": get_slack_webhook_url(),
        "preferred_theatre_substrings": get_preferred_theatre_substrings(),
        "preferred_show_types": get_preferred_show_types(),
    }
