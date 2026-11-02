# SPDX-License-Identifier: LGPL-2.1-or-later
"""SimpleHex: parametric hexagon pattern workbench for FreeCAD.

Kept free of FreeCAD imports so ``core`` can be tested without FreeCAD.
"""

import os

__version__ = "0.1.0"

ICON_DIR = os.path.join(os.path.dirname(__file__), "resources", "icons")


def icon(name):
    return os.path.join(ICON_DIR, name)
