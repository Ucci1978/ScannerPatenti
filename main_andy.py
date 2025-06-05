import streamlit as st
from PIL import Image
import pytesseract
import pandas as pd
import gspread
import re
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import io
import pillow_heif

# Registra il lettore HEIC (necessario per Pillow)
pillow_heif.register_heif_opener()

import pytz
rome_tz = pytz.timezone('Europe/Rome')
now_rome = datetime.now(pytz.utc).astimezone(rome_tz)
#current_datetime_str = now_rome.strftime("%Y-%m-%d %H:%M:%S")
# Percorso locale a Tesseract (LASCIAMO COMMENTATO PER IL DEPLOYMENT SU STREAMLIT CLOUD)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# === CONFIGURAZIONE PAGINA STREAMLIT ===
st.set_page_config(
    page_title="Scanner Patenti - GdF",
    page_icon="👮‍♂️", # Icona che appare nella tab del browser
    layout="centered", # 'centered' è solitamente migliore per mobile, 'wide' per desktop
    initial_sidebar_state="collapsed" # Per mantenere la sidebar nascosta all'inizio
)

# === GOOGLE SHEET SETUP ===
# Le tue credenziali e la configurazione di gspread
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

try:
    creds_json_string = st.secrets["google_service_account_json"]
    service_account_info = json.loads(creds_json_string)
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    client = gspread.authorize(creds)
    # Assicurati che "Controlli_Pattuglia" sia il nome corretto del tuo Google Sheet
    # e che sheet1 sia la scheda corretta.
    sheet = client.open("Controlli_Pattuglia").sheet1
except KeyError:
    st.error("Errore: La secret 'google_service_account_json' non è configurata o ha un nome errato. Verifica le tue Streamlit secrets.")
    # st.stop() # Commentato per permettere all'app di caricare anche senza credenziali, ma con errore visibile
except json.JSONDecodeError as e:
    st.error(f"Errore di decodifica JSON delle credenziali Google Sheets: {e}. Controlla la formattazione della secret.")
    # st.stop()
except Exception as e:
    st.error(f"Errore generico durante l'autorizzazione di Google Sheets: {e}. Controlla la connessione o i permessi.")
    # st.stop()

# === FUNZIONE BANNER (se 'sfondo.png' è un file locale, assicurati che sia nel repository) ===
st.title("COMPAGNIA NOVI LIGURE")
def show_banner():
    # Per un deployment, assicurati che 'sfondo.png' sia accessibile (es. nella stessa cartella del main_andy.py)
    try:
        st.image("sfondo.png", use_container_width=True) # use_column_width è più flessibile di use_container_width
    except FileNotFoundError:
        st.warning("File 'sfondo.png' non trovato. Assicurati che sia nel tuo repository.")
    
    st.markdown("""
    <style>
    .main {
        background-color: #1e1e1e; /* Il tuo colore di sfondo attuale */
        color: white; /* Colore testo principale */
    }
    /* Puoi aggiungere più CSS qui per personalizzare ulteriormente */
    </style>
    """, unsafe_allow_html=True)

# === FUNZIONI PER L'ESTRAZIONE E IL SALVATAGGIO DEI DATI ===
def estrai_dati_patente(testo):
    # Passaggio 1: Pulizia e normalizzazione del testo OCR
    # Converti tutto in maiuscolo per rendere le regex case-insensitive (anche se re.IGNORECASE aiuta)
    # Rimuovi i caratteri che spesso sono rumore o errori di OCR
    cleaned_text = testo.upper().replace(':', ' ').replace(';', ' ').replace('|', ' ').replace('O', '0').replace('I', '1').replace('L', '1')
    righe = [r.strip() for r in cleaned_text.split("\n") if r.strip()]

    dati = {
        "COGNOME": "",
        "NOME": "",
        "DATA_NASCITA": "",
        "LUOGO_NASCITA": ""
    }

    # Tentativi multipli per trovare i campi, usando diverse strategie

    # --- Estrazione del Cognome (Campo 1) ---
    # Cerca "1." o "COGNOME" o "SURNAME" o "1 COGNOME" e poi il cognome
    # La regex è più flessibile su spazi e caratteri (anche apostrofi e trattini)
    # Cerca la riga successiva se il dato non è sulla stessa riga di "1."
    pattern_cognome = r"(?:^|\n)(?:1[\.\s]?)?\s*(?:COGNOME|SURNAME|LAST NAME|COGNOMN?)?\s*([A-Z\s\'\-]+)"
    for i, r in enumerate(righe):
        match = re.search(pattern_cognome, r)
        if match:
            # Cattura il gruppo 1 (il cognome)
            dati["COGNOME"] = match.group(1).strip()
            # Pulizia extra: rimuovi numeri o simboli non alfabetici se compaiono per errore
            dati["COGNOME"] = re.sub(r'[^A-Z\s\'-]', '', dati["COGNOME"]).strip()
            if dati["COGNOME"]: break # Se trovato, esci

    # --- Estrazione del Nome (Campo 2) ---
    # Simile al cognome, cerca "2." o "NOME" o "FIRST NAME"
    pattern_nome = r"(?:^|\n)(?:2[\.\s]?)?\s*(?:NOME|FIRST NAME|NAME)?\s*([A-Z\s\'\-]+)"
    for i, r in enumerate(righe):
        match = re.search(pattern_nome, r)
        if match:
            dati["NOME"] = match.group(1).strip()
            dati["NOME"] = re.sub(r'[^A-Z\s\'-]', '', dati["NOME"]).strip()
            if dati["NOME"]: break

    # --- Estrazione Data e Luogo di Nascita (Campo 3) ---
    # Questo è più complesso. Cerca "3." o "DATA DI NASCITA" / "LUOGO DI NASCITA"
    # La data deve essere robusta a GG.MM.AAAA, GG/MM/AAAA, GG-MM-AAAA
    # Il luogo può contenere spazi e caratteri vari
    pattern_data_luogo = r"(?:^|\n)(?:3[\.\s]?)?\s*(?:DATA DI NASCITA|DATE OF BIRTH|BORN)?\s*(\d{2}[./-]\d{2}[./-]\d{2,4})\s*(\S.*)"
    for i, r in enumerate(righe):
        match = re.search(pattern_data_luogo, r)
        if match:
            # Data di nascita: uniforma il separatore a '.'
            data_nascita_raw = match.group(1)
            dati["DATA_NASCITA"] = re.sub(r'[/-]', '.', data_nascita_raw)
            
            # Luogo di nascita: ripulisci e assegna
            luogo_nascita_raw = match.group(2).strip()
            # Rimuovi numeri o pattern di date che Tesseract potrebbe aver confuso con il luogo
            luogo_nascita_raw = re.sub(r'\d{2}[./-]\d{2}[./-]\d{2,4}', '', luogo_nascita_raw).strip()
            # Rimuovi caratteri non desiderati
            dati["LUOGO_NASCITA"] = re.sub(r'[^\w\s\'-]', '', luogo_nascita_raw).strip() # Consente lettere, numeri, spazi, ', -
            if dati["DATA_NASCITA"] and dati["LUOGO_NASCITA"]: break

    # Tentativi aggiuntivi se i primi falliscono (cerca pattern di date senza etichetta "3.")
    # Questo è utile se l'OCR non riconosce bene il "3."
    if not dati["DATA_NASCITA"] and not dati["LUOGO_NASCITA"]:
        for r in righe:
            # Cerca solo una data e poi un testo che segue, assumendo che sia la data/luogo di nascita
            match = re.search(r"(\d{2}[./-]\d{2}[./-]\d{2,4})\s*(\S.+)", r)
            if match:
                # Controlla se la riga non sembra una data di emissione o scadenza
                # Puoi aggiungere qui delle heuristche, es. se la riga contiene "DATA DI RILASCIO" o "SCADENZA" la ignori.
                if not re.search(r'(DATA DI RILASCIO|SCADENZA|EMISSIONE|VALIDA)', r, re.IGNORECASE):
                    dati["DATA_NASCITA"] = re.sub(r'[/-]', '.', match.group(1))
                    luogo_nascita_raw = match.group(2).strip()
                    dati["LUOGO_NASCITA"] = re.sub(r'[^\w\s\'-]', '', luogo_nascita_raw).strip()
                    if dati["DATA_NASCITA"] and dati["LUOGO_NASCITA"]: break
    
    # Post-pulizia finale per i dati estratti: Assicurati che siano solo lettere, spazi, apostrofi, trattini
    for key in ["COGNOME", "NOME", "LUOGO_NASCITA"]:
        if dati[key]:
            dati[key] = re.sub(r'[^A-Z\s\'-]', '', dati[key]).strip()
            dati[key] = dati[key].replace('  ', ' ') # Rimuovi doppi spazi

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
        # Cerca l'intestazione DATA_ORA in modo case-insensitive e strip
        if "DATA_ORA" in [c.strip().upper() for c in row]:
            header_row_index = i
            break
    
    if header_row_index == -1:
        st.warning("Impossibile trovare le intestazioni nel foglio Google. Verificare il formato o il nome della colonna 'DATA_ORA'.")
        return pd.DataFrame(columns=COLUMNS)
    
    headers = [c.strip().upper() for c in data_raw[header_row_index]]
    data_rows = data_raw[header_row_index + 1:]
    
    # Filtra righe vuote
    data_rows = [r for r in data_rows if any(cell.strip() for cell in r)]

    # Crea DataFrame, gestendo il caso di colonne non corrispondenti se il DataFrame è vuoto
    if data_rows and len(headers) == len(data_rows[0]):
        df = pd.DataFrame(data_rows, columns=headers)
    else:
        st.warning("I dati recuperati non corrispondono alle intestazioni previste o sono vuoti.")
        df = pd.DataFrame(columns=headers if headers else COLUMNS) # Usa le intestazioni trovate o COLUMNS come fallback
        
    return df

# === DEFINIZIONE COLONNE DEL FOGLIO GOOGLE ===
COLUMNS = [
    "DATA_ORA", "COMUNE", "VEICOLO", "TARGA", "COGNOME", "NOME",
    "LUOGO_NASCITA", "DATA_NASCITA", "COMMERCIALE", "COPE", "RILIEVI", "CINOFILI"
]

# === INIZIALIZZAZIONE STATI DI SESSIONE ===
# Gli stati di sessione sono fondamentali per mantenere i dati tra i rerun di Streamlit
if "comune_corrente" not in st.session_state:
    st.session_state["comune_corrente"] = "NON DEFINITO"
if "inizio_turno" not in st.session_state:
    st.session_state["inizio_turno"] = ""
if "dati_precompilati" not in st.session_state:
    st.session_state["dati_precompilati"] = {k: "" for k in COLUMNS} # Inizializza con chiavi vuote
if "df_controlli" not in st.session_state: # Inizializza anche questo per le statistiche
    st.session_state["df_controlli"] = pd.DataFrame(columns=COLUMNS)
if "uploaded_file_data" not in st.session_state: # Per persistere il file caricato
    st.session_state["uploaded_file_data"] = None

# === ESECUZIONE BANNER ===
show_banner()

# === INTERFACCIA CON SCHEDE ===
tabs = st.tabs(["📍START SOFFERMO", "📥 DATI SOGGETTO", "🔁STOP SOFFERMO", "📋STATISTICHE"])

# === TAB 1: START SOFFERMO ===
with tabs[0]:
    st.header("📍 Inizia il Posto di Controllo")
    
    comuni_lista = [
        "ALBERA LIGURE", "ARQUATA SCRIVIA", "BASALUZZO", "BORGHETTO DI BORBERA", "BOSIO",
        "CABELLA LIGURE", "CANTALUPO LIGURE", "CAPRIATA D'ORBA", "CARREGA LIGURE", "CARROSIO",
        "CASALEGGIO BOIRO", "CASTELLETTO D'ORBA", "FRACONALTO", "FRANCAVILLA BISIO", "GAVI",
        "GRONDONA", "LERMA", "MONGIARDINO LIGURE", "MONTALDEO", "MORNESE", "NOVI LIGURE",
        "PARODI LIGURE", "PASTURANA", "POZZOLO FORMIGARO", "ROCCAFORTE LIGURE", "ROCCHETTA LIGURE",
        "SAN CRISTOFORO", "SERRAVALLE SCRIVIA", "SILVANO D'ORBA", "STAZZANO", "TASSAROLO",
        "VOLTAGGIO", "VIGNOLE BORBERA"
    ]

    # Trova l'indice del comune corrente per pre-selezionare la selectbox
    current_comune_index = 0
    if st.session_state.get("comune_corrente") and st.session_state["comune_corrente"] in comuni_lista:
        try:
            current_comune_index = comuni_lista.index(st.session_state["comune_corrente"])
        except ValueError:
            current_comune_index = 0 # Se il comune non è nella lista, resetta a 0

    comune_selezionato = st.selectbox(
        "Seleziona Comune del controllo",
        options=comuni_lista,
        index=current_comune_index,
        key="select_comune_start"
    )

    success_message_placeholder = st.empty() # Placeholder per messaggi di successo

    if st.button("▶️ INIZIA SOFFERMO", key="start_soffermo_button", use_container_width=True):
        st.session_state["comune_corrente"] = comune_selezionato
        st.session_state["inizio_turno"] = now_rome.strftime("%d/%m/%Y %H:%M")
        success_message_placeholder.success(f"Inizio soffermo nel comune di **{st.session_state['comune_corrente']}** alle **{st.session_state['inizio_turno']}**")
        st.rerun() # Forza un re-run per aggiornare lo stato dell'app

    # Mostra lo stato corrente del soffermo
    if st.session_state.get("comune_corrente") and st.session_state["comune_corrente"] != "NON DEFINITO":
        st.info(f"Soffermo attualmente in corso a **{st.session_state['comune_corrente']}** (Iniziato alle {st.session_state['inizio_turno']})")
    else:
        st.info("Nessun soffermo attivo. Seleziona un comune e clicca 'INIZIA SOFFERMO'.")

# === TAB 2: DATI SOGGETTO ===
with tabs[1]:
    st.header("📥 Inserimento Dati Controllo")

    if st.session_state["comune_corrente"] == "NON DEFINITO":
        st.warning("⚠️ Per favore, inizia un nuovo posto di controllo nella tab '📍START SOFFERMO' prima di inserire i dati.")
    else:
        st.info(f"Stai registrando un controllo a **{st.session_state['comune_corrente']}**")

        # Campi input VEICOLO e TARGA
        col_input_veicolo, col_input_targa = st.columns(2)
        with col_input_veicolo:
            veicolo = st.text_input("Marca e Modello del veicolo", value=st.session_state.get('dati_precompilati', {}).get('VEICOLO', ''), key="veicolo_input")
        with col_input_targa:
            targa = st.text_input("Targa del veicolo", value=st.session_state.get('dati_precompilati', {}).get('TARGA', ''), key="targa_input")
        
        # Campi radio (Commerciale, COPE, Cinofili, Rilievi)
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
        st.subheader("Documento e Dati Anagrafici")
        
        # Caricamento immagine documento
        uploaded_file = st.file_uploader(
            "📸 Carica foto del documento", 
            type=["jpg", "jpeg", "png", "heic", "heif"], # AGGIUNTO HEIC/HEIF
            key="upload_document_file"
        )
        
        # Gestione del file caricato e OCR
        image = None # Inizializza image a None

        if uploaded_file is not None:
            st.session_state["uploaded_file_data"] = uploaded_file.getvalue() # Salva il contenuto per persistenza
            st.image(uploaded_file, caption="Documento caricato", use_container_width=True)

            # --- GESTIONE HEIC / CONVERSIONE IMMAGINE ---
            file_extension = uploaded_file.name.split('.')[-1].lower()

            if file_extension == 'heic' or file_extension == 'heif':
                try:
                    heif_file = pillow_heif.read_heif(io.BytesIO(st.session_state["uploaded_file_data"]))
                    image = Image.frombytes(
                        heif_file.mode, heif_file.size, heif_file.data, "raw", heif_file.mode, heif_file.stride
                    )
                    if image.mode == 'RGBA':
                        image = image.convert('RGB')
                except Exception as e:
                    st.error(f"Errore nella conversione dell'immagine HEIC: {e}. Assicurati che l'immagine sia valida.")
                    st.stop()
            else:
                try:
                    image = Image.open(io.BytesIO(st.session_state["uploaded_file_data"]))
                    if image.mode == 'RGBA':
                        image = image.convert('RGB')
                except Exception as e:
                    st.error(f"Errore nell'apertura dell'immagine: {e}. Assicurati che il file sia un'immagine valida.")
                    st.stop()
            # --- FINE GESTIONE HEIC / CONVERSIONE IMMAGINE ---
            
            # --- Sezione OCR e Form per la correzione (dentro un expander) ---
            if image is not None:
                with st.expander("📝 Rivedi e Correggi Dati Estratti", expanded=True):
                    with st.spinner("Estrazione dati in corso..."):
                        try:
                            testo_estratto = pytesseract.image_to_string(image, lang="ita")
                            # Testo estratto visibile per controllo avanzato
                            st.text_area("🔍 Testo estratto (OCR)", value=testo_estratto, height=150, key="ocr_text_area") # Altezza ridotta
                            dati_patente_ocr = estrai_dati_patente(testo_estratto)
                            st.session_state["dati_precompilati"] = dati_patente_ocr # Salva per precompilazione

                        except Exception as e:
                            st.error(f"Errore durante l'OCR: {e}. Controlla i log per maggiori dettagli.")
                            testo_estratto = ""
                            st.session_state["dati_precompilati"] = {k: "" for k in COLUMNS} # Reset in caso di errore
                    
                    st.markdown("### Dati Anagrafici (Modificabili)")
                    # Campi di input precompilati con i dati OCR
                    col_cognome, col_nome = st.columns(2)
                    with col_cognome:
                        st.session_state["dati_precompilati"]["COGNOME"] = st.text_input(
                            "Cognome", 
                            value=st.session_state.get('dati_precompilati', {}).get('COGNOME', '')
                        ).upper()
                    with col_nome:
                        st.session_state["dati_precompilati"]["NOME"] = st.text_input(
                            "Nome", 
                            value=st.session_state.get('dati_precompilati', {}).get('NOME', '')
                        ).upper()

                    col_luogo_nascita, col_data_nascita = st.columns(2)
                    with col_luogo_nascita:
                        st.session_state["dati_precompilati"]["LUOGO_NASCITA"] = st.text_input(
                            "Luogo di Nascita", 
                            value=st.session_state.get('dati_precompilati', {}).get('LUOGO_NASCITA', '')
                        ).upper()
                    with col_data_nascita:
                        st.session_state["dati_precompilati"]["DATA_NASCITA"] = st.text_input(
                            "Data di Nascita (GG.MM.AAAA)", 
                            value=st.session_state.get('dati_precompilati', {}).get('DATA_NASCITA', ''), 
                            key="data_nascita_input"
                        )
            
            # --- Bottone per Salvare i dati ---
            if st.button("✅ Salva Controllo", key="salva_controllo_button", use_container_width=True):
                if not st.session_state["comune_corrente"] or st.session_state["comune_corrente"] == "NON DEFINITO":
                    st.error("Per favore, inizia un nuovo posto di controllo nella tab '📍START SOFFERMO' prima di salvare.")
                else:
                    dati_finali = {
                        "DATA_ORA": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "COMUNE": st.session_state["comune_corrente"],
                        "VEICOLO": veicolo.upper(),
                        "TARGA": targa.upper(),
                        "COGNOME": st.session_state["dati_precompilati"]["COGNOME"], # Usa i valori da session_state
                        "NOME": st.session_state["dati_precompilati"]["NOME"],
                        "LUOGO_NASCITA": st.session_state["dati_precompilati"]["LUOGO_NASCITA"],
                        "DATA_NASCITA": st.session_state["dati_precompilati"]["DATA_NASCITA"],
                        "COMMERCIALE": commerciale,
                        "COPE": cope,
                        "RILIEVI": rilievi.upper() if rilievi_si == "SI" else "",
                        "CINOFILI": cinofili
                    }

                    try:
                        aggiorna_su_google_sheets(dati_finali)
                        st.success("Controllo salvato correttamente!")
                        # Resetta i campi per il prossimo inserimento
                        st.session_state["dati_precompilati"] = {k: "" for k in COLUMNS}
                        st.session_state["uploaded_file_data"] = None # Rimuovi il file caricato
                        st.rerun() # Forza un re-run per pulire l'interfaccia
                    except Exception as e:
                        st.error(f"Errore durante il salvataggio su Google Sheets: {e}")

# === TAB 3: STOP SOFFERMO ===
with tabs[2]:
    st.header("🔁 Ferma il Posto di Controllo")
    if st.session_state.get("comune_corrente", "NON DEFINITO") != "NON DEFINITO":
        st.info(f"Il controllo è attualmente in corso nel comune di **{st.session_state['comune_corrente']}** (Iniziato alle {st.session_state['inizio_turno']})")
        if st.button("🛑 CONFERMA FINE SOFFERMO", key="stop_soffermo_button", use_container_width=True):
            ora_fine = now_rome.strftime("%d/%m/%Y %H:%M")
            st.success(f"✅ Il controllo nel comune di **{st.session_state['comune_corrente']}** è terminato il **{ora_fine}**")
            st.info(f"⏱️ Durata del controllo: dalle **{st.session_state['inizio_turno']}** alle **{ora_fine}**")
            st.session_state["comune_corrente"] = "NON DEFINITO"
            st.session_state["inizio_turno"] = ""
            st.success("Sessione di controllo TERMINATA. Puoi iniziare una nuova.")
            st.rerun()
    else:
        st.info("Nessun posto di controllo attivo al momento.")

# === TAB 4: STATISTICHE ===
with tabs[3]:
    st.header("📊 Statistiche Giornaliere e Totali")
    
    # Pulsante per aggiornare/caricare i dati
    if st.button("🔄 Carica/Aggiorna Dati Statistiche", key="update_stats_button", use_container_width=True):
        st.session_state["df_controlli"] = get_current_data_from_sheet()
        st.success("Dati statistiche aggiornati!")

    df = st.session_state["df_controlli"]
    
    if not df.empty:
        st.subheader("📋 Report Controlli Completo")
        st.dataframe(df, use_container_width=True) # Dataframe a tutta larghezza

        oggi = datetime.now().strftime("%d/%m/%Y")
        # Filtra per data e assicurati che la colonna DATA_ORA sia stringa per startswith
        df_oggi = df[df["DATA_ORA"].astype(str).str.startswith(oggi, na=False)].copy()

        if not df_oggi.empty and "COMUNE" in df_oggi.columns:
            st.markdown(f"### 📈 Statistiche Controlli del {oggi}")
            
            tot_soggetti_oggi = len(df_oggi)
            commerciali_oggi = df_oggi["COMMERCIALE"].astype(str).str.upper().eq("SI").sum()
            privati_oggi = tot_soggetti_oggi - commerciali_oggi
            cope_oggi = df_oggi["COPE"].astype(str).str.upper().eq("SI").sum()
            cinofili_oggi = df_oggi["CINOFILI"].astype(str).str.upper().eq("SI").sum()
            rilievi_oggi = df_oggi[df_oggi["RILIEVI"].astype(str).str.strip() != ""].shape[0]

            # Uso di metriche per un layout più compatto
            st.markdown("#### Riepilogo della giornata:")
            col_tot, col_comm, col_priv = st.columns(3)
            col_tot.metric("Totale Controlli", tot_soggetti_oggi)
            col_comm.metric("Mezzi Commerciali", commerciali_oggi)
            col_priv.metric("Mezzi Privati", privati_oggi)
            
            col_cope, col_cinofili, col_rilievi = st.columns(3)
            col_cope.metric("Interventi COPE", cope_oggi)
            col_cinofili.metric("Interventi Cinofili", cinofili_oggi)
            col_rilievi.metric("Rilievi Contestati", rilievi_oggi)

            st.markdown("### 🗂️ Rendicontazione attività per ciascun Comune (Oggi)")
            
            # Assicurati che 'COMUNE' sia una stringa per le operazioni successive
            df_oggi['COMUNE'] = df_oggi['COMUNE'].astype(str)
            comuni_oggi = df_oggi["COMUNE"].unique()

            for comune in comuni_oggi:
                df_comune_oggi = df_oggi[df_oggi["COMUNE"] == comune]
                
                ora_inizio_comune = df_comune_oggi["DATA_ORA"].min()
                ora_fine_comune = df_comune_oggi["DATA_ORA"].max()
                tot_soggetti_comune = len(df_comune_oggi)
                
                commerciali_comune = df_comune_oggi["COMMERCIALE"].astype(str).str.upper().eq("SI").sum()
                privati_comune = tot_soggetti_comune - commerciali_comune
                
                st.markdown(f"""
                ---
                **📍 Comune:** **`{comune}`** ⏱️ **Primo controllo:** `{ora_inizio_comune}` — **Ultimo controllo:** `{ora_fine_comune}`  
                🚗 **Totale mezzi controllati:** `{tot_soggetti_comune}`  
                🔧 **Mezzi commerciali:** `{commerciali_comune}` — **Privati:** `{privati_comune}`  
                """)
        else:
            st.info(f"Nessun dato di controllo disponibile per la giornata di oggi ({oggi}).")
    else:
        st.info("Nessun dato disponibile nel report generale. Clicca 'Carica/Aggiorna Dati Statistiche' o effettua i controlli.")
