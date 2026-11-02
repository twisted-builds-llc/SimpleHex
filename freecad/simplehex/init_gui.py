# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCADGui as Gui

from . import icon


class SimpleHexWorkbench(Gui.Workbench):
    MenuText = "SimpleHex"
    ToolTip = "Parametric hexagon patterns"
    Icon = icon("SimpleHex.svg")

    def Initialize(self):
        from .gui import commands

        names = list(commands.COMMANDS)
        self.appendToolbar("SimpleHex", names)
        self.appendMenu("SimpleHex", names)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(SimpleHexWorkbench())
