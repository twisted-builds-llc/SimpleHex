# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rebuild the example documents.

Run with the FreeCAD GUI so the objects get their view providers, e.g.:

    QT_QPA_PLATFORM=offscreen <FreeCAD AppImage> examples/build_examples.py
"""

import os
import sys

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import freecad  # noqa: E402  FreeCAD's own namespace package

if os.path.join(ROOT, "freecad") not in freecad.__path__:
    freecad.__path__.append(os.path.join(ROOT, "freecad"))

from freecad.hexfill.features.hexfill import make_hexfill  # noqa: E402

V = App.Vector


def build_plasma_panel(doc):
    """200 x 120 mm plate, four 6.5 mm mounting holes, 40 mm centre bore."""
    sk = doc.addObject("Sketcher::SketchObject", "PanelOutline")
    pts = [V(0, 0, 0), V(200, 0, 0), V(200, 120, 0), V(0, 120, 0)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        sk.addGeometry(Part.LineSegment(a, b))
    for x, y in ((10, 10), (190, 10), (190, 110), (10, 110)):
        sk.addGeometry(Part.Circle(V(x, y, 0), V(0, 0, 1), 3.25))
    sk.addGeometry(Part.Circle(V(100, 60, 0), V(0, 0, 1), 20))

    fill = make_hexfill(doc, (sk, []))
    fill.Label = "PlasmaHexFill"
    fill.CellSize = 10
    fill.Wall = 3
    fill.Margin = 6
    fill.CornerRadius = 1
    fill.EdgeMode = "WholeOnly"
    doc.recompute()
    return sk, fill


def main():
    if not App.GuiUp:
        App.Console.PrintWarning("Run with the GUI so objects get view providers.\n")
    doc = App.newDocument("plasma_panel")
    build_plasma_panel(doc)
    doc.saveAs(os.path.join(HERE, "plasma_panel.FCStd"))
    App.closeDocument(doc.Name)


if __name__ == "__main__":
    main()
