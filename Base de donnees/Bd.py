import sqlite3
import json
import os

# Nom du fichier JSON corrigé
json_file = '/Users/paki/Desktop/PFE/1- ExtractionDonnees/Data.json'

# Nom de la base de données SQLite
db_file = 'awr_data_corrected.db'

# Vérifier si le fichier JSON existe
if not os.path.exists(json_file):
    raise FileNotFoundError(f"Le fichier JSON {json_file} n'existe pas.")

# Charger les données JSON corrigées
with open(json_file, 'r', encoding='utf-8') as f:
    corrected_data = json.load(f)

# Connexion ou création de la base de données SQLite
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Créer la table awr_data si elle n'existe pas
cursor.execute('''
    CREATE TABLE IF NOT EXISTS awr_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_id TEXT,
        awr_file TEXT,
        elapsed_time REAL,
        rows_processed INTEGER
    )
''')

# Insérer les données du JSON corrigé dans la table
for entry in corrected_data:
    cursor.execute('''
        INSERT INTO awr_data (query_id, awr_file, elapsed_time, rows_processed)
        VALUES (?, ?, ?, ?)
    ''', (
        entry.get('query_id'),
        entry.get('awr_file'),
        entry.get('elapsed_time'),
        entry.get('rows_processed')
    ))

# Sauvegarder les changements et fermer la connexion
conn.commit()
conn.close()

print(f"✅ Base de données '{db_file}' créée et données insérées avec succès depuis '{json_file}'.")