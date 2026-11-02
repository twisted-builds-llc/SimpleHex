# SPDX-License-Identifier: LGPL-2.1-or-later
import math

import pytest

from freecad.hexfill.core import hexgrid as hg
from freecad.hexfill.core.develop import (
    ConeDevelopment, CylinderDevelopment, lattice_period, unwrap_angles, wrap_pitch)


def cylinder_point(r, u, v):
    return (r * math.cos(u), r * math.sin(u), v)


def cone_point(r0, a, u, v):
    rad = r0 + v * math.sin(a)
    return (rad * math.cos(u), rad * math.sin(u), v * math.cos(a))


def check_isometry(dev, point, samples):
    """Small steps have the same length on the surface and in the plane."""
    h = 1e-5
    for u, v in samples:
        for du, dv in ((h, 0), (0, h), (h, h), (h, -2 * h)):
            surf = math.dist(point(u, v), point(u + du, v + dv))
            flat = math.dist(dev.to_flat(u, v), dev.to_flat(u + du, v + dv))
            assert flat == pytest.approx(surf, rel=1e-4)


SAMPLES = [(0.1, 2.0), (1.5, 10.0), (3.0, 0.0), (5.9, 25.0)]


def test_cylinder_is_isometric_and_invertible():
    dev = CylinderDevelopment(25)
    check_isometry(dev, lambda u, v: cylinder_point(25, u, v), SAMPLES)
    for u, v in SAMPLES:
        assert dev.to_param(*dev.to_flat(u, v)) == pytest.approx((u, v))
    assert dev.circumference == pytest.approx(2 * math.pi * 25)


@pytest.mark.parametrize("angle", [0.35, -0.35, 1.2])
def test_cone_is_isometric_and_invertible(angle):
    dev = ConeDevelopment(30, angle, u_mid=math.pi)
    check_isometry(dev, lambda u, v: cone_point(30, angle, u, v), SAMPLES)
    for u, v in SAMPLES:
        assert dev.to_param(*dev.to_flat(u, v)) == pytest.approx((u, v))


def test_cone_sector_centred_on_u_mid():
    dev = ConeDevelopment(30, 0.35, u_mid=math.pi)
    # A full turn stays inside (-pi, pi) of polar angle, so it inverts cleanly.
    us = [i * 2 * math.pi / 100 for i in range(100)]
    assert [dev.to_param(*dev.to_flat(u, 5.0))[0] for u in us] == pytest.approx(us)


def test_invalid_developments():
    with pytest.raises(ValueError):
        CylinderDevelopment(0)
    with pytest.raises(ValueError):
        ConeDevelopment(10, 0.0)


def test_unwrap_angles():
    raw = [6.0, 6.2, 0.1, 0.3, 6.25, 6.28, 0.0]
    out = unwrap_angles(raw)
    assert all(abs(b - a) < math.pi for a, b in zip(out, out[1:]))
    assert out[2] == pytest.approx(0.1 + 2 * math.pi)
    assert [(o - r) % (2 * math.pi) for o, r in zip(out, raw)] == pytest.approx([0] * 7, abs=1e-12)


@pytest.mark.parametrize("orientation", hg.ORIENTATIONS)
def test_wrap_pitch_repeats_exactly(orientation):
    circumference = 2 * math.pi * 25
    n, p = wrap_pitch(circumference, 7.2, orientation)
    assert n * lattice_period(p, orientation) == pytest.approx(circumference)
    assert abs(p - 7.2) <= lattice_period(7.2, orientation) / n
    # The lattice really repeats: shifting a centre by the circumference
    # lands on another lattice point.
    g = hg.HexGrid(p - 1.2, 1.2, orientation)
    for i in range(-5, 5):
        for j in range(-3, 3):
            x, y = g.center(i, j)
            lx, ly = g.to_local((x + circumference, y))
            row = ly / g.row_spacing
            assert row == pytest.approx(round(row), abs=1e-9)
            col = lx / g.pitch - 0.5 * (round(row) & 1)
            assert col == pytest.approx(round(col), abs=1e-9)


def test_wrap_pitch_tiny_circumference():
    assert wrap_pitch(1.0, 7.2, hg.POINTY_TOP) == (1, pytest.approx(1.0))
