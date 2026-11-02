# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from .. import icon
from ..export import export_dxf
from ..features.simplehex import make_simplehex
from ..features.pd_features import (SimpleHexCut, SimpleHexPad, HexSurfaceCut, HexSurfacePad,
                                   make_body_feature)
from ..features.surface import is_curved, make_hexsurface


def _curved_face(sel):
    """True when the selection is one curved (non-planar) face."""
    names = [n for n in sel.SubElementNames if n]
    if len(names) != 1 or not names[0].startswith("Face"):
        return False
    return is_curved(sel.Object.Shape.getElement(names[0]))


def _is_simplehex(obj):
    """A flat SimpleHex (Part feature with an Output), the only DXF-exportable kind."""
    return obj.isDerivedFrom("Part::FeaturePython") and "Output" in obj.PropertiesList


class SimpleHexRegionCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("SimpleHex.svg"),
            "MenuText": "Hex Fill Region",
            "ToolTip": "Fill a closed sketch, wire, or planar face with a hex pattern. "
                       "On a curved face, make hex cell solids to cut or emboss",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and bool(Gui.Selection.getSelectionEx())

    def Activated(self):
        sel = Gui.Selection.getSelectionEx()[0]
        doc = App.ActiveDocument
        # Persistent, so it outlives this command; the task panel closes it.
        App.setActiveTransaction("Hex Fill Region", True)
        source = (sel.Object, list(sel.SubElementNames))
        make = make_hexsurface if _curved_face(sel) else make_simplehex
        obj = make(doc, source)
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
    """Create a SimpleHexCut or SimpleHexPad in the Body of the selected sketch/face."""

    def __init__(self, feature_class, surface_class, pixmap, menu_text, tooltip):
        self.feature_class = feature_class
        self.surface_class = surface_class
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
        feature_class = self.surface_class if _curved_face(sel) else self.feature_class
        obj = make_body_feature(body, (sel.Object, list(sel.SubElementNames)), feature_class)
        App.ActiveDocument.recompute()
        Gui.ActiveDocument.setEdit(obj, 0)


class ExportDxfCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("SimpleHexExportDXF.svg"),
            "MenuText": "Export to DXF",
            "ToolTip": "Export selected SimpleHex objects and their source outlines to DXF",
        }

    def IsActive(self):
        return any(_is_simplehex(o) for o in Gui.Selection.getSelection())

    def Activated(self):
        fills = [o for o in Gui.Selection.getSelection() if _is_simplehex(o)]
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
    "SimpleHex_Region": SimpleHexRegionCommand(),
    "SimpleHex_Cut": BodyFeatureCommand(
        SimpleHexCut, HexSurfaceCut, "SimpleHexCut.svg", "Hex Fill Cut",
        "Cut a hex pattern into the Body (PartDesign feature). Works on sketches, "
        "planar faces, and curved faces"),
    "SimpleHex_Pad": BodyFeatureCommand(
        SimpleHexPad, HexSurfacePad, "SimpleHexPad.svg", "Hex Fill Pad",
        "Raise a hex pattern on the Body (PartDesign feature). Works on sketches, "
        "planar faces, and curved faces"),
    "SimpleHex_ExportDXF": ExportDxfCommand(),
}

for _name, _command in COMMANDS.items():
    Gui.addCommand(_name, _command)
