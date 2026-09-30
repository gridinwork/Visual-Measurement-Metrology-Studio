"""Saved measurements."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.theme import FAIL_HEX, PASS_HEX
from measurement.units import length_to_unit


class HistoryPanel(QWidget):
    export_clicked = Signal()
    clear_clicked = Signal()
    add_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["TIME", "PART", "WIDTH", "HEIGHT", "ANGLE", "RESULT"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        add_button = QPushButton("Add Current")
        export_button = QPushButton("Export CSV")
        clear_button = QPushButton("Clear History")
        add_button.clicked.connect(self.add_clicked.emit)
        export_button.clicked.connect(self.export_clicked.emit)
        clear_button.clicked.connect(self.clear_clicked.emit)
        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(export_button)
        buttons.addWidget(clear_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

    def set_rows(self, rows, unit: str) -> None:
        self.table.setHorizontalHeaderLabels(
            ["TIME", "PART", f"WIDTH ({unit})", f"HEIGHT ({unit})", "ANGLE", "RESULT"]
        )
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            clock = row.timestamp.split(" ")[-1]
            values = [
                clock,
                row.part or "—",
                f"{length_to_unit(row.width_mm, unit):.2f}",
                f"{length_to_unit(row.height_mm, unit):.2f}",
                f"{row.angle_deg:.1f}°",
                row.result,
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if column == 5 and row.result == "PASS":
                    item.setForeground(QColor(PASS_HEX))
                elif column == 5 and row.result == "FAIL":
                    item.setForeground(QColor(FAIL_HEX))
                self.table.setItem(index, column, item)
        if rows:
            self.table.scrollToBottom()
