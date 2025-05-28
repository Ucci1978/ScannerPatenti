import streamlit as st
from PIL import Image
import pytesseract
import pandas as pd
import gspread
import re
from google.oauth2.service_account import Credentials
from datetime import datetime
import json # Assicurati che json sia importato

# Percorso locale a Tesseract (da commentare o rimuovere per il deployment)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# === CONFIG ===
st.set_page_config(page_title="AL124 - Guardia di Finanza", layout="wide")

# --- DEBUG: Inizio script ---
st.write(f"DEBUG: Inizio esecuzione script. Comune corrente: {st.session_state.get('comune_corrente', 'NON INIZIALIZZATO')}")
if "select_comune_start" in st.session_state:
    st.write(f"DEBUG: st.session_state['select_comune_start'] = {st.session_state['select_comune_start']}")
# --- FINE DEBUG ---

# === GOOGLE SHEET SETUP ===
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

try:
    # RECUPERA LA STRINGA DALLE SECRETS (È UNA STRINGA, NON UN DIZIONARIO)
    creds_json_string = st.secrets["google_service_account_json"] 
    
    # PARSIFICA LA STRINGA IN UN DIZIONARIO PYTHON
    service_account_info = json.loads(creds_json_string) 
    
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("Controlli_Pattuglia").sheet1
except KeyError:
    st.error("Errore: La secret 'google_service_account_json' non è configurata o ha un nome errato. Verifica le tue Streamlit secrets.")
    st.stop()
except json.JSONDecodeError as e:
    st.error(f"Errore di decodifica JSON delle credenziali Google Sheets: {e}. Questo significa che il contenuto della secret non è un JSON valido. Controlla la formattazione, inclusi gli a capo e gli spazi.")
    st.stop()
except Exception as e:
    st.error(f"Errore generico durante l'autorizzazione di Google Sheets: {e}")
    st.stop()


# === STYLE / LOGO / BANNER ===
def show_banner():
    # Per deployment, assicurati che 'sfondo.png' sia accessibile (es. nella stessa cartella)
    st.image("sfondo.png", use_container_width=True)

    st.markdown("""
    <style>
    .main {
        background-color: #1e1e1e;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

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

    # Tentativo 1: Regex per trovare i campi più comuni sulle patenti italiane
    for r in righe:
        match_cognome = re.search(r"1\.\s*([A-Z\s]+)", r, re.IGNORECASE)
        if match_cognome and not dati["COGNOME"]:
            dati["COGNOME"] = match_cognome.group(1).strip()
            continue

        match_nome = re.search(r"2\.\s*([A-Z\s]+)", r, re.IGNORECASE)
        if match_nome and not dati["NOME"]:
            dati["NOME"] = match_nome.group(1).strip()
            continue
        
        match_data_luogo = re.search(r"3\.\s*(\d{2}[./-]\d{2}[./-]\d{2,4})\s*(\S.+)", r, re.IGNORECASE)
        if match_data_luogo and not dati["DATA_NASCITA"]:
            dati["DATA_NASCITA"] = match_data_luogo.group(1).replace('/', '.') # Uniforma il separatore
            dati["LUOGO_NASCITA"] = match_data_luogo.group(2).strip()
            continue
    
    return dati

def aggiorna_su_google_sheets(dati_dict):
    values = [dati_dict.get(col, "") for col in COLUMNS]
    sheet.append_row(values)

def get_current_data_from_sheet():
    data_raw = sheet.get_all_values()
    if not data_raw:
        return pd.DataFrame(columns=COLUMNS)
    
    header_row_index = -1
    for i, row in enumerate(data_raw):
        if "DATA_ORA" in [c.strip().upper() for c in row]:
            header_row_index = i
            break
    
    if header_row_index == -1:
        st.warning("Impossibile trovare le intestazioni nel foglio Google. Verificare il formato.")
        return pd.DataFrame(columns=COLUMNS)
    
    headers = [c.strip().upper() for c in data_raw[header_row_index]]
    data_rows = data_raw[header_row_index + 1:]
    
    data_rows = [r for r in data_rows if any(cell.strip() for cell in r)]

    df = pd.DataFrame(data_rows, columns=headers)
    return df


COLUMNS = [
    "DATA_ORA", "COMUNE", "VEICOLO", "TARGA", "COGNOME", "NOME",
    "LUOGO_NASCITA", "DATA_NASCITA", "COMMERCIALE", "COPE", "RILIEVI", "CINOFILI"
]

# Inizializzazione degli stati di sessione se non esistono
if "comune_corrente" not in st.session_state:
    st.session_state["comune_corrente"] = "NON DEFINITO"
if "inizio_turno" not in st.session_state:
    st.session_state["inizio_turno"] = ""
if "dati_precompilati" not in st.session_state:
    st.session_state["dati_precompilati"] = {}
if "df_controlli" not in st.session_state: # Inizializza anche questo per le statistiche
    st.session_state["df_controlli"] = pd.DataFrame(columns=COLUMNS)

# ================================================================
# TEST ISOLATO DEL PULSANTE: METTIAMO UN PULSANTE QUI FUORI DALLE TAB
# PER VEDERE SE VIENE RENDERIZZATO IN ASSOLUTO
# ================================================================
if st.button("TEST BUTTON - DEVE APPARIRE!", key="test_button_global"):
    st.write("DEBUG: Test button clicked!")
# ================================================================

# === INTERFACCIA CON SCHEDE ===
tabs = st.tabs(["📍START SOFFERMO", "📥 DATI SOGGETTO", "🔁STOP SOFFERMO", "📋STATISTICA"])

# === TABS 1: START SOFFERMO ===
with tabs[0]:
    st.header("📍INIZIA IL POSTO DI CONTROLLO")
    
    comuni_lista = [
        "ALBERA LIGURE", "ARQUATA SCRIVIA", "BASALUZZO", "BORGHETTO DI BORBERA", "BOSIO",
        "CABELLA LIGURE", "CANTALUPO LIGURE", "CAPRIATA D'ORBA", "CARREGA LIGURE", "CARROSIO",
        "CASALEGGIO BOIRO", "CASTELLETTO D'ORBA", "FRACONALTO", "FRANCAVILLA BISIO", "GAVI",
        "GRONDONA", "LERMA", "MONGIARDINO LIGURE", "MONTALDEO", "MORNESE", "NOVI LIGURE",
        "PARODI LIGURE", "PASTURANA", "POZZOLO FORMIGARO", "ROCCAFORTE LIGURE", "ROCCHETTA LIGURE",
        "SAN CRISTOFORO", "SERRAVALLE SCRIVIA", "SILVANO D'ORBA", "STAZZANO", "TASSAROLO",
        "VOLTAGGIO", "VIGNOLE BORBERA"
    ]
    # --- DEBUG: Stampa la lista dei comuni ---
    st.write(f"DEBUG: comuni_lista (lunghezza {len(comuni_lista)}): {comuni_lista}")

    current_comune_index = 0
    if st.session_state.get("comune_corrente") and st.session_state["comune_corrente"] in comuni_lista:
        current_comune_index = comuni_lista.index(st.session_state["comune_corrente"])

    comune_selezionato = st.selectbox(
        "Seleziona Comune del controllo", 
        options=comuni_lista, 
        index=current_comune_index, 
        key="select_comune_start"
    )

    st.write(f"DEBUG: Valore attuale di comune_selezionato (dopo selectbox): {comune_selezionato}")

    success_message_placeholder = st.empty() 

    # ====================================================================================================
    # IL TUO PULSANTE ORIGINALE
    # ====================================================================================================
    if st.button("🔴 INIZIA SOFFERMO", key="start_soffermo_button"):
        st.session_state["comune_corrente"] = comune_selezionato
        st.session_state["inizio_turno"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        success_message_placeholder.success(f"Inizio soffermo nel comune di **{st.session_state['comune_corrente']}** alle **{st.session_state['inizio_turno']}**")
        st.experimental_rerun() 
    # ====================================================================================================

    # Mostra lo stato corrente del soffermo
    if st.session_state.get("comune_corrente") and st.session_state["comune_corrente"] != "NON DEFINITO":
        st.info(f"Soffermo attualmente in corso a **{st.session_state['comune_corrente']}** (Iniziato alle {st.session_state['inizio_turno']})")
    else:
        st.info("Nessun soffermo attivo. Seleziona un comune e clicca 'INIZIA SOFFERMO'.")

# === TABS 2: DATI SOGGETTO ===
with tabs[1]:
    st.header("📥 INSERIMENTO DATI CONTROLLO")

    if st.session_state["comune_corrente"] == "NON DEFINITO":
        st.warning("⚠️ Per favore, inizia un nuovo posto di controllo nella tab '📍START SOFFERMO' prima di inserire i dati.")
    else:
        st.info(f"Stai registrando un controllo a **{st.session_state['comune_corrente']}**")

        col_input_veicolo, col_input_targa = st.columns(2)
        with col_input_veicolo:
            veicolo = st.text_input("Marca e Modello del veicolo", value=st.session_state.get('dati_precompilati', {}).get('VEICOLO', ''), key="veicolo_input")
        with col_input_targa:
            targa = st.text_input("Targa del veicolo", value=st.session_state.get('dati_precompilati', {}).get('TARGA', ''), key="targa_input")
        
        col_radio_commerciale, col_radio_cope = st.columns(2)
        with col_radio_commerciale:
            commerciale = st.radio("Veicolo commerciale?", ["NO", "SI"], horizontal=True, key="commerciale_radio")
        with col_radio_cope:
            cope = st.radio("COPE?", ["NO", "SI"], horizontal=True, key="cope_radio")
        
        col_radio_cinofili, col_radio_rilievi_si = st.columns(2)
        with col_radio_cinofili:
            cinofili = st.radio("Intervento cinofili?", ["NO", "SI"], horizontal=True, key="cinofili_radio")
        with col_radio_rilievi_si:
            rilievi_si = st.radio("Rilievi contestati?", ["NO", "SI"], horizontal=True, key="rilievi_radio")
        
        rilievi = ""
        if rilievi_si == "SI":
            rilievi = st.text_area("Specifica rilievi", value=st.session_state.get('dati_precompilati', {}).get('RILIEVI', ''), key="rilievi_text_area")

        st.markdown("---")
        st.subheader("Dati Documento")
        uploaded_file = st.file_uploader("📸 Carica foto del documento", type=["jpg", "jpeg", "png"], key="upload_document_file")
        
        if uploaded_file:
            st.image(uploaded_file, caption="Documento caricato", use_container_width=True)
            image = Image.open(uploaded_file)
            
            with st.spinner("Estrazione dati in corso..."):
                try:
                    testo_estratto = pytesseract.image_to_string(image, lang="ita")
                    st.text_area("🔍 Testo estratto (OCR)", value=testo_estratto, height=200, key="ocr_text_area")
                    dati_patente_ocr = estrai_dati_patente(testo_estratto)
                    st.session_state["dati_precompilati"] = dati_patente_ocr # Salva per precompilazione

                except Exception as e:
                    st.error(f"Errore durante l'OCR: {e}. Assicurati che Tesseract sia installato e configurato correttamente.")
                    testo_estratto = ""
                    st.session_state["dati_precompilati"] = {k: "" for k in COLUMNS} # Reset in caso di errore
        
        st.markdown("### 📝 Rivedi e Correggi Dati Estratti")
        # Ho aggiunto .upper() direttamente sul valore del text_input
        col_cognome, col_nome = st.columns(2)
        with col_cognome:
            cognome_input = st.text_input("Cognome", value=st.session_state.get('dati_precompilati', {}).get('COGNOME', '')).upper()
        with col_nome:
            nome_input = st.text_input("Nome", value=st.session_state.get('dati_precompilati', {}).get('NOME', '')).upper()

        col_luogo_nascita, col_data_nascita = st.columns(2)
        with col_luogo_nascita:
            luogo_nascita_input = st.text_input("Luogo di Nascita", value=st.session_state.get('dati_precompilati', {}).get('LUOGO_NASCITA', '')).upper()
        with col_data_nascita:
            data_nascita_input = st.text_input("Data di Nascita (GG/MM/AAAA)", value=st.session_state.get('dati_precompilati', {}).get('DATA_NASCITA', ''), key="data_nascita_input")

        if st.button("📤 Salva Controllo", key="salva_controllo_button"):
            if not st.session_state["comune_corrente"] or st.session_state["comune_corrente"] == "NON DEFINITO":
                st.error("Per favore, inizia un nuovo posto di controllo nella tab '📍START SOFFERMO' prima di salvare.")
            else:
                dati_finali = {
                    "DATA_ORA": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "COMUNE": st.session_state["comune_corrente"],
                    "VEICOLO": veicolo.upper(),
                    "TARGA": targa.upper(),
                    "COGNOME": cognome_input,
                    "NOME": nome_input,
                    "LUOGO_NASCITA": luogo_nascita_input,
                    "DATA_NASCITA": data_nascita_input,
                    "COMMERCIALE": commerciale,
                    "COPE": cope,
                    "RILIEVI": rilievi.upper() if rilievi_si == "SI" else "",
                    "CINOFILI": cinofili
                }

                try:
                    aggiorna_su_google_sheets(dati_finali)
                    st.success("Controllo salvato correttamente!")
                    st.session_state["dati_precompilati"] = {}
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Errore durante il salvataggio su Google Sheets: {e}")

# === TABS 3: STOP SOFFERMO ===
with tabs[2]:
    st.header("🔁STOP SOFFERMO")
    if st.session_state.get("comune_corrente", "NON DEFINITO") != "NON DEFINITO":
        st.info(f"Il controllo è attualmente in corso nel comune di **{st.session_state['comune_corrente']}** (Iniziato alle {st.session_state['inizio_turno']})")
        if st.button("✅ CONFERMA FINE SOFFERMO", key="stop_soffermo_button"):
            ora_fine = datetime.now().strftime("%d/%m/%Y %H:%M")
            st.success(f"✅ Il controllo nel comune di **{st.session_state['comune_corrente']}** è terminato il **{ora_fine}**")
            st.info(f"⏱️ Orario del controllo: dalle **{st.session_state['inizio_turno']}** alle **{ora_fine}**")
            st.session_state["comune_corrente"] = "NON DEFINITO"
            st.session_state["inizio_turno"] = ""
            st.success("Sessione di controllo TERMINATA.")
            st.experimental_rerun()
    else:
        st.info("Nessun posto di controllo attivo.")

# === TABS 4: STATISTICA ===
with tabs[3]:
    st.header("📋STATISTICHE GIORNALIERE E TOTALI")
    
    if st.button("🔄 Aggiorna Statistiche", key="update_stats_button"):
        st.session_state["df_controlli"] = get_current_data_from_sheet()

    # Carica i dati all'inizio o se non sono ancora in session_state
    if st.session_state["df_controlli"].empty and st.button("Carica Dati Iniziali", key="load_initial_data_button"):
        st.session_state["df_controlli"] = get_current_data_from_sheet()

    df = st.session_state["df_controlli"]
    
    if not df.empty:
        st.subheader("📋 Report Controlli Completo")
        st.dataframe(df)

        oggi = datetime.now().strftime("%d/%m/%Y")
        df_oggi = df[df["DATA_ORA"].str.startswith(oggi, na=False)].copy()

        if not df_oggi.empty and "COMUNE" in df_oggi.columns:
            st.markdown(f"### 📊 Statistiche Controlli del {oggi}")
            
            tot_soggetti_oggi = len(df_oggi)
            commerciali_oggi = df_oggi["COMMERCIALE"].str.upper().eq("SI").sum()
            privati_oggi = tot_soggetti_oggi - commerciali_oggi
            cope_oggi = df_oggi["COPE"].str.upper().eq("SI").sum()
            cinofili_oggi = df_oggi["CINOFILI"].str.upper().eq("SI").sum()
            rilievi_oggi = df_oggi[df_oggi["RILIEVI"].astype(str).str.strip() != ""].shape[0]

            st.markdown(f"""
            **Riepilogo della giornata:**
            - **Totale controlli (soggetti/veicoli):** `{tot_soggetti_oggi}`
            - **Mezzi commerciali:** `{commerciali_oggi}` — **Mezzi privati:** `{privati_oggi}`
            - **Interventi COPE:** `{cope_oggi}`
            - **Interventi Cinofili:** `{cinofili_oggi}`
            - **Rilievi contestati:** `{rilievi_oggi}`
            """)

            st.markdown("### 🗂️ Rendicontazione attività per ciascun Comune (Oggi)")
            
            df_oggi['COMUNE'] = df_oggi['COMUNE'].astype(str)

            comuni_oggi = df_oggi["COMUNE"].unique()

            for comune in comuni_oggi:
                df_comune_oggi = df_oggi[df_oggi["COMUNE"] == comune]
                
                ora_inizio_comune = df_comune_oggi["DATA_ORA"].min()
                ora_fine_comune = df_comune_oggi["DATA_ORA"].max()
                tot_soggetti_comune = len(df_comune_oggi)
                
                commerciali_comune = df_comune_oggi["COMMERCIALE"].str.upper().eq("SI").sum()
                privati_comune = tot_soggetti_comune - commerciali_comune
                
                st.markdown(f"""
                **📍 Comune:** {comune}  
                ⏱️ Primo controllo: `{ora_inizio_comune}` — Ultimo controllo: `{ora_fine_comune}`  
                🚗 Totale mezzi controllati: `{tot_soggetti_comune}`  
                🔧 Mezzi commerciali: `{commerciali_comune}` — Privati: `{privati_comune}`  
                ---
                """)
        else:
            st.info(f"Nessun dato di controllo disponibile per la giornata di oggi ({oggi}).")
    else:
        st.info("Nessun dato disponibile nel report generale. Carica i dati o effettua i controlli.")