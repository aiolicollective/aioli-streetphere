# satmap — flat satellite image, true to scale

Downloads the satellite imagery around a point as a **square image, north up,
centred on the point**, at a known scale in metres. It replaces screenshots of
Google Maps, which lose resolution as soon as you zoom out.

The image uses **the same frame as the 3D module** (earth3d): with the same
point and the same radius, it lies exactly under the 3D mesh.

## How it works

1. You paste a Google Maps URL (or `lat, lng`), exactly as for the other modes.
2. You give a radius in metres (default 150 m, max 10,000 m). The image covers
   the **whole square** of 2 × radius on each side, corners included (the 3D
   module keeps a disc; the satellite square contains that disc).
3. The script checks, at the centre of the square, the finest zoom level where
   Google has a real image (up to zoom 20).
4. It shows the resolutions available, finest first, with what each one costs:

   ```
       zoom    m/px     image side     tiles to download
         20    0.13     92527 px (  > 16K)     131406
         19    0.26     46264 px (  > 16K)      33124
         18    0.52     23132 px (  > 16K)       8464  <-- suggested
         17    1.04     11566 px (1 image)       2162
   ```

   The suggestion is the finest zoom that stays under ~10,000 tiles; [Enter]
   takes it, or type another zoom. When only one level makes sense (small
   areas), there is nothing to choose.
5. **Up to 16,384 px**: one image, at the native resolution of that zoom —
   never upscaled, never reduced.
   **Beyond 16,384 px**, two choices:
   - [Enter] **cut** into N × N equal square pieces, no reduction
     (e.g. 2 × 2 pieces of 11,566 px, each covering 6,000 × 6,000 m);
   - [r] **reduce** once (Lanczos) to a single 16,384 px image. That is
     sharper than taking the next zoom level down.
6. An optional short name (e.g. `wadirum`), as in earth3d, and whether to also
   write a textured OBJ plane ([Enter] = yes).
7. The tiles are downloaded (4 at a time, with retries), then reprojected
   pixel by pixel into the local square (see *Scale* below), and saved as JPEG.

## Output

Folder `output/sat/<prefix>/`, same prefix logic as earth3d:
`[name_]29p5770N_35p4200E_r6000_sat18` (optional name + GPS + radius +
`sat` and the zoom; the 3D module writes `d19` for its detail in the same place).
Every image name also says **how many metres it covers**:

| File | Content |
|---|---|
| `<prefix>_12000m.jpg` | one image covering 12,000 × 12,000 m |
| `<prefix>_6000m_r1c1.jpg` … | pieces of a grid (here 2 × 2), each 6,000 × 6,000 m; `r1` = north row, `c1` = west column |
| `<prefix>.txt` | centre, zoom, m/px, and for each image its size in metres and the position of its centre (east / north, in metres, from the point) |
| `<prefix>.obj` / `.mtl` | optional: one flat textured square per image, at its place |

Only letters, digits and `_` in the names; a decimal size is written with `p`
(e.g. `1714p29m`), like the GPS. Without a name, a grid piece is
`29p5770N_35p4200E_r6000_sat18_6000m_r1c1.jpg`: about as long as the 3D files.

The downloaded tiles stay in `output/sat/_cache/`: an interrupted download
(Ctrl+C, connection lost, Google refusing) resumes where it stopped when you
run the same point again, and a second run at the same zoom (to cut instead
of reduce, for instance) downloads nothing. Delete that folder whenever you want.

## Using it with the 3D mesh

**The OBJ plane.** Import `<prefix>.obj` like the mesh (3ds Max: tick
*Import materials*; Blender: *Wavefront (.obj)*). Each image arrives as a flat
square, textured, at the right size and place: centre of the square at 0,0,
north up, 1 unit = 1 m, same axes as earth3d. With a grid, every piece lands
next to its neighbours, nothing to place by hand.

The plane is at height 0, which in an earth3d extraction is the lowest point
of the mesh: it sits under the terrain. Move it up or down if needed.

A typical use: a 3D extraction with a small radius at high detail, and the
satellite image over a much larger radius around it, as context.

**Without the OBJ.** The `.txt` file gives everything to build the planes by
hand: a plane of *size* × *size* metres, at X = centre east, Y = centre north
(Z up, in Max and Blender).

**In Photoshop.** The pieces of a grid are all the same size and touch exactly:
put them side by side, `r1c1` at the top left.

## Scale: the mesh's metres, on purpose

Web Mercator imagery is not at a constant scale: the metres per pixel change
with the latitude, even inside a few kilometres. Resizing a Google Maps crop in
one go would put the corners of a 12 km square about 3 m off (9 m at 20 km).
The script reprojects every pixel instead: tests put known points at less than
0.2 px from their exact position.

The reference is the **earth3d mesh**, not the true WGS84 metres. The 3D
module places the data on the Google Earth sphere (radius 6,371,010 m, verified
in v2.3), and on that sphere distances are slightly off from true ground
distances: at 30° latitude, about **+0.3 % north-south and -0.2 % east-west**,
i.e. ~3 m per km (the exact figures depend on the latitude). The satellite image
follows the mesh, so the two line up exactly — at the price of that same small
gap when you compare with the measuring tool of Google Maps. For
previsualisation it does not show; it is documented here so that nobody is
surprised by a measurement.

## Limits

- Unofficial access to the Google Maps satellite tiles: it may stop working
  without notice. Personal / research use; the imagery remains the property of
  Google (see CREDITS.md).
- Google may refuse too many requests: the script slows down, retries, and
  stops cleanly if the refusals go on — run it again later, it resumes.
- The zoom check looks at the centre only; a tile missing elsewhere comes out
  as flat grey, with a warning. At the finest zooms Google sometimes serves
  upscaled imagery: the table cannot tell, compare two zooms if in doubt.
- The imagery is not always from the same date as the 3D textures.
- JPEG only (a 16K PNG would weigh several hundred MB).
- Needs the venv (setup.bat): requests + Pillow, nothing more.
