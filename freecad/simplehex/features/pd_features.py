# SPDX-License-Identifier: LGPL-2.1-or-later
"""PartDesign SimpleHexCut / SimpleHexPad: hex patterns as native Body features."""

import FreeCAD as App
import Part

from .simplehex import SimpleHexError, add_pattern_properties, add_property, compute_pattern
from .surface import surface_tools

V = App.Vector


class SimpleHexBodyFeature:
    """Common base; subclasses set ``subtractive`` and ``type_id``."""

    subtractive = True
    type_id = None

    def __init__(self, obj):
        obj.Proxy = self
        self.add_properties(obj)

    def add_properties(self, obj):
        add_pattern_properties(obj)
        doc = ("Cut depth into the material; 0 cuts through all, both sides"
               if self.subtractive else "Height of the raised cells")
        add_property(obj, "App::PropertyLength", "Depth", "SimpleHex", doc,
                     0.0 if self.subtractive else 1.0)
        add_property(obj, "App::PropertyBool", "Reversed", "SimpleHex",
                     "Flip the direction relative to the sketch normal", False)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads

    def execute(self, obj):
        base = obj.BaseFeature.Shape if obj.BaseFeature else Part.Shape()
        if base.isNull() or not base.Solids:
            raise SimpleHexError("Needs a solid to work on: add it after a Pad or other "
                               "feature in the Body")
        tool = self.make_tool(obj, base)
        if not tool.Solids:
            raise SimpleHexError("No cells fit in the region")

        result = base.cut(tool) if self.subtractive else base.fuse(tool)
        if obj.Refine:
            result = result.removeSplitter()
        if len(result.Solids) != 1:
            raise SimpleHexError(
                "Result has {} solids; a Body needs exactly one. "
                "Check Depth, Reversed and the edge mode.".format(len(result.Solids)))

        obj.AddSubShape = tool
        obj.Shape = result

    def make_tool(self, obj, base):
        """Prisms of the flat pattern, in Body coordinates."""
        faces, placement = compute_pattern(obj)
        if not faces:
            return Part.Compound([])
        start, extent = self._extrusion(obj, base, placement)
        tool = Part.makeCompound([f.translated(V(0, 0, start)).extrude(V(0, 0, extent))
                                  for f in faces])
        tool.transformShape(placement.toMatrix())
        return tool

    def _extrusion(self, obj, base, placement):
        """Return (start, extent) along the region's local Z."""
        depth = obj.Depth.Value
        if self.subtractive and depth <= 0:
            box = base.BoundBox
            length = box.DiagonalLength + (box.Center - placement.Base).Length + 1.0
            return -length, 2.0 * length
        if depth <= 0:
            raise SimpleHexError("Depth must be greater than zero")
        # Cuts go into the material (against the sketch normal), pads out of it.
        direction = -1.0 if self.subtractive else 1.0
        if obj.Reversed:
            direction = -direction
        return 0.0, direction * depth


class SimpleHexCut(SimpleHexBodyFeature):
    subtractive = True
    type_id = "PartDesign::FeatureSubtractivePython"


class SimpleHexPad(SimpleHexBodyFeature):
    subtractive = False
    type_id = "PartDesign::FeatureAdditivePython"


class HexSurfaceBodyFeature(SimpleHexBodyFeature):
    """Pattern on a curved face of the Body."""

    def add_properties(self, obj):
        add_pattern_properties(obj)
        doc = ("Depth along the surface normal; 0 cuts through the wall"
               if self.subtractive else "Height of the raised cells")
        add_property(obj, "App::PropertyLength", "Depth", "SimpleHex", doc,
                     0.0 if self.subtractive else 1.0)

    def make_tool(self, obj, base):
        return Part.makeCompound(surface_tools(obj, base, self.subtractive))


class HexSurfaceCut(HexSurfaceBodyFeature):
    subtractive = True
    type_id = "PartDesign::FeatureSubtractivePython"


class HexSurfacePad(HexSurfaceBodyFeature):
    subtractive = False
    type_id = "PartDesign::FeatureAdditivePython"


def make_body_feature(body, source, feature_class):
    """Add a SimpleHexCut or SimpleHexPad after the Body's Tip."""
    obj = body.newObject(feature_class.type_id, feature_class.__name__)
    feature_class(obj)
    obj.Source = source
    if App.GuiUp:
        from ..gui.viewproviders import ViewProviderSimpleHex
        ViewProviderSimpleHex(obj.ViewObject)
    return obj
