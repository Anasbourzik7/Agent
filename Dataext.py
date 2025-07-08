import os
import json
from bs4 import BeautifulSoup

awr_folder = '/Users/paki/Desktop/Data/AWR/'
all_data = []

# === Fonction 1 : extraire les requêtes complètes
def extract_complete_sql_texts(soup):
    sql_texts = {}
    sections = soup.find_all("h3", class_="awr")

    for section in sections:
        if "Complete List of SQL Text" in section.text:
            table = section.find_next("table")
            if not table:
                continue

            rows = table.find_all("tr")
            headers = [th.text.strip() for th in rows[0].find_all("th")]
            header_map = {h: i for i, h in enumerate(headers)}

            sql_id_idx = header_map.get("SQL Id")
            sql_text_idx = header_map.get("SQL Text")

            if sql_id_idx is None or sql_text_idx is None:
                continue

            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) <= max(sql_id_idx, sql_text_idx):
                    continue

                sql_id = cells[sql_id_idx].text.strip()
                sql_text = cells[sql_text_idx].text.strip()
                sql_texts[sql_id] = sql_text

    return sql_texts

# === Fonction 2 : extraire les métriques
def extract_metrics_from_executions(soup, filename):
    local_data = {}
    sections = soup.find_all("h3", class_="awr")
    for section in sections:
        if section.text.strip() == "SQL ordered by Executions":
            table = section.find_next("table")
            if not table:
                print(f"⚠️ Pas de table après SQL ordered by Executions dans {filename}")
                return {}

            rows = table.find_all("tr")
            headers = [th.text.strip() for th in rows[0].find_all("th")]
            header_map = {header: idx for idx, header in enumerate(headers)}

            # Index dynamiques
            sql_id_idx = header_map.get("SQL Id")
            rows_proc_idx = header_map.get("Rows Processed")
            elapsed_idx = header_map.get("Elapsed Time (s)")
            executions_idx = header_map.get("Executions")
            cpu_idx = header_map.get("%CPU")

            if sql_id_idx is None:
                print(f"⚠️ Colonne SQL Id manquante dans {filename}")
                return {}

            for row in rows[1:]:
                cells = [td.text.strip() for td in row.find_all("td")]
                if len(cells) < len(header_map):
                    continue

                try:
                    sql_id = cells[sql_id_idx]
                    rows_processed = int(cells[rows_proc_idx].replace(',', '')) if rows_proc_idx is not None and cells[rows_proc_idx] else 0
                    elapsed_time = float(cells[elapsed_idx].replace(',', '')) if elapsed_idx is not None and cells[elapsed_idx] else 0
                    cpu_percent = float(cells[cpu_idx].replace('%', '').replace(',', '.')) if cpu_idx is not None and cells[cpu_idx] else 0

                    local_data[sql_id] = {
                        "query_id": sql_id,
                        "awr_file": filename,
                        "rows_processed": rows_processed,
                        "elapsed_time": elapsed_time,
                        "cpu_percent": cpu_percent
                    }

                except Exception as e:
                    print(f"⚠️ Erreur dans {filename} pour SQL Id={sql_id} : {e}")
    return local_data

# === Parcours des fichiers AWR
for filename in os.listdir(awr_folder):
    if filename.endswith('.html'):
        print(f"🔍 Traitement de {filename}...")
        with open(os.path.join(awr_folder, filename), 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')

            # 1. Extraire requêtes complètes
            sql_texts = extract_complete_sql_texts(soup)

            # 2. Extraire métriques
            metrics = extract_metrics_from_executions(soup, filename)

            # 3. Fusionner les deux
            if metrics:
                for sql_id, entry in metrics.items():
                    entry['query_text'] = sql_texts.get(sql_id, "")
                    all_data.append(entry)

# === Sauvegarde finale
if not all_data:
    print("❌ Aucune donnée extraite.")
else:
    with open('Data.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=4)
    print("✅ Fichier créé : Data.json")

