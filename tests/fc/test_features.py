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
from freecad.hexfill.export import export_dxf  # noqa: E402
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


def check_cells_inside(fill, sketch, margin, whole=True):
    """Every cell lies in the region and at least ``margin`` from its edges."""
    region = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
    boundary = Part.makeCompound(region.Wires)
    full = hexgrid.cell_area(fill.CellSize.Value, fill.CornerRadius.Value)
    # Curved edges are discretized with a chord error of CellSize * 0.002.
    tol = fill.CellSize.Value * 0.002 + 1e-6
    for face in fill.Shape.Faces:
        if whole:
            assert math.isclose(face.Area, full, rel_tol=1e-6), face.Area
        else:
            assert face.Area <= full * (1 + 1e-6)
        assert math.isclose(face.common(region).Area, face.Area, rel_tol=1e-6)
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


def test_edge_modes_and_corner_radius():
    doc = App.newDocument("HexFillEdges")
    sk = rectangle_sketch(doc, 120, 80, hole_radius=15)
    fill = make_hexfill(doc, (sk, []))
    full = hexgrid.cell_area(6.0)

    counts = {}
    for mode in ("WholeOnly", "Clip", "ClipMinArea"):
        fill.EdgeMode = mode
        doc.recompute()
        assert fill.isValid(), fill.getStatusString()
        assert fill.Shape.isValid()
        check_cells_inside(fill, sk, fill.Margin.Value, whole=(mode == "WholeOnly"))
        counts[mode] = fill.CellCount
        if mode == "ClipMinArea":
            assert min(f.Area for f in fill.Shape.Faces) >= 0.35 * full - 1e-9
        if mode == "Clip":
            clip_open = fill.OpenAreaPercent
    assert counts["WholeOnly"] < counts["ClipMinArea"] < counts["Clip"], counts
    # Clipped open area is close to the infinite-grid ratio over the inset region.
    inset_area = (116 * 76 - math.pi * 17 ** 2) / (120 * 80 - math.pi * 15 ** 2)
    assert math.isclose(clip_open / 100, inset_area * hexgrid.open_area_ratio(6, 1.2),
                        rel_tol=0.03), clip_open

    fill.EdgeMode = "WholeOnly"
    fill.CornerRadius = 1.0
    doc.recompute()
    assert fill.isValid(), fill.getStatusString()
    check_cells_inside(fill, sk, fill.Margin.Value)
    assert any(e.Curve.TypeId == "Part::GeomCircle" for e in fill.Shape.Edges)

    fill.CornerRadius = 3.0  # cells become circles
    doc.recompute()
    assert fill.isValid(), fill.getStatusString()
    assert math.isclose(fill.Shape.Faces[0].Area, math.pi * 9, rel_tol=1e-6)

    fill.CornerRadius = 3.5
    doc.recompute()
    assert not fill.isValid()
    App.closeDocument(doc.Name)


def dxf_entities(path):
    """Parse LINE, ARC, CIRCLE and LWPOLYLINE entities from a DXF file."""
    with open(path) as f:
        lines = [l.strip() for l in f]
    pairs = list(zip(lines[0::2], lines[1::2]))
    entities, current = [], None
    for code, value in pairs:
        if code == "0":
            current = [value, []]
            entities.append(current)
        elif current is not None:
            current[1].append((code, value))
    return [(kind, data) for kind, data in entities
            if kind in ("LINE", "ARC", "CIRCLE", "LWPOLYLINE")]


def check_dxf_contours(path):
    """All contours closed, no duplicate entities. Returns the contour count."""
    key = lambda x, y: (round(x, 4), round(y, 4))
    ends, seen, closed = {}, set(), 0
    for kind, data in dxf_entities(path):
        values = {}
        for code, value in data:
            values.setdefault(code, []).append(float(value) if 10 <= int(code) < 100 else value)
        if kind == "LINE":
            pts = [key(values["10"][0], values["20"][0]), key(values["11"][0], values["21"][0])]
        elif kind == "ARC":
            cx, cy, r = values["10"][0], values["20"][0], values["40"][0]
            pts = [key(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
                   for a in (values["50"][0], values["51"][0])]
        elif kind == "CIRCLE":
            closed += 1
            pts = []
        else:
            assert int(values["70"][0]) & 1, "open polyline"
            closed += 1
            pts = []
        ident = (kind, tuple(sorted(pts)),
                 tuple(round(v, 4) for c in ("10", "20", "40") for v in values.get(c, [])))
        assert ident not in seen, ident
        seen.add(ident)
        for p in pts:
            ends[p] = ends.get(p, 0) + 1
    assert all(n == 2 for n in ends.values()), [p for p, n in ends.items() if n != 2][:5]
    return closed, len(ends)


def test_plasma_example_dxf_export():
    doc = App.openDocument(os.path.join(ROOT, "examples", "plasma_panel.FCStd"))
    fill = doc.getObject("HexFill")
    fill.touch()
    doc.recompute()
    assert fill.isValid(), fill.getStatusString()
    assert fill.CellCount == 98, fill.CellCount
    path = os.path.join(tempfile.mkdtemp(), "panel.dxf")
    export_dxf([fill], path)
    kinds = [kind for kind, _ in dxf_entities(path)]
    assert kinds.count("CIRCLE") == 5  # mounting holes and centre bore
    check_dxf_contours(path)
    App.closeDocument(doc.Name)


for _name, _test in list(globals().items()):
    if _name.startswith("test_"):
        _test()
        print("PASS", _name)
