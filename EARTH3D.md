# earth3d — Google Earth 3D → true-to-scale OBJ

Downloads the textured 3D mesh of the surroundings within a **radius in metres**
around a point (Google Earth data) and recentres it at metric scale, ready for
Blender / 3ds Max. No account, no API key, no credit card — same philosophy as
streetphere.

## How it works

1. You paste a Google Maps URL (or `lat, lng`). The script extracts the position.
2. You give a radius in metres (default 150 m, max 3000 m) and a level of
   detail (Google Earth LOD: 17-18 light, 20 = recommended maximum).
3. The script queries Google Earth's unofficial protocol
   (`kh.google.com/rt/…`, reverse engineered by
   [earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering),
   cloned automatically into `earth3d_vendor/` on first run) and selects the
   octants — cells of the 3D octree — covering the requested disc
   (`earth3d_radius.js`).
4. It downloads mesh + textures → `model.obj` (raw geocentric coordinates).
5. Python post-processing:
   - scale **auto-detected** (vertex norm vs Earth radius) and exact origin on
     the requested point (Google sphere convention, verified),
   - ground pinned to 0, east/north/altitude axes, standard Y-up OBJ convention,
   - **cropping to the radius**: faces outside the disc are removed (~15 m margin),
   - the dump's `.bmp` textures (32-bit, not read properly by 3ds Max) are
     converted to `.png`, `.mtl` files cleaned up.
6. Optional ([Enter] = yes): **packing** — every texture into a single PNG atlas
   (16,384 px ceiling, anti-seam margins), UVs remapped, one single material.
   Tiles stay in `g` groups (required so that the 3ds Max OBJ importer does not
   break the geometry).

## Output

`output/3d/<lat>_<lng>_r<N>m_d<D>/`:

- `model_packed.obj` + `model_packed.mtl` + `atlas.png` — 1 material, 1 texture ← import this one
- `model_local.obj` + `model_local.mtl` + textures — multi-texture version
- `model.obj` / `model.mtl` — raw geocentric (debug)

(360 spheres go to `output/spheres/` — outputs are kept consistent.)

## Usage

```bat
streetphere.bat  (option 2, or option 3 for sphere + 3D in one go)
```

Requirements: Node.js + Git in the PATH. Python is detected automatically
(venv → `py` launcher → PATH → common paths → manual entry).
The 3D mode does not need the venv: no pip dependency.
First run: automatic clone + `npm install` (~1 min).

## Import

- **Blender**: File > Import > Wavefront (.obj) → `model_packed.obj`.
  One single object, 1 unit = 1 m.
- **3ds Max**: Import OBJ → `model_packed.obj`, tick "Import materials"
  **and "Import as single mesh"** (merges the groups into one object).
  The file is in metres: if your system units are centimetres, set the
  importer's unit option (or scale ×100).

## Isolation

Nothing is installed outside the repo folder: Python = stdlib + Pillow from the
`setup.bat` venv, Node dependencies local to `earth3d_vendor/node_modules/`,
nothing global.

## Known limits

- Unofficial protocol: it can break without notice on Google's side.
- Downloading happens by whole cells before the geometry is cropped to the
  radius: the downloaded volume can exceed what is kept.
- Atlas capped at 16,384 px: over very large areas, textures are scaled down
  proportionally (reported in the log) — use the multi-texture version instead
  if resolution matters most.
- LOD: the maximum detail depends on the city's 3D coverage.
- The ground is pinned to the lowest point of the mesh (an approximation).

## Legal and credits

This module is not affiliated with Google. The downloaded meshes and textures
remain the property of Google and its data providers: previsualisation, study and
personal or research use only, no commercial exploitation of the extracted assets.
The protocol used is unofficial and using it may be at odds with Google's terms of
service — it is up to you to check what your own context allows.

The core of this module is the reverse engineering work of
[retroplasma/earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering),
cloned at runtime and never redistributed here (its repository declares no license).

Full disclaimer and list of sources: [CREDITS.md](CREDITS.md).
