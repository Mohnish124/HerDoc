"""Telegram Bot API client for HerDoc Emergency SOS alerts.

The bot token lives only in backend settings. Error messages and logs never
include the request URL (which embeds the token).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings

LOGGER = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_TIMEOUT_SECONDS = 10.0
TELEGRAM_MAX_MESSAGE_LEN = 4096


class TelegramError(Exception):
    """Raised when an alert cannot be delivered. Message is safe to log."""


class TelegramNotConfiguredError(TelegramError):
    """Raised when TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set."""


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.TELEGRAM_BOT_TOKEN.strip() and settings.TELEGRAM_CHAT_ID.strip())


def build_emergency_message(
    *,
    user_name: str,
    role: str,
    phone: str | None,
    facility_name: str | None,
    latitude: float | None,
    longitude: float | None,
    note: str | None,
    sent_at: datetime | None = None,
) -> str:
    sent_at = sent_at or datetime.now(timezone.utc)
    lines = [
        "🚨 HERDOC EMERGENCY SOS 🚨",
        "",
        f"From: {user_name} ({role})",
    ]
    if phone:
        lines.append(f"Phone: {phone}")
    if facility_name:
        lines.append(f"Facility: {facility_name}")
    lines.append(f"Time: {sent_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if latitude is not None and longitude is not None:
        lines.append(f"Location: {latitude:.6f}, {longitude:.6f}")
        lines.append(f"Map: https://maps.google.com/?q={latitude:.6f},{longitude:.6f}")
    else:
        lines.append("Location: not available")
    if note:
        lines.append(f"Note: {note}")
    return "\n".join(lines)[:TELEGRAM_MAX_MESSAGE_LEN]


def send_telegram_message(text: str) -> None:
    """Send plain text to the configured chat. Raises TelegramError on failure."""
    settings = get_settings()
    token = settings.TELEGRAM_BOT_TOKEN.strip()
    chat_id = settings.TELEGRAM_CHAT_ID.strip()
    if not token or not chat_id:
        raise TelegramNotConfiguredError("Telegram is not configured")

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    try:
        response = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=TELEGRAM_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        # Do not log str(exc): it may contain the URL with the bot token.
        LOGGER.error("Telegram request failed: %s", type(exc).__name__)
        raise TelegramError("Telegram request failed") from None

    if response.status_code != 200:
        LOGGER.error("Telegram API returned HTTP %s", response.status_code)
        raise TelegramError(f"Telegram API returned HTTP {response.status_code}")

    try:
        ok = bool(response.json().get("ok"))
    except ValueError:
        ok = False
    if not ok:
        LOGGER.error("Telegram API responded with ok=false")
        raise TelegramError("Telegram API rejected the message")


def send_emergency_alert(**kwargs) -> None:
    """Build and send an emergency alert. See build_emergency_message for args."""
    send_telegram_message(build_emergency_message(**kwargs))
