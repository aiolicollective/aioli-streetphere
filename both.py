#!/usr/bin/env python3
"""
both.py  --  360 sphere + 3D environment from the same URL
==========================================================
For every Google Maps URL, runs in sequence:
  1. the download of the equirectangular panorama (streetview.py)
  2. the extraction of the true-to-scale 3D mesh (earth3d.py)

Started from streetphere.bat (option 3). Needs the venv (setup.bat) + Node/Git.
"""

import requests

import streetview
import earth3d


def main():
    print()
    print("=" * 62)
    print("  360 Sphere + 3D Environment   (combined mode)")
    print("  [Q + Enter] to quit")
    print("=" * 62)
    print()
    print("  Checking the 3D requirements:")
    ok_node = earth3d.check_prereq("Node.js", "node --version")
    ok_git  = earth3d.check_prereq("Git",     "git --version")
    has3d   = ok_node and ok_git and earth3d.ensure_vendor()
    if not has3d:
        print()
        print("  [!] 3D module unavailable (missing requirements):")
        print("      only the spheres will be produced.")

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

        while True:
            print()
            print("  Google Maps URL (or panoID):")
            print()
            raw = input("  > ").strip()
            if not raw:
                continue
            if raw.lower() == "q":
                print()
                print("  Goodbye.")
                print()
                break

            print()
            print("  ---[ 1/2 : 360 sphere ]" + "-" * 38)
            streetview.process_url(session, raw)

            if has3d:
                print()
                print("  ---[ 2/2 : 3D environment ]" + "-" * 34)
                earth3d.process(raw)


if __name__ == "__main__":
    main()
