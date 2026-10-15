import os
import smtplib
import time
import random
import threading
from email.message import EmailMessage
import pandas as pd
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- AYARLAR ---
GMAIL_USER = "aligorkemdurmazz@gmail.com"
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

EXCEL_FILE = "restoranlar.xlsx"
CV_FILE = "Ali_Gorkem_Durmaz_CV.pdf"

CALISIYOR = False

# --- WEB SUNUCUSU (UptimeRobot için) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot aktif ve calisiyor!"

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
Tel: +90 553 876 75 40"""
    },
    "NL": {
        "konu": "Application: Culinary Internship (February – May) – {sirket} – Ali Görkem Durmaz",
        "icerik": """Dear Hiring Team / Head Chef,

My name is Ali Görkem Durmaz, a senior Gastronomy and Culinary Arts student at Bolu Abant Izzet Baysal University.

I am seeking an official culinary internship position from February until May. Having worked in high-volume luxury hotel kitchens and semi-fine dining concepts (including Titanic Hotels and Cosmos Theatre across hot stations and HACCP standards), I am eager to contribute effectively to your kitchen brigade at {sirket}.

Please find my CV attached for your review.

Kind regards,
Ali Görkem Durmaz
Tel: +90 553 876 75 40"""
    }
}

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

def mail_gonderim_gorevi(bot_app):
    global CALISIYOR
    if not os.path.exists(EXCEL_FILE):
        return

    df = pd.read_excel(EXCEL_FILE)
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
                df.to_excel(EXCEL_FILE, index=False)
                
                bot_app.bot.send_message(
                    chat_id=ADMIN_CHAT_ID, 
                    text=f"✅ Gönderildi:\nİşletme: {sirket} ({ulke})\nMail: {email}"
                )
                
                # Saatte 40-45 aralığı için 80-95 sn bekleme
                time.sleep(random.randint(80, 95))
        except Exception as e:
            df.at[idx, "Durum"] = f"Hata: {str(e)[:25]}"
            df.to_excel(EXCEL_FILE, index=False)
            bot_app.bot.send_message(
                chat_id=ADMIN_CHAT_ID, 
                text=f"❌ Hata ({sirket}): {e}"
            )
            time.sleep(15)

    CALISIYOR = False
    bot_app.bot.send_message(chat_id=ADMIN_CHAT_ID, text="🏁 Gönderim tamamlandı veya durduruldu.")

# --- TELEGRAM KOMUTLARI ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    await update.message.reply_text("👋 Sistem hazır Ali!\n\n/baslat - Gönderimi başlatır\n/durdur - Gönderimi durdurur\n/durum - Kaç mail gittiğini gösterir")

async def baslat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CALISIYOR
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if CALISIYOR:
        await update.message.reply_text("⚠️ Sistem zaten şu an mail gönderiyor.")
        return
    
    CALISIYOR = True
    await update.message.reply_text("🚀 Mail gönderimi başladı! Gönderildikçe bildirim alacaksın.")
    threading.Thread(target=mail_gonderim_gorevi, args=(context.application,)).start()

async def durdur_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CALISIYOR
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    CALISIYOR = False
    await update.message.reply_text("🛑 Gönderim durduruldu.")

async def durum_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not os.path.exists(EXCEL_FILE):
        await update.message.reply_text("Excel dosyası bulunamadı.")
        return
    df = pd.read_excel(EXCEL_FILE)
    gonderilen = len(df[df.get("Durum") == "Gonderildi"])
    toplam = len(df)
    await update.message.reply_text(f"📊 Durum:\nToplam: {toplam}\nGönderilen: {gonderilen}\nKalan: {toplam - gonderilen}\nAktif mi?: {'Evet' if CALISIYOR else 'Hayır'}")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()

    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("baslat", baslat_cmd))
    bot_app.add_handler(CommandHandler("durdur", durdur_cmd))
    bot_app.add_handler(CommandHandler("durum", durum_cmd))
    
    bot_app.run_polling()
