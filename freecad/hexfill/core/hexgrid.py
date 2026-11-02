# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure-Python hexagon grid math and region classification.

This module must not import FreeCAD, so it can be unit-tested with pytest.

Conventions
-----------
* ``cell_size`` is the hex opening measured flat-to-flat (F).
* ``wall`` is the web thickness between neighbouring cells (W).
* Pitch ``P = F + W`` is the centre-to-centre distance between neighbours.
* The grid is built pointy-top in its own "grid-local" frame; flat-top is the
  same grid rotated by 90 degrees. ``angle`` adds a further rotation and
  ``origin`` is where cell (0, 0) sits, in region coordinates.
* Regions are given as rings (closed polylines) of ``(x, y)`` tuples and use
  the even-odd fill rule, so holes need no special orientation.
"""

import math
from bisect import bisect_left
from collections import namedtuple

SQRT3 = math.sqrt(3.0)

POINTY_TOP = "PointyTop"
FLAT_TOP = "FlatTop"
ORIENTATIONS = (POINTY_TOP, FLAT_TOP)

INSIDE = "inside"
STRADDLE = "straddle"

Cell = namedtuple("Cell", "index center vertices status")
"""A grid cell touching the region.

``index`` is the ``(i, j)`` lattice index, ``center`` and ``vertices`` are in
region coordinates (vertices counter-clockwise), ``status`` is INSIDE (fully
inside the region) or STRADDLE (crossed by the region boundary).
"""


# --- Scalar formulas -------------------------------------------------------

def pitch(cell_size, wall):
    return cell_size + wall


def circumradius(cell_size):
    """Centre-to-corner distance of a hex with the given flat-to-flat size."""
    return cell_size / SQRT3


def cell_area(cell_size):
    return SQRT3 / 2.0 * cell_size * cell_size


def open_area_ratio(cell_size, wall):
    """Open fraction of an infinite grid."""
    return (cell_size / (cell_size + wall)) ** 2


# --- Alternative sizing modes (all convert to cell_size, wall) -------------

def from_corner_to_corner(corner_to_corner, wall):
    return corner_to_corner * SQRT3 / 2.0, wall


def from_pitch_and_open_area(pitch_value, open_ratio):
    """Return ``(cell_size, wall)`` for a pitch and open-area ratio in (0, 1]."""
    if pitch_value <= 0:
        raise ValueError("Pitch must be positive")
    if not 0.0 < open_ratio <= 1.0:
        raise ValueError("Open area ratio must be in (0, 1]")
    size = pitch_value * math.sqrt(open_ratio)
    return size, pitch_value - size


# --- Grid -----------------------------------------------------------------

class HexGrid:
    def __init__(self, cell_size, wall, orientation=POINTY_TOP, angle=0.0,
                 origin=(0.0, 0.0)):
        if cell_size <= 0:
            raise ValueError("Cell size must be positive")
        if wall < 0:
            raise ValueError("Wall must not be negative")
        if orientation not in ORIENTATIONS:
            raise ValueError("Unknown orientation: {!r}".format(orientation))

        self.cell_size = float(cell_size)
        self.wall = float(wall)
        self.pitch = pitch(self.cell_size, self.wall)
        self.radius = circumradius(self.cell_size)
        self.row_spacing = self.pitch * SQRT3 / 2.0
        self.origin = (float(origin[0]), float(origin[1]))

        rotation = math.radians(angle + (90.0 if orientation == FLAT_TOP else 0.0))
        self._cos = math.cos(rotation)
        self._sin = math.sin(rotation)

        # Pointy-top corners in grid-local frame, counter-clockwise.
        self._corners = [
            (self.radius * math.cos(math.radians(30 + 60 * k)),
             self.radius * math.sin(math.radians(30 + 60 * k)))
            for k in range(6)
        ]

    # Frame conversions
    def to_local(self, point):
        dx = point[0] - self.origin[0]
        dy = point[1] - self.origin[1]
        return (dx * self._cos + dy * self._sin, -dx * self._sin + dy * self._cos)

    def to_world(self, point):
        x, y = point
        return (self.origin[0] + x * self._cos - y * self._sin,
                self.origin[1] + x * self._sin + y * self._cos)

    # Lattice
    def local_center(self, i, j):
        """Odd rows shift by half a pitch."""
        return ((i + 0.5 * (j & 1)) * self.pitch, j * self.row_spacing)

    def local_vertices(self, i, j):
        cx, cy = self.local_center(i, j)
        return [(cx + vx, cy + vy) for vx, vy in self._corners]

    def center(self, i, j):
        return self.to_world(self.local_center(i, j))

    def vertices(self, i, j):
        return [self.to_world(p) for p in self.local_vertices(i, j)]

    def _rows(self, ymin, ymax):
        """Rows whose hexes can overlap the local y-range [ymin, ymax]."""
        eps = 1e-9 * self.pitch
        return range(math.ceil((ymin - self.radius - eps) / self.row_spacing),
                     math.floor((ymax + self.radius + eps) / self.row_spacing) + 1)

    def _cols(self, j, xmin, xmax):
        """Columns of row j whose hexes can overlap the local x-range."""
        eps = 1e-9 * self.pitch
        half = self.cell_size / 2.0
        shift = 0.5 * (j & 1) * self.pitch
        return range(math.ceil((xmin - half - shift - eps) / self.pitch),
                     math.floor((xmax + half - shift + eps) / self.pitch) + 1)

    def fill(self, rings):
        """Classify every cell that overlaps the region bounded by ``rings``.

        Returns a list of :class:`Cell`. Cells fully outside are omitted.
        """
        segments = []
        for ring in rings:
            pts = [self.to_local(p) for p in ring]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                if a != b:
                    segments.append((a, b))
        if not segments:
            return []

        # Bucket boundary segments by the cells whose hex bbox they may touch.
        near = {}
        for idx, ((x0, y0), (x1, y1)) in enumerate(segments):
            xmin, xmax = min(x0, x1), max(x0, x1)
            for j in self._rows(min(y0, y1), max(y0, y1)):
                for i in self._cols(j, xmin, xmax):
                    near.setdefault((i, j), []).append(idx)

        xs = [c for s in segments for c in (s[0][0], s[1][0])]
        ys = [c for s in segments for c in (s[0][1], s[1][1])]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)

        cells = []
        for j in self._rows(ymin, ymax):
            crossings = _row_crossings(segments, j * self.row_spacing)
            for i in self._cols(j, xmin, xmax):
                hexagon = self.local_vertices(i, j)
                nearby = near.get((i, j))
                if nearby and any(_segment_enters_convex(segments[k], hexagon)
                                  for k in nearby):
                    status = STRADDLE
                else:
                    # Boundary does not enter the hex, so the hex is wholly on
                    # one side: its centre decides (even-odd rule).
                    cx = self.local_center(i, j)[0]
                    if bisect_left(crossings, cx) % 2 == 0:
                        continue
                    status = INSIDE
                cells.append(Cell((i, j), self.center(i, j),
                                  [self.to_world(p) for p in hexagon], status))
        return cells


# --- Geometry helpers -----------------------------------------------------

def _row_crossings(segments, y):
    """Sorted x positions where a horizontal line at y crosses the rings."""
    xs = []
    for (x0, y0), (x1, y1) in segments:
        if (y0 <= y) != (y1 <= y):
            xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    return xs


def _segment_enters_convex(segment, polygon, eps=1e-9):
    """True if the segment passes through the interior of a CCW convex polygon.

    Cyrus-Beck clipping: touching only an edge or a corner does not count.
    """
    (ax, ay), (bx, by) = segment
    dx, dy = bx - ax, by - ay
    t_lo, t_hi = 0.0, 1.0
    scale = eps * max(1.0, abs(polygon[0][0]), abs(polygon[0][1]))
    for (qx, qy), (rx, ry) in zip(polygon, polygon[1:] + polygon[:1]):
        nx, ny = -(ry - qy), rx - qx  # inward normal for CCW polygon
        num = nx * (ax - qx) + ny * (ay - qy) - scale * math.hypot(nx, ny)
        den = nx * dx + ny * dy
        if den == 0.0:
            if num <= 0.0:
                return False
        elif den > 0.0:
            t_lo = max(t_lo, -num / den)
        else:
            t_hi = min(t_hi, -num / den)
        if t_lo >= t_hi:
            return False
    return True
