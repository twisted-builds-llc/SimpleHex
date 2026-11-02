# SPDX-License-Identifier: LGPL-2.1-or-later
import FreeCADGui as Gui

from . import icon


class HexFillWorkbench(Gui.Workbench):
    MenuText = "HexFill"
    ToolTip = "Parametric hexagon patterns"
    Icon = icon("HexFill.svg")

    def Initialize(self):
        from .gui import commands

        names = list(commands.COMMANDS)
        self.appendToolbar("HexFill", names)
        self.appendMenu("HexFill", names)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(HexFillWorkbench())
