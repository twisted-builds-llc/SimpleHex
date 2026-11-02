# HexFill — FreeCAD Hexagon Pattern Workbench

**Design Document v0.1**
**Owner:** Dale / Twisted Builds LLC
**Status:** Draft, pre-development
**License:** LGPL-2.1-or-later (see §11)
**Working name:** "HexFill" (placeholder; check for name collisions on GitHub and the FreeCAD Addon catalog before publishing)

---

## 1. Summary

HexFill is an open source FreeCAD workbench that fills a user-chosen region with a parametric hexagon (honeycomb) pattern. The user selects a closed sketch (or a face), sets the hex size, wall thickness, margin and edge behavior, and gets a live, editable feature. Changing any value re-flows the pattern. The same engine also puts hex patterns on curved surfaces, either cut through or as a shallow texture.

Target uses:
- **3D printing:** lightweighting, vents, grilles, decorative infill panels
- **Laser / plasma / waterjet:** flat sheet parts with clean hex cutouts and no slivers, exported to DXF
- **Surface texture:** shallow hex recesses or embossing on a printed face, including curved faces

## 2. Why build this

Existing options and their gaps:

| Existing tool | What it does | Gap |
|---|---|---|
| Macro Honeycomb (TheMarkster, LGPL-2.1) | Parametric hex grid, rectangle or ellipse, optional border | Only rectangles and ovals, not arbitrary closed sketches. No surface support. No partial-cell control. |
| Macro FCHoneycombMaker (older) | Spreadsheet-driven Draft arrays | Not a real feature object. Superseded. |
| PartDesign MultiTransform / LinearPattern | Manual hex patterning | Tedious. Doesn't clip to an arbitrary boundary. Slow with many instances. |
| Curves WB "Map sketch on surface" + macro | Hexes on curved surfaces | Around 30 manual steps, plus cleanup of duplicate edges. Not parametric end-to-end. |

HexFill's job is to make "pick region → set numbers → done" a single feature, on flat and curved geometry.

## 3. Goals and non-goals

### Goals
1. Fill **any closed planar boundary** (sketch, face, or Draft wire), including boundaries with inner holes or islands, with a hex pattern.
2. Fully **parametric**: a FeaturePython object with editable properties and a task panel.
3. **Fabrication-aware** edge handling: whole cells only, clipped cells, or clipped cells with a minimum-sliver filter.
4. Work **in and out of PartDesign**: usable as a pocket/pad profile or directly as a subtractive/additive feature.
5. **Curved surfaces**: cylinders and cones in an early release, freeform B-spline faces later.
6. Installable through the **Addon Manager**.
7. A **pure-Python geometry core** with no FreeCAD dependency, so it can be unit-tested with pytest.

### Non-goals (for now)
- Other lattice types (triangle, Voronoi, gyroid). The architecture should allow them later, but v1 is hex only.
- Generating a Sketcher sketch with thousands of constrained hexes. That's too slow for the solver; see §6.
- Mesh-based output (STL texture displacement). We stay in B-rep.

## 4. User workflow

### 4.1 Flat region (primary workflow)
1. Draw a closed sketch for the region you want patterned, or select a planar face.
2. Click **HexFill → Hex Fill Region**.
3. In the task panel, set hex size, wall, margin, angle, edge mode, and output mode. The preview updates live.
4. Click OK. A `HexFill` object appears in the tree, linked to the source.
5. Use it:
   - **PartDesign:** as a subtractive feature (cuts through or to a depth) or as a profile for Pocket
   - **Part WB:** extrude it and Boolean-cut
   - **Sheet / plasma:** export the 2D result to DXF

### 4.2 Surface pattern
1. Select a face (cylinder, cone, or later, freeform).
2. Click **HexFill → Hex Pattern on Surface**.
3. Set the cell parameters plus **depth** and **mode**: cut through, recess (texture), or emboss.
4. The result is a solid you can Boolean with the body, or a PartDesign feature.

## 5. Parameters

All lengths are in document units (mm by default).

| Property | Type | Default | Notes |
|---|---|---|---|
| `Source` | Link / LinkSub | — | Closed sketch, wire, or face |
| `CellSize` | Length | 6.0 | Hex **flat-to-flat** opening (what you'd measure with calipers) |
| `Wall` | Length | 1.2 | Web thickness between neighboring cells |
| `Margin` | Length | 2.0 | Solid border kept inside the boundary (0 allowed) |
| `Orientation` | Enum | PointyTop | PointyTop / FlatTop |
| `Angle` | Angle | 0° | Rotates the whole grid |
| `OffsetX`, `OffsetY` | Length | 0 | Shifts the grid inside the region |
| `Anchor` | Enum | Centered | Centered / BoundaryOrigin / Custom (where the grid's origin sits) |
| `EdgeMode` | Enum | WholeOnly | WholeOnly / Clip / ClipMinArea |
| `MinCellFraction` | Float | 0.35 | For ClipMinArea: drop clipped cells smaller than this fraction of a full cell |
| `CornerRadius` | Length | 0 | Fillets cell corners (useful for printing and plasma) |
| `Output` | Enum | Faces | Wires / Faces / Solid |
| `Depth` | Length | 0 = through | For Solid output and surface mode |
| `Reversed` | Bool | False | Flips cut direction |
| **Read-only** |  |  |  |
| `CellCount` | Integer | — | Number of cells generated |
| `OpenAreaPercent` | Float | — | Open area / region area (handy for vents and airflow) |
| `Pitch` | Length | — | CellSize + Wall |

### Alternative sizing (task panel convenience)
The user can switch the panel between sizing modes; underneath, everything converts to `CellSize` + `Wall`:
- Flat-to-flat + wall (default)
- Corner-to-corner + wall
- Pitch + open-area %

## 6. Geometry engine

### 6.1 Grid math (pure Python, `hexgrid.py`)
For **pointy-top** hexes with flat-to-flat `F` and wall `W`:
- Pitch `P = F + W` (center-to-center distance between neighbors)
- Circumradius `R = F / √3`
- Column spacing `dx = P`
- Row spacing `dy = P · √3 / 2`
- Odd rows shift by `P / 2`
- Open-area ratio of an infinite grid = `(F / P)²`

Flat-top is the same grid rotated 90°. `Angle` applies an extra rotation about the anchor.

Steps:
1. Get the boundary's 2D bounding box in its local plane (sketch placement or face plane).
2. Generate candidate centers covering the bbox plus one pitch of padding, in grid-local coordinates, then rotate and offset.
3. Filter candidates (§6.2).
4. Emit hex vertex lists (with optional corner fillets as arc segments).

The core outputs plain tuples/lists with no FreeCAD imports, so pytest can check cell counts, spacing, and open area.

### 6.2 Boundary handling
1. **Inset the boundary** by `Margin` using `Part.Face.makeOffset2D(-Margin)`. Inner holes grow outward by the same amount, so islands keep their margin too. *(M0 finding, FreeCAD 1.1.3: `makeOffset2D` on a face with holes is wrong; it drops the outer boundary on a negative offset. Instead, offset each outer wire by `-Margin` and each hole by `+Margin` separately, then cut the holes away.)*
2. **Classify each candidate cell** against the inset face:
   - Cheap prefilter: cell bbox vs. face bbox
   - **Fully inside:** all 6 vertices inside (`face.isInside(pt, tol, True)`) *and* the hex wire doesn't intersect the inset boundary edges
   - **Fully outside:** discard
   - **Straddling:** depends on `EdgeMode`
3. **EdgeMode behavior:**
   - `WholeOnly`: keep only fully-inside cells. Best for plasma/laser: no slivers, uniform webs.
   - `Clip`: keep straddling cells intersected with the inset face (`hexFace.common(insetFace)`).
   - `ClipMinArea`: like Clip, but drop pieces with area < `MinCellFraction × fullCellArea`. (A `MinWeb` property was considered and dropped: clipped cells stop at the margin line, so `Margin` already sets the minimum material at the boundary.)
4. Boolean ops run **only on straddling cells**. Interior cells are built directly as faces, which keeps large patterns fast.

### 6.3 Performance targets
- 2,000 cells (e.g. a 300×200 mm panel with 6 mm cells): recompute < 2 s on a typical desktop
- 10,000 cells: < 10 s, with a warning in the task panel above a configurable cell count
- Preview in the task panel may use wires only (no faces) for responsiveness

Tactics: build interior cells with `Part.makePolygon` → `Part.Face`, no Booleans; `Part.Compound` instead of fusing; fuse only when a solid is needed, and then prefer one `cut` of a compound of prisms over many sequential cuts.

### 6.4 Output modes
- **Wires:** compound of closed hex wires. Lightest; good for DXF export.
- **Faces:** compound of planar faces. Usable as a Pocket/Pad profile (verify in M0, see §9).
- **Solid:** faces extruded by `Depth` (or through the target's thickness) as a compound of prisms, ready to Boolean.

### 6.5 Curved surfaces

**Cylinders and cones (M4).** Developable surfaces unroll without distortion:
1. Get the face's parametric surface and its (u, v) range.
2. Map u (angle) to arc length `s = r·u` so cells keep true size. For cones, use the unrolled sector.
3. Run the flat engine on the unrolled rectangle, or on the unrolled trimmed boundary if the face is trimmed.
4. Map each hex back onto the surface: build its edges as 2D curves in parameter space with `Part.Geom2d` and `.toShape(surface)`. That gives edges lying exactly on the surface.
5. Make a face on the surface from those wires, then thicken along the normal by `Depth` (`makeOffsetShape` with fill) to get a cutting/embossing solid that's normal to the surface.
6. Seam handling: if the pattern wraps a full 360°, adjust the pitch so the cell count around the circumference is an integer (shown as a read-only "actual pitch").

**Freeform B-spline faces (M5, research).** Parameter space is distorted, so cells stretch. Options to evaluate:
- (a) Accept UV mapping with a warning; fine for gently curved faces
- (b) Approximate flattening (like Curves WB) and map cells back
- (c) Project flat hexes along a direction onto the face (`Part.Face.project` / `makeParallelProjection`), then thicken along normals. Simple and predictable for "texture on a mostly-flat-ish face"

Likely ship (c) first for freeform, since it's the most predictable.

## 7. FreeCAD integration

### 7.1 Objects
- `HexFill` — `Part::FeaturePython` for general use (Part WB, export)
- `HexFillCut` / `HexFillPad` — PartDesign subtractive/additive variants built on `PartDesign::FeatureSubtractivePython` / `PartDesign::FeatureAdditivePython`, so it sits in the Body tree like a normal Pocket/Pad (verify the API in M0)
- `HexSurface` — surface-pattern feature (Part and PartDesign variants)

Each has a ViewProvider with an icon, double-click to reopen the task panel, and `claimChildren` for the source.

### 7.2 Task panel (Qt via FreeCAD's `PySide` shim)
- Source selector (pre-filled from selection)
- Cell size, wall, margin (unit-aware quantity spin boxes)
- Orientation, angle, X/Y offset
- Edge mode with conditional fields
- Output mode, depth
- Live readouts: cell count, open %, pitch
- Live preview toggle

### 7.3 Commands / toolbar
- Hex Fill Region
- Hex Pattern on Surface
- Export to DXF (convenience wrapper around FreeCAD's importer/exporter for the flat result)

### 7.4 Compatibility
- **Target:** FreeCAD 1.0 and 1.1. Test on both.
- Use `from PySide import QtCore, QtGui` (FreeCAD's shim) so the code runs on both PySide2 and PySide6 builds.
- Python 3.8+ syntax only.
- Save/restore: proxies must serialize cleanly (`dumps`/`loads`, or `onDocumentRestored` to re-attach).
- Graceful failure: if the source is missing or not closed, set an error state with a clear message instead of crashing recompute.

## 8. Repository layout

```
HexFill/
├── package.xml                # Addon Manager metadata (required for catalog)
├── LICENSE                    # LGPL-2.1 full text
├── README.md                  # User-facing docs + screenshots/GIFs
├── CHANGELOG.md
├── CONTRIBUTING.md
├── docs/
│   └── design.md              # this document
├── freecad/
│   └── hexfill/
│       ├── __init__.py
│       ├── init_gui.py        # Workbench registration (namespace-style workbench)
│       ├── core/
│       │   ├── hexgrid.py     # pure-Python grid math (no FreeCAD imports)
│       │   └── units.py
│       ├── features/
│       │   ├── hexfill.py     # Part::FeaturePython
│       │   ├── pd_features.py # PartDesign additive/subtractive
│       │   └── surface.py
│       ├── gui/
│       │   ├── commands.py
│       │   ├── taskpanel.py
│       │   └── viewproviders.py
│       └── resources/
│           └── icons/*.svg
├── tests/
│   ├── test_hexgrid.py        # pytest, no FreeCAD needed
│   └── fc/                    # integration tests run with freecadcmd
│       └── test_features.py
└── examples/
    ├── plasma_panel.FCStd
    ├── vent_cover.FCStd
    └── cylinder_texture.FCStd
```

The layout follows the FreeCAD Addon Academy's namespace-package convention. Confirm against the current Addon Academy guide when scaffolding.

## 9. Milestones

| # | Milestone | Deliverable | Done when |
|---|---|---|---|
| M0 | Spike / API checks | Throwaway script | Confirmed: which output types PartDesign Pocket accepts as a profile; that `PartDesign::FeatureSubtractivePython` works in 1.0/1.1; that `makeOffset2D` handles sketches with holes |
| M1 | Flat fill, WholeOnly | `hexgrid.py` + `HexFill` object, properties only | Fills an arbitrary closed sketch with holes; pytest passing |
| M2 | Edge modes + polish | Clip, ClipMinArea, CornerRadius, task panel, icons | Task panel live preview; plasma example part produces clean DXF |
| M3 | PartDesign features | `HexFillCut` / `HexFillPad` | Works as a native Body feature, survives save/reopen and upstream sketch edits |
| M4 | Cylinder / cone | `HexSurface` (developable) + `HexSurfaceCut` / `HexSurfacePad` | Hex vent around a tube, recess texture on a cylinder, seam pitch correction |
| M5 | Freeform faces | Projection mode | Texture on a gently curved B-spline face |
| M6 | Release | package.xml, README, wiki page, catalog PR | Installable from the Addon Manager |

### M0 findings (FreeCAD 1.1.3, 2026-11-02)
FreeCAD 1.0 was not available to test; re-check these there.
- **Pocket profile:** a PartDesign Pocket accepts a `HexFill` (Part::FeaturePython, Faces output) directly as its Profile, even when the HexFill sits outside the Body. A `PartDesign::SubShapeBinder` of the HexFill also works. (The GUI may still ask about out-of-scope links.)
- **Body membership:** a `Part::FeaturePython` cannot be added to a Body ("object is not allowed").
- **`PartDesign::FeatureSubtractivePython`** works: added to a Body it gets `BaseFeature` set automatically, becomes the Tip, and exposes `AddSubShape` and `Refine`. M3 can build on it.
- **M3 conventions:** HexFillCut `Depth = 0` cuts through all on *both* sides of the sketch plane (the usual intent for vents; differs from Pocket's one-sided Through All). Face sources use the face's outward normal. A result with more than one solid is an error.
- **M4 findings:** Booleans on cylindrical faces are inherently slow in OCC (300 plain radial drill holes in a tube: 7.5 s vs 0.4 s in a plate; already multi-threaded). Mitigations used: canonical coaxial offset surfaces instead of `Part.OffsetSurface` (which also produced invalid faces on rotated cylinders), one template tool per whole cylinder cell placed by rotate/slide, exact rational pcurves for rounded corners on cylinders (halves Boolean time), and live preview off by default for curved faces. Cone full wraps cannot be made periodic (the unrolled sector is not translation-periodic), so the seam is a boundary. Cuts start above any material proud of the face (bounding-box clearance) so earlier embossing is cut cleanly.
- **`makeOffset2D` with holes** is wrong (see §6.2); HexFill offsets each wire separately.
- **Task panel transactions:** use `App.setActiveTransaction(name, True)` / `App.closeActiveTransaction(abort)`, and close the transaction *before* `resetEdit()`, which otherwise commits it.
- **DXF export:** FreeCAD's exporter writes all-line wires as LWPOLYLINE but wires with arcs (rounded cells) as loose LINE/ARC entities. Contours are closed and free of duplicates (checked in tests).

## 10. Testing

- **Unit (pytest, no FreeCAD):** pitch/row spacing, cell counts for known rectangles, rotation, open-area math, ClipMinArea thresholds on synthetic polygons.
- **Integration (`freecadcmd`):** build features from example sketches, recompute, check `CellCount`, check the solid is valid (`shape.isValid()`), save/reopen round-trip.
- **Manual fabrication checks:**
  - Print a test coupon at a few cell/wall combos (e.g. 4/0.8, 6/1.2, 10/2.0)
  - Laser/plasma: export DXF, confirm closed contours, no duplicate edges, and webs ≥ Wall after kerf
- **CI:** GitHub Actions runs pytest on every push. FreeCAD integration tests run in a container with FreeCAD AppImage/conda (optional, add once stable).

## 11. License

**Recommended: LGPL-2.1-or-later.**

Rationale:
- It matches FreeCAD itself and most of the addon ecosystem, which makes contributions and code reuse with other addons painless.
- People can use HexFill freely, including on commercial parts, and the parts they design are theirs. The license covers the code, not the models made with it.
- Anyone who distributes a modified HexFill has to share those changes, so improvements stay open. MIT wouldn't require that.
- The prior-art Honeycomb macro is also LGPL-2.1, so borrowing ideas from it, or code with attribution, stays compatible.

Alternatives:
- **MIT:** simplest and most permissive. Pick it if you don't care whether forks stay open.
- **GPL-3.0-or-later:** stronger copyleft. Fine, but it can complicate mixing with LGPL code.

Implementation:
- Full license text in `LICENSE`
- SPDX header in every source file: `# SPDX-License-Identifier: LGPL-2.1-or-later`
- `package.xml`: `<license file="LICENSE">LGPL-2.1-or-later</license>`
- Icons and docs can stay under the same license, or use CC-BY-SA-4.0 if preferred (list both in package.xml if so)

## 12. Open questions

1. Final project name and repo URL.
2. Does Pocket accept a `Part::FeaturePython` face compound directly as a profile, or does it need a ShapeBinder? (M0)
3. Should `WholeOnly` support "fill to edge with partial cells, but merge tiny edge pieces into the margin" as a fourth mode?
4. Kerf compensation for plasma: add a `Kerf` property that offsets cells, or leave that to CAM? (Leaning: leave to CAM, but document it.)
5. Should variable cell size (gradient density) be a future feature? It would be cool for lightweighting, but it's out of scope for v1.

## 13. Notes for development with Claude Code

- Keep this file at `docs/design.md` and reference it from a `CLAUDE.md` at the repo root.
- Suggested `CLAUDE.md` contents: target FreeCAD versions, "core/ must not import FreeCAD", run `pytest tests/` before committing, SPDX header required, PySide via FreeCAD shim only.
- Work milestone by milestone; each milestone ends with tests passing and an example `.FCStd` updated.
- Claude Code can't drive the FreeCAD GUI, so GUI checks (task panel, preview, icons) are manual. Headless `freecadcmd` tests cover the geometry.
