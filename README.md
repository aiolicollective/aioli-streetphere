# aioli-streetphere

> `> ai.oli/` — a tool by the [ai.oli collective](https://aiolicollective.com), Marseille.
> [Website](https://aiolicollective.com) · [Instagram](https://instagram.com/aioli.collective) · [GitHub](https://github.com/aiolicollective)
>
> Not affiliated with Google. Personal / research use, without warranty.
> See [LICENSE](LICENSE) and [CREDITS.md](CREDITS.md).

Downloads a Google Street View panorama and exports it as a 2:1 equirectangular
image, ready to use as an environment sphere in V-Ray, 3ds Max, Blender, Cinema 4D, etc.

Two modes, detected automatically:

- Official Street View: tiles assembled from the Google API (up to 13,312 x 6,656 px)
- User photo sphere: direct download from the Google CDN

Also includes a 3D module (textured, true-to-scale mesh of the surroundings —
see below and EARTH3D.md).

---

## Requirements

Python 3.8+ must be installed on your machine.

If you don't have Python:
1. Go to https://www.python.org/downloads/
2. Download the latest version (e.g. Python 3.12)
3. Run the installer and tick "Add Python to PATH" (important!)

For the 3D module only: Node.js (https://nodejs.org) and Git
(https://git-scm.com) must also be in your PATH.

---

## Installation

1. Download the project: https://github.com/aiolicollective/aioli-streetphere/archive/refs/heads/main.zip
2. Unzip it wherever you like
3. Open the unzipped folder
4. Double-click setup.bat

setup.bat does everything on its own:
- Finds Python on your machine
- Creates an isolated virtual environment (venv) inside the folder
- Installs the dependencies (requests and Pillow)
- Checks for Node.js and Git (3D module)
- Offers to open the menu (streetphere.bat)

What is a virtual environment (venv)?
A venv folder is created inside the project folder. It holds a local copy of Python
and the required libraries. It does not touch the rest of your system at all.
Delete it and everything is back to how it was.

Two files to double-click, no more: **setup.bat** once to install,
**streetphere.bat** afterwards to run everything.

---

## Usage

1. Open Google Maps in your browser
2. Switch to Street View somewhere you like
3. Copy the full URL from the address bar
4. Double-click streetphere.bat (or setup.bat the first time) and choose
   [1] 360 sphere, [2] 3D environment, or [3] both
5. Paste the URL when the program asks for it and press Enter
6. Choose the resolution level (Enter = zoom 4 by default)

The file panorama_[ID]_z[zoom].jpg is written to output/spheres/.

The program stays open after each download: paste another URL straight away
to download one more. To quit, type Q then Enter.

---

## Resolution: the ZOOM setting

Street View does not serve the panorama as a single image: it is cut into
512x512 px tiles that the script downloads and stitches. The zoom decides how
many tiles are requested, and therefore the size of the final image.

| ZOOM | Resolution          | Tiles | Use case                     |
|------|---------------------|-------|------------------------------|
| 3    | 4,096 x 2,048 px    | 32    | Quick preview                |
| 4    | 8,192 x 4,096 px    | 128   | Recommended (V-Ray, Blender) |
| 5    | 13,312 x 6,656 px   | 338   | High resolution              |

Zoom 4 is the highest reliable level: every tile is available, seamless image guaranteed.

Zoom 5 produces a larger image, but Google does not always serve every tile at
that level -- the extreme areas (sky/ground) can return errors and stay black in
the final image. The image keeps its 2:1 ratio and remains usable, but the sphere
may show artefacts at the poles. The program warns you if you pick zoom 5.

Note: this setting only applies to official Street View. For user photo spheres,
the resolution is the original resolution of the photo.

---

## Risks and limits

- Personal, educational or research use only: Street View imagery and Google
  Earth data remain the property of Google. Do not exploit the results
  commercially. Details and full disclaimer: [CREDITS.md](CREDITS.md).
- The 3D module relies on an unofficial protocol: it may stop working without
  notice, and using it may be at odds with Google's terms of service.
  It is up to you to check what your own context allows.
- Internet connection required: the script talks to Google servers.
- Street View only: regular map or satellite links will not work.
- No API key required: this tool uses the same CDNs as the browser.
  No Google account is needed.

---

## Automatic horizon levelling

Third-party photo spheres (helmet cams, bikes, backpacks...) are often uploaded
TILTED. Google knows their pose and levels the horizon on display, but the JPEG
served by the CDN stays tilted. The result: a panorama whose horizon "smiles" --
it dips in the middle and rises at the edges. Unusable as-is as an environment sphere.

The script fixes this automatically:

1. After the download, it reads the pose of the panorama (heading/pitch/roll) from
   Google's metadata (photometa endpoint).
2. If the tilt exceeds 0.5 deg, it offers to level it. [Enter] applies the inverse
   rotation to bring the horizon back to flat.
3. The result is written to a SEPARATE _leveled.jpg file -- the downloaded original
   is never modified.

If the metadata is unavailable, you can type the tilt in by hand
(two numbers: pitch roll). Levelling performs a spherical resampling (numpy):
the horizon comes back flat to within less than a pixel. Only panoramas that are
actually tilted get processed -- an already straight panorama is not resampled
for nothing.

---

## 3D module: earth3d

On top of the 2:1 sphere, the repo contains a module that downloads the textured
3D mesh of the surroundings within a radius in metres around a point (Google Earth
data, unofficial protocol -- no account, no API key) and recentres it at metric
scale for Blender / 3ds Max.

- Run it: streetphere.bat, option [2] (or [3] for sphere + 3D in one go)
- Extra requirements: Node.js and Git in the PATH (no pip dependency:
  this mode does not even need the venv)
- Radius in metres respected (geometry cropped to the requested disc)
- Exact metric scale and origin (1 unit = 1 m, ground at 0)
- Textures converted to .png (3ds Max compatibility)
- Optional packing: a single material + a single PNG atlas (model_packed.obj);
  in Max, tick 'Import as single mesh' to merge everything into one object
- Output: output/3d/<coords>_r<radius>m/
- Full documentation: EARTH3D.md

---

## Companion tool: builder.html

A standalone 360° viewer is included in the repo. Independent from the Python
script, it runs entirely locally in a browser -- nothing to install, no file ever
sent over the Internet.

Two uses:

- View any 2:1 equirectangular image in an immersive viewer
  (whether it comes from the script or elsewhere)
- Generate a standalone HTML viewer with the image embedded in base64. Handy for
  sharing a render under NDA: a single file to send, the client double-clicks and
  lands straight into the immersive view, with nothing to install

### Usage

1. Double-click builder.html
2. Drag and drop your 2:1 image (JPEG, PNG or WebP), or click to browse
3. Explore: drag to look around, scroll to zoom
4. To export a standalone viewer: down-arrow button at the bottom right, or key E

The exported HTML is named after the source image and embeds it encoded in base64.
No external dependency apart from Three.js, loaded from a CDN on first run and
cached afterwards.

The 2:1 ratio is checked automatically -- an image with the wrong ratio is
rejected cleanly rather than rendered distorted.

### Shortcuts

| Key | Action           |
|-----|------------------|
| R   | Reset the view   |
| F   | Fullscreen       |
| E   | Export to HTML   |

---

## File layout

    .
    +-- setup.bat                 Installation (venv + dependencies) -- run once
    +-- streetphere.bat           The launcher: 360 sphere / 3D / both
    +-- streetview.py             Equirectangular 360 sphere
    +-- earth3d.py                3D module: textured, true-to-scale mesh
    +-- both.py                   Combined mode: sphere + 3D from the same URL
    +-- banner.py                 Intro screen (logo, links, credits)
    +-- earth3d_radius.js         3D helper: octant selection by radius
    +-- requirements.txt          Python libraries (requests, Pillow, numpy)
    +-- builder.html              360° viewer + standalone HTML exporter (independent)
    +-- EARTH3D.md                3D module documentation
    +-- CREDITS.md                Sources, third-party licenses, disclaimer
    +-- LICENSE                   MIT (our code only)
    +-- venv/                     Created on first run, do not edit
    +-- earth3d_vendor/           Third-party exporter, cloned automatically (3D module)
    +-- output/spheres/           2:1 panoramas (+ intermediate tiles/)
    +-- output/3d/                3D environments (model_packed.obj + atlas)

---

## Credits

The 3D module builds on the reverse engineering work of
[retroplasma/earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering),
cloned at runtime (never redistributed here). The viewer uses three.js.
Full list of sources, licenses and usage disclaimer: [CREDITS.md](CREDITS.md).

Our code is MIT licensed ([LICENSE](LICENSE)) — it covers neither the downloaded
Google data, nor the third-party code, nor the collective's name and logo.

---

[ai.oli](https://aiolicollective.com) collective — victor.oli with ai.claude, 2026.
We say what is generated and by whom.
