# earth3d — Google Earth 3D → OBJ à l'échelle (v0, expérimental)

Télécharge le mesh 3D texturé de l'environnement autour d'un point (données
Google Earth) et le recentre à l'échelle métrique, prêt pour Blender / 3ds Max.
Sans compte, sans clé API, sans CB — même philosophie que streetphere.

## Comment ça marche

1. Tu colles une URL Google Maps (ou `lat, lng`). Le script en extrait la position.
2. Il interroge le protocole non officiel de Google Earth (`kh.google.com/rt/…`,
   reversé par [earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering),
   cloné automatiquement dans `earth3d_vendor/` au premier lancement) pour
   trouver les octants — les cellules de l'octree 3D qui contiennent le point.
3. Tu choisis la taille de zone (niveau d'octant : plus profond = plus petit)
   et le niveau de détail (20 = max).
4. Il télécharge mesh + textures → `model.obj` (coordonnées géocentriques brutes).
5. Post-traitement Python : recentrage sur le point demandé, sol calé vers 0,
   axes locaux (est / nord / altitude), unités = mètres, convention OBJ Y-up
   standard → `model_local.obj`.

Sortie : `earth3d_out/<lat>_<lng>_lvl<N>_d<D>/model_local.obj` + textures.

## Isolation

Rien ne s'installe hors du dossier du repo : Python = stdlib uniquement (le venv
de `setup.bat` est utilisé s'il existe), dépendances Node locales à
`earth3d_vendor/node_modules/`, rien en global.

## Utilisation

```bat
earth3d.bat
```

Prérequis : Node.js + Git dans le PATH. Python est détecté automatiquement
(venv → lanceur `py` → PATH → chemins courants → saisie manuelle).
Premier lancement : clone + `npm install` automatiques (~1 min).

## Import

- **Blender** : File > Import > Wavefront (.obj) → `model_local.obj`. 1 unité = 1 m.
- **3ds Max** : import OBJ, régler les unités (fichier en mètres ; en unités
  système cm, scale ×100).

## Limites connues (v0)

- Protocole non officiel : peut casser sans préavis côté Google.
- Exporter tiers testé historiquement sous Node 8 ; installe sous Node 22,
  mais le dump réel reste à valider (→ ce test).
- La « zone » est un octant (cellule carrée), pas un rayon en mètres exact.
- LOD : le détail max dépend de la couverture 3D de la ville.
- Le sol est calé sur le point le plus bas du mesh (approximation).

## Légal

Données propriété de Google. Prévisualisation et usage interne uniquement,
pas d'exploitation commerciale directe des assets extraits.
