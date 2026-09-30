"""Edge and recording settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.models import DETECTION_DEFAULTS


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.resize(420, 460)
        self.canny_low = self._int(0, 254, settings.canny_low)
        self.canny_high = self._int(1, 255, settings.canny_high)
        self.blur = self._int(1, 31, settings.blur)
        self.morph = self._int(1, 31, settings.morph_kernel)
        self.min_area = self._int(10, 2_000_000, settings.min_area)
        self.max_area = self._int(0, 5_000_000, settings.max_area)
        self.threshold = self._int(0, 255, settings.threshold)
        self.record_resolution = QComboBox()
        self.record_resolution.addItems(["1280x720", "1920x1080"])
        index = self.record_resolution.findText(settings.record_resolution)
        if index >= 0:
            self.record_resolution.setCurrentIndex(index)
        self.record_fps = QComboBox()
        self.record_fps.addItems(["24", "30", "60"])
        fps_index = self.record_fps.findText(str(settings.record_fps))
        if fps_index >= 0:
            self.record_fps.setCurrentIndex(fps_index)
        reset = QPushButton("Reset Defaults")
        reset.clicked.connect(self._reset)
        form = QFormLayout()
        form.addRow("Canny low", self.canny_low)
        form.addRow("Canny high", self.canny_high)
        form.addRow("Blur", self.blur)
        form.addRow("Morphology kernel", self.morph)
        form.addRow("Minimum area", self.min_area)
        form.addRow("Maximum area (0 = auto)", self.max_area)
        form.addRow("Threshold (0 = Otsu)", self.threshold)
        form.addRow("Demo resolution", self.record_resolution)
        form.addRow("Demo FPS", self.record_fps)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(reset)
        layout.addWidget(buttons)

    def values(self) -> dict:
        low = int(self.canny_low.value())
        high = int(self.canny_high.value())
        if high <= low:
            high = min(255, low + 1)
        blur = int(self.blur.value())
        morph = int(self.morph.value())
        if blur % 2 == 0:
            blur += 1
        if morph % 2 == 0:
            morph += 1
        return {
            "canny_low": low,
            "canny_high": high,
            "blur": blur,
            "morph_kernel": morph,
            "min_area": int(self.min_area.value()),
            "max_area": int(self.max_area.value()),
            "threshold": int(self.threshold.value()),
            "record_resolution": self.record_resolution.currentText(),
            "record_fps": int(self.record_fps.currentText()),
        }

    def _reset(self) -> None:
        self.canny_low.setValue(DETECTION_DEFAULTS["canny_low"])
        self.canny_high.setValue(DETECTION_DEFAULTS["canny_high"])
        self.blur.setValue(DETECTION_DEFAULTS["blur"])
        self.morph.setValue(DETECTION_DEFAULTS["morph_kernel"])
        self.min_area.setValue(DETECTION_DEFAULTS["min_area"])
        self.max_area.setValue(DETECTION_DEFAULTS["max_area"])
        self.threshold.setValue(DETECTION_DEFAULTS["threshold"])

    @staticmethod
    def _int(low: int, high: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(low, high)
        box.setValue(int(value))
        return box
