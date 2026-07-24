#!/usr/bin/env python3
"""
both.py  --  Sphere 360 + environnement 3D depuis la meme URL
=============================================================
Enchaine pour chaque URL Google Maps :
  1. le telechargement du panorama equirectangulaire (streetview.py)
  2. l'extraction du mesh 3D a l'echelle (earth3d.py)

Lance via run.bat (choix 3). Requiert le venv (setup.bat) + Node/Git.
"""

import requests

import streetview
import earth3d


def main():
    print()
    print("=" * 62)
    print("  Sphere 360 + Environnement 3D   (mode combine)")
    print("  [Q + Entree] pour quitter")
    print("=" * 62)
    print()
    print("  Verification des prerequis 3D :")
    ok_node = earth3d.check_prereq("Node.js", "node --version")
    ok_git  = earth3d.check_prereq("Git",     "git --version")
    has3d   = ok_node and ok_git and earth3d.ensure_vendor()
    if not has3d:
        print()
        print("  [!] Module 3D indisponible (prerequis manquants) :")
        print("      seules les spheres seront produites.")

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

        while True:
            print()
            print("  URL Google Maps (ou panoID) :")
            print()
            raw = input("  > ").strip()
            if not raw:
                continue
            if raw.lower() == "q":
                print()
                print("  Au revoir.")
                print()
                break

            print()
            print("  ---[ 1/2 : sphere 360 ]" + "-" * 38)
            streetview.process_url(session, raw)

            if has3d:
                print()
                print("  ---[ 2/2 : environnement 3D ]" + "-" * 32)
                earth3d.process(raw)


if __name__ == "__main__":
    main()
