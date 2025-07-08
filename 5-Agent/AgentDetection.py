import pandas as pd
import joblib

# === Charger le modèle
model_path = "/Users/paki/Desktop/PFE/2-Models/XGext.pkl"
model = joblib.load(model_path)

# === Charger les données JSON
data_path = "/Users/paki/Desktop/PFE/1- ExtractionDonnees/Data.json"
df = pd.read_json(data_path)

# == Supprimer 'incident' si déjà présente
if 'incident' in df.columns:
    df = df.drop(columns=['incident'])

# == Colonnes exactes attendues par le modèle
model_features = model.feature_names_in_.tolist()

# === Ajouter les colonnes manquantes avec valeur par défaut
for col in model_features:
    if col not in df.columns:
        print(f"⚠️ Colonne manquante ajoutée automatiquement : {col}")
        df[col] = 0

# == Créer X sans jamais inclure accidentellement 'incident'
X = df[model_features]

# == Prédictions
df['incident'] = model.predict(X)

# == Affichage des incidents
incidents = df[df['incident'] == 1]
print("🔍 Incidents détectés :")
print(incidents[['query_id', 'elapsed_time', 'rows_processed', 'incident']])

# == Export CSV
df.to_csv("/Users/paki/Desktop/PFE/incidents_detectedXGext.csv", index=False)
print("✅ Résultat enregistré dans 'incidents_detectedXGext.csv'")
