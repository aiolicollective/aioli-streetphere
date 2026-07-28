# Credits, sources et avertissement

`aioli-streetphere` est developpe par le collectif [ai.oli](https://aiolicollective.com)
(Marseille). Notre code est sous licence MIT : voir [LICENSE](LICENSE).

Cet outil ne serait pas possible sans le travail ci-dessous. Rien de tout cela
n'est redistribue dans ce depot : tout est telecharge a l'execution, depuis la
source d'origine.

---

## Avertissement

**Ce projet n'est ni affilie a Google, ni approuve ou sponsorise par Google.**
Google, Google Maps, Street View et Google Earth sont des marques de Google LLC.

- Les images et les modeles 3D obtenus restent la **propriete de Google et de ses
  fournisseurs de donnees**. Ce depot ne contient ni ne redistribue aucune donnee
  Google.
- L'outil s'adresse a un **usage personnel, pedagogique ou de recherche**
  (etude de faisabilite, references de travail, previsualisation).
  Il ne donne aucun droit d'exploitation commerciale des donnees recuperees.
- Le module 3D repose sur un **protocole non documente et non officiel**. Il peut
  cesser de fonctionner du jour au lendemain, et son usage peut etre contraire aux
  conditions d'utilisation des services Google.
- **C'est a chaque utilisateur de verifier ce que sa juridiction et les conditions
  d'utilisation applicables lui permettent de faire.** Le logiciel est fourni sans
  garantie (voir LICENSE) : les auteurs ne sauraient etre tenus responsables de
  l'usage qui en est fait.

Si vous avez besoin de donnees 3D geospatiales pour un usage commercial, la voie
officielle et sous licence existe : l'API Google Photorealistic 3D Tiles
(compte Google Cloud requis).

---

## Code tiers

| Projet | Role | Licence | Comment |
|---|---|---|---|
| [earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering) (retroplasma) | Reverse du protocole Google Earth et exporteur de mesh : c'est le coeur du module 3D | **Aucune licence declaree** par l'auteur (donc tous droits reserves) | Clone automatiquement dans `earth3d_vendor/` au premier lancement. Jamais copie ni redistribue ici. |
| [three.js](https://threejs.org) | Rendu du viewer 360 (`builder.html`) | MIT | Charge depuis un CDN au premier lancement du viewer |
| [requests](https://requests.readthedocs.io) | Requetes HTTP | Apache-2.0 | Installe par `setup.bat` dans le venv local |
| [Pillow](https://python-pillow.org) | Assemblage des tuiles, conversion des textures | MIT-CMU / HPND | Installe par `setup.bat` dans le venv local |
| [NumPy](https://numpy.org) | Reechantillonnage spherique (redressement d'horizon) | BSD-3-Clause | Installe par `setup.bat` dans le venv local |

Mention particuliere a **retroplasma** : sans son travail de reverse, le module 3D
n'existerait pas. Comme son depot ne declare pas de licence, nous ne le
redistribuons pas et nous n'en derivons pas de code — nous le clonons a
l'execution et nous l'appelons tel quel. Si vous reutilisez notre code, gardez
ce fonctionnement.

## Sources de donnees

| Source | Usage |
|---|---|
| Google Street View (`cbk0.google.com`, `lh3.googleusercontent.com`, endpoint `photometa`) | Tuiles de panorama et pose (heading / pitch / roll) |
| Google Earth (`kh.google.com/rt/...`) | Mesh 3D et textures, via le protocole non officiel ci-dessus |

Aucune cle API, aucun compte, aucun contournement de paiement : l'outil utilise
les memes points d'acces publics que le navigateur lorsqu'on consulte Google Maps.

---

## Le collectif

- Site : [aiolicollective.com](https://aiolicollective.com)
- Instagram : [@aioli.collective](https://instagram.com/aioli.collective)
- GitHub : [github.com/aiolicollective](https://github.com/aiolicollective)

Outil developpe par victor.oli avec ai.claude. On dit ce qui est genere et par qui.
