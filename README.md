# HexFill for FreeCAD

Open source FreeCAD workbench that fills a closed sketch or planar face with a parametric hexagon (honeycomb) pattern. Useful for 3D-print lightweighting, vents and grilles, and laser/plasma sheet parts.

**Status:** early development (milestone M1). Not yet in the Addon Manager.

## Install (development)
Link or clone this repository into your FreeCAD `Mod` folder, e.g. on Linux:

    ln -s "$PWD" ~/.local/share/FreeCAD/Mod/HexFill

Restart FreeCAD and pick the **HexFill** workbench.

## Use
1. Select a closed sketch (holes allowed) or a planar face.
2. Click **HexFill → Hex Fill Region**.
3. Edit `CellSize` (flat-to-flat), `Wall`, `Margin`, `Orientation`, `Angle`, offsets, and `Output` in the property editor.

Only whole cells are kept for now. Clipped edge cells, corner radius, and a task panel come in M2.

## Development
    python3 -m venv .venv && .venv/bin/pip install pytest
    .venv/bin/pytest
    freecadcmd tests/fc/test_features.py   # needs FreeCAD

## License
LGPL-2.1-or-later. See `LICENSE`.
