"""Send a message to Slack via Incoming Webhook when tickets are available."""

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def send_message(webhook_url: str, text: str) -> bool:
    """
    POST a text message to a Slack Incoming Webhook.
    Returns True on success, False on failure (logs the error).
    """
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.warning("Slack webhook returned status %s", resp.status)
                return False
            return True
    except urllib.error.HTTPError as e:
        logger.warning("Slack send failed: %s %s", e.code, e.read().decode())
        return False
    except Exception as e:
        logger.warning("Slack send failed: %s", e)
        return False


def notify_tickets_available(
    webhook_url: str,
    movie_name: str,
    target_date_str: str,
    message: str,
    showtimes: list[str],
    movie_url: str | None,
    theatres: list[str] | None = None,
    preferred_matches: list[str] | None = None,
    show_types: list[str] | None = None,
    theatre_show_types: dict[str, list[str]] | None = None,
) -> bool:
    """Build a notification message and send it to Slack."""
    lines = [
        ":ticket: *Tickets available!*",
        "",
        f"*Movie:* {movie_name}",
        f"*Date:* {target_date_str}",
        "",
        message,
    ]
    if preferred_matches:
        lines.append("")
        lines.append("*Preferred location(s) available:*")
        for t in preferred_matches:
            lines.append(f"• {t}")
    if theatre_show_types:
        lines.append("")
        lines.append("*Theatres & show types:*")
        for t in list(theatre_show_types.keys())[:30]:
            types_str = ", ".join(theatre_show_types[t]) if theatre_show_types[t] else "—"
            lines.append(f"• {t}: {types_str}")
        if len(theatre_show_types) > 30:
            lines.append(f"… and {len(theatre_show_types) - 30} more")
    elif show_types:
        lines.append("")
        lines.append("*Show types:* " + ", ".join(show_types))
    if showtimes:
        lines.append("")
        lines.append("Showtimes / options: " + ", ".join(showtimes[:10]))
    if theatres and not theatre_show_types:
        lines.append("")
        lines.append("*Theatres:*")
        for t in theatres[:30]:
            lines.append(f"• {t}")
        if len(theatres) > 30:
            lines.append(f"… and {len(theatres) - 30} more")
    if movie_url:
        lines.append("")
        lines.append(f"<{movie_url}|Book on BookMyShow>")
    text = "\n".join(lines)
    return send_message(webhook_url, text)
