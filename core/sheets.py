"""
Google Sheets database layer for Phantom AI Leads.
All CRUD operations for the leads database.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import SHEET_URL, LEADS_TAB, LOG_TAB, COL

import gumloop

def get_client():
    return Client(
        user_id=os.getenv("GUMCP_USER_ID"),
        gumcp_api_key=os.getenv("GUMCP_ACCESS_TOKEN") or os.getenv("GUMCP_API_KEY"),
        base_url=os.getenv("GUMCP_BASE_URL"),
    )


def now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── READ ─────────────────────────────────────────────────────

def get_all_leads() -> list[dict]:
    """Fetch every row from the Leads sheet as a list of dicts."""
    with get_client() as client:
        raw = client.call_tool("gsheets__batch-get", {
            "spreadsheet_url": SHEET_URL,
            "ranges": [f"{LEADS_TAB}!A1:O1000"]
        })
        data = json.loads(raw[0])

    rows = []
    value_ranges = data.get("valueRanges", [])
    if not value_ranges:
        return rows

    values = value_ranges[0].get("values", [])
    if len(values) < 2:
        return rows

    headers = values[0]
    for row in values[1:]:
        padded = row + [""] * (len(headers) - len(row))
        rows.append(dict(zip(headers, padded)))
    return rows


def find_lead(telegram_id: str) -> dict | None:
    """Search for a lead by Telegram ID. Returns the lead dict or None."""
    leads = get_all_leads()
    for lead in leads:
        if str(lead.get("telegram_id", "")) == str(telegram_id):
            return lead
    return None


def get_row_number(telegram_id: str) -> int | None:
    """Returns 1-indexed row number for a given telegram_id (row 1 = headers)."""
    with get_client() as client:
        raw = client.call_tool("gsheets__batch-get", {
            "spreadsheet_url": SHEET_URL,
            "ranges": [f"{LEADS_TAB}!A1:A1000"]
        })
        data = json.loads(raw[0])

    values = data.get("valueRanges", [{}])[0].get("values", [])
    for i, row in enumerate(values):
        if row and str(row[0]) == str(telegram_id):
            return i + 1  # 1-indexed
    return None


# ─── WRITE ────────────────────────────────────────────────────

def create_lead(telegram_id: str, username: str = "") -> dict:
    """Create a new lead row. Returns the new lead dict."""
    ts = now_ts()
    new_row = [[
        str(telegram_id),   # telegram_id
        "",                  # name
        username,            # username
        "new",               # stage
        "new",               # status
        "no",                # vsl_sent
        "",                  # choice
        "",                  # last_message
        ts,                  # last_contact_ts
        "0",                 # nudge_count
        "0",                 # followup_day
        "",                  # followup_last_sent
        "",                  # notes
        ts,                  # created_at
        "[]",                # conversation_history
    ]]
    with get_client() as client:
        client.call_tool("gsheets__append-values", {
            "spreadsheet_url": SHEET_URL,
            "range": f"{LEADS_TAB}!A1",
            "values": new_row
        })
    return {
        "telegram_id": str(telegram_id),
        "name": "",
        "username": username,
        "stage": "new",
        "status": "new",
        "vsl_sent": "no",
        "choice": "",
        "last_message": "",
        "last_contact_ts": ts,
        "nudge_count": "0",
        "followup_day": "0",
        "followup_last_sent": "",
        "notes": "",
        "created_at": ts,
        "conversation_history": "[]",
    }


def update_lead(telegram_id: str, updates: dict):
    """Update specific fields for a lead. updates = {field_name: value}."""
    row_num = get_row_number(telegram_id)
    if row_num is None:
        raise ValueError(f"Lead {telegram_id} not found")

    # Always update last_contact_ts
    updates["last_contact_ts"] = now_ts()

    with get_client() as client:
        for field, value in updates.items():
            if field not in COL:
                continue
            col_letter = chr(ord("A") + COL[field])
            cell = f"{LEADS_TAB}!{col_letter}{row_num}"
            client.call_tool("gsheets__batch-update", {
                "spreadsheet_url": SHEET_URL,
                "data": [{
                    "range": cell,
                    "values": [[str(value)]]
                }],
                "value_input_option": "RAW"
            })


def append_conversation(telegram_id: str, role: str, content: str):
    """Append a message to the conversation_history JSON array."""
    lead = find_lead(telegram_id)
    if not lead:
        return

    try:
        history = json.loads(lead.get("conversation_history", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        history = []

    history.append({
        "role": role,
        "content": content,
        "ts": now_ts()
    })

    # Keep last 40 messages to avoid sheet cell overflow
    if len(history) > 40:
        history = history[-40:]

    update_lead(telegram_id, {"conversation_history": json.dumps(history)})


def get_conversation_history(telegram_id: str) -> list[dict]:
    """Return parsed conversation history for a lead."""
    lead = find_lead(telegram_id)
    if not lead:
        return []
    try:
        return json.loads(lead.get("conversation_history", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


# ─── RECOVERY SCAN ────────────────────────────────────────────

def get_leads_by_status(status: str) -> list[dict]:
    return [l for l in get_all_leads() if l.get("status") == status]


def get_leads_needing_nudge(hours: int = 2) -> list[dict]:
    """Returns leads that haven't responded in `hours` and are active."""
    from datetime import timedelta
    threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    for lead in get_all_leads():
        if lead.get("status") not in ("active", "new"):
            continue
        ts_str = lead.get("last_contact_ts", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts < threshold:
                results.append(lead)
        except ValueError:
            pass
    return results


def log_followup(telegram_id: str, name: str, day: int, message: str):
    """
    Log a follow-up event by adding a note to the lead's 'notes' column.
    (FollowUpLog tab not available — single-tab fallback)
    """
    try:
        lead = find_lead(telegram_id)
        if not lead:
            return
        existing_notes = lead.get("notes", "") or ""
        ts = now_ts()
        new_note = f"[Day {day} @ {ts[:10]}]: {message[:60]}"
        combined = f"{existing_notes} | {new_note}" if existing_notes else new_note
        update_lead(telegram_id, {"notes": combined[-500:]})  # keep last 500 chars
    except Exception:
        pass  # log_followup is non-critical — never crash the main flow
