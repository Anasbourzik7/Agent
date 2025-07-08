import os
import re
import json

folder_path = '/Users/paki/Desktop/PFE/AWR'
result = {}

# Regex plus souple pour extraire Snap Type et Sessions
snap_pattern = re.compile(
    r'<tr><td[^>]*>(Begin Snap:|End Snap:)</td>(?:<td[^>]*>.*?</td>){2}<td[^>]*>(\d+)</td>',
    re.IGNORECASE
)

# Liste des fichiers .html ou .txt dans le dossier
files = [f for f in os.listdir(folder_path) if f.endswith('.html') or f.endswith('.txt')]

for filename in files:
    file_path = os.path.join(folder_path, filename)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Chercher Begin Snap et End Snap sessions
    matches = snap_pattern.findall(content)
    begin_sessions = None
    end_sessions = None

    for snap_type, sessions in matches:
        if snap_type.strip().lower() == 'begin snap:':
            begin_sessions = int(sessions)
        elif snap_type.strip().lower() == 'end snap:':
            end_sessions = int(sessions)

    if begin_sessions is not None and end_sessions is not None:
        moyenne = (begin_sessions + end_sessions) / 2
        awr_name = os.path.splitext(filename)[0]  # Nom de fichier 
        result[awr_name] = {
            "moyenne_sessions": moyenne,
            "begin_sessions": begin_sessions,
            "end_sessions": end_sessions
        }
    else:
        print(f"[IGNORÉ] Pas de Snap complet trouvé dans {filename}")

# Sauvegarder en JSON dans /Users/paki/Desktop/PFE
output_file = '/Users/paki/Desktop/PFE/4-Sessions/sessions_moyenne.json'
with open(output_file, 'w', encoding='utf-8') as json_file:
    json.dump(result, json_file, indent=4)

print(f"✅ Traitement terminé. Résultats sauvegardés dans : {output_file}")
