import os
import re
import base64
import time
import random
import threading
import logging
import asyncio
import requests
import pandas as pd
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# --- LOG AYARLARI ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
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

# ================= KALICI GÖNDERİLENLER LİSTESİ =================
# Render sıfırlansa bile bu maillere ASLA ikinci kez mail gitmez!
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
    # Köln
    "info@excelsior-hotel-ernst.de",
    "cologne.regency@hyatt.com",
    "taku@excelsior-hotel-ernst.de",
    "contact@lemoissonnier.de"
}

def slugify(text: str) -> str:
    """Telegram komutlarına uygun hale getirir: sadece a-z0-9_"""
    text = text.lower()
    text = text.replace("ü", "u").replace("ö", "o").replace("ş", "s").replace("ı", "i")
    text = text.replace("ğ", "g").replace("ç", "c").replace("ä", "a").replace("é", "e")
    text = text.replace("è", "e").replace("á", "a").replace("í", "i").replace("ó", "o")
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text

VERIFIED_DATABASE = {
    # ================= ALMANYA =================
    "berlin": [
        {"isim": "Hotel Adlon Kempinski Berlin", "email": "adlon@kempinski.com", "ulke": "DE"},
        {"isim": "The Ritz-Carlton Berlin", "email": "berlin@ritzcarlton.com", "ulke": "DE"},
        {"isim": "Waldorf Astoria Berlin", "email": "berlin.info@waldorfastoria.com", "ulke": "DE"},
        {"isim": "Restaurant Tim Raue", "email": "office@tim-raue.com", "ulke": "DE"},
        {"isim": "Rutz Restaurant Berlin", "email": "info@rutz-restaurant.de", "ulke": "DE"},
        {"isim": "Restaurant FACIL Berlin", "email": "welcome@facil.de", "ulke": "DE"},
        {"isim": "Grand Hyatt Berlin", "email": "berlin.grand@hyatt.com", "ulke": "DE"},
        {"isim": "SO/ Berlin Das Stue", "email": "stay@so-berlin-das-stue.com", "ulke": "DE"},
        {"isim": "Hotel de Rome Rocco Forte", "email": "reservations.derome@roccofortehotels.com", "ulke": "DE"}
    ],
    "frankfurt": [
        {"isim": "Steigenberger Icon Frankfurter Hof", "email": "frankfurter-hof@steigenberger.com", "ulke": "DE"},
        {"isim": "Sofitel Frankfurt Opera", "email": "h8159@sofitel.com", "ulke": "DE"},
        {"isim": "Restaurant Lafleur Frankfurt", "email": "lafleur@gesellschaftshaus-palmengarten.de", "ulke": "DE"},
        {"isim": "The Westin Grand Frankfurt", "email": "grandfrankfurt@westin.com", "ulke": "DE"},
        {"isim": "Kempinski Hotel Gravenbruch", "email": "hotel.frankfurt@kempinski.com", "ulke": "DE"},
        {"isim": "Roomers Frankfurt", "email": "info@roomers-frankfurt.com", "ulke": "DE"}
    ],
    "munich": [
        {"isim": "Hotel Bayerischer Hof Munich", "email": "info@bayerischerhof.de", "ulke": "DE"},
        {"isim": "Hotel Vier Jahreszeiten Kempinski München", "email": "reservations.vierjahreszeiten@kempinski.com", "ulke": "DE"},
        {"isim": "Mandarin Oriental Munich", "email": "momuc-info@mohg.com", "ulke": "DE"},
        {"isim": "Restaurant Tantris München", "email": "kontakt@tantris.de", "ulke": "DE"},
        {"isim": "Restaurant Atelier München", "email": "atelier@bayerischerhof.de", "ulke": "DE"},
        {"isim": "Rosewood Munich", "email": "munich@rosewoodhotels.com", "ulke": "DE"}
    ],
    "hamburg": [
        {"isim": "Fairmont Hotel Vier Jahreszeiten Hamburg", "email": "hamburg@fairmont.com", "ulke": "DE"},
        {"isim": "The Fontenay Hamburg", "email": "info@thefontenay.com", "ulke": "DE"},
        {"isim": "Restaurant Haerlin Hamburg", "email": "haerlin.hamburg@fairmont.com", "ulke": "DE"},
        {"isim": "The Table Kevin Fehling", "email": "info@the-table-hamburg.de", "ulke": "DE"}
    ],
    "koln": [
        {"isim": "Excelsior Hotel Ernst Köln", "email": "info@excelsior-hotel-ernst.de", "ulke": "DE"},
        {"isim": "Hyatt Regency Köln", "email": "cologne.regency@hyatt.com", "ulke": "DE"},
        {"isim": "Restaurant taku Köln", "email": "taku@excelsior-hotel-ernst.de", "ulke": "DE"},
        {"isim": "Le Moissonnier Köln", "email": "contact@lemoissonnier.de", "ulke": "DE"}
    ],
    "dusseldorf": [
        {"isim": "Breidenbacher Hof Düsseldorf", "email": "info@breidenbacherhof.com", "ulke": "DE"},
        {"isim": "Hyatt Regency Düsseldorf", "email": "dusseldorf.regency@hyatt.com", "ulke": "DE"},
        {"isim": "Steigenberger Icon Parkhotel Düsseldorf", "email": "parkhotel-duesseldorf@steigenberger.com", "ulke": "DE"}
    ],
    "stuttgart": [
        {"isim": "Steigenberger Graf Zeppelin Stuttgart", "email": "stuttgart@steigenberger.com", "ulke": "DE"},
        {"isim": "Althoff Hotel am Schlossgarten Stuttgart", "email": "info@hotelschlossgarten.com", "ulke": "DE"},
        {"isim": "Restaurant Speisemeisterei Stuttgart", "email": "info@speisemeisterei.de", "ulke": "DE"}
    ],
    "dresden": [
        {"isim": "Hotel Taschenbergpalais Kempinski Dresden", "email": "reservations.taschenbergpalais@kempinski.com", "ulke": "DE"},
        {"isim": "Bülow Palais Dresden", "email": "info@buelow-hotels.de", "ulke": "DE"},
        {"isim": "Restaurant Caroussel Nouvelle", "email": "caroussel@buelow-hotels.de", "ulke": "DE"}
    ],
    "leipzig": [
        {"isim": "Steigenberger Grandhotel Handelshof Leipzig", "email": "leipzig@steigenberger.com", "ulke": "DE"},
        {"isim": "The Westin Leipzig", "email": "info@westin-leipzig.com", "ulke": "DE"},
        {"isim": "Restaurant FALCO Leipzig", "email": "falco@westin-leipzig.com", "ulke": "DE"}
    ],
    "hannover": [
        {"isim": "Kastens Hotel Luisenhof Hannover", "email": "info@kastens-luisenhof.de", "ulke": "DE"},
        {"isim": "Restaurant Jante Hannover", "email": "info@jante-restaurant.de", "ulke": "DE"}
    ],
    "nurnberg": [
        {"isim": "Sheraton Carlton Hotel Nuernberg", "email": "carltonnuernberg@sheraton.com", "ulke": "DE"},
        {"isim": "Restaurant Essigbrätlein Nürnberg", "email": "restaurant@essigbraetlein.de", "ulke": "DE"}
    ],
    "bonn": [
        {"isim": "Kameha Grand Bonn", "email": "bonn@kamehagrand.com", "ulke": "DE"},
        {"isim": "Steigenberger Icon Petersberg Königswinter", "email": "petersberg@steigenberger.com", "ulke": "DE"}
    ],
    "heidelberg": [
        {"isim": "Europäischer Hof Heidelberg", "email": "welcome@europaeischerhof.com", "ulke": "DE"},
        {"isim": "Restaurant Le Gourmet Heidelberg", "email": "legourmet@hirsch-gass.de", "ulke": "DE"}
    ],
    "badenbaden": [
        {"isim": "Brenners Park-Hotel & Spa Oetker Collection", "email": "information.brenners@oetkercollection.com", "ulke": "DE"},
        {"isim": "Roomers Baden-Baden", "email": "info@roomers-badenbaden.com", "ulke": "DE"}
    ],

    # ================= HOLLANDA =================
    "amsterdam": [
        {"isim": "Waldorf Astoria Amsterdam", "email": "amsterdam.info@waldorfastoria.com", "ulke": "NL"},
        {"isim": "Conservatorium Hotel Amsterdam", "email": "info@conservatoriumhotel.com", "ulke": "NL"},
        {"isim": "Hotel De L'Europe Amsterdam", "email": "hotel@deleurope.com", "ulke": "NL"},
        {"isim": "Sofitel Legend The Grand Amsterdam", "email": "h2783@sofitel.com", "ulke": "NL"},
        {"isim": "Restaurant Ciel Bleu Amsterdam", "email": "cielbleu@okura.nl", "ulke": "NL"},
        {"isim": "RIJKS Restaurant Amsterdam", "email": "info@rijksrestaurant.nl", "ulke": "NL"},
        {"isim": "Restaurant Spectrum Amsterdam", "email": "spectrum.amsterdam@waldorfastoria.com", "ulke": "NL"},
        {"isim": "W Amsterdam Hotel", "email": "wamsterdam@whotels.com", "ulke": "NL"},
        {"isim": "The Dylan Amsterdam", "email": "hotel@dylanamsterdam.com", "ulke": "NL"},
        {"isim": "Restaurant De Kas", "email": "info@restaurantdekas.nl", "ulke": "NL"}
    ],
    "rotterdam": [
        {"isim": "Hotel New York Rotterdam", "email": "info@hotelnewyork.nl", "ulke": "NL"},
        {"isim": "The Slaak Rotterdam", "email": "info@theslaakrotterdam.nl", "ulke": "NL"},
        {"isim": "Restaurant FG Rotterdam", "email": "info@fgrestaurant.nl", "ulke": "NL"},
        {"isim": "Restaurant Parkheuvel Rotterdam", "email": "info@parkheuvel.nl", "ulke": "NL"},
        {"isim": "Mainport Hotel Rotterdam", "email": "info@mainporthotel.com", "ulke": "NL"},
        {"isim": "Restaurant Fred Rotterdam", "email": "info@restaurantfred.nl", "ulke": "NL"}
    ],
    "utrecht": [
        {"isim": "Grand Hotel Karel V Utrecht", "email": "info@karelv.nl", "ulke": "NL"},
        {"isim": "Restaurant Karel 5 Utrecht", "email": "restaurant@karelv.nl", "ulke": "NL"},
        {"isim": "Restaurant Maeve Utrecht", "email": "info@restaurantmaeve.nl", "ulke": "NL"}
    ],
    "lahey": [
        {"isim": "Hotel Des Indes The Hague", "email": "resintouch@hoteldesindes.nl", "ulke": "NL"},
        {"isim": "Grand Hotel Amrâth Kurhaus The Hague", "email": "info@amrathkurhaus.com", "ulke": "NL"},
        {"isim": "Restaurant Calla's The Hague", "email": "info@restaurantcallas.nl", "ulke": "NL"}
    ],
    "eindhoven": [
        {"isim": "Kazerne Design Hotel Eindhoven", "email": "reservations@kazerne.com", "ulke": "NL"},
        {"isim": "Restaurant Zarzo Eindhoven", "email": "info@zarzo.nl", "ulke": "NL"},
        {"isim": "Restaurant Wiesen Eindhoven", "email": "info@wiesen.nl", "ulke": "NL"}
    ],
    "maastricht": [
        {"isim": "Kruisherenhotel Maastricht", "email": "info@kruisherenhotel.chateauhotels.nl", "ulke": "NL"},
        {"isim": "Restaurant Beluga Loves You Maastricht", "email": "info@belugalovesyou.com", "ulke": "NL"},
        {"isim": "Château Neercanne Maastricht", "email": "info@neercanne.chateauhotels.nl", "ulke": "NL"}
    ],

    # ================= İTALYA =================
    "roma": [
        {"isim": "Hotel Eden Rome Dorchester", "email": "reservations.her@dorchestercollection.com", "ulke": "IT"},
        {"isim": "Hotel de Russie Rocco Forte Rome", "email": "reservations.derussie@roccofortehotels.com", "ulke": "IT"},
        {"isim": "Rome Cavalieri Waldorf Astoria", "email": "romhi.guestrelations@waldorfastoria.com", "ulke": "IT"},
        {"isim": "The St. Regis Rome", "email": "stregisrome@stregis.com", "ulke": "IT"},
        {"isim": "Hotel Hassler Roma", "email": "booking@hotelhassler.it", "ulke": "IT"},
        {"isim": "Il Pagliaccio Rome", "email": "info@ristoranteilpagliaccio.com", "ulke": "IT"}
    ],
    "milano": [
        {"isim": "Bulgari Hotel Milano", "email": "milano@bulgarihotels.com", "ulke": "IT"},
        {"isim": "Four Seasons Hotel Milano", "email": "milano@fourseasons.com", "ulke": "IT"},
        {"isim": "Mandarin Oriental Milan", "email": "momln-info@mohg.com", "ulke": "IT"},
        {"isim": "Armani Hotel Milano", "email": "milan@armanihotels.com", "ulke": "IT"},
        {"isim": "Enrico Bartolini al Mudec", "email": "info@enricobartolini.net", "ulke": "IT"}
    ],
    "floransa": [
        {"isim": "Four Seasons Hotel Firenze", "email": "flo.reservations@fourseasons.com", "ulke": "IT"},
        {"isim": "The St. Regis Florence", "email": "streflorence@stregis.com", "ulke": "IT"},
        {"isim": "Enoteca Pinchiorri Firenze", "email": "ristorante@enotecapinchiorri.com", "ulke": "IT"}
    ],
    "venedik": [
        {"isim": "The Gritti Palace Venice", "email": "grittipalace@luxurycollection.com", "ulke": "IT"},
        {"isim": "Hotel Danieli Venice", "email": "danieli@fourseasons.com", "ulke": "IT"},
        {"isim": "Aman Venice", "email": "amanvenice.res@aman.com", "ulke": "IT"},
        {"isim": "Ristorante Quadri Venice", "email": "info@alajmo.it", "ulke": "IT"}
    ],
    "napoli": [
        {"isim": "Grand Hotel Vesuvio Napoli", "email": "info@vesuvio.it", "ulke": "IT"},
        {"isim": "Romeo Hotel Napoli", "email": "reservations@romeohotel.it", "ulke": "IT"},
        {"isim": "Palazzo Petrucci Napoli", "email": "info@palazzopetrucci.it", "ulke": "IT"}
    ],
    "torino": [
        {"isim": "Grand Hotel Sitea Torino", "email": "info@grandhotelsitea.it", "ulke": "IT"},
        {"isim": "Principi di Piemonte UNA Esperienze", "email": "principi.to@unaesperienze.it", "ulke": "IT"},
        {"isim": "Ristorante Del Cambio Torino", "email": "welcome@delcambio.it", "ulke": "IT"}
    ],
    "bologna": [
        {"isim": "Grand Hotel Majestic gia Baglioni Bologna", "email": "info.ghmajestic@baglionihotels.com", "ulke": "IT"},
        {"isim": "Iacobucci Restaurant Bologna", "email": "prenotazioni@ristoranteiacobucci.it", "ulke": "IT"}
    ],
    "verona": [
        {"isim": "Due Torri Hotel Verona", "email": "duetorrihotelverona@duetorrihotels.com", "ulke": "IT"},
        {"isim": "Ristorante 12 Apostoli Verona", "email": "info@12apostoli.com", "ulke": "IT"}
    ],
    "palermo": [
        {"isim": "Villa Igiea Rocco Forte Palermo", "email": "reservations.villaigiea@roccofortehotels.com", "ulke": "IT"},
        {"isim": "Grand Hotel Wagner Palermo", "email": "info@grandhotelwagner.it", "ulke": "IT"},
        {"isim": "Ristorante Gagini Palermo", "email": "info@gaginirestaurant.com", "ulke": "IT"}
    ],
    "amalfi": [
        {"isim": "Hotel Santa Caterina Amalfi", "email": "info@hotelsantacaterina.it", "ulke": "IT"},
        {"isim": "Belmond Hotel Caruso Ravello", "email": "reservations.car@belmond.com", "ulke": "IT"},
        {"isim": "Le Sirenuse Positano", "email": "info@sirenuse.it", "ulke": "IT"}
    ],

    # ================= FRANSA =================
    "paris": [
        {"isim": "The Ritz Paris", "email": "contact@ritzparis.com", "ulke": "FR"},
        {"isim": "Le Meurice Dorchester Collection", "email": "reservations.lmp@dorchestercollection.com", "ulke": "FR"},
        {"isim": "Hotel de Crillon Rosewood", "email": "crillon@rosewoodhotels.com", "ulke": "FR"},
        {"isim": "Four Seasons Hotel George V Paris", "email": "reservation.paris@fourseasons.com", "ulke": "FR"},
        {"isim": "Plaza Athenee Paris", "email": "reservations.hpa@dorchestercollection.com", "ulke": "FR"},
        {"isim": "Shangri-La Paris", "email": "paris@shangri-la.com", "ulke": "FR"},
        {"isim": "Restaurant Guy Savoy Paris", "email": "reservations@guysavoy.com", "ulke": "FR"}
    ],
    "lyon": [
        {"isim": "InterContinental Lyon Hotel Dieu", "email": "lyon@ihg.com", "ulke": "FR"},
        {"isim": "Villa Florentine Lyon", "email": "florentine@relaischateaux.com", "ulke": "FR"},
        {"isim": "Restaurant Paul Bocuse Lyon", "email": "reservation@bocuse.fr", "ulke": "FR"}
    ],
    "nice": [
        {"isim": "Hotel Negresco Nice", "email": "concierge@hotel-negresco.com", "ulke": "FR"},
        {"isim": "Hyatt Regency Nice Palais de la Mediterranee", "email": "nice.regency@hyatt.com", "ulke": "FR"},
        {"isim": "Le Chantecler Nice", "email": "chantecler@hotel-negresco.com", "ulke": "FR"}
    ],
    "bordeaux": [
        {"isim": "InterContinental Bordeaux Le Grand Hotel", "email": "info.bordeaux@ihg.com", "ulke": "FR"},
        {"isim": "Le Pressoir d'Argent Gordon Ramsay", "email": "pressoir.bordeaux@ihg.com", "ulke": "FR"},
        {"isim": "La Grande Maison de Bernard Magrez", "email": "contact@lagrandemaison-bordeaux.com", "ulke": "FR"}
    ],
    "marsilya": [
        {"isim": "InterContinental Marseille Hotel Dieu", "email": "marseille@ihg.com", "ulke": "FR"},
        {"isim": "Le Petit Nice Passedat", "email": "contact@passedat.fr", "ulke": "FR"},
        {"isim": "Sofitel Marseille Vieux Port", "email": "h0542@sofitel.com", "ulke": "FR"}
    ],
    "strasbourg": [
        {"isim": "Hotel Regent Petite France Strasbourg", "email": "info@regent-petite-france.com", "ulke": "FR"},
        {"isim": "Restaurant Au Crocodile Strasbourg", "email": "contact@au-crocodile.com", "ulke": "FR"},
        {"isim": "Sofitel Strasbourg Grande Ile", "email": "h0568@sofitel.com", "ulke": "FR"}
    ],
    "toulouse": [
        {"isim": "Le Grand Balcon Hotel Toulouse", "email": "contact@grandbalconhotel.com", "ulke": "FR"},
        {"isim": "Restaurant Michel Sarran Toulouse", "email": "contact@michel-sarran.com", "ulke": "FR"},
        {"isim": "La Cour des Consuls Hotel & Spa MGallery", "email": "h9517@accor.com", "ulke": "FR"}
    ],
    "cannes": [
        {"isim": "Hotel Martinez Cannes Hyatt", "email": "martinez.reservation@hyatt.com", "ulke": "FR"},
        {"isim": "InterContinental Carlton Cannes", "email": "carlton@ihg.com", "ulke": "FR"},
        {"isim": "La Palme d'Or Cannes", "email": "palmedor-martinez@hyatt.com", "ulke": "FR"}
    ],
    "monaco": [
        {"isim": "Hotel de Paris Monte-Carlo", "email": "reserva@sbm.mc", "ulke": "MC"},
        {"isim": "Hotel Hermitage Monte-Carlo", "email": "vipreserva@sbm.mc", "ulke": "MC"},
        {"isim": "Le Louis XV Alain Ducasse Monaco", "email": "lelouisxv@sbm.mc", "ulke": "MC"}
    ],

    # ================= İSPANYA =================
    "madrid": [
        {"isim": "Four Seasons Hotel Madrid", "email": "madrid@fourseasons.com", "ulke": "ES"},
        {"isim": "Mandarin Oriental Ritz Madrid", "email": "mormd-reservations@mohg.com", "ulke": "ES"},
        {"isim": "The Westin Palace Madrid", "email": "palace@westin.com", "ulke": "ES"},
        {"isim": "DiverXO Madrid", "email": "info@diverxo.com", "ulke": "ES"}
    ],
    "barcelona": [
        {"isim": "Hotel Arts Barcelona Ritz-Carlton", "email": "artsreservations@ritzcarlton.com", "ulke": "ES"},
        {"isim": "Mandarin Oriental Barcelona", "email": "mobcn-info@mohg.com", "ulke": "ES"},
        {"isim": "W Barcelona Hotel", "email": "reservaswbarcelona@whotels.com", "ulke": "ES"},
        {"isim": "Restaurant Lasarte Barcelona", "email": "info@restaurantlasarte.com", "ulke": "ES"},
        {"isim": "ABaC Restaurant Barcelona", "email": "hotel@abacbarcelona.com", "ulke": "ES"}
    ],
    "valencia": [
        {"isim": "The Westin Valencia", "email": "reservas@westinvalencia.com", "ulke": "ES"},
        {"isim": "Hotel Las Arenas Balneario Resort", "email": "reservas@hotelvalencialasarenas.com", "ulke": "ES"},
        {"isim": "Restaurant Ricard Camarena Valencia", "email": "reservas@ricardcamarena.com", "ulke": "ES"}
    ],
    "sevilla": [
        {"isim": "Hotel Alfonso XIII Luxury Collection Seville", "email": "alfonsoxiii@luxurycollection.com", "ulke": "ES"},
        {"isim": "Hotel Colon Gran Melia Seville", "email": "gran.melia.colon@melia.com", "ulke": "ES"},
        {"isim": "Restaurant Abantal Sevilla", "email": "abantal@abantalrestaurante.es", "ulke": "ES"}
    ],
    "sansebastian": [
        {"isim": "Hotel Maria Cristina Luxury Collection", "email": "mariacristina@luxurycollection.com", "ulke": "ES"},
        {"isim": "Restaurant Arzak San Sebastian", "email": "arzak@arzak.es", "ulke": "ES"},
        {"isim": "Akelarre Restaurant & Hotel Pedro Subijana", "email": "restaurante@akelarre.net", "ulke": "ES"},
        {"isim": "Martin Berasategui Restaurant", "email": "restaurante@martinberasategui.com", "ulke": "ES"}
    ],
    "bilbao": [
        {"isim": "Gran Hotel Domine Bilbao", "email": "info@hoteldominebilbao.com", "ulke": "ES"},
        {"isim": "Hotel Carlton Bilbao", "email": "carlton@aranzazu-hoteles.com", "ulke": "ES"},
        {"isim": "Nerua Guggenheim Bilbao", "email": "info@neruaguggenheimbilbao.com", "ulke": "ES"}
    ],
    "malaga": [
        {"isim": "Gran Hotel Miramar Malaga", "email": "reservas@granhotelmiramarmalaga.com", "ulke": "ES"},
        {"isim": "Restaurant Kaleja Malaga", "email": "reservas@restaurantekaleja.com", "ulke": "ES"}
    ],

    # ================= PORTEKİZ =================
    "lizbon": [
        {"isim": "Four Seasons Hotel Ritz Lisbon", "email": "lisbon@fourseasons.com", "ulke": "PT"},
        {"isim": "Bairro Alto Hotel Lisbon", "email": "info@bairroaltohotel.com", "ulke": "PT"},
        {"isim": "Belcanto by José Avillez", "email": "belcanto@joseavillez.pt", "ulke": "PT"},
        {"isim": "Alma Restaurant Lisbon", "email": "alma@almarestaurante.pt", "ulke": "PT"},
        {"isim": "The Ivens Autograph Collection Lisbon", "email": "reservations@theivenshotel.com", "ulke": "PT"}
    ],
    "porto": [
        {"isim": "The Yeatman Hotel Porto", "email": "reservations@theyeatman.com", "ulke": "PT"},
        {"isim": "InterContinental Porto Palacio das Cardosas", "email": "porto@ihg.com", "ulke": "PT"},
        {"isim": "Casa de Chá da Boa Nova", "email": "boanova@ruipaula.com", "ulke": "PT"},
        {"isim": "Maison Albar Hotels Le Monumental Palace", "email": "porto.reservation@maisonalbar.eu", "ulke": "PT"}
    ],
    "faro": [
        {"isim": "Vila Vita Parc Resort & Spa Algarve", "email": "reservas@vilavitaparc.com", "ulke": "PT"},
        {"isim": "Ocean Restaurant Algarve", "email": "info@restauranteocean.com", "ulke": "PT"},
        {"isim": "Pine Cliffs Hotel Luxury Collection Algarve", "email": "pinecliffs.reservations@luxurycollection.com", "ulke": "PT"}
    ],
    "funchal": [
        {"isim": "Belmond Reid's Palace Madeira", "email": "reservations.rdp@belmond.com", "ulke": "PT"},
        {"isim": "Il Gallo d'Oro The Cliff Bay", "email": "cliffbay@portobay.pt", "ulke": "PT"}
    ],

    # ================= İSVİÇRE & AVUSTURYA =================
    "zurich": [
        {"isim": "The Dolder Grand Zurich", "email": "info@thedoldergrand.com", "ulke": "CH"},
        {"isim": "Baur au Lac Zurich", "email": "info@bauraulac.ch", "ulke": "CH"},
        {"isim": "Park Hyatt Zurich", "email": "zurich.park@hyatt.com", "ulke": "CH"}
    ],
    "geneva": [
        {"isim": "The Ritz-Carlton Hotel de la Paix Geneva", "email": "geneva@ritzcarlton.com", "ulke": "CH"},
        {"isim": "Four Seasons Hotel des Bergues Geneva", "email": "geneva.reservations@fourseasons.com", "ulke": "CH"},
        {"isim": "Beau-Rivage Geneve", "email": "info@beau-rivage.ch", "ulke": "CH"}
    ],
    "basel": [
        {"isim": "Grand Hotel Les Trois Rois Basel", "email": "info@lestroisrois.com", "ulke": "CH"},
        {"isim": "Cheval Blanc by Peter Knogl Basel", "email": "chevalblanc@lestroisrois.com", "ulke": "CH"}
    ],
    "bern": [
        {"isim": "Hotel Bellevue Palace Bern", "email": "info@bellevue-palace.ch", "ulke": "CH"},
        {"isim": "Schweizerhof Bern & Spa", "email": "info@schweizerhofbern.com", "ulke": "CH"}
    ],
    "lucerne": [
        {"isim": "Mandarin Oriental Palace Luzern", "email": "molzn-reservations@mohg.com", "ulke": "CH"},
        {"isim": "Bürgenstock Hotel & Alpine Spa", "email": "information@burgenstockresort.com", "ulke": "CH"}
    ],
    "stmoritz": [
        {"isim": "Badrutt's Palace Hotel St. Moritz", "email": "reservations@badruttspalace.com", "ulke": "CH"},
        {"isim": "Kulm Hotel St. Moritz", "email": "reservations@kulm.com", "ulke": "CH"}
    ],
    "vienna": [
        {"isim": "Hotel Sacher Wien", "email": "wien@sacher.com", "ulke": "AT"},
        {"isim": "The Ritz-Carlton Vienna", "email": "vienna.info@ritzcarlton.com", "ulke": "AT"},
        {"isim": "Restaurant Steirereck Vienna", "email": "wien@steirereck.at", "ulke": "AT"},
        {"isim": "Park Hyatt Vienna", "email": "vienna.park@hyatt.com", "ulke": "AT"}
    ],
    "salzburg": [
        {"isim": "Hotel Sacher Salzburg", "email": "salzburg@sacher.com", "ulke": "AT"},
        {"isim": "Hotel Schloss Mönchstein Salzburg", "email": "salzburg@monchstein.at", "ulke": "AT"},
        {"isim": "Restaurant Ikarus Hangar-7 Salzburg", "email": "ikarus@hangar-7.com", "ulke": "AT"}
    ],
    "innsbruck": [
        {"isim": "Grand Hotel Europa Innsbruck", "email": "info@grandhoteleuropa.at", "ulke": "AT"},
        {"isim": "Restaurant Lichtblick Innsbruck", "email": "restaurant@lichtblick.at", "ulke": "AT"}
    ],
    "graz": [
        {"isim": "Schlossberghotel Graz", "email": "office@schlossberghotel.at", "ulke": "AT"},
        {"isim": "Restaurant Schlossberg Graz", "email": "office@schlossberg-graz.at", "ulke": "AT"}
    ],

    # ================= İNGİLTERE & İRLANDA =================
    "london": [
        {"isim": "The Savoy London", "email": "savoy@fairmont.com", "ulke": "GB"},
        {"isim": "The Ritz London", "email": "enquire@theritzlondon.com", "ulke": "GB"},
        {"isim": "Claridge's London", "email": "info@claridges.co.uk", "ulke": "GB"},
        {"isim": "The Dorchester London", "email": "reservations.tdl@dorchestercollection.com", "ulke": "GB"},
        {"isim": "Restaurant Gordon Ramsay London", "email": "royalhospitalroad@gordonramsay.com", "ulke": "GB"},
        {"isim": "Core by Clare Smyth London", "email": "info@corebyclaresmyth.com", "ulke": "GB"}
    ],
    "edinburgh": [
        {"isim": "The Balmoral Rocco Forte Edinburgh", "email": "reservations.balmoral@roccofortehotels.com", "ulke": "GB"},
        {"isim": "Restaurant The Kitchin Edinburgh", "email": "info@thekitchin.com", "ulke": "GB"},
        {"isim": "Restaurant Martin Wishart Edinburgh", "email": "info@martin-wishart.co.uk", "ulke": "GB"}
    ],
    "manchester": [
        {"isim": "The Lowry Hotel Manchester", "email": "enquiries@thelowryhotel.com", "ulke": "GB"},
        {"isim": "Restaurant Mana Manchester", "email": "reservations@manamcr.com", "ulke": "GB"},
        {"isim": "The Edwardian Manchester Radisson", "email": "manchester@theedwardian.com", "ulke": "GB"}
    ],
    "birmingham": [
        {"isim": "The Grand Hotel Birmingham", "email": "hello@thegrandhotelbirmingham.co.uk", "ulke": "GB"},
        {"isim": "Opheem Restaurant Birmingham", "email": "info@opheem.com", "ulke": "GB"},
        {"isim": "Simpsons Restaurant Birmingham", "email": "info@simpsonsrestaurant.co.uk", "ulke": "GB"}
    ],
    "liverpool": [
        {"isim": "Titanic Hotel Liverpool", "email": "info@titanichotelliverpool.com", "ulke": "GB"},
        {"isim": "The Art School Restaurant Liverpool", "email": "eat@theartschoolrestaurant.co.uk", "ulke": "GB"}
    ],
    "dublin": [
        {"isim": "The Merrion Hotel Dublin", "email": "info@merrionhotel.com", "ulke": "IE"},
        {"isim": "The Shelbourne Autograph Collection Dublin", "email": "theshelbourne.info@marriott.com", "ulke": "IE"},
        {"isim": "Chapter One by Mickael Viljanen", "email": "info@chapteronerestaurant.com", "ulke": "IE"},
        {"isim": "Restaurant Patrick Guilbaud", "email": "restaurantpatrickguilbaud@eircom.net", "ulke": "IE"},
        {"isim": "The Westbury Dublin", "email": "westbury@doylecollection.com", "ulke": "IE"}
    ],
    "cork": [
        {"isim": "Castlemartyr Resort Cork", "email": "info@castlemartyrresort.ie", "ulke": "IE"},
        {"isim": "Terre Restaurant Castlemartyr", "email": "info@terre.ie", "ulke": "IE"},
        {"isim": "The River Lee Hotel Cork", "email": "riverlee@doylecollection.com", "ulke": "IE"}
    ],
    "galway": [
        {"isim": "The g Hotel & Spa Galway", "email": "stay@theg.ie", "ulke": "IE"},
        {"isim": "Aniar Restaurant Galway", "email": "food@aniarrestaurant.jp", "ulke": "IE"}
    ],

    # ================= BELÇİKA =================
    "brussels": [
        {"isim": "Hotel Amigo Rocco Forte Brussels", "email": "reservations.amigo@roccofortehotels.com", "ulke": "BE"},
        {"isim": "Steigenberger Wiltcher's Brussels", "email": "brussels@steigenberger.com", "ulke": "BE"},
        {"isim": "Comme Chez Soi Brussels", "email": "info@commechezsoi.be", "ulke": "BE"},
        {"isim": "The Hotel Brussels", "email": "book@thehotel.be", "ulke": "BE"}
    ],
    "antwerp": [
        {"isim": "Botanic Sanctuary Antwerp", "email": "info@botanicantwerp.com", "ulke": "BE"},
        {"isim": "The Jane Antwerp", "email": "contact@thejaneantwerp.com", "ulke": "BE"}
    ],
    "gent": [
        {"isim": "1898 The Post Ghent", "email": "info@1898thepost.com", "ulke": "BE"},
        {"isim": "Restaurant Oak Gent", "email": "info@oakgent.be", "ulke": "BE"}
    ],
    "brugge": [
        {"isim": "Hotel Dukes' Palace Bruges", "email": "info@hoteldukespalace.com", "ulke": "BE"},
        {"isim": "Restaurant De Karmeliet Bruges", "email": "info@dekarmeliet.be", "ulke": "BE"}
    ],

    # ================= İSKANDİNAVYA =================
    "kopenhag": [
        {"isim": "Hotel d'Angleterre Copenhagen", "email": "info@dangleterre.com", "ulke": "DK"},
        {"isim": "Geranium Restaurant Copenhagen", "email": "info@geranium.dk", "ulke": "DK"},
        {"isim": "Noma Copenhagen", "email": "booking@noma.dk", "ulke": "DK"},
        {"isim": "Alchemist Copenhagen", "email": "restaurant@alchemist.dk", "ulke": "DK"},
        {"isim": "Villa Copenhagen", "email": "info@villacph.com", "ulke": "DK"},
        {"isim": "Nimb Hotel Copenhagen", "email": "contact@nimb.dk", "ulke": "DK"}
    ],
    "aarhus": [
        {"isim": "Radisson Blu Scandinavia Hotel Aarhus", "email": "info.aarhus@radissonblu.com", "ulke": "DK"},
        {"isim": "Restaurant Frederikshøj Aarhus", "email": "info@frederikshoj.com", "ulke": "DK"},
        {"isim": "Restaurant Gastromé Aarhus", "email": "info@gastrome.dk", "ulke": "DK"}
    ],
    "stockholm": [
        {"isim": "Grand Hôtel Stockholm", "email": "info@grandhotel.se", "ulke": "SE"},
        {"isim": "Bank Hotel Stockholm", "email": "contact@bankhotel.se", "ulke": "SE"},
        {"isim": "Restaurant Frantzén Stockholm", "email": "reservation@restaurantfrantzen.com", "ulke": "SE"},
        {"isim": "Ett Hem Stockholm", "email": "mail@etthem.se", "ulke": "SE"},
        {"isim": "Operakällaren Stockholm", "email": "info@operakallaren.se", "ulke": "SE"}
    ],
    "goteborg": [
        {"isim": "Upper House Gothenburg", "email": "info@upperhouse.se", "ulke": "SE"},
        {"isim": "Restaurant 28+ Gothenburg", "email": "kontakt@28plus.se", "ulke": "SE"},
        {"isim": "Dorsia Hotel & Restaurant Gothenburg", "email": "reservation@dorsia.se", "ulke": "SE"}
    ],
    "malmo": [
        {"isim": "The Duxiana Malmö", "email": "malmo@theduxiana.com", "ulke": "SE"},
        {"isim": "Restaurant Vollmers Malmö", "email": "info@vollmers.nu", "ulke": "SE"}
    ],
    "oslo": [
        {"isim": "Grand Hotel Oslo", "email": "reservations@grand.no", "ulke": "NO"},
        {"isim": "The Thief Oslo", "email": "stay@thethief.com", "ulke": "NO"},
        {"isim": "Maaemo Restaurant Oslo", "email": "booking@maaemo.no", "ulke": "NO"},
        {"isim": "Sommerro Hotel Oslo", "email": "stay@sommerrohouse.com", "ulke": "NO"}
    ],
    "bergen": [
        {"isim": "Opus XVI Bergen", "email": "booking@opusxvi.no", "ulke": "NO"},
        {"isim": "Restaurant Lysverket Bergen", "email": "booking@lysverket.no", "ulke": "NO"},
        {"isim": "Bergen Børs Hotel", "email": "post@bergenbors.no", "ulke": "NO"}
    ],
    "trondheim": [
        {"isim": "Britannia Hotel Trondheim", "email": "post@britannia.no", "ulke": "NO"},
        {"isim": "Speilsalen at Britannia Trondheim", "email": "speilsalen@britannia.no", "ulke": "NO"},
        {"isim": "Credo Restaurant Trondheim", "email": "post@restaurantcredo.no", "ulke": "NO"}
    ],
    "stavanger": [
        {"isim": "Eilert Smith Hotel Stavanger", "email": "booking@eilertsmith.no", "ulke": "NO"},
        {"isim": "RE-NAA Restaurant Stavanger", "email": "post@re-naa.no", "ulke": "NO"}
    ],
    "helsinki": [
        {"isim": "Hotel Kämp Helsinki", "email": "hotelkamp@kampingroup.com", "ulke": "FI"},
        {"isim": "Hotel St. George Helsinki", "email": "stgeorge@stgeorgehelsinki.com", "ulke": "FI"},
        {"isim": "Palace Restaurant Helsinki", "email": "palace@palacerestaurant.fi", "ulke": "FI"},
        {"isim": "Restaurant Olo Helsinki", "email": "info@olo-ravintola.fi", "ulke": "FI"}
    ],
    "turku": [
        {"isim": "Kakola Hotel Turku", "email": "info@kakola.fi", "ulke": "FI"},
        {"isim": "Restaurant Kaskis Turku", "email": "info@kaskis.fi", "ulke": "FI"}
    ],
    "tampere": [
        {"isim": "Radisson Blu Grand Hotel Tammer Tampere", "email": "info.tammer.tampere@radissonblu.com", "ulke": "FI"},
        {"isim": "Restaurant Ravinteli Bertha Tampere", "email": "info@bertha.fi", "ulke": "FI"}
    ],

    # ================= ORTA VE DOĞU AVRUPA =================
    "prag": [
        {"isim": "Four Seasons Hotel Prague", "email": "prague@fourseasons.com", "ulke": "CZ"},
        {"isim": "The Grand Mark Prague", "email": "info@grandmark.cz", "ulke": "CZ"},
        {"isim": "Field Restaurant Prague", "email": "info@fieldrestaurant.cz", "ulke": "CZ"},
        {"isim": "La Degustation Boheme Bourgeoise", "email": "boheme@degustation.cz", "ulke": "CZ"},
        {"isim": "Augustine a Luxury Collection Hotel", "email": "augustine@luxurycollection.com", "ulke": "CZ"}
    ],
    "brno": [
        {"isim": "Barceló Brno Palace", "email": "brnopalace@barcelo.com", "ulke": "CZ"},
        {"isim": "Restaurant Castellana Trattoria Brno", "email": "info@trattoria.cz", "ulke": "CZ"}
    ],
    "budapeste": [
        {"isim": "Four Seasons Hotel Gresham Palace Budapest", "email": "budapest.reservations@fourseasons.com", "ulke": "HU"},
        {"isim": "The Ritz-Carlton Budapest", "email": "rc.budrz.reservations@ritzcarlton.com", "ulke": "HU"},
        {"isim": "Costes Restaurant Budapest", "email": "reservation@costes.hu", "ulke": "HU"},
        {"isim": "Borkonyha Winekitchen Budapest", "email": "borkonyha@borkonyha.hu", "ulke": "HU"},
        {"isim": "Matild Palace a Luxury Collection Hotel", "email": "info@matildpalace.com", "ulke": "HU"}
    ],
    "debrecen": [
        {"isim": "Hotel Divinus Debrecen", "email": "info@hoteldivinus.hu", "ulke": "HU"},
        {"isim": "IKON Restaurant Debrecen", "email": "ikon@ikonrestaurant.hu", "ulke": "HU"}
    ],
    "varsova": [
        {"isim": "Hotel Bristol a Luxury Collection Hotel Warsaw", "email": "bristol@luxurycollection.com", "ulke": "PL"},
        {"isim": "Raffles Europejski Warsaw", "email": "warsaw@raffles.com", "ulke": "PL"},
        {"isim": "Nuta Restaurant Warsaw", "email": "restauracja@nuta.com.pl", "ulke": "PL"},
        {"isim": "InterContinental Warsaw", "email": "warsaw@ihg.com", "ulke": "PL"}
    ],
    "krakow": [
        {"isim": "Hotel Copernicus Krakow", "email": "copernicus@hotel.com.pl", "ulke": "PL"},
        {"isim": "Bottiglieria 1881 Krakow", "email": "kontakt@1881.com.pl", "ulke": "PL"},
        {"isim": "Hotel Stary Krakow", "email": "stary@hotel.com.pl", "ulke": "PL"}
    ],
    "gdansk": [
        {"isim": "Radisson Blu Hotel Gdansk", "email": "info.gdansk@radissonblu.com", "ulke": "PL"},
        {"isim": "Restaurant Mercato Hilton Gdansk", "email": "gdansk.info@hilton.com", "ulke": "PL"}
    ],
    "wroclaw": [
        {"isim": "The Bridge Wroclaw MGallery", "email": "hb1z1@accor.com", "ulke": "PL"},
        {"isim": "Restaurant Acquario Wroclaw", "email": "hotel@monopolwroclaw.hotel.com.pl", "ulke": "PL"}
    ],
    "atina": [
        {"isim": "Hotel Grande Bretagne Athens", "email": "grandebretagne.reservation@luxurycollection.com", "ulke": "GR"},
        {"isim": "Four Seasons Astir Palace Hotel Athens", "email": "reservations.athens@fourseasons.com", "ulke": "GR"},
        {"isim": "Spondi Restaurant Athens", "email": "info@spondi.gr", "ulke": "GR"},
        {"isim": "King George Luxury Collection Athens", "email": "kinggeorge.reservation@luxurycollection.com", "ulke": "GR"},
        {"isim": "Botrini's Restaurant Athens", "email": "info@botrinis.com", "ulke": "GR"}
    ],
    "selanik": [
        {"isim": "The Met Hotel Thessaloniki", "email": "themethotel@chandris.gr", "ulke": "GR"},
        {"isim": "Daios Luxury Living Thessaloniki", "email": "info@daioshotels.com", "ulke": "GR"},
        {"isim": "Clochard Restaurant Thessaloniki", "email": "info@clochard.gr", "ulke": "GR"}
    ],
    "santorini": [
        {"isim": "Canaves Oia Suites Santorini", "email": "info@canaves.com", "ulke": "GR"},
        {"isim": "Katikies Santorini", "email": "info@katikies.com", "ulke": "GR"},
        {"isim": "Selene Restaurant Santorini", "email": "info@selene.gr", "ulke": "GR"}
    ],
    "mykonos": [
        {"isim": "Cavo Tagoo Mykonos", "email": "reservations@cavotagoo.com", "ulke": "GR"},
        {"isim": "Myconian Ambassador Relais & Chateaux", "email": "ambassador@myconiancollection.gr", "ulke": "GR"}
    ],
    "girit": [
        {"isim": "Blue Palace a Luxury Collection Resort Crete", "email": "reservations@bluepalace.gr", "ulke": "GR"},
        {"isim": "Elounda Mare Hotel Relais & Chateaux", "email": "mare@elounda.sa", "ulke": "GR"}
    ],

    # ================= AMERİKA BİRLEŞİK DEVLETLERİ =================
    "newyork": [
        {"isim": "The Plaza Hotel New York", "email": "theplaza@fairmont.com", "ulke": "US"},
        {"isim": "The Mark Hotel New York", "email": "info@themarkhotel.com", "ulke": "US"},
        {"isim": "The St. Regis New York", "email": "stregisnewyork@stregis.com", "ulke": "US"},
        {"isim": "The Carlyle Rosewood New York", "email": "thecarlyle@rosewoodhotels.com", "ulke": "US"},
        {"isim": "Eleven Madison Park NY", "email": "info@elevenmadisonpark.com", "ulke": "US"},
        {"isim": "Le Bernardin New York", "email": "reservations@le-bernardin.com", "ulke": "US"},
        {"isim": "Per Se New York", "email": "perseny@perseny.com", "ulke": "US"},
        {"isim": "Gramercy Tavern NY", "email": "info@gramercytavern.com", "ulke": "US"},
        {"isim": "Baccarat Hotel New York", "email": "baccaratguestservices@baccarathotels.com", "ulke": "US"}
    ],
    "chicago": [
        {"isim": "The Peninsula Chicago", "email": "pch@peninsula.com", "ulke": "US"},
        {"isim": "The Langham Chicago", "email": "tlchi.info@langhamhotels.com", "ulke": "US"},
        {"isim": "Alinea Restaurant Chicago", "email": "hospitality@alinearestaurant.com", "ulke": "US"},
        {"isim": "Waldorf Astoria Chicago", "email": "chigi.waldorf@waldorfastoria.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel Chicago", "email": "contactus.chicago@fourseasons.com", "ulke": "US"}
    ],
    "losangeles": [
        {"isim": "The Beverly Hills Hotel Dorchester", "email": "reservations.bhh@dorchestercollection.com", "ulke": "US"},
        {"isim": "Hotel Bel-Air Dorchester", "email": "reservations.hba@dorchestercollection.com", "ulke": "US"},
        {"isim": "Waldorf Astoria Beverly Hills", "email": "laxwa.waldorf@waldorfastoria.com", "ulke": "US"},
        {"isim": "Spago Beverly Hills Wolfgang Puck", "email": "spagobh@wolfgangpuck.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel Los Angeles at Beverly Hills", "email": "res.losangeles@fourseasons.com", "ulke": "US"}
    ],
    "sanfrancisco": [
        {"isim": "The Ritz-Carlton San Francisco", "email": "sanfrancisco@ritzcarlton.com", "ulke": "US"},
        {"isim": "The St. Regis San Francisco", "email": "stregissf@stregis.com", "ulke": "US"},
        {"isim": "Atelier Crenn San Francisco", "email": "contact@ateliercrenn.com", "ulke": "US"},
        {"isim": "Benu Restaurant San Francisco", "email": "contact@benusf.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel San Francisco", "email": "fourseasons@fourseasons.com", "ulke": "US"}
    ],
    "miami": [
        {"isim": "Faena Hotel Miami Beach", "email": "reservations-miamibeach@faena.com", "ulke": "US"},
        {"isim": "The Setai Miami Beach", "email": "setai@thesetaihotel.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel at The Surf Club Miami", "email": "surfclub@fourseasons.com", "ulke": "US"},
        {"isim": "Mandarin Oriental Miami", "email": "momia-reservations@mohg.com", "ulke": "US"}
    ],
    "boston": [
        {"isim": "The Newbury Boston", "email": "info@thenewburyboston.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel One Dalton Street Boston", "email": "reservations.onedalton@fourseasons.com", "ulke": "US"},
        {"isim": "Boston Harbor Hotel", "email": "reservations@bhh.com", "ulke": "US"},
        {"isim": "The Ritz-Carlton Boston", "email": "boston@ritzcarlton.com", "ulke": "US"}
    ],
    "lasvegas": [
        {"isim": "The Venetian Resort Las Vegas", "email": "reservations@venetianlasvegas.com", "ulke": "US"},
        {"isim": "Wynn Las Vegas", "email": "roomres@wynnlasvegas.com", "ulke": "US"},
        {"isim": "Bellagio Las Vegas", "email": "guestservices@bellagioresort.com", "ulke": "US"},
        {"isim": "Joël Robuchon Las Vegas", "email": "concierge@mgmgrand.com", "ulke": "US"}
    ],
    "washington": [
        {"isim": "The Hay-Adams Washington DC", "email": "reserve@hayadams.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel Washington DC", "email": "reservations.was@fourseasons.com", "ulke": "US"},
        {"isim": "The St. Regis Washington DC", "email": "stregisdc@stregis.com", "ulke": "US"},
        {"isim": "The Inn at Little Washington", "email": "reservations@theinnatlittlewashington.com", "ulke": "US"}
    ],
    "seattle": [
        {"isim": "Four Seasons Hotel Seattle", "email": "reservations.sea@fourseasons.com", "ulke": "US"},
        {"isim": "Canlis Restaurant Seattle", "email": "info@canlis.com", "ulke": "US"},
        {"isim": "The Fairmont Olympic Hotel Seattle", "email": "olympic@fairmont.com", "ulke": "US"}
    ],
    "austin": [
        {"isim": "Commodore Perry Estate Auberge Austin", "email": "cpe.reservations@aubergeresorts.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel Austin", "email": "reservations.aus@fourseasons.com", "ulke": "US"},
        {"isim": "The Driskill Austin", "email": "driskillguestservices@hyatt.com", "ulke": "US"}
    ],
    "houston": [
        {"isim": "The Post Oak Hotel at Uptown Houston", "email": "reservations@thepostoak.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel Houston", "email": "reservations.houston@fourseasons.com", "ulke": "US"},
        {"isim": "March Restaurant Houston", "email": "reservations@marchrestaurant.com", "ulke": "US"}
    ],
    "dallas": [
        {"isim": "The Ritz-Carlton Dallas", "email": "dallas.info@ritzcarlton.com", "ulke": "US"},
        {"isim": "Rosewood Mansion on Turtle Creek Dallas", "email": "themansion@rosewoodhotels.com", "ulke": "US"}
    ],
    "philadelphia": [
        {"isim": "Four Seasons Hotel Philadelphia at Comcast Center", "email": "philadelphia.reservations@fourseasons.com", "ulke": "US"},
        {"isim": "The Rittenhouse Philadelphia", "email": "rittenhouse@rittenhousehotel.com", "ulke": "US"},
        {"isim": "Zahav Restaurant Philadelphia", "email": "info@zahavrestaurant.com", "ulke": "US"}
    ],
    "atlanta": [
        {"isim": "The St. Regis Atlanta", "email": "stregisatlanta@stregis.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel Atlanta", "email": "contactus.atlanta@fourseasons.com", "ulke": "US"},
        {"isim": "Atlas Restaurant Atlanta", "email": "info@atlasrestaurant.com", "ulke": "US"}
    ],
    "sandiego": [
        {"isim": "The US Grant Luxury Collection San Diego", "email": "info@theusgrant.com", "ulke": "US"},
        {"isim": "Addison Restaurant San Diego", "email": "info@addisondelmar.com", "ulke": "US"}
    ],
    "denver": [
        {"isim": "The Brown Palace Hotel Denver", "email": "guestrelations@brownpalace.com", "ulke": "US"},
        {"isim": "The Ritz-Carlton Denver", "email": "denver.info@ritzcarlton.com", "ulke": "US"}
    ],
    "neworleans": [
        {"isim": "The Ritz-Carlton New Orleans", "email": "neworleans.info@ritzcarlton.com", "ulke": "US"},
        {"isim": "Four Seasons Hotel New Orleans", "email": "contactus.neworleans@fourseasons.com", "ulke": "US"},
        {"isim": "Commander's Palace New Orleans", "email": "info@commanderspalace.com", "ulke": "US"}
    ],
    "orlando": [
        {"isim": "Four Seasons Resort Orlando at Walt Disney World", "email": "reservations.orlando@fourseasons.com", "ulke": "US"},
        {"isim": "The Ritz-Carlton Orlando Grande Lakes", "email": "orlandograndelakes@ritzcarlton.com", "ulke": "US"}
    ],
    "honolulu": [
        {"isim": "Halekulani Hotel Honolulu", "email": "info@halekulani.com", "ulke": "US"},
        {"isim": "The Kahala Hotel & Resort Honolulu", "email": "reservations@kahalaresort.com", "ulke": "US"}
    ],
    "aspen": [
        {"isim": "The Little Nell Aspen", "email": "stay@thelittlenell.com", "ulke": "US"},
        {"isim": "Hotel Jerome Auberge Resorts Aspen", "email": "jerome.reservations@aubergeresorts.com", "ulke": "US"}
    ]
}

COUNTRY_DIRECTORIES = {
    "amerika": [
        "newyork", "chicago", "losangeles", "sanfrancisco", "miami",
        "boston", "lasvegas", "washington", "seattle", "austin",
        "houston", "dallas", "philadelphia", "atlanta", "sandiego",
        "denver", "neworleans", "orlando", "honolulu", "aspen"
    ],
    "almanya": [
        "berlin", "munich", "frankfurt", "hamburg", "koln",
        "dusseldorf", "stuttgart", "dresden", "leipzig", "hannover",
        "nurnberg", "bonn", "heidelberg", "badenbaden"
    ],
    "hollanda": [
        "amsterdam", "rotterdam", "utrecht", "lahey", "eindhoven", "maastricht"
    ],
    "italya": [
        "roma", "milano", "floransa", "venedik", "napoli",
        "torino", "bologna", "verona", "palermo", "amalfi"
    ],
    "fransa": [
        "paris", "lyon", "nice", "bordeaux", "marsilya",
        "strasbourg", "toulouse", "cannes", "monaco"
    ],
    "ispanya": [
        "madrid", "barcelona", "valencia", "sevilla",
        "sansebastian", "bilbao", "malaga"
    ],
    "portekiz": [
        "lizbon", "porto", "faro", "funchal"
    ],
    "isvicre": [
        "zurich", "geneva", "basel", "bern", "lucerne", "stmoritz"
    ],
    "avusturya": [
        "vienna", "salzburg", "innsbruck", "graz"
    ],
    "ingiltere": [
        "london", "edinburgh", "manchester", "birmingham", "liverpool"
    ],
    "irlanda": [
        "dublin", "cork", "galway"
    ],
    "belcika": [
        "brussels", "antwerp", "gent", "brugge"
    ],
    "iskandinavya": [
        "kopenhag", "aarhus", "stockholm", "goteborg", "malmo",
        "oslo", "bergen", "trondheim", "stavanger", "helsinki",
        "turku", "tampere"
    ],
    "cekyo": [
        "prag", "brno"
    ],
    "macaristan": [
        "budapeste", "debrecen"
    ],
    "polonya": [
        "varsova", "krakow", "gdansk", "wroclaw"
    ],
    "yunanistan": [
        "atina", "selanik", "santorini", "mykonos", "girit"
    ]
}

server = Flask(__name__)

@server.route('/')
def home():
    return "Bot ve Web Sunucusu 7/24 Aktif!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port, use_reloader=False)

def get_sent_history():
    """Hem kod içi kalıcı kümeden hem de sunucu hafızasından gönderilenleri çeker"""
    sent = set(PERMANENT_SENT_EMAILS)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                val = line.strip().lower()
                if val:
                    sent.add(val)
    return sent

def add_to_sent_history(email):
    """Gönderilen maili kalıcı hafıza dosyasına yazar"""
    try:
        clean = email.lower().strip()
        PERMANENT_SENT_EMAILS.add(clean)
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(clean + "\n")
    except Exception as e:
        logger.error(f"Hafıza dosyasına yazılamadı: {e}")

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

def mail_at_brevo(alici_mail, sirket, ulke):
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

def radar_gorevi(sehir_sorgu, chat_id, loop, bot_app):
    global RADAR_CALISIYOR
    RADAR_CALISIYOR = True

    sehir_anahtar = slugify(sehir_sorgu)
    hedefler = VERIFIED_DATABASE.get(sehir_anahtar, [])

    if not hedefler:
        for k, v in VERIFIED_DATABASE.items():
            if slugify(k) == sehir_anahtar:
                hedefler = v
                break

    if not hedefler:
        RADAR_CALISIYOR = False
        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ '{sehir_sorgu.capitalize()}' veritabanında bulunamadı.\n\n"
                     f"Ülkelerdeki tüm şehirleri listelemek ve tek tıkla eklemek için `/ulkeler` yazabilirsin!"
            ),
            loop
        )
        return

    ornek_ulke = hedefler[0]["ulke"]
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(chat_id=chat_id, text=f"🔍 Radar devrede: {sehir_sorgu.capitalize()} ({ornek_ulke}) taranıyor..."),
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
    bulunan_sayisi = 0

    for item in hedefler:
        m_clean = item["email"].lower().strip()
        sirket = item["isim"]
        item_ulke = item["ulke"]

        # Daha önce gönderildiyse doğrudan Gönderildi işaretle!
        baslangic_durum = "Gonderildi" if m_clean in sent_history else "Bekliyor"

        if m_clean not in mevcut_mailler:
            yeni_satir = pd.DataFrame([{
                "Isim": sirket,
                "Email": m_clean,
                "Ulke": item_ulke,
                "Durum": baslangic_durum
            }])
            df = pd.concat([df, yeni_satir], ignore_index=True)
            mevcut_mailler.add(m_clean)
            bulunan_sayisi += 1
            df.to_csv(CSV_FILE, index=False)

            durum_notu = " (Önceden Gönderilmişti)" if baslangic_durum == "Gonderildi" else ""
            asyncio.run_coroutine_threadsafe(
                bot_app.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎯 Hedef Algılandı!\nİşletme: {sirket}\nMail: {m_clean}\nÜlke: {item_ulke}{durum_notu}"
                ),
                loop
            )
            time.sleep(0.5)

    RADAR_CALISIYOR = False
    asyncio.run_coroutine_threadsafe(
        bot_app.bot.send_message(
            chat_id=chat_id,
            text=f"🏁 Radar tamamlandı! {sehir_sorgu.capitalize()} için {bulunan_sayisi} işletme listeye işlendi."
        ),
        loop
    )

def mail_gonderim_gorevi(chat_id, loop, bot_app):
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
    # Hafızadaki mailleri doğrudan 'Gonderildi'ye çek
    for idx, row in df.iterrows():
        m = str(row["Email"]).lower().strip()
        if m in sent_history and str(row["Durum"]).strip() != "Gonderildi":
            df.at[idx, "Durum"] = "Gonderildi"
    df.to_csv(CSV_FILE, index=False)

    bekleyenler = df[df["Durum"] != "Gonderildi"]
    if len(bekleyenler) == 0:
        asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(chat_id=chat_id, text="ℹ️ Listede bekleyen yeni işletme yok! Şehir ekleyebilirsiniz."),
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
                    text=f"✅ Gönderildi:\nİşletme: {sirket} ({ulke})\nMail: {email}"
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

def olustur_sehir_komut_listesi(ulke_kodu, baslik, sehir_listesi):
    satirlar = [f"📍 *{baslik} Şehirleri* (Tek tıkla radara ekle):\n"]
    for s in sehir_listesi:
        satirlar.append(f"/radar_{slugify(s)}")
    satirlar.append("\n💡 *İpucu:* Mavi komutun üzerine basman yeterli, otomatik eklenir!")
    return "\n".join(satirlar)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mesaj = (
        f"👋 Selam Ali! Küresel radar hazır.\n"
        f"Senin Chat ID: `{chat_id}`\n\n"
        "🌍 *Ülke Menüleri (Tüm Şehirleri Gör):*\n"
        "🇺🇸 /amerika - 20 ABD şehri\n"
        "🇩🇪 /almanya - 14 Alman şehri\n"
        "🇮🇹 /italya - 10 İtalyan şehri\n"
        "🇫🇷 /fransa - 9 Fransız şehri\n"
        "🇪🇸 /ispanya - 7 İspanyol şehri\n"
        "🇳🇱 /hollanda - 6 Hollanda şehri\n"
        "🇬🇧 /ingiltere - 5 İngiliz şehri\n"
        "🇮🇪 /irlanda - 3 İrlanda şehri\n"
        "🇨🇭 /isvicre - 6 İsviçre şehri\n"
        "🇦🇹 /avusturya - 4 Avusturya şehri\n"
        "🇵🇹 /portekiz - 4 Portekiz şehri\n"
        "🇧🇪 /belcika - 4 Belçika şehri\n"
        "❄️ /iskandinavya - Danimarka, İsveç, Norveç, Finlandiya\n"
        "🏛 /diger - Çekya, Macaristan, Polonya, Yunanistan\n"
        "📜 /ulkeler - Tüm ülkelerin tam listesi\n\n"
        "⚙️ *Operasyon Komutları:*\n"
        "🚀 /baslat - Gönderimi başlatır\n"
        "🛑 /durdur - Gönderimi durdurur\n"
        "📊 /durum - Liste durumunu gösterir\n"
        "💾 /csv_indir - Mevcut listeyi telefonuna indirir\n"
        "📥 *CSV Yükleme:* .csv dosyasını buraya atarsan listeyi anında günceller!"
    )
    await update.message.reply_text(mesaj, parse_mode="Markdown")

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

async def ulkeler_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "🌍 *Tüm Ülkeler ve Şehir Listeleri:*\n\n"
        "🇺🇸 /amerika\n"
        "🇩🇪 /almanya\n"
        "🇮🇹 /italya\n"
        "🇫🇷 /fransa\n"
        "🇪🇸 /ispanya\n"
        "🇳🇱 /hollanda\n"
        "🇬🇧 /ingiltere\n"
        "🇮🇪 /irlanda\n"
        "🇨🇭 /isvicre\n"
        "🇦🇹 /avusturya\n"
        "🇵🇹 /portekiz\n"
        "🇧🇪 /belcika\n"
        "❄️ /iskandinavya (Danimarka, İsveç, Norveç, Finlandiya)\n"
        "🇨🇿 /cekyo (Çekya)\n"
        "🇭🇺 /macaristan (Macaristan)\n"
        "🇵🇱 /polonya (Polonya)\n"
        "🇬🇷 /yunanistan (Yunanistan)\n\n"
        "Birine tıkla, o ülkedeki tüm şehirlerin tek tıkla çalışan `/radar_sehir` butonları gelsin!"
    )
    await update.message.reply_text(mesaj, parse_mode="Markdown")

async def amerika_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("amerika", "Amerika Birleşik Devletleri (ABD)", COUNTRY_DIRECTORIES["amerika"]),
        parse_mode="Markdown"
    )

async def almanya_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("almanya", "Almanya", COUNTRY_DIRECTORIES["almanya"]),
        parse_mode="Markdown"
    )

async def hollanda_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("hollanda", "Hollanda", COUNTRY_DIRECTORIES["hollanda"]),
        parse_mode="Markdown"
    )

async def italya_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("italya", "İtalya", COUNTRY_DIRECTORIES["italya"]),
        parse_mode="Markdown"
    )

async def fransa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("fransa", "Fransa & Monako", COUNTRY_DIRECTORIES["fransa"]),
        parse_mode="Markdown"
    )

async def ispanya_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("ispanya", "İspanya", COUNTRY_DIRECTORIES["ispanya"]),
        parse_mode="Markdown"
    )

async def portekiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("portekiz", "Portekiz", COUNTRY_DIRECTORIES["portekiz"]),
        parse_mode="Markdown"
    )

async def isvicre_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("isvicre", "İsviçre", COUNTRY_DIRECTORIES["isvicre"]),
        parse_mode="Markdown"
    )

async def avusturya_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("avusturya", "Avusturya", COUNTRY_DIRECTORIES["avusturya"]),
        parse_mode="Markdown"
    )

async def ingiltere_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("ingiltere", "Birleşik Krallık", COUNTRY_DIRECTORIES["ingiltere"]),
        parse_mode="Markdown"
    )

async def irlanda_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("irlanda", "İrlanda", COUNTRY_DIRECTORIES["irlanda"]),
        parse_mode="Markdown"
    )

async def belcika_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("belcika", "Belçika", COUNTRY_DIRECTORIES["belcika"]),
        parse_mode="Markdown"
    )

async def iskandinavya_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("iskandinavya", "İskandinavya (Danimarka, İsveç, Norveç, Finlandiya)", COUNTRY_DIRECTORIES["iskandinavya"]),
        parse_mode="Markdown"
    )

async def cekyo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("cekyo", "Çekya", COUNTRY_DIRECTORIES["cekyo"]),
        parse_mode="Markdown"
    )

async def macaristan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("macaristan", "Macaristan", COUNTRY_DIRECTORIES["macaristan"]),
        parse_mode="Markdown"
    )

async def polonya_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("polonya", "Polonya", COUNTRY_DIRECTORIES["polonya"]),
        parse_mode="Markdown"
    )

async def yunanistan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        olustur_sehir_komut_listesi("yunanistan", "Yunanistan & Adalar", COUNTRY_DIRECTORIES["yunanistan"]),
        parse_mode="Markdown"
    )

async def diger_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "🏛 *Orta ve Doğu Avrupa Ülkeleri:*\n\n"
        "🇨🇿 /cekyo - Prag, Brno\n"
        "🇭🇺 /macaristan - Budapeşte, Debrecen\n"
        "🇵🇱 /polonya - Varşova, Krakow, Gdansk, Wroclaw\n"
        "🇬🇷 /yunanistan - Atina, Selanik, Santorini, Mykonos, Girit\n\n"
        "Birine tıkla, şehirler gelsin!"
    )
    await update.message.reply_text(mesaj, parse_mode="Markdown")

async def radar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global RADAR_CALISIYOR
    chat_id = update.effective_chat.id
    if RADAR_CALISIYOR:
        await update.message.reply_text("⚠️ Radar şu anda işlem yapıyor, lütfen bekle.")
        return

    text = update.message.text.strip()
    if "_" in text:
        sehir = text.split("_", 1)[1].strip()
    else:
        args = context.args
        if not args:
            await update.message.reply_text(
                "Lütfen bir şehir belirt! Örn:\n/radar roma\n/radar newyork\n\n"
                "Ya da ülke komutunu yazarak tek tıkla ekle:\n/amerika, /almanya, /italya, /fransa..."
            )
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
    if "Durum" not in df.columns:
        df["Durum"] = "Bekliyor"

    sent_history = get_sent_history()
    # Hafızadakileri ekranda doğru göster
    gonderilen = len(df[(df["Durum"] == "Gonderildi") | (df["Email"].astype(str).str.lower().isin(sent_history))])
    toplam = len(df)
    kalan = max(0, toplam - gonderilen)

    await update.message.reply_text(
        f"📊 Durum Özeti:\n"
        f"Toplam Kayıtlı: {toplam}\n"
        f"Gönderilen: {gonderilen}\n"
        f"Kalan: {kalan}\n"
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
    bot_app.add_handler(CommandHandler("baslat", baslat_cmd))
    bot_app.add_handler(CommandHandler("durdur", durdur_cmd))
    bot_app.add_handler(CommandHandler("durum", durum_cmd))
    bot_app.add_handler(CommandHandler("ulkeler", ulkeler_cmd))
    bot_app.add_handler(CommandHandler("diger", diger_cmd))
    bot_app.add_handler(CommandHandler("csv_indir", csv_indir_cmd))

    bot_app.add_handler(MessageHandler(filters.Document.FileExtension("csv"), dosya_yukle_handler))

    bot_app.add_handler(CommandHandler("amerika", amerika_cmd))
    bot_app.add_handler(CommandHandler("almanya", almanya_cmd))
    bot_app.add_handler(CommandHandler("hollanda", hollanda_cmd))
    bot_app.add_handler(CommandHandler("italya", italya_cmd))
    bot_app.add_handler(CommandHandler("fransa", fransa_cmd))
    bot_app.add_handler(CommandHandler("ispanya", ispanya_cmd))
    bot_app.add_handler(CommandHandler("portekiz", portekiz_cmd))
    bot_app.add_handler(CommandHandler("isvicre", isvicre_cmd))
    bot_app.add_handler(CommandHandler("avusturya", avusturya_cmd))
    bot_app.add_handler(CommandHandler("ingiltere", ingiltere_cmd))
    bot_app.add_handler(CommandHandler("irlanda", irlanda_cmd))
    bot_app.add_handler(CommandHandler("belcika", belcika_cmd))
    bot_app.add_handler(CommandHandler("iskandinavya", iskandinavya_cmd))
    bot_app.add_handler(CommandHandler("cekyo", cekyo_cmd))
    bot_app.add_handler(CommandHandler("macaristan", macaristan_cmd))
    bot_app.add_handler(CommandHandler("polonya", polonya_cmd))
    bot_app.add_handler(CommandHandler("yunanistan", yunanistan_cmd))

    bot_app.add_handler(CommandHandler("radar", radar_cmd))

    kayitli_komutlar = set()
    for city_key in VERIFIED_DATABASE.keys():
        temiz_komut = slugify(f"radar_{city_key}")
        if temiz_komut not in kayitli_komutlar and len(temiz_komut) > 6:
            kayitli_komutlar.add(temiz_komut)
            bot_app.add_handler(CommandHandler(temiz_komut, radar_cmd))

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
