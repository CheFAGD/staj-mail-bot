import os
import re
import base64
import time
import random
import threading
import logging
import asyncio
from urllib.parse import urlparse, unquote
import requests
import pandas as pd
from bs4 import BeautifulSoup
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

GMAIL_USER = "durmaz40ali@gmail.com"
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()

CSV_FILE = "restoranlar.csv"
HISTORY_FILE = "gonderilen_mailler.txt"
CV_FILE = "Ali_Gorkem_Durmaz_CV.pdf"

CALISIYOR = False
RADAR_CALISIYOR = False

# Permanent hardcoded sent history preventing duplicate dispatches
PERMANENT_SENT_EMAILS = {
    # Amsterdam
    "amsterdam.info@waldorfastoria.com",
    "info@conservatoriumhotel.com",
    "hotel@deleurope.com",
    "h2783@sofitel.com",
    "cielbleu@okura.nl",
    "info@rijksrestaurant.nl",
    "spectrum.amsterdam@waldorfastoria.com",
    "wamsterdam@whotels.com",
    "hotel@dylanamsterdam.com",
    "career@okura.nl",
    "hr.wamsterdam@whotels.com",
    "recruitment@conservatoriumhotel.com",
    "jobs@deleurope.com",
    "info@restaurantdekas.nl",
    "jobs.amsterdam@pestana.com",
    "h2783-hr@sofitel.com",
    "info@restaurantfred.nl",
    "info@hotelnewyork.nl",
    "info@theslaakrotterdam.nl",
    "info@fgrestaurant.nl",
    "info@parkheuvel.nl",
    "info@mainporthotel.com",
    # Berlin
    "adlon@kempinski.com",
    "berlin@ritzcarlton.com",
    "berlin.info@waldorfastoria.com",
    "office@tim-raue.com",
    "info@rutz-restaurant.de",
    "welcome@facil.de",
    "berlin.grand@hyatt.com",
    "stay@so-berlin-das-stue.com",
    "reservations.derome@roccofortehotels.com",
    # Koln
    "info@excelsior-hotel-ernst.de",
    "cologne.regency@hyatt.com",
    "taku@excelsior-hotel-ernst.de",
    "contact@lemoissonnier.de",
}

# Comprehensive City and Country Directory for instant UI commands
CITY_DIRECTORY = {
    "Almanya": [
        "Berlin", "Munich", "Frankfurt", "Hamburg", "Koln", "Dusseldorf",
        "Stuttgart", "Dresden", "Leipzig", "Hannover", "Nurnberg", "Bonn",
        "Heidelberg", "Baden Baden", "Bremen", "Dortmund", "Essen"
    ],
    "Amerika": [
        "New York", "Chicago", "Los Angeles", "San Francisco", "Miami",
        "Boston", "Las Vegas", "Washington", "Seattle", "Austin",
        "Houston", "Dallas", "Philadelphia", "Atlanta", "San Diego",
        "Denver", "New Orleans", "Orlando", "Honolulu", "Aspen", "Nashville"
    ],
    "Italya": [
        "Roma", "Milano", "Firenze", "Venezia", "Napoli", "Torino",
        "Bologna", "Verona", "Palermo", "Amalfi", "Genova", "Bari"
    ],
    "Fransa": [
        "Paris", "Lyon", "Nice", "Bordeaux", "Marseille", "Strasbourg",
        "Toulouse", "Cannes", "Monaco", "Lille", "Nantes", "Montpellier"
    ],
    "Ispanya": [
        "Madrid", "Barcelona", "Valencia", "Sevilla", "San Sebastian",
        "Bilbao", "Malaga", "Granada", "Palma de Mallorca", "Ibiza"
    ],
    "Hollanda": [
        "Amsterdam", "Rotterdam", "Utrecht", "Den Haag", "Eindhoven",
        "Maastricht", "Groningen", "Haarlem"
    ],
    "Ingiltere": [
        "London", "Edinburgh", "Manchester", "Birmingham", "Liverpool",
        "Bristol", "Glasgow", "Oxford", "Cambridge", "Leeds"
    ],
    "Isvicre": [
        "Zurich", "Geneva", "Basel", "Bern", "Lucerne", "St Moritz",
        "Lausanne", "Zermatt", "Lugano", "Interlaken"
    ],
    "Avusturya": [
        "Vienna", "Salzburg", "Innsbruck", "Graz", "Linz", "Kitzbuhel"
    ],
    "Portekiz": [
        "Lisbon", "Porto", "Faro", "Funchal", "Cascais", "Sintra", "Coimbra"
    ],
    "Belcika": [
        "Brussels", "Antwerp", "Gent", "Brugge", "Liege", "Leuven"
    ],
    "Iskandinavya": [
        "Copenhagen", "Aarhus", "Stockholm", "Gothenburg", "Malmo",
        "Oslo", "Bergen", "Trondheim", "Stavanger", "Helsinki",
        "Turku", "Tampere", "Reykjavik"
    ],
    "Polonya": [
        "Warsaw", "Krakow", "Gdansk", "Wroclaw", "Poznan", "Lodz"
    ],
    "Cekya": [
        "Prague", "Brno", "Ostrava", "Plzen", "Karlovy Vary"
    ],
    "Yunanistan": [
        "Athens", "Thessaloniki", "Santorini", "Mykonos", "Heraklion", "Rhodes"
    ],
    "Macaristan": [
        "Budapest", "Debrecen", "Szeged", "Pecs", "Gyor"
    ],
    "Diger": [
        "Dublin", "Bratislava", "Ljubljana", "Zagreb", "Dubrovnik",
        "Tallinn", "Riga", "Vilnius", "Luxembourg"
    ]
}

def slugify(text: str) -> str:
    """Sanitizes any string into ASCII a-z0-9_ for Telegram command compatibility."""
    text = text.lower().strip()
    replacements = {
        "ü": "u", "ö": "o", "ş": "s", "ı": "i", "ğ": "g", "ç": "c",
        "ä": "a", "é": "e", "è": "e", "á": "a", "í": "i", "ó": "o",
        "ú": "u", "ñ": "n", "ß": "ss", " ": "_", "-": "_"
    }
    for char, rep in replacements.items():
        text = text.replace(char, rep)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text

def get_country_code(city_slug: str) -> str:
    """Maps cities to national codes (DE/AT vs EN international template)."""
    clean = city_slug.lower().replace("_", "")
    de_cities = [
        "berlin", "munich", "munchen", "frankfurt", "hamburg", "koln",
        "cologne", "dusseldorf", "stuttgart", "dresden", "leipzig",
        "hannover", "nurnberg", "bonn", "heidelberg", "badenbaden",
        "bremen", "dortmund", "essen"
    ]
    at_ch_cities = [
        "vienna", "wien", "salzburg", "innsbruck", "graz", "linz",
        "kitzbuhel", "zurich", "geneva", "basel", "bern", "lucerne",
        "stmoritz", "lausanne", "zermatt"
    ]
    if any(c in clean for c in de_cities):
        return "DE"
    if any(c in clean for c in at_ch_cities):
        return "AT"
    return "EN"

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IGNORE_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css',
    '.js', '.woff', '.woff2', '.ttf'
)
USER_AGENT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8"
}

def extract_email_from_website(website_url: str) -> str:
    """Crawls official venue homepages and contact/career subpages to discover emails."""
    if not website_url or not website_url.startswith("http"):
        return ""
    
    try:
        resp = requests.get(website_url, headers=USER_AGENT_HEADERS, timeout=7)
        if resp.status_code == 200:
            emails = set(EMAIL_REGEX.findall(resp.text))
            valid = [
                e for e in emails 
                if not e.lower().endswith(IGNORE_EXTENSIONS) 
                and not any(x in e.lower() for x in ["wix", "sentry", "example", "schema", "bootstrap", "wordpress"])
            ]
            if valid:
                for mail in valid:
                    m = mail.lower()
                    if any(k in m for k in ["karriere", "career", "hr", "jobs", "recruitment", "info", "kontakt", "contact"]):
                        return mail
                return valid[0]
            
            # Sub-crawl for Contact / Jobs links
            soup = BeautifulSoup(resp.text, "html.parser")
            sub_links = []
            for a in soup.find_all("a", href=True):
                href = a['href'].lower()
                if any(x in href for x in ["contact", "kontakt", "impressum", "career", "jobs", "about"]):
                    if a['href'].startswith("http"):
                        sub_links.append(a['href'])
                    else:
                        base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(website_url))
                        sub_links.append(base + ("/" if not a['href'].startswith("/") else "") + a['href'])
            
            for s_url in sub_links[:3]:
                try:
                    s_resp = requests.get(s_url, headers=USER_AGENT_HEADERS, timeout=6)
                    if s_resp.status_code == 200:
                        s_emails = set(EMAIL_REGEX.findall(s_resp.text))
                        valid_sub = [
                            e for e in s_emails 
                            if not e.lower().endswith(IGNORE_EXTENSIONS) 
                            and not any(x in e.lower() for x in ["wix", "sentry", "example", "schema"])
                        ]
                        if valid_sub:
                            for c_mail in valid_sub:
                                if any(k in c_mail.lower() for k in ["career", "jobs", "hr", "karriere", "kontakt", "info"]):
                                    return c_mail
                            return valid_sub[0]
                except Exception:
                    continue
    except Exception:
        pass
    return ""

def live_serp_crawler(city: str, limit: int = 15):
    """
    Searches the live public web using targeted search queries to directly extract
    real hotel & fine dining contact email addresses for the designated city.
    """
    clean_city = city.replace("_", " ").title()
    search_queries = [
        f'"{clean_city}" luxury hotel email contact OR karriere OR jobs',
        f'"{clean_city}" fine dining restaurant email OR kontakt OR career',
        f'"{clean_city}" boutique hotel email info OR reservations'
    ]
    
    found = []
    seen_emails = set()

    for q in search_queries:
        if len(found) >= limit:
            break
        try:
            url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(q)}"
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": q},
                headers=USER_AGENT_HEADERS,
                timeout=10
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                results = soup.select(".result")
                for r in results:
                    title_elem = r.select_one(".result__title")
                    snip_elem = r.select_one(".result__snippet")
                    url_elem = r.select_one(".result__url")
                    
                    raw_text = (snip_elem.get_text() if snip_elem else "") + " " + (title_elem.get_text() if title_elem else "")
                    emails = set(EMAIL_REGEX.findall(raw_text))
                    
                    venue_title = title_elem.get_text(strip=True) if title_elem else f"Hospitality {clean_city}"
                    venue_title = re.sub(r"(\.\.\.| - .*| \| .*)", "", venue_title).strip()
                    if not venue_title:
                        venue_title = f"Luxury Venue {clean_city}"

                    for email in emails:
                        e_clean = email.lower().strip()
                        if not e_clean.endswith(IGNORE_EXTENSIONS) and e_clean not in seen_emails and "duckduckgo" not in e_clean:
                            seen_emails.add(e_clean)
                            found.append({"isim": venue_title, "email": e_clean})
                            break
                    
                    # If snippet didn't have email directly, crawl destination domain
                    if url_elem and len(found) < limit:
                        link_href = url_elem.get_text(strip=True)
                        if link_href and not link_href.startswith("http"):
                            link_href = "https://" + link_href
                        extracted = extract_email_from_website(link_href)
                        if extracted and extracted.lower() not in seen_emails:
                            seen_emails.add(extracted.lower())
                            found.append({"isim": venue_title, "email": extracted.strip()})
        except Exception as e:
            logger.warning(f"SERP arama uyarisi ({q}): {e}")
            continue

    return found

def live_search_venues(city: str, limit: int = 30):
    """
    Harvests luxury venues using a robust 2-stage pipeline:
    1. OpenStreetMap Overpass bounding box query with direct contact extraction.
    2. Deep SERP search engine fallback crawler ensuring endless real-time discoverability.
    """
    clean_city = city.strip().replace("_", " ").title()
    logger.info(f"Otonom radar sahada: {clean_city}")
    results = []
    seen_emails = set()

    # Stage 1: Geocoded Bounding Box via Nominatim + Overpass
    try:
        nom_url = f"https://nominatim.openstreetmap.org/search?city={clean_city}&format=json&limit=1"
        nom_resp = requests.get(nom_url, headers=USER_AGENT_HEADERS, timeout=8)
        bbox = None
        if nom_resp.status_code == 200 and nom_resp.json():
            bb = nom_resp.json()[0].get("boundingbox", [])
            if len(bb) == 4:
                # south, north, west, east -> south, west, north, east
                bbox = f"{bb[0]},{bb[2]},{bb[1]},{bb[3]}"

        overpass_url = "https://overpass-api.de/api/interpreter"
        if bbox:
            query = f"""
            [out:json][timeout:20];
            (
              nwr["tourism"="hotel"]({bbox});
              nwr["amenity"="restaurant"]["cuisine"~"fine_dining|french|italian|gourmet|steak_house"]({bbox});
            );
            out tags 100;
            """
        else:
            query = f"""
            [out:json][timeout:20];
            area["name"="{clean_city}"]->.a;
            (
              nwr["tourism"="hotel"](area.a);
              nwr["amenity"="restaurant"](area.a);
            );
            out tags 100;
            """

        op_resp = requests.post(overpass_url, data={'data': query}, timeout=22)
        if op_resp.status_code == 200:
            elements = op_resp.json().get("elements", [])
            for elem in elements:
                tags = elem.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue
                email = tags.get("email") or tags.get("contact:email")
                website = tags.get("website") or tags.get("contact:website")
                
                if email and "@" in email:
                    e_clean = email.strip().lower()
                    if e_clean not in seen_emails:
                        seen_emails.add(e_clean)
                        results.append({"isim": name, "email": e_clean})
                elif website and len(results) < limit:
                    extracted = extract_email_from_website(website)
                    if extracted and extracted.lower() not in seen_emails:
                        seen_emails.add(extracted.lower())
                        results.append({"isim": name, "email": extracted.strip()})
                
                if len(results) >= limit:
                    break
    except Exception as e:
        logger.warning(f"Overpass harita tarama atlandi: {e}")

    # Stage 2: SERP Crawler to continuously expand pool beyond static boundaries
    if len(results) < limit:
        logger.info(f"Canlı SERP radarı devreye giriyor: {clean_city}")
        serp_results = live_serp_crawler(clean_city, limit=(limit - len(results)))
        for sr in serp_results:
            if sr["email"].lower() not in seen_emails:
                seen_emails.add(sr["email"].lower())
                results.append(sr)

    return results

server = Flask(__name__)

@server.route('/')
def home():
    return "Ali Staj Botu 7/24 Kesintisiz Otonom Radar Aktif!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port, use_reloader=False)

def get_sent_history():
    """Returns all historically contacted emails across memory and storage."""
    sent = set(PERMANENT_SENT_EMAILS)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                val = line.strip().lower()
                if val:
                    sent.add(val)
    return sent

def add_to_sent_history(email: str):
    """Permanently commits an email to file and memory cache."""
    try:
        clean = email.lower().strip()
        PERMANENT_SENT_EMAILS.add(clean)
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(clean + "\n")
    except Exception as e:
        logger.error(f"Hafıza dosyası yazma hatası: {e}")

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
    "EN": {
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

def mail_at_brevo(alici_mail: str, sirket: str, ulke: str):
    dil = "DE" if str(ulke).upper() in ["DE", "AT"] else "EN"
    ayar = TEMPLATES[dil]
    konu = ayar["konu"].format(sirket=sirket)
    metin = ayar["icerik"].format(sirket=sirket)

    if not os.path.exists(CV_FILE):
        raise FileNotFoundError(f"CV dosyası '{CV_FILE}' bulunamadı.")

    with open(CV_FILE, "rb") as f:
        cv_base64 = base64.b64encode(f.read()).decode('utf-8')

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": "Ali Görkem Durmaz", "email": GMAIL_USER},
        "to": [{"email": alici_mail, "name": sirket}],
        "bcc": [{"email": GMAIL_USER, "name": "Kopya - Ali Görkem Durmaz"}],
        "replyTo": {"email": GMAIL_USER, "name": "Ali Görkem Durmaz"},
        "subject": konu,
        "textContent": metin,
        "attachment": [
            {
                "content": cv_base64,
                "name": "Ali_Gorkem_Durmaz_CV.pdf"
            }
        ]
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=20)
    if resp.status_code not in [200, 201, 202]:
        raise Exception(f"Brevo API Hatası ({resp.status_code}): {resp.text}")
    return True

def radar_gorevi(sehir_sorgu: str, chat_id: int, loop, bot_app):
    global RADAR_CALISIYOR
    RADAR_CALISIYOR = True

    sehir_temiz = sehir_sorgu.replace("_", " ").title()
    sehir_slug = slugify(sehir_sorgu)
    ulke_kodu = get_country_code(sehir_slug)

    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(
            chat_id=chat_id, 
            text=f"🛰️ *Otonom Canlı Radar Başlatıldı!*\n"
                 f"📍 Hedef Bölge: `{sehir_temiz}` ({ulke_kodu})\n"
                 f"İnternet arama motorları ve harita sistemleri taranıyor, yeni işletmeler çekiliyor..."
        ),
        loop
    )

    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=["Isim", "Email", "Ulke", "Durum"])
        df.to_csv(CSV_FILE, index=False)

    df = pd.read_csv(CSV_FILE)
    if "Durum" not in df.columns:
        df["Durum"] = "Bekliyor"

    sent_history = get_sent_history()
    mevcut_mailler = set(df["Email"].astype(str).str.lower().tolist())

    canli_bulunanlar = live_search_venues(sehir_sorgu, limit=25)
    bulunan_sayisi = 0

    for item in canli_bulunanlar:
        m_clean = item["email"].lower().strip()
        sirket = item["isim"]

        if m_clean in sent_history or m_clean in mevcut_mailler:
            continue

        yeni_satir = pd.DataFrame([{
            "Isim": sirket,
            "Email": m_clean,
            "Ulke": ulke_kodu,
            "Durum": "Bekliyor"
        }])
        df = pd.concat([df, yeni_satir], ignore_index=True)
        mevcut_mailler.add(m_clean)
        bulunan_sayisi += 1
        df.to_csv(CSV_FILE, index=False)

        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(
                chat_id=chat_id,
                text=f"🎯 *Yeni Hedef Bulundu!*\n"
                     f"İşletme: {sirket}\n"
                     f"Mail: `{m_clean}`\n"
                     f"Bölge: {sehir_temiz} ({ulke_kodu})"
            ),
            loop
        )
        time.sleep(0.4)

    RADAR_CALISIYOR = False
    sonuc_metni = (
        f"🏁 Otonom tarama başarıyla tamamlandı!\n"
        f"📍 `{sehir_temiz}` için **{bulunan_sayisi}** yeni işletme listeye eklendi.\n\n"
        f"Gönderimi başlatmak için: /baslat"
    ) if bulunan_sayisi > 0 else (
        f"ℹ️ `{sehir_temiz}` için tespit edilen işletmeler zaten hafızada kayıtlı veya daha önce mail iletilmiş. "
        f"Dilerseniz gönderimi başlatabilir (/baslat) veya farklı bir şehir taratabilirsiniz."
    )

    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text=sonuc_metni, parse_mode="Markdown"),
        loop
    )

def mail_gonderim_gorevi(chat_id: int, loop, bot_app):
    global CALISIYOR
    if not os.path.exists(CSV_FILE):
        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(chat_id=chat_id, text="Hata: restoranlar.csv bulunamadı."),
            loop
        )
        CALISIYOR = False
        return

    df = pd.read_csv(CSV_FILE)
    if "Durum" not in df.columns:
        df["Durum"] = "Bekliyor"

    sent_history = get_sent_history()
    for idx, row in df.iterrows():
        m = str(row["Email"]).lower().strip()
        if m in sent_history and str(row["Durum"]).strip() != "Gonderildi":
            df.at[idx, "Durum"] = "Gonderildi"
    df.to_csv(CSV_FILE, index=False)

    bekleyenler = df[df["Durum"] != "Gonderildi"]
    if len(bekleyenler) == 0:
        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(
                chat_id=chat_id, 
                text="ℹ️ Listede bekleyen işletme kalmadı! Yeni bir şehir taratabilirsiniz."
            ),
            loop
        )
        CALISIYOR = False
        return

    for idx, row in df.iterrows():
        if not CALISIYOR:
            break
        if str(row["Durum"]).strip() == "Gonderildi":
            continue

        email = str(row["Email"]).strip()
        sirket = str(row["Isim"]).strip()
        ulke = str(row.get("Ulke", "US")).strip()

        if email.lower() in sent_history:
            df.at[idx, "Durum"] = "Gonderildi"
            df.to_csv(CSV_FILE, index=False)
            continue

        try:
            logger.info(f"Mail iletiliyor: {sirket} ({email})")
            mail_at_brevo(email, sirket, ulke)
            
            df.at[idx, "Durum"] = "Gonderildi"
            df.to_csv(CSV_FILE, index=False)
            add_to_sent_history(email)
            sent_history.add(email.lower())
            
            asyncio.run_coroutine_threadsafe(
                bot_app.bot.send_message(
                    chat_id=chat_id, 
                    text=f"✅ Gönderildi:\nİşletme: {sirket} ({ulke})\nMail: `{email}`"
                ),
                loop
            )
            time.sleep(random.randint(60, 75))
        except Exception as e:
            hata_mesaji = str(e)[:120]
            logger.error(f"Gonderim hatasi: {hata_mesaji}")
            df.at[idx, "Durum"] = "Hata"
            df.to_csv(CSV_FILE, index=False)
            asyncio.run_coroutine_threadsafe(
                bot_app.bot.send_message(
                    chat_id=chat_id, 
                    text=f"❌ Hata ({sirket}):\n{hata_mesaji}"
                ),
                loop
            )
            time.sleep(10)

    CALISIYOR = False
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text="🏁 Gönderim döngüsü tamamlandı veya durduruldu."),
        loop
    )

def build_country_message(country_name: str, cities: list) -> str:
    lines = [f"🌍 *{country_name.upper()} ŞEHİR RADARLARI* 🛰️", "Aşağıdaki şehirlere tıklayarak canlı taramayı hemen başlatabilirsin:\n"]
    for c in cities:
        c_slug = slugify(c)
        lines.append(f"👉 /radar_{c_slug}  _({c})_")
    lines.append("\n🚀 Taramadan sonra gönderimi başlatmak için: /baslat")
    return "\n".join(lines)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        f"👋 Selam Ali! Küresel Otonom Staj Radarı 7/24 Devrede.\n\n"
        "🛰️ *Tam Otonom Canlı Radar:*\n"
        "Artık hiçbir manuel sınır yok! İstediğin şehir veya ülkeyi seç, bot internetten "
        "en lüks otelleri ve restoranları canlı olarak bulup listeye ekler.\n\n"
        "🌐 *Ülke Menüleri:*\n"
        "👉 /amerika - ABD şehirleri (New York, Miami, LA...)\n"
        "👉 /almanya - Almanya şehirleri (Berlin, Münih, Köln...)\n"
        "👉 /italya - İtalya şehirleri (Roma, Milano, Floransa...)\n"
        "👉 /fransa - Fransa şehirleri (Paris, Lyon, Nice...)\n"
        "👉 /ispanya - İspanya şehirleri (Madrid, Barselona...)\n"
        "👉 /hollanda - Hollanda şehirleri (Amsterdam, Rotterdam...)\n"
        "👉 /ingiltere - İngiltere şehirleri (Londra, Edinburgh...)\n"
        "👉 /iskandinavya - Danimarka, İsveç, Norveç, Finlandiya\n"
        "👉 /isvicre & /avusturya - Alpler ve Merkez Avrupa\n"
        "👉 /portekiz & /belcika\n"
        "👉 /ulkeler - Tüm ülkelerin tam listesi\n\n"
        "⚙️ *Operasyon Komutları:*\n"
        "🚀 /baslat - Gönderimi başlatır (60-75 sn aralıkla)\n"
        "🛑 /durdur - Gönderimi durdurur\n"
        "📊 /durum - Anlık durumu gösterir\n"
        "💾 /csv_indir - Güncel CSV yedeğini indirir"
    )
    await update.message.reply_text(mesaj, parse_mode="Markdown")

async def ulkeler_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "🌍 *DESTEKLENEN TÜM ÜLKE MENÜLERİ*\n"
        "Tıklayarak o ülkedeki tüm şehir listesini görebilirsin:\n\n"
        "🇺🇸 /amerika\n"
        "🇩🇪 /almanya\n"
        "🇮🇹 /italya\n"
        "🇫🇷 /fransa\n"
        "🇪🇸 /ispanya\n"
        "🇳🇱 /hollanda\n"
        "🇬🇧 /ingiltere\n"
        "🇨🇭 /isvicre\n"
        "🇦🇹 /avusturya\n"
        "🇵🇹 /portekiz\n"
        "🇧🇪 /belcika\n"
        "❄️ /iskandinavya\n"
        "🇵🇱 /polonya\n"
        "🇨🇿 /cekyo\n"
        "🇬🇷 /yunanistan\n"
        "🇭🇺 /macaristan\n"
        "🌐 /diger (İrlanda, Hırvatistan, Slovenya...)"
    )
    await update.message.reply_text(mesaj, parse_mode="Markdown")

async def country_shortcut_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.strip().replace("/", "").lower()
    mapping = {
        "almanya": "Almanya",
        "amerika": "Amerika",
        "italya": "Italya",
        "fransa": "Fransa",
        "ispanya": "Ispanya",
        "hollanda": "Hollanda",
        "ingiltere": "Ingiltere",
        "isvicre": "Isvicre",
        "avusturya": "Avusturya",
        "portekiz": "Portekiz",
        "belcika": "Belcika",
        "iskandinavya": "Iskandinavya",
        "polonya": "Polonya",
        "cekyo": "Cekya",
        "yunanistan": "Yunanistan",
        "macaristan": "Macaristan",
        "diger": "Diger"
    }
    target = mapping.get(cmd)
    if target and target in CITY_DIRECTORY:
        text = build_country_message(target, CITY_DIRECTORY[target])
        await update.message.reply_text(text, parse_mode="Markdown")

async def radar_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global RADAR_CALISIYOR
    chat_id = update.effective_chat.id
    if RADAR_CALISIYOR:
        await update.message.reply_text("⚠️ Radar şu anda işlem yapıyor, lütfen taramanın bitmesini bekle.")
        return

    text = update.message.text.strip()
    if text.startswith("/radar_"):
        sehir = text.replace("/radar_", "").strip()
    elif text.startswith("/radar"):
        args = context.args
        if not args:
            await update.message.reply_text("Lütfen bir şehir belirt! Örn: `/radar berlin` veya `/radar_roma`")
            return
        sehir = " ".join(args).strip()
    else:
        return

    loop = asyncio.get_running_loop()
    threading.Thread(target=radar_gorevi, args=(sehir, chat_id, loop, context.application), daemon=True).start()

async def baslat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CALISIYOR
    chat_id = update.effective_chat.id
    if CALISIYOR:
        await update.message.reply_text("⚠️ Sistem zaten gönderim yapıyor.")
        return
    
    CALISIYOR = True
    await update.message.reply_text("🚀 Mail gönderimi başlatıldı!")
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
    if "Durum" not in df.columns:
        df["Durum"] = "Bekliyor"

    sent_history = get_sent_history()
    gonderilen = len(df[(df["Durum"] == "Gonderildi") | (df["Email"].astype(str).str.lower().isin(sent_history))])
    toplam = len(df)
    kalan = max(0, toplam - gonderilen)

    await update.message.reply_text(
        f"📊 *Durum Özeti:*\n"
        f"Toplam Kayıtlı: {toplam}\n"
        f"Gönderilen: {gonderilen}\n"
        f"Kalan: {kalan}\n"
        f"Gönderim Aktif mi?: {'Evet' if CALISIYOR else 'Hayır'}\n"
        f"Radar Aktif mi?: {'Evet' if RADAR_CALISIYOR else 'Hayır'}",
        parse_mode="Markdown"
    )

async def csv_indir_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(CSV_FILE):
        await update.message.reply_text("⚠️ Henüz oluşturulmuş bir restoranlar.csv dosyası yok.")
        return
    with open(CSV_FILE, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="restoranlar.csv",
            caption="💾 İşte sunucudaki güncel liste!"
        )

async def dosya_yukle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".csv"):
        return
    
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(CSV_FILE)
    
    try:
        df = pd.read_csv(CSV_FILE)
        gonderilenler = df[df.get("Durum") == "Gonderildi"]["Email"].dropna().tolist()
        for g in gonderilenler:
            add_to_sent_history(str(g))
        
        toplam = len(df)
        gonderilen_sayisi = len(gonderilenler)
        await update.message.reply_text(
            f"✅ `restoranlar.csv` başarıyla yüklendi!\n"
            f"Toplam Kayıt: {toplam}\n"
            f"Gönderildi: {gonderilen_sayisi}\n"
            f"Kalan: {toplam - gonderilen_sayisi}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Dosya yüklendi fakat okunurken bir sorun oluştu: {e}")

async def main():
    if not TELEGRAM_TOKEN:
        logger.error("HATA: TELEGRAM_TOKEN bulunamadı!")
        return

    # Start Flask Web Keep-Alive Thread
    t = threading.Thread(target=run_web, daemon=True)
    t.start()

    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(CommandHandler("ulkeler", ulkeler_cmd))
    bot_app.add_handler(CommandHandler("baslat", baslat_cmd))
    bot_app.add_handler(CommandHandler("durdur", durdur_cmd))
    bot_app.add_handler(CommandHandler("durum", durum_cmd))
    bot_app.add_handler(CommandHandler("csv_indir", csv_indir_cmd))
    bot_app.add_handler(MessageHandler(filters.Document.FileExtension("csv"), dosya_yukle_handler))
    bot_app.add_handler(CommandHandler("radar", radar_dispatcher))

    # Country Shortcuts
    country_commands = [
        "almanya", "amerika", "italya", "fransa", "ispanya", "hollanda",
        "ingiltere", "isvicre", "avusturya", "portekiz", "belcika",
        "iskandinavya", "polonya", "cekyo", "yunanistan", "macaristan", "diger"
    ]
    for c_cmd in country_commands:
        bot_app.add_handler(CommandHandler(c_cmd, country_shortcut_handler))

    # Catch-all regex handler for any /radar_<city> command
    bot_app.add_handler(MessageHandler(filters.Regex(r"^/radar_"), radar_dispatcher))

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
