#!/usr/bin/env python3
"""
earth3d.py  --  Google Earth 3D -> OBJ a l'echelle (v1, experimental)
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
    """Recentre model.obj sur (lat,lng), sol a ~0, unites = metres.

    Les coordonnees du dump sont geocentriques. L'echelle est auto-detectee :
    la norme moyenne des vertices doit valoir le rayon terrestre au point
    demande ; sinon le dump est en unites normalisees et on rescale.

    Ecrit en convention OBJ standard Y-up (X=est, Y=altitude, Z=sud) :
    Blender et 3ds Max remettent le Z-up a l'import automatiquement.
    Reference model_local.mtl (version nettoyee pour 3ds Max)."""
    ox, oy, oz = _geodetic_to_ecef(lat, lng)
    expected = math.sqrt(ox * ox + oy * oy + oz * oz)
    (ex, ey, ez), (nx, ny, nz), (ux, uy, uz) = _enu_basis(lat, lng)

    raw = []
    lines = []
    with open(obj_in, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                raw.append((float(p[1]), float(p[2]), float(p[3])))
                lines.append(None)          # emplacement du vertex
            elif line.startswith("mtllib"):
                lines.append("mtllib model_local.mtl\n")
            else:
                lines.append(line)

    if not raw:
        print("  [ERREUR] Aucun vertex dans le .obj.")
        return False

    # --- auto-detection de l'echelle ------------------------------------
    n = len(raw)
    cx = sum(v[0] for v in raw) / n
    cy = sum(v[1] for v in raw) / n
    cz = sum(v[2] for v in raw) / n
    raw_norm = math.sqrt(cx * cx + cy * cy + cz * cz)
    if raw_norm < 1e-12:
        print("  [ERREUR] Vertices degeneres (norme nulle).")
        return False
    scale = expected / raw_norm
    if 0.99 < scale < 1.01:
        scale = 1.0                          # deja en metres
    else:
        print(f"  [i] Dump en unites non metriques -> "
              f"facteur d'echelle x{scale:.6g} applique.")

    # --- transformation ECEF -> ENU local -------------------------------
    verts = []
    for (x, y, z) in raw:
        x, y, z = x * scale - ox, y * scale - oy, z * scale - oz
        E = ex * x + ey * y + ez * z
        N = nx * x + ny * y + nz * z
        U = ux * x + uy * y + uz * z
        verts.append((E, N, U))

    # garde-fou : si le point calcule est loin de la zone (convention
    # geodesique differente), on recentre sur le centre de la zone.
    mE = sum(v[0] for v in verts) / n
    mN = sum(v[1] for v in verts) / n
    dE = dN = 0.0
    horiz = math.hypot(mE, mN)
    if horiz > 5000:
        print(f"  [!] Zone detectee a {horiz/1000:.1f} km de l'origine "
              f"calculee -> recentrage sur le centre de la zone.")
        dE, dN = mE, mN

    u_min = min(v[2] for v in verts)        # cale le sol vers 0

    vi = 0
    with open(obj_out, "w", encoding="utf-8") as f:
        for line in lines:
            if line is None:
                E, N, U = verts[vi]
                vi += 1
                # ENU -> OBJ Y-up : x=est, y=altitude, z=-nord (sud)
                f.write(f"v {E - dE:.3f} {U - u_min:.3f} {-(N - dN):.3f}\n")
            else:
                f.write(line)

    # --- diagnostics ----------------------------------------------------
    Es = [v[0] - dE for v in verts]
    Ns = [v[1] - dN for v in verts]
    Us = [v[2] - u_min for v in verts]
    print(f"  [OK] {n} vertices | zone {max(Es)-min(Es):.0f} x "
          f"{max(Ns)-min(Ns):.0f} m, hauteur {max(Us):.0f} m")
    print(f"       centre du mesh a {math.hypot(mE-dE, mN-dN):.0f} m de "
          f"l'origine | 1 unite = 1 m")
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

    detail = ask_detail()

    dump_dir = dump_octants(octants, detail)
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

    write_clean_mtl(os.path.join(out_dir, "model.mtl"),
                    os.path.join(out_dir, "model_local.mtl"))
    ok = recenter_obj(os.path.join(out_dir, "model.obj"),
                      os.path.join(out_dir, "model_local.obj"), lat, lng)

    print()
    print("=" * 62)
    print(f"  TERMINE  --  {out_dir}")
    print(f"    model_local.obj  -> recentre, metres  <-- importer celui-ci")
    print(f"    model_local.mtl  -> materiaux nettoyes (3ds Max friendly)")
    print(f"    model.obj/.mtl   -> bruts geocentriques (debug)")
    print("=" * 62)
    print()
    print("  Blender : File > Import > Wavefront (.obj) -> model_local.obj.")
    print("            1 unite = 1 m.")
    print("  3ds Max : Import OBJ -> model_local.obj, cocher 'Import materials'.")
    print("            Fichier en METRES : si tes unites systeme sont en cm,")
    print("            regle l'option d'unites de l'importeur (ou scale x100).")
    if not ok:
        print("  (Recentrage echoue : model.obj brut disponible quand meme.)")


def main():
    print()
    print("=" * 62)
    print("  Earth 3D -> OBJ a l'echelle   (v1 experimental)")
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
