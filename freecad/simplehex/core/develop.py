# SPDX-License-Identifier: LGPL-2.1-or-later
"""Developments (unrollings) of cylinders and cones. Must not import FreeCAD.

A development maps surface parameters ``(u, v)`` to a flat plane ``(x, y)``
without stretching, so hex cells laid out flat keep their true size when
mapped back. Parameters follow OpenCASCADE: ``u`` is the angle around the
axis, ``v`` runs along the axis (cylinder) or the generatrix (cone).
"""

import math

from .hexgrid import FLAT_TOP, SQRT3


class CylinderDevelopment:
    """Cylinder of radius r: x = r * u (arc length), y = v."""

    affine = True

    def __init__(self, radius):
        if radius <= 0:
            raise ValueError("Radius must be positive")
        self.radius = float(radius)
        self.circumference = 2.0 * math.pi * self.radius

    def to_flat(self, u, v):
        return (self.radius * u, v)

    def to_param(self, x, y):
        return (x / self.radius, y)


class ConeDevelopment:
    """Cone with radius ``radius`` at v = 0 and the given semi-angle.

    The cone unrolls to an annular sector around the apex. The sector is
    centred on the +x axis at ``u_mid`` so the polar angle stays within
    (-pi, pi) for any part of the cone.
    """

    affine = False

    def __init__(self, radius, semi_angle, u_mid=0.0):
        s = math.sin(semi_angle)
        if abs(s) < 1e-12:
            raise ValueError("Semi-angle must not be zero")
        self.radius = float(radius)
        self.sin = s
        self.k = abs(s)  # sector angle = 2 * pi * k
        self.u_mid = float(u_mid)

    def local_radius(self, v):
        return self.radius + v * self.sin

    def to_flat(self, u, v):
        rho = self.local_radius(v) / self.k
        phi = (u - self.u_mid) * self.k
        return (rho * math.cos(phi), rho * math.sin(phi))

    def to_param(self, x, y):
        rho = math.hypot(x, y)
        phi = math.atan2(y, x)
        return (phi / self.k + self.u_mid, (rho * self.k - self.radius) / self.sin)


def unwrap_angles(us, period=2.0 * math.pi):
    """Make a sequence of periodic angles continuous (no jumps > period / 2)."""
    out = []
    for u in us:
        if out:
            u += period * round((out[-1] - u) / period)
        out.append(u)
    return out


def lattice_period(pitch, orientation):
    """Shortest repeat of the hex lattice along its x axis (angle 0)."""
    return pitch * (SQRT3 if orientation == FLAT_TOP else 1.0)


def wrap_pitch(circumference, pitch, orientation):
    """Pitch adjusted so the lattice repeats exactly around a circumference.

    Returns ``(repeats, actual_pitch)``, rounding to the nearest whole number
    of repeats (at least one).
    """
    repeats = max(1, round(circumference / lattice_period(pitch, orientation)))
    return repeats, pitch * circumference / (repeats * lattice_period(pitch, orientation))
