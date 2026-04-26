# aioli-streetphere

Telecharge un panorama Google Street View et l'exporte comme image equirectangulaire 2:1,
prete a utiliser comme sphere d'environnement dans V-Ray, 3ds Max, Blender, Cinema 4D, etc.

Deux modes detectes automatiquement :

- Street View officiel : assemblage de tuiles via l'API Google (jusqu'a 13 312 x 6 656 px)
- Photo sphere utilisateur : telechargement direct depuis le CDN Google

---

## Prerequis

Python 3.8+ doit etre installe sur votre machine.

Si vous n'avez pas Python :
1. Allez sur https://www.python.org/downloads/
2. Telechargez la derniere version (ex : Python 3.12)
3. Lancez l'installeur et cochez "Add Python to PATH" (important !)

---

## Installation

1. Telechargez le projet : https://github.com/aiolicollective/aioli-streetphere/archive/refs/heads/main.zip
2. Dezippez-le ou vous voulez
3. Ouvrez le dossier dezzippe
4. Double-cliquez sur setup.bat

setup.bat fait tout seul :
- Detecte Python sur votre machine
- Cree un environnement virtuel (venv) isole dans le dossier
- Installe les dependances (requests et Pillow)
- Lance le script

Qu'est-ce qu'un environnement virtuel (venv) ?
Un dossier venv sera cree dans le dossier du projet. Il contient une copie locale de Python
et les librairies necessaires. Cela ne touche absolument pas au reste de votre systeme.
En l'effacant, tout revient comme avant.

---

## Utilisation

1. Ouvrez Google Maps dans votre navigateur
2. Passez en mode Street View sur un endroit qui vous plait
3. Copiez l'URL complete dans la barre d'adresse
4. Double-cliquez sur run.bat (ou setup.bat la premiere fois)
5. Collez l'URL quand le programme le demande et appuyez Entree
6. Choisissez le niveau de resolution (Entree = zoom 4 par defaut)

Le fichier panorama_[ID]_z[zoom].jpg sera cree dans le dossier.

Le programme reste ouvert apres chaque telechargement : collez une nouvelle URL directement
pour en telecharger une autre. Pour quitter, tapez Q puis Entree.

---

## Resolution : le parametre ZOOM

Street View ne livre pas le panorama en une seule image : il est decoupe en tuiles de
512x512 px que le script telecharge et assemble. Le zoom determine combien de tuiles
sont demandees, donc la taille de l'image finale.

| ZOOM | Resolution          | Nb de tuiles | Usage                        |
|------|---------------------|--------------|------------------------------|
| 3    | 4 096 x 2 048 px    | 32           | Apercu rapide                |
| 4    | 8 192 x 4 096 px    | 128          | Recommande (V-Ray, Blender)  |
| 5    | 13 312 x 6 656 px   | 338          | Haute resolution             |

Le zoom 4 est le maximum fiable : toutes les tuiles sont disponibles, image seamless garantie.

Le zoom 5 produit une image plus grande mais Google ne fournit pas toujours toutes les tuiles
a ce niveau -- les zones extremes (ciel/sol) peuvent retourner des erreurs et rester noires
dans l'image finale. L'image garde son ratio 2:1 et reste utilisable, mais la sphere peut
presenter des artefacts aux poles. Le programme affiche un avertissement si zoom 5 est choisi.

Note : ce parametre ne s'applique qu'au Street View officiel. Pour les photos spheres
utilisateur, la resolution est celle d'origine de la photo.

---

## Risques et limites

- Usage personnel seulement : les images Street View sont propriete de Google.
  Ne pas exploiter les resultats commercialement.
- Connexion Internet requise : le script accede aux serveurs Google.
- Street View uniquement : les liens de cartes normales ou satellite ne fonctionnent pas.
- Pas de cle API requise : cet outil utilise les memes CDNs que le navigateur.
  Aucun compte Google n'est necessaire.

---

## Structure des fichiers

    .
    +-- streetview.py             Script principal
    +-- requirements.txt          Librairies Python (requests, Pillow)
    +-- setup.bat                 Installation + 1er lancement
    +-- run.bat                   Lancement seul (fois suivantes)
    +-- venv/                     Cree au 1er lancement, ne pas modifier
    +-- tiles/                    Tuiles telechargees (intermediaires)
    +-- panorama_[ID]_z[zoom].jpg Resultat final (Street View officiel)
    +-- panorama_[ID].jpg         Resultat final (photo sphere utilisateur)

---

ai.claude pour aiolicollective - 2026
