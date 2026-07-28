#!/usr/bin/env python3
"""
earth3d.py  --  Google Earth 3D -> true-to-scale OBJ (v2.3, experimental)
========================================================================
From a Google Maps URL (or lat,lng) and a radius in metres, downloads the
textured 3D mesh of the surroundings (Google Earth data) and recentres it
at metric scale (scale auto-detected), ready to import into Blender or
3ds Max.

Built on the unofficial kh.google.com protocol, reverse engineered by
retroplasma/earth-reverse-engineering (cloned automatically into
earth3d_vendor/). No account, no API key.

Requirements: Python 3, Node.js, Git in the PATH.
No pip dependency (stdlib only).

Usage:
    python earth3d.py

Personal / research use -- the data remains the property of Google.
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

DEFAULT_DETAIL = 20    # max detail level of the dump (20 = usual maximum)

# WGS84
_A  = 6378137.0
_E2 = 6.69437999014e-3


# ==============================================================================
#  SYSTEM HELPERS
# ==============================================================================

def _run(cmd, cwd=None, capture=False):
    """Runs a command (string, shell=True for npm/node compat on Windows)."""
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
    """Clones the retroplasma exporter + npm install (first run)."""
    if not os.path.isdir(EXPORTER_DIR):
        print()
        print("  First run: cloning earth-reverse-engineering...")
        r = _run(f'git clone --depth 1 "{VENDOR_REPO}" "{VENDOR_DIR}"')
        if r.returncode != 0 or not os.path.isdir(EXPORTER_DIR):
            print("  [ERROR] Clone failed. Check git + your connection.")
            return False

    if not os.path.isdir(os.path.join(EXPORTER_DIR, "node_modules")):
        print("  Installing the Node dependencies (npm install)...")
        print("  (local to the earth3d_vendor/ folder, nothing global)")
        r = _run("npm install --no-audit --no-fund", cwd=EXPORTER_DIR)
        if r.returncode != 0:
            print("  [ERROR] npm install failed.")
            return False

    # copies/refreshes the radius selection helper into the exporter
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "earth3d_radius.js")
    if os.path.isfile(src):
        shutil.copy2(src, os.path.join(EXPORTER_DIR, "earth3d_radius.js"))
    return True


# ==============================================================================
#  URL PARSING
# ==============================================================================

def extract_lat_lng(text):
    """Extracts (lat, lng) from a Google Maps URL or from a 'lat, lng' input."""
    text = text.strip()

    # !3d<lat>!4d<lng> : exact position of the panorama (takes precedence)
    m = re.search(r"!3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    # @lat,lng, : camera position
    m = re.search(r"@(-?\d+\.?\d*),(-?\d+\.?\d*)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    # direct input "lat, lng" or "lat lng"
    m = re.fullmatch(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    return None


# ==============================================================================
#  OCTANTS
# ==============================================================================

DEFAULT_RADIUS = 150   # default radius in metres


def ask_radius():
    print()
    while True:
        raw = input(f"  Radius around the point, in metres "
                    f"[Enter = {DEFAULT_RADIUS}] : ").strip()
        if raw == "":
            return DEFAULT_RADIUS
        if raw.isdigit() and 10 <= int(raw) <= 3000:
            return int(raw)
        print("  Invalid value (10 to 3000 m).")


def find_octants_radius(lat, lng, radius):
    """Calls earth3d_radius.js: octants covering the disc of the given radius.
    Returns (level, cell_size_m, [octants]) or None."""
    print()
    print("  Selecting the octants inside the radius (kh.google.com requests)...")
    r = _run(f"node earth3d_radius.js {lat} {lng} {radius}",
             cwd=EXPORTER_DIR, capture=True)
    if r.returncode != 0:
        print("  [!] Radius-based selection failed:")
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
    """Calls lat_long_to_octant.js and parses its output.
    Returns {level(int): [octants(str)]}."""
    print()
    print("  Looking for octants (requests to kh.google.com)...")
    r = _run(f"node lat_long_to_octant.js {lat} {lng}",
             cwd=EXPORTER_DIR, capture=True)
    if r.returncode != 0:
        print("  [ERROR] lat_long_to_octant failed:")
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
    """Octant level = size of the area. Default: the deepest one
    (the smallest area around the point)."""
    deepest = max(levels)
    print()
    print("  Area to extract (octant level: deeper = smaller):")
    print()
    for lvl in sorted(levels):
        approx = 40000 / (2 ** lvl) * 1000   # rough order of magnitude, side in m
        mark = "  <-- default (most local area)" if lvl == deepest else ""
        print(f"    {lvl:2d}  ->  ~{approx:6.0f} m across, "
              f"{len(levels[lvl])} octant(s){mark}")
    print()
    while True:
        raw = input(f"  Level [Enter = {deepest}] : ").strip()
        if raw == "":
            return deepest
        if raw.isdigit() and int(raw) in levels:
            return int(raw)
        print(f"  Invalid value. Available levels: {sorted(levels)}")


def ask_detail():
    print()
    print("  Detail (Google Earth LOD level):")
    print("    17-18 -> coarse volumes, very light (blocking/distant)")
    print("    19    -> intermediate")
    print("    20    -> usual maximum in cities  <-- recommended")
    print("  Weight/time grows fast; above 20 it is rarely available")
    print("  (the dump stops at the deepest existing level anyway).")
    while True:
        raw = input(f"  Max detail [Enter = {DEFAULT_DETAIL}] : ").strip()
        if raw == "":
            return DEFAULT_DETAIL
        if raw.isdigit() and 1 <= int(raw) <= 30:
            return int(raw)
        print("  Invalid value (1-30).")


# ==============================================================================
#  DUMP
# ==============================================================================

def dump_octants(octants, detail):
    """Runs dump_obj.js (live output) and returns the folder it produced."""
    obj_root = os.path.join(EXPORTER_DIR, "downloaded_files", "obj")
    before = set(os.listdir(obj_root)) if os.path.isdir(obj_root) else set()

    cmd = f"node dump_obj.js {' '.join(octants)} {detail} --parallel-search"
    print()
    print(f"  Downloading the mesh ({len(octants)} octant(s), "
          f"detail {detail})... This can take several minutes.")
    print()
    r = _run(cmd, cwd=EXPORTER_DIR)
    if r.returncode != 0:
        print("  [ERROR] dump_obj failed.")
        return None

    after = set(os.listdir(obj_root)) if os.path.isdir(obj_root) else set()
    new = [d for d in after - before
           if os.path.isdir(os.path.join(obj_root, d))]
    if new:
        return os.path.join(obj_root, new[0])
    # folder already there (re-dump): take the most recent one
    dirs = [os.path.join(obj_root, d) for d in after]
    dirs = [d for d in dirs if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


# ==============================================================================
#  METRIC RECENTRING (ECEF -> local, Y-up, metres)
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


R_GOOGLE = 6371010.0   # radius of the Google Earth sphere (rocktree)


def recenter_obj(obj_in, obj_out, lat, lng, radius=None):
    """Recentres model.obj on (lat,lng), ground at ~0, units = metres.

    Verified convention (Sydney test, 2026-07): the Google Earth globe is a
    SPHERE, and geodetic latitude is used there as spherical latitude.
    The local origin is therefore taken in that convention (no ellipsoid).
    The scale is auto-detected from the mean norm of the vertices.

    If radius is given, the geometry is CROPPED: only the faces whose
    vertices all sit inside the radius (+ margin) are kept.

    Written in the standard Y-up OBJ convention (X=east, Y=altitude, Z=south):
    Blender and 3ds Max restore Z-up on import automatically.
    References model_local.mtl (cleaned-up version for 3ds Max)."""
    import array

    (ex, ey, ez), (nx, ny, nz), (ux, uy, uz) = _enu_basis(lat, lng)

    # ---- pass 1: read the vertices, project them onto the local axes ---
    # E and N are directly relative to the meridian/parallel of the requested
    # point (e/n axes perpendicular to its radial direction).
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
        print("  [ERROR] No vertex in the .obj.")
        return False

    # ---- auto scale (mean norm ~ radius of the Google sphere) ---------
    raw_norm = math.sqrt((sx / n) ** 2 + (sy / n) ** 2 + (sz / n) ** 2)
    if raw_norm < 1e-12:
        print("  [ERROR] Degenerate vertices (zero norm).")
        return False
    scale = R_GOOGLE / raw_norm
    if 0.99 < scale < 1.01:
        scale = 1.0                          # already in metres
    else:
        print(f"  [i] Dump in non-metric units -> "
              f"scale factor x{scale:.6g} applied.")
    if scale != 1.0:
        for i in range(n):
            E[i] *= scale; N[i] *= scale; U[i] *= scale

    # guard rail in case the convention differed after all
    mE = sum(E) / n
    mN = sum(N) / n
    dE = dN = 0.0
    horiz = math.hypot(mE, mN)
    if horiz > 5000:
        print(f"  [!] Area detected {horiz/1000:.1f} km away from the computed "
              f"origin -> recentring on the centre of the area.")
        dE, dN = mE, mN

    u_min = min(U)                          # pin the ground to 0

    # ---- vertex selection (cropping to the radius) ---------------------
    keep = bytearray(n)
    if radius:
        rk2 = (float(radius) + 15.0) ** 2   # margin ~ max triangle size
        kept = 0
        for i in range(n):
            eE = E[i] - dE; eN = N[i] - dN
            if eE * eE + eN * eN <= rk2:
                keep[i] = 1; kept += 1
        if kept == 0:
            print("  [!] Nothing inside the requested radius?! Cropping cancelled.")
            for i in range(n):
                keep[i] = 1
        else:
            print(f"  [i] Cropping to the {radius} m radius: "
                  f"{kept}/{n} vertices kept.")
    else:
        for i in range(n):
            keep[i] = 1

    # new (1-based) index of each kept vertex, 0 = removed
    remap = array.array("l", [0]) * (n + 1)
    nv = 0
    for i in range(n):
        if keep[i]:
            nv += 1
            remap[i + 1] = nv

    # ---- pass 2: rewrite the file --------------------------------------
    vi = 0
    dropped_faces = 0
    with open(obj_in, "r", encoding="utf-8", errors="replace") as fin, \
         open(obj_out, "w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith("v "):
                vi += 1
                if keep[vi - 1]:
                    # ENU -> OBJ Y-up: x=east, y=altitude, z=-north (south)
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
    print(f"  [OK] {nv} vertices ({dropped_faces} faces outside the radius removed)")
    print(f"       area {max(kE)-min(kE):.0f} x {max(kN)-min(kN):.0f} m, "
          f"height {max(kU):.0f} m | 1 unit = 1 m")
    print(f"       mesh centre {math.hypot(mE-dE, mN-dN):.0f} m "
          f"from the origin")
    return True


def convert_bmp_textures(out_dir):
    """Converts the .bmp textures (32-bit ABGR, misread by 3ds Max:
    black band) to .png and updates the references in the .mtl files.
    Requires Pillow (present in the setup.bat venv); otherwise the step
    is skipped with a warning."""
    bmps = [f for f in os.listdir(out_dir) if f.lower().endswith(".bmp")]
    if not bmps:
        return
    try:
        from PIL import Image
    except ImportError:
        print("  [!] Pillow missing: textures left as .bmp (32-bit).")
        print("      3ds Max reads them badly (black band) -> run the tool via")
        print("      streetphere.bat after setup.bat (venv with Pillow), or")
        print("      convert the .bmp files to .png yourself.")
        return
    print(f"  [i] Converting {len(bmps)} .bmp texture(s) -> .png "
          f"(3ds Max compatibility)...")
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


ATLAS_MAX = 16384      # max atlas size (px), readable everywhere
ATLAS_GUTTER = 4       # margin between textures (avoids mip bleeding)


def pack_obj(out_dir, obj_name="model_local.obj"):
    """Merges the tiles with ONE SINGLE material: every texture is packed
    into a single PNG atlas and the UVs are remapped to each tile's slot.
    The tiles stay in 'g' groups (see the note about the Max importer).

    Produces: model_packed.obj + model_packed.mtl + atlas.png.
    Requires Pillow. The multi-texture files are kept."""
    import array
    try:
        from PIL import Image
    except ImportError:
        print("  [!] Pillow missing: atlas packing impossible (setup.bat venv).")
        return False

    obj_in  = os.path.join(out_dir, obj_name)
    mtl_in  = os.path.join(out_dir, "model_local.mtl")
    if not (os.path.isfile(obj_in) and os.path.isfile(mtl_in)):
        print("  [!] Missing files for packing.")
        return False

    # ---- materials -> texture files ------------------------------------
    mat_tex = {}
    cur = None
    with open(mtl_in, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            t = line.strip()
            if t.startswith("newmtl "):
                cur = t.split(None, 1)[1]
            elif t.startswith("map_Kd ") and cur:
                mat_tex[cur] = t.split(None, 1)[1]

    # ---- pass 1: map each vt to its material ---------------------------
    mats = []                      # order of appearance
    mat_of_vt = array.array("i")   # material index per vt (file order)
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
        print("  [!] No texture referenced: packing cancelled.")
        return False

    # ---- loading the textures + layout (shelf packing) -----------------
    imgs = {}
    for m in set(used):
        p = os.path.join(out_dir, mat_tex[m])
        if not os.path.isfile(p):
            print(f"  [!] Texture missing: {mat_tex[m]} -> packing cancelled.")
            return False
        imgs[m] = Image.open(p).convert("RGB")

    g = ATLAS_GUTTER
    order = sorted(set(used), key=lambda m: -imgs[m].height)
    # target width ~ square
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
        print(f"  [i] Atlas capped at {ATLAS_MAX}px: textures scaled down "
              f"to {scale*100:.0f}% to fit.")

    print(f"  [i] Atlas {atlas_w} x {atlas_h} px, "
          f"{len(set(used))} textures packed...")
    atlas = Image.new("RGB", (atlas_w, atlas_h), (0, 0, 0))
    for m, (x, y, w, h) in pos.items():
        im = imgs[m] if (w, h) == imgs[m].size else imgs[m].resize((w, h))
        atlas.paste(im, (x, y))
        # bleed: duplicates the edges and corners into the margin
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

    # ---- pass 2: rewrite the obj (one material, remapped UVs) ----------
    with open(os.path.join(out_dir, "model_packed.mtl"), "w",
              encoding="utf-8") as f:
        f.write("newmtl atlas\nKa 1.000 1.000 1.000\nKd 1.000 1.000 1.000\n"
                "d 1.0\nillum 1\nmap_Kd atlas.png\n")

    W, H = float(atlas_w), float(atlas_h)
    vt_i = 0
    with open(obj_in, "r", encoding="utf-8", errors="replace") as fin, \
         open(os.path.join(out_dir, "model_packed.obj"), "w",
              encoding="utf-8") as fout:
        # One single material, but we KEEP the tile groups (g):
        # the 3ds Max OBJ importer breaks the geometry on a single block of
        # several million faces. Blender does not split on g (one object);
        # in Max, tick 'Import as single mesh'.
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
                    v = (H - (y + h) + v * h) / H   # OBJ origin at the bottom
                fout.write(f"vt {u:.6f} {v:.6f}\n")
            elif line.startswith("o "):
                fout.write("g " + line[2:])        # object -> group
            elif line.startswith(("usemtl", "mtllib", "g ")):
                continue
            else:
                fout.write(line)

    print(f"  [OK] model_packed.obj : 1 material, atlas.png, tiles as groups.")
    print(f"       Blender: direct import (1 object). 3ds Max: tick")
    print(f"       'Import as single mesh' in the OBJ importer.")
    return True


def write_clean_mtl(mtl_in, mtl_out):
    """Rewrites the .mtl in a minimal form (newmtl / Ka / Kd / map_Kd),
    easier to digest for the 3ds Max OBJ importer."""
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
#  MAIN PROGRAM
# ==============================================================================

def process(raw):
    coords = extract_lat_lng(raw)
    if not coords:
        print("  [ERROR] Could not extract lat/lng. Paste a Google Maps URL")
        print("  (with @lat,lng or !3d..!4d..) or type 'lat, lng'.")
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
        print(f"  [OK] {len(octants)} octant(s) at level {lvl} "
              f"(~{cell_m} m cells) cover the {radius} m radius.")
    else:
        print("  [!] Radius selection unavailable -> level mode (fallback).")
        levels = find_octants(lat, lng)
        if not levels:
            print("  [ERROR] No octant found. Area without 3D data, or the")
            print("  protocol changed on Google's side. Try another point.")
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
        print(f"  [ERROR] model.obj not found in {dump_dir}")
        return

    # output folder
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
        ans = input("  Pack into a single object + texture atlas? "
                    "[Enter = yes / n] : ").strip().lower()
        if ans not in ("n", "no", "non"):
            packed = pack_obj(out_dir)

    print()
    print("=" * 62)
    print(f"  DONE  --  {out_dir}")
    if packed:
        print(f"    model_packed.obj -> 1 object, 1 material, atlas.png  <-- import this one")
        print(f"    model_local.obj  -> multi-texture (recentred, metres)")
    else:
        print(f"    model_local.obj  -> recentred, metres  <-- import this one")
    print(f"    model_local.mtl  -> cleaned-up materials (3ds Max friendly)")
    print(f"    model.obj/.mtl   -> raw geocentric (debug)")
    print("=" * 62)
    print()
    best = "model_packed.obj" if packed else "model_local.obj"
    print(f"  Blender : File > Import > Wavefront (.obj) -> {best}.")
    print("            1 unit = 1 m.")
    print(f"  3ds Max : Import OBJ -> {best}, tick 'Import materials'.")
    if packed:
        print("            + tick 'Import as single mesh' (merges the groups).")
    print("            File is in METRES: if your system units are cm,")
    print("            set the importer's unit option (or scale x100).")
    if not ok:
        print("  (Recentring failed: the raw model.obj is still available.)")


def main():
    print()
    print("=" * 62)
    print("  Earth 3D -> true-to-scale OBJ   (v2.3 experimental)")
    print("  [Q + Enter] to quit")
    print("=" * 62)
    print()
    print("  Checking requirements:")
    ok_node = check_prereq("Node.js", "node --version")
    ok_git  = check_prereq("Git",     "git --version")
    if not (ok_node and ok_git):
        print()
        print("  Install the missing requirements and run it again.")
        print("  Node.js : https://nodejs.org  |  Git : https://git-scm.com")
        sys.exit(1)

    if not ensure_vendor():
        sys.exit(1)

    while True:
        print()
        print("  Google Maps URL (or lat, lng):")
        print()
        raw = input("  > ").strip()
        if not raw:
            continue
        if raw.lower() == "q":
            print()
            print("  Goodbye.")
            print()
            break
        process(raw)


if __name__ == "__main__":
    main()
