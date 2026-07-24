#!/usr/bin/env python3
"""
earth3d.py  --  Google Earth 3D -> OBJ a l'echelle (v2.3, experimental)
====================================================================
Depuis une URL Google Maps (ou lat,lng) et un rayon en metres,
telecharge le mesh 3D texture de l'environnement (donnees Google Earth)
et le recentre a l'echelle metrique (echelle auto-detectee), pret a
importer dans Blender ou 3ds Max.

S'appuie sur le protocole non officiel kh.google.com reverse par
retroplasma/earth-reverse-engineering (clone automatiquement dans
earth3d_vendor/). Aucun compte, aucune cle API.

Prerequis : Python 3, Node.js, Git dans le PATH.
Aucune dependance pip (stdlib uniquement).

Utilisation :
    python earth3d.py        (ou earth3d.bat)

Usage interne uniquement -- donnees propriete de Google.
"""

import os
import re
import sys
import math
import shutil
import subprocess

# ==============================================================================
#  CONFIGURATION
# ==============================================================================

VENDOR_DIR   = "earth3d_vendor"
VENDOR_REPO  = "https://github.com/retroplasma/earth-reverse-engineering.git"
EXPORTER_DIR = os.path.join(VENDOR_DIR, "exporter")
OUT_DIR      = os.path.join("output", "3d")

DEFAULT_DETAIL = 20    # niveau de detail max du dump (20 = max habituel)

# WGS84
_A  = 6378137.0
_E2 = 6.69437999014e-3


# ==============================================================================
#  OUTILS SYSTEME
# ==============================================================================

def _run(cmd, cwd=None, capture=False):
    """Lance une commande (chaine, shell=True pour compat npm/node Windows)."""
    if capture:
        return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    return subprocess.run(cmd, cwd=cwd, shell=True)


def check_prereq(name, cmd):
    r = _run(cmd, capture=True)
    ok = (r.returncode == 0)
    version = (r.stdout or "").strip().splitlines()[0] if ok and r.stdout else ""
    print(f"  [{'OK' if ok else '!!'}] {name:8s} {version}")
    return ok


def ensure_vendor():
    """Clone l'exporter retroplasma + npm install (premier lancement)."""
    if not os.path.isdir(EXPORTER_DIR):
        print()
        print("  Premier lancement : clonage de earth-reverse-engineering...")
        r = _run(f'git clone --depth 1 "{VENDOR_REPO}" "{VENDOR_DIR}"')
        if r.returncode != 0 or not os.path.isdir(EXPORTER_DIR):
            print("  [ERREUR] Clonage impossible. Verifiez git + connexion.")
            return False

    if not os.path.isdir(os.path.join(EXPORTER_DIR, "node_modules")):
        print("  Installation des dependances Node (npm install)...")
        print("  (locale au dossier earth3d_vendor/, rien en global)")
        r = _run("npm install --no-audit --no-fund", cwd=EXPORTER_DIR)
        if r.returncode != 0:
            print("  [ERREUR] npm install a echoue.")
            return False

    # copie/rafraichit le helper de selection par rayon dans l'exporter
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "earth3d_radius.js")
    if os.path.isfile(src):
        shutil.copy2(src, os.path.join(EXPORTER_DIR, "earth3d_radius.js"))
    return True


# ==============================================================================
#  ANALYSE DE L'URL
# ==============================================================================

def extract_lat_lng(text):
    """Extrait (lat, lng) d'une URL Google Maps ou d'une saisie 'lat, lng'."""
    text = text.strip()

    # !3d<lat>!4d<lng> : position precise du panorama (prioritaire)
    m = re.search(r"!3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    # @lat,lng, : position de la camera
    m = re.search(r"@(-?\d+\.?\d*),(-?\d+\.?\d*)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    # saisie directe "lat, lng" ou "lat lng"
    m = re.fullmatch(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    return None


# ==============================================================================
#  OCTANTS
# ==============================================================================

DEFAULT_RADIUS = 150   # rayon par defaut en metres


def ask_radius():
    print()
    while True:
        raw = input(f"  Rayon autour du point en metres "
                    f"[Entree = {DEFAULT_RADIUS}] : ").strip()
        if raw == "":
            return DEFAULT_RADIUS
        if raw.isdigit() and 10 <= int(raw) <= 3000:
            return int(raw)
        print("  Valeur invalide (10 a 3000 m).")


def find_octants_radius(lat, lng, radius):
    """Appelle earth3d_radius.js : octants couvrant le disque de rayon donne.
    Retourne (niveau, taille_cellule_m, [octants]) ou None."""
    print()
    print("  Selection des octants dans le rayon (requetes kh.google.com)...")
    r = _run(f"node earth3d_radius.js {lat} {lng} {radius}",
             cwd=EXPORTER_DIR, capture=True)
    if r.returncode != 0:
        print("  [!] Echec de la selection par rayon :")
        print((r.stderr or "").strip()[:1500])
        return None

    level, cell_m, octants = None, None, []
    for line in (r.stdout or "").splitlines():
        p = line.split()
        if len(p) == 2 and p[0] == "LEVEL" and p[1].isdigit():
            level = int(p[1])
        elif len(p) == 2 and p[0] == "CELL_M" and p[1].isdigit():
            cell_m = int(p[1])
        elif len(p) == 2 and p[0] == "OCT" and re.fullmatch(r"[0-7]{2,32}", p[1]):
            octants.append(p[1])

    if not octants or level is None:
        return None
    return level, cell_m, octants


def find_octants(lat, lng):
    """Appelle lat_long_to_octant.js et parse la sortie.
    Retourne {niveau(int): [octants(str)]}."""
    print()
    print("  Recherche des octants (requetes vers kh.google.com)...")
    r = _run(f"node lat_long_to_octant.js {lat} {lng}",
             cwd=EXPORTER_DIR, capture=True)
    if r.returncode != 0:
        print("  [ERREUR] lat_long_to_octant a echoue :")
        print((r.stderr or "").strip()[:2000])
        return None

    levels = {}
    current = None
    for line in (r.stdout or "").splitlines():
        m = re.match(r"^Octant Level:\s*(\d+)", line)
        if m:
            current = int(m.group(1))
            levels.setdefault(current, [])
            continue
        m = re.match(r"^\s+([0-7]{2,32})\s*$", line)
        if m and current is not None:
            levels[current].append(m.group(1))

    return {k: v for k, v in levels.items() if v} or None


def ask_octant_level(levels):
    """Choix du niveau d'octant = taille de la zone. Defaut : le plus profond
    (zone la plus petite autour du point)."""
    deepest = max(levels)
    print()
    print("  Zone a extraire (niveau d'octant : + profond = + petit) :")
    print()
    for lvl in sorted(levels):
        approx = 40000 / (2 ** lvl) * 1000   # ordre de grandeur cote en m
        mark = "  <-- defaut (zone la plus locale)" if lvl == deepest else ""
        print(f"    {lvl:2d}  ->  ~{approx:6.0f} m de cote, "
              f"{len(levels[lvl])} octant(s){mark}")
    print()
    while True:
        raw = input(f"  Niveau [Entree = {deepest}] : ").strip()
        if raw == "":
            return deepest
        if raw.isdigit() and int(raw) in levels:
            return int(raw)
        print(f"  Valeur invalide. Niveaux disponibles : {sorted(levels)}")


def ask_detail():
    print()
    print("  Detail (niveau de LOD Google Earth) :")
    print("    17-18 -> masses grossieres, tres leger (blocage/lointain)")
    print("    19    -> intermediaire")
    print("    20    -> maximum habituel en ville  <-- recommande")
    print("  Le poids/temps augmente vite ; au-dela de 20, rarement dispo")
    print("  (le dump s'arrete de toute facon au niveau existant).")
    while True:
        raw = input(f"  Detail max [Entree = {DEFAULT_DETAIL}] : ").strip()
        if raw == "":
            return DEFAULT_DETAIL
        if raw.isdigit() and 1 <= int(raw) <= 30:
            return int(raw)
        print("  Valeur invalide (1-30).")


# ==============================================================================
#  DUMP
# ==============================================================================

def dump_octants(octants, detail):
    """Lance dump_obj.js (sortie en direct) et retourne le dossier produit."""
    obj_root = os.path.join(EXPORTER_DIR, "downloaded_files", "obj")
    before = set(os.listdir(obj_root)) if os.path.isdir(obj_root) else set()

    cmd = f"node dump_obj.js {' '.join(octants)} {detail} --parallel-search"
    print()
    print(f"  Telechargement du mesh ({len(octants)} octant(s), "
          f"detail {detail})... Ca peut prendre plusieurs minutes.")
    print()
    r = _run(cmd, cwd=EXPORTER_DIR)
    if r.returncode != 0:
        print("  [ERREUR] dump_obj a echoue.")
        return None

    after = set(os.listdir(obj_root)) if os.path.isdir(obj_root) else set()
    new = [d for d in after - before
           if os.path.isdir(os.path.join(obj_root, d))]
    if new:
        return os.path.join(obj_root, new[0])
    # dossier deja existant (re-dump) : prendre le plus recent
    dirs = [os.path.join(obj_root, d) for d in after]
    dirs = [d for d in dirs if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


# ==============================================================================
#  RECENTRAGE METRIQUE (ECEF -> local, Y-up, metres)
# ==============================================================================

def _geodetic_to_ecef(lat_deg, lng_deg, h=0.0):
    lat, lng = math.radians(lat_deg), math.radians(lng_deg)
    n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
    x = (n + h) * math.cos(lat) * math.cos(lng)
    y = (n + h) * math.cos(lat) * math.sin(lng)
    z = (n * (1 - _E2) + h) * math.sin(lat)
    return x, y, z


def _enu_basis(lat_deg, lng_deg):
    lat, lng = math.radians(lat_deg), math.radians(lng_deg)
    sl, cl = math.sin(lat), math.cos(lat)
    so, co = math.sin(lng), math.cos(lng)
    e = (-so, co, 0.0)
    n = (-sl * co, -sl * so, cl)
    u = (cl * co, cl * so, sl)
    return e, n, u


R_GOOGLE = 6371010.0   # rayon de la sphere Google Earth (rocktree)


def recenter_obj(obj_in, obj_out, lat, lng, radius=None):
    """Recentre model.obj sur (lat,lng), sol a ~0, unites = metres.

    Convention verifiee (test Sydney 2026-07) : le globe Google Earth est une
    SPHERE, la latitude geodesique y est utilisee comme latitude spherique.
    L'origine locale est donc prise dans cette convention (pas d'ellipsoide).
    L'echelle est auto-detectee via la norme moyenne des vertices.

    Si radius est fourni, la geometrie est RECADREE : seules les faces dont
    tous les sommets sont dans le rayon (+ marge) sont conservees.

    Ecrit en convention OBJ standard Y-up (X=est, Y=altitude, Z=sud) :
    Blender et 3ds Max remettent le Z-up a l'import automatiquement.
    Reference model_local.mtl (version nettoyee pour 3ds Max)."""
    import array

    (ex, ey, ez), (nx, ny, nz), (ux, uy, uz) = _enu_basis(lat, lng)

    # ---- passe 1 : lire les vertices, projeter sur les axes locaux -----
    # E et N sont directement relatifs au meridien/parallele du point
    # demande (axes e/n perpendiculaires a sa direction radiale).
    E = array.array("d"); N = array.array("d"); U = array.array("d")
    sx = sy = sz = 0.0
    with open(obj_in, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                x, y, z = float(p[1]), float(p[2]), float(p[3])
                sx += x; sy += y; sz += z
                E.append(ex * x + ey * y + ez * z)
                N.append(nx * x + ny * y + nz * z)
                U.append(ux * x + uy * y + uz * z)

    n = len(E)
    if n == 0:
        print("  [ERREUR] Aucun vertex dans le .obj.")
        return False

    # ---- echelle auto (norme moyenne ~ rayon de la sphere Google) ------
    raw_norm = math.sqrt((sx / n) ** 2 + (sy / n) ** 2 + (sz / n) ** 2)
    if raw_norm < 1e-12:
        print("  [ERREUR] Vertices degeneres (norme nulle).")
        return False
    scale = R_GOOGLE / raw_norm
    if 0.99 < scale < 1.01:
        scale = 1.0                          # deja en metres
    else:
        print(f"  [i] Dump en unites non metriques -> "
              f"facteur d'echelle x{scale:.6g} applique.")
    if scale != 1.0:
        for i in range(n):
            E[i] *= scale; N[i] *= scale; U[i] *= scale

    # garde-fou si la convention differait malgre tout
    mE = sum(E) / n
    mN = sum(N) / n
    dE = dN = 0.0
    horiz = math.hypot(mE, mN)
    if horiz > 5000:
        print(f"  [!] Zone detectee a {horiz/1000:.1f} km de l'origine "
              f"calculee -> recentrage sur le centre de la zone.")
        dE, dN = mE, mN

    u_min = min(U)                          # cale le sol vers 0

    # ---- selection des vertices (recadrage au rayon) -------------------
    keep = bytearray(n)
    if radius:
        rk2 = (float(radius) + 15.0) ** 2   # marge ~ taille de triangle max
        kept = 0
        for i in range(n):
            eE = E[i] - dE; eN = N[i] - dN
            if eE * eE + eN * eN <= rk2:
                keep[i] = 1; kept += 1
        if kept == 0:
            print("  [!] Rien dans le rayon demande ?! Recadrage annule.")
            for i in range(n):
                keep[i] = 1
        else:
            print(f"  [i] Recadrage au rayon {radius} m : "
                  f"{kept}/{n} vertices conserves.")
    else:
        for i in range(n):
            keep[i] = 1

    # nouvel index (1-base) de chaque vertex conserve, 0 = supprime
    remap = array.array("l", [0]) * (n + 1)
    nv = 0
    for i in range(n):
        if keep[i]:
            nv += 1
            remap[i + 1] = nv

    # ---- passe 2 : reecrire le fichier ---------------------------------
    vi = 0
    dropped_faces = 0
    with open(obj_in, "r", encoding="utf-8", errors="replace") as fin, \
         open(obj_out, "w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith("v "):
                vi += 1
                if keep[vi - 1]:
                    # ENU -> OBJ Y-up : x=est, y=altitude, z=-nord (sud)
                    fout.write(f"v {E[vi-1]-dE:.3f} "
                               f"{U[vi-1]-u_min:.3f} {-(N[vi-1]-dN):.3f}\n")
            elif line.startswith("f "):
                toks = line.split()[1:]
                new = []
                ok = True
                for t in toks:
                    parts = t.split("/")
                    old = int(parts[0])
                    nn = remap[old] if 0 < old <= n else 0
                    if nn == 0:
                        ok = False
                        break
                    parts[0] = str(nn)
                    new.append("/".join(parts))
                if ok:
                    fout.write("f " + " ".join(new) + "\n")
                else:
                    dropped_faces += 1
            elif line.startswith("mtllib"):
                fout.write("mtllib model_local.mtl\n")
            else:
                fout.write(line)

    # ---- diagnostics ----------------------------------------------------
    kE = [E[i] - dE for i in range(n) if keep[i]]
    kN = [N[i] - dN for i in range(n) if keep[i]]
    kU = [U[i] - u_min for i in range(n) if keep[i]]
    print(f"  [OK] {nv} vertices ({dropped_faces} faces hors rayon retirees)")
    print(f"       zone {max(kE)-min(kE):.0f} x {max(kN)-min(kN):.0f} m, "
          f"hauteur {max(kU):.0f} m | 1 unite = 1 m")
    print(f"       centre du mesh a {math.hypot(mE-dE, mN-dN):.0f} m "
          f"de l'origine")
    return True


def convert_bmp_textures(out_dir):
    """Convertit les textures .bmp (32 bits ABGR, mal lues par 3ds Max :
    bande noire) en .png et met a jour les references des .mtl.
    Necessite Pillow (present dans le venv de setup.bat) ; sinon, saute
    l'etape avec un avertissement."""
    bmps = [f for f in os.listdir(out_dir) if f.lower().endswith(".bmp")]
    if not bmps:
        return
    try:
        from PIL import Image
    except ImportError:
        print("  [!] Pillow absent : textures laissees en .bmp (32 bits).")
        print("      3ds Max les lit mal (bande noire) -> lance l'outil via")
        print("      streetphere.bat apres setup.bat (venv avec Pillow), ou")
        print("      convertis les .bmp en .png.")
        return
    print(f"  [i] Conversion de {len(bmps)} texture(s) .bmp -> .png "
          f"(compatibilite 3ds Max)...")
    for f in bmps:
        p = os.path.join(out_dir, f)
        Image.open(p).convert("RGB").save(p[:-4] + ".png")
        os.remove(p)
    for mtl in ("model.mtl", "model_local.mtl"):
        p = os.path.join(out_dir, mtl)
        if os.path.isfile(p):
            txt = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(
                txt.replace(".bmp", ".png").replace(".BMP", ".png"))


ATLAS_MAX = 16384      # taille max de l'atlas (px), lisible partout
ATLAS_GUTTER = 4       # marge entre textures (evite le bleed des mips)


def pack_obj(out_dir, obj_name="model_local.obj"):
    """Fusionne les tuiles avec UN SEUL materiau : toutes les textures sont
    packees dans un atlas PNG unique et les UV re-mappes vers la case de
    chaque tuile. Les tuiles restent en groupes 'g' (voir note importeur Max).

    Produit : model_packed.obj + model_packed.mtl + atlas.png.
    Necessite Pillow. Les fichiers multi-textures sont conserves."""
    import array
    try:
        from PIL import Image
    except ImportError:
        print("  [!] Pillow absent : packing atlas impossible (venv setup.bat).")
        return False

    obj_in  = os.path.join(out_dir, obj_name)
    mtl_in  = os.path.join(out_dir, "model_local.mtl")
    if not (os.path.isfile(obj_in) and os.path.isfile(mtl_in)):
        print("  [!] Fichiers manquants pour le packing.")
        return False

    # ---- materiaux -> fichiers texture ---------------------------------
    mat_tex = {}
    cur = None
    with open(mtl_in, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            t = line.strip()
            if t.startswith("newmtl "):
                cur = t.split(None, 1)[1]
            elif t.startswith("map_Kd ") and cur:
                mat_tex[cur] = t.split(None, 1)[1]

    # ---- passe 1 : associer chaque vt a son materiau -------------------
    mats = []                      # ordre d'apparition
    mat_of_vt = array.array("i")   # index materiau par vt (ordre du fichier)
    cur_idx = -1
    with open(obj_in, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("usemtl "):
                name = line.split(None, 1)[1].strip()
                if not mats or mats[-1] != name:
                    mats.append(name)
                cur_idx = len(mats) - 1
            elif line.startswith("vt "):
                mat_of_vt.append(cur_idx)

    used = [m for m in mats if m in mat_tex]
    if not used:
        print("  [!] Aucune texture referencee : packing annule.")
        return False

    # ---- chargement des textures + layout (shelf packing) --------------
    imgs = {}
    for m in set(used):
        p = os.path.join(out_dir, mat_tex[m])
        if not os.path.isfile(p):
            print(f"  [!] Texture absente : {mat_tex[m]} -> packing annule.")
            return False
        imgs[m] = Image.open(p).convert("RGB")

    g = ATLAS_GUTTER
    order = sorted(set(used), key=lambda m: -imgs[m].height)
    # largeur cible ~ carre
    total_area = sum((imgs[m].width + g) * (imgs[m].height + g) for m in order)
    atlas_w = min(ATLAS_MAX, max(1024, 1 << (int(total_area ** 0.5) - 1).bit_length()))

    def layout(scale):
        pos, x, y, row_h, W = {}, g, g, 0, atlas_w
        for m in order:
            w = max(1, int(imgs[m].width * scale))
            h = max(1, int(imgs[m].height * scale))
            if x + w + g > W:
                x = g; y += row_h + g; row_h = 0
            pos[m] = (x, y, w, h)
            x += w + g; row_h = max(row_h, h)
        return pos, y + row_h + g

    scale = 1.0
    pos, atlas_h = layout(scale)
    while atlas_h > ATLAS_MAX and scale > 0.05:
        scale *= (ATLAS_MAX / float(atlas_h)) ** 0.5 * 0.98
        pos, atlas_h = layout(scale)
    atlas_h = min(1 << (atlas_h - 1).bit_length(), ATLAS_MAX)
    pos, real_h = layout(scale)
    if real_h > atlas_h:
        atlas_h = min(ATLAS_MAX, 1 << (real_h - 1).bit_length())

    if scale < 1.0:
        print(f"  [i] Atlas plafonne a {ATLAS_MAX}px : textures reduites "
              f"a {scale*100:.0f}% pour tenir.")

    print(f"  [i] Atlas {atlas_w} x {atlas_h} px, "
          f"{len(set(used))} textures packees...")
    atlas = Image.new("RGB", (atlas_w, atlas_h), (0, 0, 0))
    for m, (x, y, w, h) in pos.items():
        im = imgs[m] if (w, h) == imgs[m].size else imgs[m].resize((w, h))
        atlas.paste(im, (x, y))
        # bleed : duplique bords et coins dans la marge
        if g:
            atlas.paste(im.crop((0, 0, w, 1)).resize((w, g)), (x, y - g))
            atlas.paste(im.crop((0, h - 1, w, h)).resize((w, g)), (x, y + h))
            atlas.paste(im.crop((0, 0, 1, h)).resize((g, h)), (x - g, y))
            atlas.paste(im.crop((w - 1, 0, w, h)).resize((g, h)), (x + w, y))
            atlas.paste(im.crop((0, 0, 1, 1)).resize((g, g)), (x - g, y - g))
            atlas.paste(im.crop((w - 1, 0, w, 1)).resize((g, g)), (x + w, y - g))
            atlas.paste(im.crop((0, h - 1, 1, h)).resize((g, g)), (x - g, y + h))
            atlas.paste(im.crop((w - 1, h - 1, w, h)).resize((g, g)), (x + w, y + h))
    atlas.save(os.path.join(out_dir, "atlas.png"))

    # ---- passe 2 : reecrire l'obj (un materiau, UV remappes) -----------
    with open(os.path.join(out_dir, "model_packed.mtl"), "w",
              encoding="utf-8") as f:
        f.write("newmtl atlas\nKa 1.000 1.000 1.000\nKd 1.000 1.000 1.000\n"
                "d 1.0\nillum 1\nmap_Kd atlas.png\n")

    W, H = float(atlas_w), float(atlas_h)
    vt_i = 0
    with open(obj_in, "r", encoding="utf-8", errors="replace") as fin, \
         open(os.path.join(out_dir, "model_packed.obj"), "w",
              encoding="utf-8") as fout:
        # Un seul materiau, mais on CONSERVE les groupes de tuiles (g) :
        # l'importeur OBJ de 3ds Max casse la geometrie sur un bloc unique
        # de plusieurs millions de faces. Blender ne split pas sur les g
        # (un seul objet) ; dans Max, cocher 'Import as single mesh'.
        fout.write("mtllib model_packed.mtl\nusemtl atlas\n")
        for line in fin:
            if line.startswith("vt "):
                p = line.split()
                u = min(max(float(p[1]), 0.0), 1.0)
                v = min(max(float(p[2]), 0.0), 1.0)
                mi = mat_of_vt[vt_i]; vt_i += 1
                m = mats[mi] if 0 <= mi < len(mats) else None
                if m in pos:
                    x, y, w, h = pos[m]
                    u = (x + u * w) / W
                    v = (H - (y + h) + v * h) / H   # origine OBJ en bas
                fout.write(f"vt {u:.6f} {v:.6f}\n")
            elif line.startswith("o "):
                fout.write("g " + line[2:])        # objet -> groupe
            elif line.startswith(("usemtl", "mtllib", "g ")):
                continue
            else:
                fout.write(line)

    print(f"  [OK] model_packed.obj : 1 materiau, atlas.png, tuiles en groupes.")
    print(f"       Blender : import direct (1 objet). 3ds Max : cocher")
    print(f"       'Import as single mesh' dans l'importeur OBJ.")
    return True


def write_clean_mtl(mtl_in, mtl_out):
    """Reecrit le .mtl en version minimale (newmtl / Ka / Kd / map_Kd),
    plus digeste pour l'importeur OBJ de 3ds Max."""
    if not os.path.isfile(mtl_in):
        return False
    mats = []
    with open(mtl_in, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            t = line.strip()
            if t.startswith("newmtl "):
                mats.append([t.split(None, 1)[1], None])
            elif t.startswith("map_Kd ") and mats:
                mats[-1][1] = t.split(None, 1)[1]
    if not mats:
        return False
    with open(mtl_out, "w", encoding="utf-8") as f:
        for name, tex in mats:
            f.write(f"newmtl {name}\n")
            f.write("Ka 1.000 1.000 1.000\nKd 1.000 1.000 1.000\n")
            f.write("d 1.0\nillum 1\n")
            if tex:
                f.write(f"map_Kd {tex}\n")
            f.write("\n")
    return True


# ==============================================================================
#  PROGRAMME PRINCIPAL
# ==============================================================================

def process(raw):
    coords = extract_lat_lng(raw)
    if not coords:
        print("  [ERREUR] Impossible d'extraire lat/lng. Collez une URL Google")
        print("  Maps (avec @lat,lng ou !3d..!4d..) ou tapez 'lat, lng'.")
        return
    lat, lng = coords

    print()
    print("=" * 62)
    print(f"  Position : {lat}, {lng}")
    print("=" * 62)

    radius = ask_radius()
    found  = find_octants_radius(lat, lng, radius)
    if found:
        lvl, cell_m, octants = found
        print(f"  [OK] {len(octants)} octant(s) niveau {lvl} "
              f"(cellules ~{cell_m} m) couvrent le rayon de {radius} m.")
    else:
        print("  [!] Selection par rayon indisponible -> mode niveau (fallback).")
        levels = find_octants(lat, lng)
        if not levels:
            print("  [ERREUR] Aucun octant trouve. Zone sans 3D, ou protocole")
            print("  modifie cote Google. Essayez un autre point.")
            return
        lvl     = ask_octant_level(levels)
        octants = levels[lvl]
        radius  = None

    detail = ask_detail()

    dump_dir = dump_octants(octants, detail)
    if not dump_dir:
        return

    obj_in = os.path.join(dump_dir, "model.obj")
    if not os.path.isfile(obj_in):
        print(f"  [ERREUR] model.obj introuvable dans {dump_dir}")
        return

    # dossier de sortie
    zone    = f"r{radius}m" if radius else f"lvl{lvl}"
    name    = f"{lat:.5f}_{lng:.5f}_{zone}_d{detail}".replace("-", "m")
    out_dir = os.path.join(OUT_DIR, name)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(dump_dir, out_dir)

    write_clean_mtl(os.path.join(out_dir, "model.mtl"),
                    os.path.join(out_dir, "model_local.mtl"))
    convert_bmp_textures(out_dir)
    ok = recenter_obj(os.path.join(out_dir, "model.obj"),
                      os.path.join(out_dir, "model_local.obj"),
                      lat, lng, radius=radius)

    packed = False
    if ok:
        print()
        ans = input("  Packer en 1 seul objet + atlas de textures ? "
                    "[Entree = oui / n] : ").strip().lower()
        if ans not in ("n", "non", "no"):
            packed = pack_obj(out_dir)

    print()
    print("=" * 62)
    print(f"  TERMINE  --  {out_dir}")
    if packed:
        print(f"    model_packed.obj -> 1 objet, 1 materiau, atlas.png  <-- importer celui-ci")
        print(f"    model_local.obj  -> multi-textures (recentre, metres)")
    else:
        print(f"    model_local.obj  -> recentre, metres  <-- importer celui-ci")
    print(f"    model_local.mtl  -> materiaux nettoyes (3ds Max friendly)")
    print(f"    model.obj/.mtl   -> bruts geocentriques (debug)")
    print("=" * 62)
    print()
    best = "model_packed.obj" if packed else "model_local.obj"
    print(f"  Blender : File > Import > Wavefront (.obj) -> {best}.")
    print("            1 unite = 1 m.")
    print(f"  3ds Max : Import OBJ -> {best}, cocher 'Import materials'.")
    if packed:
        print("            + cocher 'Import as single mesh' (fusionne les groupes).")
    print("            Fichier en METRES : si tes unites systeme sont en cm,")
    print("            regle l'option d'unites de l'importeur (ou scale x100).")
    print("            Viewport noir malgre les bitmaps ? Lance le script")
    print("            max_show_textures.ms (Scripting > Run Script) ou active")
    print("            'Show Shaded Material in Viewport' sur les materiaux.")
    if not ok:
        print("  (Recentrage echoue : model.obj brut disponible quand meme.)")


def main():
    print()
    print("=" * 62)
    print("  Earth 3D -> OBJ a l'echelle   (v2.3 experimental)")
    print("  [Q + Entree] pour quitter")
    print("=" * 62)
    print()
    print("  Verification des prerequis :")
    ok_node = check_prereq("Node.js", "node --version")
    ok_git  = check_prereq("Git",     "git --version")
    if not (ok_node and ok_git):
        print()
        print("  Installez les prerequis manquants puis relancez.")
        print("  Node.js : https://nodejs.org  |  Git : https://git-scm.com")
        sys.exit(1)

    if not ensure_vendor():
        sys.exit(1)

    while True:
        print()
        print("  URL Google Maps (ou lat, lng) :")
        print()
        raw = input("  > ").strip()
        if not raw:
            continue
        if raw.lower() == "q":
            print()
            print("  Au revoir.")
            print()
            break
        process(raw)


if __name__ == "__main__":
    main()
