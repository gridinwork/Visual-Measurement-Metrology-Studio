"""Shared data used by the measurement engine and the desktop interface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


def parse_resolution(text: str) -> tuple[int, int]:
    parts = str(text).lower().replace(" ", "").split("x")
    if len(parts) != 2:
        return 1280, 720
    return int(parts[0]), int(parts[1])


@dataclass
class Settings:
    camera_index: int = 0
    resolution: str = "1280x720"
    source: str = "webcam"
    last_video: str = ""
    last_image: str = ""
    units: str = "mm"
    calibration_mode: str = "reference"
    reference_width_mm: float = 50.0
    marker_size_mm: float = 50.0
    aruco_dictionary: str = "DICT_4X4_50"
    manual_distance_mm: float = 100.0
    manual_points: list = field(default_factory=list)
    manual_frame_wh: list = field(default_factory=list)
    fixed_profile: str = ""
    fixed_pixels_per_mm: float = 0.0
    lens_correction: bool = False
    detection_method: str = "AUTO"
    canny_low: int = 50
    canny_high: int = 100
    blur: int = 7
    morph_kernel: int = 3
    min_area: int = 800
    max_area: int = 0
    threshold: int = 0
    ignore_border: bool = True
    roi_enabled: bool = False
    roi: list = field(default_factory=list)
    smoothing: str = "MEDIUM"
    stability_threshold_mm: float = 0.40
    stability_samples: int = 8
    auto_capture: bool = False
    auto_capture_seconds: float = 1.0
    track_timeout_s: float = 1.0
    qc_enabled: bool = False
    part_name: str = ""
    nominal_width_mm: float = 82.0
    nominal_height_mm: float = 46.5
    width_upper_mm: float = 0.5
    width_lower_mm: float = 0.5
    height_upper_mm: float = 0.5
    height_lower_mm: float = 0.5
    tolerance_symmetric: bool = True
    record_resolution: str = "1920x1080"
    record_fps: int = 30
    debug: bool = False
    show_contours: bool = True
    show_boxes: bool = True
    show_dimensions: bool = True
    show_angle: bool = True
    show_id: bool = True
    show_center: bool = True
    show_fps: bool = True
    show_calibration: bool = True
    presentation: bool = False
    selected_object_id: int = -1
    window_geometry: str = ""
    revision: int = 0
    record_badge: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("revision", None)
        data.pop("record_badge", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        known = {item.name for item in fields(cls)}
        clean = {key: value for key, value in data.items() if key in known}
        settings = cls(**clean)
        settings.sanitize()
        return settings

    def sanitize(self) -> None:
        if self.blur < 1:
            self.blur = 1
        if self.blur % 2 == 0:
            self.blur += 1
        if self.morph_kernel < 1:
            self.morph_kernel = 1
        if self.morph_kernel % 2 == 0:
            self.morph_kernel += 1
        if self.canny_high <= self.canny_low:
            self.canny_high = min(255, self.canny_low + 50)
        self.min_area = max(1, int(self.min_area))
        self.stability_samples = max(3, int(self.stability_samples))
        self.track_timeout_s = max(0.2, float(self.track_timeout_s))
        self.record_fps = int(self.record_fps) if self.record_fps in (24, 30, 60) else 30
        if self.units not in ("mm", "cm", "inch"):
            self.units = "mm"
        if self.calibration_mode not in ("reference", "aruco", "manual", "fixed"):
            self.calibration_mode = "reference"
        if self.detection_method not in ("AUTO", "CANNY", "THRESHOLD", "ADAPTIVE"):
            self.detection_method = "AUTO"
        if self.smoothing not in ("OFF", "LOW", "MEDIUM", "HIGH"):
            self.smoothing = "MEDIUM"
        if self.resolution not in ("640x480", "1280x720", "1920x1080"):
            self.resolution = "1280x720"
        if self.record_resolution not in ("1280x720", "1920x1080"):
            self.record_resolution = "1920x1080"


DETECTION_DEFAULTS = {
    "detection_method": "AUTO",
    "canny_low": 50,
    "canny_high": 100,
    "blur": 7,
    "morph_kernel": 3,
    "min_area": 800,
    "max_area": 0,
    "threshold": 0,
    "ignore_border": True,
}


@dataclass
class MeasuredObject:
    id: int
    width_mm: float | None
    height_mm: float | None
    raw_width_mm: float | None
    raw_height_mm: float | None
    width_px: float
    height_px: float
    angle_deg: float | None
    area_px: float
    area_mm2: float | None
    perimeter_px: float
    perimeter_mm: float | None
    center_px: tuple[float, float]
    center_mm: tuple[float, float] | None
    box: list
    width_edge: list
    height_edge: list
    partial: bool
    result: str
    width_pass: bool | None
    height_pass: bool | None
    stable: bool
    is_reference: bool = False
    contour: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "width_mm": _round(self.width_mm, 3),
            "height_mm": _round(self.height_mm, 3),
            "raw_width_mm": _round(self.raw_width_mm, 3),
            "raw_height_mm": _round(self.raw_height_mm, 3),
            "width_px": round(self.width_px, 2),
            "height_px": round(self.height_px, 2),
            "angle_deg": _round(self.angle_deg, 2),
            "area_px": round(self.area_px, 1),
            "area_mm2": _round(self.area_mm2, 2),
            "perimeter_px": round(self.perimeter_px, 2),
            "perimeter_mm": _round(self.perimeter_mm, 2),
            "center_px": [round(self.center_px[0], 1), round(self.center_px[1], 1)],
            "center_mm": None
            if self.center_mm is None
            else [round(self.center_mm[0], 2), round(self.center_mm[1], 2)],
            "partial": self.partial,
            "result": self.result,
            "stable": self.stable,
            "is_reference": self.is_reference,
        }


@dataclass
class CalibrationInfo:
    valid: bool = False
    paused: bool = False
    mode: str = "reference"
    pixels_per_mm: float | None = None
    message: str = "REFERENCE NOT FOUND"
    detail: str = ""
    perspective_warning: bool = False
    perspective_message: str = ""
    aruco_id: int | None = None
    marker_size_mm: float | None = None
    reference_width_mm: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "paused": self.paused,
            "mode": self.mode,
            "pixels_per_mm": _round(self.pixels_per_mm, 4),
            "message": self.message,
            "detail": self.detail,
            "perspective_warning": self.perspective_warning,
            "perspective_message": self.perspective_message,
            "aruco_id": self.aruco_id,
            "marker_size_mm": self.marker_size_mm,
            "reference_width_mm": self.reference_width_mm,
        }


@dataclass
class FrameResult:
    raw_bgr: Any
    display_bgr: Any
    objects: list[MeasuredObject]
    calibration: CalibrationInfo
    timings_ms: dict
    camera_fps: float
    processing_fps: float
    stability: str
    warnings: list[str]
    frame_id: int
    contour_count: int
    accepted_count: int
    method_used: str
    reference: MeasuredObject | None = None
    marker_label: str = ""


@dataclass
class HistoryRow:
    timestamp: str
    part: str
    object_id: int
    width_mm: float
    height_mm: float
    angle_deg: float
    area_mm2: float | None
    result: str
    pixels_per_mm: float | None
    calibration_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryRow":
        known = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


def _round(value: float | None, digits: int):
    if value is None:
        return None
    return round(float(value), digits)
