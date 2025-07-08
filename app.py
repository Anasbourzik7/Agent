import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
from bs4 import BeautifulSoup

# === Config de la page (DOIT être appelée en premier)
st.set_page_config(page_title="Détection des perfs", layout="wide")

# === Logo en haut, titre juste en dessous (centré sur la ligne suivante)
st.markdown("""
    <div style="text-align: center;">
        <a href="#" onclick="window.location.reload();">
            <img src="logo.png" width="120" style="cursor: pointer;" />
        </a>
    </div>
""", unsafe_allow_html=True)

# Titre sur la ligne suivante, en noir
st.markdown("<h2 style='color:#000000;'>🧠 Détection des performances </h2>", unsafe_allow_html=True)


# === Styles personnalisés (facultatif)
st.markdown("""
    <style>
        .stApp {
            background-color: #F5F5F5;
        }
        h1, h2, h3, h4 {
            color: #000000;
        }
        .stButton > button {
            background-color: #FFA500;
            color: white;
             img {
            border-radius: 0% !important;
        }
        }
    </style>
""", unsafe_allow_html=True)

# === Charger le modèle
model_path = "2-Models/XGext.pkl"
model = joblib.load(model_path)

# === Fonction d'extraction des données AWR avec query_text
def extract_data_from_awr(html_content, filename="uploaded_file"):
    soup = BeautifulSoup(html_content, 'lxml')
    all_data = []
    sql_texts = {}

    # Extraire les SQL Texts depuis une section spécifique (Complete List of SQL Text)
    for section in soup.find_all("h3", class_="awr"):
        if "Complete List of SQL Text" in section.text:
            table = section.find_next("table")
            if table:
                for row in table.find_all('tr')[1:]:
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        sql_id = cols[0].text.strip()
                        query_text = cols[1].text.strip()
                        sql_texts[sql_id] = query_text

    # Extraire les métriques des tables de classe 'tdiff'
    for table in soup.find_all('table', class_='tdiff'):
        headers = [th.text.strip() for th in table.find_all('th')]

        required_headers = ['Executions', 'Rows Processed', 'Elapsed  Time (s)', 'SQL Id']
        if all(header in headers for header in required_headers):
            header_map = {header: idx for idx, header in enumerate(headers)}

            executions_idx = header_map['Executions']
            rows_proc_idx = header_map['Rows Processed']
            elapsed_time_idx = header_map['Elapsed  Time (s)']
            sql_id_idx = header_map['SQL Id']

            cpu_idx = None
            for i, h in enumerate(headers):
                if '%' in h and 'CPU' in h.upper():
                    cpu_idx = i
                    break

            rows = table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= len(header_map):
                    try:
                        executions = int(cells[executions_idx].text.strip().replace(',', ''))
                        rows_processed = int(cells[rows_proc_idx].text.strip().replace(',', ''))
                        elapsed_time = float(cells[elapsed_time_idx].text.strip().replace(',', ''))
                        sql_id = cells[sql_id_idx].text.strip()

                        cpu_percent = 0.0
                        if cpu_idx is not None:
                            cpu_text = cells[cpu_idx].text.strip().replace('%', '').replace(',', '.')
                            cpu_percent = float(cpu_text) if cpu_text else 0.0

                        data = {
                            'query_id': sql_id,
                            'awr_file': filename,
                            'elapsed_time': elapsed_time,
                            'rows_processed': rows_processed,
                            'cpu_percent': cpu_percent,
                            'query_text': sql_texts.get(sql_id, "")
                        }
                        all_data.append(data)
                    except Exception as e:
                        st.warning(f"⚠️ Erreur ligne : {e}")

    return pd.DataFrame(all_data)

# === Fonctions d’analyse de performance
def get_regression_threshold_rows(rows_processed):
    return (2.78e-04 * rows_processed + 106.40) * 1.5

def get_regression_threshold_cpu(cpu_percent):
    return (-3.06 * cpu_percent + 250.51) * 1.5

def identifier_cause_ai(row):
    if row['incident'] != 1:
        return "Aucun"
    causes = []
    if row['elapsed_time'] > get_regression_threshold_rows(row['rows_processed']):
        causes.append("Lignes traitées élevées")
    if row['elapsed_time'] > get_regression_threshold_cpu(row['cpu_percent']):
        causes.append("Surcharge CPU")
    return ", ".join(causes) if causes else "Incident probable"

st.markdown("<h6 style='color:#000000;'>📤 Upload un fichier AWR (.html)</h6>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type="html")  # label vide


if uploaded_file is not None:
    try:
        html_string = uploaded_file.read().decode("utf-8", errors='ignore')
        df = extract_data_from_awr(html_string, filename=uploaded_file.name)

        if df.empty:
            st.error("❌ Aucune donnée extraite.")
        else:
            st.markdown(f"<p style='color:black; font-size:18px;'>✅ {len(df)} requêtes extraites. Détection en cours...</p>", unsafe_allow_html=True)


            for col in model.feature_names_in_:
                if col not in df.columns:
                    df[col] = 0

            X = df[model.feature_names_in_]
            df['incident'] = model.predict(X)
            df['cause_probable'] = df.apply(identifier_cause_ai, axis=1)

            incidents = df[df['incident'] == 1]
            st.markdown(f"<p style='color:black; font-size:18px;'>🚨 {len(incidents)} incident(s) détecté(s).</p>", unsafe_allow_html=True)


            if not incidents.empty:
                st.markdown("<h3 style='color:black;'>📊 Requêtes lentes détectées</h3>", unsafe_allow_html=True)
                st.dataframe(incidents[['query_id', 'query_text', 'elapsed_time', 'rows_processed', 'cpu_percent', 'incident', 'cause_probable']])

                fig = px.bar(
                    incidents,
                    x='query_id',
                    y='elapsed_time',
                    hover_data=['rows_processed', 'cpu_percent', 'cause_probable'],
                    title="Temps d'exécution par requête (incidents)",
                    labels={'elapsed_time': 'Temps (s)', 'query_id': 'SQL ID'},
                    color='rows_processed',
                    color_continuous_scale='reds'
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

            # Bouton d'export CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Télécharger les résultats (CSV)", csv, "incidents_detected.csv")

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
