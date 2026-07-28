# Credits, sources and disclaimer

`aioli-streetphere` is developed by the [ai.oli](https://aiolicollective.com)
collective (Marseille, France). Our code is MIT licensed: see [LICENSE](LICENSE).

This tool would not exist without the work listed below. None of it is
redistributed in this repository: everything is downloaded at runtime, from its
original source.

---

## Disclaimer

**This project is not affiliated with, endorsed or sponsored by Google.**
Google, Google Maps, Street View and Google Earth are trademarks of Google LLC.

- The imagery and 3D models obtained remain the **property of Google and its data
  providers**. This repository neither contains nor redistributes any Google data.
- The tool is meant for **personal, educational or research use**
  (feasibility studies, working references, previsualisation).
  It grants no right to exploit the retrieved data commercially.
- The 3D module relies on an **undocumented, unofficial protocol**. It may stop
  working overnight, and using it may be at odds with the terms of service of
  Google's products.
- **It is up to each user to check what their jurisdiction and the applicable
  terms of service allow them to do.** The software is provided without warranty
  (see LICENSE): the authors cannot be held liable for how it is used.

If you need geospatial 3D data for commercial use, there is an official, licensed
route: the Google Photorealistic 3D Tiles API (Google Cloud account required).

---

## Third-party code

| Project | Role | License | How |
|---|---|---|---|
| [earth-reverse-engineering](https://github.com/retroplasma/earth-reverse-engineering) (retroplasma) | Reverse engineering of the Google Earth protocol and mesh exporter: the heart of the 3D module | **No license declared** by the author (therefore all rights reserved) | Cloned automatically into `earth3d_vendor/` on first run. Never copied nor redistributed here. |
| [three.js](https://threejs.org) | Rendering of the 360 viewer (`builder.html`) | MIT | Loaded from a CDN on the viewer's first run |
| [requests](https://requests.readthedocs.io) | HTTP requests | Apache-2.0 | Installed by `setup.bat` into the local venv |
| [Pillow](https://python-pillow.org) | Tile stitching, texture conversion | MIT-CMU / HPND | Installed by `setup.bat` into the local venv |
| [NumPy](https://numpy.org) | Spherical resampling (horizon levelling) | BSD-3-Clause | Installed by `setup.bat` into the local venv |

Special thanks to **retroplasma**: without that reverse engineering work, the 3D
module would not exist. Since that repository declares no license, we do not
redistribute it and we derive no code from it — we clone it at runtime and call
it as-is. If you reuse our code, keep it that way.

## Data sources

| Source | Use |
|---|---|
| Google Street View (`cbk0.google.com`, `lh3.googleusercontent.com`, `photometa` endpoint) | Panorama tiles and pose (heading / pitch / roll) |
| Google Earth (`kh.google.com/rt/...`) | 3D mesh and textures, through the unofficial protocol above |

No API key, no account, no payment bypass: the tool uses the same public
endpoints as the browser does when you visit Google Maps.

---

## The collective

- Website: [aiolicollective.com](https://aiolicollective.com)
- Instagram: [@aioli.collective](https://instagram.com/aioli.collective)
- GitHub: [github.com/aiolicollective](https://github.com/aiolicollective)

Tool developed by victor.oli with ai.claude. We say what is generated and by whom.
