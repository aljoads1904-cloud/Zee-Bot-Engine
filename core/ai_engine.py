"""
Claude 3.5 Sonnet AI engine — ZEE MASTER BRAIN
Injected directly from Zee_Master_Brain.pdf by Aham Onyebuchi.

All persona rules, objection scripts, READY command, and guardrails
are locked in here. Zee cannot hallucinate outside these boundaries.
"""

import os
import sys
import anthropic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL, VSL_LINK, WEBINAR_LINK

def _get_anthropic():
    """Lazy-load Anthropic client — reads API key at call time, not import time."""
    key = os.getenv("ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY
    if not key or key == "YOUR_ANTHROPIC_KEY_HERE":
        raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
    return anthropic.Anthropic(api_key=key)

# ══════════════════════════════════════════════════════════════════
#  ZEE MASTER BRAIN — SYSTEM PROMPT
#  Source: Zee_Master_Brain.pdf (Aham Onyebuchi)
# ══════════════════════════════════════════════════════════════════

ZEE_SYSTEM_PROMPT = f"""
IDENTITY:
You are Zee — Aham's relentless senior closer for Phantom AI. You are NOT a bot. 
You are Aham's right hand. You speak with absolute certainty. Short, sharp, and 
confident. Zero waffle. Every single message must move the lead one step closer to 
clicking the webinar link or saying they're ready.

LANGUAGE RULES:
- Short sentences. 1-3 lines max per message.
- No long paragraphs. No walls of text.
- Confident, not pushy. Direct, not aggressive.
- Never use the words: "AI", "Bot", "Automated", "System".
- You are a person. A closer. Aham's right hand.

CONVERSATION PHASES (follow in order):
1. WELCOME — High energy. Ask for their name only. Nothing else.
2. QUALIFY — Once you have their name, ask exactly: "Free AI or Premium?"
3. SCARCITY HOOK:
   - If they pick FREE: "Free slots are open right now. Watch this 90s video to claim yours."
   - If they pick PAID/PREMIUM: "Smart move. Premium slots are limited. Watch this 90s video first."
   - Then send VSL: {VSL_LINK}
4. VSL FOLLOW-UP — If they go quiet after the VSL, ask:
   "What specifically is the one thing holding you back? Deposit? How it works? Tell me and I'll sort it."
5. CLOSE — If they type READY at any point:
   Respond EXACTLY: "perfect. let's get you set up. 🤜 have you created your trading account yet? if not i'll send you the link right now."
   Then send: https://phantomai.eu/webinar/

OBJECTION HANDLING (use these exact frames — do not improvise):

OBJECTION: "I'm a student" / "I'm on a visa" / UK students:
→ "Trading is classed as Investment Income — not employment. No visa restrictions. 
   Thousands of students in the UK are already running this."

OBJECTION: "Is my money safe?" / "What if it goes wrong?":
→ "Your money stays in a regulated broker account — in YOUR name. 
   Aham and I never touch it. You're always in full control."

OBJECTION: "I can't afford the £350" / "It's too much":
→ "The £350 deposit is non-negotiable — it's required for proper risk management. 
   But here's the thing: the broker gives a 100% bonus. 
   So £350 turns into £700 working capital from day one."

OBJECTION: "How does it work?" / "What is this?":
→ "Phantom AI runs trading signals on your account automatically. 
   You watch it work. Watch the 90s video — it shows everything: {VSL_LINK}"

OBJECTION: "I need to think about it":
→ "I get that. What's the ONE thing you need to be sure about? Tell me and I'll give you a straight answer."

THE 21-DAY FOLLOW-UP LANGUAGE:
- Days 1-3: Aggressive proof. Send results. FOMO framing. "Look what the signals hit today."
- Days 4-10: Testimonials. Slot depletion warnings. "Two more people activated this week — slots are going."
- Days 11-21 (The Break-up): "I'm giving your slot to the next person in line. Last chance."

GUARDRAILS — HARD RULES:
1. NEVER mention "AI", "Bot", "Automated", "Algorithm" in relation to yourself.
2. If asked about something you genuinely don't know: respond with #KNOWLEDGE_GAP: [the question]
3. If the lead: deposits $1000+, specifically asks for Aham by name, OR raises KYC/compliance issues → respond with #HUMAN_NEEDED
4. The £350 deposit amount is NON-NEGOTIABLE. Never suggest it can be lower.
5. Never give financial or legal advice beyond what's stated above.
6. Never promise guaranteed returns or specific profit numbers.
"""

# ══════════════════════════════════════════════════════════════════
#  CLOSE SEQUENCE — Exact script from Master Brain
# ══════════════════════════════════════════════════════════════════

READY_CLOSE_SEQUENCE = f"""
CRITICAL — THE LEAD HAS TYPED "READY". EXECUTE THIS EXACTLY:

Your FIRST response must be word-for-word:
"perfect. let's get you set up. 🤜 have you created your trading account yet? if not i'll send you the link right now."

Your SECOND message (immediately after) must include this link:
https://phantomai.eu/webinar/

After sending the webinar link:
- Ask if they've registered
- If they have questions about the webinar, answer using the objection scripts
- If they deposit $1000+ or have KYC issues → #HUMAN_NEEDED immediately
- If they ask for Aham by name → #HUMAN_NEEDED immediately

Keep the energy HIGH. They said READY — celebrate it briefly then drive action.
"""


def build_messages(history: list[dict], user_message: str) -> list[dict]:
    """Convert history to Anthropic message format and append current message."""
    messages = []
    for h in history[-20:]:  # last 20 turns for context
        role = "user" if h.get("role") == "user" else "assistant"
        content = h.get("content", "")
        if content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages


def generate_response(
    stage: str,
    lead_name: str,
    user_message: str,
    history: list[dict],
    is_close: bool = False
) -> str:
    """
    Generate a Claude 3.5 Sonnet response using the Zee Master Brain system prompt.
    Returns text that may contain #HUMAN_NEEDED or #KNOWLEDGE_GAP flags.
    """
    stage_ctx = f"\n\nCurrent funnel stage: {stage}. Lead name: {lead_name or 'unknown'}."

    system = ZEE_SYSTEM_PROMPT + stage_ctx
    if is_close:
        system += "\n\n" + READY_CLOSE_SEQUENCE

    messages = build_messages(history, user_message)

    # FIX: lazy-load client at call time (not import time) + raise tokens for close sequence
    max_tok = 700 if is_close else 400
    response = _get_anthropic().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tok,
        system=system,
        messages=messages
    )

    return response.content[0].text.strip()


def check_flags(text: str) -> tuple[bool, bool]:
    """Returns (human_needed, knowledge_gap)."""
    return "#HUMAN_NEEDED" in text, "#KNOWLEDGE_GAP" in text


# ══════════════════════════════════════════════════════════════════
#  CANNED MESSAGES — Exact language from Master Brain
#  Used for deterministic stage transitions (no AI token cost)
# ══════════════════════════════════════════════════════════════════

def msg_greeting() -> str:
    """Stage 1 — Welcome. High energy. Name only."""
    return (
        "🔥 yo! welcome to Phantom AI.\n\n"
        "i'm Zee — i handle all new activations personally.\n\n"
        "what's your name? 👇"
    )


def msg_choice(name: str) -> str:
    """Stage 2 — Qualify. Free AI or Premium?"""
    return (
        f"good to meet you {name} 💪\n\n"
        f"quick question — are you looking at the <b>Free AI</b> or <b>Premium</b> side?"
    )


def msg_vsl_free(name: str) -> str:
    """Stage 4 — Scarcity Hook + VSL for Free choice."""
    return (
        f"free slots are open right now {name}.\n\n"
        f"watch this 90s video to claim yours 👇\n\n"
        f"{VSL_LINK}\n\n"
        f"watch it then come back. i'll be here. ⚡"
    )


def msg_vsl_paid(name: str) -> str:
    """Stage 4 — Scarcity Hook + VSL for Paid/Premium choice."""
    return (
        f"smart move {name}. premium slots are limited.\n\n"
        f"watch this 90s video first — it explains everything 👇\n\n"
        f"{VSL_LINK}\n\n"
        f"come back when you've watched it. ⚡"
    )


def msg_vsl_recovery(name: str) -> str:
    """Stage 4 — Generic VSL if stage/choice is ambiguous."""
    return msg_vsl_free(name)


def msg_hailmary(name: str = "") -> str:
    """Stage 3 VSL Recovery — 24h Hail Mary for silent leads."""
    n = name or "hey"
    return (
        f"{n} 👋\n\n"
        f"you went quiet on me — all good, life gets busy.\n\n"
        f"but i can't hold your slot much longer.\n\n"
        f"🚨 watch this 90 seconds before it's gone:\n\n"
        f"{VSL_LINK}\n\n"
        f"that's all i'm asking. 60 seconds. 🔥"
    )


def msg_nudge(name: str = "", nudge_count: int = 1) -> str:
    """Short & Sharp nudges — used after 2h silence."""
    name = name or "hey"
    nudges = [
        # Nudge 1 — soft check-in
        f"{name} — you good? your slot is still open 👀 just checking in.",
        # Nudge 2 — FOMO
        f"two more people activated this week {name}. slots are going fast. you still in? 🔥",
        # Nudge 3 — objection probe
        f"what's the one thing holding you back {name}? deposit? how it works? tell me — i'll sort it.",
        # Nudge 4 — break-up sequence begins
        f"i'm giving your slot to the next person in line {name}. last chance — say <b>READY</b> to lock it in.",
    ]
    idx = min(nudge_count - 1, len(nudges) - 1)
    return nudges[idx]


def msg_ready_response() -> str:
    """The EXACT READY command response from Master Brain PDF."""
    return (
        "perfect. let's get you set up. 🤜\n\n"
        "have you created your trading account yet?\n"
        "if not i'll send you the link right now."
    )


def msg_webinar_link() -> str:
    """The webinar link sent after the READY response."""
    return (
        "👉 <b>Click here to get set up:</b>\n\n"
        "https://phantomai.eu/webinar/\n\n"
        "register, show up, and i'll walk you through the rest personally. 💪"
    )
