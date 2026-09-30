"""Measurement, quality-control, and detection panels."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.theme import FAIL_HEX, PASS_HEX, WARN_HEX
from calibration.aruco_calibration import dictionary_names
from calibration.profile_manager import ProfileManager
from measurement.units import area_suffix, format_angle, format_area, format_length, length_from_unit, length_to_unit, unit_suffix


def _spin(minimum: float, maximum: float, step: float, decimals: int = 2) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    return box


def _scroll(inner: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(inner)
    area.setFrameShape(QScrollArea.NoFrame)
    return area


class MeasurementPanel(QWidget):
    edited = Signal()
    object_selected = Signal(int)
    clear_points = Signal()
    save_profile = Signal(str)
    load_profile = Signal(str)
    delete_profile = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mute = False
        self._unit = "mm"
        self.profiles = ProfileManager()

        self.state_label = QLabel("REFERENCE NOT FOUND")
        self.state_label.setObjectName("statusBad")
        self.detail_label = QLabel("—")
        self.ppm_label = QLabel("—")
        self.perspective_label = QLabel("")
        self.perspective_label.setObjectName("statusWarn")
        self.perspective_label.setVisible(False)

        self.ref_width = _spin(0.1, 2000, 0.5)
        self.marker_size = _spin(1, 500, 0.5)
        self.dictionary_combo = QComboBox()
        for name in dictionary_names():
            self.dictionary_combo.addItem(name)
        self.manual_distance = _spin(0.1, 5000, 1)
        self.clear_points_button = QPushButton("Clear Points")
        self.manual_hint = QLabel("Click two points on the image, then enter the real distance.")
        self.manual_hint.setWordWrap(True)
        self.profile_combo = QComboBox()
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("Office Camera 01")
        self.save_profile_button = QPushButton("Save Profile")
        self.load_profile_button = QPushButton("Load as Fixed")
        self.delete_profile_button = QPushButton("Delete")
        self.lens_check = QCheckBox("Lens Distortion Correction")

        reference_page = QWidget()
        reference_form = QFormLayout(reference_page)
        reference_form.addRow("Reference width", self.ref_width)
        aruco_page = QWidget()
        aruco_form = QFormLayout(aruco_page)
        aruco_form.addRow("Marker size", self.marker_size)
        aruco_form.addRow("Dictionary", self.dictionary_combo)
        manual_page = QWidget()
        manual_layout = QVBoxLayout(manual_page)
        manual_form = QFormLayout()
        manual_form.addRow("Real distance", self.manual_distance)
        manual_layout.addLayout(manual_form)
        manual_layout.addWidget(self.manual_hint)
        manual_layout.addWidget(self.clear_points_button)
        fixed_page = QWidget()
        fixed_layout = QVBoxLayout(fixed_page)
        fixed_layout.addWidget(self.profile_combo)
        fixed_layout.addWidget(self.profile_name)
        profile_buttons = QHBoxLayout()
        profile_buttons.addWidget(self.save_profile_button)
        profile_buttons.addWidget(self.load_profile_button)
        profile_buttons.addWidget(self.delete_profile_button)
        fixed_layout.addLayout(profile_buttons)
        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(reference_page)
        self.mode_stack.addWidget(aruco_page)
        self.mode_stack.addWidget(manual_page)
        self.mode_stack.addWidget(fixed_page)

        self.object_title = QLabel("OBJECT")
        self.object_title.setObjectName("value")
        self.width_label = QLabel("—")
        self.height_label = QLabel("—")
        self.area_label = QLabel("—")
        self.perimeter_label = QLabel("—")
        self.angle_label = QLabel("—")
        self.center_label = QLabel("—")
        self.plane_label = QLabel("—")
        self.scale_label = QLabel("—")
        self.result_label = QLabel("—")
        self.width_flag = QLabel("")
        self.height_flag = QLabel("")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "WIDTH", "HEIGHT", "ANGLE", "RESULT"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        status_box = QGroupBox("Calibration")
        status_form = QFormLayout(status_box)
        status_form.addRow("Status", self.state_label)
        status_form.addRow("Source", self.detail_label)
        status_form.addRow("Scale", self.ppm_label)
        status_form.addRow("", self.perspective_label)
        status_form.addRow(self.mode_stack)
        status_form.addRow(self.lens_check)

        selected_box = QGroupBox("Selected Object")
        selected_form = QFormLayout(selected_box)
        selected_form.addRow(self.object_title)
        selected_form.addRow("Width", self.width_label)
        selected_form.addRow("", self.width_flag)
        selected_form.addRow("Height", self.height_label)
        selected_form.addRow("", self.height_flag)
        selected_form.addRow("Area", self.area_label)
        selected_form.addRow("Perimeter", self.perimeter_label)
        selected_form.addRow("Angle", self.angle_label)
        selected_form.addRow("Center", self.center_label)
        selected_form.addRow("Plane X/Y", self.plane_label)
        selected_form.addRow("Calibration", self.scale_label)
        selected_form.addRow("Status", self.result_label)

        table_box = QGroupBox("Measured Objects")
        table_layout = QVBoxLayout(table_box)
        table_layout.addWidget(self.table)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(status_box)
        layout.addWidget(selected_box)
        layout.addWidget(table_box)
        layout.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(inner))

        for widget in (
            self.ref_width,
            self.marker_size,
            self.dictionary_combo,
            self.manual_distance,
            self.lens_check,
        ):
            if isinstance(widget, QCheckBox):
                widget.toggled.connect(self._emit)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._emit)
            else:
                widget.valueChanged.connect(self._emit)
        self.clear_points_button.clicked.connect(self.clear_points.emit)
        self.save_profile_button.clicked.connect(self._save_profile)
        self.load_profile_button.clicked.connect(self._load_profile)
        self.delete_profile_button.clicked.connect(self._delete_profile)
        self.table.itemSelectionChanged.connect(self._selection)

    def set_settings(self, settings) -> None:
        self._mute = True
        self._unit = settings.units
        suffix = " " + unit_suffix(settings.units)
        for box in (self.ref_width, self.marker_size, self.manual_distance):
            box.setSuffix(suffix)
        self.ref_width.setValue(length_to_unit(settings.reference_width_mm, settings.units) or 0)
        self.marker_size.setValue(length_to_unit(settings.marker_size_mm, settings.units) or 0)
        self.manual_distance.setValue(length_to_unit(settings.manual_distance_mm, settings.units) or 0)
        index = self.dictionary_combo.findText(settings.aruco_dictionary)
        if index >= 0:
            self.dictionary_combo.setCurrentIndex(index)
        self.lens_check.setChecked(bool(settings.lens_correction))
        mode_index = {"reference": 0, "aruco": 1, "manual": 2, "fixed": 3}.get(settings.calibration_mode, 0)
        self.mode_stack.setCurrentIndex(mode_index)
        self._reload_profiles(settings.fixed_profile)
        if settings.fixed_profile and not self.profile_name.text():
            self.profile_name.setText(settings.fixed_profile)
        self._mute = False

    def changes(self) -> dict:
        unit = self._unit
        return {
            "reference_width_mm": length_from_unit(self.ref_width.value(), unit),
            "marker_size_mm": length_from_unit(self.marker_size.value(), unit),
            "aruco_dictionary": self.dictionary_combo.currentText(),
            "manual_distance_mm": length_from_unit(self.manual_distance.value(), unit),
            "lens_correction": self.lens_check.isChecked(),
        }

    def show_result(self, result, settings) -> None:
        calibration = result.calibration
        self.state_label.setText(calibration.message)
        self.state_label.setObjectName("statusGood" if calibration.valid else "statusBad")
        self._repolish(self.state_label)
        detail = calibration.detail or "—"
        if calibration.aruco_id is not None:
            detail = f"ARUCO #{calibration.aruco_id}"
        if calibration.marker_size_mm:
            detail += "   " + format_length(calibration.marker_size_mm, "mm")
        self.detail_label.setText(detail)
        if calibration.pixels_per_mm:
            self.ppm_label.setText(f"{calibration.pixels_per_mm:.2f} px/mm")
        else:
            self.ppm_label.setText("—")
        self.perspective_label.setVisible(calibration.perspective_warning)
        self.perspective_label.setText(calibration.perspective_message or "PERSPECTIVE WARNING")
        self._fill_table(result.objects, settings)
        self._fill_selected(result, settings)

    def _fill_selected(self, result, settings) -> None:
        selected = None
        for obj in result.objects:
            if obj.id == settings.selected_object_id:
                selected = obj
                break
        if selected is None and result.objects:
            selected = result.objects[0]
        unit = settings.units
        if selected is None:
            self.object_title.setText("No object")
            for label in (
                self.width_label,
                self.height_label,
                self.area_label,
                self.perimeter_label,
                self.angle_label,
                self.center_label,
                self.plane_label,
                self.scale_label,
                self.result_label,
            ):
                label.setText("—")
            self.width_flag.setText("")
            self.height_flag.setText("")
            return
        self.object_title.setText(f"OBJECT #{selected.id}")
        self.width_label.setText(format_length(selected.width_mm, unit))
        self.height_label.setText(format_length(selected.height_mm, unit))
        self.area_label.setText(format_area(selected.area_mm2, unit))
        if selected.perimeter_mm is None:
            self.perimeter_label.setText("—")
        else:
            self.perimeter_label.setText(format_length(selected.perimeter_mm, unit))
        self.angle_label.setText(format_angle(selected.angle_deg))
        self.center_label.setText(f"X {selected.center_px[0]:.0f}    Y {selected.center_px[1]:.0f}")
        if selected.center_mm is None:
            self.plane_label.setText("—")
        else:
            self.plane_label.setText(
                f"X {length_to_unit(selected.center_mm[0], unit):.2f}    "
                f"Y {length_to_unit(selected.center_mm[1], unit):.2f} {unit_suffix(unit)}"
            )
        if result.calibration.pixels_per_mm:
            self.scale_label.setText(f"{result.calibration.pixels_per_mm:.2f} px/mm")
        else:
            self.scale_label.setText("—")
        self.result_label.setText(selected.result)
        self._paint_result(self.result_label, selected.result)
        self._paint_flag(self.width_flag, selected.width_pass)
        self._paint_flag(self.height_flag, selected.height_pass)

    def _fill_table(self, objects, settings) -> None:
        unit = settings.units
        header = self.table.horizontalHeaderItem(1)
        if header is not None:
            header.setText(f"WIDTH ({unit_suffix(unit)})")
            self.table.horizontalHeaderItem(2).setText(f"HEIGHT ({unit_suffix(unit)})")
        selected_id = settings.selected_object_id
        self.table.blockSignals(True)
        self.table.setRowCount(len(objects))
        select_row = -1
        for row, obj in enumerate(objects):
            width = "—" if obj.width_mm is None else f"{length_to_unit(obj.width_mm, unit):.2f}"
            height = "—" if obj.height_mm is None else f"{length_to_unit(obj.height_mm, unit):.2f}"
            angle = "—" if obj.angle_deg is None else f"{obj.angle_deg:.1f}°"
            values = [str(obj.id), width, height, angle, obj.result]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, obj.id)
                item.setTextAlignment(Qt.AlignCenter)
                if column == 4 and obj.result == "PASS":
                    item.setForeground(QColor(PASS_HEX))
                elif column == 4 and obj.result == "FAIL":
                    item.setForeground(QColor(FAIL_HEX))
                elif column == 4 and obj.result == "PARTIAL":
                    item.setForeground(QColor(WARN_HEX))
                self.table.setItem(row, column, item)
            if obj.id == selected_id:
                select_row = row
        if select_row >= 0:
            self.table.selectRow(select_row)
        self.table.blockSignals(False)

    def _reload_profiles(self, selected: str) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in self.profiles.list_profiles():
            self.profile_combo.addItem(name)
        if selected:
            index = self.profile_combo.findText(selected)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)

    def _emit(self, *_args) -> None:
        if not self._mute:
            self.edited.emit()

    def _selection(self) -> None:
        if self._mute:
            return
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.object_selected.emit(int(item.data(Qt.UserRole)))

    def _save_profile(self) -> None:
        name = self.profile_name.text().strip() or self.profile_combo.currentText().strip() or "Office Camera 01"
        self.save_profile.emit(name)

    def _load_profile(self) -> None:
        name = self.profile_combo.currentText().strip()
        if name:
            self.load_profile.emit(name)

    def _delete_profile(self) -> None:
        name = self.profile_combo.currentText().strip()
        if name:
            self.delete_profile.emit(name)

    def _paint_flag(self, label: QLabel, passed: bool | None) -> None:
        if passed is None:
            label.setText("")
            return
        label.setText("PASS" if passed else "FAIL")
        self._paint_result(label, "PASS" if passed else "FAIL")

    def _paint_result(self, label: QLabel, result: str) -> None:
        if result == "PASS":
            label.setObjectName("statusGood")
        elif result in ("FAIL", "PAUSED", "REFERENCE NOT FOUND"):
            label.setObjectName("statusBad")
        elif result == "PARTIAL":
            label.setObjectName("statusWarn")
        else:
            label.setObjectName("")
        self._repolish(label)

    @staticmethod
    def _repolish(widget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class QualityPanel(QWidget):
    edited = Signal()
    save_preset = Signal()
    delete_preset = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mute = False
        self._unit = "mm"
        self._parts = {}
        self.enabled = QCheckBox("Enable quality control")
        self.part_combo = QComboBox()
        self.part_name = QLineEdit()
        self.part_name.setPlaceholderText("Bracket_A")
        self.save_button = QPushButton("Save Preset")
        self.delete_button = QPushButton("Delete Preset")
        self.nominal_width = _spin(0.01, 5000, 0.1)
        self.nominal_height = _spin(0.01, 5000, 0.1)
        self.symmetric = QCheckBox("Symmetric tolerance")
        self.symmetric.setChecked(True)
        self.tolerance = _spin(0.0, 100, 0.05)
        self.width_upper = _spin(0.0, 100, 0.05)
        self.width_lower = _spin(0.0, 100, 0.05)
        self.height_upper = _spin(0.0, 100, 0.05)
        self.height_lower = _spin(0.0, 100, 0.05)

        form = QFormLayout()
        form.addRow(self.enabled)
        form.addRow("Preset", self.part_combo)
        form.addRow("Part name", self.part_name)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)
        form.addRow(buttons)
        form.addRow("Nominal width", self.nominal_width)
        form.addRow("Nominal height", self.nominal_height)
        form.addRow(self.symmetric)
        form.addRow("Tolerance ±", self.tolerance)
        form.addRow("Width upper +", self.width_upper)
        form.addRow("Width lower −", self.width_lower)
        form.addRow("Height upper +", self.height_upper)
        form.addRow("Height lower −", self.height_lower)
        box = QGroupBox("Quality Control")
        box.setLayout(form)
        note = QLabel(
            "PASS when both dimensions sit inside the nominal band. "
            "Upper and lower limits can differ."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(box)
        layout.addWidget(note)
        layout.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(inner))

        self.enabled.toggled.connect(self._emit)
        self.part_combo.currentIndexChanged.connect(self._part_chosen)
        self.part_name.textChanged.connect(self._emit)
        self.symmetric.toggled.connect(self._symmetry_toggled)
        for box_widget in (
            self.nominal_width,
            self.nominal_height,
            self.tolerance,
            self.width_upper,
            self.width_lower,
            self.height_upper,
            self.height_lower,
        ):
            box_widget.valueChanged.connect(self._emit)
        self.save_button.clicked.connect(self.save_preset.emit)
        self.delete_button.clicked.connect(self.delete_preset.emit)
        self._symmetry_toggled(True)

    def set_parts(self, parts, selected: str) -> None:
        self._mute = True
        self._parts = {part.name: part for part in parts}
        current = selected
        self.part_combo.blockSignals(True)
        self.part_combo.clear()
        self.part_combo.addItem("—", "")
        for part in parts:
            self.part_combo.addItem(part.name, part.name)
        index = self.part_combo.findData(current)
        self.part_combo.setCurrentIndex(index if index >= 0 else 0)
        self.part_combo.blockSignals(False)
        self._mute = False

    def set_settings(self, settings) -> None:
        self._mute = True
        self._unit = settings.units
        suffix = " " + unit_suffix(settings.units)
        for box in (
            self.nominal_width,
            self.nominal_height,
            self.tolerance,
            self.width_upper,
            self.width_lower,
            self.height_upper,
            self.height_lower,
        ):
            box.setSuffix(suffix)
        self.enabled.setChecked(bool(settings.qc_enabled))
        self.part_name.setText(settings.part_name)
        self.nominal_width.setValue(length_to_unit(settings.nominal_width_mm, settings.units) or 0)
        self.nominal_height.setValue(length_to_unit(settings.nominal_height_mm, settings.units) or 0)
        self.symmetric.setChecked(bool(settings.tolerance_symmetric))
        self.tolerance.setValue(length_to_unit(settings.width_upper_mm, settings.units) or 0)
        self.width_upper.setValue(length_to_unit(settings.width_upper_mm, settings.units) or 0)
        self.width_lower.setValue(length_to_unit(settings.width_lower_mm, settings.units) or 0)
        self.height_upper.setValue(length_to_unit(settings.height_upper_mm, settings.units) or 0)
        self.height_lower.setValue(length_to_unit(settings.height_lower_mm, settings.units) or 0)
        self._apply_symmetry()
        self._mute = False

    def changes(self) -> dict:
        unit = self._unit
        if self.symmetric.isChecked():
            band = length_from_unit(self.tolerance.value(), unit)
            width_upper = width_lower = height_upper = height_lower = band
        else:
            width_upper = length_from_unit(self.width_upper.value(), unit)
            width_lower = length_from_unit(self.width_lower.value(), unit)
            height_upper = length_from_unit(self.height_upper.value(), unit)
            height_lower = length_from_unit(self.height_lower.value(), unit)
        return {
            "qc_enabled": self.enabled.isChecked(),
            "part_name": self.part_name.text().strip(),
            "nominal_width_mm": length_from_unit(self.nominal_width.value(), unit),
            "nominal_height_mm": length_from_unit(self.nominal_height.value(), unit),
            "width_upper_mm": width_upper,
            "width_lower_mm": width_lower,
            "height_upper_mm": height_upper,
            "height_lower_mm": height_lower,
            "tolerance_symmetric": self.symmetric.isChecked(),
        }

    def _part_chosen(self) -> None:
        if self._mute:
            return
        name = self.part_combo.currentData() or ""
        part = self._parts.get(name)
        self._mute = True
        self.part_name.setText(name)
        if part is not None:
            self.enabled.setChecked(True)
            self.nominal_width.setValue(length_to_unit(part.nominal_width_mm, self._unit) or 0)
            self.nominal_height.setValue(length_to_unit(part.nominal_height_mm, self._unit) or 0)
            self.width_upper.setValue(length_to_unit(part.width_upper_mm, self._unit) or 0)
            self.width_lower.setValue(length_to_unit(part.width_lower_mm, self._unit) or 0)
            self.height_upper.setValue(length_to_unit(part.height_upper_mm, self._unit) or 0)
            self.height_lower.setValue(length_to_unit(part.height_lower_mm, self._unit) or 0)
            same = (
                part.width_upper_mm == part.width_lower_mm == part.height_upper_mm == part.height_lower_mm
            )
            self.symmetric.setChecked(same)
            if same:
                self.tolerance.setValue(length_to_unit(part.width_upper_mm, self._unit) or 0)
            self._apply_symmetry()
        self._mute = False
        self.edited.emit()

    def _symmetry_toggled(self, _checked: bool) -> None:
        self._apply_symmetry()
        self._emit()

    def _apply_symmetry(self) -> None:
        symmetric = self.symmetric.isChecked()
        self.tolerance.setVisible(symmetric)
        for widget in (self.width_upper, self.width_lower, self.height_upper, self.height_lower):
            widget.setVisible(not symmetric)

    def _emit(self, *_args) -> None:
        if not self._mute:
            self.edited.emit()


class DetectionPanel(QWidget):
    edited = Signal()
    redraw_roi = Signal()
    advanced = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mute = False
        self._unit = "mm"
        self.method = QComboBox()
        self.method.addItems(["AUTO", "CANNY", "THRESHOLD", "ADAPTIVE"])
        self.smoothing = QComboBox()
        self.smoothing.addItems(["OFF", "LOW", "MEDIUM", "HIGH"])
        self.min_area = QSpinBox()
        self.min_area.setRange(10, 2_000_000)
        self.min_area.setSingleStep(50)
        self.ignore_border = QCheckBox("Ignore border objects")
        self.roi_enabled = QCheckBox("Measurement ROI")
        self.redraw_button = QPushButton("Draw ROI")
        self.stability_threshold = _spin(0.01, 20, 0.05)
        self.stability_samples = QSpinBox()
        self.stability_samples.setRange(3, 30)
        self.auto_capture = QCheckBox("Auto capture when stable")
        self.auto_seconds = _spin(0.2, 10, 0.1, decimals=1)
        self.track_timeout = _spin(0.2, 10, 0.1, decimals=1)
        self.advanced_button = QPushButton("Advanced Settings")

        form = QFormLayout()
        form.addRow("Detection", self.method)
        form.addRow("Smoothing", self.smoothing)
        form.addRow("Minimum area px", self.min_area)
        form.addRow(self.ignore_border)
        form.addRow(self.roi_enabled)
        form.addRow(self.redraw_button)
        form.addRow("Stability band", self.stability_threshold)
        form.addRow("Stability samples", self.stability_samples)
        form.addRow(self.auto_capture)
        form.addRow("Stable for, s", self.auto_seconds)
        form.addRow("Track timeout, s", self.track_timeout)
        form.addRow(self.advanced_button)
        box = QGroupBox("Detection")
        box.setLayout(form)
        note = QLabel(
            "AUTO keeps the classic Canny preset when the contour count is stable, "
            "and tries thresholding when the scene is empty or flooded."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(box)
        layout.addWidget(note)
        layout.addWidget(QLabel(f"Area is reported in {area_suffix('mm')} after calibration."))
        layout.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(inner))

        self.method.currentIndexChanged.connect(self._emit)
        self.smoothing.currentIndexChanged.connect(self._emit)
        self.min_area.valueChanged.connect(self._emit)
        self.ignore_border.toggled.connect(self._emit)
        self.roi_enabled.toggled.connect(self._emit)
        self.stability_threshold.valueChanged.connect(self._emit)
        self.stability_samples.valueChanged.connect(self._emit)
        self.auto_capture.toggled.connect(self._emit)
        self.auto_seconds.valueChanged.connect(self._emit)
        self.track_timeout.valueChanged.connect(self._emit)
        self.redraw_button.clicked.connect(self.redraw_roi.emit)
        self.advanced_button.clicked.connect(self.advanced.emit)

    def set_settings(self, settings) -> None:
        self._mute = True
        self._unit = settings.units
        self.stability_threshold.setSuffix(" " + unit_suffix(settings.units))
        self._set_text(self.method, settings.detection_method)
        self._set_text(self.smoothing, settings.smoothing)
        self.min_area.setValue(int(settings.min_area))
        self.ignore_border.setChecked(bool(settings.ignore_border))
        self.roi_enabled.setChecked(bool(settings.roi_enabled))
        self.stability_threshold.setValue(length_to_unit(settings.stability_threshold_mm, settings.units) or 0.1)
        self.stability_samples.setValue(int(settings.stability_samples))
        self.auto_capture.setChecked(bool(settings.auto_capture))
        self.auto_seconds.setValue(float(settings.auto_capture_seconds))
        self.track_timeout.setValue(float(settings.track_timeout_s))
        self._mute = False

    def changes(self) -> dict:
        return {
            "detection_method": self.method.currentText(),
            "smoothing": self.smoothing.currentText(),
            "min_area": int(self.min_area.value()),
            "ignore_border": self.ignore_border.isChecked(),
            "roi_enabled": self.roi_enabled.isChecked(),
            "stability_threshold_mm": length_from_unit(self.stability_threshold.value(), self._unit),
            "stability_samples": int(self.stability_samples.value()),
            "auto_capture": self.auto_capture.isChecked(),
            "auto_capture_seconds": float(self.auto_seconds.value()),
            "track_timeout_s": float(self.track_timeout.value()),
        }

    def _emit(self, *_args) -> None:
        if not self._mute:
            self.edited.emit()

    @staticmethod
    def _set_text(combo: QComboBox, text: str) -> None:
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
