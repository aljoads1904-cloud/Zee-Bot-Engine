"""
Recovery Engine — The 21-Day Aggressive Follow-up Machine.
Language sourced directly from Zee_Master_Brain.pdf.

TIMELINE:
  Days 1-3:   Aggressive proof + results + FOMO
  Days 4-10:  Testimonials + slot depletion warnings
  Days 11-21: The Break-up ("giving your slot to the next person")
  Day 21:     Final message → mark as LOST

TRIGGERS:
  - 2h silence → Short & Sharp nudge (max 4x)
  - 24h silence at Stage 1/2 → Hail Mary VSL
  - Daily → advance drip day
"""

import os
import sys
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    NUDGE_HOURS, VSL_HAILMARY_HOURS, FOLLOWUP_DAYS,
    STAGE_IDENTITY, STAGE_CHOICE, STAGE_VSL,
    STATUS_ACTIVE, STATUS_NEW, STATUS_MANUAL, STATUS_LOST,
)
from core.sheets import get_all_leads, update_lead, append_conversation
from core.telegram_api import send_message
from core.ai_engine import msg_nudge, msg_hailmary

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  21-DAY MESSAGE SEQUENCE — Master Brain Language
#  Days 1-3:  Proof + FOMO
#  Days 4-10: Testimonials + Slot depletion
#  Days 11-21: The Break-up sequence
# ══════════════════════════════════════════════════════════════════

FOLLOWUP_SEQUENCE = {
    # ── DAYS 1-3: Aggressive proof + FOMO ─────────────────────
    1: (
        "hey {name} 👋 just checking you got the video?\n\n"
        "phantom AI hit 4 winning signals today. your slot is still open 🔥\n\n"
        "just say <b>READY</b> when you're set to activate."
    ),
    2: (
        "results from today 📈\n\n"
        "3 trades. all winners. phantom AI running clean.\n\n"
        "this is what you're sitting on the sidelines missing, {name}.\n\n"
        "what's stopping you? tell me."
    ),
    3: (
        "{name} — real talk.\n\n"
        "we had 6 new activations this week. all making moves.\n\n"
        "your spot is still here but i can't hold it forever.\n\n"
        "what's the ONE thing holding you back? i'll sort it."
    ),

    # ── DAYS 4-10: Testimonials + slot depletion ──────────────
    4: (
        "just heard from one of our guys — first week live, £340 profit.\n\n"
        "that's phantom AI doing its thing, {name}.\n\n"
        "your slot is still open. ⚡"
    ),
    5: (
        "{name} two more people activated yesterday.\n\n"
        "slots are going. once they're gone, you're on the waitlist.\n\n"
        "say <b>READY</b> to lock yours in now."
    ),
    6: (
        "📊 this week's numbers just came in.\n\n"
        "free tier users: 68% positive weeks.\n"
        "premium tier: 84% positive weeks.\n\n"
        "which side do you want to be on? free or premium?\n\n"
        "still got your spot, {name}."
    ),
    7: (
        "one week since we spoke {name}.\n\n"
        "most of the people who started the same time as you have already activated.\n\n"
        "don't let indecision cost you. slot is still yours — just say <b>READY</b>."
    ),
    8: (
        "testimonial just in 🗣️\n\n"
        "\"i was sceptical. now i'm just watching the bot work\" — @user_uk23\n\n"
        "your slot, {name}. still waiting for you."
    ),
    9: (
        "{name} — offer on the table:\n\n"
        "i'll walk you through the full setup personally. step by step.\n\n"
        "just say GO and i'll send you the direct link."
    ),
    10: (
        "🚨 slot depletion update:\n\n"
        "this week's onboarding round is almost full.\n\n"
        "next round: 3 weeks away.\n\n"
        "don't end up on a waiting list, {name}. say <b>READY</b> now."
    ),

    # ── DAYS 11-21: The Break-up sequence ─────────────────────
    11: (
        "real talk {name}.\n\n"
        "i've been holding your slot for 11 days.\n\n"
        "i have 3 people on the waitlist asking for it.\n\n"
        "one more day. then i'm moving on. what's it gonna be?"
    ),
    13: (
        "{name} — i'm giving your slot to the next person in line tomorrow.\n\n"
        "last chance.\n\n"
        "if you want it, say <b>READY</b> right now."
    ),
    15: (
        "halfway through the window, {name}.\n\n"
        "most people who don't activate by now never do.\n\n"
        "don't be that person. the results are real. the slot is real.\n\n"
        "what do you need from me to make this happen?"
    ),
    17: (
        "{name} — final push from my end.\n\n"
        "i've fought to keep your slot open this long.\n\n"
        "say <b>READY</b> and we go. or i let it go to the waitlist.\n\n"
        "your call."
    ),
    19: (
        "two days left {name}.\n\n"
        "after that your slot closes and i can't reopen it without going back to Aham.\n\n"
        "don't ghost me on this one. 🙏\n\n"
        "just say <b>READY</b>."
    ),
    21: (
        "last message from me {name}.\n\n"
        "your slot expires today. i'm closing it out.\n\n"
        "if you ever want back in — just message me. no hard feelings.\n\n"
        "take care. 🤝"
    ),
}


def _hours_since(ts_str: str) -> float:
    """Returns hours since the given ISO timestamp."""
    if not ts_str:
        return 9999.0
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    except (ValueError, TypeError):
        return 9999.0


def _send(telegram_id: str, text: str, name: str, description: str):
    """Send a message, record it, and log."""
    send_message(telegram_id, text)
    append_conversation(telegram_id, "assistant", text)
    logger.info(f"[RECOVERY] {description} → {telegram_id} ({name})")


def run_recovery_scan():
    """
    Main daily recovery scanner.
    Processes all active/new leads through the recovery logic.
    """
    logger.info("═══ 🔄 PHANTOM AI RECOVERY SCAN STARTING ═══")
    leads     = get_all_leads()
    processed = 0
    skipped   = 0

    for lead in leads:
        tid          = lead.get("telegram_id", "")
        name         = lead.get("name", "friend") or "friend"
        stage        = lead.get("stage",  "new")
        status       = lead.get("status", "new")
        vsl_sent     = lead.get("vsl_sent", "no")
        last_ts      = lead.get("last_contact_ts", "")
        last_sent    = lead.get("followup_last_sent", "")
        followup_day = int(lead.get("followup_day", "0") or "0")
        nudge_count  = int(lead.get("nudge_count",  "0") or "0")

        if not tid:
            continue

        # Skip manual / closed / done leads
        if status in (STATUS_MANUAL, "closed", "done", STATUS_LOST):
            skipped += 1
            continue

        hours_silent      = _hours_since(last_ts)
        hours_since_nudge = _hours_since(last_sent) if last_sent else hours_silent

        # ── HAIL MARY — 24h silence at Stage 1 or 2 → bypass to VSL
        if (stage in (STAGE_IDENTITY, STAGE_CHOICE, "new")
                and hours_silent >= VSL_HAILMARY_HOURS
                and vsl_sent == "no"):

            msg = msg_hailmary(name)
            _send(tid, msg, name, "HAIL MARY VSL")
            update_lead(tid, {
                "stage":    STAGE_VSL,
                "vsl_sent": "yes",
                "notes":    f"Hail Mary VSL sent after {int(hours_silent)}h silence"
            })
            processed += 1
            continue

        # ── SHORT & SHARP NUDGE — 2h silence, max 4 nudges ──────
        if (hours_silent >= NUDGE_HOURS
                and hours_since_nudge >= NUDGE_HOURS
                and nudge_count < 4):

            msg = msg_nudge(name, nudge_count + 1)
            _send(tid, msg, name, f"NUDGE #{nudge_count + 1}")
            update_lead(tid, {
                "nudge_count":        str(nudge_count + 1),
                "followup_last_sent": datetime.now(timezone.utc).isoformat()
            })
            processed += 1
            continue

        # ── 21-DAY DRIP SEQUENCE ──────────────────────────────────
        if followup_day < FOLLOWUP_DAYS:
            next_day = followup_day + 1

            if next_day in FOLLOWUP_SEQUENCE:
                msg_template = FOLLOWUP_SEQUENCE[next_day]
                msg = msg_template.format(name=name)

                _send(tid, msg, name, f"DAY {next_day} DRIP")
                update_lead(tid, {
                    "followup_day":       str(next_day),
                    "followup_last_sent": datetime.now(timezone.utc).isoformat()
                })
                processed += 1

            # Day 21 reached — mark as LOST
            if next_day >= FOLLOWUP_DAYS:
                update_lead(tid, {
                    "status": STATUS_LOST,
                    "notes":  "21-day sequence complete — marked LOST"
                })
                logger.info(f"[LOST] Lead {tid} ({name}) — 21 days exhausted.")

    logger.info(f"═══ ✅ SCAN COMPLETE: {processed} actions | {skipped} skipped ═══")
    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    run_recovery_scan()
