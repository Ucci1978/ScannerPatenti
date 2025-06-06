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
import pytz

pillow_heif.register_heif_opener()

st.set_page_config(
    page_title="Scanner Patenti - GdF",
    page_icon="👮‍♂️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

rome_tz = pytz.timezone('Europe/Rome')
now_rome = datetime.now(pytz.utc).astimezone(rome_tz)

# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

logo_path = "Logo1.png"
try:
    st.sidebar.image(logo_path, use_container_width=True)
except Exception as e:
    st.sidebar.error(f"Errore nel caricamento del logo '{logo_path}': {e}. Assicurati che il file esista e sia leggibile.")

st.sidebar.markdown("---")
st.sidebar.write("La mia App Patenti")

scope = [
    "[https://spreadsheets.google.com/feeds](https://spreadsheets.google.com/feeds)",
    "[https://www.googleapis.com/auth/spreadsheets](https://www.googleapis.com/auth/spreadsheets)",
    "[https://www.googleapis.com/auth/drive.file](https://www.googleapis.com/auth/drive.file)",
    "[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)"
]

try:
    creds_json_string = st.secrets["google_service_account_json"]
    service_account_info = json.loads(creds_json_string)
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("Controlli_Pattuglia").sheet1
except KeyError:
    st.error("Errore: La secret 'google_service_account_json' non è configurata o ha un nome errato. Verifica le tue Streamlit secrets.")
except json.JSONDecodeError as e:
    st.error(f"Errore di decodifica JSON delle credenziali Google Sheets: {e}. Controlla la formattazione della secret.")
except Exception as e:
    st.error(f"Errore generico durante l'autorizzazione di Google Sheets: {e}. Controlla la connessione o i permessi.")

st.title("COMPAGNIA NOVI LIGURE")
def show_banner():
    try:
        st.image("sfondo.png", use_container_width=True)
    except FileNotFoundError:
        st.warning("File 'sfondo.png' non trovato. Assicurati che sia nel tuo repository.")

    st.markdown("""
    <style>
    .main {
        background-color: #1e1e1e;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

def estrai_dati_patente(image_input):
    """
    Estrae i dati da un'immagine della patente usando OCR.
    Accetta un percorso di file (stringa) o un oggetto immagine Pillow/Streamlit UploadedFile.
    """
    image = None
    if isinstance(image_input, str):
        # Se è un percorso, apri l'immagine
        image = Image.open(image_input)
    elif hasattr(image_input, 'getvalue'): # Se è un oggetto Streamlit UploadedFile
        image = Image.open(io.BytesIO(image_input.getvalue()))
    elif isinstance(image_input, Image.Image):
        # Se è già un oggetto Pillow Image, usalo direttamente
        image = image_input
    else:
        raise TypeError(f"Tipo di oggetto immagine non supportato: {type(image_input)}")

    # Assicurati che l'immagine sia in modalità RGB per Tesseract se necessario
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    elif image.mode == 'P': # Gestisci immagini con palette
        image = image.convert('RGB')

    # Esegui l'OCR sull'intera immagine con lingua italiana
    full_text = pytesseract.image_to_string(image, lang='ita')
    print(f"DEBUG: Testo OCR completo estratto:\n{full_text}")

    # Pulizia del testo: Rimuovi caratteri non alfanumerici, ma mantieni '/' '.' '-' '(' ')' ':'
    # E poi normalizza gli spazi e le parentesi per il luogo di nascita
    cleaned_text_block = full_text.upper()
    
    # Passaggio 1: Rimuovi caratteri indesiderati che non sono numeri, lettere, o i delimitatori / . - : ( )
    # Mantieni il punto, il trattino, lo slash, i due punti, le parentesi e gli spazi.
    # Ogni altro carattere viene rimosso.
    cleaned_text_block = re.sub(r'[^A-Z0-9\s\/\.:\-\(\)]', '', cleaned_text_block)
    
    # Passaggio 2: Rimuovi le parentesi intorno al luogo di nascita
    cleaned_text_block = re.sub(r'\(([A-Z\s]+)\)', r'\1', cleaned_text_block)
    
    # Passaggio 3: Normalizza gli spazi multipli in un singolo spazio
    cleaned_text_block = re.sub(r'\s+', ' ', cleaned_text_block).strip()
    
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

    # === REGEX MIGLIORATE E PIÙ SPECIFICHE PER I DELIMITATORI NUMERICI ===

    # Regex per il cognome (campo 1)
    # Cerchiamo "1." seguito da spazi, poi catturiamo il dato fino al prossimo numero di campo (2., 3., 4A., 4B., 4C., 5.)
    cognome_match = re.search(r'1\s*\.\s*(.+?)(?=\s*(?:2|3|4A|4B|4C|5)\s*\.|$)', cleaned_text_block)
    if cognome_match:
        extracted_value = cognome_match.group(1).strip()
        # Pulizia per rimuovere eventuali caratteri speciali indesiderati che Tesseract potrebbe aver aggiunto
        cleaned_value = re.sub(r'[^A-Z\s\'-]', '', extracted_value).strip()
        dati_patente['cognome'] = cleaned_value
        print(f"DEBUG: Cognome (Campo 1) - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
    else:
        print("DEBUG: Cognome (Campo 1) non trovato.")


    # Regex per il nome (campo 2)
    # Cerchiamo "2." seguito da spazi, poi catturiamo il dato fino al prossimo numero di campo (3., 4A., 4B., 4C., 5.)
    nome_match = re.search(r'2\s*\.\s*(.+?)(?=\s*(?:3|4A|4B|4C|5)\s*\.|$)', cleaned_text_block)
    if nome_match:
        extracted_value = nome_match.group(1).strip()
        cleaned_value = re.sub(r'[^A-Z\s\'-]', '', extracted_value).strip()
        dati_patente['nome'] = cleaned_value
        print(f"DEBUG: Nome (Campo 2) - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
    else:
        print("DEBUG: Nome (Campo 2) non trovato.")

    # Regex per data e luogo di nascita (campo 3)
    # Cattura da "3." data (GG/MM/AA o AAAA) e poi luogo, fino all'inizio del campo 4A o 4C o fine stringa
    data_luogo_nascita_match = re.search(
        r'3\s*\.\s*(\d{2}[./]\d{2}[./]\d{2}(?:\d{2})?)\s*([A-Z\s\'-]+?)(?=\s*(?:4A|4C|4B|5)\s*\.|$)',
        cleaned_text_block
    )
    if data_luogo_nascita_match:
        data_nascita_raw = data_luogo_nascita_match.group(1).strip()
        # Converte l'anno a 2 cifre in 4 cifre
        anno_raw = data_nascita_raw[-2:]
        if len(anno_raw) == 2:
            current_year_last_two_digits = datetime.now().year % 100
            # Aggiunta una tolleranza di 5 anni nel futuro per patenti molto recenti
            if int(anno_raw) <= current_year_last_two_digits + 5:
                anno_full = f"20{anno_raw}"
            else:
                anno_full = f"19{anno_raw}"
            dati_patente['data_nascita'] = data_nascita_raw[:-2] + anno_full
        else: # Se l'anno è già a 4 cifre
            dati_patente['data_nascita'] = data_nascita_raw

        extracted_luogo = data_luogo_nascita_match.group(2).strip() # Group 2 per il luogo
        cleaned_luogo = re.sub(r'[^A-Z\s\'-]', '', extracted_luogo).strip() # Pulizia ulteriore
        dati_patente['luogo_nascita'] = cleaned_luogo
        print(f"DEBUG: Data di Nascita (Campo 3) - Estratto: '{data_nascita_raw}', Pulito: '{dati_patente['data_nascita']}'")
        print(f"DEBUG: Luogo di Nascita (Campo 3) - Estratto: '{extracted_luogo}', Pulito: '{cleaned_luogo}'")
    else:
        print("DEBUG: Data e Luogo di Nascita (Campo 3) non trovati.")

    # Regex per data di rilascio (campo 4a)
    data_rilascio_match = re.search(r'4A\s*\.\s*(\d{2}[./]\d{2}[./]\d{4})(?=\s*(?:4C|4B|5)\s*\.|$)', cleaned_text_block)
    if data_rilascio_match:
        dati_patente['data_rilascio'] = data_rilascio_match.group(1).strip()
        print(f"DEBUG: Data di Rilascio (Campo 4A) - Estratto: '{dati_patente['data_rilascio']}'")
    else:
        print("DEBUG: Data di Rilascio (Campo 4A) non trovata.")

    # Regex per data di scadenza (campo 4b)
    data_scadenza_match = re.search(r'4B\s*\.\s*(\d{2}[./]\d{2}[./]\d{4})(?=\s*(?:4C|5)\s*\.|$)', cleaned_text_block)
    if data_scadenza_match:
        dati_patente['data_scadenza'] = data_scadenza_match.group(1).strip()
        print(f"DEBUG: Data di Scadenza (Campo 4B) - Estratto: '{dati_patente['data_scadenza']}'")
    else:
        print("DEBUG: Data di Scadenza (Campo 4B) non trovata.")

    # Regex per il numero della patente (campo 5)
    # Cerchiamo "5." seguito da spazi, poi una sequenza di alfanumerici, "/", o "-" di almeno 8 caratteri.
    numero_patente_match = re.search(r'5\s*\.\s*([A-Z0-9\/\-]{8,})', cleaned_text_block)
    if numero_patente_match:
        extracted_value = numero_patente_match.group(1).strip()
        cleaned_value = re.sub(r'\s+', '', extracted_value) # Rimuovi spazi extra interni
        dati_patente['numero_patente'] = cleaned_value
        print(f"DEBUG: Numero Patente (Campo 5) - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
    else:
        # Fallback più generico se la regex stretta fallisce.
        # Questo catturerà qualsiasi cosa dopo "5." ma potrebbe essere meno preciso.
        numero_patente_fallback_match = re.search(r'5\s*\.\s*(\S+)', cleaned_text_block)
        if numero_patente_fallback_match:
            extracted_value = numero_patente_fallback_match.group(1).strip()
            cleaned_value = re.sub(r'\s+', '', extracted_value)
            dati_patente['numero_patente'] = cleaned_value
            print(f"DEBUG: Numero Patente (Campo 5) - FALLBACK - Estratto: '{extracted_value}', Pulito: '{cleaned_value}'")
        else:
            print("DEBUG: Numero Patente (Campo 5) non trovato.")

    return dati_patente, full_text, cleaned_text_block

st.title("Scanner Patente")

uploaded_file = st.file_uploader("Carica un'immagine della patente", type=["png", "jpg", "jpeg", "heic"])

if uploaded_file is not None:
    try:
        st.image(uploaded_file, caption='Immagine Caricata.', use_column_width=True)
        st.write("Elaborazione in corso...")

        dati_patente, full_text_debug, cleaned_text_block_debug = estrai_dati_patente(uploaded_file)

        st.subheader("Dati Estratti:")
        st.write(f"**Cognome:** {dati_patente['cognome']}")
        st.write(f"**Nome:** {dati_patente['nome']}")
        st.write(f"**Data di Nascita:** {dati_patente['data_nascita']}")
        st.write(f"**Luogo di Nascita:** {dati_patente['luogo_nascita']}")
        st.write(f"**Data di Rilascio:** {dati_patente['data_rilascio']}")
        st.write(f"**Data di Scadenza:** {dati_patente['data_scadenza']}")
        st.write(f"**Numero Patente:** {dati_patente['numero_patente']}")

        st.subheader("Informazioni di Debug (per l'assistenza):")
        st.text_area("Testo OCR completo estratto:", value=full_text_debug, height=200)
        st.text_area("Testo OCR pulito per l'elaborazione:", value=cleaned_text_block_debug, height=200)
        st.json(dati_patente)

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
        if "DATA_ORA" in [c.strip().upper() for c in row]:
            header_row_index = i
            break

    if header_row_index == -1:
        st.warning("Impossibile trovare le intestazioni nel foglio Google. Verificare il formato o il nome della colonna 'DATA_ORA'.")
        return pd.DataFrame(columns=COLUMNS)

    headers = [c.strip().upper() for c in data_raw[header_row_index]]
    data_rows = data_raw[header_row_index + 1:]
    data_rows = [r for r in data_rows if any(cell.strip() for cell in r)]

    if data_rows and len(headers) == len(data_rows[0]):
        df = pd.DataFrame(data_rows, columns=headers)
    else:
        st.warning("I dati recuperati non corrispondono alle intestazioni previste o sono vuoti.")
        df = pd.DataFrame(columns=headers if headers else COLUMNS)

    return df

COLUMNS = [
    "DATA_ORA", "COMUNE", "VEICOLO", "TARGA", "COGNOME", "NOME",
    "LUOGO_NASCITA", "DATA_NASCITA", "COMMERCIALE", "COPE", "RILIEVI", "CINOFILI"
]

if "comune_corrente" not in st.session_state:
    st.session_state["comune_corrente"] = "NON DEFINITO"
if "inizio_turno" not in st.session_state:
    st.session_state["inizio_turno"] = ""
if "dati_precompilati" not in st.session_state:
    st.session_state["dati_precompilati"] = {k: "" for k in COLUMNS}
if "df_controlli" not in st.session_state:
    st.session_state["df_controlli"] = pd.DataFrame(columns=COLUMNS)
if "uploaded_file_data" not in st.session_state:
    st.session_state["uploaded_file_data"] = None

show_banner()

tabs = st.tabs(["📍START SOFFERMO", "📥 DATI SOGGETTO", "🔁STOP SOFFERMO", "📋STATISTICHE"])

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

    current_comune_index = 0
    if st.session_state.get("comune_corrente") and st.session_state["comune_corrente"] in comuni_lista:
        try:
            current_comune_index = comuni_lista.index(st.session_state["comune_corrente"])
        except ValueError:
            current_comune_index = 0

    comune_selezionato = st.selectbox(
        "Seleziona Comune del controllo",
        options=comuni_lista,
        index=current_comune_index,
        key="select_comune_start"
    )

    success_message_placeholder = st.empty()

    if st.button("▶️ INIZIA SOFFERMO", key="start_soffermo_button", use_container_width=True):
        st.session_state["comune_corrente"] = comune_selezionato
        st.session_state["inizio_turno"] = now_rome.strftime("%d/%m/%Y %H:%M")
        success_message_placeholder.success(f"Inizio soffermo nel comune di **{st.session_state['comune_corrente']}** alle **{st.session_state['inizio_turno']}**")
        st.rerun()

    if st.session_state.get("comune_corrente") and st.session_state["comune_corrente"] != "NON DEFINITO":
        st.info(f"Soffermo attualmente in corso a **{st.session_state['comune_corrente']}** (Iniziato alle {st.session_state['inizio_turno']})")
    else:
        st.info("Nessun soffermo attivo. Seleziona un comune e clicca 'INIZIA SOFFERMO'.")

with tabs[1]:
    st.header("📥 Inserimento Dati Controllo")

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
        st.subheader("Documento e Dati Anagrafici")

        uploaded_file = st.file_uploader(
            "📸 Carica foto del documento",
            type=["jpg", "jpeg", "png", "heic", "heif"],
            key="upload_document_file"
        )

        image = None

        if uploaded_file is not None:
            st.session_state["uploaded_file_data"] = uploaded_file.getvalue()
            st.image(uploaded_file, caption="Documento caricato", use_container_width=True)

            with st.expander("📝 Rivedi e Correggi Dati Estratti", expanded=True):
                with st.spinner("Estrazione dati in corso..."):
                    try:
                        dati_patente_ocr, full_text_ocr, cleaned_text_block_ocr = estrai_dati_patente(uploaded_file)
                        st.session_state["dati_precompilati"] = dati_patente_ocr

                        st.text_area("🔍 Testo estratto (OCR)", value=full_text_ocr, height=150, key="ocr_text_area")
                        st.text_area("Testo OCR pulito per l'elaborazione:", value=cleaned_text_block_ocr, height=150, key="cleaned_ocr_text_area")

                    except Exception as e:
                        st.error(f"Errore durante l'OCR: {e}. Controlla i log per maggiori dettagli.")
                        full_text_ocr = ""
                        cleaned_text_block_ocr = ""
                        st.session_state["dati_precompilati"] = {k: "" for k in COLUMNS}

                st.markdown("### Dati Anagrafici (Modificabili)")
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

            if st.button("✅ Salva Controllo", key="salva_controllo_button", use_container_width=True):
                if not st.session_state["comune_corrente"] or st.session_state["comune_corrente"] == "NON DEFINITO":
                    st.error("Per favor, inizia un nuovo posto di controllo nella tab '📍START SOFFERMO' prima di salvare.")
                else:
                    dati_finali = {
                        "DATA_ORA": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "COMUNE": st.session_state["comune_corrente"],
                        "VEICOLO": veicolo.upper(),
                        "TARGA": targa.upper(),
                        "COGNOME": st.session_state["dati_precompilati"]["COGNOME"],
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
                        st.session_state["dati_precompilati"] = {k: "" for k in COLUMNS}
                        st.session_state["uploaded_file_data"] = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore durante il salvataggio su Google Sheets: {e}")

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

with tabs[3]:
    st.header("📊 Statistiche Giornaliere e Totali")

    if st.button("🔄 Carica/Aggiorna Dati Statistiche", key="update_stats_button", use_container_width=True):
        st.session_state["df_controlli"] = get_current_data_from_sheet()
        st.success("Dati statistiche aggiornati!")

    df = st.session_state["df_controlli"]

    if not df.empty:
        st.subheader("📋 Report Controlli Completo")
        st.dataframe(df, use_container_width=True)

        oggi = datetime.now().strftime("%d/%m/%Y")
        df_oggi = df[df["DATA_ORA"].astype(str).str.startswith(oggi, na=False)].copy()

        if not df_oggi.empty and "COMUNE" in df_oggi.columns:
            st.markdown(f"### 📈 Statistiche Controlli del {oggi}")

            tot_soggetti_oggi = len(df_oggi)
            commerciali_oggi = df_oggi["COMMERCIALE"].astype(str).str.upper().eq("SI").sum()
            privati_oggi = tot_soggetti_oggi - commerciali_oggi
            cope_oggi = df_oggi["COPE"].astype(str).str.upper().eq("SI").sum()
            cinofili_oggi = df_oggi["CINOFILI"].astype(str).str.upper().eq("SI").sum()
            rilievi_oggi = df_oggi[df_oggi["RILIEVI"].astype(str).str.strip() != ""].shape[0]

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

            df_oggi['COMUNE'] = df_oggi['COMUNE'].astype(str)
            comuni_oggi = df_oggi["COMUNE"].unique()

            for comune in comuni_oggi:
                df_comune_oggi = df_oggi[df_oggi["COMUNE"] == comune]

                ora_inizio_comune = df_comune_oggi["DATA_ORA"].min()
                ora_fine_comune = df_comune_oggi["DATA_ORA"].max()
                tot_soggetti_comune = len(df_comune_oggi)

                commerciali_comune = df_comune_oggi["COMMERCIALE"].astype(str).str.upper().eq("SI").sum()
                privati_comune = tot_soggetti_comune - commercials_comune

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
