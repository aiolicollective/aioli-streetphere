#!/usr/bin/env python3
"""
streetview.py  --  Google Street View Panorama Downloader
=========================================================
Accepts a Google Maps URL or a raw panoID.
Detects the panorama type automatically and uses the
matching download method:

  - Official Street View (!2e0):
    tiles from cbk0.google.com  ->  stitched into an equirectangular image

  - User photo sphere (!2e1, !2e10, etc.):
    direct download from lh3.googleusercontent.com

Usage:
    python streetview.py

Dependencies: requests, Pillow  (see setup.bat)
"""

import os
import re
import sys
import json
import time
import math
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import numpy as np
from PIL import Image
from io import BytesIO


# ==============================================================================
#  CONFIGURATION
# ==============================================================================

DEFAULT_ZOOM = 4   # Default value when the user just presses Enter

OUT_DIR      = os.path.join("output", "spheres")
TILES_DIR    = os.path.join(OUT_DIR, "tiles")
JPEG_QUALITY = 95
TIMEOUT      = 20
RETRIES      = 2
MAX_WORKERS  = 8

# -- Horizon levelling (de-tilt)
TILT_THRESHOLD_DEG = 0.5   # below this: pano considered straight, no correction
PHOTOMETA_URL      = "https://www.google.com/maps/photometa/v1"


# ==============================================================================
#  INTERNAL DATA
# ==============================================================================

GRID = {
    0: (1,  1),
    1: (2,  1),
    2: (4,  2),
    3: (8,  4),
    4: (16, 8),
    5: (26, 13),
}

TILE_SIZE        = 512
TILE_API_URL     = "https://cbk0.google.com/cbk?output=tile&panoid={pano}&zoom={zoom}&x={x}&y={y}"
TILE_API_URL_ALT = "https://streetviewpixels-pa.googleapis.com/v1/tile?cb_client=maps_sv.tactile&panoid={pano}&zoom={zoom}&x={x}&y={y}"

_PANOID_RE = re.compile(r"[A-Za-z0-9_\-]{20,25}")


# ==============================================================================
#  URL PARSING
# ==============================================================================

def extract_pano_id(text):
    text = text.strip()
    decoded = urllib.parse.unquote(text)

    m = re.search(r"panoid[=:]([A-Za-z0-9_\-]{20,25})", decoded)
    if m:
        return m.group(1)

    m = re.search(r"!1s([A-Za-z0-9_\-]{20,25})!", text)
    if m:
        return m.group(1)

    if _PANOID_RE.fullmatch(text):
        return text

    return None


def parse_url_metadata(url):
    decoded = urllib.parse.unquote(url)

    pano_type = 0
    m = re.search(r"!2e(\d+)", decoded)
    if m:
        pano_type = int(m.group(1))

    width, height = None, None
    m = re.search(r"!7i(\d+)", decoded)
    if m:
        width = int(m.group(1))
    m = re.search(r"!8i(\d+)", decoded)
    if m:
        height = int(m.group(1))

    photo_url = None
    m = re.search(r"!6s(https://[^\s!]+)", decoded)
    if m:
        raw = urllib.parse.unquote(m.group(1))
        base = re.match(r"(https://[A-Za-z0-9._/\-]+)", raw)
        if base:
            photo_url = base.group(1)

    return {
        "pano_type": pano_type,
        "width":     width,
        "height":    height,
        "photo_url": photo_url,
    }


# ==============================================================================
#  ZOOM SELECTION (interactive)
# ==============================================================================

def ask_zoom():
    print()
    print("  Choose the resolution level:")
    print()
    print("    3  ->   4 096 x  2 048 px    32 tiles   low resolution")
    print("    4  ->   8 192 x  4 096 px   128 tiles   recommended  <--")
    print("    5  ->  13 312 x  6 656 px   338 tiles   high resolution")
    print("           Careful with zoom 5: Google does not always serve every")
    print("           tile -- the missing areas stay black.")
    print()

    while True:
        raw = input(f"  Zoom [Enter = {DEFAULT_ZOOM}] : ").strip()

        if raw == "":
            return DEFAULT_ZOOM

        if raw in ("3", "4", "5"):
            return int(raw)

        print(f"  Invalid value. Enter 3, 4 or 5 (or Enter for {DEFAULT_ZOOM}).")


# ==============================================================================
#  METHOD A -- OFFICIAL STREET VIEW: tile stitching
# ==============================================================================

def _download_tile(session, pano_id, zoom, x, y):
    last_err = "unknown"
    for url_template in (TILE_API_URL_ALT, TILE_API_URL):
        url = url_template.format(pano=pano_id, zoom=zoom, x=x, y=y)
        for attempt in range(1, RETRIES + 2):
            try:
                r = session.get(url, timeout=TIMEOUT)
                r.raise_for_status()
                return Image.open(BytesIO(r.content)).convert("RGB"), None
            except requests.exceptions.HTTPError as e:
                last_err = f"HTTP {e.response.status_code}"
                if e.response.status_code == 403:
                    break
            except requests.exceptions.Timeout:
                last_err = "timeout"
            except requests.exceptions.ConnectionError:
                last_err = "connection refused"
            except Exception as e:
                last_err = str(e)
            if attempt <= RETRIES:
                time.sleep(1.5)
    return None, last_err


def _progress_bar(done, total, width=35):
    pct    = done / total if total else 0
    filled = int(width * pct)
    return f"[{'█' * filled}{'░' * (width - filled)}] {done:3d}/{total}  {pct*100:5.1f}%"


def download_streetview_tiles(session, pano_id, zoom):
    if zoom not in GRID:
        print(f"[ERROR] zoom={zoom} invalid.")
        return None

    cols, rows = GRID[zoom]
    total      = cols * rows
    workers    = max(1, MAX_WORKERS)

    print()
    print(f"  Method      : official Street View tiles")
    print(f"  Zoom        : {zoom}  ->  {cols * TILE_SIZE} x {rows * TILE_SIZE} px")
    print(f"  Total tiles : {total}  ({cols}x{rows})")
    print(f"  Parallelism : {workers} workers")
    if zoom == 5:
        print(f"  Careful     : some tiles may be unavailable (black areas)")
    print()

    tiles_subdir = os.path.join(TILES_DIR, pano_id)
    os.makedirs(tiles_subdir, exist_ok=True)

    tiles_dict = {}
    ok_count   = 0
    fail_count = 0
    done       = 0
    lock       = threading.Lock()

    def _fetch_and_report(x, y):
        img, err = _download_tile(session, pano_id, zoom, x, y)
        return x, y, img, err

    coords = [(x, y) for y in range(rows) for x in range(cols)]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fetch_and_report, x, y): (x, y) for x, y in coords}
        for future in as_completed(futures):
            x, y, img, err = future.result()
            with lock:
                done += 1
                if img is not None:
                    path = os.path.join(tiles_subdir, f"tile_{x:02d}_{y:02d}.jpg")
                    img.save(path, "JPEG", quality=JPEG_QUALITY)
                    tiles_dict[(x, y)] = img
                    ok_count += 1
                    status = " OK "
                    suffix = ""
                else:
                    fail_count += 1
                    status = "FAIL"
                    suffix = f"  -- {err}"
                print(f"  [{status}] tile ({x:02d},{y:02d})  {_progress_bar(done, total)}{suffix}", flush=True)

    print()
    print(f"  Summary : {ok_count}/{total} OK  |  {fail_count} failed")

    if ok_count == 0:
        print("[ERROR] No tile received. Check the panoID.")
        return None

    if fail_count > 0:
        print(f"  {fail_count} missing tile(s) -> black areas in the final image")

    print()
    print("  Stitching...")
    panorama = Image.new("RGB", (cols * TILE_SIZE, rows * TILE_SIZE), (0, 0, 0))
    for (x, y), img in tiles_dict.items():
        panorama.paste(img, (x * TILE_SIZE, y * TILE_SIZE))
    return panorama


# ==============================================================================
#  METHOD B -- USER PHOTO SPHERE: direct CDN download
# ==============================================================================

def download_photo_sphere(session, photo_url, width, height):
    if not photo_url:
        print("[ERROR] CDN URL not found in the Google Maps link.")
        print("  Copy the URL straight from the Street View address bar.")
        return None

    if not width or not height:
        width, height = 8192, 4096
        print(f"  Dimensions not detected, fallback: {width}x{height}")

    cdn_url = f"{photo_url}=w{width}-h{height}-k-no"

    print(f"  Method   : user photo sphere (direct CDN)")
    print(f"  Size     : {width} x {height} px")
    print(f"  CDN URL  : {cdn_url[:80]}...")
    print()
    print("  Downloading...", flush=True)

    for attempt in range(1, RETRIES + 2):
        try:
            r = session.get(cdn_url, timeout=60, stream=True)
            r.raise_for_status()

            content = b""
            total_size = int(r.headers.get("Content-Length", 0))
            downloaded = 0
            for chunk in r.iter_content(chunk_size=65536):
                content += chunk
                downloaded += len(chunk)
                if total_size:
                    pct = downloaded / total_size * 100
                    print(f"\r  Received : {downloaded/1024/1024:.1f} MB / {total_size/1024/1024:.1f} MB  ({pct:.0f}%)", end="", flush=True)

            print()
            img = Image.open(BytesIO(content)).convert("RGB")
            print(f"  [OK] Image received : {img.width}x{img.height} px")
            return img

        except requests.exceptions.Timeout:
            err = "timeout"
        except requests.exceptions.HTTPError as e:
            err = f"HTTP {e.response.status_code}"
        except Exception as e:
            err = str(e)

        print(f"\n  [Attempt {attempt}] Failed : {err}")
        if attempt <= RETRIES:
            time.sleep(2)

    print(f"[ERROR] Could not download the photo sphere : {err}")
    return None


# ==============================================================================
#  HORIZON LEVELLING (DE-TILT)
# ==============================================================================
#
#  Third-party photo spheres (trail cams, helmets, bikes...) are often uploaded
#  TILTED. Google stores the pose (heading/pitch/roll) and levels the horizon
#  on display -- but the JPEG served by the CDN stays tilted. Hence the
#  "smile/frown" effect: horizon dipping in the middle, rising at the edges.
#
#  Here we: 1) fetch the pose from Google's photometa endpoint
#           2) if the tilt is not close to 0, apply a 3D rotation of the
#              equirectangular sphere to bring the horizon back to flat.
#  Only pitch + roll matter for levelling (heading merely turns the view
#  horizontally, it does not bend the horizon).


def _pose_matrix(heading_deg, pitch_deg, roll_deg):
    """Camera->world rotation matrix. Frame: X right, Y up, Z forward."""
    h = math.radians(heading_deg); p = math.radians(pitch_deg); r = math.radians(roll_deg)
    ch, sh = math.cos(h), math.sin(h)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    Ry = np.array([[ch, 0, sh], [0, 1, 0], [-sh, 0, ch]], dtype=np.float64)  # heading
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], dtype=np.float64)  # pitch
    Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]], dtype=np.float64)  # roll
    return Ry @ Rx @ Rz


def relevel_equirect(img, pitch_deg, roll_deg, heading_deg=0.0, block=384):
    """Levels a 2:1 equirectangular image by cancelling pitch/roll.

    Vectorised inverse remap (numpy), bilinear sampling with horizontal
    wrap-around. Processed in blocks of rows to stay light on memory
    even at 7680x3840.
    """
    src = np.asarray(img.convert("RGB"))            # H,W,3 uint8
    H, W = src.shape[:2]
    Rt = _pose_matrix(heading_deg, pitch_deg, roll_deg).T   # world->camera
    out = np.empty((H, W, 3), dtype=np.uint8)

    cols = (np.arange(W, dtype=np.float64) + 0.5) / W
    lon = cols * 2 * np.pi - np.pi
    sin_lon = np.sin(lon); cos_lon = np.cos(lon)

    for y0 in range(0, H, block):
        y1 = min(y0 + block, H)
        rows = (np.arange(y0, y1, dtype=np.float64) + 0.5) / H
        lat = np.pi / 2 - rows * np.pi
        clat = np.cos(lat)[:, None]; slat = np.sin(lat)[:, None]

        dx = clat * sin_lon[None, :]
        dy = np.broadcast_to(slat, (y1 - y0, W))
        dz = clat * cos_lon[None, :]

        sx = Rt[0, 0] * dx + Rt[0, 1] * dy + Rt[0, 2] * dz
        sy = Rt[1, 0] * dx + Rt[1, 1] * dy + Rt[1, 2] * dz
        sz = Rt[2, 0] * dx + Rt[2, 1] * dy + Rt[2, 2] * dz

        lon_s = np.arctan2(sx, sz)
        lat_s = np.arcsin(np.clip(sy, -1.0, 1.0))
        u = (lon_s + np.pi) / (2 * np.pi) * W - 0.5
        v = (np.pi / 2 - lat_s) / np.pi * H - 0.5

        u0 = np.floor(u).astype(np.int64); fu = (u - u0).astype(np.float32)[..., None]
        v0 = np.floor(v).astype(np.int64); fv = (v - v0).astype(np.float32)[..., None]
        u0m = np.mod(u0, W); u1m = np.mod(u0 + 1, W)
        v0c = np.clip(v0, 0, H - 1); v1c = np.clip(v0 + 1, 0, H - 1)

        p00 = src[v0c, u0m].astype(np.float32); p01 = src[v0c, u1m].astype(np.float32)
        p10 = src[v1c, u0m].astype(np.float32); p11 = src[v1c, u1m].astype(np.float32)
        top = p00 * (1 - fu) + p01 * fu
        bot = p10 * (1 - fu) + p11 * fu
        out[y0:y1] = np.clip(top * (1 - fv) + bot * fv + 0.5, 0, 255).astype(np.uint8)

    return Image.fromarray(out, "RGB")


# photometa request. The !1e{idt} token = ID type:
#   1e2  -> official Street View    1e10 -> third-party photo sphere / 360
# We try both: the right one returns ~350 kB, the wrong one ~74 bytes (empty).
_PHOTOMETA_PB = (
    "!1m4!1smaps_sv.tactile!11m2!2m1!1b1!2m2!1sen!2sus"
    "!3m3!1m2!1e{idt}!2s{pano}!4m57!1e1!1e2!1e3!1e4!1e5!1e6!1e8!1e12"
    "!2m1!1e1!4m1!1i48!5m1!1e1!5m1!1e2!6m1!1e1!6m1!1e2"
    "!9m36!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3!1m3!1e3!2b1!3e2"
    "!1m3!1e3!2b0!3e3!1m3!1e8!2b0!3e3!1m3!1e1!2b0!3e3"
    "!1m3!1e4!2b0!3e3!1m3!1e10!2b1!3e2!1m3!1e10!2b0!3e3"
)


def fetch_pano_pose(session, pano_id):
    """Fetches the pose (heading/pitch/roll in degrees) from the photometa endpoint.

    NB: INTERNAL, undocumented Google endpoint. The index path can change on
    Google's side -> everything is best-effort plus guard rails. On failure we
    return None and the user can type the tilt in by hand.

    Google's triple [1][0][5][0][1][2] = [heading, tilt, roll] in degrees, where
    'tilt' follows the convention 90 = horizon (like the 't' in Google Maps URLs).
    From it we derive pitch = tilt - 90 (the real deviation) and roll brought
    back into [-180, 180].
    """
    for idt in (10, 2):                           # 10 = third-party, 2 = official SV
        pb = _PHOTOMETA_PB.format(idt=idt, pano=pano_id)
        try:
            r = session.get(PHOTOMETA_URL, params={"authuser": "0", "hl": "en",
                                                   "gl": "us", "pb": pb}, timeout=TIMEOUT)
            r.raise_for_status()
            txt = r.text
            data = json.loads(txt[txt.find("["):])    # strip the ")]}'" prefix
            node = data[1][0][5][0][1][2]
            heading, tilt, roll_raw = float(node[0]), float(node[1]), float(node[2])
        except Exception:
            continue                                   # empty reply / bad format -> try the other

        pitch = tilt - 90.0
        roll  = ((roll_raw + 180.0) % 360.0) - 180.0

        # Guard rail: levelling stays moderate. Otherwise we probably grabbed
        # the wrong field -> better to refuse than to twist a correct pano.
        if abs(pitch) <= 45.0 and abs(roll) <= 45.0:
            return {"heading": heading % 360.0, "pitch": pitch, "roll": roll}

    return None


def _ask_tilt(detected):
    """Asks what to do. Returns the (pitch, roll) to apply, or None to skip."""
    has_sugg = detected is not None
    sugg = (has_sugg and (abs(detected["pitch"]) >= TILT_THRESHOLD_DEG
                          or abs(detected["roll"]) >= TILT_THRESHOLD_DEG))

    print()
    if has_sugg:
        print(f"  Google pose : pitch={detected['pitch']:+.2f}  roll={detected['roll']:+.2f}"
              f"  (heading={detected['heading']:.1f})")
        if not sugg:
            print(f"  Tilt close to 0 (<{TILT_THRESHOLD_DEG} deg) -> no levelling needed.")
    else:
        print("  Pose not retrieved from Google (metadata unavailable).")

    if sugg:
        hint = "[Enter]=level (inverse of the pose), n=skip, or manual 'pitch roll'"
        default_apply = (-detected["pitch"], -detected["roll"])   # correction = inverse pose
    else:
        hint = "[Enter]=skip, or type a manual 'pitch roll' (e.g. 2.5 -1)"
        default_apply = None

    while True:
        ans = input(f"  Level the horizon? {hint} > ").strip().lower()
        if ans == "":
            return default_apply
        if ans in ("n", "no", "non"):
            return None
        if ans in ("y", "yes", "o", "oui"):
            if has_sugg:
                return (-detected["pitch"], -detected["roll"])
            print("  No detected value to apply -- type two numbers 'pitch roll'.")
            continue
        parts = ans.replace(",", " ").split()
        try:
            if len(parts) == 1:
                return (float(parts[0]), 0.0)
            if len(parts) >= 2:
                return (float(parts[0]), float(parts[1]))
        except ValueError:
            pass
        print("  Invalid answer. Enter, 'n', or two numbers 'pitch roll'.")


def maybe_relevel(session, pano_id, panorama, output):
    """Offers and applies levelling. Non-destructive: writes a '_leveled.jpg'
    file next to the original (which is never modified)."""
    detected = fetch_pano_pose(session, pano_id)
    choice = _ask_tilt(detected)
    if choice is None:
        return
    pitch, roll = choice

    print(f"  Levelling : pitch={pitch:+.2f}  roll={roll:+.2f} ...", flush=True)
    leveled = relevel_equirect(panorama, pitch, roll)
    leveled_path = re.sub(r"\.jpg$", "_leveled.jpg", output)
    leveled.save(leveled_path, "JPEG", quality=JPEG_QUALITY)
    print(f"  [OK] Horizon levelled -> {leveled_path}")
    print("       (the uncorrected original is kept)")
    print("       If the curve flips instead of being corrected, run it again")
    print("       with negated values (e.g. -2.5 1 instead of 2.5 -1).")


# ==============================================================================
#  MAIN PROGRAM
# ==============================================================================

PANO_TYPE_LABELS = {
    0:  "Official Street View",
    1:  "User photo (Google Maps)",
    2:  "Trusted contributor",
    10: "Third-party photo sphere / 360",
}

def process_url(session, raw):
    """Handles one URL/panoID: download, save, levelling.
    Used by the interactive loop and by the combined mode (both.py)."""
    # -- panoID extraction
    pano_id = extract_pano_id(raw)
    if not pano_id:
        print("  [ERROR] Could not extract a panoID. Check the URL.")
        return

    meta = parse_url_metadata(raw) if raw.startswith("http") else {
        "pano_type": 0, "width": None, "height": None, "photo_url": None
    }

    pano_type  = meta["pano_type"]
    type_label = PANO_TYPE_LABELS.get(pano_type, f"Unknown type ({pano_type})")

    print()
    print("=" * 62)
    print(f"  PanoID   : {pano_id}")
    print(f"  Type     : {type_label}")
    if meta["width"] and meta["height"]:
        print(f"  Max res. : {meta['width']} x {meta['height']} px")
    print("=" * 62)

    # -- Zoom selection
    if pano_type == 0:
        zoom = ask_zoom()
    else:
        zoom = DEFAULT_ZOOM
        print()
        print("  (Photo sphere: zoom has no effect, original resolution used)")

    # -- Download
    if pano_type == 0:
        panorama = download_streetview_tiles(session, pano_id, zoom)
        output   = os.path.join(OUT_DIR, f"panorama_{pano_id}_z{zoom}.jpg")
    else:
        panorama = download_photo_sphere(
            session,
            meta["photo_url"],
            meta["width"],
            meta["height"],
        )
        output = os.path.join(OUT_DIR, f"panorama_{pano_id}.jpg")

    if panorama is None:
        print("  Download failed. Try another URL.")
        return

    # -- Save
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"  Saving -> {output}")
    panorama.save(output, "JPEG", quality=JPEG_QUALITY)

    w, h    = panorama.size
    size_mb = os.path.getsize(output) / (1024 * 1024)
    ratio   = w / h if h else 0

    print()
    print("=" * 62)
    print(f"  DONE  --  {output}")
    print(f"  Dimensions : {w} x {h} px")
    print(f"  Ratio      : {ratio:.2f}:1  (target 2.00:1)")
    print(f"  Size       : {size_mb:.1f} MB")
    print("=" * 62)

    # -- Optional horizon levelling (non-destructive)
    maybe_relevel(session, pano_id, panorama, output)

    print()
    print("  Ready to use as a spherical map in 3ds Max + V-Ray.")


def main():

    print()
    print("=" * 62)
    print("  Street View Panorama Downloader")
    print("  [Q + Enter] to quit")
    print("=" * 62)

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

        while True:

            # -- URL input
            print()
            print("  New Google Maps URL or panoID:")
            print()
            raw = input("  > ").strip()

            if not raw:
                continue

            if raw.lower() == "q":
                print()
                print("  Goodbye.")
                print()
                break

            process_url(session, raw)


if __name__ == "__main__":
    main()
