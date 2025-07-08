import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.ticker as ticker

# --- 1. Paramètres ---
json_file = '/Users/paki/Desktop/PFE/1- ExtractionDonnees/Data.json'

# --- 2. Charger le fichier JSON ---
try:
    df = pd.read_json(json_file)
    print(f"✅ Données chargées depuis {json_file}")
except Exception as e:
    print(f"❌ Erreur lors du chargement du JSON : {e}")
    exit()

# --- 3. Nettoyage ---
# Filtrage du cpu_percent et elapsed_time > 0 et on peut ajouter une limite max pour cpu_percent si souhaité (par exemple < 100)
df_clean = df[
    (df['cpu_percent'] > 0) & 
    (df['cpu_percent'] <= 100) &
    (df['elapsed_time'] > 0)
]

# --- 4. Régression linéaire ---
coef = np.polyfit(df_clean['cpu_percent'], df_clean['elapsed_time'], 1)
poly1d_fn = np.poly1d(coef)

# --- 5. Tracer le graphique ---
plt.figure(figsize=(14, 7))
sns.scatterplot(data=df_clean, x='cpu_percent', y='elapsed_time', alpha=0.6, label="Données")

# --- 6. Ajouter les query_id sur les points ---
for i in range(df_clean.shape[0]):
    plt.text(
        df_clean['cpu_percent'].iloc[i],
        df_clean['elapsed_time'].iloc[i],
        df_clean['query_id'].iloc[i],
        fontsize=8,
        alpha=0.7
    )

# --- 7. Courbe de régression ---
x_vals = np.linspace(df_clean['cpu_percent'].min(), df_clean['cpu_percent'].max(), 100)
plt.plot(x_vals, poly1d_fn(x_vals), color='red', label=f"Régression : y = {coef[0]:.2e}x + {coef[1]:.2f}")

# --- 8. Mise en forme ---
plt.title("Temps d'exécution vs pourcentage CPU", fontsize=16)
plt.xlabel("Pourcentage CPU (%)", fontsize=14)
plt.ylabel("Temps écoulé (secondes)", fontsize=14)
plt.grid(True)
plt.legend(fontsize=12)

# Axe X avec pourcentage (format simple sans séparateurs)
plt.gca().xaxis.set_major_formatter(ticker.PercentFormatter())

plt.tight_layout()
plt.show()
