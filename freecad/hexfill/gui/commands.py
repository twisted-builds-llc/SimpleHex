# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from .. import icon
from ..export import export_dxf
from ..features.hexfill import make_hexfill
from ..features.pd_features import HexFillCut, HexFillPad, make_body_feature


def _is_hexfill(obj):
    return obj.isDerivedFrom("Part::FeaturePython") and "CellSize" in obj.PropertiesList


class HexFillRegionCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("HexFill.svg"),
            "MenuText": "Hex Fill Region",
            "ToolTip": "Fill a closed sketch, wire, or planar face with a hex pattern",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and bool(Gui.Selection.getSelectionEx())

    def Activated(self):
        sel = Gui.Selection.getSelectionEx()[0]
        doc = App.ActiveDocument
        # Persistent, so it outlives this command; the task panel closes it.
        App.setActiveTransaction("Hex Fill Region", True)
        obj = make_hexfill(doc, (sel.Object, list(sel.SubElementNames)))
        doc.recompute()
        Gui.ActiveDocument.setEdit(obj, 0)


def _body_for(obj):
    """The PartDesign Body holding obj, else the active Body, else None."""
    parent = obj.getParentGeoFeatureGroup()
    if parent is not None and parent.isDerivedFrom("PartDesign::Body"):
        return parent
    view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
    return view.getActiveObject("pdbody") if view else None


class BodyFeatureCommand:
    """Create a HexFillCut or HexFillPad in the Body of the selected sketch/face."""

    def __init__(self, feature_class, pixmap, menu_text, tooltip):
        self.feature_class = feature_class
        self.resources = {"Pixmap": icon(pixmap), "MenuText": menu_text, "ToolTip": tooltip}

    def GetResources(self):
        return self.resources

    def IsActive(self):
        return App.ActiveDocument is not None and bool(Gui.Selection.getSelectionEx())

    def Activated(self):
        sel = Gui.Selection.getSelectionEx()[0]
        body = _body_for(sel.Object)
        if body is None:
            QtGui.QMessageBox.warning(
                Gui.getMainWindow(), self.resources["MenuText"],
                "Select a sketch or face inside a PartDesign Body, or activate a Body.")
            return
        App.setActiveTransaction(self.resources["MenuText"], True)
        obj = make_body_feature(body, (sel.Object, list(sel.SubElementNames)),
                                self.feature_class)
        App.ActiveDocument.recompute()
        Gui.ActiveDocument.setEdit(obj, 0)


class ExportDxfCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("HexFillExportDXF.svg"),
            "MenuText": "Export to DXF",
            "ToolTip": "Export selected Hex Fill objects and their source outlines to DXF",
        }

    def IsActive(self):
        return any(_is_hexfill(o) for o in Gui.Selection.getSelection())

    def Activated(self):
        fills = [o for o in Gui.Selection.getSelection() if _is_hexfill(o)]
        if any(o.Output == "Solid" for o in fills):
            QtGui.QMessageBox.warning(Gui.getMainWindow(), "Export to DXF",
                                      "Set Output to Faces or Wires to export a flat DXF.")
            return
        path, _ = QtGui.QFileDialog.getSaveFileName(
            Gui.getMainWindow(), "Export to DXF", "", "DXF (*.dxf)")
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"
        export_dxf(fills, path)


COMMANDS = {
    "HexFill_Region": HexFillRegionCommand(),
    "HexFill_Cut": BodyFeatureCommand(
        HexFillCut, "HexFillCut.svg", "Hex Fill Cut",
        "Cut a hex pattern into the Body (PartDesign feature)"),
    "HexFill_Pad": BodyFeatureCommand(
        HexFillPad, "HexFillPad.svg", "Hex Fill Pad",
        "Raise a hex pattern on the Body (PartDesign feature)"),
    "HexFill_ExportDXF": ExportDxfCommand(),
}

for _name, _command in COMMANDS.items():
    Gui.addCommand(_name, _command)
