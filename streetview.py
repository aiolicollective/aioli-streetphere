#!/usr/bin/env python3
"""
streetview.py  --  Google Street View Panorama Downloader
=========================================================
Accepte une URL Google Maps ou un panoID brut.
Detecte automatiquement le type de panorama et utilise
la methode de telechargement appropriee :

  - Street View officiel (!2e0) :
    tiles via cbk0.google.com  ->  assemblage en equirectangulaire

  - Photo sphere utilisateur (!2e1, !2e10, etc.) :
    telechargement direct depuis lh3.googleusercontent.com

Utilisation :
    python streetview.py

Dependances : requests, Pillow  (voir setup.bat)
"""

import os
import re
import sys
import time
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from PIL import Image
from io import BytesIO


# ==============================================================================
#  CONFIGURATION
# ==============================================================================

DEFAULT_ZOOM = 4   # Valeur par defaut si l'utilisateur appuie sur Entree

TILES_DIR    = "tiles"
JPEG_QUALITY = 95
TIMEOUT      = 20
RETRIES      = 2
MAX_WORKERS  = 8


# ==============================================================================
#  DONNEES INTERNES
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
#  ANALYSE DE L'URL
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
#  CHOIX DU ZOOM (interactif)
# ==============================================================================

def ask_zoom():
    print()
    print("  Choisissez le niveau de resolution :")
    print()
    print("    3  ->   4 096 x  2 048 px   32 tuiles   basse resolution")
    print("    4  ->   8 192 x  4 096 px  128 tuiles   recommande  <--")
    print("    5  ->  13 312 x  6 656 px  338 tuiles   haute resolution, lent")
    print()

    while True:
        raw = input(f"  Zoom [Entree = {DEFAULT_ZOOM}] : ").strip()

        if raw == "":
            return DEFAULT_ZOOM

        if raw in ("3", "4", "5"):
            return int(raw)

        print(f"  Valeur invalide. Entrez 3, 4 ou 5 (ou Entree pour {DEFAULT_ZOOM}).")


# ==============================================================================
#  METHODE A -- STREET VIEW OFFICIEL : assemblage de tiles
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
                last_err = "connexion refusee"
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
        print(f"[ERREUR] zoom={zoom} invalide.")
        return None

    cols, rows = GRID[zoom]
    total      = cols * rows
    workers    = max(1, MAX_WORKERS)

    print()
    print(f"  Methode     : tiles Street View officiel")
    print(f"  Zoom        : {zoom}  ->  {cols * TILE_SIZE} x {rows * TILE_SIZE} px")
    print(f"  Total tiles : {total}  ({cols}x{rows})")
    print(f"  Parallelisme: {workers} workers")
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
    print(f"  Bilan : {ok_count}/{total} OK  |  {fail_count} echecs")

    if ok_count == 0:
        print("[ERREUR] Aucune tile recue. Verifiez le panoID.")
        return None

    if fail_count > 0:
        print(f"  Attention : {fail_count/total*100:.1f}% manquantes -> zones noires")

    print()
    print("  Assemblage...")
    panorama = Image.new("RGB", (cols * TILE_SIZE, rows * TILE_SIZE), (0, 0, 0))
    for (x, y), img in tiles_dict.items():
        panorama.paste(img, (x * TILE_SIZE, y * TILE_SIZE))
    return panorama


# ==============================================================================
#  METHODE B -- PHOTO SPHERE UTILISATEUR : telechargement direct CDN
# ==============================================================================

def download_photo_sphere(session, photo_url, width, height):
    if not photo_url:
        print("[ERREUR] URL CDN introuvable dans le lien Google Maps.")
        print("  Copiez l'URL directement depuis la barre d'adresse Street View.")
        return None

    if not width or not height:
        width, height = 8192, 4096
        print(f"  Dimensions non detectees, fallback : {width}x{height}")

    cdn_url = f"{photo_url}=w{width}-h{height}-k-no"

    print(f"  Methode  : photo sphere utilisateur (CDN direct)")
    print(f"  Taille   : {width} x {height} px")
    print(f"  URL CDN  : {cdn_url[:80]}...")
    print()
    print("  Telechargement en cours...", flush=True)

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
                    print(f"\r  Recu : {downloaded/1024/1024:.1f} Mo / {total_size/1024/1024:.1f} Mo  ({pct:.0f}%)", end="", flush=True)

            print()
            img = Image.open(BytesIO(content)).convert("RGB")
            print(f"  [OK] Image recue : {img.width}x{img.height} px")
            return img

        except requests.exceptions.Timeout:
            err = "timeout"
        except requests.exceptions.HTTPError as e:
            err = f"HTTP {e.response.status_code}"
        except Exception as e:
            err = str(e)

        print(f"\n  [Tentative {attempt}] Echec : {err}")
        if attempt <= RETRIES:
            time.sleep(2)

    print(f"[ERREUR] Impossible de telecharger la photo sphere : {err}")
    return None


# ==============================================================================
#  PROGRAMME PRINCIPAL
# ==============================================================================

PANO_TYPE_LABELS = {
    0:  "Street View officiel",
    1:  "Photo utilisateur (Google Maps)",
    2:  "Trusted contributor",
    10: "Photo sphere / 360 tiers",
}

def main():

    print()
    print("=" * 62)
    print("  Street View Panorama Downloader")
    print("  [Q + Entree] pour quitter")
    print("=" * 62)

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

        while True:

            # -- Saisie URL
            print()
            print("  Nouvelle URL Google Maps ou panoID :")
            print()
            raw = input("  > ").strip()

            if not raw:
                continue

            if raw.lower() == "q":
                print()
                print("  Au revoir.")
                print()
                break

            # -- Extraction du panoID
            pano_id = extract_pano_id(raw)
            if not pano_id:
                print("  [ERREUR] Impossible d'extraire un panoID. Verifiez l'URL.")
                continue

            meta = parse_url_metadata(raw) if raw.startswith("http") else {
                "pano_type": 0, "width": None, "height": None, "photo_url": None
            }

            pano_type  = meta["pano_type"]
            type_label = PANO_TYPE_LABELS.get(pano_type, f"Type inconnu ({pano_type})")

            print()
            print("=" * 62)
            print(f"  PanoID   : {pano_id}")
            print(f"  Type     : {type_label}")
            if meta["width"] and meta["height"]:
                print(f"  Res. max : {meta['width']} x {meta['height']} px")
            print("=" * 62)

            # -- Choix du zoom
            if pano_type == 0:
                zoom = ask_zoom()
            else:
                zoom = DEFAULT_ZOOM
                print()
                print("  (Photo sphere : zoom sans effet, resolution d'origine utilisee)")

            # -- Telechargement
            if pano_type == 0:
                panorama = download_streetview_tiles(session, pano_id, zoom)
                output   = f"panorama_{pano_id}_z{zoom}.jpg"
            else:
                panorama = download_photo_sphere(
                    session,
                    meta["photo_url"],
                    meta["width"],
                    meta["height"],
                )
                output = f"panorama_{pano_id}.jpg"

            if panorama is None:
                print("  Echec du telechargement. Essayez une autre URL.")
                continue

            # -- Sauvegarde
            print(f"  Sauvegarde -> {output}")
            panorama.save(output, "JPEG", quality=JPEG_QUALITY)

            w, h    = panorama.size
            size_mb = os.path.getsize(output) / (1024 * 1024)
            ratio   = w / h if h else 0

            print()
            print("=" * 62)
            print(f"  TERMINE  --  {output}")
            print(f"  Dimensions : {w} x {h} px")
            print(f"  Ratio      : {ratio:.2f}:1  (cible 2.00:1)")
            print(f"  Taille     : {size_mb:.1f} Mo")
            print("=" * 62)
            print()
            print("  Utilisable comme carte spherique dans 3ds Max + V-Ray.")


if __name__ == "__main__":
    main()
