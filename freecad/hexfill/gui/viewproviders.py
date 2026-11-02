# SPDX-License-Identifier: LGPL-2.1-or-later
from .. import icon


class ViewProviderHexFill:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return icon("HexFill.svg")

    def claimChildren(self):
        source = self.Object.Source
        return [source[0]] if source else []

    def doubleClicked(self, vobj):
        vobj.Document.setEdit(vobj.Object, 0)
        return True

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCAD as App
        import FreeCADGui as Gui
        from .taskpanel import HexFillTaskPanel

        # The create command already opened one; Cancel then removes the object.
        creating = App.getActiveTransaction() is not None
        if not creating:
            App.setActiveTransaction("Edit Hex Fill", True)
        Gui.Control.showDialog(HexFillTaskPanel(vobj.Object, creating))
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
