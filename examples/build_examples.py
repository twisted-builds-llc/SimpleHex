# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rebuild the example documents.

Run with the FreeCAD GUI so the objects get their view providers, e.g.:

    QT_QPA_PLATFORM=offscreen <FreeCAD AppImage> examples/build_examples.py
"""

import math
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
from freecad.hexfill.features.pd_features import HexFillCut, make_body_feature  # noqa: E402

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


def build_vent_cover(doc):
    """3 mm PartDesign plate, 140 x 90 mm with rounded corners, hex vent cut through."""
    body = doc.addObject("PartDesign::Body", "Body")
    sk = doc.addObject("Sketcher::SketchObject", "CoverOutline")
    body.addObject(sk)
    w, h, r = 140.0, 90.0, 8.0
    corners = [(w - r, h - r, 0), (r, h - r, 90), (r, r, 180), (w - r, r, 270)]
    for (cx, cy, start) in corners:
        a0 = math.radians(start)
        sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(cx, cy, 0), V(0, 0, 1), r),
                                        a0, a0 + math.pi / 2))
    sk.addGeometry(Part.LineSegment(V(w - r, h, 0), V(r, h, 0)))
    sk.addGeometry(Part.LineSegment(V(0, h - r, 0), V(0, r, 0)))
    sk.addGeometry(Part.LineSegment(V(r, 0, 0), V(w - r, 0, 0)))
    sk.addGeometry(Part.LineSegment(V(w, r, 0), V(w, h - r, 0)))
    for x, y in ((6, 6), (w - 6, 6), (w - 6, h - 6), (6, h - 6)):
        sk.addGeometry(Part.Circle(V(x, y, 0), V(0, 0, 1), 2.0))
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = 3
    doc.recompute()

    cut = make_body_feature(body, (sk, []), HexFillCut)
    cut.CellSize = 7
    cut.Wall = 1.6
    cut.Margin = 10
    cut.CornerRadius = 0.8
    cut.EdgeMode = "ClipMinArea"
    sk.Visibility = False
    doc.recompute()
    return body, cut


def main():
    if not App.GuiUp:
        App.Console.PrintWarning("Run with the GUI so objects get view providers.\n")
    doc = App.newDocument("plasma_panel")
    build_plasma_panel(doc)
    doc.saveAs(os.path.join(HERE, "plasma_panel.FCStd"))
    App.closeDocument(doc.Name)

    doc = App.newDocument("vent_cover")
    build_vent_cover(doc)
    doc.saveAs(os.path.join(HERE, "vent_cover.FCStd"))
    App.closeDocument(doc.Name)


if __name__ == "__main__":
    main()
