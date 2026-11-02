# SPDX-License-Identifier: LGPL-2.1-or-later
from .. import icon

ICONS = {"SimpleHexCut": "SimpleHexCut.svg", "SimpleHexPad": "SimpleHexPad.svg",
         "HexSurfaceCut": "SimpleHexCut.svg", "HexSurfacePad": "SimpleHexPad.svg"}


class ViewProviderSimpleHex:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        obj = getattr(self, "Object", None)
        kind = type(obj.Proxy).__name__ if obj is not None else "SimpleHex"
        return icon(ICONS.get(kind, "SimpleHex.svg"))

    def claimChildren(self):
        # Claim a whole-object source (a sketch), never the solid a face is on.
        source = self.Object.Source
        return [source[0]] if source and not any(source[1]) else []

    def doubleClicked(self, vobj):
        vobj.Document.setEdit(vobj.Object, 0)
        return True

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCAD as App
        import FreeCADGui as Gui
        from .taskpanel import SimpleHexTaskPanel

        # The create command already opened one; Cancel then removes the object.
        creating = App.getActiveTransaction() is not None
        if not creating:
            App.setActiveTransaction("Edit SimpleHex", True)
        Gui.Control.showDialog(SimpleHexTaskPanel(vobj.Object, creating))
        return True

    def unsetEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui as Gui

        Gui.Control.closeDialog()
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads
