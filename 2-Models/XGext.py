import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from xgboost import XGBClassifier
import joblib

# --- 1. Paramètres des régressions ---
slope_rows = 2.78e-04
intercept_rows = 106.40

slope_cpu = -3.06
intercept_cpu = 250.51

seuil_multiplicateur = 1.5

# --- 2. Fonctions d'évaluation ---
def get_regression_threshold_rows(rows_processed):
    return (slope_rows * rows_processed + intercept_rows) * seuil_multiplicateur

def get_regression_threshold_cpu(cpu_percent):
    return (slope_cpu * cpu_percent + intercept_cpu) * seuil_multiplicateur

def is_bad_performance(row):
    threshold_rows = get_regression_threshold_rows(row['rows_processed'])
    threshold_cpu = get_regression_threshold_cpu(row['cpu_percent'])
    # Mauvaise performance si elapsed_time dépasse au moins un des seuils
    return 1 if (row['elapsed_time'] > threshold_rows) or (row['elapsed_time'] > threshold_cpu) else 0

# --- 3. Charger les données ---
json_path = '/Users/paki/Desktop/PFE/1- ExtractionDonnees/Data.json'

try:
    df = pd.read_json(json_path)
    print(f"✅ Données chargées depuis {json_path}")
except Exception as e:
    print(f"❌ Erreur lors du chargement : {e}")
    exit()

# --- 4. Nettoyage ---
df = df[(df['rows_processed'] > 0) & (df['elapsed_time'] > 0) & (df['cpu_percent'] >= 0)]
df = df.fillna(0)

# --- 5. Détection des mauvaises performances avec les 2 critères ---
df['Bad_performance'] = df.apply(is_bad_performance, axis=1)

# --- 6. Préparation des données pour le modèle ---
X = df[['elapsed_time', 'rows_processed', 'cpu_percent']]
y = df['Bad_performance']

# --- 7. Split entraînement/test ---
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- 8. Entraînement XGBoost ---
xgb_model = XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)
xgb_model.fit(X_train, y_train)

# --- 9. Évaluation ---
y_pred_xgb = xgb_model.predict(X_test)
print(f"\n✅ Précision XGBoost : {xgb_model.score(X_test, y_test):.2f}")
print("\n🧠 Rapport de classification :\n", classification_report(y_test, y_pred_xgb))

# --- 10. Sauvegarde ---
joblib.dump(xgb_model, 'XGext.pkl')
print("📦 Modèle sauvegardé dans 'XGext.pkl'")
