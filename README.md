# HexFill for FreeCAD

Open source FreeCAD workbench that fills a closed sketch or planar face with a parametric hexagon (honeycomb) pattern. Useful for 3D-print lightweighting, vents and grilles, and laser/plasma sheet parts.

**Status:** early development (milestone M3 done). Not yet in the Addon Manager.

## Install (development)
Link or clone this repository into your FreeCAD `Mod` folder, e.g. on Linux:

    ln -s "$PWD" ~/.local/share/FreeCAD/Mod/HexFill

Restart FreeCAD and pick the **HexFill** workbench.

## Use
1. Select a closed sketch (holes allowed) or a planar face.
2. Click **HexFill → Hex Fill Region**.
3. Set cell size, wall, margin, corner radius, angle, edge mode and output in the task panel. The preview updates live. Double-click the object later to edit it.
4. For laser/plasma, select the HexFill and use **HexFill → Export to DXF**. The source outline is exported with it.

Edge modes: **WholeOnly** keeps only complete cells (no slivers), **Clip** trims edge cells to the margin, **ClipMinArea** trims but drops pieces smaller than `MinCellFraction` of a cell.

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
