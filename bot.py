"""
BOT KEUANGAN PRIBADI — Full Version (Fixed)
Fix: parser diperluas, laporan baca sheet, data benar ditulis, credentials typo
"""

import os, re, json, logging
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

logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.getenv("BOT_TOKEN")
ALLOWED_ID = int(os.getenv("CHAT_ID", "0"))
SHEET_ID   = os.getenv("SHEET_ID")
SCOPES     = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─────────────────────────────────────────────────────────────
# CREDENTIALS  (FIX #4: hilangkan typo .json.json)
# ─────────────────────────────────────────────────────────────
def get_credentials():
    # Opsi 1: Railway env var
    creds_json = os.getenv("GOOGLE_CREDS_JSON")
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            logger.info("✅ Credentials dari Railway env")
            # Langsung pakai dict, tidak perlu temp file (lebih aman)
            return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except json.JSONDecodeError as e:
            logger.error(f"GOOGLE_CREDS_JSON bukan valid JSON: {e}")
        except Exception as e:
            logger.error(f"Credentials error: {e}")

    # Opsi 2: file lokal
    local = "credentials.json"
    if os.path.exists(local):
        logger.info("✅ Credentials dari file lokal")
        return Credentials.from_service_account_file(local, scopes=SCOPES)

    raise Exception("Tidak ada credentials! Isi GOOGLE_CREDS_JSON di Railway Variables.")


def get_sheet():
    creds = get_credentials()
    gc    = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def is_owner(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_ID


# ─────────────────────────────────────────────────────────────
# PARSER  (FIX #1: keyword jauh lebih banyak)
# ─────────────────────────────────────────────────────────────
class Parser:

    KW_OUT = [
        "beli", "bayar", "bayarin", "habis", "keluar", "jajan",
        "nonton", "makan", "minum", "ngopi", "kopi",
        "transfer ke", "kirim ke", "isi bensin", "isi pulsa",
        "top up", "topup", "tagihan", "cicilan", "belanja",
        "sewa", "kontrak", "parkir", "tol", "ojol", "grab",
        "gojek", "shopee", "tokopedia", "lazada", "bioskop",
        "langganan", "subscribe", "netflix", "spotify",
        "listrik", "air pam", "internet", "pulsa", "pln",
        "obat", "dokter", "apotek", "klinik",
    ]

    KW_IN = [
        "gaji", "masuk", "dapet", "dapat", "terima",
        "income", "bonus", "dividen", "dividend", "cashback",
        "jual", "laku", "dibayar", "cair", "profit",
        "freelance", "proyek", "project", "honor", "fee",
        "komisi", "refund",
    ]

    KW_HUTANG = ["hutang ke", "ngutang ke", "pinjam ke", "minjem ke", "utang ke"]
    KW_PIUTANG = ["piutangin", "pinjemin", "minjemin", "kasih pinjam", "ngasih pinjam"]
    POLA_PIUTANG = r"^(\w+)\s+pinjam\s+"

    KW_PORT = [
        "beli saham", "beli btc", "beli bitcoin",
        "beli crypto", "beli emas", "beli reksa", "beli reksadana",
        "jual saham", "jual btc", "jual crypto",
        "update harga", "update saham", "update btc",
        " lot ",
    ]

    KW_LAPORAN = [
        "saldo", "laporan", "ringkasan", "summary",
        "net worth", "rekap", "status keuangan",
        "pengeluaran bulan", "pemasukan bulan",
        "total pengeluaran", "total pemasukan",
    ]

    CAT_MAP = {
        "makan": "Makan & Minum", "minum": "Makan & Minum",
        "kopi": "Makan & Minum", "ngopi": "Makan & Minum",
        "nasi": "Makan & Minum", "sarapan": "Makan & Minum",
        "resto": "Makan & Minum", "warteg": "Makan & Minum",
        "jajan": "Makan & Minum", "makan siang": "Makan & Minum",
        "nonton": "Hiburan", "bioskop": "Hiburan",
        "game": "Hiburan", "spotify": "Hiburan",
        "netflix": "Hiburan", "subscribe": "Hiburan",
        "langganan": "Hiburan",
        "bensin": "Transportasi", "bbm": "Transportasi",
        "gojek": "Transportasi", "grab": "Transportasi",
        "ojol": "Transportasi", "parkir": "Transportasi",
        "tol": "Transportasi", "busway": "Transportasi",
        "baju": "Belanja", "sepatu": "Belanja",
        "shopee": "Belanja", "tokopedia": "Belanja",
        "lazada": "Belanja", "belanja": "Belanja",
        "obat": "Kesehatan", "dokter": "Kesehatan",
        "apotek": "Kesehatan", "klinik": "Kesehatan",
        "listrik": "Tagihan", "pln": "Tagihan",
        "internet": "Tagihan", "pulsa": "Tagihan",
        "tagihan": "Tagihan", "cicilan": "Tagihan",
        "buku": "Pendidikan", "kursus": "Pendidikan",
        "sewa": "Rumah Tangga", "kontrak": "Rumah Tangga",
        "kos": "Rumah Tangga",
    }

    def parse_amount(self, text: str) -> float:
        t = text.lower().replace(",", ".")
        patterns = [
            (r"(\d+(?:\.\d+)?)\s*(?:jt|juta)", 1_000_000),
            (r"(\d+(?:\.\d+)?)\s*(?:rb|ribu|k)\b", 1_000),
            (r"(\d+(?:\.\d+)?)\s*(?:m|miliar|milyar)", 1_000_000_000),
            (r"rp\.?\s*([\d\.]+)", 1),
        ]
        for pattern, mult in patterns:
            m = re.search(pattern, t)
            if m:
                raw = m.group(1).replace(".", "")
                return float(raw) * mult
        m = re.search(r"\b(\d{4,})\b", t)
        if m:
            return float(m.group(1))
        m = re.search(r"\b(\d{1,3})\b", t)
        if m:
            return float(m.group(1)) * 1_000
        return 0.0

    def detect_type(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in self.KW_PORT):
            return "PORTFOLIO"
        if any(k in t for k in self.KW_HUTANG):
            return "HUTANG"
        if any(k in t for k in self.KW_PIUTANG):
            return "PIUTANG"
        if re.search(self.POLA_PIUTANG, t):
            return "PIUTANG"
        if any(k in t for k in self.KW_LAPORAN):
            return "LAPORAN"
        if any(k in t for k in self.KW_IN):
            return "PEMASUKAN"
        if any(k in t for k in self.KW_OUT):
            return "PENGELUARAN"
        return "UNKNOWN"

    def guess_category(self, text: str) -> str:
        t = text.lower()
        for kw, cat in self.CAT_MAP.items():
            if kw in t:
                return cat
        return "Lainnya"

    def parse_portfolio(self, text: str) -> dict:
        t = text.lower()
        result = {"action": "jual" if "jual" in t else "beli", "jenis": "Saham", "ticker": "-", "lot": 1, "harga": 0}
        if any(k in t for k in ["btc", "bitcoin", "eth", "crypto"]):
            result["jenis"]  = "Crypto"
            result["ticker"] = "BTC" if "btc" in t or "bitcoin" in t else "ETH"
        elif any(k in t for k in ["emas", "gold", "antam"]):
            result["jenis"]  = "Emas/Komoditas"
            result["ticker"] = "XAU"
        elif any(k in t for k in ["reksa", "reksadana"]):
            result["jenis"]  = "Reksa Dana"
            result["ticker"] = "-"
        else:
            m = re.search(r"\b([A-Z]{2,6})\b", text.upper())
            if m:
                result["ticker"] = m.group(1)
        m_lot = re.search(r"(\d+)\s*lot", t)
        if m_lot:
            result["lot"] = int(m_lot.group(1)) * 100
        nums = [float(x.replace(",", "")) for x in re.findall(r"[\d,]+", text)
                if float(x.replace(",", "")) > 100]
        if nums:
            result["harga"] = nums[-1]
        return result


parser = Parser()


# ─────────────────────────────────────────────────────────────
# SHEETS WRITERS  (FIX #3: data benar-benar ditulis ke sheet)
# ─────────────────────────────────────────────────────────────
def next_id(ws, prefix: str) -> str:
    vals = ws.col_values(1)
    nums = [int(v.split("-")[1]) for v in vals if re.match(rf"^{prefix}-\d+$", v)]
    return f"{prefix}-{max(nums)+1:03d}" if nums else f"{prefix}-001"


def tulis_pengeluaran(data: dict) -> str:
    wb  = get_sheet()
    ws  = wb.worksheet("📤 PENGELUARAN")
    rid = next_id(ws, "PGR")
    now = datetime.now()
    ws.append_row([
        rid, now.strftime("%d/%m/%Y"), now.strftime("%A"),
        data.get("amount", 0), data.get("category", "Lainnya"), "",
        data.get("description", ""), data.get("method", "Cash"), "",
        "Tidak", "Tidak", "-", f"Telegram: {data.get('raw', '')}",
    ])
    return rid


def tulis_pemasukan(data: dict) -> str:
    wb  = get_sheet()
    ws  = wb.worksheet("📥 PEMASUKAN")
    rid = next_id(ws, "PMS")
    now = datetime.now()
    cat_map = {
        "gaji": "Gaji/Tetap", "bonus": "Bonus",
        "dividen": "Investasi/Dividen", "dividend": "Investasi/Dividen",
        "freelance": "Freelance", "jual": "Jual Barang",
        "proyek": "Freelance", "project": "Freelance",
    }
    category = "Lainnya"
    for k, v in cat_map.items():
        if k in data.get("raw", "").lower():
            category = v
            break
    ws.append_row([
        rid, now.strftime("%d/%m/%Y"), now.strftime("%A"),
        data.get("amount", 0), category, data.get("description", ""),
        "", "Tidak", "Tidak", "-", f"Telegram: {data.get('raw', '')}",
    ])
    return rid


def tulis_hutang_piutang(data: dict) -> str:
    wb  = get_sheet()
    ws  = wb.worksheet("💳 HUTANG PIUTANG")
    rid = next_id(ws, "HTP")
    now = datetime.now()
    ws.append_row([
        rid, now.strftime("%d/%m/%Y"),
        data.get("pihak", "-"), data.get("amount", 0), "",
        data.get("tipe", "Hutang"), 0, "Aktif", "0%", 0,
        data.get("description", ""), f"Telegram: {data.get('raw', '')}",
    ])
    return rid


def tulis_portfolio(data: dict) -> str:
    wb  = get_sheet()
    ws  = wb.worksheet("📈 PORTFOLIO")
    rid = next_id(ws, "PRT")
    now = datetime.now()
    ws.append_row([
        rid, data.get("nama", data.get("ticker", "-")),
        data.get("jenis", "Saham"), data.get("ticker", "-"),
        now.strftime("%d/%m/%Y"), data.get("lot", 1),
        data.get("harga", 0), data.get("harga", 0), 0,
        "", "", "", "", "", "Hold",
        f"Telegram: {data.get('raw', '')}",
    ])
    return rid


def tulis_log(msg, tipe, amount, cat, target, status, error=""):
    try:
        wb  = get_sheet()
        ws  = wb.worksheet("🤖 LOG TELEGRAM")
        now = datetime.now().strftime("%d/%m/%y %H:%M")
        vals = ws.col_values(1)
        num  = len([v for v in vals if v.strip().isdigit()]) + 1
        ws.append_row([num, now, msg[:100], tipe, amount, cat, target, status, error])
    except Exception as e:
        logger.warning(f"Log gagal: {e}")


# ─────────────────────────────────────────────────────────────
# LAPORAN  (FIX #2: baca data nyata dari sheet)
# ─────────────────────────────────────────────────────────────
def _parse_tgl(s):
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y")
    except:
        return None

def _parse_num(s):
    try:
        return float(re.sub(r"[^\d.]", "", str(s)) or 0)
    except:
        return 0.0


def ambil_laporan() -> str:
    try:
        wb  = get_sheet()
        now = datetime.now()
        bln, thn = now.month, now.year

        ws_out   = wb.worksheet("📤 PENGELUARAN")
        rows_out = ws_out.get_all_values()[7:]
        total_out, trx_out = 0.0, 0
        for row in rows_out:
            if len(row) < 4 or not row[1]:
                continue
            tgl = _parse_tgl(row[1])
            if tgl and tgl.month == bln and tgl.year == thn:
                total_out += _parse_num(row[3])
                trx_out   += 1

        ws_inc   = wb.worksheet("📥 PEMASUKAN")
        rows_inc = ws_inc.get_all_values()[7:]
        total_in, trx_in = 0.0, 0
        for row in rows_inc:
            if len(row) < 4 or not row[1]:
                continue
            tgl = _parse_tgl(row[1])
            if tgl and tgl.month == bln and tgl.year == thn:
                total_in += _parse_num(row[3])
                trx_in   += 1

        ws_debt   = wb.worksheet("💳 HUTANG PIUTANG")
        rows_debt = ws_debt.get_all_values()[7:]
        total_hutang, total_piutang = 0.0, 0.0
        for row in rows_debt:
            if len(row) < 8:
                continue
            tipe   = str(row[5]).strip()
            status = str(row[7]).strip()
            sisa   = max(0, _parse_num(row[3]) - _parse_num(row[6]))
            if status == "Aktif":
                if tipe == "Hutang":
                    total_hutang += sisa
                elif tipe == "Piutang":
                    total_piutang += sisa

        saldo = total_in - total_out
        icon  = "📈" if saldo >= 0 else "📉"
        bln_nama = now.strftime("%B %Y")

        return (
            f"📊 *RINGKASAN — {bln_nama}*\n\n"
            f"💰 Pemasukan    : *Rp{total_in:,.0f}* ({trx_in} trx)\n"
            f"💸 Pengeluaran  : *Rp{total_out:,.0f}* ({trx_out} trx)\n"
            f"{icon} Saldo Bersih  : *Rp{saldo:,.0f}*\n\n"
            f"💳 Hutang Aktif  : *Rp{total_hutang:,.0f}*\n"
            f"💵 Piutang Aktif : *Rp{total_piutang:,.0f}*\n\n"
            f"_Data dari Google Sheets — {now.strftime('%d/%m/%Y %H:%M')}_"
        )
    except Exception as e:
        logger.error(f"Laporan error: {e}")
        return f"⚠️ Gagal ambil laporan: {e}"


# ─────────────────────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(
        "👋 *Bot Keuangan Pribadi Aktif!*\n\n"
        "Ketik bebas:\n"
        "• `beli kopi 15rb` → pengeluaran\n"
        "• `nonton bioskop 40rb` → pengeluaran\n"
        "• `gaji masuk 8jt` → pemasukan\n"
        "• `hutang ke budi 500rb` → hutang\n"
        "• `andi pinjam 200rb` → piutang\n"
        "• `beli BBCA 10 lot 9500` → portfolio\n"
        "• `saldo` / `laporan` → ringkasan dari Sheets\n\n"
        "Semua langsung masuk Google Sheets! 🚀",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    tipe   = parser.detect_type(text)
    amount = parser.parse_amount(text)

    try:
        if tipe == "LAPORAN":
            await update.message.reply_text("⏳ Mengambil data dari Sheets...")
            await update.message.reply_text(ambil_laporan(), parse_mode="Markdown")
            tulis_log(text, "LAPORAN", 0, "-", "DASHBOARD", "✅ Berhasil")

        elif tipe == "PENGELUARAN":
            cat = parser.guess_category(text)
            rid = tulis_pengeluaran({"amount": amount, "category": cat, "description": text, "raw": text})
            tulis_log(text, "PENGELUARAN", amount, cat, "📤 PENGELUARAN", "✅ Berhasil")
            await update.message.reply_text(
                f"✅ *Pengeluaran dicatat!*\n"
                f"ID: `{rid}` | Rp{amount:,.0f}\n"
                f"Kategori: {cat}\n_{text}_",
                parse_mode="Markdown"
            )

        elif tipe == "PEMASUKAN":
            rid = tulis_pemasukan({"amount": amount, "description": text, "raw": text})
            tulis_log(text, "PEMASUKAN", amount, "Pemasukan", "📥 PEMASUKAN", "✅ Berhasil")
            await update.message.reply_text(
                f"✅ *Pemasukan dicatat!*\nID: `{rid}` | Rp{amount:,.0f}\n_{text}_",
                parse_mode="Markdown"
            )

        elif tipe == "HUTANG":
            m = re.search(r"(?:hutang ke|ngutang ke|pinjam ke|utang ke)\s+(\w+)", text, re.I)
            pihak = m.group(1).capitalize() if m else "-"
            rid = tulis_hutang_piutang({"amount": amount, "tipe": "Hutang", "pihak": pihak, "description": text, "raw": text})
            tulis_log(text, "HUTANG", amount, "Hutang", "💳 HUTANG PIUTANG", "✅ Berhasil")
            await update.message.reply_text(
                f"💳 *Hutang dicatat!*\nID: `{rid}` | Ke: {pihak} | Rp{amount:,.0f}",
                parse_mode="Markdown"
            )

        elif tipe == "PIUTANG":
            m = re.search(r"^(\w+)\s+pinjam", text, re.I)
            pihak = m.group(1).capitalize() if m else "-"
            rid = tulis_hutang_piutang({"amount": amount, "tipe": "Piutang", "pihak": pihak, "description": text, "raw": text})
            tulis_log(text, "PIUTANG", amount, "Piutang", "💳 HUTANG PIUTANG", "✅ Berhasil")
            await update.message.reply_text(
                f"💰 *Piutang dicatat!*\nID: `{rid}` | Dari: {pihak} | Rp{amount:,.0f}",
                parse_mode="Markdown"
            )

        elif tipe == "PORTFOLIO":
            pd = parser.parse_portfolio(text)
            pd["raw"]  = text
            pd["nama"] = pd.get("ticker", "?")
            rid = tulis_portfolio(pd)
            tulis_log(text, "PORTFOLIO", pd.get("harga", 0) * pd.get("lot", 1),
                      pd.get("jenis", "-"), "📈 PORTFOLIO", "✅ Berhasil")
            await update.message.reply_text(
                f"📈 *Portfolio diupdate!*\n"
                f"ID: `{rid}` | {pd.get('action','beli').upper()} {pd.get('ticker','-')}\n"
                f"Lot: {pd.get('lot',1)} | Harga: Rp{pd.get('harga',0):,.0f}",
                parse_mode="Markdown"
            )

        else:
            keyboard = [
                [
                    InlineKeyboardButton("💸 Pengeluaran", callback_data=f"out|{amount}|{text[:60]}"),
                    InlineKeyboardButton("💰 Pemasukan",   callback_data=f"inc|{amount}|{text[:60]}"),
                ],
                [
                    InlineKeyboardButton("💳 Hutang",   callback_data=f"debt|{amount}|{text[:60]}"),
                    InlineKeyboardButton("📈 Portfolio", callback_data=f"port|0|{text[:60]}"),
                ],
                [InlineKeyboardButton("❌ Abaikan", callback_data="ignore|0|")],
            ]
            await update.message.reply_text(
                f"🤔 Mau dicatat sebagai apa?\n_{text[:80]}_",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error: {e}")
        tulis_log(text, tipe, amount, "-", "-", "❌ Error", str(e))
        await update.message.reply_text(f"❌ Error: `{e}`", parse_mode="Markdown")


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("|", 2)
    action = parts[0]
    amount = float(parts[1]) if parts[1] else 0
    raw    = parts[2] if len(parts) > 2 else ""

    if action == "ignore":
        await query.edit_message_text("❌ Diabaikan.")
    elif action == "out":
        cat = parser.guess_category(raw)
        rid = tulis_pengeluaran({"amount": amount, "category": cat, "description": raw, "raw": raw})
        await query.edit_message_text(f"✅ Pengeluaran ({rid}) Rp{amount:,.0f} — {cat}")
    elif action == "inc":
        rid = tulis_pemasukan({"amount": amount, "description": raw, "raw": raw})
        await query.edit_message_text(f"✅ Pemasukan ({rid}) Rp{amount:,.0f}")
    elif action == "debt":
        rid = tulis_hutang_piutang({"amount": amount, "tipe": "Hutang", "pihak": "-", "raw": raw})
        await query.edit_message_text(f"💳 Hutang ({rid}) Rp{amount:,.0f}")
    elif action == "port":
        pd  = parser.parse_portfolio(raw)
        pd["raw"]  = raw
        pd["nama"] = pd.get("ticker", "?")
        rid = tulis_portfolio(pd)
        await query.edit_message_text(f"📈 Portfolio ({rid}) dicatat")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    caption = (update.message.caption or "").strip()
    if caption:
        tipe   = parser.detect_type(caption)
        amount = parser.parse_amount(caption)
        if tipe == "PENGELUARAN" and amount > 0:
            cat = parser.guess_category(caption)
            rid = tulis_pengeluaran({"amount": amount, "category": cat, "description": caption, "raw": caption})
            await update.message.reply_text(
                f"📷✅ *Pengeluaran dari foto dicatat!*\nID: `{rid}` | Rp{amount:,.0f} | {cat}",
                parse_mode="Markdown"
            )
            return
    await update.message.reply_text(
        "📷 Foto diterima! Kirim teks keterangan:\nContoh: `bayar belanja 125rb`"
    )


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN tidak ada!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("Bot Keuangan Pribadi berjalan!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
