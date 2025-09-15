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
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT

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

# === Fonction pour générer le PDF avec le style moderne
def generate_professional_pdf(df, awr_title, logo_path):
    """
    Génère un PDF professionnel avec le style du rapport HTML
    """
    pdf_buffer = BytesIO()
    
    # Utiliser le format paysage pour plus d'espace
    doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4), 
                          rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Style pour le titre principal
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=HexColor('#2c3e50'),
        alignment=TA_CENTER,
        spaceAfter=30,
        fontName='Helvetica-Bold'
    )
    
    # Style pour les méta-informations
    meta_style = ParagraphStyle(
        'MetaInfo',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#555555'),
        leftIndent=20,
        rightIndent=20,
        spaceAfter=10
    )
    
    # Éléments du document
    story = []
    
    # Logo (si existe)
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=80, height=30)
            logo.hAlign = 'LEFT'
            story.append(logo)
            story.append(Spacer(1, 20))
        except:
            pass
    
    # Titre principal
    title = Paragraph(f"Rapport d'Analyse des Requêtes Lentes", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Informations métadonnées
    from datetime import datetime
    current_date = datetime.now().strftime("%d %B %Y")
    
    meta_info = f"""
    <b>Fichier AWR :</b> {awr_title}<br/>
    <b>Date de génération :</b> {current_date}<br/>
    <b>Nombre de requêtes analysées :</b> {len(df)}
    """
    
    meta_paragraph = Paragraph(meta_info, meta_style)
    story.append(meta_paragraph)
    story.append(Spacer(1, 20))
    
    # Statistiques résumées
    max_time = df['elapsed_time'].max()
    avg_time = df['elapsed_time'].mean()
    max_cpu = df['cpu_percent'].max()
    incidents_count = len(df[df['cause_probable'] == 'Incident probable'])
    
    stats_data = [
        ['Métrique', 'Valeur'],
        ['Temps maximum', f'{max_time:.2f}s'],
        ['Temps moyen', f'{avg_time:.2f}s'],
        ['CPU maximum', f'{max_cpu:.1f}%'],
        ['Incidents probables', str(incidents_count)]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROW
