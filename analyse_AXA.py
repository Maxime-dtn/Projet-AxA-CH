# %%
"""Analyse exploratoire des données VA d'AXA.


Sorties : resultats_AXA/ (CSV, compte rendu, graphiques PNG).
Le programme ne modifie jamais le classeur Excel.

IMPORTANT : les 1 100 RW SCN appartiennent à un seul scénario de stress, non identifié. 
Les colonnes 'Before' et 'After' sont des évaluations appariées; 
la méthode de réduction du bruit n'est pas documentée dans le fichier fourni.
"""

from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display
from chargement_donnees_AXA import df_rw, df_calibration, df_parametres, DOSSIER_PROJET

# %% Configuration et légende des unités
DOSSIER_SORTIE = DOSSIER_PROJET / "resultats_AXA"
DOSSIER_FIGURES = DOSSIER_SORTIE / "figures"

# On affiche les impacts en millions d'unités de la source pour faciliter
# la lecture, SANS supposer que les montants sont en euros.
ECHELLE_GRAPHIQUES = 1_000_000
UNITES_AXE = "Impact VA (millions d'unités du fichier)"
COULEURS = {"avant": "#2563EB", "apres": "#0F766E", "ecart": "#D97706"}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 14,
    "axes.titleweight": "semibold",
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.17,
    "grid.linestyle": "--",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def sauvegarder_figure(nom: str) -> None:
    """Enregistre la figure active dans resultats_AXA/figures/."""
    DOSSIER_FIGURES.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(DOSSIER_FIGURES / nom, dpi=190, bbox_inches="tight")
    plt.close()


def exporter_table(table: pd.DataFrame, nom: str) -> None:
    """UTF-8 avec BOM + séparateur ; : ouverture facilitée dans Excel FR."""
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    table.to_csv(DOSSIER_SORTIE / nom, sep=";", encoding="utf-8-sig", index=False)


# %% Contrôle qualité
# on vérifie : Dimensions, types, valeurs manquantes, doublons, identifiants et cohérence des différences

def controle_qualite(rw: pd.DataFrame,
                    calibration: pd.DataFrame,
                    parametres: pd.DataFrame
                    ) -> pd.DataFrame:
    """Contrôles qualité, sert à vérifier que les données sont correctement structurées et exploitables avant de commencer l'analyse. 
    Attention cependant, aucune suppression ou correction n'est apportée. """
    
    resultats = []

    def ajouter(jeu, controle, valeur, statut, remarque=""):
        resultats.append({
            "jeu": jeu, "controle": controle, "valeur": valeur,
            "statut": statut, "remarque": remarque,
        })

    # Dimensions attendues et types réellement reçus
    for nom, table, attendu in [
        ("RW SCN", rw, 1100),
        ("Calibration", calibration, 6),
        ("Paramètres", parametres, 4),
    ]:
        # Pour chacun des trois jeux de données, on vérifie le nombre de lignes et de colonnes, ainsi que la présence de lignes entièrement dupliquées et de valeurs manquantes.
        ajouter(nom, "nombre_lignes", len(table),
               "OK" if len(table) == attendu else "ALERTE",
               f"Nombre attendu : {attendu}")
    
        ajouter(nom, "nombre_colonnes", table.shape[1], "INFO")

        ajouter(nom, "lignes_entierement_dupliquees",
               int(table.duplicated().sum()),
               "OK" if not table.duplicated().any() else "ALERTE")
        
        for col in table.columns:
            n_missing = int(table[col].isna().sum())
            ajouter(nom, f"valeurs_manquantes::{col}", n_missing,
                   "OK" if n_missing == 0 else "ALERTE",
                   f"Type pandas : {table[col].dtype}")

    # Vérifications des doublons d'id
    col_id = "rw_scn"
    ids = pd.to_numeric(rw[col_id], errors="coerce")
    doublons_id = int(ids.dropna().duplicated().sum())
    ajouter("RW SCN", "identifiants_dupliques", doublons_id,
           "OK" if doublons_id == 0 else "ALERTE")

    # On vérifie ici que les 1 100 identifiants sont présents
    valeurs_id = ids.dropna().astype(int)
    sequence_attendue = set(range(1, 1101))
    ids_observes = set(valeurs_id.tolist())
    manquants = sorted(sequence_attendue - ids_observes)
    inattendus = sorted(ids_observes - sequence_attendue)

    ajouter("RW SCN", "identifiants_manquants_1_a_1100", len(manquants),
           "OK" if not manquants else "ALERTE",
           str(manquants))
    
    ajouter("RW SCN", "identifiants_hors_plage_1_a_1100", len(inattendus),
           "OK" if not inattendus else "ALERTE",
           str(inattendus))

    # On vérifie que chaque réalisation possède deux impacts
    a = pd.to_numeric(rw["impact_avant"], errors="coerce")
    b = pd.to_numeric(rw["impact_apres"], errors="coerce")
    n_paires = int((a.notna() & b.notna() & ids.notna()).sum())
    ajouter("RW SCN", "paires_avant_apres_completes", n_paires,
           "OK" if n_paires == len(rw) else "ALERTE")
    # Le fichier réunit déjà les deux séries sur une même ligne et avec un seul ID.
    # Cette vérification confirme l'appariement STRUCTUREL, pas sa validité actuarielle.

    # Vérification des valeurs des écarts signés
    diff_recalculee = b - a
    if "ecart_apres_moins_avant" in rw:
        d = pd.to_numeric(rw["ecart_apres_moins_avant"], errors="coerce")
        anomalies = int((~np.isclose(d, diff_recalculee,
                                   rtol=0, atol=1e-6, equal_nan=True)).sum())
        ajouter("RW SCN", "incoherences_ecart_signe", anomalies,
               "OK" if anomalies == 0 else "ALERTE")

    
    # Vérification des écarts absolus
    if "ecart_absolu" in rw:
        da = pd.to_numeric(rw["ecart_absolu"], errors="coerce")
        anomalies = int((~np.isclose(da, diff_recalculee.abs(),
                                   rtol=0, atol=1e-6, equal_nan=True)).sum())
        ajouter("RW SCN", "incoherences_ecart_absolu", anomalies,
               "OK" if anomalies == 0 else "ALERTE")

    # Vérifier les six scénarios de calibration
    identifiants_st = calibration["scenario_stress"]
    doublons_st = int(identifiants_st.dropna().duplicated().sum())
    ajouter("Calibration", "scenarios_stress_dupliques", doublons_st,
           "OK" if doublons_st == 0 else "ALERTE")

    controles = pd.DataFrame(resultats)
    exporter_table(controles, "01_controles_qualite.csv")
    exporter_table(pd.DataFrame([
        {"jeu": nom, "colonne": col, "type_pandas": str(table[col].dtype),
         "valeurs_manquantes": int(table[col].isna().sum())}
        for nom, table in [("RW SCN", rw), ("Calibration", calibration),
                           ("Paramètres", parametres)]
        for col in table.columns
    ]), "01_types_colonnes.csv")
    return controles

# tests des contrôles
df_controles = controle_qualite(
    df_rw,
    df_calibration,
    df_parametres
)

# Afficher tous les résultats
display(df_controles)

# %% Les statistiques descriptives

# La fonction prend deux arguments :
# - serie : une colonne pandas contenant des valeurs numériques.
# - libelle : le nom que nous souhaitons donner à cette série dans les résultats.
# Elle renvoie un dictionnaire Python (dict) contenant les statistiques calculées.


def statistiques_serie(serie: pd.Series, libelle: str) -> dict:
    """Statistiques classiques ; variance/écart-type avec ddof=1.

    Skewness = coefficient d'asymétrie pandas.
    Kurtosis = excès de kurtosis (convention de Fisher : normale = 0).
    """
    x = pd.to_numeric(serie, errors="coerce").dropna().astype(float)
    if x.empty:
        raise ValueError(f"Aucune valeur numérique disponible pour {libelle}")
    return {
        "serie": libelle,
        "n": len(x),
        "moyenne": x.mean(),
        "mediane": x.median(),
        "variance_ddof1": x.var(ddof=1),
        "ecart_type_ddof1": x.std(ddof=1),
        "minimum": x.min(),
        "q01": x.quantile(0.01),
        "q05": x.quantile(0.05),
        "q25": x.quantile(0.25),
        "q75": x.quantile(0.75),
        "q95": x.quantile(0.95),
        "q99": x.quantile(0.99),
        "maximum": x.max(),
        "asymetrie_skew": x.skew(),
        "exces_kurtosis_fisher": x.kurt(),
        "pourcentage_negatif": 100 * (x < 0).mean(),
        "pourcentage_nul": 100 * (x == 0).mean(),
        "pourcentage_positif": 100 * (x > 0).mean(),
    }


def analyser_distributions(rw: pd.DataFrame) -> pd.DataFrame:
    """Statistiques des impacts avant et après et de leur différence."""
    avant = rw["impact_avant"]
    apres = rw["impact_apres"]
    diff = pd.to_numeric(apres, errors="coerce") - pd.to_numeric(avant, errors="coerce")

    tableau = pd.DataFrame([
        statistiques_serie(avant, "Avant réduction du bruit"),
        statistiques_serie(apres, "Après réduction du bruit"),
        statistiques_serie(diff, "Différence (après - avant)"),
        statistiques_serie(diff.abs(), "Différence absolue"),
    ])
    exporter_table(tableau, "02_statistiques_descriptives.csv")
    return tableau


# Test de la fonction statistiques_serie
resultat = statistiques_serie(
    df_rw["impact_apres"],
    "Impact après réduction du bruit"
)

df_resultat = pd.DataFrame([resultat])

display(df_resultat)


df_stats = analyser_distributions(df_rw)

df_comparaison = df_stats.set_index("serie").T

display(df_comparaison)

# %% Analyse des différences appariées

# La fonction analyser_differences() permet d'étudier comment la réduction du bruit modifie les impacts VA des 1 100 réalisations Monte Carlo.
def analyser_differences(rw: pd.DataFrame) -> pd.DataFrame:
    """Compare paire à paire les deux évaluations du même RW SCN.
    L'écart après-avant n'est PAS automatiquement le bruit réel ni une
    erreur de prédiction, faute de valeur de référence indépendante.
    """
    avant = pd.to_numeric(rw["impact_avant"], errors="coerce")
    apres = pd.to_numeric(rw["impact_apres"], errors="coerce")
    valides = avant.notna() & apres.notna()
    a, b = avant.loc[valides].astype(float), apres.loc[valides].astype(float)
    d = b - a
    if len(d) < 2:
        raise ValueError("Il faut au moins deux paires valides pour l'analyse.")

    indicateurs = {
        "nombre_paires_valides": len(d),
        "correction_moyenne_signee": d.mean(),
        "correction_mediane_signee": d.median(),
        "correction_absolue_moyenne": d.abs().mean(),
        "correction_absolue_mediane": d.abs().median(),
        "ecart_type_des_corrections": d.std(ddof=1),
        "maximum_correction_absolue": d.abs().max(),
        "pourcentage_corrections_positives": 100 * (d > 0).mean(),
        "pourcentage_corrections_negatives": 100 * (d < 0).mean(),
        "pourcentage_corrections_nulles": 100 * (d == 0).mean(),
        "pourcentage_changement_de_signe": 100 * ((a * b < 0)).mean(),
        "correlation_pearson_avant_apres": a.corr(b, method="pearson"),
        "correlation_spearman_avant_apres": a.corr(b, method="spearman"),
        "pourcentage_abs_correction_sup_100k": 100 * (d.abs() > 100_000).mean(),
        "pourcentage_abs_correction_sup_500k": 100 * (d.abs() > 500_000).mean(),
        "pourcentage_abs_correction_sup_1M": 100 * (d.abs() > 1_000_000).mean(),
    }
    tableau = pd.DataFrame({
        "indicateur": list(indicateurs),
        "valeur": list(indicateurs.values()),
    })
    exporter_table(tableau, "03_analyse_differences.csv")

    # Observations dont la valeur a le plus changé, utiles pour diagnostic.
    audit = rw.loc[valides, ["rw_scn", "impact_avant", "impact_apres"]].copy()
    audit["correction_signee"] = d
    audit["correction_absolue"] = d.abs()
    exporter_table(audit.nlargest(15, "correction_absolue"), "03_top15_corrections.csv")
    return tableau


# Test de la fonction analyser_differences

df_differences = analyser_differences(df_rw)

display(df_differences)

# %% Visualisations des résultats 
def visualiser(rw: pd.DataFrame) -> None:
    """Crée 5 graphiques en PNG, tous exprimés en millions d'unités."""
    donnees = rw.dropna(subset=["impact_avant", "impact_apres"]).copy()
    avant = donnees["impact_avant"].astype(float).to_numpy() / ECHELLE_GRAPHIQUES
    apres = donnees["impact_apres"].astype(float).to_numpy() / ECHELLE_GRAPHIQUES
    ecart = apres - avant

    # Mêmes bornes / mêmes classes : comparaison des histogrammes honnête.
    bins = np.histogram_bin_edges(np.concatenate([avant, apres]), bins=45)
    fig, axes = plt.subplots(2, 1, figsize=(10, 9), sharex=True, sharey=True)
    fig.suptitle("Distribution des impacts VA — avant / après", fontweight="semibold")
    for ax, valeurs, cle, titre in [
        (axes[0], avant, "avant", "Avant réduction"),
        (axes[1], apres, "apres", "Après réduction"),
    ]:
        ax.hist(valeurs, bins=bins, color=COULEURS[cle], alpha=0.8,
                edgecolor="white", linewidth=0.4)
        ax.axvline(np.mean(valeurs), color="#111827", linestyle="--",
                   linewidth=1.5, label="Moyenne")
        ax.set(title=titre, ylabel="Nombre de réalisations")
        ax.legend(frameon=False)
    axes[1].set_xlabel(UNITES_AXE)
    sauvegarder_figure("01_histogrammes_avant_apres.png")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    bp = ax.boxplot([avant, apres], tick_labels=["Avant réduction", "Après réduction"],
                    vert=False, patch_artist=True, widths=0.5,
                    medianprops={"color": "#111827", "linewidth": 2},
                    flierprops={"marker": ".", "markersize": 3, "alpha": 0.45})
    for patch, couleur in zip(bp["boxes"], [COULEURS["avant"], COULEURS["apres"]]):
        patch.set_facecolor(couleur)
        patch.set_alpha(0.55)
    ax.set(title="Dispersion et valeurs atypiques des impacts VA", xlabel=UNITES_AXE)
    sauvegarder_figure("02_boxplots_avant_apres.png")

    fig, ax = plt.subplots(figsize=(7.6, 7.1))
    ax.scatter(avant, apres, s=22, alpha=0.55, color=COULEURS["avant"],
               edgecolors="none")
    bornes = [min(np.min(avant), np.min(apres)), max(np.max(avant), np.max(apres))]
    marge = max((bornes[1]-bornes[0]) * 0.035, 0.1)
    bornes = [bornes[0]-marge, bornes[1]+marge]
    ax.plot(bornes, bornes, color="#334155", linestyle="--", linewidth=1.5,
            label="Identité : après = avant")
    ax.set_xlim(bornes)
    ax.set_ylim(bornes)
    ax.set_aspect("equal", adjustable="box")
    ax.set(title="Comparaison appariée des 1 100 réalisations",
           xlabel="Impact avant (millions d'unités)",
           ylabel="Impact après (millions d'unités)")
    ax.legend(frameon=False, loc="upper left")
    sauvegarder_figure("03_scatter_avant_apres.png")

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.hist(ecart, bins=55, color=COULEURS["ecart"], alpha=0.85,
            edgecolor="white", linewidth=0.4)
    ax.axvline(0, color="#334155", linestyle="--", label="Aucune correction")
    ax.axvline(np.mean(ecart), color="#7C2D12", linestyle="-",
               label=f"Moyenne : {np.mean(ecart):.3f} M")
    ax.set(title="Distribution des corrections : après − avant",
           xlabel="Correction (millions d'unités)", ylabel="Nombre de réalisations")
    ax.legend(frameon=False)
    sauvegarder_figure("04_histogramme_corrections.png")

    # Bland-Altman :
    x_moyen = (avant + apres) / 2
    moyenne_ecart, sd_ecart = ecart.mean(), ecart.std(ddof=1)
    fig, ax = plt.subplots(figsize=(9.5, 5.3))
    ax.scatter(x_moyen, ecart, s=21, color=COULEURS["ecart"], alpha=0.58,
               edgecolors="none")
    ax.axhline(0, color="#64748B", linewidth=1, linestyle=":")
    ax.axhline(moyenne_ecart, color="#1D4ED8", linewidth=1.5,
               label="Correction moyenne")
    for signe in (-1, 1):
        ax.axhline(moyenne_ecart + signe * 1.96 * sd_ecart, color="#475569",
                   linewidth=1.25, linestyle="--")
    ax.set(title="Différence en fonction de l'impact moyen (Bland–Altman)",
           xlabel="Moyenne des deux impacts (millions d'unités)",
           ylabel="Après − avant (millions d'unités)")
    ax.legend(frameon=False)
    fig.text(0.11, 0.005,
             "Lignes ±1,96 écart-type : repères descriptifs, pas validation du débruitage.",
             fontsize=8, color="#475569")
    sauvegarder_figure("05_bland_altman_corrections.png")


# %% --- Point d'entrée principal ---
def main() -> None:
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    DOSSIER_FIGURES.mkdir(parents=True, exist_ok=True)

    print("\n=== 1. CONTRÔLES QUALITÉ ===")
    controles = controle_qualite(df_rw, df_calibration, df_parametres)
    alertes = controles[controles["statut"] == "ALERTE"]
    print(f"RW SCN : {df_rw.shape[0]} lignes × {df_rw.shape[1]} colonnes")
    print(f"Calibration : {df_calibration.shape[0]} lignes")
    print(f"Paramètres : {df_parametres.shape[0]} lignes")
    print(f"Alertes : {len(alertes)}")
    if not alertes.empty:
        print(alertes[["jeu", "controle", "valeur"]].to_string(index=False))
        warnings.warn("Des anomalies ont été détectées : voir 01_controles_qualite.csv")

    if df_rw["rw_scn"].duplicated().any():
        raise ValueError("Identifiants RW SCN dupliqués : corriger avant l'analyse appariée.")

    print("\n=== 2. STATISTIQUES DESCRIPTIVES ===")
    statistiques = analyser_distributions(df_rw)
    print(statistiques[["serie", "n", "moyenne", "mediane", "ecart_type_ddof1",
                        "asymetrie_skew", "exces_kurtosis_fisher"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    print("\n=== 3. ANALYSE DES CORRECTIONS ===")
    differences = analyser_differences(df_rw)
    print(differences.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    print("\n=== 4. GRAPHIQUES ===")
    visualiser(df_rw)
    for chemin in sorted(DOSSIER_FIGURES.glob("*.png")):
        print("  ", chemin.name)

    print(f"\nTerminé : fichiers disponibles dans {DOSSIER_SORTIE}")
    print("Le fichier Excel d'origine n'a pas été modifié.")


if __name__ == "__main__":
    main()
