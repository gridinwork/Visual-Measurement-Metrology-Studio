"""Lightweight centroid / IoU tracker so object numbers stay put between frames."""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Track:
    id: int
    center: tuple[float, float]
    rect: tuple
    width_mm: float | None
    height_mm: float | None
    angle_deg: float | None
    last_seen: float


@dataclass
class TrackMatch:
    candidate_index: int
    track_id: int
    previous_width_mm: float | None
    previous_height_mm: float | None


class ObjectTracker:
    def __init__(self) -> None:
        self.tracks: list[Track] = []
        self._next_id = 1

    def reset(self) -> None:
        self.tracks.clear()
        self._next_id = 1

    def update(self, detections: list[dict], now: float, timeout_s: float) -> list[TrackMatch]:
        self.tracks = [track for track in self.tracks if now - track.last_seen <= timeout_s]
        if not detections:
            return []

        pairs: list[tuple[float, int, int]] = []
        for det_index, detection in enumerate(detections):
            for track_index, track in enumerate(self.tracks):
                score = _match_score(detection, track)
                if score is not None:
                    pairs.append((score, det_index, track_index))
        pairs.sort(key=lambda item: item[0], reverse=True)

        used_det: set[int] = set()
        used_track: set[int] = set()
        matches: list[TrackMatch] = []
        for _score, det_index, track_index in pairs:
            if det_index in used_det or track_index in used_track:
                continue
            used_det.add(det_index)
            used_track.add(track_index)
            track = self.tracks[track_index]
            detection = detections[det_index]
            track.center = detection["center"]
            track.rect = detection["rect"]
            track.last_seen = now
            matches.append(
                TrackMatch(
                    candidate_index=det_index,
                    track_id=track.id,
                    previous_width_mm=track.width_mm,
                    previous_height_mm=track.height_mm,
                )
            )

        for det_index, detection in enumerate(detections):
            if det_index in used_det:
                continue
            track = Track(
                id=self._next_id,
                center=detection["center"],
                rect=detection["rect"],
                width_mm=None,
                height_mm=None,
                angle_deg=None,
                last_seen=now,
            )
            self._next_id += 1
            self.tracks.append(track)
            matches.append(
                TrackMatch(
                    candidate_index=det_index,
                    track_id=track.id,
                    previous_width_mm=None,
                    previous_height_mm=None,
                )
            )
        matches.sort(key=lambda item: item.track_id)
        return matches

    def remember(self, track_id: int, width_mm: float | None, height_mm: float | None, angle_deg: float | None) -> None:
        for track in self.tracks:
            if track.id == track_id:
                track.width_mm = width_mm
                track.height_mm = height_mm
                track.angle_deg = angle_deg
                return


def _match_score(detection: dict, track: Track) -> float | None:
    iou = _rotated_iou(detection["rect"], track.rect)
    if iou >= 0.15:
        return 1.0 + iou
    distance = math.hypot(detection["center"][0] - track.center[0], detection["center"][1] - track.center[1])
    limit = max(48.0, 0.45 * max(float(detection["rect"][1][0]), float(detection["rect"][1][1]), 1.0))
    if distance <= limit:
        return 0.5 * (1.0 - distance / limit)
    return None


def _rotated_iou(first, second) -> float:
    try:
        retval, intersection = cv2.rotatedRectangleIntersection(first, second)
    except cv2.error:
        return 0.0
    if retval == cv2.INTERSECT_NONE or intersection is None:
        return 0.0
    inter_area = float(cv2.contourArea(intersection))
    area_a = abs(float(first[1][0]) * float(first[1][1]))
    area_b = abs(float(second[1][0]) * float(second[1][1]))
    union = area_a + area_b - inter_area
    if union <= 1.0:
        return 0.0
    return float(np.clip(inter_area / union, 0.0, 1.0))
