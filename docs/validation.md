# Vérifications du modèle — 19 novembre 2026

- Windows, Python 3.12.14, environnement virtuel neuf : installation de
  `requirements.txt` et du package éditable réussie.
- `manage.py download`, puis `manage.py run` : 5 valeurs, moyenne 3,
  minimum 1, maximum 5 ; SHA-256 de l'entrée présent dans le JSON.
- `manage.py test` : **8 tests réussis**.
- `pip check` : aucune incompatibilité de dépendances détectée.
- Copie propre initialisée en dépôt Git temporaire : audit de l'index réussi,
  règles `.gitignore` vérifiées pour données, résultats et `.env` ; conservation
  des `.gitkeep` et de `.env.example` vérifiée.
- Vérification négative de l'audit : un faux jeton ajouté à l'index reste détecté
  même après remplacement de son contenu dans le fichier de travail.
- YAML Conda analysé ; notebook sans sorties enregistrées ; intégrité ZIP contrôlée.

La première installation a rencontré une incompatibilité setuptools avec les
accolades dans le chemin temporaire du bac à sable de validation. La relance avec
TEMP/TMP dirigés vers un dossier temporaire ordinaire a réussi, sans modification
du projet ni des credentials. Ce réglage n'est pas requis par le modèle.

Pas d'exécution réelle sur Colab, ENSMA, Kaggle ou Azure. WSL était inaccessible
depuis la session de validation. L'environnement Conda n'a pas été créé ; son
fichier est fourni, mais la résolution Conda reste à vérifier sur le poste cible.
Le téléchargement HTTPS est testé avec une réponse simulée et un contrôle de
hash ; aucun dataset tiers réel n'a été téléchargé.

L'audit de secrets est heuristique et ne couvre pas l'historique Git. Aucun vrai
`.env`, credential ou token n'est fourni. Aucun service cloud n'a été créé.
