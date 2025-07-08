import os
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg

awr_folder = '/Users/paki/Desktop/Data/AWR/'
logo_path = '/Users/paki/Desktop/PFE/7-assests/Logo_hps_0 (1).png'  # Logo
all_data = []

def extract_metrics_from_executions(soup, filename):
    sections = soup.find_all("h3", class_="awr")
    for section in sections:
        if section.text.strip() == "SQL ordered by Executions":
            table = section.find_next("table")
            if not table:
                print(f"⚠️ Pas de table après 'SQL ordered by Executions' dans {filename}")
                return

            rows = table.find_all("tr")
            headers = [th.text.strip() for th in rows[0].find_all("th")]
            print(f"DEBUG [{filename}] Headers: {headers}")

            header_map = {header: idx for idx, header in enumerate(headers)}

            sql_id_idx = header_map.get("SQL Id")
            rows_proc_idx = header_map.get("Rows Processed")

            elapsed_idx = None
            for h in headers:
                if "Elapsed" in h and "Time" in h:
                    elapsed_idx = header_map[h]
                    break

            cpu_idx = header_map.get("%CPU")

            if sql_id_idx is None:
                print(f"⚠️ Colonne 'SQL Id' manquante dans {filename}")
                return

            for row in rows[1:]:
                cells = [td.text.strip() for td in row.find_all("td")]
                if len(cells) < len(headers):
                    continue

                try:
                    sql_id = cells[sql_id_idx]

                    rows_processed = 0
                    if rows_proc_idx is not None and cells[rows_proc_idx]:
                        rows_processed = int(cells[rows_proc_idx].replace(',', ''))

                    elapsed_time = 0.0
                    if elapsed_idx is not None and cells[elapsed_idx]:
                        elapsed_str = cells[elapsed_idx].replace(',', '').strip()
                        elapsed_time = float(elapsed_str)

                    cpu_percent = 0.0
                    if cpu_idx is not None and cells[cpu_idx]:
                        cpu_percent = float(cells[cpu_idx].replace('%', '').replace(',', '').strip())

                    all_data.append({
                        "SQL Id": sql_id,
                        "AWR File": filename,
                        "Rows Processed": rows_processed,
                        "Elapsed Time (s)": elapsed_time,
                        "%CPU": cpu_percent
                    })
                except Exception as e:
                    print(f"⚠️ Erreur lors de l'analyse d'une ligne dans {filename} : {e}")
            return

# Extraction des données
for filename in os.listdir(awr_folder):
    if filename.endswith('.html'):
        print(f"🔍 Traitement de {filename}...")
        with open(os.path.join(awr_folder, filename), 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')
            extract_metrics_from_executions(soup, filename)

if not all_data:
    print("❌ Aucune donnée extraite.")
    exit()

df = pd.DataFrame(all_data)
df = df.sort_values(by="Elapsed Time (s)", ascending=False).reset_index(drop=True)

# Chargement du logo
logo_img = mpimg.imread(logo_path)

pdf_path = "rapport_awr_with_logo_header.pdf"
with PdfPages(pdf_path) as pdf:
    # Création d'une figure globale avec 2 sous-figures (logo en haut, tableau en bas)
    fig = plt.figure(figsize=(12, max(6, len(df) * 0.4 + 2)))
    
    # 1) Axes logo (sans axes visibles)
    ax_logo = fig.add_axes([0, 0.9, 0.15, 0.1])  # [left, bottom, width, height] en fraction figure
    ax_logo.imshow(logo_img)
    ax_logo.axis('off')

    # 2) Axes tableau en dessous du logo
    ax_table = fig.add_axes([0, 0, 1, 0.85])
    ax_table.axis('tight')
    ax_table.axis('off')
    
    table = ax_table.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(col=list(range(len(df.columns))))

    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

    # Graphiques par fichier AWR (logo en haut à gauche de chaque graphique)
    for filename, group_df in df.groupby("AWR File"):
        if group_df.empty:
            continue

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.scatter(group_df["Elapsed Time (s)"], group_df["Rows Processed"], color='blue')
        for _, row in group_df.iterrows():
            ax.text(row["Elapsed Time (s)"], row["Rows Processed"], row["SQL Id"], fontsize=8, alpha=0.7)
        ax.set_xlabel("Elapsed Time (s)")
        ax.set_ylabel("Rows Processed")
        ax.set_title(f"Rows Processed vs Elapsed Time\nFichier : {filename}")
        ax.grid(True)

        # On crée un inset_axes (petite zone pour l'image)
        from mpl_toolkits.axes_grid1.inset_locator import inset_axes
        axins = inset_axes(ax, width="15%", height="15%", loc='upper left', borderpad=1)
        axins.imshow(logo_img)
        axins.axis('off')

        pdf.savefig(fig)
        plt.close()

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.scatter(group_df["%CPU"], group_df["Rows Processed"], color='green')
        for _, row in group_df.iterrows():
            ax.text(row["%CPU"], row["Rows Processed"], row["SQL Id"], fontsize=8, alpha=0.7)
        ax.set_xlabel("%CPU")
        ax.set_ylabel("Rows Processed")
        ax.set_title(f"Rows Processed vs %CPU\nFichier : {filename}")
        ax.grid(True)

        axins = inset_axes(ax, width="15%", height="15%", loc='upper left', borderpad=1)
        axins.imshow(logo_img)
        axins.axis('off')

        pdf.savefig(fig)
        plt.close()

print(f"✅ Rapport PDF généré avec logo en header : {pdf_path}")
