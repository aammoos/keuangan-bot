"""
╔══════════════════════════════════════════════════════╗
║     BOT KEUANGAN PRIBADI — Telegram + Google Sheets  ║
║     Deploy Railway (Gratis)                          ║
╚══════════════════════════════════════════════════════╝
"""

import os
import re
import json
import tempfile
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

logging.basicConfig(
    format="%(asctime)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN   = os.getenv("BOT_TOKEN")
ALLOWED_ID  = int(os.getenv("CHAT_ID", "0"))
SHEET_ID    = os.getenv("SHEET_ID")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─── GOOGLE CREDENTIALS (Railway Support) ─────────────────────
def get_credentials():
    creds_json_str = os.getenv("GOOGLE_CREDS_JSON")
    if creds_json_str:
        try:
            creds_dict = json.loads(creds_json_str)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(creds_dict, f)
                temp_path = f.name
            logger.info("✅ Credentials loaded from GOOGLE_CREDS_JSON (Railway)")
            return Credentials.from_service_account_file(temp_path, scopes=SCOPES)
        except Exception as e:
            logger.error(f"❌ JSON Error: {e}")

    # Local fallback
    local_file = "credentials.json.json"
    if os.path.exists(local_file):
        logger.info(f"✅ Using local {local_file}")
        return Credentials.from_service_account_file(local_file, scopes=SCOPES)
    
    raise Exception("❌ Credentials not found! Set GOOGLE_CREDS_JSON in Railway Variables.")

def get_sheet():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)

# ─── Security ────────────────────────────────────────────────
def is_owner(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_ID

# (Parser class dan fungsi-fungsi lain tetap sama seperti kode kamu sebelumnya)
# Saya tidak ubah parser karena sudah bagus

# ... [Copy seluruh class Parser, fungsi append_*, get_summary, dll dari kode lama kamu] ...

# ─── Main ────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN tidak ditemukan di Railway Variables!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("🚀 Bot Keuangan Pribadi berjalan di Railway!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()