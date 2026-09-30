"""Chessboard and ChArUco camera calibration, stored apart from the pixel scale."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from app.paths import DIR_CALIBRATION, ensure_dirs
from calibration.aruco_calibration import dictionary_by_name


class CameraCalibrator:
    def __init__(self) -> None:
        self.object_points: list[np.ndarray] = []
        self.image_points: list[np.ndarray] = []
        self.image_size: tuple[int, int] | None = None
        self.matrix: np.ndarray | None = None
        self.dist: np.ndarray | None = None
        self.rms: float | None = None
        self.path: Path | None = None
        self.loaded_resolution: tuple[int, int] | None = None

    def reset_samples(self) -> None:
        self.object_points.clear()
        self.image_points.clear()
        self.image_size = None

    def sample_count(self) -> int:
        return len(self.object_points)

    def add_chessboard(self, frame_bgr, corners_x: int, corners_y: int, square_mm: float) -> bool:
        gray = _gray(frame_bgr)
        found, corners = _find_chessboard(gray, (int(corners_x), int(corners_y)))
        if not found or corners is None:
            return False
        if not hasattr(cv2, "findChessboardCornersSB"):
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objp = np.zeros((corners_x * corners_y, 3), np.float32)
        objp[:, :2] = np.mgrid[0:corners_x, 0:corners_y].T.reshape(-1, 2)
        objp *= float(square_mm)
        self.object_points.append(objp)
        self.image_points.append(corners.reshape(-1, 2).astype(np.float32))
        self.image_size = (gray.shape[1], gray.shape[0])
        return True

    def preview_chessboard(self, frame_bgr, corners_x: int, corners_y: int) -> np.ndarray | None:
        gray = _gray(frame_bgr)
        found, corners = _find_chessboard(gray, (int(corners_x), int(corners_y)))
        if not found:
            return None
        return corners

    def add_charuco(
        self,
        frame_bgr,
        squares_x: int,
        squares_y: int,
        square_mm: float,
        marker_mm: float,
        dictionary_name: str,
    ) -> bool:
        detected = self._charuco_points(frame_bgr, squares_x, squares_y, square_mm, marker_mm, dictionary_name)
        if detected is None:
            return False
        obj_points, img_points, image_size = detected
        if len(obj_points) < 6:
            return False
        self.object_points.append(obj_points)
        self.image_points.append(img_points)
        self.image_size = image_size
        return True

    def preview_charuco(self, frame_bgr, squares_x, squares_y, square_mm, marker_mm, dictionary_name) -> bool:
        return self._charuco_points(frame_bgr, squares_x, squares_y, square_mm, marker_mm, dictionary_name) is not None

    def calibrate(self) -> float:
        if len(self.object_points) < 4 or self.image_size is None:
            raise RuntimeError("Capture at least 4 pattern views before calibrating.")
        rms, matrix, dist, _rvecs, _tvecs = cv2.calibrateCamera(
            self.object_points,
            self.image_points,
            self.image_size,
            None,
            None,
        )
        self.rms = float(rms)
        self.matrix = matrix
        self.dist = dist
        self.loaded_resolution = self.image_size
        return self.rms

    def save(self, camera_index: int, pattern: str) -> Path:
        if self.matrix is None or self.dist is None or self.image_size is None:
            raise RuntimeError("Calibrate the camera before saving.")
        ensure_dirs()
        width, height = self.image_size
        path = DIR_CALIBRATION / f"camera{int(camera_index)}_{width}x{height}.json"
        payload = {
            "camera_index": int(camera_index),
            "resolution": [width, height],
            "camera_matrix": self.matrix.tolist(),
            "dist_coeffs": self.dist.reshape(-1).tolist(),
            "rms": self.rms,
            "pattern": pattern,
            "date": datetime.now().isoformat(timespec="seconds"),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.path = path
        return path

    def load_for(self, camera_index: int, width: int, height: int) -> bool:
        path = DIR_CALIBRATION / f"camera{int(camera_index)}_{int(width)}x{int(height)}.json"
        if not path.exists():
            self.matrix = None
            self.dist = None
            self.loaded_resolution = None
            self.path = None
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        self.matrix = np.array(data["camera_matrix"], dtype=np.float64)
        self.dist = np.array(data["dist_coeffs"], dtype=np.float64)
        resolution = data.get("resolution") or [width, height]
        self.loaded_resolution = (int(resolution[0]), int(resolution[1]))
        self.rms = data.get("rms")
        self.path = path
        return True

    def undistort(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        if self.matrix is None or self.dist is None or self.loaded_resolution is None:
            return None
        height, width = frame_bgr.shape[:2]
        if (width, height) != self.loaded_resolution:
            return None
        new_matrix, _roi = cv2.getOptimalNewCameraMatrix(
            self.matrix, self.dist, (width, height), 1, (width, height)
        )
        return cv2.undistort(frame_bgr, self.matrix, self.dist, None, new_matrix)

    def _charuco_points(self, frame_bgr, squares_x, squares_y, square_mm, marker_mm, dictionary_name):
        gray = _gray(frame_bgr)
        dictionary = dictionary_by_name(dictionary_name)
        board = cv2.aruco.CharucoBoard(
            (int(squares_x), int(squares_y)),
            float(square_mm),
            float(marker_mm),
            dictionary,
        )
        if hasattr(cv2.aruco, "CharucoDetector"):
            detector = cv2.aruco.CharucoDetector(board)
            detected = detector.detectBoard(gray)
            charuco_corners = detected[0]
            charuco_ids = detected[1]
        else:
            marker_corners, marker_ids, _rejected = cv2.aruco.detectMarkers(gray, dictionary)
            if marker_ids is None:
                return None
            _count, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                marker_corners, marker_ids, gray, board
            )
        if charuco_corners is None or charuco_ids is None or len(charuco_ids) < 6:
            return None
        if hasattr(board, "matchImagePoints"):
            obj_points, img_points = board.matchImagePoints(charuco_corners, charuco_ids)
            obj_points = np.asarray(obj_points, dtype=np.float32).reshape(-1, 3)
            img_points = np.asarray(img_points, dtype=np.float32).reshape(-1, 2)
        else:
            return None
        if len(obj_points) < 6:
            return None
        return obj_points, img_points, (gray.shape[1], gray.shape[0])


def _gray(frame_bgr: np.ndarray) -> np.ndarray:
    if frame_bgr.ndim == 2:
        return frame_bgr
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)


def _find_chessboard(gray: np.ndarray, pattern: tuple[int, int]):
    if hasattr(cv2, "findChessboardCornersSB"):
        found, corners = cv2.findChessboardCornersSB(gray, pattern, cv2.CALIB_CB_EXHAUSTIVE)
        if found:
            return True, corners
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
    return cv2.findChessboardCorners(gray, pattern, flags)
