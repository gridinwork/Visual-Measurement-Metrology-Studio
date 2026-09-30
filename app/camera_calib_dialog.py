"""Collect chessboard or ChArUco views and save the camera matrix."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.logging_setup import get_logger
from calibration.aruco_calibration import dictionary_names
from calibration.camera_calibration import CameraCalibrator


class CameraCalibrationDialog(QDialog):
    def __init__(self, camera_index: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Camera Calibration")
        self.resize(560, 640)
        self.camera_index = int(camera_index)
        self.calibrator = CameraCalibrator()
        self._raw = None
        self.pattern = QComboBox()
        self.pattern.addItem("Chessboard", "chessboard")
        self.pattern.addItem("ChArUco", "charuco")
        self.corners_x = self._spin_int(3, 20, 9)
        self.corners_y = self._spin_int(3, 20, 6)
        self.squares_x = self._spin_int(3, 20, 5)
        self.squares_y = self._spin_int(3, 20, 7)
        self.square_mm = self._spin_float(1, 200, 25)
        self.marker_mm = self._spin_float(1, 200, 15)
        self.dictionary = QComboBox()
        self.dictionary.addItems(dictionary_names() or ["DICT_4X4_50"])
        self.preview = QLabel("Start the camera, then show the pattern.")
        self.preview.setMinimumHeight(280)
        self.preview.setAlignment(Qt.AlignCenter)
        self.status = QLabel("No frame yet.")
        self.status.setWordWrap(True)
        self.capture_button = QPushButton("Capture View")
        self.clear_button = QPushButton("Clear")
        self.calibrate_button = QPushButton("Calibrate and Save")
        self.calibrate_button.setObjectName("primary")
        self.capture_button.clicked.connect(self._capture)
        self.clear_button.clicked.connect(self._clear)
        self.calibrate_button.clicked.connect(self._calibrate)
        self.pattern.currentIndexChanged.connect(self._toggle_pattern)
        form = QFormLayout()
        form.addRow("Pattern", self.pattern)
        form.addRow("Chessboard corners X", self.corners_x)
        form.addRow("Chessboard corners Y", self.corners_y)
        form.addRow("ChArUco squares X", self.squares_x)
        form.addRow("ChArUco squares Y", self.squares_y)
        form.addRow("Square size, mm", self.square_mm)
        form.addRow("Marker size, mm", self.marker_mm)
        form.addRow("Dictionary", self.dictionary)
        buttons = QHBoxLayout()
        buttons.addWidget(self.capture_button)
        buttons.addWidget(self.clear_button)
        buttons.addWidget(self.calibrate_button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self._toggle_pattern()

    def set_camera_index(self, index: int) -> None:
        self.camera_index = int(index)

    def consider(self, raw_bgr) -> None:
        if raw_bgr is None or not self.isVisible():
            return
        self._raw = raw_bgr
        preview = raw_bgr.copy()
        found = False
        if self.pattern.currentData() == "chessboard":
            corners = self.calibrator.preview_chessboard(raw_bgr, self.corners_x.value(), self.corners_y.value())
            if corners is not None:
                cv2.drawChessboardCorners(
                    preview,
                    (int(self.corners_x.value()), int(self.corners_y.value())),
                    corners,
                    True,
                )
                found = True
        else:
            found = self.calibrator.preview_charuco(
                raw_bgr,
                self.squares_x.value(),
                self.squares_y.value(),
                self.square_mm.value(),
                self.marker_mm.value(),
                self.dictionary.currentText(),
            )
        self._show(preview)
        state = "Pattern found — capture this view." if found else "Pattern not found."
        self.status.setText(f"{state}  Captured views: {self.calibrator.sample_count()}")

    def _capture(self) -> None:
        if self._raw is None:
            self.status.setText("Start the camera first.")
            return
        if self.pattern.currentData() == "chessboard":
            ok = self.calibrator.add_chessboard(
                self._raw,
                self.corners_x.value(),
                self.corners_y.value(),
                self.square_mm.value(),
            )
        else:
            ok = self.calibrator.add_charuco(
                self._raw,
                self.squares_x.value(),
                self.squares_y.value(),
                self.square_mm.value(),
                self.marker_mm.value(),
                self.dictionary.currentText(),
            )
        if ok:
            self.status.setText(f"View stored. Captured views: {self.calibrator.sample_count()}")
        else:
            self.status.setText("This frame does not contain a clear pattern.")

    def _clear(self) -> None:
        self.calibrator.reset_samples()
        self.status.setText("Captured views cleared.")

    def _calibrate(self) -> None:
        try:
            rms = self.calibrator.calibrate()
            path = self.calibrator.save(self.camera_index, self.pattern.currentData())
        except RuntimeError as exc:
            self.status.setText(str(exc))
            return
        self.status.setText(f"Saved {path.name}. RMS {rms:.3f}. Enable Lens Distortion Correction to use it.")
        get_logger().info("Camera calibration saved %s rms %.4f", path, rms)
        if self.parent() is not None and hasattr(self.parent(), "worker"):
            self.parent().worker.engine.request_camera_reload()

    def _toggle_pattern(self) -> None:
        chess = self.pattern.currentData() == "chessboard"
        self.corners_x.setEnabled(chess)
        self.corners_y.setEnabled(chess)
        self.squares_x.setEnabled(not chess)
        self.squares_y.setEnabled(not chess)
        self.marker_mm.setEnabled(not chess)
        self.dictionary.setEnabled(not chess)

    def _show(self, bgr) -> None:
        rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image)
        self.preview.setPixmap(pixmap.scaled(520, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    @staticmethod
    def _spin_int(low, high, value) -> QSpinBox:
        box = QSpinBox()
        box.setRange(low, high)
        box.setValue(value)
        return box

    @staticmethod
    def _spin_float(low, high, value) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(low, high)
        box.setDecimals(2)
        box.setValue(value)
        return box
