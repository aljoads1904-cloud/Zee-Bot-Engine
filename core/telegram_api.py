"""
Telegram API wrapper with typing indicators and message sending.
"""

import time
import requests
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import TELEGRAM_API_URL, TYPING_DELAY_SECS


def send_typing(chat_id: int | str, duration: float = TYPING_DELAY_SECS):
    """Broadcast 'typing...' action for `duration` seconds."""
    requests.post(f"{TELEGRAM_API_URL}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    }, timeout=10)
    time.sleep(duration)


def _escape_markdown(text: str) -> str:
    """Escape special chars for Telegram's legacy Markdown to prevent parse errors."""
    # Escape underscores that aren't part of *bold* or _italic_ intentional formatting
    # Safest fix: switch all unintentional underscores in plain words
    import re
    # Only escape underscores NOT surrounded by spaces (i.e., in usernames/words)
    return re.sub(r'(?<!\*)\b_\b(?!\*)', r'\\_', text)


def send_message(chat_id: int | str, text: str, parse_mode: str = "HTML",
                 reply_markup: dict = None, typing: bool = True) -> dict:
    """
    Send a message with an optional 3-second typing indicator first.
    Supports chunking for messages > 4096 chars.
    """
    if typing:
        send_typing(chat_id)

    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    last_result = {}
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
        }
        if reply_markup and chunk == chunks[-1]:
            payload["reply_markup"] = reply_markup

        resp = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=15)
        last_result = resp.json()
        if len(chunks) > 1:
            time.sleep(0.5)  # brief gap between chunks

    return last_result


def send_inline_keyboard(chat_id: int | str, text: str, buttons: list[list[dict]]) -> dict:
    """Send a message with inline keyboard buttons."""
    return send_message(chat_id, text, reply_markup={
        "inline_keyboard": buttons
    })


def answer_callback(callback_query_id: str, text: str = ""):
    """Acknowledge an inline button press."""
    requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={
        "callback_query_id": callback_query_id,
        "text": text
    }, timeout=10)


def set_webhook(webhook_url: str) -> dict:
    """Register the webhook URL with Telegram."""
    resp = requests.post(f"{TELEGRAM_API_URL}/setWebhook", json={
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query"]
    }, timeout=15)
    return resp.json()


def get_webhook_info() -> dict:
    resp = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo", timeout=10)
    return resp.json()
