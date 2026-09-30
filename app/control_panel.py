"""Top bar: source, camera, resolution, calibration mode, units, and transport."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

SOURCES = [("Webcam", "webcam"), ("Video File", "video"), ("Image", "image")]
MODES = [
    ("Known Reference Object", "reference"),
    ("ArUco Marker", "aruco"),
    ("Manual Calibration", "manual"),
    ("Fixed Camera Calibration", "fixed"),
]
RESOLUTIONS = ["640x480", "1280x720", "1920x1080"]
UNITS = ["mm", "cm", "inch"]


class ControlPanel(QFrame):
    start_clicked = Signal()
    stop_clicked = Signal()
    pause_clicked = Signal()
    source_changed = Signal(str)
    camera_changed = Signal(int)
    resolution_changed = Signal(str)
    mode_changed = Signal(str)
    units_changed = Signal(str)
    browse_clicked = Signal()
    refresh_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.source_combo = QComboBox()
        for label, key in SOURCES:
            self.source_combo.addItem(label, key)
        self.camera_combo = QComboBox()
        self.camera_combo.addItem("Camera 0", 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        self.mode_combo = QComboBox()
        for label, key in MODES:
            self.mode_combo.addItem(label, key)
        self.units_combo = QComboBox()
        self.units_combo.addItems(UNITS)
        self.browse_button = QPushButton("Open File")
        self.refresh_button = QPushButton("Find Cameras")
        self.start_button = QPushButton("START CAMERA")
        self.start_button.setObjectName("primary")
        self.stop_button = QPushButton("STOP")
        self.pause_button = QPushButton("PAUSE")
        self.path_label = QLabel("Webcam")
        self.path_label.setObjectName("muted")

        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("Source"))
        row_a.addWidget(self.source_combo)
        row_a.addWidget(self.browse_button)
        row_a.addWidget(QLabel("Camera"))
        row_a.addWidget(self.camera_combo)
        row_a.addWidget(self.refresh_button)
        row_a.addWidget(QLabel("Resolution"))
        row_a.addWidget(self.resolution_combo)
        row_a.addStretch(1)

        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("Calibration"))
        row_b.addWidget(self.mode_combo)
        row_b.addWidget(QLabel("Units"))
        row_b.addWidget(self.units_combo)
        row_b.addWidget(self.start_button)
        row_b.addWidget(self.stop_button)
        row_b.addWidget(self.pause_button)
        row_b.addWidget(self.path_label, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(row_a)
        layout.addLayout(row_b)

        self.source_combo.currentIndexChanged.connect(self._emit_source)
        self.camera_combo.currentIndexChanged.connect(self._emit_camera)
        self.resolution_combo.currentIndexChanged.connect(self._emit_resolution)
        self.mode_combo.currentIndexChanged.connect(self._emit_mode)
        self.units_combo.currentIndexChanged.connect(self._emit_units)
        self.browse_button.clicked.connect(self.browse_clicked.emit)
        self.refresh_button.clicked.connect(self.refresh_clicked.emit)
        self.start_button.clicked.connect(self.start_clicked.emit)
        self.stop_button.clicked.connect(self.stop_clicked.emit)
        self.pause_button.clicked.connect(self.pause_clicked.emit)
        self._apply_source_visibility()

    def set_settings(self, settings) -> None:
        self._set_combo_data(self.source_combo, settings.source)
        self._set_combo_data(self.camera_combo, int(settings.camera_index))
        self._set_combo_text(self.resolution_combo, settings.resolution)
        self._set_combo_data(self.mode_combo, settings.calibration_mode)
        self._set_combo_text(self.units_combo, settings.units)
        if settings.source == "video" and settings.last_video:
            self.path_label.setText(settings.last_video)
        elif settings.source == "image" and settings.last_image:
            self.path_label.setText(settings.last_image)
        else:
            self.path_label.setText("Webcam")
        self._apply_source_visibility()

    def set_cameras(self, indexes: list[int]) -> None:
        current = self.camera_combo.currentData()
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        if not indexes:
            indexes = [0]
        for index in indexes:
            self.camera_combo.addItem(f"Camera {index}", int(index))
        restored = self.camera_combo.findData(current)
        self.camera_combo.setCurrentIndex(restored if restored >= 0 else 0)
        self.camera_combo.blockSignals(False)

    def set_running(self, running: bool, paused: bool) -> None:
        self.stop_button.setEnabled(running)
        self.pause_button.setEnabled(running)
        self.pause_button.setText("RESUME" if paused else "PAUSE")
        source = self.source_combo.currentData()
        self.start_button.setText("START" if source != "webcam" else "START CAMERA")

    def _apply_source_visibility(self) -> None:
        webcam = self.source_combo.currentData() == "webcam"
        self.camera_combo.setEnabled(webcam)
        self.refresh_button.setEnabled(webcam)
        self.browse_button.setEnabled(not webcam)
        self.start_button.setText("START CAMERA" if webcam else "START")

    def _emit_source(self) -> None:
        self._apply_source_visibility()
        self.source_changed.emit(self.source_combo.currentData())

    def _emit_camera(self) -> None:
        data = self.camera_combo.currentData()
        if data is not None:
            self.camera_changed.emit(int(data))

    def _emit_resolution(self) -> None:
        self.resolution_changed.emit(self.resolution_combo.currentText())

    def _emit_mode(self) -> None:
        self.mode_changed.emit(self.mode_combo.currentData())

    def _emit_units(self) -> None:
        self.units_changed.emit(self.units_combo.currentText())

    @staticmethod
    def _set_combo_data(combo: QComboBox, value) -> None:
        combo.blockSignals(True)
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    @staticmethod
    def _set_combo_text(combo: QComboBox, text: str) -> None:
        combo.blockSignals(True)
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
