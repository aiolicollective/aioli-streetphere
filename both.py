#!/usr/bin/env python3
"""
both.py  --  360 sphere + 3D environment + satellite image from the same URL
============================================================================
(The file keeps its historical name: it used to run the sphere and the 3D.)

For every Google Maps URL, runs in sequence:
  1. the equirectangular 360 panorama (streetview.py) -- needs a Street View link
  2. the true-to-scale 3D mesh (earth3d.py)            -- needs Node.js + Git
  3. the flat satellite image (satmap.py)

The radius and the short name are asked ONCE and shared by the 3D mesh and
the satellite image: same point + same radius, so the image lies exactly
under the mesh and both carry the same name.

Started from streetphere.bat (option 4). Needs the venv (setup.bat);
without Node.js / Git, the 3D step is skipped.
"""

import requests

import streetview
import earth3d
import satmap


class _Preset:
    """Answers earth3d's radius and name questions in advance, for one call.

    earth3d.py itself is not modified: during the call, its two question
    functions are replaced by the answers already given, then put back
    (even if the call fails)."""

    def __init__(self, radius, label):
        self.radius, self.label = radius, label

    def __enter__(self):
        self._saved = (earth3d.ask_radius, earth3d.ask_name)
        earth3d.ask_radius = lambda: self.radius
        earth3d.ask_name = lambda: self.label
        return self

    def __exit__(self, *exc):
        earth3d.ask_radius, earth3d.ask_name = self._saved
        return False


def main():
    print()
    print("=" * 62)
    print("  360 Sphere + 3D Environment + Satellite Image   (all three)")
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
        print("      only the spheres and the satellite images will be produced.")

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

        while True:
            print()
            print("  Google Maps URL (a Street View link, for the sphere):")
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
            print("  ---[ 1/3 : 360 sphere ]" + "-" * 38)
            streetview.process_url(session, raw)

            if not earth3d.extract_lat_lng(raw):
                print()
                print("  [!] No position (@lat,lng) in this link: 3D environment")
                print("      and satellite image skipped.")
                continue

            # asked once, shared by the 3D mesh and the satellite image
            print()
            print("  ---[ radius and name, shared by the 3D and the satellite ]" + "-" * 3)
            radius = earth3d.ask_radius()
            label = earth3d.ask_name()

            if has3d:
                print()
                print("  ---[ 2/3 : 3D environment ]" + "-" * 34)
                with _Preset(radius, label):
                    earth3d.process(raw)

            print()
            print("  ---[ 3/3 : satellite image ]" + "-" * 33)
            satmap.process(session, raw, radius=radius, label=label)


if __name__ == "__main__":
    main()
