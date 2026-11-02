# SPDX-License-Identifier: LGPL-2.1-or-later
"""HexFill Part::FeaturePython: fills a closed planar region with hex cells."""

import FreeCAD as App
import Part

from ..core import hexgrid

ANCHORS = ("Centered", "BoundaryOrigin")
OUTPUTS = ("Wires", "Faces", "Solid")

# Chord tolerance used to turn curved boundaries into polylines, as a
# fraction of the cell size. Kept cells may touch a curved boundary by at most
# this much.
DEFLECTION_RATIO = 0.002


class HexFillError(Exception):
    pass


class HexFill:
    def __init__(self, obj):
        obj.Proxy = self
        self.add_properties(obj)

    @staticmethod
    def add_properties(obj):
        """Add any missing properties (also migrates older documents)."""

        def add(kind, name, group, doc, value=None, enum=None, read_only=False):
            if name in obj.PropertiesList:
                return
            obj.addProperty(kind, name, group, doc)
            if enum is not None:
                setattr(obj, name, list(enum))
            if value is not None:
                setattr(obj, name, value)
            if read_only:
                obj.setEditorMode(name, 1)

        add("App::PropertyLinkSub", "Source", "HexFill",
            "Closed sketch, wire, or planar face to fill")
        add("App::PropertyLength", "CellSize", "Cells",
            "Hex opening, flat-to-flat", 6.0)
        add("App::PropertyLength", "Wall", "Cells",
            "Web thickness between neighbouring cells", 1.2)
        add("App::PropertyLength", "Margin", "Cells",
            "Solid border kept inside the boundary", 2.0)
        add("App::PropertyEnumeration", "Orientation", "Grid",
            "Hex orientation", hexgrid.POINTY_TOP, hexgrid.ORIENTATIONS)
        add("App::PropertyAngle", "Angle", "Grid", "Rotates the whole grid", 0.0)
        add("App::PropertyDistance", "OffsetX", "Grid", "Shifts the grid along X", 0.0)
        add("App::PropertyDistance", "OffsetY", "Grid", "Shifts the grid along Y", 0.0)
        add("App::PropertyEnumeration", "Anchor", "Grid",
            "Where the grid origin sits: region centre, or the sketch origin "
            "(non-sketch sources always use the centre)",
            "Centered", ANCHORS)
        add("App::PropertyEnumeration", "Output", "Output",
            "Closed wires, planar faces, or extruded prisms", "Faces", OUTPUTS)
        add("App::PropertyLength", "Depth", "Output",
            "Extrusion depth for Solid output", 0.0)
        add("App::PropertyBool", "Reversed", "Output",
            "Extrude in the opposite direction", False)
        add("App::PropertyInteger", "CellCount", "Result",
            "Number of cells generated", read_only=True)
        add("App::PropertyFloat", "OpenAreaPercent", "Result",
            "Open area as a percentage of the source region", read_only=True)
        add("App::PropertyLength", "Pitch", "Result",
            "Centre-to-centre spacing (CellSize + Wall)", read_only=True)

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
        faces, placement, is_sketch_frame = source_region(obj.Source)
        local = faces.copy()
        local.transformShape(placement.inverse().toMatrix())

        size, wall = obj.CellSize.Value, obj.Wall.Value
        if size <= 0:
            raise HexFillError("CellSize must be greater than zero")

        region = inset(local, obj.Margin.Value)
        deflection = max(1e-4, size * DEFLECTION_RATIO)
        rings = [[(p.x, p.y) for p in wire.discretize(Deflection=deflection)]
                 for face in region.Faces for wire in face.Wires]

        if obj.Anchor == "Centered" or not is_sketch_frame:
            box = local.BoundBox
            origin = (box.Center.x, box.Center.y)
        else:
            origin = (0.0, 0.0)
        origin = (origin[0] + obj.OffsetX.Value, origin[1] + obj.OffsetY.Value)

        grid = hexgrid.HexGrid(size, wall, obj.Orientation, obj.Angle.Value, origin)
        cells = [c for c in grid.fill(rings) if c.status == hexgrid.INSIDE]

        # The feature's Placement owns the frame: FreeCAD would overwrite any
        # placement carried by the shape itself.
        obj.Shape = build_output(cells, obj.Output, obj.Depth.Value, obj.Reversed)
        obj.Placement = placement

        obj.CellCount = len(cells)
        obj.Pitch = grid.pitch
        area = local.Area
        obj.OpenAreaPercent = (100.0 * len(cells) * hexgrid.cell_area(size) / area
                               if area > 0 else 0.0)


def source_region(source):
    """Return ``(faces, placement, is_sketch_frame)`` for a Source link.

    ``faces`` is a shape of coplanar faces. ``placement`` maps the region's
    local XY frame to the source's coordinates. ``is_sketch_frame`` is True
    when that frame is the source's own (so BoundaryOrigin is meaningful).
    """
    if not source:
        raise HexFillError("No Source selected")
    obj, subs = source
    subs = [s for s in subs if s]
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        raise HexFillError("Source {} has no shape".format(obj.Label))

    if subs:
        elements = [obj.Shape.getElement(s) for s in subs]
        if not all(e.ShapeType == "Face" for e in elements):
            raise HexFillError("Only faces can be selected as sub-elements")
        faces = Part.makeCompound(elements)
    elif obj.Shape.Faces:
        faces = Part.makeCompound(obj.Shape.Faces)
    else:
        wires = obj.Shape.Wires
        if not wires or not all(w.isClosed() for w in wires):
            raise HexFillError("Source must contain closed wires or faces")
        try:
            faces = Part.makeFace(wires, "Part::FaceMakerBullseye")
        except Part.OCCError as e:
            raise HexFillError("Could not build a face from the source wires: {}".format(e))

    plane = faces.findPlane()
    if plane is None:
        raise HexFillError("Source is not planar")

    if obj.isDerivedFrom("Sketcher::SketchObject"):
        return faces, obj.Placement, True
    rotation = App.Rotation(App.Vector(0, 0, 1), plane.Axis)
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
    except Part.OCCError as e:
        raise HexFillError("Margin offset failed: {}".format(e))
    result = Part.makeCompound(pieces)
    if not result.Faces:
        raise HexFillError("Margin is too large for this region")
    return result


def build_output(cells, output, depth, reversed_):
    wires = [Part.makePolygon([App.Vector(x, y, 0) for x, y in c.vertices + c.vertices[:1]])
             for c in cells]
    if output == "Wires":
        return Part.makeCompound(wires)
    faces = [Part.Face(w) for w in wires]
    if output == "Faces":
        return Part.makeCompound(faces)
    if depth <= 0:
        raise HexFillError("Solid output needs a Depth greater than zero")
    direction = App.Vector(0, 0, -depth if reversed_ else depth)
    return Part.makeCompound([f.extrude(direction) for f in faces])


def make_hexfill(doc, source):
    obj = doc.addObject("Part::FeaturePython", "HexFill")
    HexFill(obj)
    obj.Source = source
    if App.GuiUp:
        from ..gui.viewproviders import ViewProviderHexFill
        ViewProviderHexFill(obj.ViewObject)
    return obj
