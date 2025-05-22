import streamlit as st
from PIL import Image
import easyocr
import pandas as pd
import re
import datetime
import os
import base64
import numpy as np
from pytz import timezone
from streamlit_cropper import st_cropper

italy = timezone("Europe/Rome")

st.set_page_config(page_title="Controllo Patenti - Guardia di Finanza", layout="centered")

# === SFONDO E INTESTAZIONE ===
def set_background(image_file):
    if os.path.exists(image_file):
        with open(image_file, "rb") as image:
            encoded = base64.b64encode(image.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{encoded}");
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

set_background("sfondo.png")

# LOGO E INTESTAZIONE CENTRATI
if os.path.exists("logo.png"):
    with open("logo.png", "rb") as file:
        logo_base64 = base64.b64encode(file.read()).decode()
    st.markdown(f"""
    <div style='text-align: center;'>
        <img src='data:image/png;base64,{logo_base64}' width='120'>
        <h1 style='color: darkgreen;'>GUARDIA DI FINANZA</h1>
        <h2>COMPAGNIA NOVI LIGURE</h2>
        <h3 style='color: gray;'>Nucleo Mobile</h3>
    </div>
    <hr>
    """, unsafe_allow_html=True)

# === SESSION STATE ===
if "comune" not in st.session_state:
    st.session_state.comune = ""
if "registro" not in st.session_state:
    st.session_state.registro = []
if "inizio_turno" not in st.session_state:
    st.session_state.inizio_turno = None
if "fine_turno" not in st.session_state:
    st.session_state.fine_turno = None
if "last_uploaded" not in st.session_state:
    st.session_state.last_uploaded = None
if "comune_attivo" not in st.session_state:
    st.session_state.comune_attivo = ""

# === COMUNI DISPONIBILI ===
COMUNI_CONTROLLABILI = [
    "ALBERA LIGURE", "ARQUATA SCRIVIA", "BASALUZZO", "BORGHETTO DI BORBERA", "BOSIO",
    "CABELLA LIGURE", "CANTALUPO LIGURE", "CAPRIATA D'ORBA", "CARREGA LIGURE", "CARROSIO",
    "CASALEGGIO BOIRO", "CASTELLETTO D'ORBA", "FRACONALTO", "FRANCAVILLA BISIO", "GAVI",
    "GRONDONA", "LERMA", "MONGIARDINO LIGURE", "MONTALDEO", "MORNESE", "NOVI LIGURE",
    "PARODI LIGURE", "PASTURANA", "POZZOLO FORMIGARO", "ROCCAFORTE LIGURE", "ROCCHETTA LIGURE",
    "SAN CRISTOFORO", "SERRAVALLE SCRIVIA", "SILVANO D'ORBA", "STAZZANO", "TASSAROLO",
    "VOLTAGGIO", "VIGNOLE BORBERA"
]

# === OCR CON CACHE ===
@st.cache_resource
def get_easyocr_reader():
    return easyocr.Reader(['it'], gpu=False)

def estrai_dati_patente_easyocr(image_np):
    reader = get_easyocr_reader()
    results = reader.readtext(image_np)
    testo = "\n".join([r[1] for r in results])
    st.text_area("📄 Testo OCR rilevato (debug)", testo, height=200)

    dati = {"COGNOME": "", "NOME": "", "DATA DI NASCITA": "", "LUOGO DI NASCITA": ""}
    righe = [r.strip() for r in testo.split("\n") if r.strip()]

    blocchi = {}
    blocco_attivo = None

    for riga in righe:
        if re.match(r"^\d\.", riga):
            blocco_attivo = riga[0]
            blocchi[blocco_attivo] = []
        elif blocco_attivo:
            blocchi[blocco_attivo].append(riga)

    if "1" in blocchi:
        dati["COGNOME"] = " ".join(blocchi["1"]).strip().upper()
    if "2" in blocchi:
        dati["NOME"] = " ".join(blocchi["2"]).strip().upper()
    if "3" in blocchi:
        blocco3 = " ".join(blocchi["3"])
        match_data = re.search(r"\d{2}/\d{2}/\d{2,4}", blocco3)
        if match_data:
            data_raw = match_data.group(0)
            giorno, mese, anno = data_raw.split("/")
            anno = "19" + anno if len(anno) == 2 and int(anno) > 25 else ("20" + anno if len(anno) == 2 else anno)
            dati["DATA DI NASCITA"] = f"{giorno}/{mese}/{anno}"
            luogo = blocco3.replace(match_data.group(), "").strip(" ,.-")
            dati["LUOGO DI NASCITA"] = luogo.upper()

    return dati

# === NAVIGAZIONE ===
tabs = st.tabs(["🏁 Inizio", "📝 Inserimento", "✅ Fine", "📊 Report"])

with tabs[0]:
    st.header("🏁 Inizio Posto di Controllo")
    comune = st.selectbox("Comune del controllo", COMUNI_CONTROLLABILI)
    if st.button("✅ Avvia controllo"):
        st.session_state.comune = comune
        st.session_state.inizio_turno = datetime.datetime.now(italy)
        st.session_state.last_uploaded = None
        st.session_state.comune_attivo = comune
        st.success(f"Controllo iniziato alle {st.session_state.inizio_turno.strftime('%H:%M:%S')} nel comune di {comune}")

with tabs[1]:
    st.header("📝 Inserimento Dati")
    uploaded_file = st.file_uploader("Carica immagine patente", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        st.session_state.last_uploaded = uploaded_file

    if st.session_state.last_uploaded:
        image = Image.open(st.session_state.last_uploaded).convert("RGB")
        st.subheader("✂️ Ritaglia l'immagine prima dell'elaborazione")
        cropped_img = st_cropper(image, realtime_update=True, box_color='#00FF00', aspect_ratio=None)
        if cropped_img:
            image_np = np.array(cropped_img)
            with st.spinner("🧠 Estrazione in corso..."):
                dati = estrai_dati_patente_easyocr(image_np)

            st.image(cropped_img, caption="Immagine ritagliata", use_container_width=True)

            cognome = st.text_input("COGNOME", value=dati["COGNOME"])
            nome = st.text_input("NOME", value=dati["NOME"])
            data_nascita = st.text_input("DATA DI NASCITA", value=dati["DATA DI NASCITA"])
            luogo_nascita = st.text_input("LUOGO DI NASCITA", value=dati["LUOGO DI NASCITA"])
            marca_modello = st.text_input("MARCA E MODELLO VEICOLO").upper()
            targa = st.text_input("TARGA").upper()
            commerciale = st.checkbox("Veicolo commerciale?")
            cope = st.checkbox("COPE?")
            cinofili = st.checkbox("Intervento cinofili?")
            rilievi = st.checkbox("Rilievi contestati?")
            rilievi_note = st.text_input("Estremi rilievo") if rilievi else "NO"

            if st.button("💾 Salva controllo"):
                orario = datetime.datetime.now(italy)
                st.session_state.registro.append({
                    "COMUNE": st.session_state.comune_attivo,
                    "ORA": orario,
                    "COGNOME": cognome,
                    "NOME": nome,
                    "DATA NASCITA": data_nascita,
                    "LUOGO NASCITA": luogo_nascita,
                    "MARCA MODELLO": marca_modello,
                    "TARGA": targa,
                    "COMMERCIALE": "SÌ" if commerciale else "NO",
                    "COPE": "SÌ" if cope else "NO",
                    "CINOFILI": "SÌ" if cinofili else "NO",
                    "RILIEVI": rilievi_note.upper() if rilievi_note != "NO" else "NO"
                })
                st.session_state.last_uploaded = None
                st.success("Dati salvati e immagine azzerata.")

with tabs[2]:
    st.header("✅ Fine Posto di Controllo")
    if st.button("🛑 Termina il controllo"):
        st.session_state.fine_turno = datetime.datetime.now(italy)
        st.session_state.last_uploaded = None
        st.success(f"Controllo terminato alle {st.session_state.fine_turno.strftime('%H:%M:%S')}")

with tabs[3]:
    st.header("📊 Report e Statistiche")
    if len(st.session_state.registro) == 0:
        st.warning("Nessun controllo registrato.")
    else:
        df = pd.DataFrame(st.session_state.registro)
        st.dataframe(df)

        st.subheader("🕒 Attività per Comune")
        for comune in df['COMUNE'].unique():
            sottodf = df[df['COMUNE'] == comune].sort_values('ORA')
            ora_inizio = sottodf['ORA'].iloc[0].strftime("%H:%M:%S")
            ora_fine = sottodf['ORA'].iloc[-1].strftime("%H:%M:%S")
            st.markdown(f"- **{comune}**: dalle **{ora_inizio}** alle **{ora_fine}**")

        st.subheader("📈 Statistiche di riepilogo")
        st.markdown(f"**Totale soggetti controllati:** {len(df)}")
        st.markdown(f"**Veicoli commerciali:** {sum(df['COMMERCIALE'] == 'SÌ')}")
        st.markdown(f"**COPE:** {sum(df['COPE'] == 'SÌ')}")
        st.markdown(f"**Rilievi contestati:** {sum(df['RILIEVI'] != 'NO')}")

        df['ORA'] = df['ORA'].astype(str)
        file_path = "report_turno.xlsx"
        df.to_excel(file_path, index=False)
        with open(file_path, "rb") as f:
            st.download_button("📥 Scarica Excel", f.read(), file_name=file_path)

        if st.button("🧹 Azzera turno"):
            st.session_state.registro = []
            st.session_state.inizio_turno = None
            st.session_state.fine_turno = None
            st.session_state.last_uploaded = None
            st.session_state.comune_attivo = ""
            st.success("Sessione azzerata con successo.")
