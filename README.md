# Modèle de projet scientifique Python portable

Petit pipeline CPU, sans compte cloud ni secret : un CSV de démonstration contient
les valeurs 1 à 5, puis le pipeline écrit une moyenne de 3 dans `outputs/summary.json`.
Python **3.10 minimum**, 3.11 conseillé. Git sert à cloner/versionner ; pip et un
accès réseau sont nécessaires à l'installation initiale. Aucun GPU nécessaire.

## Démarrage Windows / WSL / Linux

Après avoir extrait ce modèle et publié votre propre dépôt, ou après un clonage :

```text
git clone <URL_DE_VOTRE_DEPOT>
cd <NOM_DU_DEPOT>
python manage.py setup
python manage.py download
python manage.py run
python manage.py test
```

Sur Windows, remplacer `python` par `py -3.11` si nécessaire. Sur WSL/Linux,
utiliser `python3` si `python` n'existe pas. `setup` crée `.venv`, installe le
projet en mode éditable et les dépendances. Les autres commandes utilisent
automatiquement ce même environnement : aucune activation PowerShell requise.
Ne partagez pas `.venv` entre Windows et WSL : créez un clone et un environnement
dans chaque système. Si `venv` est indisponible, utiliser Conda ou demander
l'installation du composant Python correspondant à l'administrateur.

`download` refuse d'écraser un fichier existant ; `python manage.py download --force`
le remplace explicitement. `run` remplace le résumé précédent.

## Conda (alternative)

Depuis la racine du dépôt :

```text
conda env create -f environment.yml
conda activate scientific-project
python manage.py download --current
python manage.py run --current
python manage.py test --current
```

`--current` force l'interpréteur actif, même si une ancienne `.venv` existe.
Le YAML Conda réutilise `requirements.txt` : PyYAML est la seule dépendance
d'exécution et pytest la seule dépendance de test. Le backend d'installation est
setuptools. Pas de NumPy, pandas, Jupyter, SDK cloud ou dotenv imposé.
Les versions sont bornées, pas verrouillées : pour une publication scientifique,
archiver aussi la version Python, le commit, la config, les sommes des données
et `python -m pip freeze` depuis l'environnement effectivement utilisé.

## Google Colab

Dans un notebook Colab vierge, remplacer l'URL et le nom du dossier :

```python
!git clone https://github.com/VOTRE_COMPTE/VOTRE_DEPOT.git
%cd /content/VOTRE_DEPOT
%pip install -r requirements.txt
!python manage.py download --current
!python manage.py run --current
!python manage.py test --current
```

Le notebook `notebooks/01_demo.ipynb` montre ensuite les imports du package.
Ne pas stocker de token dans les cellules ni dans l'URL Git. Les commandes de
clonage ci-dessus supposent un dépôt public ; gérer un dépôt privé séparément
avec les mécanismes d'authentification de la plateforme.

Le disque de la VM Colab est temporaire. Télécharger le résultat avant de
quitter la session :

```python
from google.colab import files
files.download("outputs/summary.json")
```

Ou monter Drive explicitement et définir les chemins **avant** le pipeline :

```python
from google.colab import drive
import os
drive.mount("/content/drive")
os.environ["SCI_DATA_DIR"] = "/content/drive/MyDrive/scientific-project/data"
os.environ["SCI_OUTPUT_DIR"] = "/content/drive/MyDrive/scientific-project/outputs"
```

Cette option demande l'autorisation Drive interactive de Colab et n'est pas
nécessaire au démarrage. Le modèle ne monte aucun stockage automatiquement.

## ENSMA

Suivre [docs/ensma_setup.md](docs/ensma_setup.md) : installation dans un espace
utilisateur, sans `sudo`, avec une alternative Conda et une préparation hors ligne.
Aucun serveur, proxy, chemin réseau ou quota ENSMA n'est supposé connu.

## Organisation

```text
src/scientific_project/  logique réutilisable, configuration et chemins
notebooks/              exploration ; retirer les sorties avant commit
scripts/                entrées CLI, téléchargement et audit de secrets
configs/                configurations YAML sans informations sensibles
tests/                  tests hors ligne avec répertoires temporaires
data/raw/               données sources, jamais modifiées par le pipeline
data/interim/           transformations intermédiaires (réservé)
data/processed/         données prêtes à analyser (réservé)
outputs/                résultats régénérables
docs/                   procédures et conventions
```

## Chemins et configuration

`pathlib` ancre les chemins relatifs à la racine du clone, indépendamment du dossier
courant. Installation éditable requise ; ce modèle est conçu pour être exécuté
depuis un clone, pas distribué comme une wheel autonome. Les noms de fichiers
d'entrée/sortie doivent rester dans leur répertoire configuré.

Priorité : variables `SCI_DATA_DIR` / `SCI_OUTPUT_DIR`, puis YAML, puis valeurs par
défaut. `.env.example` documente ces variables ; aucun `.env` n'est créé ou chargé.

PowerShell : `$env:SCI_DATA_DIR = 'D:/datasets/mon-projet'`.
Bash : `export SCI_DATA_DIR="$HOME/datasets/mon-projet"`.
Notebook : `os.environ["SCI_DATA_DIR"] = "/chemin/data"`.

```text
python manage.py download --config configs/default.yaml
python manage.py run --config configs/default.yaml
```

Les scripts sont aussi exécutables directement avec le Python de l'environnement :
`python scripts/run_pipeline.py --config configs/default.yaml`.
Pour des données publiques, renseigner `download.url` (HTTPS sans identifiants
ni paramètres de requête), `download.sha256` (obligatoire) et `download.filename`.
Adapter `pipeline.input` au même nom. L'exemple attend un CSV avec une colonne
numérique `value` ; adapter le lecteur pour vos vrais jeux de données.
Le téléchargement utilise des blocs de 1 Mio et vérifie le hash avant de remplacer
le fichier final. Le pipeline de démonstration charge le CSV en mémoire : il ne
prétend pas traiter de gros datasets. Aucun téléchargement réseau n'est fait par défaut.

## Git et secrets

Les données, résultats, environnements et principaux formats volumineux sont
ignorés ; seuls les `.gitkeep` préservent les dossiers. Les CSV stockés ailleurs
que dans `data/` restent versionnables : ranger les datasets dans `data/` ou hors
du dépôt. Git n'est pas un stockage de gros datasets ; documenter leur provenance,
licence et SHA-256. Retirer les sorties des notebooks avant de les versionner.

Pour transformer le dossier extrait en dépôt (aucun commit automatique) :

```text
git init
git add .
python manage.py check-secrets
git diff --cached --stat
git commit -m "Initial scientific project template"
```

Répéter l'audit après `git add` avant chaque commit. Il examine le contenu de
l'index Git, y compris les fichiers déjà suivis malgré `.gitignore`. Un code de
sortie non nul signale un problème. Sans dépôt :
`python manage.py check-secrets --source-tree` inspecte les sources distribuables.
L'audit reconnaît des formats courants et des fichiers sensibles ; c'est une
heuristique, pas une garantie, et il n'inspecte pas l'historique Git. Un secret
déjà commité doit être révoqué auprès du fournisseur et l'historique traité
séparément. Le modèle ne modifie aucun credential.

## Kaggle / Azure ultérieurement

Les mêmes commandes pip fonctionnent dans un environnement Python compatible
où l'installation est autorisée. Configurer les chemins absolus des volumes
montés via les deux variables ; utiliser un dossier de sorties accessible en
écriture. Un dataset monté en lecture seule doit déjà contenir `raw/example.csv`
(ou adapter le code/configuration à son organisation) : ne pas lancer `download`
sur ce volume. Aucune ressource, souscription, API ou instance cloud n'est créée.
Ces plateformes ne sont pas validées par ce modèle initial.

## Références

- [Environnements Conda](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html)
- [FAQ Colab : durée de vie des VM et stockage](https://research.google.com/colaboratory/faq.html)
