"""Send a message via Telegram Bot API when tickets are available."""

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """
    Send a text message to the given chat via the Telegram Bot API.
    Returns True on success, False on failure (logs the error).
    """
    # Telegram expects chat_id as integer for user chats; strip and allow numeric string
    raw_id = (chat_id or "").strip()
    try:
        payload_chat_id = int(raw_id)
    except ValueError:
        payload_chat_id = raw_id  # e.g. @channelusername
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    body = json.dumps({"chat_id": payload_chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                logger.warning("Telegram API returned status %s", resp.status)
                return False
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        logger.warning("Telegram send failed: %s %s", e.code, err_body)
        if e.code == 400 and "chat not found" in err_body.lower():
            logger.warning(
                "Hint: Open the bot in Telegram (e.g. t.me/YourBot), send it a message, "
                "and use the numeric chat ID from @userinfobot (digits only)."
            )
        return False
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
        return False


def notify_tickets_available(
    bot_token: str,
    chat_id: str,
    movie_name: str,
    target_date_str: str,
    message: str,
    showtimes: list[str],
    movie_url: str | None,
) -> bool:
    """Build a notification message and send it via Telegram."""
    lines = [
        "🎟️ Tickets available!",
        "",
        f"Movie: {movie_name}",
        f"Date: {target_date_str}",
        "",
        message,
    ]
    if showtimes:
        lines.append("")
        lines.append("Showtimes / options: " + ", ".join(showtimes[:10]))
    if movie_url:
        lines.append("")
        lines.append(movie_url)
    text = "\n".join(lines)
    return send_message(bot_token, chat_id, text)
