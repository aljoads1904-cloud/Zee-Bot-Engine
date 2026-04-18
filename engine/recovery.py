"""
Recovery Engine — The 21-Day Aggressive Follow-up Machine.
Runs on a daily schedule. Scans leads and fires follow-ups.

LOGIC:
  - New leads with no response in 2h → short nudge
  - New/Active leads at Stage 1/2 silent for 24h → Hail Mary VSL
  - Leads in follow-up window → 21-day drip sequence
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    NUDGE_HOURS, VSL_HAILMARY_HOURS, FOLLOWUP_DAYS,
    STAGE_IDENTITY, STAGE_CHOICE, STAGE_VSL,
    STATUS_ACTIVE, STATUS_NEW, STATUS_MANUAL, STATUS_LOST,
    AHAM_TELEGRAM_ID
)
from core.sheets import get_all_leads, update_lead, append_conversation, log_followup
from core.telegram_api import send_message
from core.ai_engine import msg_nudge, msg_hailmary, msg_vsl, generate_response

logger = logging.getLogger(__name__)


# ─── 21-DAY MESSAGE SEQUENCE ──────────────────────────────────
FOLLOWUP_SEQUENCE = {
    1:  "Hey {name} 👋 Just making sure you got everything set up with Phantom AI. Any questions?",
    2:  "{name}, our AI made 3 profitable signals today 📈 — your slot is still open. Type READY to activate.",
    3:  "Quick one {name} — what's stopping you? Let me know and I'll sort it out for you personally 💬",
    4:  "🔥 {name}! New Phantom AI update just dropped. Premium users are seeing insane results this week.",
    5:  "{name}, I pulled your profile — you're a perfect fit for our Premium tier. Want me to hold it for you?",
    6:  "The free tier is getting results. Paid tier is getting *life-changing* results 💎 Which do you want, {name}?",
    7:  "One week check-in ⏰ {name} — most people who start this week hit their first win within 14 days.",
    9:  "Still thinking it over? {name}, here's what I'll do — I'll walk you through the setup personally. Just say GO.",
    11: "🚨 {name} — we're closing this round's applications in 48 hours. After that, waitlist only.",
    13: "Real talk, {name} — I don't want to see you miss this. 3 people from our last cohort already cashed out.",
    15: "Halfway through our activation window {name} — you're running out of time to join this round.",
    17: "Final push {name} 🎯 — I've fought to keep your slot open. Say READY and let's do this.",
    19: "This is almost it {name}. Closing your slot tomorrow unless you respond. Don't ghost me 🙏",
    21: "Last message from me, {name}. Your slot expires today. If you want back in — just say so. Otherwise, take care! 🤝",
}


def _hours_since(ts_str: str) -> float:
    """Returns hours since the given ISO timestamp."""
    if not ts_str:
        return 9999
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    except ValueError:
        return 9999


def run_recovery_scan():
    """Main recovery scanner — runs daily. Processes all active/new leads."""
    logger.info("🔄 Recovery scan starting...")
    leads = get_all_leads()
    processed = 0

    for lead in leads:
        tid     = lead.get("telegram_id", "")
        name    = lead.get("name", "friend")
        stage   = lead.get("stage", "new")
        status  = lead.get("status", "new")
        vsl_sent = lead.get("vsl_sent", "no")
        last_ts  = lead.get("last_contact_ts", "")

        if not tid:
            continue

        # Skip leads in manual or closed/done states
        if status in (STATUS_MANUAL, "closed", "done"):
            continue

        hours_silent = _hours_since(last_ts)
        followup_day = int(lead.get("followup_day", "0") or "0")

        # ── STAGE 1/2: Hail Mary after 24h silence ──────────────
        if stage in (STAGE_IDENTITY, STAGE_CHOICE) and hours_silent >= VSL_HAILMARY_HOURS and vsl_sent == "no":
            logger.info(f"[HAILMARY] Sending Hail Mary VSL to {tid} ({name})")
            reply = msg_hailmary(name)
            send_message(tid, reply)
            append_conversation(tid, "assistant", reply)
            update_lead(tid, {
                "stage": STAGE_VSL,
                "vsl_sent": "yes",
                "notes": f"Hail Mary VSL sent at {datetime.now(timezone.utc).isoformat()}"
            })
            processed += 1
            continue

        # ── NUDGE: 2h silence on any active stage ────────────────
        nudge_count = int(lead.get("nudge_count", "0") or "0")
        last_sent   = lead.get("followup_last_sent", "")
        hours_since_nudge = _hours_since(last_sent) if last_sent else hours_silent

        if hours_silent >= NUDGE_HOURS and hours_since_nudge >= NUDGE_HOURS and nudge_count < 4:
            logger.info(f"[NUDGE] Nudging {tid} ({name}) — nudge #{nudge_count + 1}")
            nudge_msg = msg_nudge(name, nudge_count + 1)
            send_message(tid, nudge_msg)
            append_conversation(tid, "assistant", nudge_msg)
            update_lead(tid, {
                "nudge_count": str(nudge_count + 1),
                "followup_last_sent": datetime.now(timezone.utc).isoformat()
            })
            processed += 1
            continue

        # ── 21-DAY DRIP SEQUENCE ──────────────────────────────────
        if followup_day < FOLLOWUP_DAYS:
            next_day = followup_day + 1
            if next_day in FOLLOWUP_SEQUENCE:
                msg_template = FOLLOWUP_SEQUENCE[next_day]
                msg = msg_template.format(name=name or "friend")
                logger.info(f"[DRIP] Day {next_day} follow-up to {tid} ({name})")
                send_message(tid, msg)
                append_conversation(tid, "assistant", msg)
                update_lead(tid, {
                    "followup_day": str(next_day),
                    "followup_last_sent": datetime.now(timezone.utc).isoformat()
                })
                log_followup(tid, name, next_day, msg)
                processed += 1

            # If day 21 reached and still no close
            if next_day >= FOLLOWUP_DAYS:
                update_lead(tid, {"status": STATUS_LOST, "notes": "21-day sequence exhausted"})

    logger.info(f"✅ Recovery scan complete. Processed {processed} leads.")
    return processed


def run_nudge_scan():
    """Fast scan for 2-hour nudges only. Can run hourly."""
    from core.sheets import get_leads_needing_nudge
    leads = get_leads_needing_nudge(hours=NUDGE_HOURS)
    for lead in leads:
        tid   = lead.get("telegram_id", "")
        name  = lead.get("name", "friend")
        count = int(lead.get("nudge_count", "0") or "0")
        if count >= 4:
            continue
        nudge_msg = msg_nudge(name, count + 1)
        send_message(tid, nudge_msg)
        append_conversation(tid, "assistant", nudge_msg)
        update_lead(tid, {
            "nudge_count": str(count + 1),
            "followup_last_sent": datetime.now(timezone.utc).isoformat()
        })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_recovery_scan()
