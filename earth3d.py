#!/usr/bin/env python3
"""
earth3d.py  --  Google Earth 3D -> OBJ a l'echelle (v0, experimental)
====================================================================
Depuis une URL Google Maps (ou lat,lng), telecharge le mesh 3D texture
de l'environnement (donnees Google Earth) et le recentre a l'echelle
metrique, pret a importer dans Blender ou 3ds Max.

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
OUT_DIR      = "earth3d_out"

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


def recenter_obj(obj_in, obj_out, lat, lng):
    """Recentre model.obj sur (lat,lng), sol a ~0, metres.
    Ecrit en convention OBJ standard Y-up (X=est, Y=altitude, Z=sud) :
    Blender et 3ds Max remettent le Z-up a l'import automatiquement.
    Les vertices du dump sont en ECEF (geocentrique, metres)."""
    ox, oy, oz = _geodetic_to_ecef(lat, lng)
    (ex, ey, ez), (nx, ny, nz), (ux, uy, uz) = _enu_basis(lat, lng)

    verts = []
    lines = []
    with open(obj_in, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                x, y, z = float(p[1]) - ox, float(p[2]) - oy, float(p[3]) - oz
                E = ex * x + ey * y + ez * z
                N = nx * x + ny * y + nz * z
                U = ux * x + uy * y + uz * z
                verts.append((E, N, U))
                lines.append(None)          # emplacement du vertex
            else:
                lines.append(line)

    if not verts:
        print("  [ERREUR] Aucun vertex dans le .obj.")
        return False

    u_min = min(v[2] for v in verts)        # cale le sol vers 0

    vi = 0
    with open(obj_out, "w", encoding="utf-8") as f:
        for line in lines:
            if line is None:
                E, N, U = verts[vi]
                vi += 1
                # ENU -> OBJ Y-up : x=est, y=altitude, z=-nord (sud)
                f.write(f"v {E:.3f} {U - u_min:.3f} {-N:.3f}\n")
            else:
                f.write(line)

    print(f"  [OK] Recentre : {len(verts)} vertices, origine = point demande,"
          f" sol ~0, unites = metres.")
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

    levels = find_octants(lat, lng)
    if not levels:
        print("  [ERREUR] Aucun octant trouve. Zone sans 3D, ou protocole")
        print("  modifie cote Google. Essayez un autre point.")
        return

    lvl    = ask_octant_level(levels)
    detail = ask_detail()

    dump_dir = dump_octants(levels[lvl], detail)
    if not dump_dir:
        return

    obj_in = os.path.join(dump_dir, "model.obj")
    if not os.path.isfile(obj_in):
        print(f"  [ERREUR] model.obj introuvable dans {dump_dir}")
        return

    # dossier de sortie propre a la racine du repo
    name    = f"{lat:.5f}_{lng:.5f}_lvl{lvl}_d{detail}".replace("-", "m")
    out_dir = os.path.join(OUT_DIR, name)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(dump_dir, out_dir)

    ok = recenter_obj(os.path.join(out_dir, "model.obj"),
                      os.path.join(out_dir, "model_local.obj"), lat, lng)

    print()
    print("=" * 62)
    print(f"  TERMINE  --  {out_dir}")
    print(f"    model_local.obj  -> recentre, metres  <-- importer celui-ci")
    print(f"    model.obj        -> brut geocentrique (debug)")
    print("=" * 62)
    print()
    print("  Import Blender : File > Import > Wavefront (.obj), regle sur")
    print("  model_local.obj. 1 unite = 1 m. Dans 3ds Max (unites cm),")
    print("  appliquer un scale x100 ou regler File Units a l'import.")
    if not ok:
        print("  (Recentrage echoue : model.obj brut disponible quand meme.)")


def main():
    print()
    print("=" * 62)
    print("  Earth 3D -> OBJ a l'echelle   (v0 experimental)")
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
