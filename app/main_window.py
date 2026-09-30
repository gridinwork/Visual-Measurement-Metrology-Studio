"""Main window of Visual Measurement & Metrology Studio."""

from __future__ import annotations

import math
import os
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
from PySide6.QtCore import QByteArray, Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.calibration_wizard import CalibrationWizard
from app.camera_calib_dialog import CameraCalibrationDialog
from app.control_panel import ControlPanel
from app.history_panel import HistoryPanel
from app.history_store import HistoryStore
from app.logging_setup import get_logger
from app.measurement_panel import DetectionPanel, MeasurementPanel, QualityPanel
from app.models import HistoryRow, parse_resolution
from app.part_store import PartPreset, PartStore
from app.paths import DIR_DEMOS, DIR_EXPORTS, DIR_MEASUREMENTS, ensure_dirs
from app.processor import ProcessingWorker
from app.settings_dialog import SettingsDialog
from app.settings_store import SettingsStore
from app.video_widget import VideoWidget
from calibration.profile_manager import ProfileManager
from capture.camera_capture import list_cameras
from export.csv_exporter import export_history
from export.measurement_exporter import save_measurement
from recording.demo_recorder import DemoRecorder


class _CameraScan(QThread):
    found = Signal(list)

    def run(self) -> None:
        self.found.emit(list_cameras())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        ensure_dirs()
        self.setWindowTitle("Visual Measurement & Metrology Studio")
        self.resize(1440, 900)
        self.log = get_logger()
        self.store = SettingsStore()
        self.parts = PartStore()
        self.history = HistoryStore()
        self.profiles = ProfileManager()
        self.worker = ProcessingWorker(self.store)
        self._result = None
        self._running = False
        self._paused = False
        self._recorder: DemoRecorder | None = None
        self._wizard: CalibrationWizard | None = None
        self._camera_dialog: CameraCalibrationDialog | None = None
        self._seen_ids: set[int] = set()
        self._result_state: dict[int, str] = {}
        self._was_valid = False
        self._stable_since: float | None = None
        self._auto_signature = None
        self._last_ppm: float | None = None
        self._size_noted = False
        self._disp_times: deque[float] = deque(maxlen=30)
        self._build()
        self._wire()
        self._push_settings()
        self._restore_geometry()
        self.history_panel.set_rows(self.history.rows, self.store.snapshot().units)
        self.worker.start()
        self._scan_cameras()

    def _build(self) -> None:
        self.controls = ControlPanel()
        self.video = VideoWidget()
        self.measure = MeasurementPanel()
        self.quality = QualityPanel()
        self.detection = DetectionPanel()
        self.history_panel = HistoryPanel()
        tabs = QTabWidget()
        tabs.addTab(self.measure, "Measurement")
        tabs.addTab(self.quality, "Quality")
        tabs.addTab(self.detection, "Detection")
        tabs.addTab(self.history_panel, "History")
        self.tabs = tabs

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.video)
        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([980, 420])

        self.status_line = QLabel("CAM —    PROC —    DISP —    REFERENCE NOT FOUND")
        self.status_line.setObjectName("muted")
        self.upwork_button = QPushButton("UPWORK DEMO")
        self.record_button = QPushButton("● RECORD 15s DEMO")
        self.record_button.setObjectName("record")
        self.freeze_button = QPushButton("FREEZE MEASUREMENT")
        self.save_button = QPushButton("SAVE MEASUREMENT")
        self.export_button = QPushButton("EXPORT CSV")
        self.folder_button = QPushButton("OPEN FOLDER")
        self.timer_label = QLabel("")
        self.timer_label.setObjectName("value")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFormat("Demo")
        actions = QHBoxLayout()
        actions.addWidget(self.upwork_button)
        actions.addWidget(self.record_button)
        actions.addWidget(self.freeze_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.timer_label)
        actions.addWidget(self.progress, 1)

        central = QWidget()
        central.setObjectName("central")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.controls)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.status_line)
        layout.addLayout(actions)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self._build_menu()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("Open Video", self._browse_video)
        file_menu.addAction("Open Image", self._browse_image)
        file_menu.addAction("Export CSV", self._export_csv)
        file_menu.addAction("Open Measurements", lambda: os.startfile(DIR_MEASUREMENTS))
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        calib_menu = self.menuBar().addMenu("Calibration")
        calib_menu.addAction("Calibration Wizard", self._open_wizard)
        calib_menu.addAction("Camera Calibration", self._open_camera_calibration)

        view_menu = self.menuBar().addMenu("View")
        self.debug_action = QAction("Debug", self, checkable=True)
        self.presentation_action = QAction("Clean Presentation", self, checkable=True)
        view_menu.addAction(self.debug_action)
        view_menu.addAction(self.presentation_action)
        view_menu.addSeparator()
        self.overlay_actions = {}
        for key, label in (
            ("show_contours", "Contours"),
            ("show_boxes", "Boxes"),
            ("show_dimensions", "Dimensions"),
            ("show_angle", "Angle"),
            ("show_id", "Object ID"),
            ("show_center", "Center"),
            ("show_fps", "FPS"),
            ("show_calibration", "Calibration Status"),
        ):
            action = QAction(label, self, checkable=True)
            view_menu.addAction(action)
            self.overlay_actions[key] = action
            action.toggled.connect(lambda checked, name=key: self.store.update(**{name: checked}))
        self.debug_action.toggled.connect(lambda checked: self.store.update(debug=checked))
        self.presentation_action.toggled.connect(lambda checked: self.store.update(presentation=checked))

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction("Advanced Settings", self._open_settings)
        tools_menu.addAction("Clear History", self._clear_history)

    def _wire(self) -> None:
        self.controls.start_clicked.connect(self._start)
        self.controls.stop_clicked.connect(self._stop)
        self.controls.pause_clicked.connect(self._toggle_pause)
        self.controls.source_changed.connect(lambda value: self.store.update(source=value))
        self.controls.camera_changed.connect(self._camera_changed)
        self.controls.resolution_changed.connect(self._resolution_changed)
        self.controls.mode_changed.connect(self._mode_changed)
        self.controls.units_changed.connect(self._units_changed)
        self.controls.browse_clicked.connect(self._browse_current)
        self.controls.refresh_clicked.connect(self._scan_cameras)
        self.video.clicked.connect(self._select_at)
        self.video.point_clicked.connect(self._add_manual_point)
        self.video.roi_finished.connect(self._set_roi)
        self.measure.edited.connect(self._measure_edited)
        self.measure.object_selected.connect(lambda object_id: self.store.update(selected_object_id=int(object_id)))
        self.measure.clear_points.connect(self._clear_points)
        self.measure.save_profile.connect(self._save_profile)
        self.measure.load_profile.connect(self._load_profile)
        self.measure.delete_profile.connect(self._delete_profile)
        self.quality.edited.connect(self._quality_edited)
        self.quality.save_preset.connect(self._save_part)
        self.quality.delete_preset.connect(self._delete_part)
        self.detection.edited.connect(self._detection_edited)
        self.detection.redraw_roi.connect(lambda: self.video.set_mode("roi"))
        self.detection.advanced.connect(self._open_settings)
        self.history_panel.export_clicked.connect(self._export_csv)
        self.history_panel.clear_clicked.connect(self._clear_history)
        self.history_panel.add_clicked.connect(self._add_history_current)
        self.upwork_button.clicked.connect(self._upwork_demo)
        self.record_button.clicked.connect(self._toggle_record)
        self.freeze_button.clicked.connect(self._toggle_pause)
        self.save_button.clicked.connect(self._save_measurement)
        self.export_button.clicked.connect(self._export_csv)
        self.folder_button.clicked.connect(lambda: os.startfile(DIR_DEMOS))
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.source_started.connect(self._on_source_started)
        self.worker.source_stopped.connect(self._on_source_stopped)
        self.worker.source_error.connect(self._on_source_error)

    def _push_settings(self) -> None:
        settings = self.store.snapshot()
        self.controls.set_settings(settings)
        self.measure.set_settings(settings)
        self.quality.set_parts(self.parts.parts, settings.part_name)
        self.quality.set_settings(settings)
        self.detection.set_settings(settings)
        self.debug_action.blockSignals(True)
        self.presentation_action.blockSignals(True)
        self.debug_action.setChecked(settings.debug)
        self.presentation_action.setChecked(settings.presentation)
        self.debug_action.blockSignals(False)
        self.presentation_action.blockSignals(False)
        for key, action in self.overlay_actions.items():
            action.blockSignals(True)
            action.setChecked(bool(getattr(settings, key)))
            action.blockSignals(False)
        self.history_panel.set_rows(self.history.rows, settings.units)

    def _restore_geometry(self) -> None:
        settings = self.store.snapshot()
        if not settings.window_geometry:
            return
        try:
            self.restoreGeometry(QByteArray.fromHex(settings.window_geometry.encode("ascii")))
        except (ValueError, TypeError):
            return

    def _scan_cameras(self) -> None:
        self._scan = _CameraScan()
        self._scan.found.connect(self.controls.set_cameras)
        self._scan.start()

    def _start(self) -> None:
        settings = self.store.snapshot()
        if settings.source == "video":
            if not settings.last_video:
                self._browse_video()
                return
            spec = {"kind": "video", "path": settings.last_video}
        elif settings.source == "image":
            if not settings.last_image:
                self._browse_image()
                return
            spec = {"kind": "image", "path": settings.last_image}
        else:
            spec = {"kind": "webcam", "index": settings.camera_index, "resolution": settings.resolution}
        self._paused = False
        self.freeze_button.setText("FREEZE MEASUREMENT")
        self.worker.request_start(spec)
        self.log.info(
            "Source start requested kind=%s camera=%s resolution=%s mode=%s",
            spec["kind"],
            settings.camera_index,
            settings.resolution,
            settings.calibration_mode,
        )

    def _stop(self) -> None:
        self._paused = False
        self.freeze_button.setText("FREEZE MEASUREMENT")
        self.worker.request_stop()

    def _toggle_pause(self) -> None:
        if not self._running:
            return
        self._paused = not self._paused
        self.worker.request_pause(self._paused)
        self.freeze_button.setText("RESUME" if self._paused else "FREEZE MEASUREMENT")
        self.controls.set_running(True, self._paused)
        self.statusBar().showMessage("Measurement frozen" if self._paused else "Live")

    def _camera_changed(self, index: int) -> None:
        self.store.update(camera_index=int(index))
        if self._running and self.store.snapshot().source == "webcam":
            self._start()

    def _resolution_changed(self, text: str) -> None:
        self.store.update(resolution=text)
        if self._running and self.store.snapshot().source == "webcam":
            self._start()

    def _mode_changed(self, mode: str) -> None:
        self.store.update(calibration_mode=mode)
        self.measure.set_settings(self.store.snapshot())
        if mode == "manual":
            self.video.set_mode("points")
            self.statusBar().showMessage("Click two points on the image, then enter the real distance.")
        elif self.video._mode == "points":
            self.video.set_mode("select")

    def _units_changed(self, unit: str) -> None:
        self.store.update(units=unit)
        self._push_settings()

    def _browse_current(self) -> None:
        source = self.store.snapshot().source
        if source == "video":
            self._browse_video()
        elif source == "image":
            self._browse_image()

    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open video", "", "Video (*.mp4 *.avi *.mov *.mkv)"
        )
        if not path:
            return
        self.store.update(source="video", last_video=path)
        self.controls.set_settings(self.store.snapshot())
        self._start()

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", "", "Image (*.jpg *.jpeg *.png *.webp)"
        )
        if not path:
            return
        self.store.update(source="image", last_image=path)
        self.controls.set_settings(self.store.snapshot())
        self._start()

    def _measure_edited(self) -> None:
        self.store.update(**self.measure.changes())

    def _quality_edited(self) -> None:
        self.store.update(**self.quality.changes())

    def _detection_edited(self) -> None:
        changes = self.detection.changes()
        self.store.update(**changes)
        if changes.get("roi_enabled") and not self.store.snapshot().roi:
            self.video.set_mode("roi")
            self.statusBar().showMessage("Drag a rectangle on the image to set the measurement ROI.")
        elif self.video._mode == "roi" and not changes.get("roi_enabled"):
            self.video.set_mode("select")

    def _set_roi(self, x: float, y: float, width: float, height: float) -> None:
        self.store.update(roi=[x, y, width, height], roi_enabled=True)
        self.detection.set_settings(self.store.snapshot())
        self.video.set_mode("select")
        self.log.info("ROI set")

    def _add_manual_point(self, x: float, y: float) -> None:
        if self._result is None:
            return
        settings = self.store.snapshot()
        points = [list(point) for point in settings.manual_points]
        if len(points) >= 2:
            points = []
        points.append([float(x), float(y)])
        height, width = self._result.display_bgr.shape[:2]
        self.store.update(manual_points=points, manual_frame_wh=[width, height], calibration_mode="manual")
        if len(points) >= 2 and (self._wizard is None):
            self.video.set_mode("select")
        self.statusBar().showMessage(f"Manual points: {len(points)} / 2")

    def _clear_points(self) -> None:
        self.store.update(manual_points=[], manual_frame_wh=[])
        self.video.set_mode("points")

    def _select_at(self, x: float, y: float) -> None:
        if self._result is None:
            return
        point = (float(x), float(y))
        for obj in self._result.objects:
            contour = obj.contour if obj.contour is not None else np.asarray(obj.box, dtype=np.float32)
            if contour is None or len(contour) < 3:
                continue
            if cv2.pointPolygonTest(np.asarray(contour, dtype=np.float32), point, False) >= 0:
                self.store.update(selected_object_id=int(obj.id))
                return

    def _save_profile(self, name: str) -> None:
        ppm = None
        if self._result and self._result.calibration.pixels_per_mm:
            ppm = self._result.calibration.pixels_per_mm
        elif self._last_ppm:
            ppm = self._last_ppm
        if not ppm:
            QMessageBox.warning(self, "Profile", "Calibrate a scale before saving a profile.")
            return
        settings = self.store.snapshot()
        if self._result is not None:
            height, width = self._result.display_bgr.shape[:2]
        else:
            width, height = parse_resolution(settings.resolution)
        self.profiles.save(
            name,
            ppm,
            (width, height),
            settings.camera_index,
            "fixed",
            reference_width_mm=settings.reference_width_mm,
            marker_size_mm=settings.marker_size_mm,
        )
        self.store.update(calibration_mode="fixed", fixed_profile=name, fixed_pixels_per_mm=float(ppm))
        self._push_settings()
        self.log.info("Calibration profile saved %s %.3f px/mm", name, ppm)
        self.statusBar().showMessage(f"Profile saved: {name}")

    def _load_profile(self, name: str) -> None:
        data = self.profiles.load(name)
        if not data or not data.get("pixels_per_mm"):
            QMessageBox.warning(self, "Profile", "That profile could not be read.")
            return
        self.store.update(
            calibration_mode="fixed",
            fixed_profile=data.get("name", name),
            fixed_pixels_per_mm=float(data["pixels_per_mm"]),
        )
        self._push_settings()
        self.log.info("Calibration profile loaded %s", name)

    def _delete_profile(self, name: str) -> None:
        self.profiles.delete(name)
        self.store.update(fixed_profile="")
        self._push_settings()

    def _save_part(self) -> None:
        changes = self.quality.changes()
        name = changes["part_name"] or "Part"
        self.parts.upsert(
            PartPreset(
                name=name,
                nominal_width_mm=changes["nominal_width_mm"],
                nominal_height_mm=changes["nominal_height_mm"],
                width_upper_mm=changes["width_upper_mm"],
                width_lower_mm=changes["width_lower_mm"],
                height_upper_mm=changes["height_upper_mm"],
                height_lower_mm=changes["height_lower_mm"],
            )
        )
        changes["part_name"] = name
        changes["qc_enabled"] = True
        self.store.update(**changes)
        self.quality.set_parts(self.parts.parts, name)
        self.quality.set_settings(self.store.snapshot())
        self.log.info("Part preset saved %s", name)

    def _delete_part(self) -> None:
        name = self.quality.part_name.text().strip()
        if not name:
            return
        self.parts.delete(name)
        self.store.update(part_name="")
        self.quality.set_parts(self.parts.parts, "")
        self.quality.set_settings(self.store.snapshot())

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.store.snapshot(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.store.update(**dialog.values())
        self._push_settings()

    def _open_wizard(self) -> None:
        self._wizard = CalibrationWizard(self.store, self._start, self)
        self._wizard.finished.connect(self._wizard_closed)
        self._wizard.show()

    def _wizard_closed(self) -> None:
        self._wizard = None
        if self.video._mode == "points" and len(self.store.snapshot().manual_points) >= 2:
            self.video.set_mode("select")
        self._push_settings()

    def _open_camera_calibration(self) -> None:
        if self._camera_dialog is None:
            self._camera_dialog = CameraCalibrationDialog(self.store.snapshot().camera_index, self)
        self._camera_dialog.set_camera_index(self.store.snapshot().camera_index)
        self._camera_dialog.show()
        self._camera_dialog.raise_()

    def _upwork_demo(self) -> None:
        settings = self.store.snapshot()
        changes = {
            "show_contours": True,
            "show_boxes": True,
            "show_dimensions": True,
            "show_angle": True,
            "show_id": True,
            "show_center": True,
            "show_fps": True,
            "show_calibration": True,
            "debug": False,
            "presentation": True,
        }
        if settings.part_name or settings.qc_enabled:
            changes["qc_enabled"] = True
        self.store.update(**changes)
        self._push_settings()
        self.statusBar().showMessage("Upwork demo preset is on. Press RECORD 15s DEMO.")

    def _toggle_record(self) -> None:
        if self._recorder is not None and self._recorder.isRunning():
            if not self._recorder.accepts_frames:
                self._recorder.cancel()
            return
        if self._result is None:
            QMessageBox.information(self, "Demo", "Start the camera before recording the demo.")
            return
        settings = self.store.snapshot()
        width, height = parse_resolution(settings.record_resolution)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DIR_DEMOS / f"visual_measurement_demo_{stamp}.mp4"
        self._recorder = DemoRecorder(path, (width, height), int(settings.record_fps), 15.0)
        self._recorder.countdown.connect(self._on_countdown)
        self._recorder.progress.connect(self._on_progress)
        self._recorder.saved.connect(self._on_demo_saved)
        self._recorder.failed.connect(self._on_demo_failed)
        self._recorder.phase_changed.connect(self._on_record_phase)
        self.worker.set_sink(self._recorder.submit)
        self.progress.setValue(0)
        self._recorder.start()
        self.log.info("Recording started %s", path)

    def _on_countdown(self, number: int) -> None:
        if number > 0:
            self.video.set_banner(str(number))
            self.timer_label.setText(str(number))
        else:
            self.video.set_banner("")
            self.timer_label.setText("00:15")

    def _on_progress(self, remaining: float, fraction: float) -> None:
        self.progress.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
        self.timer_label.setText(f"00:{max(0, int(math.ceil(remaining))):02d}")
        self.video.set_banner("")

    def _on_record_phase(self, phase: str) -> None:
        if phase == "countdown":
            self.record_button.setText("CANCEL")
        elif phase == "recording":
            self.record_button.setText("● REC")
            self.record_button.setEnabled(False)
        elif phase == "cancelled":
            self._reset_record_ui()

    def _on_demo_saved(self, info: dict) -> None:
        self._reset_record_ui()
        self.progress.setValue(1000)
        size_mb = info.get("size_bytes", 0) / (1024 * 1024)
        text = (
            "DEMO SAVED\n\n"
            f"Duration: {info.get('duration_s', 0):.2f} s\n"
            f"Resolution: {info.get('width')}x{info.get('height')}\n"
            f"FPS: {info.get('fps', 0):.2f}\n"
            f"File size: {size_mb:.2f} MB\n"
            f"Codec: {info.get('codec')}\n\n"
            f"{info.get('path')}"
        )
        self.log.info(
            "Recording completed duration=%.2fs path=%s",
            info.get("duration_s", 0),
            info.get("path"),
        )
        box = QMessageBox(self)
        box.setWindowTitle("DEMO SAVED")
        box.setText(text)
        open_button = box.addButton("OPEN FOLDER", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() == open_button:
            os.startfile(DIR_DEMOS)

    def _on_demo_failed(self, message: str) -> None:
        self._reset_record_ui()
        self.log.error("Recording failed %s", message)
        QMessageBox.warning(self, "Demo", message)

    def _reset_record_ui(self) -> None:
        self.worker.set_sink(None)
        self.video.set_banner("")
        self.timer_label.setText("")
        self.record_button.setEnabled(True)
        self.record_button.setText("● RECORD 15s DEMO")

    def _save_measurement(self) -> None:
        if self._result is None:
            QMessageBox.information(self, "Save", "There is no frame to save.")
            return
        settings = self.store.snapshot()
        saved = save_measurement(self._result, settings, settings.part_name)
        self._append_history(self._result, reason="save")
        self.log.info("Measurement saved %s", saved["json"])
        self.statusBar().showMessage(f"Saved {saved['annotated'].name}")

    def _add_history_current(self) -> None:
        if self._result is None:
            return
        self._append_history(self._result, reason="manual")

    def _append_history(self, result, reason: str) -> None:
        settings = self.store.snapshot()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for obj in result.objects:
            if obj.width_mm is None or obj.partial:
                continue
            rows.append(
                HistoryRow(
                    timestamp=stamp,
                    part=settings.part_name,
                    object_id=obj.id,
                    width_mm=float(obj.width_mm),
                    height_mm=float(obj.height_mm),
                    angle_deg=float(obj.angle_deg or 0),
                    area_mm2=obj.area_mm2,
                    result=obj.result,
                    pixels_per_mm=result.calibration.pixels_per_mm,
                    calibration_mode=result.calibration.mode,
                )
            )
        if not rows:
            if reason == "manual":
                self.statusBar().showMessage("No calibrated object to add.")
            return
        self.history.extend(rows)
        self.history_panel.set_rows(self.history.rows, settings.units)
        if reason == "auto":
            self.log.info("Auto capture %s objects", len(rows))

    def _export_csv(self) -> None:
        if not self.history.rows:
            QMessageBox.information(self, "Export", "History is empty.")
            return
        stamp = datetime.now().strftime("%Y%m%d")
        path = DIR_EXPORTS / f"measurement_history_{stamp}.csv"
        export_history(path, self.history.rows)
        self.log.info("Export %s", path)
        self.statusBar().showMessage(f"Exported {path.name}")

    def _clear_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear History",
            "Delete every row in the measurement history?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.history.clear()
        self.history_panel.set_rows([], self.store.snapshot().units)
        self.log.info("History cleared")

    def _on_frame(self, result) -> None:
        self._result = result
        now = time.perf_counter()
        self._disp_times.append(now)
        self.video.set_frame(result.display_bgr)
        settings = self.store.snapshot()
        self.measure.show_result(result, settings)
        if result.calibration.pixels_per_mm:
            self._last_ppm = result.calibration.pixels_per_mm
        if not self._size_noted and result.raw_bgr is not None:
            self._size_noted = True
            height, width = result.raw_bgr.shape[:2]
            self.log.info("Frame size %sx%s", width, height)
            self.statusBar().showMessage(f"Frame {width}x{height}")
        self._log_frame_events(result)
        self._auto_capture(result, settings)
        if self._wizard is not None:
            self._wizard.set_result(result)
        if self._camera_dialog is not None:
            self._camera_dialog.consider(result.raw_bgr)
        ppm = "—" if not result.calibration.pixels_per_mm else f"{result.calibration.pixels_per_mm:.2f} px/mm"
        display_fps = _rate(self._disp_times)
        self.status_line.setText(
            f"CAM {result.camera_fps:.0f}    PROC {result.processing_fps:.0f}    "
            f"DISP {display_fps:.0f}    {result.calibration.message}    {ppm}    {result.stability}"
        )

    def _log_frame_events(self, result) -> None:
        valid = bool(result.calibration.valid)
        if valid != self._was_valid:
            if valid:
                self.log.info(
                    "Calibration completed mode=%s ppm=%s",
                    result.calibration.mode,
                    result.calibration.pixels_per_mm,
                )
            else:
                self.log.info("Calibration lost %s", result.calibration.message)
            self._was_valid = valid
        current_ids = {obj.id for obj in result.objects}
        for object_id in sorted(current_ids - self._seen_ids):
            self.log.info("Object detected #%s", object_id)
        self._seen_ids = current_ids
        for obj in result.objects:
            previous = self._result_state.get(obj.id)
            if obj.result in ("PASS", "FAIL") and obj.result != previous:
                self.log.info("Quality %s object #%s W=%.2f H=%.2f", obj.result, obj.id, obj.width_mm or 0, obj.height_mm or 0)
            self._result_state[obj.id] = obj.result

    def _auto_capture(self, result, settings) -> None:
        measurable = [obj for obj in result.objects if obj.width_mm is not None and not obj.partial]
        stable = bool(measurable) and result.stability == "STABLE" and result.calibration.valid
        if settings.auto_capture and stable:
            if self._stable_since is None:
                self._stable_since = time.perf_counter()
            elif time.perf_counter() - self._stable_since >= settings.auto_capture_seconds:
                signature = tuple((obj.id, round(obj.width_mm, 1), round(obj.height_mm, 1)) for obj in measurable)
                if signature != self._auto_signature:
                    self._append_history(result, reason="auto")
                    self._auto_signature = signature
        else:
            self._stable_since = None

    def _on_source_started(self, label: str) -> None:
        self._running = True
        self._paused = False
        self._seen_ids.clear()
        self._size_noted = False
        self.controls.set_running(True, False)
        self.freeze_button.setText("FREEZE MEASUREMENT")
        self.statusBar().showMessage(label)
        self.log.info("Source started %s", label)

    def _on_source_stopped(self) -> None:
        self._running = False
        self._paused = False
        self.controls.set_running(False, False)
        self.statusBar().showMessage("Stopped")

    def _on_source_error(self, message: str) -> None:
        self._running = False
        self.controls.set_running(False, False)
        self.log.error(message)
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "Source", message)

    def closeEvent(self, event) -> None:
        scan = getattr(self, "_scan", None)
        if scan is not None and scan.isRunning():
            scan.wait(3000)
        if self._recorder is not None and self._recorder.isRunning():
            self._recorder.cancel()
            self._recorder.wait(1500)
        geometry = bytes(self.saveGeometry().toHex()).decode("ascii")
        self.store.update(window_geometry=geometry)
        self.worker.stop_thread()
        self.worker.wait(2000)
        self.log.info("Shutdown")
        event.accept()


def _rate(times: deque[float]) -> float:
    if len(times) < 2:
        return 0.0
    span = times[-1] - times[0]
    if span <= 0:
        return 0.0
    return (len(times) - 1) / span
