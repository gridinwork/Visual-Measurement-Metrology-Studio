"""Colors shared by the Qt theme and the OpenCV overlay.

Pass and fail are theme roles. Measurement code stores the result name and
the renderer maps that name to these colors.
"""

PASS_HEX = "#3dd68c"
FAIL_HEX = "#ff6b6b"
WARN_HEX = "#f5a524"
ACCENT_HEX = "#4da3ff"
TEXT_HEX = "#e8eaed"
MUTED_HEX = "#9aa0a6"
BG_HEX = "#1a1d23"
PANEL_HEX = "#232830"


def _bgr(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    red = int(hex_color[0:2], 16)
    green = int(hex_color[2:4], 16)
    blue = int(hex_color[4:6], 16)
    return blue, green, red


BGR = {
    "pass": _bgr(PASS_HEX),
    "fail": _bgr(FAIL_HEX),
    "warn": _bgr(WARN_HEX),
    "reference": _bgr(ACCENT_HEX),
    "object": (230, 216, 170),
    "corner": (80, 80, 255),
    "center": (220, 220, 120),
    "text": _bgr(TEXT_HEX),
    "roi": _bgr(WARN_HEX),
    "manual": (255, 180, 80),
}


STYLESHEET = f"""
* {{
    font-family: "Segoe UI";
    font-size: 13px;
    color: {TEXT_HEX};
}}
QMainWindow, QDialog, QWizard {{
    background: {BG_HEX};
}}
QWidget#central {{
    background: {BG_HEX};
}}
QFrame#panel, QScrollArea, QTabWidget::pane {{
    background: {PANEL_HEX};
    border: 1px solid #3c424d;
    border-radius: 8px;
}}
QTabBar::tab {{
    background: #1c2129;
    color: {MUTED_HEX};
    padding: 8px 14px;
    border: 1px solid #3c424d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {PANEL_HEX};
    color: {TEXT_HEX};
}}
QGroupBox {{
    background: #1e232c;
    border: 1px solid #3c424d;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #9ecbff;
}}
QLabel#muted {{
    color: {MUTED_HEX};
}}
QLabel#value {{
    font-size: 22px;
    font-weight: 650;
}}
QLabel#statusGood {{
    color: {PASS_HEX};
    font-weight: 700;
}}
QLabel#statusBad {{
    color: {FAIL_HEX};
    font-weight: 700;
}}
QLabel#statusWarn {{
    color: {WARN_HEX};
    font-weight: 700;
}}
QPushButton {{
    background: #2c3440;
    border: 1px solid #4a5564;
    border-radius: 6px;
    padding: 7px 12px;
}}
QPushButton:hover {{
    background: #384354;
}}
QPushButton:pressed {{
    background: #243044;
}}
QPushButton:disabled {{
    color: #6d7480;
    background: #22262e;
}}
QPushButton#primary {{
    background: #1d4e89;
    border: 1px solid {ACCENT_HEX};
    font-weight: 650;
}}
QPushButton#record {{
    background: #8d2e2e;
    border: 1px solid {FAIL_HEX};
    font-weight: 750;
    font-size: 14px;
    padding: 10px 16px;
}}
QPushButton#record[recording="true"] {{
    background: #5a1c1c;
}}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: #14181e;
    border: 1px solid #3c424d;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: #232830;
    selection-background-color: #1d4e89;
    border: 1px solid #3c424d;
}}
QTableWidget {{
    background: #14181e;
    gridline-color: #2c3440;
    border: none;
    selection-background-color: #1d4e89;
    selection-color: {TEXT_HEX};
}}
QHeaderView::section {{
    background: #2a3140;
    color: {MUTED_HEX};
    padding: 6px;
    border: none;
    font-weight: 600;
}}
QStatusBar {{
    background: #12141a;
    color: {TEXT_HEX};
}}
QProgressBar {{
    border: 1px solid #3c424d;
    border-radius: 4px;
    background: #14181e;
    text-align: center;
    min-height: 16px;
}}
QProgressBar::chunk {{
    background: #c44747;
    border-radius: 3px;
}}
QCheckBox {{
    spacing: 6px;
}}
QMenuBar {{
    background: {BG_HEX};
}}
QMenuBar::item:selected {{
    background: #2c3440;
}}
QMenu {{
    background: {PANEL_HEX};
    border: 1px solid #3c424d;
}}
QMenu::item:selected {{
    background: #1d4e89;
}}
QScrollBar:vertical {{
    background: #14181e;
    width: 12px;
}}
QScrollBar::handle:vertical {{
    background: #3c424d;
    border-radius: 4px;
    min-height: 24px;
}}
QSplitter::handle {{
    background: #12141a;
}}
"""


def apply_theme(app) -> None:
    app.setStyleSheet(STYLESHEET)
