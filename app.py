import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
from bs4 import BeautifulSoup
import cx_Oracle

# === Config de la page
st.set_page_config(page_title="Détection des perfs", layout="wide")

# === Logo avec reload
st.markdown("""
    <div style="text-align: center;">
        <a href="#" onclick="window.location.reload();">
            <img src="logo.png" width="120" style="cursor: pointer;" />
        </a>
    </div>
""", unsafe_allow_html=True)

# === Titre principal
st.markdown("<h2 style='color:#000000;'>🧠 Détection des performances </h2>", unsafe_allow_html=True)

# === CSS perso
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
        }
    </style>
""", unsafe_allow_html=True)

# === Charger le modèle
model = joblib.load("2-Models/XGext.pkl")

# === Connexion Oracle
st.markdown("### 🔌 Connexion à la base Oracle")

with st.form("oracle_conn_form"):
    col1, col2 = st.columns(2)
    with col1:
        host = st.text_input("Hôte", value="localhost")
        port = st.text_input("Port", value="1521")
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
    with col2:
        service_sid = st.text_input("Service Name ou SID", value="ORCL")
        use_sid = st.checkbox("Utiliser un SID (au lieu d’un Service Name)", value=False)

    submitted = st.form_submit_button("Se connecter")

# === Statut de connexion
is_connected = False
conn = None

if submitted:
    try:
        dsn = cx_Oracle.makedsn(host, port, sid=service_sid) if use_sid else cx_Oracle.makedsn(host, port, service_name=service_sid)
        conn = cx_Oracle.connect(user=username, password=password, dsn=dsn)
        st.success("✅ Connexion réussie à Oracle")
        is_connected = True
    except Exception as e:
        st.error(f"❌ Erreur de connexion : {e}")
        is_connected = False

status_color = "green" if is_connected else "red"
status_label = "Connected" if is_connected else "Not Connected"

st.markdown(f"""
    <div style="text-align:right; padding:10px 0;">
        <button style="background-color:{status_color}; color:white; border:none; padding:10px 20px; border-radius:5px;" disabled>
            {status_label}
        </button>
    </div>
""", unsafe_allow_html=True)

# === Upload AWR (seulement si connecté)
if is_connected:
    st.markdown("<h6 style='color:#000000;'>📤 Upload un fichier AWR (.html)</h6>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("", type="html")

    if uploaded_file is not None:
        try:
            html_string = uploaded_file.read().decode("utf-8", errors='ignore')

            def extract_data_from_awr(html_content, filename="uploaded_file"):
                soup = BeautifulSoup(html_content, 'lxml')
                all_data = []
                sql_texts = {}
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

                for table in soup.find_all('table', class_='tdiff'):
                    headers = [th.text.strip() for th in table.find_all('th')]
                    required_headers = ['Executions', 'Rows Processed', 'Elapsed  Time (s)', 'SQL Id']
                    if all(header in headers for header in required_headers):
                        header_map = {header: idx for idx, header in enumerate(headers)}
                        executions_idx = header_map['Executions']
                        rows_proc_idx = header_map['Rows Processed']
                        elapsed_time_idx = header_map['Elapsed  Time (s)']
                        sql_id_idx = header_map['SQL Id']
                        cpu_idx = next((i for i, h in enumerate(headers) if '%' in h and 'CPU' in h.upper()), None)

                        for row in table.find_all('tr')[1:]:
                            cells = row.find_all('td')
                            if len(cells) >= len(header_map):
                                try:
                                    data = {
                                        'query_id': cells[sql_id_idx].text.strip(),
                                        'awr_file': filename,
                                        'elapsed_time': float(cells[elapsed_time_idx].text.strip().replace(',', '')),
                                        'rows_processed': int(cells[rows_proc_idx].text.strip().replace(',', '')),
                                        'cpu_percent': float(cells[cpu_idx].text.strip().replace('%', '').replace(',', '.')) if cpu_idx is not None else 0.0,
                                        'query_text': sql_texts.get(cells[sql_id_idx].text.strip(), "")
                                    }
                                    all_data.append(data)
                                except Exception as e:
                                    st.warning(f"⚠️ Erreur ligne : {e}")

                return pd.DataFrame(all_data)

            df = extract_data_from_awr(html_string, filename=uploaded_file.name)

            if df.empty:
                st.error("❌ Aucune donnée extraite.")
            else:
                st.markdown(f"<p style='color:black; font-size:18px;'>✅ {len(df)} requêtes extraites. Détection en cours...</p>", unsafe_allow_html=True)

                for col in model.feature_names_in_:
                    if col not in df.columns:
                        df[col] = 0

                df['incident'] = model.predict(df[model.feature_names_in_])

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

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Télécharger les résultats (CSV)", csv, "incidents_detected.csv")

        except Exception as e:
            st.error(f"❌ Erreur : {e}")
