# earth3d — Google Earth 3D → OBJ à l'échelle (v2.3)

Télécharge le mesh 3D texturé de l'environnement dans un **rayon en mètres**
autour d'un point (données Google Earth) et le recentre à l'échelle métrique,
prêt pour Blender / 3ds Max. Sans compte, sans clé API, sans CB — même
philosophie que streetphere.

## Comment ça marche

1. Tu colles une URL Google Maps (ou `lat, lng`). Le script en extrait la position.
2. Tu donnes un rayon en mètres (défaut 150 m, max 3000 m) et un niveau de
   détail (LOD Google Earth : 17-18 léger, 20 = max recommandé).
3. Le script interroge le protocole non officiel de Google Earth
   (`kh.google.com/rt/…`, reversé par
   [earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering),
   cloné automatiquement dans `earth3d_vendor/` au premier lancement) et
   sélectionne les octants — cellules de l'octree 3D — qui couvrent le disque
   demandé (`earth3d_radius.js`).
4. Il télécharge mesh + textures → `model.obj` (coordonnées géocentriques brutes).
5. Post-traitement Python :
   - échelle **auto-détectée** (norme des vertices vs rayon terrestre) et
     origine exacte sur le point demandé (convention sphère Google vérifiée),
   - sol calé vers 0, axes est/nord/altitude, convention OBJ Y-up standard,
   - **recadrage au rayon** : les faces hors du disque sont retirées (marge ~15 m),
   - textures `.bmp` du dump (32 bits, illisibles proprement par 3ds Max)
     converties en `.png`, `.mtl` nettoyés.
6. Optionnel ([Entrée] = oui) : **packing** — toutes les textures dans un
   atlas PNG unique (plafond 16 384 px, marges anti-coutures), UV remappés,
   un seul matériau. Les tuiles restent en groupes `g` (requis pour que
   l'importeur OBJ de 3ds Max ne casse pas la géométrie).

## Sortie

`output/3d/<lat>_<lng>_r<N>m_d<D>/` :

- `model_packed.obj` + `model_packed.mtl` + `atlas.png` — 1 matériau, 1 texture ← à importer
- `model_local.obj` + `model_local.mtl` + textures — version multi-textures
- `model.obj` / `model.mtl` — bruts géocentriques (debug)

(Les sphères 360 vont dans `output/spheres/` — sorties harmonisées.)

## Utilisation

```bat
streetphere.bat  (choix 2, ou choix 3 pour sphère + 3D d'un coup)
earth3d.bat      (accès direct)
```

Prérequis : Node.js + Git dans le PATH. Python est détecté automatiquement
(venv → lanceur `py` → PATH → chemins courants → saisie manuelle).
Premier lancement : clone + `npm install` automatiques (~1 min).

## Import

- **Blender** : File > Import > Wavefront (.obj) → `model_packed.obj`.
  Un seul objet, 1 unité = 1 m.
- **3ds Max** : Import OBJ → `model_packed.obj`, cocher « Import materials »
  **et « Import as single mesh »** (fusionne les groupes en un seul objet).
  Fichier en mètres : si les unités système sont en cm, régler l'option
  d'unités de l'importeur (ou scale ×100).

## Isolation

Rien ne s'installe hors du dossier du repo : Python = stdlib + Pillow du venv
de `setup.bat`, dépendances Node locales à `earth3d_vendor/node_modules/`,
rien en global.

## Dépannage

- Matériaux noirs au viewport Max (textures pourtant assignées) :
  `max_show_textures.ms` (Scripting > Run Script) active « Show Shaded
  Material in Viewport » sur tous les matériaux d'un coup.
- Géométrie cassée à l'import Max du packed : vérifier que le fichier vient
  bien de la v2.3+ (groupes conservés) et cocher « Import as single mesh ».

## Limites connues (v2.3)

- Protocole non officiel : peut casser sans préavis côté Google.
- Le téléchargement se fait par cellules entières puis la géométrie est
  recadrée au rayon : le volume téléchargé peut dépasser ce qui est gardé.
- Atlas plafonné à 16 384 px : sur de très grandes zones, les textures sont
  réduites proportionnellement (signalé dans le log) — utiliser alors la
  version multi-textures si la résolution prime.
- LOD : le détail max dépend de la couverture 3D de la ville.
- Le sol est calé sur le point le plus bas du mesh (approximation).

## Légal

Données propriété de Google. Prévisualisation et usage interne uniquement,
pas d'exploitation commerciale directe des assets extraits.
