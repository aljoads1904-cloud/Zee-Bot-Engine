"""
The Funnel Engine — orchestrates all 5 stages of the Phantom AI closer.
This is the decision brain that processes every incoming Telegram message.
"""

import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    STAGE_NEW, STAGE_IDENTITY, STAGE_CHOICE, STAGE_VSL, STAGE_CLOSE,
    STATUS_MANUAL, STATUS_ACTIVE, STATUS_CLOSED,
    AHAM_TELEGRAM_ID
)
from core.sheets import (
    find_lead, create_lead, update_lead,
    append_conversation, get_conversation_history
)
from core.telegram_api import send_message, send_inline_keyboard
from core.ai_engine import (
    generate_response, check_flags,
    msg_greeting, msg_choice, msg_vsl, msg_nudge
)

logger = logging.getLogger(__name__)


def alert_aham(message: str):
    """Send an urgent alert to Aham's Telegram."""
    send_message(
        AHAM_TELEGRAM_ID,
        f"🚨 *PHANTOM AI ALERT*\n\n{message}",
        typing=False
    )


def process_message(telegram_id: str, username: str, text: str) -> str | None:
    """
    Main entry point for every incoming message.
    Returns the reply text sent (or None if no reply).
    """
    text = (text or "").strip()
    lower = text.lower()

    # ── 1. Find or create lead ────────────────────────────────
    lead = find_lead(telegram_id)
    if not lead:
        lead = create_lead(telegram_id, username)

    # ── 2. GATEKEEPER — hard stop if manual mode ──────────────
    if lead.get("status") == STATUS_MANUAL:
        logger.info(f"[GATE] Lead {telegram_id} is MANUAL — stopping flow.")
        return None

    stage   = lead.get("stage", STAGE_NEW)
    name    = lead.get("name", "")
    history = get_conversation_history(telegram_id)

    # Record inbound message
    append_conversation(telegram_id, "user", text)
    update_lead(telegram_id, {"last_message": text, "status": STATUS_ACTIVE})

    # ── 3. STAGE 5 — READY keyword triggers close anytime ─────
    if "ready" in lower:
        update_lead(telegram_id, {"stage": STAGE_CLOSE})
        reply = generate_response(
            stage=STAGE_CLOSE,
            lead_name=name,
            user_message=text,
            history=history,
            is_close=True
        )
        _send_and_flag(telegram_id, reply, lead, history)
        return reply

    # ── 4. /start command — Stage 1: Ask for name ─────────────
    if text.startswith("/start"):
        update_lead(telegram_id, {"stage": STAGE_IDENTITY})
        reply = msg_greeting()
        send_message(telegram_id, reply)
        append_conversation(telegram_id, "assistant", reply)
        return reply

    # ── 5. Stage 1 → Collect name ─────────────────────────────
    if stage == STAGE_IDENTITY:
        # Treat any short single-word response as name
        if len(text.split()) <= 3 and len(text) < 50 and not text.startswith("/"):
            captured_name = text.split()[0].capitalize()
            update_lead(telegram_id, {"name": captured_name, "stage": STAGE_CHOICE})
            reply = msg_choice(captured_name)
            send_message(telegram_id, reply)
            append_conversation(telegram_id, "assistant", reply)
            return reply
        else:
            # AI handles unexpected input
            reply = generate_response(STAGE_IDENTITY, name, text, history)
            _send_and_flag(telegram_id, reply, lead, history)
            return reply

    # ── 6. Stage 2 → Free or Paid choice ─────────────────────
    if stage == STAGE_CHOICE:
        if "free" in lower:
            update_lead(telegram_id, {"choice": "free", "stage": STAGE_VSL, "vsl_sent": "yes"})
            reply = msg_vsl(name, "free")
            send_message(telegram_id, reply)
            append_conversation(telegram_id, "assistant", reply)
            return reply

        elif any(w in lower for w in ["paid", "premium", "pay"]):
            update_lead(telegram_id, {"choice": "paid", "stage": STAGE_VSL, "vsl_sent": "yes"})
            reply = msg_vsl(name, "paid")
            send_message(telegram_id, reply)
            append_conversation(telegram_id, "assistant", reply)
            return reply

        else:
            # Lead is asking something else — AI handles it
            reply = generate_response(STAGE_CHOICE, name, text, history)
            _send_and_flag(telegram_id, reply, lead, history)
            return reply

    # ── 7. Stage 3/4/5 — AI-driven conversation ───────────────
    reply = generate_response(stage, name, text, history)
    _send_and_flag(telegram_id, reply, lead, history)
    return reply


def _send_and_flag(telegram_id: str, reply: str, lead: dict, history: list):
    """Send a reply and check for escalation flags."""
    send_message(telegram_id, reply)
    append_conversation(telegram_id, "assistant", reply)

    human_needed, knowledge_gap = check_flags(reply)

    if human_needed or knowledge_gap:
        flag_type = "#HUMAN_NEEDED" if human_needed else "#KNOWLEDGE_GAP"
        name = lead.get("name", "Unknown")
        username = lead.get("username", "no_username")
        tid = lead.get("telegram_id", "?")

        alert_aham(
            f"*{flag_type}*\n\n"
            f"Lead: {name} (@{username})\n"
            f"Telegram ID: `{tid}`\n\n"
            f"*Last message:* {lead.get('last_message', '')}\n\n"
            f"*Zee's response:*\n{reply[:300]}..."
        )

        if human_needed:
            # Auto-escalate to manual mode
            update_lead(telegram_id, {"status": STATUS_MANUAL, "notes": "escalated by AI"})
