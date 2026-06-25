# Dioui

> **Di**nan dit **OUI** à l'automatisation.

Application desktop de génération de PDF d'attestations pour le programme **Missions Argent de Poche** de l'[Atelier du 5 bis](https://www.atelierfivebis.com/) (Dinan).

---

## Contexte

L'Atelier du 5 bis propose des missions rémunérées à des jeunes dans le cadre du dispositif *Argent de Poche*. Chaque mission donne lieu à une attestation PDF A5 (deux exemplaires sur une feuille A4 paysage) que le jeune doit rapporter signée pour être indemnisé.

Avant Dioui, ces attestations étaient remplies à la main ou générées une par une. Dioui lit le tableau de suivi Excel et génère en un clic les PDFs pour toutes les missions sélectionnées.

---

## Fonctionnalités

- **Chargement du fichier Excel** de suivi des missions (nommé `YYYY-suivi-missions-argent-de-poche.xlsx`)
- **Sélection de la saison** : Hiver, Printemps, Été, Automne
- **Checklist interactive** : toutes les missions de la saison s'affichent avec une case à cocher
- **Génération sélective** : seules les missions cochées sont traitées
- **PDF A4 paysage** avec deux exemplaires A5 côte à côte (participant + encadrant)
- **Marquage automatique** : la colonne `pdf` du tableau passe à `TRUE` après chaque génération réussie
- **Barre de progression** avec compteur en temps réel
- **Ouverture du dossier output** en un clic après génération
- Interface **dark mode** (CustomTkinter)

---

## Structure du fichier Excel

Le fichier doit être nommé `YYYY-suivi-missions-argent-de-poche.xlsx` (ex : `2026-suivi-missions-argent-de-poche.xlsx`).

Il doit contenir **4 feuilles**, une par saison :

| Nom de la feuille     |
|-----------------------|
| `missions_hiver`      |
| `missions_printemps`  |
| `missions_ete`        |
| `missions_automne`    |

Chaque feuille doit avoir ces colonnes en **ligne 1** (l'ordre n'a pas d'importance) :

| Colonne       | Type      | Description                                      | Exemple                          |
|---------------|-----------|--------------------------------------------------|----------------------------------|
| `pdf`         | Booléen   | Coché automatiquement après génération du PDF    | `TRUE` / `FALSE`                 |
| `date`        | Date      | Date de la mission                               | `14/03/2026`                     |
| `h_debut`     | Texte     | Heure de début                                   | `9h00`                           |
| `h_fin`       | Texte     | Heure de fin                                     | `12h00`                          |
| `description` | Texte     | Description de la mission (obligatoire)          | `Ramassage des déchets au port`  |
| `lieu_rdv`    | Texte     | Lieu de rendez-vous                              | `Parking de la Tour de l'Horloge`|
| `referent`    | Texte     | Nom du référent                                  | `Marie Dupont`                   |
| `contact`     | Texte     | Téléphone ou email du référent                   | `06.12.34.56.78`                 |

> Un fichier d'exemple avec les en-têtes pré-remplies est disponible dans le dossier [`example/`](example/).

Les lignes sans `h_debut`, `h_fin` ou `description` sont automatiquement ignorées.

---

## PDFs générés

Les fichiers sont exportés dans `output/` à la racine du dossier de l'application, nommés :

```
YYYY-MM-DD_HHhMM-HHhMM_lieu-rdv.pdf
```

---

## Stack technique

| Composant      | Technologie                        |
|----------------|------------------------------------|
| Interface      | Python · CustomTkinter 6.0         |
| Lecture Excel  | pandas · openpyxl                  |
| Génération PDF | ReportLab                          |
| Images         | Pillow                             |
| Build          | PyInstaller (onefile)              |
| CI/CD          | GitHub Actions                     |

---

## Installation (développement)

```bash
# Cloner le repo
git clone https://github.com/Boutzi/dioui.git
cd dioui

# Créer l'environnement virtuel
python -m venv venv

# Activer (Windows)
venv\Scripts\activate

# Activer (Linux/macOS)
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python src/app.py
```

> Dans VS Code : `Ctrl+Shift+P` → *Python: Select Interpreter* → choisir l'interpréteur `venv`.

---

## Build

Le build est automatisé via GitHub Actions à chaque push sur `main`.  
Les binaires sont publiés dans les [Releases](https://github.com/Boutzi/dioui/releases) du repo.

| Plateforme     | Fichier         |
|----------------|-----------------|
| Windows        | `Dioui.exe`     |
| Linux (Ubuntu) | `Dioui-linux`   |

Pour builder manuellement :

```bash
pyinstaller dioui.spec --noconfirm
# → dist/Dioui.exe (Windows) ou dist/Dioui (Linux)
```

### Changer la version

Modifier le champ `version` dans [`package.json`](package.json), puis pusher. GitHub Actions crée automatiquement une nouvelle Release taguée.

---

## Architecture du projet

```
dioui/
├── src/
│   ├── app.py              # Application principale (UI + logique)
│   └── assets/
│       ├── logo-white.png  # Logo Dinan (blanc, pour le PDF)
│       ├── logo.png        # Logo Dinan (couleur, icône app)
│       └── caf.png         # Logo CAF (pied de page PDF)
├── example/
│   └── suivi-missions-exemple.xlsx  # Fichier Excel vide avec en-têtes
├── output/                 # PDFs générés (créé automatiquement, ignoré par git)
├── .github/
│   └── workflows/
│       └── build.yml       # CI/CD GitHub Actions
├── dioui.spec              # Configuration PyInstaller
├── package.json            # Nom et version de l'application
└── requirements.txt        # Dépendances Python
```

---

## Auteur

Développé pour l'**Atelier du 5 bis** — Dinan (22).
