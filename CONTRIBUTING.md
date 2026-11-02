# Contributing

- Read `docs/design.md` first.
- Keep `freecad/hexfill/core/` free of FreeCAD imports so it stays testable with plain pytest.
- Add an SPDX header (`# SPDX-License-Identifier: LGPL-2.1-or-later`) to every new source file.
- Run `pytest` and, if you have FreeCAD, `freecadcmd tests/fc/test_features.py` before opening a pull request.
- Contributions are accepted under LGPL-2.1-or-later.
