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

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads
