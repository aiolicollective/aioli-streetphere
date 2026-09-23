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

| What | Needed for | Where |
|------|-----------|-------|
| **Python 3.8+** | everything | https://www.python.org/downloads/ |
| **Node.js** (LTS) | 3D module only — options [2] and [3] | https://nodejs.org |
| **Git** | 3D module only — options [2] and [3] | https://git-scm.com |

If you don't have Python:
1. Go to https://www.python.org/downloads/
2. Download **Python 3.12** (see the note below about very recent versions)
3. Run the installer and tick "Add Python to PATH" (important!)

**If you want the 3D module, install Node.js and Git *before* running
setup.bat.** They are not optional extras for that mode — options [2] and [3]
refuse to start without them. Option [1], the 360 sphere, needs neither.

> **Note on very recent Python versions.** Python 3.12 is the safest choice.
> A Python released very recently sometimes has no prebuilt package for Pillow
> yet; pip then tries to compile it on your machine, which fails without a C
> compiler. See [Troubleshooting](#troubleshooting) if you hit that.

---

## Installation

Two ways to get the files -- pick whichever you prefer.

**A. Zip** (no Git needed)

1. Download the project: https://github.com/aiolicollective/aioli-streetphere/archive/refs/heads/main.zip
2. Unzip it wherever you like
3. Open the unzipped folder
4. Double-click setup.bat

**B. Git clone** (easier to update later: `git pull` and you are current)

```bat
git clone https://github.com/aiolicollective/aioli-streetphere.git
cd aioli-streetphere
```

Then double-click setup.bat in that folder. Git is required by the 3D module
anyway, so if you plan to use it you already have what you need.

Either way, setup.bat does everything on its own:
- Checks for Node.js and Git straight away, and says so if either is missing
- Finds Python on your machine
- Creates an isolated virtual environment (venv) inside the folder
- Installs the dependencies (requests, Pillow, numpy)
- Offers to open the menu (streetphere.bat)

What is a virtual environment (venv)?
A venv folder is created inside the project folder. It holds a local copy of Python
and the required libraries. It does not touch the rest of your system at all.
Delete it and everything is back to how it was.

Two files to double-click, no more: **setup.bat** once to install,
**streetphere.bat** afterwards to run everything.

---

## Troubleshooting

### setup.bat: "Getting requirements to build wheel did not run successfully" (Pillow)

The log mentions a `pillow-*.tar.gz` of around 46 MB and a `KeyError`.

**Cause:** your Python is newer than the prebuilt Pillow packages available, so
pip falls back to compiling Pillow from source — which needs a C compiler you
almost certainly don't have.

**Fix:** make sure you have the current version of this repo
(`git pull`, or re-download the zip), delete the `venv` folder next to
setup.bat, and run setup.bat again. The dependency list now lets pip pick a
package built for your Python version.

If it still fails, install **Python 3.12** from
https://www.python.org/downloads/ (tick "Add Python to PATH"), delete `venv`
once more, and run setup.bat again.

### Option [2] or [3] shows `[!!] Node.js`

Node.js is not installed, or not in your PATH. Install the LTS version from
https://nodejs.org, then **close the window and start streetphere.bat again** —
Windows only picks up a newly installed program in a new window. Same thing for
`[!!] Git` with https://git-scm.com.

Option [1] (360 sphere) does not need either of them and keeps working.

### setup.bat cannot find Python

It will ask you to type the full path to `python.exe`
(e.g. `C:\Users\You\AppData\Local\Programs\Python\Python312\python.exe`).
This usually means "Add Python to PATH" was not ticked when Python was
installed — reinstalling with that box ticked is the cleaner fix.

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
- Radius up to 10 km, with a suggested level of detail for large areas
- Optional packing: a single material + a single PNG atlas (model_packed.obj),
  or a few atlases for large areas (suggested, one material each);
  in Max, tick 'Import as single mesh' to merge everything into one object
- Optional .glb export of the packed model (lighter, faster in Blender / Unreal)
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
    +-- output/3d/                3D environments (model_packed.obj/.glb + atlas)

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
