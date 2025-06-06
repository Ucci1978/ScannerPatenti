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

# === CONFIGURAZIONE PAGINA STREAMLIT ===
st.set_page_config(
    page_title="Scanner Patenti - GdF",
    page_icon="👮‍♂️", # Icona che appare nella tab del browser
    layout="centered", # 'centered' è solitamente migliore per mobile, 'wide' per desktop
    initial_sidebar_state="collapsed" # Per mantenere la sidebar nascosta all'inizio
)

import pytz
rome_tz = pytz.timezone('Europe/Rome')
now_rome = datetime.now(pytz.utc).astimezone(rome_tz)
#current_datetime_str = now_rome.strftime("%Y-%m-%d %H:%M:%S")
# Percorso locale a Tesseract (LASCIAMO COMMENTATO PER IL DEPLOYMENT SU STREAMLIT CLOUD)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
logo_path = "Logo1.png" # <--- RICONTROLLA BENE MAIUSCOLE/MINUSCOLE QUI
try:
    st.sidebar.image(logo_path, use_column_width=True)
    st.sidebar.success(f"Logo '{logo_path}' caricato correttamente nella sidebar!") # Messaggio di successo!
except Exception as e:
    st.sidebar.error(f"Errore nel caricamento del logo '{logo_path}': {e}. Assicurati che il file esista e sia leggibile.")

st.sidebar.markdown("---")
st.sidebar.write("La mia App Patenti")# Puoi anche aggiungere del testo sotto il logo nella sidebar se vuoi

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
def estrai_dati_patente(image_path_or_object):
    # ... (Il resto del codice della tua funzione, con i print DEBUG, va qui) ...

    # Assicurati che l'immagine sia in formato Pillow
    if isinstance(image_path_or_object, str):
        image = Image.open(image_path_or_object)
    else:
        image = image_path_or_object

    # Esegui l'OCR sull'intera immagine con lingua italiana
    full_text = pytesseract.image_to_string(image, lang='ita')
    print(f"DEBUG: Testo OCR completo estratto:\n{full_text}")

    # Pulizia del testo per facilitare la ricerca
    cleaned_text_block = full_text.upper().replace('\n', ' ')
    cleaned_text_block = re.sub(r'[^A-Z0-9\s\/\.:-]', '', cleaned_text_block) # Manteniamo numeri, /, :, . e -
    print(f"DEBUG: Testo OCR pulito per l'elaborazione:\n{cleaned_text_block}")

    # Dizionario per i dati estratti
    dati_patente = {
        'cognome': '',
        'nome': '',
        'data_nascita': '',
        'luogo_nascita': '',
        'data_rilascio': '',
        'data_scadenza': '',
        'numero_patente': ''
    }

    # Regex per il cognome (campo 1)
    cognome_match = re.search(r'1\s*([A-Z\s\'-]+)', cleaned_text_block)
    if cognome_match:
        extracted_value = cognome_match.group(1).strip()
        # Puliamo ulteriormente il cognome da caratteri non desiderati ma manteniamo - e '
        cleaned_value = re.sub(r'[^A-Z\s\'-]', '', extracted_value).strip()
        dati_patente['cognome'] = cleaned_value
        print(f"DEBUG: Cognome (Campo 1) - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
    else:
        print("DEBUG: Cognome (Campo 1) non trovato.")


    # Regex per il nome (campo 2)
    nome_match = re.search(r'2\s*([A-Z\s\'-]+)', cleaned_text_block)
    if nome_match:
        extracted_value = nome_match.group(1).strip()
        cleaned_value = re.sub(r'[^A-Z\s\'-]', '', extracted_value).strip()
        dati_patente['nome'] = cleaned_value
        print(f"DEBUG: Nome (Campo 2) - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
    else:
        print("DEBUG: Nome (Campo 2) non trovato.")


    # Regex per data e luogo di nascita (campo 3)
    data_luogo_nascita_match = re.search(r'3\s*(\d{2}\.\d{2}\.\d{4})\s*([A-Z\s\'-]+)', cleaned_text_block)
    if data_luogo_nascita_match:
        dati_patente['data_nascita'] = data_luogo_nascita_match.group(1).strip()
        extracted_value = data_luogo_nascita_match.group(2).strip()
        cleaned_value = re.sub(r'[^A-Z\s\'-]', '', extracted_value).strip()
        dati_patente['luogo_nascita'] = cleaned_value
        print(f"DEBUG: Data di Nascita (Campo 3) - Estratto: '{data_luogo_nascita_match.group(1).strip()}'")
        print(f"DEBUG: Luogo di Nascita (Campo 3) - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
    else:
        print("DEBUG: Data e Luogo di Nascita (Campo 3) non trovati.")


    # Regex per data di rilascio (campo 4a)
    data_rilascio_match = re.search(r'4A\s*(\d{2}\.\d{2}\.\d{4})', cleaned_text_block)
    if data_rilascio_match:
        dati_patente['data_rilascio'] = data_rilascio_match.group(1).strip()
        print(f"DEBUG: Data di Rilascio (Campo 4A) - Estratto: '{data_rilascio_match.group(1).strip()}'")
    else:
        print("DEBUG: Data di Rilascio (Campo 4A) non trovata.")


    # Regex per data di scadenza (campo 4b)
    data_scadenza_match = re.search(r'4B\s*(\d{2}\.\d{2}\.\d{4})', cleaned_text_block)
    if data_scadenza_match:
        dati_patente['data_scadenza'] = data_scadenza_match.group(1).strip()
        print(f"DEBUG: Data di Scadenza (Campo 4B) - Estratto: '{data_scadenza_match.group(1).strip()}'")
    else:
        print("DEBUG: Data di Scadenza (Campo 4B) non trovata.")


    # Regex per il numero della patente (campo 5)
    # Questa regex cerca "5" seguito da spazio, poi una sequenza di numeri/lettere/slash/trattini.
    # Assumiamo che il numero di patente sia alfanumerico e possa contenere '/' o '-'.
    numero_patente_match = re.search(r'5\s*([A-Z0-9\/\-]+)', cleaned_text_block)
    if numero_patente_match:
        extracted_value = numero_patente_match.group(1).strip()
        # Pulisci ulteriormente per rimuovere spazi extra all'interno
        cleaned_value = re.sub(r'\s+', '', extracted_value)
        dati_patente['numero_patente'] = cleaned_value
        print(f"DEBUG: Numero Patente (Campo 5) - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
    else:
        print("DEBUG: Numero Patente (Campo 5) non trovato.")


    return dati_patente

# --- AGGIUNGI QUESTO CODICE NEL TUO SCRIPT PRINCIPALE Streamlit DOVE CARICHI E PROCESSI L'IMMAGINE ---

st.title("Scanner Patente")

uploaded_file = st.file_uploader("Carica un'immagine della patente", type=["png", "jpg", "jpeg", "heic"])

if uploaded_file is not None:
    try:
        # Per visualizzare l'immagine caricata
        st.image(uploaded_file, caption='Immagine Caricata.', use_column_width=True)
        st.write("Elaborazione in corso...")

        # Chiamata alla funzione di estrazione dati
        # Passiamo direttamente l'oggetto uploaded_file alla funzione
        dati_patente = estrai_dati_patente(uploaded_file)

        st.subheader("Dati Estratti:")
        st.write(f"**Cognome:** {dati_patente['cognome']}")
        st.write(f"**Nome:** {dati_patente['nome']}")
        st.write(f"**Data di Nascita:** {dati_patente['data_nascita']}")
        st.write(f"**Luogo di Nascita:** {dati_patente['luogo_nascita']}")
        st.write(f"**Data di Rilascio:** {dati_patente['data_rilascio']}")
        st.write(f"**Data di Scadenza:** {dati_patente['data_scadenza']}")
        st.write(f"**Numero Patente:** {dati_patente['numero_patente']}")

        # --- INIZIO: NUOVO CODICE PER MOSTRARE I DEBUG NELL'APP ---
        st.subheader("Informazioni di Debug (per l'assistenza):")
        # Mostra il testo OCR completo
        st.text_area("Testo OCR completo estratto:", value=full_text, height=200) # full_text deve essere accessibile qui

        # Mostra il testo pulito per l'elaborazione
        st.text_area("Testo OCR pulito per l'elaborazione:", value=cleaned_text_block, height=200) # cleaned_text_block deve essere accessibile qui

        # Per mostrare i valori puliti e estratti, puoi usare st.write o st.json per il dizionario dati_patente
        st.json(dati_patente)

        # --- FINE: NUOVO CODICE PER MOSTRARE I DEBUG NELL'APP ---

    except Exception as e:
        st.error(f"Si è verificato un errore durante l'elaborazione: {e}")
        st.error("Assicurati che l'immagine sia chiara e leggibile e che le dipendenze siano installate correttamente.")
    
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
