# earth3d — Google Earth 3D → OBJ à l'échelle (v2, expérimental)

Télécharge le mesh 3D texturé de l'environnement dans un **rayon en mètres**
autour d'un point (données Google Earth) et le recentre à l'échelle métrique,
prêt pour Blender / 3ds Max. Sans compte, sans clé API, sans CB — même
philosophie que streetphere.

## Comment ça marche

1. Tu colles une URL Google Maps (ou `lat, lng`). Le script en extrait la position.
2. Tu donnes un rayon en mètres (défaut 150 m, max 3000 m).
3. Le script interroge le protocole non officiel de Google Earth
   (`kh.google.com/rt/…`, reversé par
   [earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering),
   cloné automatiquement dans `earth3d_vendor/` au premier lancement) et
   sélectionne les octants — cellules de l'octree 3D — qui couvrent le disque
   demandé (`earth3d_radius.js`).
4. Il télécharge mesh + textures → `model.obj` (coordonnées géocentriques brutes).
5. Post-traitement Python :
   - **échelle auto-détectée** (la norme moyenne des vertices est comparée au
     rayon terrestre : si le dump est en unités normalisées, il est remis en mètres),
   - recentrage sur le point demandé, sol calé vers 0,
   - axes locaux (est / nord / altitude), convention OBJ Y-up standard,
   - `model_local.mtl` nettoyé pour l'importeur OBJ de 3ds Max,
   - diagnostics affichés : dimensions de la zone en m, distance à l'origine.

Le rayon est **respecté** : les faces hors du disque demandé sont retirées
(recadrage au post-traitement, marge ~15 m).

Sortie : `output/3d/<lat>_<lng>_r<N>m_d<D>/model_local.obj` + `.mtl` + textures.
(Les sphères 360 vont dans `output/spheres/` — sorties harmonisées.)

## Utilisation

```bat
run.bat        (choix 2, ou choix 3 pour sphère + 3D d'un coup)
earth3d.bat    (accès direct)
```

Prérequis : Node.js + Git dans le PATH. Python est détecté automatiquement
(venv → lanceur `py` → PATH → chemins courants → saisie manuelle).
Premier lancement : clone + `npm install` automatiques (~1 min).

## Isolation

Rien ne s'installe hors du dossier du repo : Python = stdlib uniquement (le venv
de `setup.bat` est utilisé s'il existe), dépendances Node locales à
`earth3d_vendor/node_modules/`, rien en global.

## Import

- **Blender** : File > Import > Wavefront (.obj) → `model_local.obj`. 1 unité = 1 m.
- **3ds Max** : Import OBJ → `model_local.obj`, cocher « Import materials ».
  Fichier en mètres : si les unités système sont en cm, régler l'option d'unités
  de l'importeur (ou scale ×100).
  **Viewport noir malgré les bitmaps ?** C'est « Show Shaded Material in
  Viewport » désactivé sur les matériaux importés : lancer `max_show_textures.ms`
  (Scripting > Run Script...) qui l'active partout d'un coup.

## Limites connues (v2)

- Protocole non officiel : peut casser sans préavis côté Google.
- Le téléchargement se fait par cellules entières puis la géométrie est
  recadrée au rayon : le volume téléchargé peut dépasser ce qui est gardé.
- LOD : le détail max dépend de la couverture 3D de la ville.
- Le sol est calé sur le point le plus bas du mesh (approximation).

## Légal

Données propriété de Google. Prévisualisation et usage interne uniquement,
pas d'exploitation commerciale directe des assets extraits.
