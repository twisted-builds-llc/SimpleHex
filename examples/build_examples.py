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

from freecad.simplehex.features.simplehex import make_simplehex  # noqa: E402
from freecad.simplehex.features.pd_features import (  # noqa: E402
    SimpleHexCut, HexSurfaceCut, make_body_feature)

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

    fill = make_simplehex(doc, (sk, []))
    fill.Label = "PlasmaSimpleHex"
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

    cut = make_body_feature(body, (sk, []), SimpleHexCut)
    cut.CellSize = 7
    cut.Wall = 1.6
    cut.Margin = 10
    cut.CornerRadius = 0.8
    cut.EdgeMode = "ClipMinArea"
    sk.Visibility = False
    doc.recompute()
    return body, cut


def build_cylinder_texture(doc):
    """Tube (40 mm OD, 3 mm wall): hex recess texture all the way round."""
    body = doc.addObject("PartDesign::Body", "Body")
    sk = doc.addObject("Sketcher::SketchObject", "TubeSection")
    body.addObject(sk)
    sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 20))
    sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 17))
    pad = body.newObject("PartDesign::Pad", "Tube")
    pad.Profile = sk
    pad.Length = 50
    doc.recompute()

    outer = next(i for i, f in enumerate(pad.Shape.Faces)
                 if isinstance(f.Surface, Part.Cylinder) and f.Surface.Radius > 19)
    texture = make_body_feature(body, (pad, ["Face{}".format(outer + 1)]), HexSurfaceCut)
    texture.Label = "HexTexture"
    texture.CellSize = 5
    texture.Wall = 1.2
    texture.Margin = 4
    texture.CornerRadius = 0.6
    texture.Depth = 0.6
    sk.Visibility = False
    doc.recompute()
    return body, texture


def build_freeform_texture(doc):
    """Gently domed B-spline lid (100 x 80) with a hex recess texture on top."""
    pts = [[V(x, y, 10 + 4 * math.sin(math.pi * x / 100) * math.sin(math.pi * y / 80))
            for y in range(0, 81, 10)] for x in range(0, 101, 10)]
    surface = Part.BSplineSurface()
    surface.interpolate(pts)
    lid = doc.addObject("Part::Feature", "DomedLid")
    lid.Shape = surface.toShape().extrude(V(0, 0, -6))
    top = next(i for i, f in enumerate(lid.Shape.Faces)
               if isinstance(f.Surface, Part.BSplineSurface) and f.CenterOfMass.z > 9)

    body = doc.addObject("PartDesign::Body", "Body")
    body.BaseFeature = lid
    doc.recompute()
    texture = make_body_feature(body, (lid, ["Face{}".format(top + 1)]), HexSurfaceCut)
    texture.Label = "HexTexture"
    texture.CellSize = 6
    texture.Wall = 1.4
    texture.Margin = 5
    texture.CornerRadius = 0.6
    texture.Depth = 0.8
    lid.Visibility = False
    doc.recompute()
    return body, texture


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

    doc = App.newDocument("cylinder_texture")
    build_cylinder_texture(doc)
    doc.saveAs(os.path.join(HERE, "cylinder_texture.FCStd"))
    App.closeDocument(doc.Name)

    doc = App.newDocument("freeform_texture")
    build_freeform_texture(doc)
    doc.saveAs(os.path.join(HERE, "freeform_texture.FCStd"))
    App.closeDocument(doc.Name)


if __name__ == "__main__":
    main()
