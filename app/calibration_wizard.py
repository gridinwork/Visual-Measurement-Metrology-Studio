"""Seven-step scale calibration. The camera view stays on the main window."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.logging_setup import get_logger
from app.models import parse_resolution
from calibration.profile_manager import ProfileManager


class CalibrationWizard(QDialog):
    def __init__(self, store, on_start, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.on_start = on_start
        self.profiles = ProfileManager()
        self._result = None
        self._fixed = False
        self.setWindowTitle("Calibration Wizard")
        self.resize(520, 420)
        self.title = QLabel("Step 1 of 7 — Select Camera")
        self.title.setObjectName("value")
        self.stack = QStackedWidget()
        self._build_pages()
        self.back_button = QPushButton("Back")
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("primary")
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        buttons = QHBoxLayout()
        buttons.addWidget(self.back_button)
        buttons.addStretch(1)
        buttons.addWidget(self.next_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.stack, 1)
        layout.addLayout(buttons)
        self._show_step(0)

    def set_result(self, result) -> None:
        self._result = result
        if self.stack.currentIndex() in (3, 5):
            self._fill_live_labels()

    def _build_pages(self) -> None:
        settings = self.store.snapshot()
        self.camera_combo = QComboBox()
        for index in range(4):
            self.camera_combo.addItem(f"Camera {index}", index)
        current = self.camera_combo.findData(settings.camera_index)
        if current >= 0:
            self.camera_combo.setCurrentIndex(current)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["640x480", "1280x720", "1920x1080"])
        resolution = self.resolution_combo.findText(settings.resolution)
        if resolution >= 0:
            self.resolution_combo.setCurrentIndex(resolution)
        self.method_combo = QComboBox()
        self.method_combo.addItem("Known Reference Object", "reference")
        self.method_combo.addItem("ArUco Marker", "aruco")
        self.method_combo.addItem("Manual Calibration", "manual")
        self.method_combo.addItem("Fixed Camera Calibration", "fixed")
        self.learn_combo = QComboBox()
        self.learn_combo.addItem("Reference object", "reference")
        self.learn_combo.addItem("ArUco marker", "aruco")
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        self.detect_label = QLabel("Waiting for a frame.")
        self.detect_label.setWordWrap(True)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.1, 5000)
        self.size_spin.setDecimals(2)
        self.size_spin.setValue(settings.reference_width_mm)
        self.size_caption = QLabel("Real size, mm")
        self.validate_label = QLabel("")
        self.validate_label.setWordWrap(True)
        self.profile_name = QLineEdit(settings.fixed_profile or "Office Camera 01")
        self.stack.addWidget(self._page("Choose the camera that looks at the working plane.", self.camera_combo))
        self.stack.addWidget(self._page("Choose the capture resolution. 1280x720 is the default.", self.resolution_combo))
        method_page = self._page("Choose how the pixel scale is established.", self.method_combo, self.learn_combo)
        self.stack.addWidget(method_page)
        self.stack.addWidget(self._page("Place the reference in view. The status updates from the live camera.", self.detect_label))
        self.stack.addWidget(self._page("Enter the real size of the reference.", self.size_caption, self.size_spin))
        self.stack.addWidget(self._page("Check the scale before saving it.", self.validate_label))
        self.stack.addWidget(self._page("Save a named profile. Fixed mode keeps this scale after the reference is removed.", self.profile_name))
        self._method_changed()

    def _page(self, text: str, *widgets) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return page

    def _method_changed(self) -> None:
        self.learn_combo.setVisible(self.method_combo.currentData() == "fixed")

    def _show_step(self, index: int) -> None:
        titles = [
            "Select Camera",
            "Select Resolution",
            "Choose Calibration Method",
            "Detect Reference",
            "Enter Real Size",
            "Validate",
            "Save Profile",
        ]
        self.stack.setCurrentIndex(index)
        self.title.setText(f"Step {index + 1} of 7 — {titles[index]}")
        self.back_button.setEnabled(index > 0)
        self.next_button.setText("Save Profile" if index == 6 else "Next")
        if index == 3:
            self._apply_live_settings()
            self.on_start()
        if index == 4:
            self._configure_size_spin()
        if index in (3, 5):
            self._fill_live_labels()

    def _back(self) -> None:
        if self.stack.currentIndex() > 0:
            self._show_step(self.stack.currentIndex() - 1)

    def _next(self) -> None:
        index = self.stack.currentIndex()
        if index == 5 and not self._scale_ready():
            self.validate_label.setText("The scale is not valid yet. Go back and show the reference.")
            return
        if index == 4:
            self._write_size()
        if index >= 6:
            self._save_profile()
            self.close()
            return
        self._show_step(index + 1)

    def _active_mode(self) -> str:
        method = self.method_combo.currentData()
        if method == "fixed":
            return self.learn_combo.currentData()
        return method

    def _apply_live_settings(self) -> None:
        method = self.method_combo.currentData()
        self._fixed = method == "fixed"
        mode = self._active_mode()
        width, height = parse_resolution(self.resolution_combo.currentText())
        self.store.update(
            camera_index=int(self.camera_combo.currentData()),
            resolution=f"{width}x{height}",
            source="webcam",
            calibration_mode=mode,
        )

    def _configure_size_spin(self) -> None:
        mode = self._active_mode()
        settings = self.store.snapshot()
        if mode == "aruco":
            self.size_caption.setText("Marker size, mm")
            self.size_spin.setValue(settings.marker_size_mm)
        elif mode == "manual":
            self.size_caption.setText("Real distance, mm")
            self.size_spin.setValue(settings.manual_distance_mm)
        else:
            self.size_caption.setText("Reference width, mm")
            self.size_spin.setValue(settings.reference_width_mm)

    def _write_size(self) -> None:
        mode = self._active_mode()
        value = float(self.size_spin.value())
        if mode == "aruco":
            self.store.update(marker_size_mm=value)
        elif mode == "manual":
            self.store.update(manual_distance_mm=value)
        else:
            self.store.update(reference_width_mm=value)

    def _scale_ready(self) -> bool:
        return self._result is not None and self._result.calibration.valid and self._result.calibration.pixels_per_mm

    def _fill_live_labels(self) -> None:
        if self._result is None:
            self.detect_label.setText("Waiting for a frame. Start is requested automatically on this step.")
            self.validate_label.setText("No frame yet.")
            return
        calibration = self._result.calibration
        ppm = "—" if not calibration.pixels_per_mm else f"{calibration.pixels_per_mm:.2f} px/mm"
        text = f"{calibration.message}\n{calibration.detail}\nScale: {ppm}\nObjects: {len(self._result.objects)}"
        if calibration.perspective_warning:
            text += "\n" + (calibration.perspective_message or "PERSPECTIVE WARNING")
        if self._active_mode() == "manual":
            text += "\nClick two points on the main image."
        self.detect_label.setText(text)
        self.validate_label.setText(text)

    def _save_profile(self) -> None:
        if not self._scale_ready():
            self.validate_label.setText("Nothing to save. The scale is not valid.")
            return
        name = self.profile_name.text().strip() or "Office Camera 01"
        calibration = self._result.calibration
        settings = self.store.snapshot()
        width, height = parse_resolution(settings.resolution)
        self.profiles.save(
            name,
            calibration.pixels_per_mm,
            (width, height),
            settings.camera_index,
            "fixed" if self._fixed else settings.calibration_mode,
            reference_width_mm=settings.reference_width_mm,
            marker_size_mm=settings.marker_size_mm,
        )
        if self._fixed:
            self.store.update(
                calibration_mode="fixed",
                fixed_profile=name,
                fixed_pixels_per_mm=float(calibration.pixels_per_mm),
            )
        else:
            self.store.update(fixed_profile=name, fixed_pixels_per_mm=float(calibration.pixels_per_mm))
        get_logger().info("Calibration profile saved %s %.3f px/mm", name, calibration.pixels_per_mm)
        self.title.setText(f"Profile saved: {name}   {calibration.pixels_per_mm:.2f} px/mm")
        self.next_button.setEnabled(False)
