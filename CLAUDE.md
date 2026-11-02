# SimpleHex

FreeCAD workbench that fills closed planar regions with parametric hexagon patterns.
Design document: `docs/design.md` (milestones in §9).

## Rules
- Target FreeCAD 1.0 and 1.1. Python 3.8+ syntax only.
- `freecad/simplehex/core/` must not import FreeCAD, Part, or PySide.
- Qt only via FreeCAD's shim: `from PySide import QtCore, QtGui`.
- Every source file starts with `# SPDX-License-Identifier: LGPL-2.1-or-later`.
- Run `.venv/bin/pytest` before committing (create with `python3 -m venv .venv && .venv/bin/pip install pytest`).
- FreeCAD integration checks: `freecadcmd tests/fc/test_features.py` (with an AppImage: `<AppImage> freecadcmd tests/fc/test_features.py`).
- GUI smoke test (task panel, OK/Cancel): `QT_QPA_PLATFORM=offscreen <AppImage> tests/fc/test_gui.py`. Visual checks (icons, 3D preview) stay manual.
- Rebuild example files with `QT_QPA_PLATFORM=offscreen <AppImage> examples/build_examples.py` (GUI mode so objects get view providers).
- Work milestone by milestone; each ends with tests passing and an example `.FCStd` updated.
