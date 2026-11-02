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

    # PartDesign: Hex Fill Cut in a Body
    body = doc.addObject("PartDesign::Body", "Body")
    plate = doc.addObject("Sketcher::SketchObject", "Plate")
    body.addObject(plate)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        plate.addGeometry(Part.LineSegment(a, b))
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = plate
    pad.Length = 3
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(plate)
    Gui.runCommand("HexFill_Cut")
    cut = doc.getObject("HexFillCut")
    panel = active_panel()
    assert not panel.has_output and "through all" in panel.depth_label.text()
    assert body.Tip == cut and cut.isValid(), cut.getStatusString()
    panel.radius_box.setProperty("rawValue", 1.0)
    panel.accept()
    assert cut.isValid() and cut.CornerRadius.Value == 1.0
    assert cut.Shape.Volume < pad.Shape.Volume
    assert cut.ViewObject.Proxy.getIcon().endswith("HexFillCut.svg")
    log("PASS Hex Fill Cut + OK")

    # Hex Fill Pad on a face, then Cancel: object gone, Tip restored
    faces = cut.Shape.Faces
    top = max(range(len(faces)), key=lambda i: faces[i].CenterOfMass.z)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(cut, "Face{}".format(top + 1))
    count = len(doc.Objects)
    Gui.runCommand("HexFill_Pad")
    assert len(doc.Objects) == count + 1 and body.Tip.Name == "HexFillPad"
    active_panel().reject()
    assert len(doc.Objects) == count and body.Tip == cut
    log("PASS Hex Fill Pad + Cancel")

    # Curved face: Hex Fill Region makes a HexSurface; Cut makes a HexSurfaceCut
    tube = doc.addObject("Part::Feature", "Tube")
    tube.Shape = Part.makeCylinder(25, 40).cut(Part.makeCylinder(22, 40))
    outer = next(i for i, f in enumerate(tube.Shape.Faces)
                 if isinstance(f.Surface, Part.Cylinder) and f.Surface.Radius > 24)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(tube, "Face{}".format(outer + 1))
    Gui.runCommand("HexFill_Region")
    surface = doc.getObject("HexSurface")
    panel = active_panel()
    assert panel.has_mode and not panel.has_output and not panel.has_reversed
    assert panel.preview_key == "LivePreviewSurface"
    assert panel.depth_label.text() == "Depth (0 = through)"  # Cut is the default mode
    panel.mode.setCurrentIndex(1)
    assert surface.Mode == "Emboss" and panel.depth_label.text() == "Depth"
    panel.mode.setCurrentIndex(0)
    assert panel.depth_label.text() == "Depth (0 = through)"
    panel.accept()
    assert surface.isValid(), surface.getStatusString()
    assert surface.CellCount > 0 and surface.Shape.Solids
    log("PASS Hex Pattern on Surface")

    ring = doc.addObject("Sketcher::SketchObject", "RingSketch")
    body2 = doc.addObject("PartDesign::Body", "Body001")
    body2.addObject(ring)
    ring.addGeometry(Part.Circle(App.Vector(), App.Vector(0, 0, 1), 20))
    ring.addGeometry(Part.Circle(App.Vector(), App.Vector(0, 0, 1), 17))
    ring_pad = body2.newObject("PartDesign::Pad", "RingPad")
    ring_pad.Profile = ring
    ring_pad.Length = 30
    doc.recompute()
    outer = next(i for i, f in enumerate(ring_pad.Shape.Faces)
                 if isinstance(f.Surface, Part.Cylinder) and f.Surface.Radius > 19)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(ring_pad, "Face{}".format(outer + 1))
    Gui.runCommand("HexFill_Cut")
    vent = doc.getObject("HexSurfaceCut")
    panel = active_panel()
    assert vent is not None and body2.Tip == vent
    assert panel.depth_label.text() == "Depth (0 = through)"
    panel.accept()
    assert vent.isValid(), vent.getStatusString()
    assert vent.ViewObject.Proxy.getIcon().endswith("HexFillCut.svg")
    log("PASS Hex Fill Cut on a curved face")


try:
    main()
    status = 0
except Exception:
    traceback.print_exc(file=OUT)
    status = 1
OUT.flush()
os._exit(status)
