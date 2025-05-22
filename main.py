import streamlit as st
from PIL import Image
import easyocr
import numpy as np
import pandas as pd
import datetime
from pytz import timezone
from streamlit_cropper import st_cropper
import io
import base64

# === CONFIGURAZIONE STREAMLIT ===
st.set_page_config(page_title="Scanner Patente", layout="centered")
italy = timezone("Europe/Rome")

# === CACHING OCR ===
@st.cache_resource
def load_reader():
    return easyocr.Reader(['it'], gpu=False)

reader = load_reader()

# === FUNZIONE OCR + PARSING ===
def estrai_dati(testo):
    righe = [r.strip() for r in testo.split('\n') if r.strip()]
    dati = {"COGNOME": "", "NOME": "", "DATA DI NASCITA": "", "LUOGO DI NASCITA": ""}
    blocchi = {}
    blocco_attivo = None
    for riga in righe:
        if riga.startswith("1."):
            blocco_attivo = "1"
            blocchi[blocco_attivo] = []
        elif riga.startswith("2."):
            blocco_attivo = "2"
            blocchi[blocco_attivo] = []
        elif riga.startswith("3."):
            blocco_attivo = "3"
            blocchi[blocco_attivo] = []
        elif blocco_attivo:
            blocchi[blocco_attivo].append(riga)

    if "1" in blocchi:
        dati["COGNOME"] = " ".join(blocchi["1"]).upper()
    if "2" in blocchi:
        dati["NOME"] = " ".join(blocchi["2"]).upper()
    if "3" in blocchi:
        riga3 = " ".join(blocchi["3"])
        import re
        match = re.search(r"(\d{2}/\d{2}/\d{2,4})", riga3)
        if match:
            data = match.group(1)
            giorno, mese, anno = data.split("/")
            if len(anno) == 2:
                anno = "19" + anno if int(anno) > 25 else "20" + anno
            dati["DATA DI NASCITA"] = f"{giorno}/{mese}/{anno}"
            luogo = riga3.replace(match.group(1), "").strip(" ,.-")
            dati["LUOGO DI NASCITA"] = luogo.upper()
    return dati

# === SESSIONE ===
if "registro" not in st.session_state:
    st.session_state.registro = []

# === INTERFACCIA ===
st.title("📄 Scanner Patente Italiana - Online")

uploaded_file = st.file_uploader("📤 Carica o scatta una foto della patente", type=["jpg", "jpeg", "png"])

if uploaded_file:
    image = Image.open(uploaded_file).convert("RGB")

    st.subheader("✂️ Ritaglia l'immagine (solo parte della patente)")
    cropped_img = st_cropper(image, realtime_update=False, box_color="#00FF00", aspect_ratio=None)

    if cropped_img:
        resized = cropped_img.resize((min(cropped_img.size[0], 700), int(cropped_img.size[1]*700/cropped_img.size[0])))
        np_image = np.array(resized)

        with st.spinner("🧠 Analisi in corso..."):
            result = reader.readtext(np_image)
            testo_ocr = "\n".join([r[1] for r in result])

        st.text_area("📋 Testo OCR rilevato", testo_ocr, height=200)

        dati = estrai_dati(testo_ocr)

        st.subheader("📌 Dati Estratti")
        cognome = st.text_input("Cognome", value=dati["COGNOME"])
        nome = st.text_input("Nome", value=dati["NOME"])
        data_nascita = st.text_input("Data di nascita", value=dati["DATA DI NASCITA"])
        luogo_nascita = st.text_input("Luogo di nascita", value=dati["LUOGO DI NASCITA"])
        marca = st.text_input("Marca e modello veicolo")
        targa = st.text_input("Targa")
        comune = st.text_input("Comune del controllo")
        commerciale = st.checkbox("Veicolo commerciale?")
        cope = st.checkbox("COPE")
        cinofili = st.checkbox("Intervento cinofili")
        rilievi = st.checkbox("Rilievi contestati")
        rilievo_descr = st.text_input("Estremi del rilievo") if rilievi else "NO"

        if st.button("💾 Salva Dati"):
            orario = datetime.datetime.now(italy)
            st.session_state.registro.append({
                "DATA ORA": orario.strftime("%d/%m/%Y %H:%M:%S"),
                "COMUNE": comune.upper(),
                "COGNOME": cognome.upper(),
                "NOME": nome.upper(),
                "DATA NASCITA": data_nascita,
                "LUOGO NASCITA": luogo_nascita.upper(),
                "VEICOLO": marca.upper(),
                "TARGA": targa.upper(),
                "COMMERCIALE": "SÌ" if commerciale else "NO",
                "COPE": "SÌ" if cope else "NO",
                "CINOFILI": "SÌ" if cinofili else "NO",
                "RILIEVI": rilievo_descr.upper() if rilievo_descr != "NO" else "NO"
            })
            st.success("✅ Dati salvati")

st.divider()

st.subheader("📊 Report di fine turno")
if st.session_state.registro:
    df = pd.DataFrame(st.session_state.registro)
    st.dataframe(df)
    file_xlsx = io.BytesIO()
    df.to_excel(file_xlsx, index=False)
    st.download_button("⬇️ Scarica report in Excel", data=file_xlsx.getvalue(), file_name="report_turno.xlsx")

    if st.button("🧹 Azzera dati turno"):
        st.session_state.registro = []
        st.success("Tutti i dati sono stati azzerati.")
else:
    st.info("Nessun dato salvato per questo turno.")
