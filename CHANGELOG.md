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
