
import streamlit as st
from PIL import Image
import pytesseract
import pandas as pd
import gspread
import re
from google.oauth2.service_account import Credentials
from datetime import datetime
import base64

# Percorso locale a Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# === CONFIG ===
st.set_page_config(page_title="AL124 - Guardia di Finanza", layout="wide")

# === GOOGLE SHEET SETUP ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file("scannerpatenti-470044eb6405.json", scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("Controlli_Pattuglia").sheet1

# === STYLE / LOGO / BANNER ===
def show_banner():
    col1, col2, col3 = st.columns([1,3,1])
    with col2:
        st.image("sfondo.png", use_container_width=True)

    banner_style = """
    <style>
    .main {
        background-color: #1e1e1e;
        color: white;
    }
    </style>
    """
    st.markdown(banner_style, unsafe_allow_html=True)

show_banner()

# === FUNZIONI ===
def estrai_dati_patente(testo):
    righe = [r.strip() for r in testo.split("\n") if r.strip()]
    dati = {
        "COGNOME": "",
        "NOME": "",
        "DATA_NASCITA": "",
        "LUOGO_NASCITA": ""
    }

    for r in righe:
        if r.startswith("1."):
            dati["COGNOME"] = r[2:].strip()
        elif r.startswith("2."):
            dati["NOME"] = r[2:].strip()
        elif r.startswith("3."):
            match = re.search(r"(\d{2}/\d{2}/\d{2,4})\s+(.+)", r[2:].strip())
            if match:
                dati["DATA_NASCITA"] = match.group(1)
                dati["LUOGO_NASCITA"] = match.group(2)
    return dati

def aggiorna_su_google_sheets(dati_dict):
    values = [dati_dict[col] for col in COLUMNS]
    sheet.append_row(values)

def filtra_turno(df):
    oggi = datetime.now().strftime("%d/%m/%Y")
    return df[df["DATA_ORA"].str.startswith(oggi)]

COLUMNS = [
    "DATA_ORA", "COMUNE", "VEICOLO", "TARGA", "COGNOME", "NOME",
    "LUOGO_NASCITA", "DATA_NASCITA", "COMMERCIALE", "COPE", "RILIEVI", "CINOFILI"
]

# === INTERFACCIA CON SCHEDE ===
tabs = st.tabs(["📍START SOFFERMO", "📥 DATI SOGGETTO",  "🔁STOP SOFFERMO", "📋STATISTICA"])

# === TABS 1 ===
with tabs[0]:
    st.header("📍INIZIA IL POSTO DI CONTROLLO")
    comune = st.selectbox("Seleziona Comune del controllo", [
        "ALBERA LIGURE", "ARQUATA SCRIVIA", "BASALUZZO", "BORGHETTO DI BORBERA", "BOSIO",
        "CABELLA LIGURE", "CANTALUPO LIGURE", "CAPRIATA D'ORBA", "CARREGA LIGURE", "CARROSIO",
        "CASALEGGIO BOIRO", "CASTELLETTO D'ORBA", "FRACONALTO", "FRANCAVILLA BISIO", "GAVI",
        "GRONDONA", "LERMA", "MONGIARDINO LIGURE", "MONTALDEO", "MORNESE", "NOVI LIGURE",
        "PARODI LIGURE", "PASTURANA", "POZZOLO FORMIGARO", "ROCCAFORTE LIGURE", "ROCCHETTA LIGURE",
        "SAN CRISTOFORO", "SERRAVALLE SCRIVIA", "SILVANO D'ORBA", "STAZZANO", "TASSAROLO",
        "VOLTAGGIO", "VIGNOLE BORBERA"
    ])
    if st.tabs("📍START SOFFERMO"):
        st.session_state["comune_corrente"] = comune
        st.session_state["inizio_turno"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        st.success(f"Inizio soffermo nel comune di {comune} alle {st.session_state['inizio_turno']}")

# === TABS 2 ===
with tabs[1]:
    veicolo = st.text_input("Marca e Modello del veicolo")
    targa = st.text_input("Targa del veicolo")
    commerciale = st.radio("Veicolo commerciale?", ["SI", "NO"], horizontal=True)
    cope = st.radio("COPE?", ["SI", "NO"], horizontal=True)
    cinofili = st.radio("Intervento cinofili?", ["SI", "NO"], horizontal=True)
    rilievi_si = st.radio("Rilievi contestati?", ["SI", "NO"], horizontal=True)
    rilievi = ""
    if rilievi_si == "SI":
        rilievi = st.text_input("Specifica rilievi")

    uploaded_file = st.file_uploader("📸 Carica foto del documento", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        st.image(uploaded_file, caption="Documento caricato", use_container_width=True)
        image = Image.open(uploaded_file)
        with st.spinner("Estrazione dati in corso..."):
            testo_estratto = pytesseract.image_to_string(image, lang="ita")
            st.text_area("🔍 Testo estratto (OCR)", value=testo_estratto, height=200)
            dati_patente = estrai_dati_patente(testo_estratto)

            dati_finali = {
                "DATA_ORA": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "COMUNE": comune,
                "VEICOLO": veicolo.upper(),
                "TARGA": targa.upper(),
                "COGNOME": dati_patente["COGNOME"].upper(),
                "NOME": dati_patente["NOME"].upper(),
                "LUOGO_NASCITA": dati_patente["LUOGO_NASCITA"].upper(),
                "DATA_NASCITA": dati_patente["DATA_NASCITA"],
                "COMMERCIALE": commerciale,
                "COPE": cope,
                "RILIEVI": rilievi.upper() if rilievi_si == "SI" else "",
                "CINOFILI": cinofili
            }

            if st.button("📤 Salva Controllo"):
                try:
                    aggiorna_su_google_sheets(dati_finali)
                    st.success("Controllo salvato correttamente!")
                except Exception as e:
                    st.error(f"Errore durante il salvataggio: {e}")

# === TABS 3 ===
with tabs[2]:
    st.header("🔁STOP SOFFERMO")
    ora_fine = datetime.now().strftime("%d/%m/%Y %H:%M")
    comune = st.session_state.get("comune_corrente", "NON DEFINITO")
    ora_inizio = st.session_state.get("inizio_turno", "NON DEFINITA")
    st.success(f"✅ Il controllo nel comune di {comune} è terminato il {ora_fine}")
    st.info(f"⏱️ Orario del controllo: dalle {ora_inizio} alle {ora_fine}")
    if st.tabs("🔁STOP SOFFERMO"):
        st.session_state["comune_corrente"] = ""
        st.session_state["inizio_turno"] = ""
        st.success("Sessione TERMINATA.")

# === TABS 4 ===
with tabs[3]:
    st.header("📋STATISTICA")
    dati_raw = sheet.get_all_values()
    dati = [r for r in dati_raw if any(cell.strip() for cell in r)]

    if len(dati) > 5:
        intestazioni = [c.strip().upper() for c in dati[4]]
        df = pd.DataFrame(dati[5:], columns=intestazioni)

        st.subheader("📋 Report Controlli")
        st.dataframe(df)

        if "COMUNE" in df.columns and "DATA_ORA" in df.columns:
            comuni = df["COMUNE"].unique()
            st.markdown(f"### 🗂️ Rendicontazione attività per ciascun Comune")

            for comune in comuni:
                df_turno = df[df["COMUNE"] == comune]
                ora_inizio = df_turno["DATA_ORA"].min()
                ora_fine = df_turno["DATA_ORA"].max()
                tot_soggetti = len(df_turno)

                commerciali = df_turno["COMMERCIALE"].str.upper().eq("SI").sum() if "COMMERCIALE" in df_turno.columns else 0
                privati = tot_soggetti - commerciali

                st.markdown(f"""
                **📍 Comune:** {comune}  
                ⏱️ Inizio: `{ora_inizio}` — Fine: `{ora_fine}`  
                🚗 Totale mezzi controllati: `{tot_soggetti}`  
                🔧 Mezzi commerciali: `{commerciali}` — Privati: `{privati}`  
                👥 Soggetti controllati: `{tot_soggetti}`
                ---
                """)
        else:
            st.warning("Dati incompleti: impossibile filtrare per turno.")
    else:
        st.info("Nessun dato disponibile nel report.")
