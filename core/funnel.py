"""
The Funnel Engine — 5-stage Phantom AI closer pipeline.
Orchestrates all conversation logic using the Zee Master Brain rules.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    STAGE_NEW, STAGE_IDENTITY, STAGE_CHOICE, STAGE_VSL, STAGE_CLOSE,
    STATUS_MANUAL, STATUS_ACTIVE,
    AHAM_TELEGRAM_ID
)
from core.sheets import (
    find_lead, create_lead, update_lead,
    append_conversation, get_conversation_history
)
from core.telegram_api import send_message
from core.ai_engine import (
    generate_response, check_flags,
    msg_greeting, msg_choice,
    msg_vsl_free, msg_vsl_paid,
    msg_ready_response, msg_webinar_link
)

logger = logging.getLogger(__name__)


def alert_aham(flag: str, lead: dict, last_message: str, ai_reply: str = ""):
    """Send an urgent escalation alert to Aham's Telegram."""
    name      = lead.get("name", "Unknown")
    username  = lead.get("username", "")
    tid       = lead.get("telegram_id", "?")
    username_str = f"@{username}" if username else "no username"

    alert_text = (
        f"🚨 <b>PHANTOM AI ALERT</b>\n\n"
        f"<b>Flag:</b> <code>{flag}</code>\n"
        f"<b>Lead:</b> {name} ({username_str})\n"
        f"<b>Telegram ID:</b> <code>{tid}</code>\n\n"
        f"<b>Their message:</b> <i>{last_message}</i>\n\n"
    )
    if ai_reply:
        alert_text += f"<b>Zee's response:</b>\n{ai_reply[:300]}"

    send_message(AHAM_TELEGRAM_ID, alert_text, typing=False)


def process_message(telegram_id: str, username: str, text: str) -> str | None:
    """
    Main entry point for every incoming Telegram message.
    Returns the reply text (or None if silenced by MANUAL gatekeeper).
    """
    text  = (text or "").strip()
    lower = text.lower()

    # ── 1. FIND OR CREATE LEAD ────────────────────────────────────
    lead = find_lead(telegram_id)
    if not lead:
        lead = create_lead(telegram_id, username)

    # ── 2. GATEKEEPER — hard stop if status = manual ──────────────
    if lead.get("status") == STATUS_MANUAL:
        logger.info(f"[GATE] {telegram_id} is MANUAL — flow stopped.")
        return None

    stage  = lead.get("stage",  STAGE_NEW)
    name   = lead.get("name",   "")
    history = get_conversation_history(telegram_id)

    # Record inbound message to sheet + update last_message
    append_conversation(telegram_id, "user", text)
    update_lead(telegram_id, {"last_message": text, "status": STATUS_ACTIVE})
    # Refresh lead dict so _deliver has the current last_message
    lead = find_lead(telegram_id) or lead

    # ── 3. STAGE 5 — READY keyword triggers close at ANY stage ───
    if "ready" in lower:
        logger.info(f"[READY] {telegram_id} ({name}) triggered close sequence.")
        update_lead(telegram_id, {"stage": STAGE_CLOSE})

        # Master Brain: EXACT two-message close sequence
        reply_1 = msg_ready_response()
        send_message(telegram_id, reply_1)
        append_conversation(telegram_id, "assistant", reply_1)

        reply_2 = msg_webinar_link()
        send_message(telegram_id, reply_2)
        append_conversation(telegram_id, "assistant", reply_2)

        return reply_1  # return first for logging

    # ── 4. /start — Stage 1: High energy greeting, ask for name ──
    if text.startswith("/start"):
        update_lead(telegram_id, {"stage": STAGE_IDENTITY})
        reply = msg_greeting()
        send_message(telegram_id, reply)
        append_conversation(telegram_id, "assistant", reply)
        return reply

    # ── 4b. NEW leads who message without /start get greeting first ──
    if stage == STAGE_NEW:
        update_lead(telegram_id, {"stage": STAGE_IDENTITY})
        reply = msg_greeting()
        send_message(telegram_id, reply)
        append_conversation(telegram_id, "assistant", reply)
        return reply

    # ── 5. Stage 1 — Collect name ─────────────────────────────────
    if stage == STAGE_IDENTITY:
        # Accept any short response (1-3 words, <50 chars) as a name
        if 0 < len(text) < 50 and not text.startswith("/") and len(text.split()) <= 4:
            captured_name = text.split()[0].capitalize()
            update_lead(telegram_id, {
                "name":  captured_name,
                "stage": STAGE_CHOICE
            })
            reply = msg_choice(captured_name)
            send_message(telegram_id, reply)
            append_conversation(telegram_id, "assistant", reply)
            return reply
        else:
            # AI handles unexpected input at this stage
            reply = generate_response(STAGE_IDENTITY, name, text, history)
            _deliver(telegram_id, reply, lead)
            return reply

    # ── 6. Stage 2 — Free or Paid choice ─────────────────────────
    if stage == STAGE_CHOICE:
        if "free" in lower:
            update_lead(telegram_id, {
                "choice":   "free",
                "stage":    STAGE_VSL,
                "vsl_sent": "yes"
            })
            reply = msg_vsl_free(name)
            send_message(telegram_id, reply)
            append_conversation(telegram_id, "assistant", reply)
            return reply

        elif any(w in lower for w in ["paid", "premium", "pay", "pro"]):
            update_lead(telegram_id, {
                "choice":   "paid",
                "stage":    STAGE_VSL,
                "vsl_sent": "yes"
            })
            reply = msg_vsl_paid(name)
            send_message(telegram_id, reply)
            append_conversation(telegram_id, "assistant", reply)
            return reply

        else:
            # Objection / question at choice stage — AI handles using Master Brain
            reply = generate_response(STAGE_CHOICE, name, text, history)
            _deliver(telegram_id, reply, lead)
            return reply

    # ── 7. All other stages — AI-driven with Master Brain context ─
    reply = generate_response(stage, name, text, history)
    _deliver(telegram_id, reply, lead)
    return reply


def _deliver(telegram_id: str, reply: str, lead: dict):
    """Send reply, record it, and check for escalation flags."""
    send_message(telegram_id, reply)
    append_conversation(telegram_id, "assistant", reply)

    human_needed, knowledge_gap = check_flags(reply)

    if human_needed:
        logger.warning(f"[#HUMAN_NEEDED] Escalating lead {telegram_id}")
        alert_aham("#HUMAN_NEEDED", lead, lead.get("last_message", ""), reply)
        # Auto-escalate: stop the bot from responding further
        update_lead(telegram_id, {
            "status": STATUS_MANUAL,
            "notes":  "#HUMAN_NEEDED — escalated automatically"
        })

    elif knowledge_gap:
        logger.warning(f"[#KNOWLEDGE_GAP] Flag for lead {telegram_id}")
        alert_aham("#KNOWLEDGE_GAP", lead, lead.get("last_message", ""), reply)
        # Do NOT stop the bot — just alert Aham to update knowledge base
