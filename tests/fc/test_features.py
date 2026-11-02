# SPDX-License-Identifier: LGPL-2.1-or-later
"""Integration checks for the HexFill feature.

Run headless from the repository root:

    freecadcmd tests/fc/test_features.py
"""

import math
import os
import sys
import tempfile

import FreeCAD as App
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import freecad  # noqa: E402  FreeCAD's own namespace package

freecad.__path__.append(os.path.join(ROOT, "freecad"))

from freecad.hexfill.core import hexgrid  # noqa: E402
from freecad.hexfill.features.hexfill import inset, make_hexfill  # noqa: E402


def rectangle_sketch(doc, w, h, hole_radius=0.0):
    sk = doc.addObject("Sketcher::SketchObject", "Region")
    pts = [App.Vector(0, 0, 0), App.Vector(w, 0, 0), App.Vector(w, h, 0), App.Vector(0, h, 0)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        sk.addGeometry(Part.LineSegment(a, b))
    if hole_radius:
        sk.addGeometry(Part.Circle(App.Vector(w / 2, h / 2, 0), App.Vector(0, 0, 1), hole_radius))
    sk.Placement = App.Placement(App.Vector(5, -3, 10), App.Rotation(App.Vector(1, 0, 0), 30))
    return sk


def check_cells_inside(fill, sketch, margin):
    """Every cell lies in the region and at least ``margin`` from its edges."""
    region = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
    boundary = Part.makeCompound(region.Wires)
    full = hexgrid.cell_area(fill.CellSize.Value)
    # Curved edges are discretized with a chord error of CellSize * 0.002.
    tol = fill.CellSize.Value * 0.002 + 1e-6
    for face in fill.Shape.Faces:
        assert math.isclose(face.Area, full, rel_tol=1e-6), face.Area
        assert math.isclose(face.common(region).Area, full, rel_tol=1e-6)
        assert face.distToShape(boundary)[0] >= margin - tol


def test_inset_with_hole():
    outer = Part.makePolygon([App.Vector(x, y, 0) for x, y in
                              [(0, 0), (120, 0), (120, 80), (0, 80), (0, 0)]])
    hole = Part.Wire(Part.makeCircle(15, App.Vector(60, 40, 0)))
    face = Part.makeFace([outer, hole], "Part::FaceMakerBullseye")
    result = inset(Part.makeCompound([face]), 2)
    assert math.isclose(result.Area, 116 * 76 - math.pi * 17 ** 2, rel_tol=1e-6)


def test_rectangle_with_hole_and_roundtrip():
    doc = App.newDocument("HexFillTest")
    sk = rectangle_sketch(doc, 120, 80, hole_radius=15)
    fill = make_hexfill(doc, (sk, []))
    doc.recompute()

    assert fill.isValid(), fill.getStatusString()
    assert fill.CellCount > 100, fill.CellCount
    assert len(fill.Shape.Faces) == fill.CellCount
    assert fill.Shape.isValid()
    assert math.isclose(fill.Pitch.Value, 7.2)
    check_cells_inside(fill, sk, fill.Margin.Value)

    fill.Output = "Solid"
    fill.Depth = 3
    doc.recompute()
    assert fill.isValid(), fill.getStatusString()
    assert len(fill.Shape.Solids) == fill.CellCount
    assert fill.Shape.isValid()

    path = os.path.join(tempfile.mkdtemp(), "hexfill.FCStd")
    count = fill.CellCount
    doc.saveAs(path)
    App.closeDocument(doc.Name)

    doc = App.openDocument(path)
    fill = doc.getObject("HexFill")
    fill.touch()
    doc.recompute()
    assert fill.isValid(), fill.getStatusString()
    assert fill.CellCount == count
    App.closeDocument(doc.Name)


def test_open_wire_reports_error():
    doc = App.newDocument("HexFillOpen")
    sk = doc.addObject("Sketcher::SketchObject", "Open")
    sk.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(10, 0, 0)))
    fill = make_hexfill(doc, (sk, []))
    doc.recompute()
    assert not fill.isValid()
    App.closeDocument(doc.Name)


for _name, _test in list(globals().items()):
    if _name.startswith("test_"):
        _test()
        print("PASS", _name)
