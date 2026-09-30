"""Measurement viewport. Frames are drawn inside the window, not with cv2.imshow."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class VideoWidget(QWidget):
    clicked = Signal(float, float)
    point_clicked = Signal(float, float)
    roi_finished = Signal(float, float, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._image_size = (0, 0)
        self._mode = "select"
        self._banner = ""
        self._drag_start: tuple[float, float] | None = None
        self._drag_current: tuple[float, float] | None = None
        self._target = QRect()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._drag_start = None
        self._drag_current = None
        self.update()

    def set_banner(self, text: str) -> None:
        self._banner = text
        self.update()

    def set_frame(self, bgr: np.ndarray) -> None:
        rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(image)
        self._image_size = (width, height)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0e1116"))
        self._target = self._layout_rect()
        if self._pixmap is not None and not self._target.isNull():
            painter.drawPixmap(self._target, self._pixmap)
        if self._drag_start and self._drag_current:
            painter.setPen(QPen(QColor("#f5a524"), 2))
            rect = QRectF(QPointF(*self._to_widget(*self._drag_start)), QPointF(*self._to_widget(*self._drag_current))).normalized()
            painter.drawRect(rect)
        if self._banner:
            painter.setPen(QColor("#ff6b6b"))
            font = QFont("Segoe UI", 72, QFont.Bold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, self._banner)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        mapped = self._map(event.position())
        if mapped is None:
            return
        if self._mode == "roi":
            self._drag_start = mapped
            self._drag_current = mapped
            self.update()
        elif self._mode == "points":
            self.point_clicked.emit(mapped[0], mapped[1])
        else:
            self.clicked.emit(mapped[0], mapped[1])

    def mouseMoveEvent(self, event) -> None:
        if self._mode != "roi" or self._drag_start is None:
            return
        mapped = self._map(event.position())
        if mapped is None:
            return
        self._drag_current = mapped
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._mode != "roi" or self._drag_start is None or self._drag_current is None:
            self._drag_start = None
            return
        x1, y1 = self._drag_start
        x2, y2 = self._drag_current
        self._drag_start = None
        self._drag_current = None
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        if width < 12 or height < 12 or self._image_size[0] <= 0:
            self.update()
            return
        image_w, image_h = self._image_size
        self.roi_finished.emit(
            min(x1, x2) / image_w,
            min(y1, y2) / image_h,
            width / image_w,
            height / image_h,
        )
        self.update()

    def _layout_rect(self) -> QRect:
        if self._pixmap is None or self._image_size[0] <= 0:
            return QRect()
        image_w, image_h = self._image_size
        scale = min(self.width() / image_w, self.height() / image_h)
        draw_w = max(1, int(image_w * scale))
        draw_h = max(1, int(image_h * scale))
        origin_x = (self.width() - draw_w) // 2
        origin_y = (self.height() - draw_h) // 2
        return QRect(origin_x, origin_y, draw_w, draw_h)

    def _map(self, position) -> tuple[float, float] | None:
        target = self._layout_rect()
        if target.isNull() or target.width() <= 0:
            return None
        x = position.x()
        y = position.y()
        if not target.contains(int(x), int(y)):
            return None
        image_w, image_h = self._image_size
        return (
            (x - target.x()) / target.width() * image_w,
            (y - target.y()) / target.height() * image_h,
        )

    def _to_widget(self, image_x: float, image_y: float) -> tuple[float, float]:
        target = self._target if not self._target.isNull() else self._layout_rect()
        if target.isNull() or self._image_size[0] <= 0:
            return 0.0, 0.0
        return (
            target.x() + image_x / self._image_size[0] * target.width(),
            target.y() + image_y / self._image_size[1] * target.height(),
        )
