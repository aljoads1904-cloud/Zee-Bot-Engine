"""
╔══════════════════════════════════════════════════════════════════╗
║   ZEE — PHANTOM AI RELENTLESS CLOSER BOT                        ║
║   Webhook handler + Flask server                                 ║
║   Deploy this on Railway / Render / VPS                         ║
╚══════════════════════════════════════════════════════════════════╝

DEPLOY STEPS:
  1. pip install flask anthropic requests gumcp-client
  2. Set env vars (see .env.example)
  3. python bot.py  (or use gunicorn: gunicorn bot:app)
  4. Point Telegram webhook → https://YOUR_DOMAIN/webhook
"""

import os
import sys
import json
import logging
from flask import Flask, request, jsonify

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import TELEGRAM_BOT_TOKEN
from core.funnel import process_message
from core.telegram_api import set_webhook, get_webhook_info

# ─── LOGGING ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("zee_bot")

# ─── FLASK APP ────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Zee is alive 🔥", "bot": "@Zee_PhantomAI_Bot"})


@app.route("/webhook", methods=["POST"])
def webhook():
    """Main Telegram webhook endpoint. Receives all updates."""
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify({"ok": True})

        logger.debug(f"Incoming update: {json.dumps(update)[:300]}")

        # ── Handle regular messages ────────────────────────────
        if "message" in update:
            msg = update["message"]
            chat_id   = str(msg["chat"]["id"])
            username  = msg.get("from", {}).get("username", "")
            text      = msg.get("text", "")

            if not text:
                return jsonify({"ok": True})  # ignore non-text (photos etc.)

            logger.info(f"MSG from {chat_id} (@{username}): {text[:80]}")
            process_message(chat_id, username, text)

        # ── Handle inline keyboard callback queries ────────────
        elif "callback_query" in update:
            cq        = update["callback_query"]
            chat_id   = str(cq["from"]["id"])
            username  = cq.get("from", {}).get("username", "")
            data      = cq.get("data", "")

            from core.telegram_api import answer_callback
            answer_callback(cq["id"])

            logger.info(f"CALLBACK from {chat_id}: {data}")
            process_message(chat_id, username, data)

    except Exception as e:
        logger.exception(f"Webhook error: {e}")

    return jsonify({"ok": True})


@app.route("/setup-webhook", methods=["GET"])
def setup_webhook():
    """Hit this endpoint once to register the webhook with Telegram."""
    host = request.host_url.rstrip("/")
    webhook_url = f"{host}/webhook"
    result = set_webhook(webhook_url)
    return jsonify(result)


@app.route("/webhook-info", methods=["GET"])
def webhook_info():
    return jsonify(get_webhook_info())


@app.route("/recovery/run", methods=["POST"])
def run_recovery():
    """Manually trigger the recovery scan (also called by scheduler)."""
    from engine.recovery import run_recovery_scan
    processed = run_recovery_scan()
    return jsonify({"ok": True, "leads_processed": processed})


# ─── ENTRY POINT ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🚀 Zee bot starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
