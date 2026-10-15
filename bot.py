import os
import re
import smtplib
import time
import random
import threading
import logging
import asyncio
from email.message import EmailMessage
import requests
import pandas as pd
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- LOG AYARLARI ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- AYARLAR ---
GMAIL_USER = "durmaz40ali@gmail.com"
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()

CSV_FILE = "restoranlar.csv"
CV_FILE = "Ali_Gorkem_Durmaz_CV.pdf"

CALISIYOR = False
RADAR_CALISIYOR = False

HEADERS = {
    "User-Agent": "StajBotApp/1.0 (contact: durmaz40ali@gmail.com)"
}

# --- WEB SUNUCUSU (UptimeRobot / Render portu için) ---
server = Flask(__name__)

@server.route('/')
def home():
    return "Bot ve Web Sunucusu 7/24 Aktif!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Web sunucusu baslatiliyor: Port {port}")
    server.run(host="0.0.0.0", port=port, use_reloader=False)

# --- MAİL ŞABLONLARI ---
TEMPLATES = {
    "DE": {
        "konu": "Bewerbung: Pflichtpraktikum Küche (Februar – Mai) – {sirket} – Ali Görkem Durmaz",
        "icerik": """Sehr geehrte Damen und Herren,

mein Name ist Ali Görkem Durmaz. Ich bin Student im letzten Studienjahr für Gastronomie und Kochkunst an der Bolu Abant Izzet Baysal Universität.

Im Rahmen meines Studiums absolviere ich von Februar bis Mai mein obligatorisches Auslandspraktikum im Küchenbereich. Durch meine bisherigen Erfahrungen in der gehobenen Hotel- und à-la-carte-Gastronomie (u.a. Titanic Hotels und Cosmos Theatre) bringe ich solide Kenntnisse in der warmen Küche und HACCP-Standards mit.

Im Anhang finden Sie meinen Lebenslauf. Über die Chance auf ein Vorstellungsgespräch freue ich mich sehr.

Mit freundlichen Grüßen
Ali Görkem Durmaz
Tel: +90 553 876 75 40
E-Mail: durmaz40ali@gmail.com"""
    },
    "NL": {
        "konu": "Application: Culinary Internship (February – May) – {sirket} – Ali Görkem Durmaz",
        "icerik": """Dear Hiring Team / Head Chef,

My name is Ali Görkem Durmaz, a senior Gastronomy and Culinary Arts student at Bolu Abant Izzet Baysal University.

I am seeking an official culinary internship position from February until May. Having worked in high-volume luxury hotel kitchens and semi-fine dining concepts (including Titanic Hotels and Cosmos Theatre across hot stations and HACCP standards), I am eager to contribute effectively to your kitchen brigade at {sirket}.

Please find my CV attached for your review.

Kind regards,
Ali Görkem Durmaz
Tel: +90 553 876 75 40
E-Mail: durmaz40ali@gmail.com"""
    }
}

# --- RESMİ VERİTABANI RADARI (OpenStreetMap Overpass API) ---
def haritadan_otel_ve_mail_topla(sehir):
    overpass_url = "https://overpass-api.de/api/interpreter"
    # Şehirdeki e-postası kayıtlı tüm otel ve restoranları doğrudan sorgular
    query = f"""
    [out:json][timeout:30];
    area[name~"{sehir}", i]->.searchArea;
    (
      node["tourism"="hotel"]["email"](area.searchArea);
      way["tourism"="hotel"]["email"](area.searchArea);
      node["amenity"="restaurant"]["email"](area.searchArea);
      way["amenity"="restaurant"]["email"](area.searchArea);
    );
    out tags;
    """
    sonuclar = []
    try:
        resp = requests.post(overpass_url, data={"data": query}, headers=HEADERS, timeout=35)
        if resp.status_code == 200:
            data = resp.json()
            for element in data.get("elements", []):
                tags = element.get("tags", {})
                isim = tags.get("name")
                email = tags.get("email") or tags.get("contact:email")
                if isim and email:
                    # Bazen birden fazla mail noktalı virgülle ayrılmıştır
                    temiz_mailler = [m.strip().lower() for m in email.replace(",", ";").split(";")]
                    for m in temiz_mailler:
                        if "@" in m and "." in m:
                            sonuclar.append({"isim": isim, "email": m})
    except Exception as e:
        logger.error(f"Harita sorgu hatasi: {e}")
    return sonuclar

def radar_gorevi(sehir, ulke, chat_id, loop, bot_app):
    global RADAR_CALISIYOR
    RADAR_CALISIYOR = True
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text=f"🔍 Radar devrede: {sehir} ({ulke}) harita veritabanı taranıyor..."),
        loop
    )

    bulunanlar = haritadan_otel_ve_mail_topla(sehir)
    bulunan_sayisi = 0

    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=["Isim", "Email", "Ulke", "Durum"])
        df.to_csv(CSV_FILE, index=False)

    df = pd.read_csv(CSV_FILE)
    mevcut_mailler = set(df["Email"].astype(str).str.lower().tolist())

    for item in bulunanlar:
        m_clean = item["email"]
        sirket = item["isim"]
        if m_clean not in mevcut_mailler:
            yeni_satir = pd.DataFrame([{
                "Isim": sirket,
                "Email": m_clean,
                "Ulke": ulke,
                "Durum": "Bekliyor"
            }])
            df = pd.concat([df, yeni_satir], ignore_index=True)
            mevcut_mailler.add(m_clean)
            bulunan_sayisi += 1
            df.to_csv(CSV_FILE, index=False)
            asyncio.run_coroutine_threadsafe(
                bot_app.bot.send_message(chat_id=chat_id, text=f"🎯 Yeni Hedef Bulundu!\nİşletme: {sirket}\nMail: {m_clean}\nÜlke: {ulke}"),
                loop
            )
            time.sleep(0.3)

    RADAR_CALISIYOR = False
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text=f"🏁 Radar bitti! {sehir} için toplam {bulunan_sayisi} yeni işletme eklendi."),
        loop
    )

# --- MAİL GÖNDERME ---
def mail_at(alici_mail, sirket, ulke):
    dil = "DE" if str(ulke).upper() == "DE" else "NL"
    ayar = TEMPLATES[dil]
    
    msg = EmailMessage()
    msg["Subject"] = ayar["konu"].format(sirket=sirket)
    msg["From"] = f"Ali Görkem Durmaz <{GMAIL_USER}>"
    msg["To"] = alici_mail
    msg.set_content(ayar["icerik"].format(sirket=sirket))

    if os.path.exists(CV_FILE):
        with open(CV_FILE, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename="Ali_Gorkem_Durmaz_CV.pdf")
    else:
        logger.error(f"CV dosyasi bulunamadi: {CV_FILE}")
        return False

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASS)
        s.send_message(msg)
    return True

def mail_gonderim_gorevi(chat_id, loop, bot_app):
    global CALISIYOR
    if not os.path.exists(CSV_FILE):
        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(chat_id=chat_id, text="Hata: restoranlar.csv bulunamadi."),
            loop
        )
        return

    df = pd.read_csv(CSV_FILE)
    if "Durum" not in df.columns:
        df["Durum"] = "Bekliyor"

    for idx, row in df.iterrows():
        if not CALISIYOR:
            break
        if row["Durum"] == "Gonderildi":
            continue

        email = str(row["Email"]).strip()
        sirket = str(row["Isim"]).strip()
        ulke = str(row.get("Ulke", "NL")).strip()

        try:
            if mail_at(email, sirket, ulke):
                df.at[idx, "Durum"] = "Gonderildi"
                df.to_csv(CSV_FILE, index=False)
                
                asyncio.run_coroutine_threadsafe(
                    bot_app.bot.send_message(
                        chat_id=chat_id, 
                        text=f"✅ Gönderildi:\nİşletme: {sirket} ({ulke})\nMail: {email}"
                    ),
                    loop
                )
                time.sleep(random.randint(80, 95))
        except Exception as e:
            df.at[idx, "Durum"] = f"Hata: {str(e)[:25]}"
            df.to_csv(CSV_FILE, index=False)
            asyncio.run_coroutine_threadsafe(
                bot_app.bot.send_message(
                    chat_id=chat_id, 
                    text=f"❌ Hata ({sirket}): {e}"
                ),
                loop
            )
            time.sleep(15)

    CALISIYOR = False
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text="🏁 Gönderim tamamlandı veya durduruldu."),
        loop
    )

# --- TELEGRAM KOMUTLARI ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mesaj = (
        f"👋 Selam Ali! Sistem aktif.\n"
        f"Senin Chat ID: `{chat_id}`\n\n"
        "Komutlar:\n"
        "🔎 /radar <sehir> - Haritadan doğrudan otel ve mailleri çeker\n"
        "🚀 /baslat - Mail gönderimini başlatır\n"
        "🛑 /durdur - Gönderimi durdurur\n"
        "📊 /durum - Liste durumunu gösterir"
    )
    await update.message.reply_text(mesaj, parse_mode="Markdown")

async def radar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global RADAR_CALISIYOR
    chat_id = update.effective_chat.id
    if RADAR_CALISIYOR:
        await update.message.reply_text("⚠️ Radar şu anda zaten çalışıyor!")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Lütfen bir şehir belirt! Örn:\n/radar Berlin\n/radar Frankfurt")
        return

    sehir = " ".join(args).strip()
    almanya_sehirleri = ['berlin', 'munich', 'münchen', 'frankfurt', 'hamburg', 'cologne', 'köln', 'düsseldorf', 'stuttgart']
    ulke = "DE" if sehir.lower() in almanya_sehirleri else "NL"

    loop = asyncio.get_running_loop()
    threading.Thread(target=radar_gorevi, args=(sehir, ulke, chat_id, loop, context.application), daemon=True).start()

async def baslat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CALISIYOR
    chat_id = update.effective_chat.id
    if CALISIYOR:
        await update.message.reply_text("⚠️ Sistem zaten çalışıyor.")
        return
    
    CALISIYOR = True
    await update.message.reply_text("🚀 Mail gönderimi başladı!")
    loop = asyncio.get_running_loop()
    threading.Thread(target=mail_gonderim_gorevi, args=(chat_id, loop, context.application), daemon=True).start()

async def durdur_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CALISIYOR
    CALISIYOR = False
    await update.message.reply_text("🛑 Gönderim durduruldu.")

async def durum_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(CSV_FILE):
        await update.message.reply_text("Henüz kayıtlı işletme yok.")
        return
    df = pd.read_csv(CSV_FILE)
    gonderilen = len(df[df.get("Durum") == "Gonderildi"])
    toplam = len(df)
    await update.message.reply_text(
        f"📊 Durum Özeti:\n"
        f"Toplam Kayıtlı: {toplam}\n"
        f"Gönderilen: {gonderilen}\n"
        f"Kalan: {toplam - gonderilen}\n"
        f"Gönderim Aktif mi?: {'Evet' if CALISIYOR else 'Hayır'}\n"
        f"Radar Aktif mi?: {'Evet' if RADAR_CALISIYOR else 'Hayır'}"
    )

async def main():
    if not TELEGRAM_TOKEN:
        logger.error("HATA: TELEGRAM_TOKEN yok!")
        return

    t = threading.Thread(target=run_web, daemon=True)
    t.start()

    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("radar", radar_cmd))
    bot_app.add_handler(CommandHandler("baslat", baslat_cmd))
    bot_app.add_handler(CommandHandler("durdur", durdur_cmd))
    bot_app.add_handler(CommandHandler("durum", durum_cmd))

    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram polling aktif!")
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
