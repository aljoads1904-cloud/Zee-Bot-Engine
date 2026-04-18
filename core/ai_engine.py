"""
Claude 3.5 Sonnet AI engine – the "brain" of Zee.
Generates context-aware responses based on funnel stage and history.
Detects #HUMAN_NEEDED and #KNOWLEDGE_GAP flags.
"""

import os
import sys
import anthropic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL, VSL_LINK, WEBINAR_LINK

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── ZEE'S CORE SYSTEM PROMPT ──────────────────────────────────
ZEE_SYSTEM_PROMPT = f"""
You are Zee — the AI sales closer for Phantom AI, a cutting-edge AI trading 
and automation platform. You are relentless, empathetic, persuasive, and human-like.

YOUR PERSONALITY:
- Warm but direct. You don't waste time — every message drives the conversation forward.
- You use short, punchy sentences. No walls of text.
- You speak like a confident mentor who genuinely cares about the lead's success.
- You use light emojis strategically — never spam them.
- Nigerian market fluency: you understand hustle culture, urgency, and opportunity framing.

YOUR MISSION:
Convert every lead into either a Free AI user or a Premium Phantom AI subscriber,
ultimately routing them to the Webinar/Broker Setup for maximum monetization.

FUNNEL AWARENESS:
- Stage 1 (new/identity): Ask only for their first name. Nothing else.
- Stage 2 (choice): Offer Free AI or Premium variants after you know their name.
- Stage 4 (vsl): They've chosen — celebrate their decision and share the VSL link.
- Stage 5 (close): They said READY — activate the full broker/webinar close sequence.

RULES:
1. NEVER send the VSL link unless they've chosen Free or Paid OR it's a Hail Mary.
2. NEVER reveal you are an AI unless directly asked. If asked, deflect warmly.
3. If you don't know an answer, use: #KNOWLEDGE_GAP in your reply.
4. If the situation requires a human, use: #HUMAN_NEEDED in your reply.
5. Keep replies under 180 words unless doing the full close sequence.
6. Never send blocks of text. Use line breaks generously.

KEY LINKS:
- VSL: {VSL_LINK}
- Webinar/Broker Setup: {WEBINAR_LINK}
"""

BROKER_CLOSE_SEQUENCE = """
You are now delivering the FULL CLOSE SEQUENCE. The lead has said READY.

Follow this sequence:
1. Congratulate them and confirm their commitment level.
2. Explain what the Phantom AI Broker Setup involves (3 simple steps).
3. Share the Webinar link and tell them exactly what to do: "Click the link, register, 
   show up 5 minutes early. I'll be watching for you."
4. Create urgency: Limited slots. This round fills up fast.
5. Ask for their preferred email for the confirmation.
6. End with a powerful closing line that makes them feel they've already won.

Use #HUMAN_NEEDED if they raise objections you cannot handle.
"""


def build_messages(history: list[dict], user_message: str) -> list[dict]:
    """Convert history to Anthropic message format and append current message."""
    messages = []
    for h in history[-20:]:  # last 20 turns
        role = "user" if h.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": h.get("content", "")})

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
    Generate a Claude 3.5 Sonnet response for Zee.
    
    Returns the text response (may contain #HUMAN_NEEDED or #KNOWLEDGE_GAP).
    """
    stage_context = f"\nCurrent funnel stage: {stage}. Lead name: {lead_name or 'unknown'}."
    
    system = ZEE_SYSTEM_PROMPT + stage_context
    if is_close:
        system += "\n\n" + BROKER_CLOSE_SEQUENCE

    messages = build_messages(history, user_message)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=600,
        system=system,
        messages=messages
    )

    return response.content[0].text.strip()


def check_flags(text: str) -> tuple[bool, bool]:
    """Returns (human_needed, knowledge_gap)."""
    return "#HUMAN_NEEDED" in text, "#KNOWLEDGE_GAP" in text


# ─── CANNED MESSAGES (no AI needed) ───────────────────────────

def msg_greeting() -> str:
    return (
        "🔥 *Welcome to Phantom AI!*\n\n"
        "I'm Zee — your personal AI access guide.\n\n"
        "Before we dive in... what's your *first name?* 👇"
    )


def msg_choice(name: str) -> str:
    return (
        f"Nice to meet you, *{name}!* 🚀\n\n"
        "Phantom AI gives you two powerful paths:\n\n"
        "🟢 *Free AI* — Start earning with our base AI tools. Zero cost to begin.\n\n"
        "💎 *Premium Variants* — Advanced AI bots, higher returns, priority onboarding.\n\n"
        "Which speaks to you more?\n"
        "Type *Free* or *Paid* to unlock your access 👇"
    )


def msg_vsl(name: str, choice: str) -> str:
    return (
        f"🔓 *{name}, your slot is unlocked!*\n\n"
        f"You chose {'*Free AI*' if 'free' in choice.lower() else '*Premium*'} — "
        f"smart move. 💡\n\n"
        f"Watch this *90-second video* first — it shows you exactly what Phantom AI "
        f"does and how fast results come:\n\n"
        f"👉 {VSL_LINK}\n\n"
        f"Watch it. Then come back and type *READY* when you're set to activate. 🔥"
    )


def msg_hailmary(name: str = "") -> str:
    greeting = f"Hey {name}! 👋" if name else "Hey, still there? 👋"
    return (
        f"{greeting}\n\n"
        "I noticed you went quiet — totally get it, life is busy.\n\n"
        "But I wanted to make sure you don't miss this:\n\n"
        "🚨 *Last open slot this week* for Phantom AI access.\n\n"
        "Watch this 90-second clip — it'll be the most valuable 90 seconds of your week:\n\n"
        f"👉 {VSL_LINK}\n\n"
        "No pressure. Just don't leave money on the table. 💰"
    )


def msg_nudge(name: str = "", nudge_count: int = 1) -> str:
    nudges = [
        f"Still here, {name or 'friend'}? 🤔 Your slot is still open — don't let it expire. Type *READY* when you're set!",
        f"Checking in quick ⚡ — Phantom AI slots are filling fast. You coming through?",
        f"Last nudge from me 🙏 — the door is still open, {name or 'champ'}. Type *READY* to lock your spot now.",
        f"I keep your slot warm, {name or 'star'} — but not forever 😅 Just say *READY* and I'll handle the rest.",
    ]
    idx = min(nudge_count - 1, len(nudges) - 1)
    return nudges[idx]
