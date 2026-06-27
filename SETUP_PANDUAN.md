# 🚀 PANDUAN SETUP LENGKAP — Bot Keuangan Pribadi

> Gratis · Aman · Auto-update Google Sheets dari Telegram

---

## GAMBARAN ARSITEKTUR

```
Kamu di Telegram
      │  chat bebas: "beli kopi 15rb"
      ▼
  Bot Telegram (Railway - GRATIS)
      │  parse pesan → deteksi tipe + jumlah
      ▼
  Google Sheets (Excel kamu online)
      │  auto-append ke sheet yang tepat
      ▼
  Formula Excel hitung otomatis
  Dashboard update real-time ✅
```

**Kenapa Google Sheets bukan file .xlsx lokal?**
- Bisa diakses dari mana saja (HP, laptop)
- Bot bisa baca + tulis tanpa upload ulang
- Gratis, tidak perlu server storage
- Tetap bisa diexport ke .xlsx kapan saja

---

## LANGKAH 1 — Buat Telegram Bot (5 menit)

1. Buka Telegram → cari **@BotFather**
2. Ketik `/newbot`
3. Beri nama: `Keuangan Saya Bot`
4. Beri username: `keuangansaya_bot` (harus unik, tambah angka jika perlu)
5. **Salin API Token** yang diberikan → simpan di .env sebagai `BOT_TOKEN`
6. Cari **@userinfobot** di Telegram → kirim pesan apapun
7. **Salin Chat ID** kamu → simpan di .env sebagai `CHAT_ID`

---

## LANGKAH 2 — Setup Google Sheets (10 menit)

### 2a. Upload Excel ke Google Drive
1. Buka [drive.google.com](https://drive.google.com)
2. Drag & drop file `Keuangan_Pribadi_Telegram.xlsx`
3. Klik kanan → **Open with Google Sheets**
4. Salin **Sheet ID** dari URL:
   ```
   https://docs.google.com/spreadsheets/d/[INI_SHEET_ID]/edit
   ```
5. Simpan di `.env` sebagai `SHEET_ID`

### 2b. Buat Google Service Account (agar bot bisa akses sheets)
1. Buka [console.cloud.google.com](https://console.cloud.google.com)
2. Buat project baru (atau pakai yang ada)
3. Aktifkan **Google Sheets API** dan **Google Drive API**:
   - Menu → APIs & Services → Library → search "Sheets" → Enable
   - Ulangi untuk "Drive API"
4. Menu → IAM & Admin → **Service Accounts** → Create Service Account
   - Nama: `bot-keuangan`
   - Role: **Editor**
5. Klik service account → tab **Keys** → Add Key → JSON
6. Download file JSON → rename jadi `credentials.json`
7. Simpan di folder yang sama dengan `bot.py`

### 2c. Share Sheet ke Service Account
1. Buka file `credentials.json` → cari field `"client_email"`
   Contoh: `bot-keuangan@project-123.iam.gserviceaccount.com`
2. Buka Google Sheets kamu → Share → paste email tadi → pilih **Editor**

---

## LANGKAH 3 — Deploy ke Railway (5 menit, GRATIS)

### 3a. Push ke GitHub dulu
```bash
git init
git add .
git commit -m "Bot keuangan pertama"
git remote add origin https://github.com/username/keuangan-bot.git
git push -u origin main
```

### 3b. Deploy di Railway
1. Buka [railway.app](https://railway.app) → Login dengan GitHub
2. **New Project** → Deploy from GitHub repo → pilih repo kamu
3. Tab **Variables** → tambahkan:
   ```
   BOT_TOKEN = [token dari BotFather]
   CHAT_ID   = [chat ID kamu]
   SHEET_ID  = [ID Google Sheets]
   ```
4. Untuk `credentials.json`: tab Variables → tambah variable `GOOGLE_CREDS_JSON`
   dengan isi seluruh konten JSON credentials → lalu di `bot.py` load dari env:
   ```python
   # Alternatif jika tidak bisa upload file:
   import json, tempfile
   creds_json = os.getenv("GOOGLE_CREDS_JSON")
   if creds_json:
       with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
           json.dump(json.loads(creds_json), f)
           os.environ["GOOGLE_CREDS"] = f.name
   ```
5. Railway auto-detect `Procfile` → deploy otomatis
6. Bot langsung aktif! ✅

**Railway Free Tier:** 500 jam/bulan → cukup untuk berjalan 24/7 jika pakai 1 service.

---

## LANGKAH 4 — Test Bot

Buka Telegram → chat bot kamu:

| Pesan | Hasil |
|-------|-------|
| `/start` | Sambutan bot |
| `beli kopi 15rb` | ✅ Pengeluaran Rp15.000 — Makan & Minum |
| `gaji masuk 8.5jt` | ✅ Pemasukan Rp8.500.000 — Gaji/Tetap |
| `hutang ke budi 500rb` | ✅ Hutang Rp500.000 — Pihak: Budi |
| `beli BBCA 10 lot 9500` | ✅ Portfolio Saham BBCA 1000 lbr @9500 |
| `update BMRI harga 5100` | ✅ Harga BMRI diupdate |
| `saldo` | 📊 Ringkasan lengkap bulan ini |
| `laporan` | 📊 Sama dengan saldo |

---

## FORMAT PESAN YANG DIKENALI

### 💸 Pengeluaran
```
beli [apa] [jumlah]
bayar [apa] [jumlah]
habis [jumlah] buat [apa]
```
Contoh: `beli bensin 150rb`, `bayar netflix 54rb`, `jajan 25000`

### 💰 Pemasukan
```
gaji masuk [jumlah]
dapet [jumlah] dari [sumber]
bonus [jumlah]
dividen [ticker] [jumlah]
```

### 💳 Hutang & Piutang
```
hutang ke [nama] [jumlah]     → catat hutang
[nama] pinjam [jumlah]        → catat piutang
[nama] udah bayar [jumlah]    → update cicilan
```

### 📈 Portfolio
```
beli [TICKER] [lot] lot [harga]
beli btc [jumlah] [harga]
beli emas [gram] gr [harga]
update [TICKER] harga [harga baru]
jual [TICKER] [lot] lot [harga]
```

### 📊 Laporan
```
saldo
laporan
laporan bulan ini
net worth
ringkasan
```

---

## KEAMANAN

- ✅ **Hanya kamu** yang bisa pakai (cek via `CHAT_ID`)
- ✅ Pesan lain langsung diabaikan tanpa respons
- ✅ Credentials Google disimpan di Railway env vars (tidak di kode)
- ✅ Bot token tidak pernah hardcode di kode
- ✅ Data tersimpan di Google Sheets milikmu sendiri
- ✅ Tidak ada pihak ketiga yang akses datamu

---

## TROUBLESHOOTING

**Bot tidak respons:**
- Cek `BOT_TOKEN` di Railway variables
- Pastikan bot sudah di-start (`/start` dulu)

**Google Sheets tidak terupdate:**
- Cek `SHEET_ID` benar
- Pastikan service account sudah di-share ke sheets
- Cek nama sheet sama persis (ada emoji di nama sheet)

**Error "Sheet not found":**
- Nama sheet harus PERSIS sama: `📤 PENGELUARAN`, `📥 PEMASUKAN`, dll.
- Cek apakah emoji ikut tercopy saat upload ke Google Sheets

---

*Setup sekali, jalan selamanya. Gratis.* 🚀
