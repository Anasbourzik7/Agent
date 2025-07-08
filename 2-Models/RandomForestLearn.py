import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
from sklearn.ensemble import RandomForestClassifier
import numpy as np

# Paramètres de la droite de régression
slope = 2.57e-04
intercept = 136.40
seuil_multiplicateur = 1.5  # Multiplicateur pour définir un seuil de temps "trop long"

# Fonction pour calculer le seuil de temps
def get_regression_threshold(rows_processed):
    return (slope * rows_processed + intercept) * seuil_multiplicateur

# Fonction pour évaluer la performance
def is_bad_performance_regression(rows_processed, elapsed_time):
    threshold = get_regression_threshold(rows_processed)
    return 1 if elapsed_time > threshold else 0

# Connexion à la base de données
conn = sqlite3.connect('/Users/paki/Desktop/PFE/Base de donnees/awr_data_corrected.db')

# Requête SQL
query = '''
    SELECT query_id, awr_file, elapsed_time, rows_processed
    FROM awr_data;
'''

# Chargement des données
df = pd.read_sql(query, conn)
conn.close()

# Affichage initial
print(df.head())

# Ajout de la colonne Bad_performance
df['Bad_performance'] = df.apply(
    lambda row: is_bad_performance_regression(row['rows_processed'], row['elapsed_time']),
    axis=1
)

# Vérification
print("\nPremières lignes avec 'Bad_performance' (calculé par régression):")
print(df.head())

# Remplacer les NaN par 0
df = df.fillna(0)

# Définition des features et de la cible
X = df[['elapsed_time', 'rows_processed']]
y = df['Bad_performance']

# Division des données
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Modèle Random Forest
rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)

# Évaluation
y_pred_rf = rf_model.predict(X_test)
print(f"\nPrécision du modèle Random Forest : {rf_model.score(X_test, y_test):.2f}")
print("\nRésultats de la classification par Random Forest :\n", classification_report(y_test, y_pred_rf))

# Sauvegarde du modèle
joblib.dump(rf_model, 'RandomForest_model.pkl')
print("Modèle Random Forest entraîné et sauvegardé dans 'RandomForest_model.pkl'")

# Affichage de l'équation utilisée
print(f"\nÉquation de régression utilisée pour définir 'Bad_performance':")
print(f"Temps seuil (secondes) = ({slope:.2e} * Nombre de lignes traitées + {intercept:.2f}) * {seuil_multiplicateur:.1f}")
