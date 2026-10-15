import os
import re
import smtplib
import time
import random
import threading
from urllib.parse import urljoin, urlparse
from email.message import EmailMessage
import requests
from bs4 import BeautifulSoup
import pandas as pd
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}
EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

# --- WEB SUNUCUSU (Render & UptimeRobot için) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Radar ve Mail Botu Calisiyor!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

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

# --- RADAR FONKSİYONLARI ---
def webden_mail_topla(url):
    emails = set()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=6)
        if resp.status_code == 200:
            found = re.findall(EMAIL_REGEX, resp.text)
            for e in found:
                if not any(ext in e.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', 'wix', 'sentry', 'bootstrap']):
                    emails.add(e)
            
            sub_paths = ['/contact', '/kontakt', '/impressum', '/jobs', '/career', '/over-ons']
            domain = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            for path in sub_paths:
                try:
                    s_resp = requests.get(urljoin(domain, path), headers=HEADERS, timeout=5)
                    s_found = re.findall(EMAIL_REGEX, s_resp.text)
                    for e in s_found:
                        if not any(ext in e.lower() for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                            emails.add(e)
                except:
                    continue
    except:
        pass
    return list(emails)

def duckduckgo_arama(sorgu):
    linkler = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={sorgu}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', class_='result__url'):
            href = a.get('href')
            if href and 'http' in href:
                linkler.append(href.strip())
            elif href and href.startswith('//duckduckgo.com/l/?uddg='):
                real_url = href.split('uddg=')[1].split('&')[0]
                import urllib.parse
                linkler.append(urllib.parse.unquote(real_url))
    except Exception as e:
        print(f"Arama hatasi: {e}")
    return list(set(linkler))[:15]

def radar_gorevi(sehir, ulke, chat_id, bot_app):
    global RADAR_CALISIYOR
    RADAR_CALISIYOR = True
    bot_app.bot.send_message(chat_id=chat_id, text=f"🔍 Radar devrede: {sehir} ({ulke}) için oteller taranıyor...")

    sorgular = [
        f"luxury hotels in {sehir} official site",
        f"fine dining restaurants in {sehir} official website",
        f"boutique hotel restaurant in {sehir}"
    ]

    bulunan_sayisi = 0
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=["Isim", "Email", "Ulke", "Durum"])
        df.to_csv(CSV_FILE, index=False)

    df = pd.read_csv(CSV_FILE)
    mevcut_mailler = set(df["Email"].astype(str).str.lower().tolist())

    for q in sorgular:
        siteler = duckduckgo_arama(q)
        for site in siteler:
            if any(cop in site for cop in ['tripadvisor', 'booking.com', 'yelp', 'expedia', 'wikipedia', 'hotels.com']):
                continue
            
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
                    bot_app.bot.send_message(chat_id=chat_id, text=f"🎯 Yeni Hedef Bulundu!\nİşletme: {domain_name}\nMail: {m_clean}\nÜlke: {ulke}")
            time.sleep(2)

    RADAR_CALISIYOR = False
    bot_app.bot.send_message(chat_id=chat_id, text=f"🏁 Radar tamamlandı! Toplam {bulunan_sayisi} yeni işletme listeye eklendi.")

# --- MAİL GÖNDERME İŞLEMLERİ ---
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
        return False

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.send_message(msg)
    return True

def mail_gonderim_gorevi(chat_id, bot_app):
    global CALISIYOR
    if not os.path.exists(CSV_FILE):
        bot_app.bot.send_message(chat_id=chat_id, text="Hata: restoranlar.csv bulunamadı.")
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
                
                bot_app.bot.send_message(
                    chat_id=chat_id, 
                    text=f"✅ Gönderildi:\nİşletme: {sirket} ({ulke})\nMail: {email}"
                )
                time.sleep(random.randint(80, 95))
        except Exception as e:
            df.at[idx, "Durum"] = f"Hata: {str(e)[:25]}"
            df.to_csv(CSV_FILE, index=False)
            bot_app.bot.send_message(
                chat_id=chat_id, 
                text=f"❌ Hata ({sirket}): {e}"
            )
            time.sleep(15)

    CALISIYOR = False
    bot_app.bot.send_message(chat_id=chat_id, text="🏁 Gönderim tamamlandı veya durduruldu.")

# --- TELEGRAM KOMUTLARI ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mesaj = (
        f"👋 Selam Ali! Sistem bağlandı ve hazır.\n"
        f"Senin Chat ID: `{chat_id}`\n\n"
        "Komutlar:\n"
        "🔎 /radar <sehir> - Otel/restoran ve e-posta bulur\n"
        "   (Örn: /radar Amsterdam veya /radar Berlin)\n"
        "🚀 /baslat - Mail gönderimini başlatır\n"
        "🛑 /durdur - Gönderimi durdurur\n"
        "📊 /durum - Liste özetini gösterir"
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

    threading.Thread(target=radar_gorevi, args=(sehir, ulke, chat_id, context.application)).start()

async def baslat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CALISIYOR
    chat_id = update.effective_chat.id
    if CALISIYOR:
        await update.message.reply_text("⚠️ Sistem zaten çalışıyor.")
        return
    
    CALISIYOR = True
    await update.message.reply_text("🚀 Mail gönderimi başladı! Bildirimler buradan gelecek.")
    threading.Thread(target=mail_gonderim_gorevi, args=(chat_id, context.application)).start()

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
        f"Toplam Kayıtlı İşletme: {toplam}\n"
        f"Mail Gönderilen: {gonderilen}\n"
        f"Kalan: {toplam - gonderilen}\n"
        f"Gönderim Aktif mi?: {'Evet' if CALISIYOR else 'Hayır'}\n"
        f"Radar Aktif mi?: {'Evet' if RADAR_CALISIYOR else 'Hayır'}"
    )

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()

    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("radar", radar_cmd))
    bot_app.add_handler(CommandHandler("baslat", baslat_cmd))
    bot_app.add_handler(CommandHandler("durdur", durdur_cmd))
    bot_app.add_handler(CommandHandler("durum", durum_cmd))
    
    bot_app.run_polling()
