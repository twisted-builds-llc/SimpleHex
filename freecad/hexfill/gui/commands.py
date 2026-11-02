# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCAD as App
import FreeCADGui as Gui

from .. import icon
from ..features.hexfill import make_hexfill


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
        source = (sel.Object, list(sel.SubElementNames))
        doc = App.ActiveDocument
        doc.openTransaction("Hex Fill Region")
        try:
            make_hexfill(doc, source)
            if not sel.SubElementNames:
                sel.Object.Visibility = False
            doc.recompute()
        finally:
            doc.commitTransaction()


COMMANDS = {"HexFill_Region": HexFillRegionCommand()}

for _name, _command in COMMANDS.items():
    Gui.addCommand(_name, _command)
