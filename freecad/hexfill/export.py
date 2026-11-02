# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flat export helpers (no GUI needed)."""


def export_dxf(fills, path):
    """Write the patterns plus their sketch/wire sources (the part outline)."""
    import importDXF

    objects = []
    for fill in fills:
        source = fill.Source
        if source and not any(s for s in source[1]) and source[0] not in objects:
            objects.append(source[0])
        objects.append(fill)
    importDXF.export(objects, path)
