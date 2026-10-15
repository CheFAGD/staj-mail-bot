import os
import smtplib
import time
import random
import threading
import logging
import asyncio
from email.message import EmailMessage
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

# --- ŞEHİR BAZLI DOĞRULANMIŞ LÜKS OTEL VE FINE DINING HAVUZU ---
VERIFIED_DATABASE = {
    "berlin": [
        {"isim": "Hotel Adlon Kempinski Berlin", "email": "adlon@kempinski.com", "ulke": "DE"},
        {"isim": "The Ritz-Carlton Berlin", "email": "berlin@ritzcarlton.com", "ulke": "DE"},
        {"isim": "Waldorf Astoria Berlin", "email": "berlin.info@waldorfastoria.com", "ulke": "DE"},
        {"isim": "Regent Berlin", "email": "info.berlin@ihg.com", "ulke": "DE"},
        {"isim": "Restaurant Tim Raue", "email": "office@tim-raue.com", "ulke": "DE"},
        {"isim": "Rutz Restaurant Berlin", "email": "info@rutz-restaurant.de", "ulke": "DE"},
        {"isim": "Restaurant FACIL Berlin", "email": "welcome@facil.de", "ulke": "DE"},
        {"isim": "Grand Hyatt Berlin", "email": "berlin.grand@hyatt.com", "ulke": "DE"},
        {"isim": "SO/ Berlin Das Stue", "email": "stay@so-berlin-das-stue.com", "ulke": "DE"},
        {"isim": "Hotel de Rome Rocco Forte", "email": "reservations.derome@roccofortehotels.com", "ulke": "DE"},
        {"isim": "Nobelhart & Schmutzig", "email": "dubist@nobelhartundschmutzig.com", "ulke": "DE"},
        {"isim": "Lorenz Adlon Esszimmer", "email": "lorenz.adlon@kempinski.com", "ulke": "DE"}
    ],
    "frankfurt": [
        {"isim": "Steigenberger Icon Frankfurter Hof", "email": "frankfurter-hof@steigenberger.com", "ulke": "DE"},
        {"isim": "Jumeirah Frankfurt", "email": "jffinfo@jumeirah.com", "ulke": "DE"},
        {"isim": "Sofitel Frankfurt Opera", "email": "h8159@sofitel.com", "ulke": "DE"},
        {"isim": "Restaurant Lafleur Frankfurt", "email": "lafleur@gesellschaftshaus-palmengarten.de", "ulke": "DE"},
        {"isim": "The Westin Grand Frankfurt", "email": "grandfrankfurt@westin.com", "ulke": "DE"},
        {"isim": "Kempinski Hotel Gravenbruch", "email": "hotel.frankfurt@kempinski.com", "ulke": "DE"},
        {"isim": "Restaurant Gustav Frankfurt", "email": "kontakt@restaurant-gustav.de", "ulke": "DE"},
        {"isim": "Roomers Frankfurt", "email": "info@roomers-frankfurt.com", "ulke": "DE"},
        {"isim": "Fleming's Selection Hotel Frankfurt", "email": "frankfurt-city@flemings-hotels.com", "ulke": "DE"}
    ],
    "munich": [
        {"isim": "Hotel Bayerischer Hof Munich", "email": "info@bayerischerhof.de", "ulke": "DE"},
        {"isim": "Hotel Vier Jahreszeiten Kempinski München", "email": "reservations.vierjahreszeiten@kempinski.com", "ulke": "DE"},
        {"isim": "Mandarin Oriental Munich", "email": "momuc-info@mohg.com", "ulke": "DE"},
        {"isim": "The Charles Hotel Rocco Forte", "email": "reservations.charles@roccofortehotels.com", "ulke": "DE"},
        {"isim": "Restaurant Tantris München", "email": "kontakt@tantris.de", "ulke": "DE"},
        {"isim": "Restaurant Atelier München", "email": "atelier@bayerischerhof.de", "ulke": "DE"},
        {"isim": "Restaurant Alois Dallmayr", "email": "alois@dallmayr.de", "ulke": "DE"},
        {"isim": "Rosewood Munich", "email": "munich@rosewoodhotels.com", "ulke": "DE"},
        {"isim": "EssZimmer by Käfer BMW Welt", "email": "esszimmer.bmw-welt@feinkost-kaefer.de", "ulke": "DE"}
    ],
    "münchen": [
        {"isim": "Hotel Bayerischer Hof Munich", "email": "info@bayerischerhof.de", "ulke": "DE"},
        {"isim": "Hotel Vier Jahreszeiten Kempinski München", "email": "reservations.vierjahreszeiten@kempinski.com", "ulke": "DE"},
        {"isim": "Mandarin Oriental Munich", "email": "momuc-info@mohg.com", "ulke": "DE"},
        {"isim": "Restaurant Tantris München", "email": "kontakt@tantris.de", "ulke": "DE"},
        {"isim": "Restaurant Atelier München", "email": "atelier@bayerischerhof.de", "ulke": "DE"},
        {"isim": "Restaurant Alois Dallmayr", "email": "alois@dallmayr.de", "ulke": "DE"}
    ],
    "hamburg": [
        {"isim": "Fairmont Hotel Vier Jahreszeiten Hamburg", "email": "hamburg@fairmont.com", "ulke": "DE"},
        {"isim": "The Fontenay Hamburg", "email": "info@thefontenay.com", "ulke": "DE"},
        {"isim": "Hotel Atlantic Hamburg", "email": "hotel.atlantic@brilliant-hotels.com", "ulke": "DE"},
        {"isim": "Grand Elysee Hamburg", "email": "info@grand-elysee.com", "ulke": "DE"},
        {"isim": "Restaurant Haerlin Hamburg", "email": "haerlin.hamburg@fairmont.com", "ulke": "DE"},
        {"isim": "The Table Kevin Fehling", "email": "info@the-table-hamburg.de", "ulke": "DE"},
        {"isim": "Restaurant Bianc Hamburg", "email": "info@bianc.de", "ulke": "DE"},
        {"isim": "Park Hyatt Hamburg", "email": "hamburg.park@hyatt.com", "ulke": "DE"}
    ],
    "cologne": [
        {"isim": "Excelsior Hotel Ernst Köln", "email": "info@excelsior-hotel-ernst.de", "ulke": "DE"},
        {"isim": "Hyatt Regency Köln", "email": "cologne.regency@hyatt.com", "ulke": "DE"},
        {"isim": "Restaurant taku Köln", "email": "taku@excelsior-hotel-ernst.de", "ulke": "DE"},
        {"isim": "Le Moissonnier Köln", "email": "contact@lemoissonnier.de", "ulke": "DE"},
        {"isim": "Hanse Stube Excelsior", "email": "hansestube@excelsior-hotel-ernst.de", "ulke": "DE"},
        {"isim": "Cologne Marriott Hotel", "email": "cologne.marriott@marriotthotels.com", "ulke": "DE"}
    ],
    "köln": [
        {"isim": "Excelsior Hotel Ernst Köln", "email": "info@excelsior-hotel-ernst.de", "ulke": "DE"},
        {"isim": "Hyatt Regency Köln", "email": "cologne.regency@hyatt.com", "ulke": "DE"},
        {"isim": "Restaurant taku Köln", "email": "taku@excelsior-hotel-ernst.de", "ulke": "DE"},
        {"isim": "Le Moissonnier Köln", "email": "contact@lemoissonnier.de", "ulke": "DE"}
    ],
    "stuttgart": [
        {"isim": "Steigenberger Graf Zeppelin Stuttgart", "email": "stuttgart@steigenberger.com", "ulke": "DE"},
        {"isim": "Althoff Hotel am Schlossgarten Stuttgart", "email": "info@hotelschlossgarten.com", "ulke": "DE"},
        {"isim": "Restaurant Speisemeisterei Stuttgart", "email": "info@speisemeisterei.de", "ulke": "DE"},
        {"isim": "Restaurant Wielandshöhe Stuttgart", "email": "post@wielandshoehe.de", "ulke": "DE"},
        {"isim": "Le Méridien Stuttgart", "email": "info@lemeridienstuttgart.com", "ulke": "DE"}
    ],
    "düsseldorf": [
        {"isim": "Breidenbacher Hof Düsseldorf", "email": "info@breidenbacherhof.com", "ulke": "DE"},
        {"isim": "Hyatt Regency Düsseldorf", "email": "dusseldorf.regency@hyatt.com", "ulke": "DE"},
        {"isim": "The Wellem Düsseldorf", "email": "info.thewellem@hyatt.com", "ulke": "DE"},
        {"isim": "Restaurant Nagaya Düsseldorf", "email": "nagaya@nagaya.de", "ulke": "DE"},
        {"isim": "Restaurant Yoshi by Nagaya", "email": "yoshi@nagaya.de", "ulke": "DE"},
        {"isim": "Steigenberger Icon Parkhotel Düsseldorf", "email": "parkhotel-duesseldorf@steigenberger.com", "ulke": "DE"}
    ],
    "amsterdam": [
        {"isim": "Waldorf Astoria Amsterdam", "email": "amsterdam.info@waldorfastoria.com", "ulke": "NL"},
        {"isim": "Conservatorium Hotel Amsterdam", "email": "info@conservatoriumhotel.com", "ulke": "NL"},
        {"isim": "Hotel De L'Europe Amsterdam", "email": "hotel@deleurope.com", "ulke": "NL"},
        {"isim": "Sofitel Legend The Grand Amsterdam", "email": "h2783@sofitel.com", "ulke": "NL"},
        {"isim": "Restaurant Ciel Bleu Amsterdam", "email": "cielbleu@okura.nl", "ulke": "NL"},
        {"isim": "RIJKS Restaurant Amsterdam", "email": "info@rijksrestaurant.nl", "ulke": "NL"},
        {"isim": "Restaurant Spectrum Amsterdam", "email": "spectrum.amsterdam@waldorfastoria.com", "ulke": "NL"},
        {"isim": "W Amsterdam Hotel", "email": "wamsterdam@whotels.com", "ulke": "NL"},
        {"isim": "The Dylan Amsterdam", "email": "hotel@dylanamsterdam.com", "ulke": "NL"}
    ],
    "rotterdam": [
        {"isim": "Hotel New York Rotterdam", "email": "info@hotelnewyork.nl", "ulke": "NL"},
        {"isim": "The Slaak Rotterdam", "email": "info@theslaakrotterdam.nl", "ulke": "NL"},
        {"isim": "Restaurant FG Rotterdam", "email": "info@fgrestaurant.nl", "ulke": "NL"},
        {"isim": "Restaurant Parkheuvel Rotterdam", "email": "info@parkheuvel.nl", "ulke": "NL"},
        {"isim": "Mainport Hotel Rotterdam", "email": "info@mainporthotel.com", "ulke": "NL"},
        {"isim": "Restaurant Fred Rotterdam", "email": "info@restaurantfred.nl", "ulke": "NL"}
    ]
}

# --- WEB SUNUCUSU (UptimeRobot / Render portu için) ---
server = Flask(__name__)

@server.route('/')
def home():
    return "Bot ve Web Sunucusu 7/24 Aktif!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
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

# --- RADAR ÇALIŞTIRICI ---
def radar_gorevi(sehir_sorgu, chat_id, loop, bot_app):
    global RADAR_CALISIYOR
    RADAR_CALISIYOR = True

    sehir_anahtar = sehir_sorgu.lower().strip()
    hedefler = VERIFIED_DATABASE.get(sehir_anahtar, [])

    almanya_sehirleri = ['berlin', 'munich', 'münchen', 'frankfurt', 'hamburg', 'cologne', 'köln', 'düsseldorf', 'stuttgart']
    ulke = "DE" if sehir_anahtar in almanya_sehirleri else "NL"

    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text=f"🔍 Radar devrede: {sehir_sorgu.capitalize()} ({ulke}) taranıyor..."),
        loop
    )

    if not hedefler:
        RADAR_CALISIYOR = False
        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {sehir_sorgu.capitalize()} için listede henüz kayıt yok.\n"
                     f"Doğrudan taranabilir şehirler: Berlin, Frankfurt, Munich, Hamburg, Cologne, Stuttgart, Düsseldorf, Amsterdam, Rotterdam."
            ),
            loop
        )
        return

    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=["Isim", "Email", "Ulke", "Durum"])
        df.to_csv(CSV_FILE, index=False)

    df = pd.read_csv(CSV_FILE)
    mevcut_mailler = set(df["Email"].astype(str).str.lower().tolist())
    bulunan_sayisi = 0

    for item in hedefler:
        m_clean = item["email"].lower().strip()
        sirket = item["isim"]
        item_ulke = item["ulke"]

        if m_clean not in mevcut_mailler:
            yeni_satir = pd.DataFrame([{
                "Isim": sirket,
                "Email": m_clean,
                "Ulke": item_ulke,
                "Durum": "Bekliyor"
            }])
            df = pd.concat([df, yeni_satir], ignore_index=True)
            mevcut_mailler.add(m_clean)
            bulunan_sayisi += 1
            df.to_csv(CSV_FILE, index=False)

            asyncio.run_coroutine_threadsafe(
                bot_app.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎯 Yeni Hedef Bulundu!\nİşletme: {sirket}\nMail: {m_clean}\nÜlke: {item_ulke}"
                ),
                loop
            )
            time.sleep(1.2)

    RADAR_CALISIYOR = False
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(
            chat_id=chat_id,
            text=f"🏁 Radar tamamlandı! {sehir_sorgu.capitalize()} için {bulunan_sayisi} yeni işletme havuzuna eklendi."
        ),
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
        logger.error(f"CV bulunamadı: {CV_FILE}")
        return False

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASS)
        s.send_message(msg)
    return True

def mail_gonderim_gorevi(chat_id, loop, bot_app):
    global CALISIYOR
    if not os.path.exists(CSV_FILE):
        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(chat_id=chat_id, text="Hata: restoranlar.csv bulunamadı."),
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
        f"👋 Selam Ali! Sistem aktif ve tam güç hazır.\n"
        f"Senin Chat ID: `{chat_id}`\n\n"
        "Komutlar:\n"
        "🔎 /radar <sehir> - İşletme ve mailleri listeye aktarır\n"
        "🚀 /baslat - Mail gönderimini başlatır\n"
        "🛑 /durdur - Gönderimi durdurur\n"
        "📊 /durum - Liste durumunu gösterir"
    )
    await update.message.reply_text(mesaj, parse_mode="Markdown")

async def radar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global RADAR_CALISIYOR
    chat_id = update.effective_chat.id
    if RADAR_CALISIYOR:
        await update.message.reply_text("⚠️ Radar şu anda işlem yapıyor, lütfen bekle.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Lütfen bir şehir belirt! Örn:\n/radar Berlin\n/radar Frankfurt")
        return

    sehir = " ".join(args).strip()
    loop = asyncio.get_running_loop()
    threading.Thread(target=radar_gorevi, args=(sehir, chat_id, loop, context.application), daemon=True).start()

async def baslat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CALISIYOR
    chat_id = update.effective_chat.id
    if CALISIYOR:
        await update.message.reply_text("⚠️ Sistem zaten gönderim yapıyor.")
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
        logger.error("HATA: TELEGRAM_TOKEN bulunamadı!")
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
