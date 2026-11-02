# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel for creating and editing HexFill objects.

Edits are written straight to the object's properties inside the application's
active transaction (opened by the create command or by setEdit): OK commits
it, Cancel aborts it, which also removes a newly created object.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from .. import icon
from ..core import hexgrid
from ..features.hexfill import ANCHORS, EDGE_MODES, OUTPUTS

PARAMS = App.ParamGet("User parameter:BaseApp/Preferences/Mod/HexFill")

SIZING_MODES = ("Flat-to-flat + wall", "Corner-to-corner + wall", "Pitch + open area")


def _quantity_box(unit, minimum=None):
    box = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    box.setProperty("unit", unit)
    if minimum is not None:
        box.setProperty("minimum", minimum)
    return box


def _combo(items):
    combo = QtGui.QComboBox()
    combo.addItems(list(items))
    return combo


class HexFillTaskPanel:
    def __init__(self, obj, creating=False):
        self.obj = obj
        self.creating = creating
        self.doc = obj.Document
        self._updating = False
        self.form = self._build_form()
        self._load()
        self._update_visibility()
        self._update_readouts()

    # --- Layout -----------------------------------------------------------

    def _build_form(self):
        form = QtGui.QWidget()
        form.setWindowTitle("Hex Fill")
        form.setWindowIcon(QtGui.QIcon(icon("HexFill.svg")))
        layout = QtGui.QFormLayout(form)

        source = self.obj.Source
        subs = ", ".join(s for s in source[1] if s) if source else ""
        text = source[0].Label + (" : " + subs if subs else "") if source else "(none)"
        layout.addRow("Source", QtGui.QLabel(text))

        self.sizing = _combo(SIZING_MODES)
        self.size_box = _quantity_box("mm", 0.0)
        self.size_label = QtGui.QLabel()
        self.wall_box = _quantity_box("mm", 0.0)
        self.open_box = QtGui.QDoubleSpinBox()
        self.open_box.setRange(1.0, 99.0)
        self.open_box.setSuffix(" %")
        self.open_box.setDecimals(1)
        self.second_label = QtGui.QLabel()
        second = QtGui.QWidget()
        second_layout = QtGui.QHBoxLayout(second)
        second_layout.setContentsMargins(0, 0, 0, 0)
        second_layout.addWidget(self.wall_box)
        second_layout.addWidget(self.open_box)
        layout.addRow("Sizing", self.sizing)
        layout.addRow(self.size_label, self.size_box)
        layout.addRow(self.second_label, second)

        self.margin_box = _quantity_box("mm", 0.0)
        self.radius_box = _quantity_box("mm", 0.0)
        self.orientation = _combo(hexgrid.ORIENTATIONS)
        self.angle_box = _quantity_box("deg")
        self.offset_x = _quantity_box("mm")
        self.offset_y = _quantity_box("mm")
        self.anchor = _combo(ANCHORS)
        self.edge_mode = _combo(EDGE_MODES)
        self.fraction_box = QtGui.QDoubleSpinBox()
        self.fraction_box.setRange(0.0, 1.0)
        self.fraction_box.setSingleStep(0.05)
        self.fraction_label = QtGui.QLabel("Min cell fraction")
        self.output = _combo(OUTPUTS)
        self.depth_box = _quantity_box("mm", 0.0)
        self.depth_label = QtGui.QLabel("Depth")
        self.reversed = QtGui.QCheckBox("Reversed")

        for label, widget in (
            ("Margin", self.margin_box),
            ("Corner radius", self.radius_box),
            ("Orientation", self.orientation),
            ("Angle", self.angle_box),
            ("Offset X", self.offset_x),
            ("Offset Y", self.offset_y),
            ("Anchor", self.anchor),
            ("Edge mode", self.edge_mode),
        ):
            layout.addRow(label, widget)
        layout.addRow(self.fraction_label, self.fraction_box)
        layout.addRow("Output", self.output)
        layout.addRow(self.depth_label, self.depth_box)
        layout.addRow("", self.reversed)

        self.readout = QtGui.QLabel()
        self.warning = QtGui.QLabel()
        self.warning.setStyleSheet("color: #c06000;")
        self.warning.setWordWrap(True)
        self.preview = QtGui.QCheckBox("Live preview")
        self.preview.setChecked(PARAMS.GetBool("LivePreview", True))
        self.refresh = QtGui.QPushButton("Refresh")
        layout.addRow(self.readout)
        layout.addRow(self.warning)
        layout.addRow(self.preview, self.refresh)

        for box in (self.size_box, self.wall_box, self.margin_box, self.radius_box,
                    self.angle_box, self.offset_x, self.offset_y, self.depth_box):
            QtCore.QObject.connect(box, QtCore.SIGNAL("valueChanged(double)"), self._changed)
        self.open_box.valueChanged.connect(self._changed)
        self.fraction_box.valueChanged.connect(self._changed)
        for combo in (self.orientation, self.anchor, self.edge_mode, self.output):
            combo.currentIndexChanged.connect(self._changed)
        self.reversed.toggled.connect(self._changed)
        self.sizing.currentIndexChanged.connect(self._sizing_changed)
        self.preview.toggled.connect(self._preview_toggled)
        self.refresh.clicked.connect(self._recompute)
        return form

    # --- Object <-> widgets -------------------------------------------------

    def _load(self):
        obj = self.obj
        self._updating = True
        try:
            self._load_sizing()
            self.margin_box.setProperty("rawValue", obj.Margin.Value)
            self.radius_box.setProperty("rawValue", obj.CornerRadius.Value)
            self.orientation.setCurrentIndex(hexgrid.ORIENTATIONS.index(obj.Orientation))
            self.angle_box.setProperty("rawValue", obj.Angle.Value)
            self.offset_x.setProperty("rawValue", obj.OffsetX.Value)
            self.offset_y.setProperty("rawValue", obj.OffsetY.Value)
            self.anchor.setCurrentIndex(ANCHORS.index(obj.Anchor))
            self.edge_mode.setCurrentIndex(EDGE_MODES.index(obj.EdgeMode))
            self.fraction_box.setValue(obj.MinCellFraction)
            self.output.setCurrentIndex(OUTPUTS.index(obj.Output))
            self.depth_box.setProperty("rawValue", obj.Depth.Value)
            self.reversed.setChecked(obj.Reversed)
        finally:
            self._updating = False

    def _load_sizing(self):
        size, wall = self.obj.CellSize.Value, self.obj.Wall.Value
        mode = self.sizing.currentIndex()
        if mode == 0:
            self.size_label.setText("Cell size (flat-to-flat)")
            self.size_box.setProperty("rawValue", size)
        elif mode == 1:
            self.size_label.setText("Cell size (corner-to-corner)")
            self.size_box.setProperty("rawValue", 2.0 * hexgrid.circumradius(size))
        else:
            self.size_label.setText("Pitch")
            self.size_box.setProperty("rawValue", hexgrid.pitch(size, wall))
            self.open_box.setValue(100.0 * hexgrid.open_area_ratio(size, wall))
        self.second_label.setText("Open area" if mode == 2 else "Wall")
        self.wall_box.setVisible(mode != 2)
        self.open_box.setVisible(mode == 2)
        self.wall_box.setProperty("rawValue", wall)

    def _cell_size_and_wall(self):
        first = self.size_box.property("rawValue")
        mode = self.sizing.currentIndex()
        if mode == 0:
            return first, self.wall_box.property("rawValue")
        if mode == 1:
            return hexgrid.from_corner_to_corner(first, self.wall_box.property("rawValue"))
        return hexgrid.from_pitch_and_open_area(first, self.open_box.value() / 100.0)

    def _store(self):
        obj = self.obj
        obj.CellSize, obj.Wall = self._cell_size_and_wall()
        obj.Margin = self.margin_box.property("rawValue")
        obj.CornerRadius = self.radius_box.property("rawValue")
        obj.Orientation = self.orientation.currentText()
        obj.Angle = self.angle_box.property("rawValue")
        obj.OffsetX = self.offset_x.property("rawValue")
        obj.OffsetY = self.offset_y.property("rawValue")
        obj.Anchor = self.anchor.currentText()
        obj.EdgeMode = self.edge_mode.currentText()
        obj.MinCellFraction = self.fraction_box.value()
        obj.Output = self.output.currentText()
        obj.Depth = self.depth_box.property("rawValue")
        obj.Reversed = self.reversed.isChecked()

    # --- Reactions ----------------------------------------------------------

    def _changed(self, *_):
        if self._updating:
            return
        try:
            self._store()
        except ValueError as e:
            self.warning.setText(str(e))
            return
        self._update_visibility()
        if self.preview.isChecked():
            self._recompute()

    def _sizing_changed(self, *_):
        self._updating = True
        try:
            self._load_sizing()
        finally:
            self._updating = False

    def _preview_toggled(self, checked):
        PARAMS.SetBool("LivePreview", checked)
        if checked:
            self._recompute()

    def _update_visibility(self):
        clip_min = self.edge_mode.currentText() == "ClipMinArea"
        self.fraction_label.setVisible(clip_min)
        self.fraction_box.setVisible(clip_min)
        solid = self.output.currentText() == "Solid"
        self.depth_label.setVisible(solid)
        self.depth_box.setVisible(solid)
        self.reversed.setVisible(solid)

    def _recompute(self):
        self.doc.recompute()
        self._update_readouts()

    def _update_readouts(self):
        obj = self.obj
        self.readout.setText("Cells: {}    Open area: {:.1f} %    Pitch: {:.3f} mm".format(
            obj.CellCount, obj.OpenAreaPercent, obj.Pitch.Value))
        if not obj.isValid():
            self.warning.setText(obj.getStatusString())
        elif obj.CellCount > PARAMS.GetInt("WarnCellCount", 10000):
            self.warning.setText("Large pattern: recompute may be slow. "
                                 "Consider turning off live preview.")
        else:
            self.warning.setText("")

    # --- Task dialog API ----------------------------------------------------

    # The transaction must be closed before leaving edit mode: resetEdit
    # commits the transaction that was active when editing started.

    def accept(self):
        self.doc.recompute()
        source = self.obj.Source
        # Hide a whole-object source (e.g. a sketch); visibility is not undoable,
        # so this happens only on OK.
        if self.creating and source and not any(source[1]):
            source[0].Visibility = False
        App.closeActiveTransaction()
        self._close()
        return True

    def reject(self):
        App.closeActiveTransaction(True)
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        gui_doc = Gui.getDocument(self.doc.Name)
        if gui_doc.getInEdit():
            gui_doc.resetEdit()
