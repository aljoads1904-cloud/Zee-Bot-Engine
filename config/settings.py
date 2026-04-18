"""
╔══════════════════════════════════════════════════════════════╗
║         ZEE PHANTOM AI – RELENTLESS CLOSER CONFIGURATION     ║
╚══════════════════════════════════════════════════════════════╝
"""

import os

# ─── TELEGRAM ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_API_URL   = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
AHAM_TELEGRAM_ID   = 825923415       # Alert target

# ─── GOOGLE SHEETS ────────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/1prqmc7YumgHESmzpIXMJNzG3lIuBFHsiRt_codf267E/edit"
SHEET_ID  = "1prqmc7YumgHESmzpIXMJNzG3lIuBFHsiRt_codf267E"
LEADS_TAB = "Sheet1"
LOG_TAB   = "FollowUpLog"

# Column index map (0-based) for Leads sheet
COL = {
    "telegram_id":        0,
    "name":               1,
    "username":           2,
    "stage":              3,
    "status":             4,
    "vsl_sent":           5,
    "choice":             6,
    "last_message":       7,
    "last_contact_ts":    8,
    "nudge_count":        9,
    "followup_day":       10,
    "followup_last_sent": 11,
    "notes":              12,
    "created_at":         13,
    "conversation_history": 14,
}

# ─── ANTHROPIC / CLAUDE ───────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_KEY_HERE")
CLAUDE_MODEL       = "claude-3-5-sonnet-20241022"
TYPING_DELAY_SECS  = 3

# ─── LINKS ────────────────────────────────────────────────────
VSL_LINK     = os.getenv("VSL_LINK",     "https://phantomai.com/vsl")      # replace with real
WEBINAR_LINK = os.getenv("WEBINAR_LINK", "https://phantomai.com/webinar")  # replace with real

# ─── TIMING ───────────────────────────────────────────────────
NUDGE_HOURS         = 2       # Send short nudge after 2h silence
VSL_HAILMARY_HOURS  = 24     # Skip to VSL after 24h silence at Stage 1/2
FOLLOWUP_DAYS       = 21     # Aggressive follow-up window

# ─── FUNNEL STAGES ────────────────────────────────────────────
STAGE_NEW      = "new"
STAGE_IDENTITY = "identity"    # Stage 1 – asked for name
STAGE_CHOICE   = "choice"      # Stage 2 – asked free/paid
STAGE_VSL      = "vsl"         # Stage 4 – VSL delivered
STAGE_CLOSE    = "close"       # Stage 5 – READY triggered
STAGE_DONE     = "done"

STATUS_NEW     = "new"
STATUS_ACTIVE  = "active"
STATUS_MANUAL  = "manual"
STATUS_LOST    = "lost"
STATUS_CLOSED  = "closed"
