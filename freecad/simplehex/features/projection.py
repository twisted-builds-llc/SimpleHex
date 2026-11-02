# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hex patterns projected onto freeform faces (B-spline, sphere, ...).

The flat pattern is laid out in a plane through the middle of the face,
perpendicular to the face normal there (the projection direction n). Each
cell becomes a prism along n, so its outline on the face is the projection
of the flat hex. A recess floor (or emboss top) is the tangent plane at the
cell centre, offset by the depth along the surface normal there; on a gently
curved face it differs from the true offset surface only by the curvature
sag across one cell.

All tool faces are planar (or cylindrical for rounded corners), which keeps
the Booleans against freeform faces fast; curved floors parallel to the face
made OCC an order of magnitude slower. This suits gently curved faces; steep regions stretch the cells
by 1 / cos(tilt), and faces that turn more than MAX_TILT_DEG away from n are
refused.
"""

import math

import FreeCAD as App
import Part

from .simplehex import SimpleHexError, pattern_cells, set_results

MAX_TILT_DEG = 75.0
# Tools start/stop this far beyond the faces they meet.
OVERSHOOT = 0.2
TILT_SAMPLES = 12

Z = App.Vector(0, 0, 1)


def projection_frame(face):
    """Placement of the pattern plane: origin on the face, Z along n."""
    u, v = face.Surface.parameter(face.CenterOfMass)
    if not face.isPartOfDomain(u, v):
        u0, u1, v0, v1 = face.ParameterRange
        u, v = (u0 + u1) / 2.0, (v0 + v1) / 2.0
    normal = face.normalAt(u, v)  # out of the material
    return App.Placement(face.valueAt(u, v), App.Rotation(Z, normal)), normal


def check_tilt(face, direction):
    """Refuse faces that turn too far from the projection direction."""
    limit = math.cos(math.radians(MAX_TILT_DEG))
    u0, u1, v0, v1 = face.ParameterRange
    worst = 1.0
    for i in range(TILT_SAMPLES + 1):
        for j in range(TILT_SAMPLES + 1):
            u = u0 + (u1 - u0) * i / TILT_SAMPLES
            v = v0 + (v1 - v0) * j / TILT_SAMPLES
            if face.isPartOfDomain(u, v):
                worst = min(worst, face.normalAt(u, v).dot(direction))
    if worst < limit:
        raise SimpleHexError(
            "Face is too curved to project onto: it turns {:.0f} degrees from its "
            "middle (limit {:.0f})".format(math.degrees(math.acos(max(-1.0, worst))),
                                          MAX_TILT_DEG))


def _local(shape, placement):
    local = shape.copy()
    local.transformShape(placement.inverse().toMatrix())
    return local


def projected_region(local_face, deflection):
    """The face's outline projected onto the pattern plane (planar faces)."""
    from .surface import polygon_face

    def ring(wire):
        # Seam edges (e.g. on a sphere) run there and back: not a boundary.
        edges = [e for e in wire.Edges if not e.isSeam(local_face)]
        if len(edges) < len(wire.Edges):
            wire = Part.Wire(Part.__sortEdges__(edges))
            if not wire.isClosed():
                raise SimpleHexError("Face wraps around; it cannot be projected")
        return [(p.x, p.y) for p in wire.discretize(Deflection=deflection)]

    try:
        outer = polygon_face(ring(local_face.OuterWire))
        holes = [polygon_face(ring(w)) for w in local_face.Wires
                 if not w.isSame(local_face.OuterWire)]
        region = outer.cut(Part.makeCompound(holes)) if holes else outer
    except Part.OCCError as e:
        raise SimpleHexError("Could not project the face outline: {}".format(e))
    if not region.isValid():
        raise SimpleHexError("The face outline overlaps itself when projected")
    return Part.makeCompound(region.Faces)


def projection_tools(obj, face, solid, subtractive):
    """Cutting (or embossing) solids for ``obj``'s pattern projected on ``face``."""
    placement, normal = projection_frame(face)
    check_tilt(face, normal)
    local_face = _local(face, placement)

    size = obj.CellSize.Value
    region = projected_region(local_face, max(1e-3, size * 0.002))
    box = region.BoundBox
    cells, grid = pattern_cells(obj, region, (box.Center.x, box.Center.y))
    faces = [f for f, _ in cells]
    set_results(obj, faces, grid.pitch, region.Area)
    if not faces:
        return []

    face_box = local_face.BoundBox
    solid_box = _local(solid, placement).BoundBox if solid is not None else face_box
    top = max(solid_box.ZMax, face_box.ZMax) + OVERSHOOT
    bottom = min(solid_box.ZMin, face_box.ZMin) - OVERSHOOT
    depth = obj.Depth.Value

    if subtractive and depth <= 0:
        if solid is None:
            raise SimpleHexError("Depth 0 (through) needs the solid the face belongs to")
        tools = [f.translated(Z * bottom).extrude(Z * (top - bottom)) for f in faces]
    else:
        if depth <= 0:
            raise SimpleHexError("Depth must be greater than zero")
        reach = (grid.pitch + depth) * 4.0 + (top - bottom)
        tools = []
        for f in faces:
            # Emboss cells reach far enough above the face to be trimmed.
            prism_top = top if subtractive else top + depth + grid.pitch
            prism = f.translated(Z * (bottom - depth)).extrude(
                Z * (prism_top - bottom + depth))
            centre = f.CenterOfMass
            point, normal, curvature = _surface_under(face, placement, centre.x, centre.y)
            half_width = f.BoundBox.DiagonalLength / 2.0
            sag = curvature * half_width * half_width / 2.0
            if subtractive:
                bound = _halfspace_box(point - normal * depth, normal, reach, reach)
            else:
                low = OVERSHOOT + sag
                bound = _halfspace_box(point - normal * low, normal, reach, depth + low)
            try:
                tools.append(prism.common(bound))
            except Part.OCCError as e:
                raise SimpleHexError("Could not shape a cell: {}".format(e))

    shape = Part.makeCompound(tools)
    shape.transformShape(placement.toMatrix())
    return list(shape.Solids)


def _surface_under(face, placement, x, y):
    """Point, normal (local pattern-plane frame) and largest principal
    curvature of the face below local (x, y)."""
    surface = face.Surface
    inverse = placement.inverse()
    z = 0.0
    for _ in range(4):
        u, v = surface.parameter(placement.multVec(App.Vector(x, y, z)))
        z = inverse.multVec(surface.value(u, v)).z
    point = inverse.multVec(face.valueAt(u, v))
    normal = inverse.Rotation.multVec(face.normalAt(u, v))
    try:
        curvature = max(abs(k) for k in face.curvatureAt(u, v))
    except Part.OCCError:
        curvature = 0.0
    return point, normal, curvature


def _halfspace_box(base, normal, width, height):
    """Box of the given height above the plane through ``base`` normal to
    ``normal``, ``width`` wide around ``base``."""
    rotation = App.Rotation(Z, normal)
    corner = base - rotation.multVec(App.Vector(width / 2.0, width / 2.0, 0))
    box = Part.makeBox(width, width, height)
    box.Placement = App.Placement(corner, rotation)
    return box
