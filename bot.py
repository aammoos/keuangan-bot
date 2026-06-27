"""
╔══════════════════════════════════════════════════════╗
║     BOT KEUANGAN PRIBADI — Telegram + Excel          ║
║     Gratis | Aman | No-Server via Railway/Render     ║
╚══════════════════════════════════════════════════════╝

Setup cepat:
1. Isi BOT_TOKEN & CHAT_ID di .env
2. Upload Keuangan_Pribadi_Telegram.xlsx ke Google Drive
   (share as "Anyone with link can edit")
3. Isi SHEET_ID di .env (dari URL Google Sheets)
4. Deploy ke Railway.app (gratis, 500 jam/bulan)
"""

import os, re, json, logging
from datetime import datetime, date
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
ALLOWED_ID  = int(os.getenv("CHAT_ID", "0"))   # hanya kamu yang bisa akses
SHEET_ID    = os.getenv("SHEET_ID")
CREDS_FILE  = os.getenv("GOOGLE_CREDS", "credentials.json")

# ─── Google Sheets Setup ─────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_sheet():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    gc    = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)

# ─── Security: tolak semua selain pemilik ────────────────────
def is_owner(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_ID

# ─── Parser Pesan Natural Language ──────────────────────────
class Parser:
    """
    Mendeteksi tipe transaksi dan ekstrak angka dari pesan bebas.
    Contoh:
      "beli kopi 15rb"          → PENGELUARAN 15000
      "gaji masuk 8.5jt"        → PEMASUKAN 8500000
      "hutang ke budi 500rb"    → HUTANG 500000
      "beli BBCA 10 lot 9500"   → PORTFOLIO saham
      "saldo"                   → LAPORAN
    """

    KEYWORDS_OUT = [
        "beli", "bayar", "habis", "keluar", "spent", "bayarin",
        "jajan", "makan", "nongkrong", "transfer ke", "kirim ke",
        "tagihan", "cicilan", "isi", "top up", "topup",
    ]
    KEYWORDS_IN = [
        "gaji", "masuk", "dapet", "dapat", "terima", "income",
        "earn", "bonus", "dividen", "dividend", "cashback",
        "jual", "laku", "dibayar", "profit", "cair",
    ]
    KEYWORDS_HUTANG = ["hutang ke", "ngutang", "pinjam ke", "minjem ke"]
    KEYWORDS_PIUTANG = ["piutangin", "pinjemin", "minjemin", "pinjam", "utangin"]
    KEYWORDS_PORTFOLIO = [
        "beli saham", "beli btc", "beli bitcoin", "beli crypto",
        "beli emas", "beli reksadana", "beli reksa", "beli obligasi",
        "jual saham", "jual btc", "update harga", "update portfolio",
        "lot", "lembar saham",
    ]
    KEYWORDS_REPORT = [
        "laporan", "report", "saldo", "ringkasan", "summary",
        "net worth", "berapa", "rekap", "status keuangan",
    ]

    # Kategori otomatis berdasarkan kata kunci
    CATEGORY_MAP = {
        "makan": "Makan & Minum", "minum": "Makan & Minum",
        "kopi": "Makan & Minum", "sarapan": "Makan & Minum",
        "makan siang": "Makan & Minum", "makan malam": "Makan & Minum",
        "resto": "Makan & Minum", "warteg": "Makan & Minum",
        "indomie": "Makan & Minum", "nasi": "Makan & Minum",
        "bensin": "Transportasi", "bbm": "Transportasi",
        "gojek": "Transportasi", "grab": "Transportasi",
        "ojol": "Transportasi", "parkir": "Transportasi",
        "tol": "Transportasi", "busway": "Transportasi",
        "baju": "Belanja", "sepatu": "Belanja", "celana": "Belanja",
        "shopee": "Belanja", "tokopedia": "Belanja", "lazada": "Belanja",
        "netflix": "Hiburan", "spotify": "Hiburan", "youtube": "Hiburan",
        "game": "Hiburan", "bioskop": "Hiburan", "nonton": "Hiburan",
        "obat": "Kesehatan", "dokter": "Kesehatan", "rs": "Kesehatan",
        "klinik": "Kesehatan", "apotek": "Kesehatan",
        "listrik": "Tagihan", "air": "Tagihan", "internet": "Tagihan",
        "pulsa": "Tagihan", "pln": "Tagihan",
        "buku": "Pendidikan", "kursus": "Pendidikan", "les": "Pendidikan",
        "rumah": "Rumah Tangga", "kos": "Rumah Tangga", "kontrakan": "Rumah Tangga",
    }

    def parse_amount(self, text: str) -> float | None:
        """Ekstrak angka dari teks (15rb → 15000, 8.5jt → 8500000)"""
        text = text.lower().replace(",", ".").replace(".", "")
        # Cari pola: angka + satuan (rb/k/ribu/jt/juta/m/miliar)
        patterns = [
            (r"(\d+(?:\.\d+)?)\s*(?:jt|juta|jt)", 1_000_000),
            (r"(\d+(?:\.\d+)?)\s*(?:rb|ribu|k)", 1_000),
            (r"(\d+(?:\.\d+)?)\s*(?:m|miliar|milyar)", 1_000_000_000),
            (r"rp\.?\s*(\d[\d\.]*)", 1),
            (r"(\d{4,})", 1),  # angka 4+ digit langsung
        ]
        # restore dot for decimal
        text_orig = text.lower().replace(",", ".")
        for pattern, multiplier in patterns[:-1]:
            m = re.search(pattern, text_orig)
            if m:
                return float(m.group(1).replace(".", "")) * multiplier
        # bare number
        m = re.search(r"(\d[\d\.]+)", text_orig)
        if m:
            val = float(m.group(1).replace(".", "")) if "." not in m.group(1)[-3:] else float(m.group(1))
            return val if val >= 100 else val * 1000  # heuristik: <100 anggap ribuan
        return None

    def guess_category(self, text: str) -> str:
        text_lower = text.lower()
        for keyword, category in self.CATEGORY_MAP.items():
            if keyword in text_lower:
                return category
        return "Lainnya"

    def detect_type(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in self.KEYWORDS_PORTFOLIO):
            return "PORTFOLIO"
        if any(k in t for k in self.KEYWORDS_HUTANG):
            return "HUTANG"
        if any(k in t for k in self.KEYWORDS_PIUTANG):
            return "PIUTANG"
        if any(k in t for k in self.KEYWORDS_REPORT):
            return "LAPORAN"
        if any(k in t for k in self.KEYWORDS_IN):
            return "PEMASUKAN"
        if any(k in t for k in self.KEYWORDS_OUT):
            return "PENGELUARAN"
        return "UNKNOWN"

    def parse_portfolio_msg(self, text: str) -> dict:
        """Parse pesan portfolio: 'beli BBCA 10 lot 9500'"""
        t = text.lower()
        result = {"action": "beli" if "beli" in t else "jual"}
        
        # Deteksi jenis aset
        if any(k in t for k in ["btc", "bitcoin", "crypto", "eth", "ethereum"]):
            result["jenis"] = "Crypto"
            result["ticker"] = "BTC" if "btc" in t or "bitcoin" in t else "ETH"
        elif any(k in t for k in ["emas", "gold", "antam"]):
            result["jenis"] = "Emas/Komoditas"
            result["ticker"] = "XAU"
        elif any(k in t for k in ["reksa", "reksadana", "mutual fund"]):
            result["jenis"] = "Reksa Dana"
            result["ticker"] = "-"
        else:
            result["jenis"] = "Saham"
            # Cari ticker (huruf kapital 2-6 karakter)
            ticker = re.search(r'\b([A-Z]{2,6})\b', text.upper())
            result["ticker"] = ticker.group(1) if ticker else "-"

        # Lot
        lot_m = re.search(r'(\d+)\s*lot', t)
        result["lot"] = int(lot_m.group(1)) * 100 if lot_m else 1

        # Harga
        amounts = re.findall(r'[\d,\.]+', text)
        nums = [float(x.replace(",","")) for x in amounts if float(x.replace(",","")) > 100]
        result["harga"] = nums[-1] if nums else 0

        return result

parser = Parser()

# ─── Google Sheets Writer ────────────────────────────────────
def next_id(ws, prefix: str, id_col: int = 1) -> str:
    """Generate ID berikutnya: PGR-001, PMS-002, dst"""
    vals = ws.col_values(id_col)
    nums = [int(v.split("-")[1]) for v in vals if re.match(rf"^{prefix}-\d+$", v)]
    next_n = max(nums) + 1 if nums else 1
    return f"{prefix}-{next_n:03d}"

def append_pengeluaran(data: dict):
    wb = get_sheet()
    ws = wb.worksheet("📤 PENGELUARAN")
    now = datetime.now()
    row_id = next_id(ws, "PGR")
    row = [
        row_id,
        now.strftime("%d/%m/%Y"),
        now.strftime("%A"),
        data.get("amount", 0),
        data.get("category", "Lainnya"),
        "",                          # sub-kategori (isi manual jika mau)
        data.get("description", ""),
        data.get("method", "Cash"),
        "",                          # merchant
        "Tidak",
        "Tidak",
        "-",
        f"Telegram: {data.get('raw', '')}",
    ]
    ws.append_row(row)
    return row_id

def append_pemasukan(data: dict):
    wb = get_sheet()
    ws = wb.worksheet("📥 PEMASUKAN")
    now = datetime.now()
    row_id = next_id(ws, "PMS")
    cat_map = {
        "gaji": "Gaji/Tetap", "bonus": "Bonus",
        "dividen": "Investasi/Dividen", "dividend": "Investasi/Dividen",
        "freelance": "Freelance", "jual": "Jual Barang",
    }
    category = "Lainnya"
    for k, v in cat_map.items():
        if k in data.get("raw", "").lower():
            category = v
            break
    row = [
        row_id,
        now.strftime("%d/%m/%Y"),
        now.strftime("%A"),
        data.get("amount", 0),
        category,
        data.get("description", ""),
        "",
        "Tidak",
        "Tidak",
        "-",
        f"Telegram: {data.get('raw', '')}",
    ]
    ws.append_row(row)
    return row_id

def append_hutang_piutang(data: dict):
    wb = get_sheet()
    ws = wb.worksheet("💳 HUTANG PIUTANG")
    now = datetime.now()
    row_id = next_id(ws, "HTP")
    row = [
        row_id,
        now.strftime("%d/%m/%Y"),
        data.get("pihak", "-"),
        data.get("amount", 0),
        "",             # jatuh tempo (isi manual)
        data.get("tipe", "Hutang"),
        0,
        "Aktif",
        "0%",
        0,
        data.get("description", ""),
        f"Telegram: {data.get('raw', '')}",
    ]
    ws.append_row(row)
    return row_id

def append_portfolio(data: dict):
    wb = get_sheet()
    ws = wb.worksheet("📈 PORTFOLIO")
    now = datetime.now()
    row_id = next_id(ws, "PRT")
    row = [
        row_id,
        data.get("nama", data.get("ticker", "-")),
        data.get("jenis", "Saham"),
        data.get("ticker", "-"),
        now.strftime("%d/%m/%Y"),
        data.get("lot", 1),
        data.get("harga", 0),
        data.get("harga", 0),   # harga skrng = harga beli awalnya
        0,                       # biaya
        "",                      # modal (formula)
        "",                      # nilai skrng (formula)
        "",                      # P/L (formula)
        "",                      # return (formula)
        "",                      # bobot (formula)
        "Hold",
        f"Telegram: {data.get('raw', '')}",
    ]
    ws.append_row(row)
    return row_id

def log_telegram(msg: str, tipe: str, amount: float, category: str, target: str, status: str, error: str = ""):
    try:
        wb = get_sheet()
        ws = wb.worksheet("🤖 LOG TELEGRAM")
        now = datetime.now().strftime("%d/%m/%y %H:%M")
        vals = ws.col_values(1)
        num = len([v for v in vals if v.strip().isdigit()]) + 1
        ws.append_row([num, now, msg[:100], tipe, amount, category, target, status, error])
    except Exception as e:
        logger.error(f"Log error: {e}")

def get_summary() -> str:
    """Ambil ringkasan dari sheet Dashboard"""
    try:
        wb    = get_sheet()
        ws_d  = wb.worksheet("📊 DASHBOARD")
        ws_p  = wb.worksheet("📈 PORTFOLIO")
        
        pemasukan   = ws_d.acell("A7").value or "0"
        pengeluaran = ws_d.acell("C7").value or "0"
        saldo       = ws_d.acell("E7").value or "0"
        total_asset = ws_d.acell("G7").value or "0"
        hutang      = ws_d.acell("I7").value or "0"
        net_worth   = ws_d.acell("K7").value or "0"

        def fmt(v):
            try:
                return f"Rp{float(str(v).replace(',','').replace('Rp',''))/1_000_000:.2f}jt"
            except:
                return str(v)

        return (
            f"📊 *RINGKASAN KEUANGAN BULAN INI*\n\n"
            f"💰 Pemasukan   : {fmt(pemasukan)}\n"
            f"💸 Pengeluaran : {fmt(pengeluaran)}\n"
            f"📈 Saldo Bersih: {fmt(saldo)}\n\n"
            f"🏦 Total Portfolio : {fmt(total_asset)}\n"
            f"💳 Hutang Aktif    : {fmt(hutang)}\n"
            f"💎 Net Worth (Est.): {fmt(net_worth)}\n\n"
            f"_Update: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
        )
    except Exception as e:
        return f"⚠️ Gagal ambil data: {e}"

# ─── Handlers ────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(
        "👋 *Bot Keuangan Pribadi aktif!*\n\n"
        "Ketik apa saja secara natural:\n"
        "• `beli kopi 15rb` → catat pengeluaran\n"
        "• `gaji masuk 8.5jt` → catat pemasukan\n"
        "• `hutang ke budi 500rb` → catat hutang\n"
        "• `beli BBCA 10 lot 9500` → update portfolio\n"
        "• `saldo` / `laporan` → ringkasan keuangan\n\n"
        "Semua langsung masuk ke Google Sheets! 🚀",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    text = update.message.text or ""
    if not text:
        await update.message.reply_text("Kirim teks ya, bukan file/foto dulu 🙏")
        return

    msg_type = parser.detect_type(text)
    amount   = parser.parse_amount(text) or 0

    try:
        if msg_type == "LAPORAN":
            summary = get_summary()
            await update.message.reply_text(summary, parse_mode="Markdown")
            log_telegram(text, "LAPORAN", 0, "-", "DASHBOARD", "✅ Berhasil")
            return

        elif msg_type == "PENGELUARAN":
            cat = parser.guess_category(text)
            row_id = append_pengeluaran({
                "amount": amount,
                "category": cat,
                "description": text,
                "raw": text,
            })
            log_telegram(text, "PENGELUARAN", amount, cat, "📤 PENGELUARAN", "✅ Berhasil")
            await update.message.reply_text(
                f"✅ *Pengeluaran dicatat!*\n"
                f"ID: `{row_id}`\n"
                f"Jumlah: Rp{amount:,.0f}\n"
                f"Kategori: {cat}\n"
                f"Keterangan: _{text}_",
                parse_mode="Markdown"
            )

        elif msg_type == "PEMASUKAN":
            row_id = append_pemasukan({"amount": amount, "description": text, "raw": text})
            log_telegram(text, "PEMASUKAN", amount, "Pemasukan", "📥 PEMASUKAN", "✅ Berhasil")
            await update.message.reply_text(
                f"✅ *Pemasukan dicatat!*\n"
                f"ID: `{row_id}`\n"
                f"Jumlah: Rp{amount:,.0f}\n"
                f"Keterangan: _{text}_",
                parse_mode="Markdown"
            )

        elif msg_type in ("HUTANG", "PIUTANG"):
            # Coba ekstrak nama pihak
            pihak = "-"
            m = re.search(r"(?:ke|dari|sama)\s+(\w+)", text, re.I)
            if m:
                pihak = m.group(1).capitalize()
            elif msg_type == "PIUTANG":
                m2 = re.search(r"(\w+)\s+pinjam", text, re.I)
                if m2:
                    pihak = m2.group(1).capitalize()

            row_id = append_hutang_piutang({
                "amount": amount,
                "tipe": msg_type,
                "pihak": pihak,
                "description": text,
                "raw": text,
            })
            emoji = "💳" if msg_type == "HUTANG" else "💰"
            log_telegram(text, msg_type, amount, msg_type, "💳 HUTANG PIUTANG", "✅ Berhasil")
            await update.message.reply_text(
                f"{emoji} *{msg_type} dicatat!*\n"
                f"ID: `{row_id}`\n"
                f"Pihak: {pihak}\n"
                f"Jumlah: Rp{amount:,.0f}\n"
                f"Status: Aktif\n"
                f"Keterangan: _{text}_",
                parse_mode="Markdown"
            )

        elif msg_type == "PORTFOLIO":
            port_data = parser.parse_portfolio_msg(text)
            port_data["raw"] = text
            port_data["nama"] = port_data.get("ticker", "?")
            row_id = append_portfolio(port_data)
            log_telegram(text, "PORTFOLIO", port_data.get("harga", 0) * port_data.get("lot", 1),
                         port_data.get("jenis", "-"), "📈 PORTFOLIO", "✅ Berhasil")
            await update.message.reply_text(
                f"📈 *Portfolio diupdate!*\n"
                f"ID: `{row_id}`\n"
                f"Aksi: {port_data.get('action','beli').upper()}\n"
                f"Ticker: {port_data.get('ticker', '-')}\n"
                f"Jenis: {port_data.get('jenis', '-')}\n"
                f"Lot/Unit: {port_data.get('lot', 1)}\n"
                f"Harga: Rp{port_data.get('harga', 0):,.0f}",
                parse_mode="Markdown"
            )

        else:
            # Tidak dikenali — tanya konfirmasi
            keyboard = [
                [
                    InlineKeyboardButton("💸 Pengeluaran", callback_data=f"out|{amount}|{text[:50]}"),
                    InlineKeyboardButton("💰 Pemasukan",   callback_data=f"inc|{amount}|{text[:50]}"),
                ],
                [
                    InlineKeyboardButton("💳 Hutang",  callback_data=f"debt|{amount}|{text[:50]}"),
                    InlineKeyboardButton("📈 Portfolio", callback_data=f"port|0|{text[:50]}"),
                ],
                [InlineKeyboardButton("❌ Abaikan", callback_data="ignore|0|")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"🤔 Pesan *\"{text[:60]}\"* ini mau dicatat sebagai apa?",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error: {e}")
        log_telegram(text, msg_type, amount, "-", "-", "❌ Error", str(e))
        await update.message.reply_text(f"⚠️ Error: {e}\n\nCoba lagi atau cek log.")

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("|", 2)
    action = parts[0]
    amount = float(parts[1]) if parts[1] else 0
    raw    = parts[2] if len(parts) > 2 else ""

    if action == "ignore":
        await query.edit_message_text("❌ Diabaikan.")
        return
    elif action == "out":
        cat = parser.guess_category(raw)
        row_id = append_pengeluaran({"amount": amount, "category": cat, "description": raw, "raw": raw})
        await query.edit_message_text(f"✅ Dicatat sebagai pengeluaran ({row_id}) — Rp{amount:,.0f}")
    elif action == "inc":
        row_id = append_pemasukan({"amount": amount, "description": raw, "raw": raw})
        await query.edit_message_text(f"✅ Dicatat sebagai pemasukan ({row_id}) — Rp{amount:,.0f}")
    elif action == "debt":
        row_id = append_hutang_piutang({"amount": amount, "tipe": "Hutang", "pihak": "-", "raw": raw})
        await query.edit_message_text(f"✅ Dicatat sebagai hutang ({row_id}) — Rp{amount:,.0f}")
    elif action == "port":
        port_data = parser.parse_portfolio_msg(raw)
        port_data["raw"] = raw
        port_data["nama"] = port_data.get("ticker", "?")
        row_id = append_portfolio(port_data)
        await query.edit_message_text(f"✅ Dicatat di portfolio ({row_id})")

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle foto nota/screenshot — simpan catatan manual"""
    if not is_owner(update):
        return
    caption = update.message.caption or ""
    await update.message.reply_text(
        f"📷 Foto diterima!\n"
        f"Caption: _{caption or 'kosong'}_\n\n"
        f"Saat ini foto butuh diproses manual.\n"
        f"Kirim jumlah & keterangan sebagai teks ya:\n"
        f"Contoh: `bayar belanja 125rb`",
        parse_mode="Markdown"
    )

# ─── Main ────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", lambda u, c: handle_message(
        type("obj", (object,), {"message": type("m", (object,), {
            "text": "saldo", "reply_text": u.message.reply_text,
            "effective_user": u.effective_user
        })(), "effective_user": u.effective_user})(), c
    )))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("🚀 Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
