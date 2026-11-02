# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hex patterns on curved faces.

Cylinders and cones are handled here; other curved faces (B-spline, sphere,
...) are handed to ``projection``.

The face is unrolled into a flat plane (see ``core.develop``), the flat
pattern engine fills it, and each cell is mapped back as curves in the
surface's (u, v) parameter space, so its edges lie exactly on the surface.
Cells are then thickened along the surface normal into cutting or embossing
solids.

Full 360-degree cylinders wrap seamlessly: the pitch is adjusted so a whole
number of cells fits around. Cones unroll to a sector whose straight edges
(the seam) are treated as boundaries.
"""

import math

import FreeCAD as App
import Part

from ..core import develop, hexgrid
from .hexfill import (HexFillError, add_pattern_properties, add_property, pattern_cells,
                      set_results)

MODES = ("Cut", "Emboss")

# Cutting tools start this far outside the surface (and embossing tools this
# far inside) so Booleans never meet coincident faces.
OVERSHOOT = 0.2
# Points sampled per curved cell edge when mapping it to the surface.
EDGE_SAMPLES = 16


def source_face(source):
    """Return ``(face, solid)`` for a Source link naming one face."""
    if not source:
        raise HexFillError("No Source selected")
    obj, subs = source
    subs = [s for s in subs if s]
    if len(subs) != 1:
        raise HexFillError("Select exactly one face")
    face = obj.Shape.getElement(subs[0])
    if face.ShapeType != "Face":
        raise HexFillError("Source must be a face")
    return face, obj.Shape


def is_developable(face):
    """Cylinders and cones unroll exactly; other faces use projection."""
    return isinstance(face.Surface, (Part.Cylinder, Part.Cone))


def is_curved(face):
    return not isinstance(face.Surface, Part.Plane)


def development_for(face):
    surface = face.Surface
    if isinstance(surface, Part.Cylinder):
        return develop.CylinderDevelopment(surface.Radius)
    if isinstance(surface, Part.Cone):
        u0, u1, _, _ = face.ParameterRange
        return develop.ConeDevelopment(surface.Radius, surface.SemiAngle, (u0 + u1) / 2.0)
    raise HexFillError("Only cylindrical and conical faces are supported "
                       "(got {})".format(type(surface).__name__))


def is_full_wrap(face):
    return (isinstance(face.Surface, Part.Cylinder)
            and any(e.isSeam(face) for e in face.Edges))


# --- Unrolling --------------------------------------------------------------

def polygon_face(points):
    pts = [App.Vector(x, y, 0) for x, y in points]
    clean = [p for i, p in enumerate(pts) if (p - pts[i - 1]).Length > 1e-9]
    return Part.Face(Part.makePolygon(clean + clean[:1]))


def developed_region(face, dev, deflection, wrap_width=None):
    """The face unrolled into planar faces in XY.

    With ``wrap_width`` (a full cylinder), copies shifted by one turn either
    side are merged so the seam disappears and cells can straddle it.
    Returns ``(region, first_turn_x0)``.
    """
    surface = face.Surface
    u0, u1, _, _ = face.ParameterRange
    u_mid = (u0 + u1) / 2.0

    def ring(wire):
        uv = [surface.parameter(p) for p in wire.discretize(Deflection=deflection)]
        us = develop.unwrap_angles([u for u, _ in uv])
        # Same turn as the face's own parameter range.
        shift = 2.0 * math.pi * round((u_mid - sum(us) / len(us)) / (2.0 * math.pi))
        return [dev.to_flat(u + shift, v) for u, (_, v) in zip(us, uv)]

    outer = ring(face.OuterWire)
    holes = [ring(w) for w in face.Wires if not w.isSame(face.OuterWire)]
    x0 = min(x for x, _ in outer)

    def shifted(points):
        if wrap_width is None:
            return [polygon_face(points)]
        return [polygon_face([(x + k * wrap_width, y) for x, y in points])
                for k in (-1, 0, 1)]

    try:
        pieces = shifted(outer)
        region = pieces[0].fuse(pieces[1:]).removeSplitter() if len(pieces) > 1 else pieces[0]
        hole_faces = [f for h in holes for f in shifted(h)]
        if hole_faces:
            region = region.cut(Part.makeCompound(hole_faces))
    except Part.OCCError as e:
        raise HexFillError("Could not unroll the face: {}".format(e))
    return Part.makeCompound(region.Faces), x0


# --- Mapping cells back -----------------------------------------------------

def _param_curve(edge, dev):
    """The edge (in developed XY) as a 2D curve in surface parameters."""
    to_v2 = lambda x, y: App.Base.Vector2d(*dev.to_param(x, y))  # noqa: E731
    kind = edge.Curve.TypeId
    if dev.affine and kind == "Part::GeomLine":
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        return Part.Geom2d.Line2dSegment(to_v2(a.x, a.y), to_v2(b.x, b.y))
    if dev.affine and kind == "Part::GeomCircle":
        # An affine map of a rational B-spline is exact: map the poles.
        nurbs = edge.Curve.toNurbs(edge.FirstParameter, edge.LastParameter)
        curve = Part.Geom2d.BSplineCurve2d()
        curve.buildFromPolesMultsKnots([to_v2(p.x, p.y) for p in nurbs.getPoles()],
                                       nurbs.getMultiplicities(), nurbs.getKnots(), False,
                                       nurbs.Degree, nurbs.getWeights())
    else:
        curve = Part.Geom2d.BSplineCurve2d()
        curve.interpolate(Points=[to_v2(p.x, p.y)
                                  for p in edge.discretize(Number=EDGE_SAMPLES)])
    return curve


def _samples(curve, n=4):
    a, b = curve.FirstParameter, curve.LastParameter
    return [(curve.value(a + (b - a) * k / n).x, curve.value(a + (b - a) * k / n).y)
            for k in range(n + 1)]


def _chained(wire, dev):
    """The wire's edges as 2D parameter curves, each running in wire order."""
    curves = [_param_curve(edge, dev) for edge in wire.OrderedEdges]
    # Orient each curve to start where the previous one ended.
    for k, curve in enumerate(curves):
        start, end = _samples(curve, 1)
        if k == 0:
            nxt = _samples(curves[1], 1) if len(curves) > 1 else [end]
            if min(math.dist(start, p) for p in nxt) < min(math.dist(end, p) for p in nxt):
                curve.reverse()
        else:
            prev_end = _samples(curves[k - 1], 1)[-1]
            if math.dist(end, prev_end) < math.dist(start, prev_end):
                curve.reverse()
    return curves


def _signed_area(curves):
    pts = [p for c in curves for p in _samples(c)[:-1]]
    return 0.5 * sum(x0 * y1 - x1 * y0
                     for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


def _wire_on(surface, curves, ccw):
    if (_signed_area(curves) > 0) != ccw:
        for curve in curves:
            curve.reverse()
        curves = list(reversed(curves))
    return Part.Wire([curve.toShape(surface) for curve in curves])


def face_on_surface(flat_face, dev, surface):
    """Map a planar cell face (developed XY) onto ``surface``."""
    outer = _wire_on(surface, _chained(flat_face.OuterWire, dev), ccw=True)
    face = Part.Face(surface, outer)
    holes = [_wire_on(surface, _chained(w, dev), ccw=False)
             for w in flat_face.Wires if not w.isSame(flat_face.OuterWire)]
    if holes:
        face = face.cutHoles(holes) or face
    face.validate()
    return face


# --- Depth -------------------------------------------------------------------

def material_side(face):
    """+1 if the solid's outside is along the surface's natural normal."""
    return 1.0 if face.Orientation == "Forward" else -1.0


class Reach:
    """How far a face can be offset along its outward normal (out of the
    material) and its inward normal, before an offset surface would collapse
    onto the axis, plus the clearance needed to start a cut above any material
    standing proud of the face."""

    def __init__(self, face, solid):
        surface = face.Surface
        u0, u1, v0, v1 = face.ParameterRange
        um, vm = (u0 + u1) / 2.0, (v0 + v1) / 2.0
        self.point = face.valueAt(um, vm)
        self.normal = face.normalAt(um, vm)  # out of the material
        self.base = surface.Center if isinstance(surface, Part.Cylinder) else surface.Apex
        self.axis = surface.Axis
        self.cos = math.cos(surface.SemiAngle) if isinstance(surface, Part.Cone) else 1.0
        radial = self.point - self.base
        radial = radial - self.axis * radial.dot(self.axis)
        self.away = self.normal.dot(radial) > 0  # outward normal leaves the axis
        radii = [surface.value(um, v).distanceToLine(self.base, self.axis) for v in (v0, v1)]
        self.axis_limit = 0.98 * min(radii) * self.cos
        self.clearance = OVERSHOOT
        if solid is not None and self.away:
            box = solid.BoundBox
            corners = [App.Vector(x, y, z) for x in (box.XMin, box.XMax)
                       for y in (box.YMin, box.YMax) for z in (box.ZMin, box.ZMax)]
            proud = max(c.distanceToLine(self.base, self.axis) for c in corners) - min(radii)
            self.clearance += max(0.0, proud / self.cos)

    @property
    def inward(self):
        return self.axis_limit if self.away else float("inf")

    @property
    def outward(self):
        return float("inf") if self.away else self.axis_limit


def through_depth(face, solid, reach):
    """Material thickness under the middle of the face, along the normal."""
    length = solid.BoundBox.DiagonalLength + 1.0
    point, normal = reach.point, reach.normal
    ray = Part.makeLine(point + normal * 1e-3, point - normal * length)
    inside = solid.common(ray)
    touching = [e for e in inside.Edges
                if min((v.Point - point).Length for v in e.Vertexes) < 1e-2]
    if not touching:
        raise HexFillError("Could not measure the wall thickness; set Depth")
    return min(max(e.Length for e in touching), reach.inward)


# --- Tools -------------------------------------------------------------------

def surface_tools(obj, solid, subtractive):
    """Cutting (or embossing) solids for ``obj``'s pattern on its Source face.

    Updates the result properties. Returns a list of solids.
    """
    face, _ = source_face(obj.Source)
    if not is_developable(face):
        from .projection import projection_tools
        return projection_tools(obj, face, solid, subtractive)
    dev = development_for(face)
    surface = face.Surface
    size, wall = obj.CellSize.Value, obj.Wall.Value
    if size <= 0:
        raise HexFillError("CellSize must be greater than zero")

    deflection = max(1e-3, size * 0.002)
    pitch_value = hexgrid.pitch(size, wall)
    keep = None
    wrap_width = None
    if is_full_wrap(face):
        if abs(obj.Angle.Value) > 1e-9:
            raise HexFillError("Angle must be 0 when the pattern wraps all the way round")
        wrap_width = dev.circumference
        _, pitch_value = develop.wrap_pitch(wrap_width, pitch_value, obj.Orientation)
        size = pitch_value - wall
        if size <= 0:
            raise HexFillError("Wall is too thick for the wrapped pitch")

    region, x0 = developed_region(face, dev, deflection, wrap_width)
    single_turn_area = region.Area / 3.0 if wrap_width else region.Area
    if wrap_width:
        keep = lambda cell: x0 <= cell.center[0] < x0 + wrap_width  # noqa: E731
    box = region.BoundBox
    origin = (x0 + wrap_width / 2.0 if wrap_width else box.Center.x, box.Center.y)
    cells, _ = pattern_cells(obj, region, origin, cell_size=size, keep=keep)
    set_results(obj, [f for f, _ in cells], pitch_value, single_turn_area)
    if not cells:
        return []

    reach = Reach(face, solid)
    depth = obj.Depth.Value
    if depth <= 0:
        if not subtractive:
            raise HexFillError("Depth must be greater than zero")
        if solid is None:
            raise HexFillError("Depth 0 (through) needs the solid the face belongs to")
        depth = through_depth(face, solid, reach)

    # Offsets are along the surface's natural normal; ``out`` converts from
    # the face's outward (out of the material) direction.
    out = material_side(face)
    if subtractive:
        if depth > reach.inward:
            raise HexFillError("Depth reaches the axis; at most {:.2f} mm".format(reach.inward))
        clearance = min(reach.clearance, reach.outward)
        start, thickness = out * clearance, -out * (depth + clearance)
    else:
        if depth > reach.outward:
            raise HexFillError("Depth reaches the axis; at most {:.2f} mm".format(reach.outward))
        start, thickness = -out * OVERSHOOT, out * (depth + OVERSHOOT)
    target = offset_surface(face, start)

    def tool_for(flat_face):
        cell = face_on_surface(flat_face, dev, target)
        try:
            return cell.makeOffsetShape(thickness, 1e-6, fill=True)
        except Part.OCCError as e:
            raise HexFillError("Could not thicken a cell: {}".format(e))

    tools = []
    template = None
    sense = _rotation_sense(face) if dev.affine else 1.0
    for flat_face, center in cells:
        if center is None or not dev.affine:
            tools.append(tool_for(flat_face))
            continue
        # Whole cells on a cylinder are congruent: rotate/slide one copy.
        if template is None:
            template = (tool_for(flat_face), center)
            tools.append(template[0])
            continue
        tool, (cx, cy) = template
        du = sense * math.degrees((center[0] - cx) / dev.radius)
        moved = tool.rotated(surface.Center, surface.Axis, du)
        tools.append(moved.translated(surface.Axis * (center[1] - cy)))
    return tools


def offset_surface(face, distance):
    """The surface ``distance`` along the natural normal, as a canonical surface.

    Offsets of cylinders and cones are coaxial cylinders and cones with the
    same (u, v) parametrization. Canonical surfaces keep the Booleans fast and
    avoid invalid faces seen on Part.OffsetSurface of rotated surfaces.
    """
    surface = face.Surface
    if distance == 0:
        return surface
    target = surface.copy()
    u0, u1, v0, v1 = face.ParameterRange
    u, v = (u0 + u1) / 2.0, (v0 + v1) / 2.0
    expected = surface.value(u, v) + surface.normal(u, v) * distance
    radial = surface.value(u, v) - surface.value(u + math.pi, v)
    sign = 1.0 if surface.normal(u, v).dot(radial) > 0 else -1.0
    if isinstance(surface, Part.Cylinder):
        target.Radius = surface.Radius + sign * distance
    else:
        semi = surface.SemiAngle
        target.Radius = surface.Radius + sign * distance * math.cos(semi)
        target.Center = surface.Center - surface.Axis * (sign * distance * math.sin(semi))
    if (target.value(u, v) - expected).Length > 1e-7 or target.Radius <= 0:
        return Part.OffsetSurface(surface, distance)
    return target


def _rotation_sense(face):
    """+1 if increasing u turns right-handed about the axis (frames may not)."""
    surface = face.Surface
    u, v = face.ParameterRange[0], face.ParameterRange[2]
    turned = Part.Vertex(surface.value(u, v)).rotated(surface.Center, surface.Axis, 1.0).Point
    return 1.0 if (turned - surface.value(u + math.radians(1.0), v)).Length < 1e-6 else -1.0


class HexSurface:
    """Part feature: hex cell solids on a curved face."""

    def __init__(self, obj):
        obj.Proxy = self
        self.add_properties(obj)

    @staticmethod
    def add_properties(obj):
        add_pattern_properties(obj)
        add_property(obj, "App::PropertyEnumeration", "Mode", "Surface",
                     "Cut: solids to subtract (recess or through). "
                     "Emboss: raised cells to fuse", "Cut", MODES)
        add_property(obj, "App::PropertyLength", "Depth", "Surface",
                     "Depth along the surface normal; 0 cuts through the wall", 1.0)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads

    def execute(self, obj):
        _, solid = source_face(obj.Source)
        tools = surface_tools(obj, solid, obj.Mode == "Cut")
        obj.Shape = Part.makeCompound(tools)


def make_hexsurface(doc, source):
    obj = doc.addObject("Part::FeaturePython", "HexSurface")
    HexSurface(obj)
    obj.Source = source
    if App.GuiUp:
        from ..gui.viewproviders import ViewProviderHexFill
        ViewProviderHexFill(obj.ViewObject)
    return obj
