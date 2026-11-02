# SimpleHex for FreeCAD

Open source FreeCAD workbench that fills a closed sketch or planar face with a parametric hexagon (honeycomb) pattern. Useful for 3D-print lightweighting, vents and grilles, and laser/plasma sheet parts.

**Status:** early development (milestone M5 done). Not yet in the Addon Manager.

## Install (development)
Not yet in the Addon Manager catalog. Clone the repository into your FreeCAD `Mod` folder (FreeCAD 1.1 on Linux shown; 1.0 uses `v1-0`):

    git clone https://github.com/twisted-builds-llc/hexagons_for_FreeCAD.git ~/.local/share/FreeCAD/v1-1/Mod/SimpleHex

Restart FreeCAD and pick the **SimpleHex** workbench. Update later with `git pull` in that folder.

Alternatively, add `https://github.com/twisted-builds-llc/hexagons_for_FreeCAD` (branch `main`) under **Addon Manager → Preferences → Custom repositories**, then install SimpleHex from the Addon Manager.

## Use
1. Select a closed sketch (holes allowed) or a planar face.
2. Click **SimpleHex → Hex Fill Region**.
3. Set cell size, wall, margin, corner radius, angle, edge mode and output in the task panel. The preview updates live. Double-click the object later to edit it.
4. For laser/plasma, select the SimpleHex and use **SimpleHex → Export to DXF**. The source outline is exported with it.

Edge modes: **WholeOnly** keeps only complete cells (no slivers), **Clip** trims edge cells to the margin, **ClipMinArea** trims but drops pieces smaller than `MinCellFraction` of a cell.

### Curved surfaces
Select one curved face and use the same commands:
- **Hex Fill Region** makes a **HexSurface**: the cell solids, for you to cut from or fuse to the part. `Mode` Cut (recess, or through the wall with `Depth` 0) or Emboss (raised cells).
- **Hex Fill Cut / Hex Fill Pad** on a face inside a Body make the PartDesign equivalents.

Cells are unrolled exactly, so they keep their true size on the surface. Walls follow the surface normal, so through-holes narrow towards the axis. On a full 360° cylinder the pitch is adjusted so a whole number of cells fits around; the read-only `Pitch` shows the value used. `Angle` must be 0 for a full wrap. On cones the seam is treated as an edge (no wrap).

Other curved faces (B-spline, sphere, ...) use **projection**: the flat pattern is laid out in a plane at the middle of the face and projected onto it along the normal there, so cells look regular seen from that direction and stretch slightly on slopes (by 1/cos of the tilt). Recess floors and emboss tops sit Depth below/above the surface, measured along the surface normal. Meant for gently curved faces; faces that turn more than 75° away are refused.

Curved Booleans are much slower than flat ones (about 3–11 s for ~120 cells on a tube, more with rounded corners), so live preview is off by default for curved faces; use **Refresh** in the task panel.

### PartDesign
Select a sketch or a planar face inside a Body and click **Hex Fill Cut** or **Hex Fill Pad**. These are native Body features: they sit in the tree like a Pocket or Pad and update when the sketch changes.
- **Hex Fill Cut:** `Depth` 0 cuts through all, on both sides of the sketch. A positive depth cuts into the material, against the sketch normal; tick `Reversed` to flip.
- **Hex Fill Pad:** raises the cells by `Depth`, along the face's outward normal or the sketch normal.

## Development
    python3 -m venv .venv && .venv/bin/pip install pytest
    .venv/bin/pytest
    freecadcmd tests/fc/test_features.py                         # needs FreeCAD
    QT_QPA_PLATFORM=offscreen freecad tests/fc/test_gui.py       # GUI smoke test

## License
LGPL-2.1-or-later. See `LICENSE`.
