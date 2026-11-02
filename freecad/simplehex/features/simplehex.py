# SPDX-License-Identifier: LGPL-2.1-or-later
"""SimpleHex Part::FeaturePython: fills a closed planar region with hex cells."""

import FreeCAD as App
import Part

from ..core import hexgrid

ANCHORS = ("Centered", "BoundaryOrigin")
OUTPUTS = ("Wires", "Faces", "Solid")
EDGE_MODES = ("WholeOnly", "Clip", "ClipMinArea")

# Chord tolerance used to turn curved boundaries into polylines, as a
# fraction of the cell size. Kept cells may touch a curved boundary by at most
# this much.
DEFLECTION_RATIO = 0.002


class SimpleHexError(Exception):
    pass


def add_property(obj, kind, name, group, doc, value=None, enum=None, read_only=False):
    """Add a property unless present (so restored documents get new ones)."""
    if name in obj.PropertiesList:
        return
    obj.addProperty(kind, name, group, doc)
    if enum is not None:
        setattr(obj, name, list(enum))
    if value is not None:
        setattr(obj, name, value)
    if read_only:
        obj.setEditorMode(name, 1)


def add_pattern_properties(obj):
    """Properties shared by every feature that generates a hex pattern."""
    add = lambda *a, **k: add_property(obj, *a, **k)  # noqa: E731
    add("App::PropertyLinkSub", "Source", "SimpleHex",
        "Closed sketch, wire, or planar face to fill")
    add("App::PropertyLength", "CellSize", "Cells",
        "Hex opening, flat-to-flat", 6.0)
    add("App::PropertyLength", "Wall", "Cells",
        "Web thickness between neighbouring cells", 1.2)
    add("App::PropertyLength", "Margin", "Cells",
        "Solid border kept inside the boundary", 2.0)
    add("App::PropertyLength", "CornerRadius", "Cells",
        "Fillet radius for cell corners (at most CellSize / 2)", 0.0)
    add("App::PropertyEnumeration", "EdgeMode", "Edges",
        "WholeOnly keeps whole cells; Clip trims edge cells to the margin; "
        "ClipMinArea also drops trimmed cells below MinCellFraction",
        "WholeOnly", EDGE_MODES)
    add("App::PropertyFloat", "MinCellFraction", "Edges",
        "ClipMinArea: drop trimmed cells smaller than this fraction of a full cell",
        0.35)
    add("App::PropertyEnumeration", "Orientation", "Grid",
        "Hex orientation", hexgrid.POINTY_TOP, hexgrid.ORIENTATIONS)
    add("App::PropertyAngle", "Angle", "Grid", "Rotates the whole grid", 0.0)
    add("App::PropertyDistance", "OffsetX", "Grid", "Shifts the grid along X", 0.0)
    add("App::PropertyDistance", "OffsetY", "Grid", "Shifts the grid along Y", 0.0)
    add("App::PropertyEnumeration", "Anchor", "Grid",
        "Where the grid origin sits: region centre, or the sketch origin "
        "(non-sketch sources always use the centre)",
        "Centered", ANCHORS)
    add("App::PropertyInteger", "CellCount", "Result",
        "Number of cells generated", read_only=True)
    add("App::PropertyFloat", "OpenAreaPercent", "Result",
        "Open area as a percentage of the source region", read_only=True)
    add("App::PropertyLength", "Pitch", "Result",
        "Centre-to-centre spacing (CellSize + Wall)", read_only=True)


def compute_pattern(obj):
    """Build the cell faces for ``obj``'s pattern properties.

    Returns ``(faces, placement)``: planar faces in the region's local XY
    frame, and the placement of that frame in the source's coordinates. Also
    updates the read-only result properties.
    """
    faces, placement, is_sketch_frame = source_region(obj.Source)
    local = faces.copy()
    local.transformShape(placement.inverse().toMatrix())

    if obj.Anchor == "Centered" or not is_sketch_frame:
        box = local.BoundBox
        origin = (box.Center.x, box.Center.y)
    else:
        origin = (0.0, 0.0)

    cells, grid = pattern_cells(obj, local, origin)
    cell_faces = [face for face, _ in cells]
    set_results(obj, cell_faces, grid.pitch, local.Area)
    return cell_faces, placement


def pattern_cells(obj, local, origin, cell_size=None, keep=None):
    """Lay ``obj``'s hex pattern over planar faces in the XY plane.

    ``origin`` is the grid anchor before OffsetX/OffsetY. ``cell_size``
    overrides obj.CellSize; ``keep(cell)`` can reject lattice cells before
    they are built. Returns ``(cells, grid)`` where ``cells`` is a list of
    ``(face, center)`` with ``center`` None for edge cells trimmed by Clip.
    """
    size = obj.CellSize.Value if cell_size is None else cell_size
    wall, radius = obj.Wall.Value, obj.CornerRadius.Value
    if size <= 0:
        raise SimpleHexError("CellSize must be greater than zero")
    try:
        full_area = hexgrid.cell_area(size, radius)
    except ValueError as e:
        raise SimpleHexError(str(e))

    region = inset(local, obj.Margin.Value)
    deflection = max(1e-4, size * DEFLECTION_RATIO)
    rings = [[(p.x, p.y) for p in wire.discretize(Deflection=deflection)]
             for face in region.Faces for wire in face.Wires]

    origin = (origin[0] + obj.OffsetX.Value, origin[1] + obj.OffsetY.Value)
    grid = hexgrid.HexGrid(size, wall, obj.Orientation, obj.Angle.Value, origin)
    # All cells are congruent: build one and place copies (shared geometry).
    template = cell_face(grid.vertices(0, 0), radius)
    x0, y0 = grid.center(0, 0)
    cells = []
    straddling = []
    for cell in grid.fill(rings):
        if keep is not None and not keep(cell):
            continue
        face = template.translated(App.Vector(cell.center[0] - x0, cell.center[1] - y0, 0))
        if cell.status == hexgrid.INSIDE:
            cells.append((face, cell.center))
        elif obj.EdgeMode != "WholeOnly":
            straddling.append(face)
    if straddling:
        min_area = (full_area * obj.MinCellFraction
                    if obj.EdgeMode == "ClipMinArea" else 1e-9)
        cells += [(f, None) for f in clip_cells(straddling, region, min_area)]
    return cells, grid


def set_results(obj, cell_faces, pitch_value, region_area):
    obj.CellCount = len(cell_faces)
    obj.Pitch = pitch_value
    open_area = sum(f.Area for f in cell_faces)
    obj.OpenAreaPercent = 100.0 * open_area / region_area if region_area > 0 else 0.0


class SimpleHex:
    def __init__(self, obj):
        obj.Proxy = self
        self.add_properties(obj)

    @staticmethod
    def add_properties(obj):
        add_pattern_properties(obj)
        add_property(obj, "App::PropertyEnumeration", "Output", "Output",
                     "Closed wires, planar faces, or extruded prisms", "Faces", OUTPUTS)
        add_property(obj, "App::PropertyLength", "Depth", "Output",
                     "Extrusion depth for Solid output", 0.0)
        add_property(obj, "App::PropertyBool", "Reversed", "Output",
                     "Extrude in the opposite direction", False)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    # FreeCAD < 1.0 names
    __getstate__ = dumps
    __setstate__ = loads

    def execute(self, obj):
        faces, placement = compute_pattern(obj)
        # The feature's Placement owns the frame: FreeCAD would overwrite any
        # placement carried by the shape itself.
        obj.Shape = build_output(faces, obj.Output, obj.Depth.Value, obj.Reversed)
        obj.Placement = placement


def source_region(source):
    """Return ``(faces, placement, is_sketch_frame)`` for a Source link.

    ``faces`` is a shape of coplanar faces. ``placement`` maps the region's
    local XY frame to the source's coordinates. ``is_sketch_frame`` is True
    when that frame is the source's own (so BoundaryOrigin is meaningful).
    """
    if not source:
        raise SimpleHexError("No Source selected")
    obj, subs = source
    subs = [s for s in subs if s]
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        raise SimpleHexError("Source {} has no shape".format(obj.Label))

    if subs:
        elements = [obj.Shape.getElement(s) for s in subs]
        if not all(e.ShapeType == "Face" for e in elements):
            raise SimpleHexError("Only faces can be selected as sub-elements")
        faces = Part.makeCompound(elements)
    elif obj.Shape.Faces:
        faces = Part.makeCompound(obj.Shape.Faces)
    else:
        wires = obj.Shape.Wires
        if not wires or not all(w.isClosed() for w in wires):
            raise SimpleHexError("Source must contain closed wires or faces")
        try:
            faces = Part.makeFace(wires, "Part::FaceMakerBullseye")
        except Part.OCCError as e:
            raise SimpleHexError("Could not build a face from the source wires: {}".format(e))

    plane = faces.findPlane()
    if plane is None:
        raise SimpleHexError("Source is not planar")

    if obj.isDerivedFrom("Sketcher::SketchObject"):
        return faces, obj.Placement, True
    # A selected face's own normal points out of its solid; a plane fitted to
    # wires has no preferred side.
    axis = faces.Faces[0].normalAt(0, 0) if subs else plane.Axis
    rotation = App.Rotation(App.Vector(0, 0, 1), axis)
    return faces, App.Placement(plane.Position, rotation), False


def inset(local_faces, margin):
    """Shrink the region by ``margin``; holes grow by the same amount.

    Each outer boundary and hole is offset on its own, then the holes are cut
    away. Offsetting a face with holes directly is wrong in FreeCAD 1.1: a
    negative offset drops the outer boundary and keeps only the shrunk hole.
    """
    if margin <= 0:
        return local_faces
    pieces = []
    try:
        for face in local_faces.Faces:
            piece = Part.Face(face.OuterWire).makeOffset2D(-margin)
            holes = [Part.Face(w).makeOffset2D(margin)
                     for w in face.Wires if not w.isSame(face.OuterWire)]
            if holes and piece.Faces:
                piece = piece.cut(Part.makeCompound(holes))
            pieces.extend(piece.Faces)
    except (Part.OCCError, ValueError) as e:
        raise SimpleHexError("Margin offset failed: {}".format(e))
    result = Part.makeCompound(pieces)
    if not result.Faces:
        raise SimpleHexError("Margin is too large for this region")
    return result


def cell_face(vertices, radius):
    """Planar face for one cell, with filleted corners when radius > 0."""
    if radius <= 0:
        pts = [App.Vector(x, y, 0) for x, y in vertices]
        return Part.Face(Part.makePolygon(pts + pts[:1]))
    edges = []
    for seg in hexgrid.rounded_outline(vertices, radius):
        pts = [App.Vector(x, y, 0) for x, y in seg[1:]]
        geom = Part.Arc(*pts) if seg[0] == "arc" else Part.LineSegment(*pts)
        edges.append(geom.toShape())
    return Part.Face(Part.Wire(edges))


def clip_cells(cells, region, min_area):
    """Trim edge cells to the region; keep pieces of at least min_area."""
    pieces = Part.makeCompound(cells).common(region)
    return [f for f in pieces.Faces if f.Area >= min_area]


def build_output(faces, output, depth, reversed_):
    if output == "Wires":
        return Part.makeCompound([w for f in faces for w in f.Wires])
    if output == "Faces":
        return Part.makeCompound(faces)
    if depth <= 0:
        raise SimpleHexError("Solid output needs a Depth greater than zero")
    direction = App.Vector(0, 0, -depth if reversed_ else depth)
    return Part.makeCompound([f.extrude(direction) for f in faces])


def make_simplehex(doc, source):
    obj = doc.addObject("Part::FeaturePython", "SimpleHex")
    SimpleHex(obj)
    obj.Source = source
    if App.GuiUp:
        from ..gui.viewproviders import ViewProviderSimpleHex
        ViewProviderSimpleHex(obj.ViewObject)
    return obj
