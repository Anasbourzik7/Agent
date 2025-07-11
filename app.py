import streamlit as st
import pandas as pd
import joblib
import plotly.express as px
from bs4 import BeautifulSoup
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import pyplot as plt
from matplotlib import image as mpimg
from io import BytesIO
import matplotlib.pyplot as plt
import textwrap
import os

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
        }
    </style>
""", unsafe_allow_html=True)

# === Formulaire Oracle (désactivé mais visible pour l'encadrant)
st.markdown("<h3 style='color:black;'>🔌 Connexion Oracle (désactivée pour le déploiement cloud)</h3>", unsafe_allow_html=True)
with st.form("oracle_conn_form"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<label style='color:black;'>Hôte</label>", unsafe_allow_html=True)
        st.text_input("host", placeholder="ex: 127.0.0.1", disabled=True)

        st.markdown("<label style='color:black;'>Port</label>", unsafe_allow_html=True)
        st.text_input("port", placeholder="ex: 1521", disabled=True)

        st.markdown("<label style='color:black;'>Utilisateur</label>", unsafe_allow_html=True)
        st.text_input("user", disabled=True)

        st.markdown("<label style='color:black;'>Mot de passe</label>", unsafe_allow_html=True)
        st.text_input("password", type="password", disabled=True)

    with col2:
        st.markdown("<label style='color:black;'>Service Name ou SID</label>", unsafe_allow_html=True)
        st.text_input("service_name", placeholder="ex: ORCL", disabled=True)
        st.checkbox("Utiliser un SID", value=False, disabled=True)

    st.form_submit_button("Se connecter", disabled=True)

# === Bouton de statut connexion simulée (désactivé)
st.markdown("""
    <div style="text-align:right; padding:10px 0;">
        <button style="background-color:#b00020; color:white; border:none; padding:10px 20px; border-radius:5px;" disabled>
            Connexion Oracle désactivée (environnement cloud)
        </button>
    </div>
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

# === Fonctions d'analyse de performance
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

# === Fonction pour calculer la largeur des colonnes automatiquement
def calculate_column_widths(df, column_labels):
    """
    Calcule les largeurs relatives des colonnes en fonction du contenu de manière intelligente
    """
    widths = []
    total_content_analysis = []
    
    for i, col in enumerate(column_labels):
        # Largeur du header
        header_width = len(col)
        
        # Analyse du contenu de la colonne
        if i < len(df.columns):
            content_series = df.iloc[:, i].astype(str)
            content_lengths = content_series.str.len()
            
            # Statistiques du contenu
            avg_length = content_lengths.mean()
            max_length = content_lengths.max()
            min_length = content_lengths.min()
            
            # Logique intelligente par type de colonne
            if col == "Texte Requête":
                # Pour les requêtes SQL : privilégier la lisibilité
                optimal_width = min(max(avg_length * 0.6, 80), 120)  # Entre 80 et 120 chars
            elif col == "ID Requête":
                # Pour les IDs : largeur fixe raisonnable
                optimal_width = max(header_width, 15)
            elif "Temps" in col or "CPU" in col:
                # Pour les métriques numériques : largeur modérée
                optimal_width = max(header_width, max_length, 12)
            elif col == "Cause probable":
                # Pour les causes : largeur adaptée au contenu
                optimal_width = min(max(avg_length * 0.8, 25), 50)
            else:
                # Cas général : utiliser la moyenne pondérée
                optimal_width = min(max(avg_length * 0.7, header_width), 80)
                
            total_content_analysis.append({
                'col': col,
                'header_width': header_width,
                'avg_length': avg_length,
                'max_length': max_length,
                'optimal_width': optimal_width
            })
        else:
            optimal_width = header_width
            
        widths.append(optimal_width)
    
    return widths

# === Fonction pour ajuster automatiquement les cellules du tableau
def create_auto_adjusted_table(df, column_labels, fig, ax_table):
    """
    Crée un tableau avec ajustement automatique et intelligent des cellules
    """
    # Calculer les largeurs des colonnes
    col_widths = calculate_column_widths(df, column_labels)
    total_width = sum(col_widths)
    
    # Normaliser les largeurs (somme = 1)
    normalized_widths = [w / total_width for w in col_widths]
    
    # Préparer les données avec wrapping intelligent et adaptatif
    wrapped_data = []
    row_heights = []
    
    for row_idx, (_, row) in enumerate(df.iterrows()):
        wrapped_row = []
        max_lines_in_row = 1
        
        for col_idx, (cell_value, width, col_name) in enumerate(zip(row, col_widths, column_labels)):
            cell_str = str(cell_value)
            
            # Logique de wrapping intelligente par type de colonne
            if col_name == "Texte Requête":
                # Pour les requêtes SQL : wrapping spécialisé
                if len(cell_str) > 150:  # Requête très longue
                    # Diviser par mots-clés SQL pour une meilleure lisibilité
                    sql_keywords = ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'AND', 'OR', 'JOIN', 'UNION']
                    wrapped_text = cell_str
                    
                    # Insérer des retours à la ligne avant les mots-clés importants
                    for keyword in sql_keywords:
                        if f' {keyword} ' in wrapped_text.upper():
                            wrapped_text = wrapped_text.replace(f' {keyword} ', f'\n{keyword} ')
                            wrapped_text = wrapped_text.replace(f' {keyword.lower()} ', f'\n{keyword.lower()} ')
                    
                    # Nettoyer les multiples retours à la ligne
                    lines = [line.strip() for line in wrapped_text.split('\n') if line.strip()]
                    
                    # Limiter le nombre de lignes pour éviter les cellules trop hautes
                    if len(lines) > 8:
                        lines = lines[:7] + ['...']
                    
                    wrapped_text = '\n'.join(lines)
                else:
                    # Wrapping standard pour les requêtes courtes
                    wrap_width = max(int(width * 0.9), 40)
                    wrapped_text = "\n".join(textwrap.wrap(cell_str, width=wrap_width))
            
            elif col_name == "ID Requête":
                # IDs : pas de wrapping généralement nécessaire
                wrapped_text = cell_str
            
            elif col_name == "Cause probable":
                # Causes : wrapping avec séparateurs intelligents
                if ', ' in cell_str:
                    causes = cell_str.split(', ')
                    if len(causes) > 1:
                        wrapped_text = '\n'.join(causes)
                    else:
                        wrapped_text = cell_str
                else:
                    wrap_width = max(int(width * 0.8), 25)
                    wrapped_text = "\n".join(textwrap.wrap(cell_str, width=wrap_width))
            
            else:
                # Colonnes numériques et autres : wrapping standard
                if len(cell_str) > width:
                    wrap_width = max(int(width * 0.8), 15)
                    wrapped_text = "\n".join(textwrap.wrap(cell_str, width=wrap_width))
                else:
                    wrapped_text = cell_str
            
            # Compter le nombre de lignes
            lines_count = len(wrapped_text.split('\n'))
            max_lines_in_row = max(max_lines_in_row, lines_count)
            
            wrapped_row.append(wrapped_text)
        
        wrapped_data.append(wrapped_row)
        row_heights.append(max_lines_in_row)
    
    # le tableau
    table = ax_table.table(
        cellText=wrapped_data,
        colLabels=column_labels,
        loc='center',
        cellLoc='left',
        colWidths=normalized_widths
    )
    
    # Ajuster les propriétés du tableau
    table.auto_set_font_size(False)
    table.set_fontsize(9)  # Taille légèrement augmentée pour une meilleure lisibilité
    
    # Ajuster la hauteur des lignes en fonction du contenu réel
    for i in range(len(wrapped_data) + 1):  # +1 pour le header
        for j in range(len(column_labels)):
            cell = table[(i, j)]
            if i == 0:  # Header
                cell.set_height(0.1)
                cell.set_facecolor('#4CAF50')
                cell.set_text_props(weight='bold', color='white', fontsize=10)
            else:
                # Hauteur adaptative basée sur le contenu réel de la ligne
                line_height = row_heights[i-1]
                height = max(0.08, 0.04 * line_height)  # Hauteur plus généreuse
                cell.set_height(height)
                
                # Alternance des couleurs pour les lignes
                if i % 2 == 0:
                    cell.set_facecolor('#f8f9fa')
                else:
                    cell.set_facecolor('#ffffff')
                
                # Ajuster la taille de police pour les cellules avec beaucoup de contenu
                if line_height > 5:
                    cell.set_text_props(fontsize=8)
                else:
                    cell.set_text_props(fontsize=9)
    
    return table, max(row_heights)

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

                # === PDF amélioré avec ajustement automatique ===
                awr_title = uploaded_file.name if uploaded_file else "AWR inconnu"

                # Les données à afficher
                pdf_df = incidents[["query_id", "query_text", "elapsed_time", "cpu_percent", "cause_probable"]].copy()
                pdf_df.rename(columns={
                    "query_id": "ID Requête",
                    "query_text": "Texte Requête",
                    "elapsed_time": "Temps écoulé (s)",
                    "cpu_percent": "CPU (%)",
                    "cause_probable": "Cause probable"
                }, inplace=True)

                # === Charger le logo HPS 
                logo_path = "7-assests/Logo_hps_0 (1).png"
                logo_img = mpimg.imread(logo_path) if os.path.exists(logo_path) else None

                # ===  PDF avec ajustement  
                pdf_buffer = BytesIO()
                with PdfPages(pdf_buffer) as pdf:
                    # Calculer la taille de la figure de manière plus précise
                    base_height = 3
                    # Estimation basée sur le contenu réel
                    avg_content_per_row = pdf_df.iloc[:, 1].astype(str).str.len().mean()  # Colonne texte requête
                    complexity_factor = min(avg_content_per_row / 100, 3)  # Facteur de complexité
                    estimated_height = base_height + len(pdf_df) * (1.2 + complexity_factor * 0.5)
                    
                    fig = plt.figure(figsize=(20, max(estimated_height, 12)))  # Largeur encore plus importante

                    # Logo
                    if logo_img is not None:
                        ax_logo = fig.add_axes([0.01, 0.94, 0.1, 0.04])
                        ax_logo.imshow(logo_img)
                        ax_logo.axis('off')

                    # Titre (centré)
                    fig.text(0.5, 0.97, f"🧠 Analyse des performances - Fichier AWR : {awr_title}",
                            ha='center', fontsize=18, fontweight='bold', color='black')

                    # Tableau avec ajustement automatique et intelligent
                    ax_table = fig.add_axes([0.01, 0.01, 0.98, 0.92])  # Maximum d'espace pour le tableau
                    ax_table.axis('off')

                    column_labels = ["ID Requête", "Texte Requête", "Temps écoulé (s)", "CPU (%)", "Cause probable"]
                    
                    # Créer le tableau avec ajustement automatique et intelligent
                    table, max_lines = create_auto_adjusted_table(pdf_df, column_labels, fig, ax_table)

                    pdf.savefig(fig, bbox_inches='tight', dpi=300, facecolor='white')  # Fond blanc
                    plt.close()

                # === Bouton de téléchargement
                pdf_buffer.seek(0)
                st.download_button(
                    label="📄 Télécharger le rapport PDF (requêtes lentes)",
                    data=pdf_buffer,
                    file_name="rapport_requetes_lentes.pdf",
                    mime="application/pdf"
                )

    except Exception as e:
        st.error(f"❌ Erreur : {e}")
