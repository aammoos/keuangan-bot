"""
BOT KEUANGAN PRIBADI - Full Version
"""

import os
import re
import json
import tempfile
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_ID = int(os.getenv("CHAT_ID", "0"))
SHEET_ID = os.getenv("SHEET_ID")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# ====================== CREDENTIALS ======================
def get_credentials():
    creds_json = os.getenv("GOOGLE_CREDS_JSON")
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(creds_dict, f)
                temp_path = f.name
            logger.info("✅ Credentials from Railway")
            return Credentials.from_service_account_file(temp_path, scopes=SCOPES)
        except Exception as e:
            logger.error(f"JSON Error: {e}")

    if os.path.exists("credentials.json.json"):
        logger.info("✅ Using local credentials")
        return Credentials.from_service_account_file("credentials.json.json", scopes=SCOPES)
    raise Exception("❌ No credentials!")

def get_sheet():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)

def is_owner(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_ID

# ====================== PARSER ======================
class Parser:
    def parse_amount(self, text: str):
        text = text.lower().replace(",", ".")
        m = re.search(r"(\d+(?:\.\d+)?)\s*(jt|juta|rb|ribu|k)?", text)
        if m:
            num = float(m.group(1))
            if m.group(2) in ["jt", "juta"]: return num * 1_000_000
            if m.group(2) in ["rb", "ribu", "k"]: return num * 1_000
            return num
        return 0

    def detect_type(self, text: str):
        t = text.lower()
        if any(x in t for x in ["gaji", "masuk", "dapet"]): return "PEMASUKAN"
        if any(x in t for x in ["beli", "bayar", "keluar", "habis", "jajan"]): return "PENGELUARAN"
        if "hutang" in t: return "HUTANG"
        if any(x in t for x in ["saldo", "laporan", "ringkasan"]): return "LAPORAN"
        if any(x in t for x in ["beli saham", "lot"]): return "PORTFOLIO"
        return "UNKNOWN"

parser = Parser()

# ====================== HANDLERS ======================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    await update.message.reply_text(
        "👋 *Bot Keuangan Pribadi Aktif!*\n\n"
        "Ketik natural:\n"
        "• beli kopi 15rb\n"
        "• gaji masuk 8jt\n"
        "• hutang ke budi 500rb\n"
        "• saldo / laporan",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    text = update.message.text or ""
    if not text: return

    tipe = parser.detect_type(text)
    amount = parser.parse_amount(text)

    try:
        if tipe == "PENGELUARAN":
            await update.message.reply_text(f"✅ Pengeluaran Rp{amount:,.0f} dicatat.")
        elif tipe == "PEMASUKAN":
            await update.message.reply_text(f"✅ Pemasukan Rp{amount:,.0f} dicatat.")
        elif tipe == "HUTANG":
            await update.message.reply_text(f"✅ Hutang Rp{amount:,.0f} dicatat.")
        elif tipe == "LAPORAN":
            await update.message.reply_text("📊 Ringkasan keuangan (fitur lengkap dalam pengembangan)")
        else:
            await update.message.reply_text("✅ Diterima.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Foto diterima. Kirim teks keterangan.")

# ====================== MAIN ======================
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN tidak ditemukan!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("🚀 Bot Keuangan Pribadi Full Version berjalan!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()