#!/usr/bin/env python3
"""
satmap.py  --  flat satellite image, square, north up, true to scale (v1)
=========================================================================
From a Google Maps URL (or lat,lng) and a radius in metres, downloads the
satellite imagery of the square around the point (side = 2 x radius), in
the same local frame as the earth3d mesh: same point + same radius = the
image lies exactly under the 3D mesh, centred on 0,0, north up.

- Resolution: the zoom levels Google offers at that spot, never upscaled.
- Up to 16384 px: one image at native resolution.
- Beyond: cut into N x N equal pieces (no reduction), or reduced once
  to a single 16384 px image.
- Optional: a textured OBJ plane per image, placed in the earth3d frame.

Requirements: the venv (setup.bat): requests + Pillow.
Personal / research use -- the imagery remains the property of Google.

Usage:
    python satmap.py
"""

import io
import os
import math
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

# same conventions as the 3D module: URL parsing, file prefix, Google sphere
from earth3d import extract_lat_lng, gps_token, ask_name, R_GOOGLE, YES


# ==============================================================================
#  CONFIGURATION
# ==============================================================================

OUT_DIR   = os.path.join("output", "sat")
CACHE_DIR = os.path.join(OUT_DIR, "_cache")    # downloaded tiles (resume)

TILE_URL  = "https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
TILE      = 256          # tile size (px)
MAX_ZOOM  = 20           # finest zoom probed
MIN_ZOOM  = 10           # coarsest zoom offered

DEFAULT_RADIUS = 150     # metres (same default as earth3d)
MAX_RADIUS     = 10000   # metres (same cap as earth3d)

MAX_SIDE    = 16384      # max side of one output image (px)
TILE_BUDGET = 10000      # the suggested zoom stays under this many tiles
                         # (to calibrate on the first real runs)

WORKERS     = 4          # parallel downloads (kept low on purpose)
PAUSE       = 0.05       # pause after each tile, per worker (s)
RETRIES     = 4          # attempts per tile, with growing waits
GIVE_UP     = 40         # consecutive failures -> stop, resume later

JPEG_QUALITY = 92
STRIP        = 512       # output rows rendered at a time (RAM stays low)
CELL         = 128       # mesh cell (px): exact mapping at every corner

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


# ==============================================================================
#  GEOMETRY  (earth3d frame <-> Web Mercator)
# ==============================================================================
#
# The earth3d mesh sits on the Google Earth sphere (R_GOOGLE), with the
# geodetic latitude used as the spherical latitude (verified in v2.3). Its
# local coordinates are the projections of a point onto the east / north
# axes of the requested point. The image uses exactly the same frame, so it
# lines up with the mesh.
#
# Note: on that sphere, distances differ slightly from true WGS84 metres
# (about +0.3 % north-south / -0.2 % east-west at 30 deg latitude). The
# image follows the mesh, on purpose: see SATMAP.md.

class Frame:
    """Local east/north frame of a point, earth3d convention."""

    def __init__(self, lat, lng):
        self.lat, self.lng = lat, lng
        la, lo = math.radians(lat), math.radians(lng)
        sl, cl, so, co = math.sin(la), math.cos(la), math.sin(lo), math.cos(lo)
        self.e = (-so, co, 0.0)
        self.n = (-sl * co, -sl * so, cl)
        self.u = (cl * co, cl * so, sl)

    def to_latlng(self, E, N):
        """Local (E, N) metres at ground level -> (lat, lng) degrees."""
        R = R_GOOGLE
        U = math.sqrt(max(R * R - E * E - N * N, 0.0))
        e, n, u = self.e, self.n, self.u
        x = E * e[0] + N * n[0] + U * u[0]
        y = E * e[1] + N * n[1] + U * u[1]
        z = E * e[2] + N * n[2] + U * u[2]
        return math.degrees(math.asin(z / R)), math.degrees(math.atan2(y, x))


def merc_px(lat, lng, z):
    """(lat, lng) -> Web Mercator world pixel coordinates at zoom z
    (continuous: pixel k covers [k, k+1))."""
    size = TILE * (1 << z)
    x = (lng + 180.0) / 360.0 * size
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * size
    return x, y


def native_mpp(lat, z):
    """Metres per pixel of zoom z at this latitude (earth3d metres)."""
    return 2 * math.pi * R_GOOGLE * math.cos(math.radians(lat)) / (TILE * (1 << z))


def square_tiles(frame, radius, z):
    """Range of tiles covering the square at zoom z: (x0, x1, y0, y1),
    inclusive. The square is sampled along its edges (in Mercator it is
    very slightly curved), with a small margin for the interpolation."""
    xs, ys = [], []
    k = 16
    for i in range(k + 1):
        t = -radius + 2.0 * radius * i / k
        for E, N in ((t, radius), (t, -radius), (radius, t), (-radius, t)):
            x, y = merc_px(*frame.to_latlng(E, N), z)
            xs.append(x); ys.append(y)
    m = 3
    return (int(math.floor((min(xs) - m) / TILE)), int(math.floor((max(xs) + m) / TILE)),
            int(math.floor((min(ys) - m) / TILE)), int(math.floor((max(ys) + m) / TILE)))


def tile_count(rng):
    x0, x1, y0, y1 = rng
    return (x1 - x0 + 1) * (y1 - y0 + 1)


# ==============================================================================
#  DOWNLOAD (cache on disk, resumable)
# ==============================================================================

def tile_path(z, x, y):
    return os.path.join(CACHE_DIR, f"z{z}", f"{x}_{y}.jpg")


def fetch_tile(session, z, x, y):
    """One tile from Google -> bytes, or None if there is no usable image.
    Raises on network / server errors (the caller retries)."""
    url = TILE_URL.format(s=(x + y) % 4, x=x, y=y, z=z)
    r = session.get(url, timeout=20)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise IOError(f"HTTP {r.status_code}")
    if not r.headers.get("content-type", "").startswith("image"):
        return None
    return r.content


def _is_real(data):
    """True if the bytes decode to an image that is not a flat placeholder."""
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return False
    lo, hi = im.convert("L").getextrema()
    return hi - lo >= 8


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)        # never a half-written tile in the cache


def probe_zoom(session, lat, lng):
    """Finest zoom where Google has a real image at the centre."""
    last_error = None
    for z in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
        x, y = merc_px(lat, lng, z)
        tx, ty = int(x // TILE), int(y // TILE)
        path = tile_path(z, tx, ty)
        if os.path.isfile(path):
            return z
        try:
            data = fetch_tile(session, z, tx, ty)
        except Exception as ex:
            last_error = ex
            data = None
        if data and _is_real(data):
            _save(path, data)
            return z
    if last_error:
        print(f"  [!] Last error: {last_error}")
    return None


def download(session, z, rng):
    """Downloads every missing tile of the range into the cache.
    Returns (ok, missing): ok = False if Google kept refusing (stop)."""
    x0, x1, y0, y1 = rng
    todo = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if not os.path.isfile(tile_path(z, x, y))]
    total = tile_count(rng)
    have = total - len(todo)
    if not todo:
        print(f"  [OK] {total} tiles already in the cache.")
        return True, 0
    if have:
        print(f"  [i] {have} tiles already in the cache, {len(todo)} to download.")

    lock = threading.Lock()
    state = {"done": 0, "missing": 0, "fails": 0, "stop": False}
    t0 = time.time()

    def one(xy):
        x, y = xy
        if state["stop"]:
            return
        data = None
        for attempt in range(RETRIES):
            try:
                data = fetch_tile(session, z, x, y)
                break
            except Exception:
                if state["stop"]:
                    return
                if attempt < RETRIES - 1:
                    time.sleep(2 ** (attempt + 1))   # 2, 4, 8 s
        else:
            with lock:
                state["fails"] += 1
                state["missing"] += 1
                state["done"] += 1
                if state["fails"] >= GIVE_UP:
                    state["stop"] = True
            return
        if data:
            _save(tile_path(z, x, y), data)
        with lock:
            state["fails"] = 0
            state["done"] += 1
            if not data:
                state["missing"] += 1
        time.sleep(PAUSE)

    def progress(final=False):
        d = state["done"]
        el = time.time() - t0
        rate = d / el if el > 0 else 0
        left = (len(todo) - d) / rate if rate > 0 else 0
        msg = (f"\r  Tiles {have + d}/{total} ({100 * (have + d) // total} %)"
               f"  {rate:.1f}/s")
        if not final and rate > 0:
            msg += f"  ~{_duration(left)} left   "
        print(msg, end="" if not final else "\n", flush=True)

    pool = ThreadPoolExecutor(WORKERS)
    try:
        futures = [pool.submit(one, xy) for xy in todo]
        while not all(f.done() for f in futures):
            progress()
            time.sleep(1)
    except KeyboardInterrupt:
        # Ctrl+C: stop now instead of waiting for the queued tiles
        state["stop"] = True
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:                     # Python 3.8: no cancel_futures
            pool.shutdown(wait=False)
        print()
        print("  [i] Interrupted. The tiles already downloaded are kept:")
        print("      run the same point again, it resumes where it stopped.")
        return False, 0
    pool.shutdown()
    progress(final=True)

    if state["stop"]:
        print()
        print("  [!] Google keeps refusing the requests: download stopped.")
        print("      The tiles already downloaded are kept: run the same")
        print("      point again later, it resumes where it stopped.")
        return False, state["missing"]
    print(f"  [OK] Downloaded in {_duration(time.time() - t0)}.")
    return True, state["missing"]


def _duration(s):
    s = int(s)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s"
    return f"{s // 3600} h {(s % 3600) // 60:02d} min"


# ==============================================================================
#  RENDERING (reprojection into the local square)
# ==============================================================================

_GREY = (128, 128, 128)          # missing tile


def _band(z, tx0, tx1, ty0, ty1, cache):
    """Mosaic of tiles [tx0..tx1] x [ty0..ty1] (decoded tiles kept in cache)."""
    band = Image.new("RGB", ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE), _GREY)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            key = (tx, ty)
            im = cache.get(key)
            if im is None:
                p = tile_path(z, tx, ty)
                im = False
                if os.path.isfile(p):
                    try:
                        im = Image.open(p).convert("RGB")
                        if im.size != (TILE, TILE):
                            im = im.resize((TILE, TILE), Image.LANCZOS)
                    except Exception:
                        im = False
                cache[key] = im
            if im:
                band.paste(im, ((tx - tx0) * TILE, (ty - ty0) * TILE))
    return band


def render(frame, radius, z, mpp, col0, row0, w, h, cache):
    """Renders output pixels [col0, col0+w) x [row0, row0+h) of the square
    grid with pixel size mpp (metres). Pixel (c, r) covers
    E in [-R + c*mpp, -R + (c+1)*mpp], N in [R - (r+1)*mpp, R - r*mpp]:
    row 0 = north edge, column 0 = west edge."""
    # exact mapping at every mesh corner, bilinear inside a CELL (the error
    # there is far below 1/1000 of a pixel)
    cols = list(range(0, w, CELL)) + [w]
    rows = list(range(0, h, CELL)) + [h]
    grid = {}
    xs, ys = [], []
    for r in rows:
        for c in cols:
            E = -radius + (col0 + c) * mpp
            N = radius - (row0 + r) * mpp
            x, y = merc_px(*frame.to_latlng(E, N), z)
            grid[(c, r)] = (x, y)
            xs.append(x); ys.append(y)
    m = 3                                    # bicubic support
    tx0 = int(math.floor((min(xs) - m) / TILE)); tx1 = int(math.floor((max(xs) + m) / TILE))
    ty0 = int(math.floor((min(ys) - m) / TILE)); ty1 = int(math.floor((max(ys) + m) / TILE))
    band = _band(z, tx0, tx1, ty0, ty1, cache)
    ox, oy = tx0 * TILE, ty0 * TILE

    mesh = []
    for j in range(len(rows) - 1):
        for i in range(len(cols) - 1):
            c0, c1, r0, r1 = cols[i], cols[i + 1], rows[j], rows[j + 1]
            q = []
            for cc, rr in ((c0, r0), (c0, r1), (c1, r1), (c1, r0)):   # ul ll lr ur
                x, y = grid[(cc, rr)]
                q += [x - ox, y - oy]
            mesh.append(((c0, r0, c1, r1), tuple(q)))
    return band.transform((w, h), Image.MESH, mesh, Image.BICUBIC)


def _forget_rows(cache, ty_keep):
    """Drops decoded tiles above the current band (RAM stays flat)."""
    for k in [k for k in cache if k[1] < ty_keep]:
        del cache[k]


def render_piece(frame, radius, z, mpp, col0, row0, size):
    """One square output image of `size` px, starting at (col0, row0)."""
    out = Image.new("RGB", (size, size))
    cache = {}
    for r in range(0, size, STRIP):
        h = min(STRIP, size - r)
        out.paste(render(frame, radius, z, mpp, col0, row0 + r, size, h, cache), (0, r))
        # rows of tiles strictly above the next strip are no longer needed
        N = radius - (row0 + r + h) * mpp
        _, y = merc_px(*frame.to_latlng(0.0, N), z)
        _forget_rows(cache, int(y // TILE) - 2)
        print(f"\r  Rendering {min(r + h, size) * 100 // size} %   ", end="", flush=True)
    print()
    return out


def render_reduced(frame, radius, z, native_side, size):
    """Whole square rendered at native resolution strip by strip, each
    strip reduced once with Lanczos: same result as reducing the full
    image, without ever holding it in RAM."""
    k = native_side / float(size)
    mpp = 2.0 * radius / native_side
    out = Image.new("RGB", (size, size))
    cache = {}
    margin = int(math.ceil(3 * k)) + 2       # Lanczos support, in native px
    for o0 in range(0, size, STRIP):
        o1 = min(size, o0 + STRIP)
        a = max(0, int(math.floor(o0 * k)) - margin)
        b = min(native_side, int(math.ceil(o1 * k)) + margin)
        strip = render(frame, radius, z, mpp, 0, a, native_side, b - a, cache)
        red = strip.resize((size, o1 - o0), Image.LANCZOS,
                           box=(0, o0 * k - a, native_side, o1 * k - a))
        out.paste(red, (0, o0))
        _, y = merc_px(*frame.to_latlng(0.0, radius - b * mpp), z)
        _forget_rows(cache, int(y // TILE) - 2)
        print(f"\r  Rendering {o1 * 100 // size} %   ", end="", flush=True)
    print()
    return out


# ==============================================================================
#  PLAN (resolution, grid)
# ==============================================================================

def plan_zoom(frame, radius, z):
    mpp = native_mpp(frame.lat, z)
    side = int(math.ceil(2.0 * radius / mpp - 1e-6))
    return {"z": z, "mpp": mpp, "side": side,
            "tiles": tile_count(square_tiles(frame, radius, z))}


def ask_zoom(frame, radius, zmax):
    """Table of the available resolutions, finest first; Enter = suggestion."""
    rows = []
    for z in range(zmax, MIN_ZOOM - 1, -1):
        p = plan_zoom(frame, radius, z)
        rows.append(p)
        if p["side"] <= MAX_SIDE:
            break                             # coarser ones would be smaller
    sugg = next((p for p in rows if p["tiles"] <= TILE_BUDGET), rows[-1])

    print()
    print(f"  Square of {2 * radius} x {2 * radius} m. Finest imagery here: zoom {zmax}.")
    print()
    print("    zoom    m/px     image side     tiles to download")
    for p in rows:
        fit = "1 image" if p["side"] <= MAX_SIDE else "> 16K"
        mark = "  <-- suggested" if p is sugg else ""
        print(f"    {p['z']:>4}  {p['mpp']:>6.2f}   {p['side']:>7} px ({fit:>7})"
              f"   {p['tiles']:>8}{mark}")
    if len(rows) == 1:
        return sugg                           # nothing to choose
    print()
    while True:
        raw = input(f"  Zoom [Enter = {sugg['z']}] : ").strip().lower()
        if raw == "" or raw in YES:
            return sugg
        if raw.isdigit():
            for p in rows:
                if p["z"] == int(raw):
                    return p
        print(f"  Invalid value ({rows[-1]['z']} to {rows[0]['z']}).")


def ask_layout(p, radius):
    """Beyond 16K: cut into N x N pieces (default) or reduce to one 16K."""
    n = int(math.ceil(p["side"] / float(MAX_SIDE)))
    piece = int(math.ceil(2.0 * radius / n / p["mpp"] - 1e-6))
    red_mpp = 2.0 * radius / MAX_SIDE
    print()
    print(f"  {p['side']} px does not fit in one 16K image:")
    pm = 2.0 * radius / n
    print(f"    [Enter] cut into {n} x {n} pieces of {piece} px "
          f"({pm:.0f} x {pm:.0f} m each), {p['mpp']:.2f} m/px, no reduction")
    print(f"    [r]     reduce to one {MAX_SIDE} px image, {red_mpp:.2f} m/px")
    while True:
        raw = input("  Choice [Enter = cut] : ").strip().lower()
        if raw == "" or raw in YES or raw in ("c", "cut"):
            return "grid", n, piece
        if raw in ("r", "reduce"):
            return "reduce", 1, MAX_SIDE
        print("  Invalid value (Enter or r).")


# ==============================================================================
#  OUTPUTS
# ==============================================================================

def write_info(path, base, lat, lng, radius, p, mode, n, piece, mpp, pieces):
    side_m = 2.0 * radius
    L = []
    L.append(f"{base} -- satellite image (aioli-streetphere satmap)")
    L.append("")
    L.append(f"Centre      : {lat}, {lng}")
    L.append(f"Square      : {side_m:.0f} x {side_m:.0f} m (radius {radius} m), north up")
    L.append(f"Imagery     : Google zoom {p['z']}, native {p['mpp']:.4f} m/px")
    if mode == "reduce":
        L.append(f"Output      : 1 image {piece} x {piece} px, {mpp:.4f} m/px (reduced)")
    elif n == 1:
        L.append(f"Output      : 1 image {piece} x {piece} px, {mpp:.4f} m/px")
    else:
        L.append(f"Output      : {n} x {n} pieces of {piece} x {piece} px, {mpp:.4f} m/px")
        L.append("              r1 = north row, c1 = west column")
    L.append("")
    L.append("Frame: the earth3d one. Origin (0, 0) = the point above, X = east,")
    L.append("north up. Same point + same radius as a 3D extraction = the image")
    L.append("lies exactly under the mesh. Sizes in metres, as in the mesh.")
    L.append("")
    L.append(f"{'file':<{max(len(q[0]) for q in pieces) + 2}}{'size (m)':>12}"
             f"{'centre east (m)':>18}{'centre north (m)':>18}")
    for fname, size_m, ce, cn in pieces:
        L.append(f"{fname:<{max(len(q[0]) for q in pieces) + 2}}{size_m:>12.3f}"
                 f"{ce:>18.3f}{cn:>18.3f}")
    L.append("")
    L.append("3ds Max (Z up): plane of 'size' x 'size', position X = east, Y = north.")
    L.append("Blender  (Z up): same, location X = east, Y = north.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def write_plane_obj(out_dir, base, pieces):
    """One flat quad per image, at height 0, in the earth3d OBJ frame
    (Y up, X = east, Z = south), each with its own material + texture."""
    obj = os.path.join(out_dir, base + ".obj")
    mtl = os.path.join(out_dir, base + ".mtl")
    with open(mtl, "w", encoding="utf-8") as f:
        for fname, *_ in pieces:
            name = os.path.splitext(fname)[0]
            f.write(f"newmtl {name}\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 1\n"
                    f"map_Kd {fname}\n\n")
    with open(obj, "w", encoding="utf-8") as f:
        f.write(f"# {base} -- satellite plane(s), metres, earth3d frame\n")
        f.write(f"mtllib {base}.mtl\n")
        f.write("vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n")
        f.write("vn 0 1 0\n")
        for i, (fname, size_m, ce, cn) in enumerate(pieces):
            h = size_m / 2.0
            w0, e0, s0, n0 = ce - h, ce + h, cn - h, cn + h
            # SW, SE, NE, NW  (Z = -north); counter-clockwise seen from above
            for E, N in ((w0, s0), (e0, s0), (e0, n0), (w0, n0)):
                f.write(f"v {E + 0.0:.4f} 0 {0.0 - N:.4f}\n")   # no "-0.0000"
        for i, (fname, *_) in enumerate(pieces):
            name = os.path.splitext(fname)[0]
            b = 4 * i
            f.write(f"g {name}\nusemtl {name}\n")
            f.write(f"f {b+1}/1/1 {b+2}/2/1 {b+3}/3/1 {b+4}/4/1\n")
    return obj


def metres_token(v):
    """12000 -> '12000m', 1714.2857 -> '1714p29m': the ground size in the
    file name, letters/digits only (decimal point -> 'p', as the GPS)."""
    if abs(v - round(v)) < 0.005:
        return f"{int(round(v))}m"
    return f"{v:.2f}".replace(".", "p") + "m"


def _mb(path):
    return os.path.getsize(path) / 1e6


# ==============================================================================
#  MAIN FLOW
# ==============================================================================

def ask_radius():
    print()
    while True:
        raw = input(f"  Radius around the point, in metres (square of 2 x radius) "
                    f"[Enter = {DEFAULT_RADIUS}] : ").strip()
        if raw == "":
            return DEFAULT_RADIUS
        if raw.isdigit() and 10 <= int(raw) <= MAX_RADIUS:
            return int(raw)
        print(f"  Invalid value (10 to {MAX_RADIUS} m).")


def process(session, raw):
    coords = extract_lat_lng(raw)
    if not coords:
        print("  [ERROR] Could not extract lat/lng. Paste a Google Maps URL")
        print("  (with @lat,lng or !3d..!4d..) or type 'lat, lng'.")
        return
    lat, lng = coords
    frame = Frame(lat, lng)

    print()
    print("=" * 62)
    print(f"  Position : {lat}, {lng}")
    print("=" * 62)

    radius = ask_radius()
    print()
    print("  Checking the finest imagery available here...")
    zmax = probe_zoom(session, lat, lng)
    if zmax is None:
        print("  [ERROR] No satellite image reachable at this point")
        print("  (no connection, or Google refused the requests).")
        return

    p = ask_zoom(frame, radius, zmax)
    if p["side"] <= MAX_SIDE:
        mode, n, piece = "single", 1, p["side"]
    else:
        mode, n, piece = ask_layout(p, radius)

    label = ask_name()
    print()
    ans = input("  Also export a textured OBJ plane (drops under the 3D mesh)? "
                "[Enter = yes / n] : ").strip().lower()
    want_obj = ans not in ("n", "no", "non")

    # prefix, same logic as earth3d (v2.6): [name_]29p5770N_35p4200E_r6000_sat18
    # (sat18 = satellite, zoom 18; the 3D module writes d19 = detail 19)
    base = f"{gps_token(lat, lng)}_r{radius}_sat{p['z']}"
    if label:
        base = f"{label}_{base}"
    out_dir = os.path.join(OUT_DIR, base)
    os.makedirs(out_dir, exist_ok=True)

    print()
    print(f"  Downloading zoom {p['z']} ({p['tiles']} tiles)...")
    ok, missing = download(session, p["z"], square_tiles(frame, radius, p["z"]))
    if not ok:
        return
    if missing:
        print(f"  [!] {missing} tile(s) missing (no image or refused):")
        print("      shown as flat grey in the output.")

    side_m = 2.0 * radius
    pieces = []                         # (file, size_m, centre_E, centre_N)
    print()
    if mode == "reduce":
        mpp = side_m / piece
        fname = f"{base}_{metres_token(side_m)}.jpg"
        img = render_reduced(frame, radius, p["z"], p["side"], piece)
        img.save(os.path.join(out_dir, fname), quality=JPEG_QUALITY)
        del img
        pieces.append((fname, side_m, 0.0, 0.0))
    else:
        # grid of n x n pieces of `piece` px on one global pixel grid:
        # the pieces touch exactly, each covers side_m / n metres
        mpp = side_m / (n * piece)
        for r in range(n):
            for c in range(n):
                # name = ground size covered (+ row / column in a grid)
                fname = (f"{base}_{metres_token(side_m)}.jpg" if n == 1
                         else f"{base}_{metres_token(side_m / n)}_r{r+1}c{c+1}.jpg")
                if n > 1:
                    print(f"  Piece r{r+1}c{c+1} ({r * n + c + 1}/{n * n})")
                img = render_piece(frame, radius, p["z"], mpp,
                                   c * piece, r * piece, piece)
                img.save(os.path.join(out_dir, fname), quality=JPEG_QUALITY)
                del img
                size_m = side_m / n
                ce = -radius + (c + 0.5) * size_m
                cn = radius - (r + 0.5) * size_m
                pieces.append((fname, size_m, ce, cn))

    info = os.path.join(out_dir, f"{base}.txt")
    write_info(info, base, lat, lng, radius, p, mode, n, piece, mpp, pieces)
    obj = write_plane_obj(out_dir, base, pieces) if want_obj else None

    total = sum(_mb(os.path.join(out_dir, q[0])) for q in pieces)
    print()
    print("=" * 62)
    print(f"  DONE  --  {out_dir}")
    if len(pieces) == 1:
        print(f"    {pieces[0][0]}")
        print(f"      covers {side_m:.0f} x {side_m:.0f} m, {piece} px, "
              f"{mpp:.2f} m/px, {total:.0f} MB")
    else:
        pm = side_m / n
        print(f"    {n} x {n} pieces ..._{metres_token(pm)}_rXcY.jpg")
        print(f"      each covers {pm:.2f} x {pm:.2f} m, {piece} px, "
              f"{mpp:.2f} m/px ({total:.0f} MB in all)")
        print("      r1 = north row, c1 = west column")
    print(f"    {base}.txt  -> size and position of each image (metres)")
    if obj:
        print(f"    {base}.obj  -> textured plane(s), import next to the mesh")
    print("=" * 62)
    print(f"  Downloaded tiles kept in {CACHE_DIR} (reused next time;")
    print("  delete that folder whenever you want).")
    if obj:
        print()
        print("  3ds Max : Import OBJ, tick 'Import materials', units = metres.")
        print("  Blender : File > Import > Wavefront (.obj). 1 unit = 1 m.")
        print("  The plane is at height 0 (the lowest point of a 3D extraction).")


def main():
    print()
    print("=" * 62)
    print("  Satellite map -> square image, true to scale   (v1)")
    print("  [Q + Enter] to quit")
    print("=" * 62)
    with requests.Session() as session:
        session.headers.update({"User-Agent": UA})
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
            process(session, raw)


if __name__ == "__main__":
    main()
