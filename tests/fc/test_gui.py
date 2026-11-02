# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI smoke test: command, task panel, OK/Cancel transactions.

Run with the FreeCAD GUI (offscreen is fine) from the repository root:

    QT_QPA_PLATFORM=offscreen <FreeCAD AppImage> tests/fc/test_gui.py

Results go to stdout; the process exits 1 on failure.
"""

import os
import sys
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = sys.__stdout__


def log(*args):
    print(*args, file=OUT, flush=True)


def main():
    sys.path.insert(0, ROOT)
    import freecad

    freecad.__path__.append(os.path.join(ROOT, "freecad"))

    import FreeCAD as App
    import FreeCADGui as Gui
    import Part
    import freecad.hexfill.init_gui  # noqa: F401  registers the workbench
    from freecad.hexfill.gui.taskpanel import HexFillTaskPanel

    def active_panel():
        dialog = Gui.Control.activeDialog()
        assert dialog, "no task dialog open"
        import gc
        panels = [o for o in gc.get_objects()
                  if isinstance(o, HexFillTaskPanel) and o not in seen]
        assert len(panels) == 1, panels
        seen.append(panels[0])
        return panels[0]

    seen = []
    Gui.activateWorkbench("HexFillWorkbench")

    doc = App.newDocument("HexFillGui")
    sk = doc.addObject("Sketcher::SketchObject", "Region")
    pts = [App.Vector(0, 0, 0), App.Vector(120, 0, 0), App.Vector(120, 80, 0), App.Vector(0, 80, 0)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        sk.addGeometry(Part.LineSegment(a, b))
    sk.addGeometry(Part.Circle(App.Vector(60, 40, 0), App.Vector(0, 0, 1), 15))
    doc.recompute()

    # Create, preview, OK
    Gui.Selection.addSelection(sk)
    Gui.runCommand("HexFill_Region")
    obj = doc.getObject("HexFill")
    panel = active_panel()
    assert obj.CellCount == 140, obj.CellCount
    panel.edge_mode.setCurrentIndex(2)
    assert obj.EdgeMode == "ClipMinArea" and obj.CellCount > 140
    panel.size_box.setProperty("rawValue", 8.0)
    assert obj.CellSize.Value == 8.0 and obj.Pitch.Value == 9.2
    panel.sizing.setCurrentIndex(2)  # pitch + open area
    panel.open_box.setValue(50.0)
    size, wall = obj.CellSize.Value, obj.Wall.Value
    assert abs((size / (size + wall)) ** 2 - 0.5) < 1e-3
    panel.radius_box.setProperty("rawValue", 99.0)
    assert "Corner radius" in panel.warning.text()
    panel.radius_box.setProperty("rawValue", 0.5)
    panel.accept()
    assert App.getActiveTransaction() is None
    assert obj.isValid() and obj.CornerRadius.Value == 0.5
    assert not sk.Visibility
    log("PASS create + OK")

    # Edit, Cancel restores values
    before = obj.CellSize.Value
    Gui.ActiveDocument.setEdit(obj, 0)
    panel = active_panel()
    panel.sizing.setCurrentIndex(0)
    panel.size_box.setProperty("rawValue", 12.0)
    assert obj.CellSize.Value == 12.0
    panel.reject()
    assert obj.CellSize.Value == before, obj.CellSize
    log("PASS edit + Cancel")

    # Create, Cancel removes the object and keeps the source visible
    sk.Visibility = True
    count = len(doc.Objects)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sk)
    Gui.runCommand("HexFill_Region")
    assert len(doc.Objects) == count + 1
    active_panel().reject()
    assert len(doc.Objects) == count and sk.Visibility
    log("PASS create + Cancel")


try:
    main()
    status = 0
except Exception:
    traceback.print_exc(file=OUT)
    status = 1
os._exit(status)
