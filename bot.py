import os
import re
import smtplib
import time
import random
import threading
import logging
import asyncio
from urllib.parse import urljoin, urlparse
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8,nl;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}
EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

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

# --- RADAR FONKSİYONLARI (ENGEL GEÇİRMEZ ÇEKİRDEK) ---
def webden_mail_topla(url):
    emails = set()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=7)
        if resp.status_code == 200:
            found = re.findall(EMAIL_REGEX, resp.text)
            for e in found:
                e_low = e.lower()
                if not any(ext in e_low for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', 'wix', 'sentry', 'bootstrap', 'example', 'domain']):
                    emails.add(e)
            
            # Alt sayfalar
            sub_paths = ['/contact', '/kontakt', '/impressum', '/about', '/contact-us', '/career', '/jobs']
            domain = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            for path in sub_paths:
                try:
                    s_resp = requests.get(urljoin(domain, path), headers=HEADERS, timeout=5)
                    s_found = re.findall(EMAIL_REGEX, s_resp.text)
                    for e in s_found:
                        e_low = e.lower()
                        if not any(ext in e_low for ext in ['.png', '.jpg', '.jpeg', '.svg', 'sentry', 'wix']):
                            emails.add(e)
                except:
                    continue
    except:
        pass
    return list(emails)

def hedef_siteleri_bul(sehir):
    siteler = []
    # 1. Kaynak: Wikipedia API üzerinden o şehirdeki otellerin doğrudan resmi linkleri (IP ban yemez)
    try:
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search=Hotels_in_{sehir}&limit=5&format=json"
        w_resp = requests.get(wiki_url, headers=HEADERS, timeout=8).json()
        if len(w_resp) > 3 and w_resp[3]:
            for w_link in w_resp[3]:
                page_resp = requests.get(w_link, headers=HEADERS, timeout=8)
                soup = BeautifulSoup(page_resp.text, 'html.parser')
                for a in soup.find_all('a', class_='external text'):
                    href = a.get('href')
                    if href and href.startswith('http') and not any(x in href for x in ['wikipedia', 'wikidata', 'google']):
                        siteler.append(href)
    except Exception as e:
        logger.error(f"Wiki aramasi: {e}")

    # 2. Kaynak: Mojeek ve Qwant arama motorları (Cloudflare ve Render IP bloklarına takılmaz)
    sorgular = [
        f"luxury hotel in {sehir} official website",
        f"boutique hotel {sehir} contact",
        f"michelin star restaurant {sehir} official site"
    ]
    for q in sorgular:
        try:
            m_url = f"https://www.mojeek.com/search?q={requests.utils.quote(q)}"
            resp = requests.get(m_url, headers=HEADERS, timeout=8)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', class_='ob'):
                href = a.get('href')
                if href and href.startswith('http'):
                    siteler.append(href)
        except Exception as e:
            logger.error(f"Mojeek arama hatasi: {e}")

    # Rezervasyon ve rehber sitelerini filtrele
    temiz_siteler = []
    cop_siteler = ['booking', 'tripadvisor', 'hotels.com', 'expedia', 'yelp', 'kayak', 'trivago', 'instagram', 'facebook', 'youtube', 'wikipedia', 'mojeek']
    for s in siteler:
        s_clean = s.strip()
        parsed = urlparse(s_clean)
        netloc = parsed.netloc.lower()
        if not any(cop in netloc for cop in cop_siteler):
            base = f"{parsed.scheme}://{parsed.netloc}"
            if base not in temiz_siteler:
                temiz_siteler.append(base)

    return temiz_siteler[:20]

def radar_gorevi(sehir, ulke, chat_id, loop, bot_app):
    global RADAR_CALISIYOR
    RADAR_CALISIYOR = True
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text=f"🔍 Radar devrede: {sehir} ({ulke}) taranıyor... Hedef siteler inceleniyor."),
        loop
    )

    siteler = hedef_siteleri_bul(sehir)
    bulunan_sayisi = 0

    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=["Isim", "Email", "Ulke", "Durum"])
        df.to_csv(CSV_FILE, index=False)

    df = pd.read_csv(CSV_FILE)
    mevcut_mailler = set(df["Email"].astype(str).str.lower().tolist())

    for site in siteler:
        domain_name = urlparse(site).netloc.replace('www.', '').split('.')[0].capitalize()
        mailler = webden_mail_topla(site)

        for m in mailler:
            m_clean = m.lower().strip()
            if m_clean not in mevcut_mailler:
                yeni_satir = pd.DataFrame([{
                    "Isim": f"{domain_name} Hotel/Restaurant",
                    "Email": m_clean,
                    "Ulke": ulke,
                    "Durum": "Bekliyor"
                }])
                df = pd.concat([df, yeni_satir], ignore_index=True)
                mevcut_mailler.add(m_clean)
                bulunan_sayisi += 1
                df.to_csv(CSV_FILE, index=False)
                asyncio.run_coroutine_threadsafe(
                    bot_app.bot.send_message(chat_id=chat_id, text=f"🎯 Yeni Hedef Bulundu!\nİşletme: {domain_name}\nMail: {m_clean}\nÜlke: {ulke}"),
                    loop
                )
        time.sleep(1)

    RADAR_CALISIYOR = False
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text=f"🏁 Radar bitti! Toplam {bulunan_sayisi} yeni işletme eklendi."),
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
        "🔎 /radar <sehir> - Otel ve mail tarar\n"
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
        await update.message.reply_text("Lütfen bir şehir belirt! Örn:\n/radar Amsterdam\n/radar Berlin")
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
