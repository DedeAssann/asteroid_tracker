# Installation sur un poste ENSMA

Procédure générique : le système d'exploitation, les logiciels autorisés,
l'accès réseau, les quotas et la persistance des dossiers doivent être vérifiés
sur le poste concerné ou auprès du service informatique. Aucun droit administrateur
n'est requis par le projet ; l'installation de Python peut en revanche dépendre
de la politique locale.

1. Choisir un dossier personnel autorisé, persistant, accessible en écriture.
   Vérifier le quota avant d'y copier des données. Éviter les dossiers partagés
   accessibles aux autres utilisateurs pour des données confidentielles.
2. Vérifier `python --version` (ou `python3 --version` / `py -3.11 --version`) :
   Python 3.10 minimum. Vérifier `git --version`. Si Git manque, extraire l'archive.
3. Cloner le dépôt puis se placer à sa racine. Ne pas copier un `.venv` Windows
   vers Linux ou depuis une autre installation Python.
4. Exécuter, en adaptant le nom de l'interpréteur :

```text
python manage.py setup
python manage.py download
python manage.py test
python manage.py run
```

Les résultats apparaissent dans `outputs/summary.json`. L'installation pip a
besoin du réseau ; le téléchargement de démonstration, les tests et le pipeline
sont ensuite hors ligne. Si `venv` est indisponible mais Conda déjà autorisé :

```text
conda env create -f environment.yml
conda activate scientific-project
python manage.py download --current
python manage.py test --current
python manage.py run --current
```

Ne pas installer globalement, ne pas utiliser `sudo pip`, ne pas désactiver TLS
pour contourner un proxy. Utiliser le dépôt de paquets et les certificats fournis
par le service informatique si nécessaire, sans publier de mot de passe.

## Réseau indisponible

Sur une machine connectée de même OS, architecture et version Python que le poste
cible, préparer un dossier de wheels avec les dépendances d'installation :

```text
python -m pip download --only-binary=:all: --dest wheelhouse "setuptools>=68" wheel "PyYAML>=6.0.1,<7" "pytest>=8,<9"
```

Transférer le projet et `wheelhouse` par un moyen autorisé. Dans PowerShell :

```powershell
$env:PIP_NO_INDEX = '1'
$env:PIP_FIND_LINKS = (Resolve-Path wheelhouse).Path
python manage.py setup
Remove-Item Env:PIP_NO_INDEX
Remove-Item Env:PIP_FIND_LINKS
```

Sous Bash, depuis la racine du projet :

```bash
PIP_NO_INDEX=1 PIP_FIND_LINKS="$PWD/wheelhouse" python3 manage.py setup
```

Placer `wheelhouse` hors du dépôt ou ajouter `/wheelhouse/` à `.gitignore`.
Les wheels ne sont pas universellement portables ; tester la préparation sur
un environnement correspondant au poste cible. Le projet n'en fournit aucune.

## Données et sauvegarde

Configurer `SCI_DATA_DIR` et `SCI_OUTPUT_DIR` pour les volumes disponibles,
comme expliqué dans le README. Utiliser un espace temporaire autorisé pour les
intermédiaires volumineux et sauvegarder les résultats avant déconnexion si le
poste efface cet espace. Ne pas supposer qu'un disque local est sauvegardé.
Ne pas transférer de données ENSMA vers un cloud sans autorisation appropriée.
