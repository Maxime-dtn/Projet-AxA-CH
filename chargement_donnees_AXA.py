#%%

from pathlib import Path
import pandas as pd


#%%

# Le chemin est construit à partir du dossier contenant ce script.
DOSSIER_PROJET = Path(__file__).resolve().parent
FICHIER_EXCEL = DOSSIER_PROJET / "AXA_VA_donnees_corrigees.xlsx"

if not FICHIER_EXCEL.is_file():
    raise FileNotFoundError(
        f"Fichier introuvable : {FICHIER_EXCEL}\n"
        "Place le fichier Excel corrigé dans le même dossier que ce script."
    )

#%%

# 1) Lecture intégrale des quatre feuilles, sans perdre leurs lignes de titre.
#    Le dictionnaire 'feuilles_brutes' contient un DataFrame pour chaque feuille.
feuilles_brutes = pd.read_excel(
    FICHIER_EXCEL,
    sheet_name=None,
    header=None,
    engine="openpyxl",
)

#%%

# 2) Les 1 100 RW SCN : observations avant et après réduction du bruit.
#    La ligne 5 (index 4) est la première ligne de données dans Excel.
df_rw = feuilles_brutes["Scenarios VA"].iloc[4:, :5].copy()
df_rw.columns = [
    "rw_scn",
    "impact_avant",
    "impact_apres",
    "ecart_apres_moins_avant",
    "ecart_absolu",
]
df_rw = df_rw.dropna(subset=["rw_scn"]).reset_index(drop=True)
for colonne in df_rw.columns:
    df_rw[colonne] = pd.to_numeric(df_rw[colonne], errors="raise")
df_rw["rw_scn"] = df_rw["rw_scn"].astype(int)

# 3) Les six scénarios de stress servant à la calibration.
#    La ligne 12 (index 11) est la première observation.
df_calibration = feuilles_brutes["Calibration"].iloc[11:17, :8].copy()
df_calibration.columns = [
    "scenario_stress",
    "dva",
    "dir_10y",
    "impact_observe",
    "impact_predit",
    "residu",
    "residu_absolu",
    "vs_tolerance",
]
df_calibration = df_calibration.reset_index(drop=True)
for colonne in ["dva", "dir_10y", "impact_observe", "impact_predit", "residu", "residu_absolu"]:
    df_calibration[colonne] = pd.to_numeric(df_calibration[colonne], errors="raise")

# 4) Coefficients du modèle AXA et seuil de tolérance.
df_parametres = feuilles_brutes["Calibration"].iloc[3:7, :2].copy()
df_parametres.columns = ["parametre", "valeur"]
df_parametres = df_parametres.reset_index(drop=True)
df_parametres["valeur"] = pd.to_numeric(df_parametres["valeur"], errors="raise")

# 5) Feuilles de documentation et de traçabilité, conservées en DataFrames.
df_source = feuilles_brutes["Source restauree"].copy()

# Dictionnaire pratique : toutes les tables accessibles par un nom.
dataframes = {
    "rw": df_rw,
    "calibration": df_calibration,
    "parametres": df_parametres,
    "source_brute": df_source,
}

# Quelques contrôles simples, sans interpréter les RW SCN comme des STxxxx.
assert len(df_rw) == 1100, f"Nombre de RW SCN inattendu : {len(df_rw)}"
assert df_rw["rw_scn"].is_unique, "Identifiants RW SCN dupliqués"
assert len(df_calibration) == 6, "Nombre de scénarios de calibration inattendu"

if __name__ == "__main__":
    print("Fichier lu :", FICHIER_EXCEL.name)
    print("Feuilles Excel :", list(feuilles_brutes))
    print("\nDimensions des DataFrames :")
    for nom, df in dataframes.items():
        print(f"  {nom:14s}: {df.shape[0]} lignes, {df.shape[1]} colonnes")

    print("\nPremières réalisations RW SCN :")
    print(df_rw.head().to_string(index=False))

    print("\nScénarios de calibration :")
    print(df_calibration.to_string(index=False))

    print("\nParamètres du modèle :")
    print(df_parametres.to_string(index=False))

# %%
