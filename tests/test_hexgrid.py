# SPDX-License-Identifier: LGPL-2.1-or-later
import math

import pytest

from freecad.simplehex.core import hexgrid as hg
from freecad.simplehex.core.hexgrid import HexGrid, INSIDE, STRADDLE


# --- Oracles --------------------------------------------------------------

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, r, n=256):
    return [(cx + r * math.cos(2 * math.pi * k / n),
             cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def overlaps(a, b, eps=1e-9):
    """Separating-axis test: convex polygons share interior area."""
    for poly in (a, b):
        for p, q in zip(poly, poly[1:] + poly[:1]):
            nx, ny = q[1] - p[1], p[0] - q[0]
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if max(pa) <= min(pb) + eps or max(pb) <= min(pa) + eps:
                return False
    return True


def in_rect(pt, r, eps=1e-9):
    return r[0][0] - eps <= pt[0] <= r[2][0] + eps and r[0][1] - eps <= pt[1] <= r[2][1] + eps


def inside_ids(cells):
    return {c.index for c in cells if c.status == INSIDE}


# --- Formulas -------------------------------------------------------------

def test_scalar_formulas():
    assert hg.pitch(6, 1.2) == pytest.approx(7.2)
    assert hg.circumradius(6) == pytest.approx(6 / math.sqrt(3))
    assert hg.cell_area(6) == pytest.approx(math.sqrt(3) / 2 * 36)
    assert hg.open_area_ratio(6, 1.2) == pytest.approx((6 / 7.2) ** 2)


def test_sizing_conversions():
    f, w = hg.from_corner_to_corner(2 * hg.circumradius(6), 1.2)
    assert (f, w) == (pytest.approx(6), 1.2)
    f, w = hg.from_pitch_and_open_area(7.2, (6 / 7.2) ** 2)
    assert f == pytest.approx(6) and w == pytest.approx(1.2)
    with pytest.raises(ValueError):
        hg.from_pitch_and_open_area(7.2, 0)


@pytest.mark.parametrize("args", [(0, 1), (6, -0.1)])
def test_invalid_grid(args):
    with pytest.raises(ValueError):
        HexGrid(*args)


# --- Lattice --------------------------------------------------------------

@pytest.mark.parametrize("orientation", hg.ORIENTATIONS)
@pytest.mark.parametrize("angle", [0, 17, 90])
def test_six_neighbours_at_pitch(orientation, angle):
    g = HexGrid(6, 1.2, orientation, angle, origin=(3, -4))
    c = g.center(0, 0)
    dists = sorted(math.dist(c, g.center(i, j))
                   for i in range(-2, 3) for j in range(-2, 3) if (i, j) != (0, 0))
    assert dists[:6] == pytest.approx([7.2] * 6)
    assert dists[6] > 7.2 + 1e-6


def test_vertices_and_orientation():
    pointy = HexGrid(6, 1)
    flat = HexGrid(6, 1, hg.FLAT_TOP)
    r = hg.circumradius(6)
    # Pointy-top has a corner straight up; flat-top has a corner on +x.
    assert any(v == pytest.approx((0, r)) for v in pointy.vertices(0, 0))
    assert any(v == pytest.approx((r, 0)) for v in flat.vertices(0, 0))
    # Flat-to-flat distance is the cell size.
    vs = pointy.vertices(0, 0)
    assert max(abs(x) for x, _ in vs) * 2 == pytest.approx(6)


def test_origin_anchors_lattice():
    g = HexGrid(5, 1, angle=30, origin=(10, 20))
    assert g.center(0, 0) == pytest.approx((10, 20))
    assert g.to_local(g.to_world((1.5, -2.5))) == pytest.approx((1.5, -2.5))


# --- Region classification -----------------------------------------------

@pytest.mark.parametrize("orientation", hg.ORIENTATIONS)
@pytest.mark.parametrize("angle", [0, 13.5, 45, 90])
@pytest.mark.parametrize("origin", [(0, 0), (1.1, 2.3)])
def test_rectangle_matches_brute_force(orientation, angle, origin):
    region = rect(0, 0, 100, 60)
    g = HexGrid(6, 1.2, orientation, angle, origin)
    cells = g.fill([region])

    expected_inside, expected_any = set(), set()
    for i in range(-40, 41):
        for j in range(-40, 41):
            vs = g.vertices(i, j)
            if all(in_rect(v, region) for v in vs):
                expected_inside.add((i, j))
            if overlaps(vs, region):
                expected_any.add((i, j))

    assert inside_ids(cells) == expected_inside
    assert {c.index for c in cells} == expected_any
    assert expected_inside  # sanity


def test_rectangle_with_hole_matches_brute_force():
    outer, hole = rect(0, 0, 100, 60), rect(30, 20, 55, 41)
    g = HexGrid(6, 1.2, angle=7, origin=(50, 30))
    cells = g.fill([outer, hole])

    expected = set()
    for i in range(-20, 21):
        for j in range(-20, 21):
            vs = g.vertices(i, j)
            if all(in_rect(v, outer) for v in vs) and not overlaps(vs, hole):
                expected.add((i, j))
    assert inside_ids(cells) == expected
    # No kept cell centre lies in the hole.
    assert not any(in_rect(c.center, hole) for c in cells if c.status == INSIDE)


def test_small_hole_inside_one_cell_makes_it_straddle():
    g = HexGrid(10, 1)
    cells = g.fill([rect(-50, -50, 50, 50), rect(-1, -1, 1, 1)])
    by_index = {c.index: c for c in cells}
    assert by_index[(0, 0)].status == STRADDLE


def test_circle_cells_within_radius():
    g = HexGrid(4, 0.8, origin=(0, 0))
    cells = g.fill([circle(0, 0, 30)])
    inside = [c for c in cells if c.status == INSIDE]
    assert inside
    assert all(math.hypot(*v) <= 30 + 1e-9 for c in inside for v in c.vertices)
    # Every lattice cell well inside the circle is found.
    expected = {(i, j) for i in range(-10, 11) for j in range(-10, 11)
                if math.hypot(*g.center(i, j)) + g.radius < 30 * math.cos(math.pi / 256)}
    assert expected <= inside_ids(cells)


def test_ring_orientation_and_closing_point_do_not_matter():
    g = HexGrid(6, 1.2)
    a = g.fill([rect(0, 0, 50, 40)])
    ring = list(reversed(rect(0, 0, 50, 40)))
    b = g.fill([ring + ring[:1]])
    assert inside_ids(a) == inside_ids(b)


def test_empty_region():
    assert HexGrid(6, 1).fill([]) == []


# --- Corner fillets -------------------------------------------------------

def outline_polygon(outline, steps=200):
    """Densify an outline into points (arcs through start/mid/end)."""
    pts = []
    for seg in outline:
        if seg[0] == "line":
            pts.append(seg[1])
            continue
        _, p, m, q = seg
        # Circle through three points.
        ax, ay = p; bx, by = m; cx, cy = q
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
        uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
        r = math.hypot(ax - ux, ay - uy)
        a0 = math.atan2(ay - uy, ax - ux)
        a1 = math.atan2(cy - uy, cx - ux)
        sweep = (a1 - a0) % (2 * math.pi)
        pts += [(ux + r * math.cos(a0 + sweep * t / steps), uy + r * math.sin(a0 + sweep * t / steps))
                for t in range(steps)]
    return pts


def shoelace(pts):
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


@pytest.mark.parametrize("radius", [0.5, 1.5, 2.9])
def test_rounded_hex_area_matches_formula(radius):
    g = HexGrid(6, 1, angle=20, origin=(3, 4))
    outline = hg.rounded_outline(g.vertices(1, 1), radius)
    assert [s[0] for s in outline] == ["arc", "line"] * 6
    assert shoelace(outline_polygon(outline)) == pytest.approx(hg.cell_area(6, radius), rel=1e-4)


def test_max_radius_gives_circle():
    g = HexGrid(6, 1)
    outline = hg.rounded_outline(g.vertices(0, 0), hg.max_corner_radius(6))
    assert [s[0] for s in outline] == ["arc"] * 6
    for pt in outline_polygon(outline, 10):
        assert math.hypot(*pt) == pytest.approx(3)
    assert hg.cell_area(6, 3) == pytest.approx(math.pi * 9)


def test_corner_radius_limits():
    with pytest.raises(ValueError):
        hg.cell_area(6, 3.1)
    with pytest.raises(ValueError):
        hg.rounded_outline(HexGrid(6, 1).vertices(0, 0), 3.1)
