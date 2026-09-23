# earth3d — Google Earth 3D → true-to-scale OBJ

Downloads the textured 3D mesh of the surroundings within a **radius in metres**
around a point (Google Earth data) and recentres it at metric scale, ready for
Blender / 3ds Max. No account, no API key, no credit card — same philosophy as
streetphere.

## How it works

1. You paste a Google Maps URL (or `lat, lng`). The script extracts the position.
2. You give a radius in metres (default 150 m, max 10,000 m) and a level of
   detail (Google Earth LOD: 17-18 light, 20 = usual maximum). The script
   suggests a detail from the radius so the volume stays manageable
   (up to 3 km → 20, up to 6 km → 19, up to 10 km → 18); [Enter] takes the
   suggestion, any other value is accepted after a volume warning.
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
   - normals rotated like the vertices (the dump's normals are geocentric),
   - the dump's `.bmp` textures (32-bit, not read properly by 3ds Max) are
     converted to `.png`, `.mtl` files cleaned up.
   - The dump is **moved** (not copied) from `earth3d_vendor/` to `output/3d/`,
     and the raw geocentric `model.obj` is deleted once recentred.
6. Optional ([Enter] = yes): **packing** — the textures go into PNG atlas(es)
   (16,384 px ceiling each, anti-seam margins), UVs remapped. Small areas:
   one atlas, one material. When the textures no longer fit in one atlas, the
   script shows the resolution each atlas count would give and suggests one
   (textures kept at about 50 % or more, 8 atlases at most); [Enter] takes it.
   Each atlas covers one contiguous area of the ground, one material per atlas.
   Textures are loaded one at a time: RAM stays at about one atlas.
   Tiles stay in `g` groups (required so that the 3ds Max OBJ importer does not
   break the geometry).
7. Optional ([Enter] = yes): **`.glb` export** of the packed model — same
   geometry and materials, binary: about 3× lighter than the OBJ and much
   faster to import in Blender or Unreal. The atlases are referenced, not
   embedded: keep the `.glb` next to its `atlas_XX.png`. For 3ds Max, stay
   on the OBJ.
8. Optional ([Enter] = keep): delete the multi-texture version
   (`model_local.*` + tile textures). It is only needed to repack with another
   atlas count without downloading again.

At the prompts that expect a number (detail, atlas count), `y` / `yes` also
takes the suggestion, like [Enter].

## Output

`output/3d/<lat>_<lng>_r<N>m_d<D>/`:

- `model_packed.obj` + `model_packed.mtl` + `atlas.png` — 1 material, 1 texture ← import this one
  (large areas: `atlas_01.png`, `atlas_02.png`… — 1 material per atlas)
- `model_packed.glb` — same, binary (optional; Blender / Unreal)
- `model_local.obj` + `model_local.mtl` + textures — multi-texture version
  (unless deleted at the end)
- `model.obj` / `model.mtl` — raw geocentric, kept only if recentring failed

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

- **Blender**: File > Import > Wavefront (.obj) → `model_packed.obj`,
  or File > Import > glTF 2.0 → `model_packed.glb` (faster).
  One single object, 1 unit = 1 m.
- **Unreal**: import `model_packed.glb` (atlases in the same folder).
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
- Atlas capped at 16,384 px: over large areas, textures are scaled down
  (reported in the log) unless you split them over several atlases.
- Detail suggestion and atlas estimates are rules of thumb (each detail level
  ≈ 4× more tiles, reference: 3 km at detail 20 ≈ 54,000 tiles, 6.9 M vertices).
- Large radii: the output folder holds the dump plus its processed copies,
  count several GB on disk (less if you delete the multi-texture version).
- The mesh is kept on the curved Earth (true geometry): the edge of a 6 km
  radius sits ~2.8 m below the tangent plane of the centre, ~7.8 m at 10 km.
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
