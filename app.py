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
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')])
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 30))
    
    # Tableau principal des requêtes
    table_data = [['ID Requête', 'Requête', 'Temps', 'Lignes', 'CPU (%)', 'Cause probable']]
    
    for _, row in df.iterrows():
        # Utiliser Paragraph pour le texte des requêtes pour permettre le wrap
        query_text = str(row['query_text'])
        query_paragraph = Paragraph(query_text, ParagraphStyle(
            'QueryText',
            parent=styles['Normal'],
            fontSize=8,
            wordWrap='CJK',
            leftIndent=3,
            rightIndent=3,
            spaceAfter=3
        ))
        
        # Format des causes avec retour à la ligne
        cause = str(row['cause_probable'])
        if ',' in cause:
            cause = cause.replace(', ', '\n')
        
        table_data.append([
            str(row['query_id']),
            query_paragraph,
            f"{row['elapsed_time']:.2f}",
            f"{row['rows_processed']:,}",
            f"{row['cpu_percent']:.1f}",
            cause
        ])
    
    # Définir les largeurs des colonnes - ajuster pour inclure la nouvelle colonne
    col_widths = [1*inch, 3.8*inch, 0.8*inch, 0.9*inch, 0.7*inch, 1.3*inch]
    
    main_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Style du tableau principal
    table_style = [
        # En-tête
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Corps du tableau
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]
    
    # Alternance des couleurs et styles conditionnels
    for i in range(1, len(table_data)):
        # Alternance des couleurs
        if i % 2 == 0:
            table_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8f9fa')))
        else:
            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.white))
        
        # Coloration selon le temps d'exécution
        elapsed_time = float(table_data[i][2])
        if elapsed_time > 400:
            table_style.append(('TEXTCOLOR', (2, i), (2, i), HexColor('#e74c3c')))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))
        elif elapsed_time > 100:
            table_style.append(('TEXTCOLOR', (2, i), (2, i), HexColor('#f39c12')))
            table_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))
        
        # Coloration selon le CPU
        cpu_percent = float(table_data[i][4])
        if cpu_percent > 25:
            table_style.append(('BACKGROUND', (4, i), (4, i), HexColor('#ffe6e6')))
            table_style.append(('TEXTCOLOR', (4, i), (4, i), HexColor('#c0392b')))
            table_style.append(('FONTNAME', (4, i), (4, i), 'Helvetica-Bold'))
        
        # Style des causes
        cause = table_data[i][5]
        if 'Incident probable' in cause:
            table_style.append(('BACKGROUND', (5, i), (5, i), HexColor('#fff3cd')))
            table_style.append(('TEXTCOLOR', (5, i), (5, i), HexColor('#856404')))
        elif 'Lignes traitées' in cause or 'Surcharge CPU' in cause:
            table_style.append(('BACKGROUND', (5, i), (5, i), HexColor('#f8d7da')))
            table_style.append(('TEXTCOLOR', (5, i), (5, i), HexColor('#721c24')))
    
    main_table.setStyle(TableStyle(table_style))
    story.append(main_table)
    story.append(Spacer(1, 30))
    
    # Recommandations
    recommendations_style = ParagraphStyle(
        'Recommendations',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#721c24'),
        leftIndent=20,
        rightIndent=20,
        spaceAfter=10
    )
    
    recommendations_title = Paragraph("<b>Recommandations</b>", 
                                    ParagraphStyle('RecommendationsTitle', 
                                                 parent=recommendations_style,
                                                 fontSize=12,
                                                 textColor=HexColor('#c0392b')))
    
    story.append(recommendations_title)
    
    # Trouver la requête la plus lente
    slowest_query = df.loc[df['elapsed_time'].idxmax()]
    
    # Liste complète des recommandations
    import random
    
    all_recommendations = [
        f"Analyser en priorité la requête <b>{slowest_query['query_id']}</b> avec un temps d'exécution de {slowest_query['elapsed_time']:.2f}s",
        "Optimiser les procédures stockées identifiées dans l'analyse",
        "Vérifier l'indexation des tables impliquées dans les requêtes problématiques",
        "Surveiller la charge CPU lors de l'exécution des requêtes critiques",
        "Créer des index composites sur les colonnes fréquemment utilisées dans les clauses WHERE, JOIN et ORDER BY",
        "Examiner les plans d'exécution pour identifier les opérations coûteuses et les goulots d'étranglement",
        "Privilégier les jointures INNER aux jointures OUTER et s'assurer que les conditions utilisent des colonnes indexées",
        "Utiliser LIMIT/TOP pour restreindre le nombre de lignes retournées et éviter les transferts inutiles",
        "Transformer les sous-requêtes corrélées en jointures ou utiliser des CTE pour améliorer les performances",
        "Maintenir des statistiques à jour sur les tables pour optimiser les plans d'exécution",
        "Éviter l'utilisation de fonctions sur les colonnes dans les clauses WHERE",
        "Implémenter le partitionnement horizontal pour les tables volumineuses",
        "Traiter les opérations en lot plutôt qu'en boucles pour réduire les allers-retours réseau",
        "Identifier et résoudre les conflits de verrous qui peuvent causer des blocages"
    ]
    
    # Sélectionner 4 recommandations aléatoires
    selected_recommendations = random.sample(all_recommendations, 4)
    
    recommendations_text = ""
    for i, rec in enumerate(selected_recommendations, 1):
        recommendations_text += f"• {rec}<br/>"
    
    recommendations_paragraph = Paragraph(recommendations_text, recommendations_style)
    story.append(recommendations_paragraph)
    
    # Construire le PDF
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

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

                # === Génération du PDF avec le nouveau style ===
                awr_title = uploaded_file.name if uploaded_file else "AWR inconnu"
                logo_path = "7-assests/Logo_hps_0 (1).png"
                
                # Préparer les données pour le PDF
                pdf_df = incidents[["query_id", "query_text", "elapsed_time", "rows_processed", "cpu_percent", "cause_probable"]].copy()
                
                # Générer le PDF professionnel
                pdf_buffer = generate_professional_pdf(pdf_df, awr_title, logo_path)

                # === Bouton de téléchargement ===
                st.download_button(
                    label="📄 Télécharger le rapport PDF (requêtes lentes)",
                    data=pdf_buffer,
                    file_name="rapport_requetes_lentes.pdf",
                    mime="application/pdf"
                )
                
    except Exception as e:
        st.error(f"❌ Erreur : {e}")
