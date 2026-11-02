# Changelog

## Unreleased
- Pure-Python hex grid core (`core/hexgrid.py`) with region classification and unit tests.
- `HexFill` Part::FeaturePython: WholeOnly fill of closed sketches, wires, or planar faces, including holes; Wires/Faces/Solid output.
- Workbench with "Hex Fill Region" command.
- Edge modes: WholeOnly, Clip, ClipMinArea (with MinCellFraction).
- CornerRadius fillets cell corners (up to CellSize / 2, which gives round holes).
- Task panel with live preview, sizing modes (flat-to-flat, corner-to-corner, pitch + open area), readouts and large-pattern warning.
- "Export to DXF" command (pattern plus its source outline).
- Example: `examples/plasma_panel.FCStd`.
- PartDesign features **Hex Fill Cut** (`PartDesign::FeatureSubtractivePython`; Depth 0 cuts through all, both sides) and **Hex Fill Pad** (`PartDesign::FeatureAdditivePython`; raised cells). Source can be a sketch or a planar face in the Body.
- Example: `examples/vent_cover.FCStd`.
- Hex patterns on cylindrical and conical faces: Part **HexSurface** (cell solids to cut or emboss) and PartDesign **HexSurfaceCut** / **HexSurfacePad**, created by the same commands when a curved face is selected. Cells keep their true size (exact unrolling), walls follow the surface normal, full 360° cylinders wrap seamlessly with the pitch adjusted to a whole number of cells. Depth 0 cuts through the wall.
- Example: `examples/cylinder_texture.FCStd`.
- Freeform faces (B-spline, sphere, ...): projection mode. The flat pattern is projected onto the face along its middle normal; recess floors / emboss tops follow the tangent plane at each cell, offset by Depth along the surface normal. Faces turning more than 75° from the middle normal are refused.
- Example: `examples/freeform_texture.FCStd`.
