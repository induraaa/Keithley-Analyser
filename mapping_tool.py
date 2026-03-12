"""
Wafer Map Viewer — KDF File Analyser
Reads Keithley ACS KDF V1.2 files and displays an interactive wafer map.

Requirements:
    pip install PyQt5 matplotlib numpy

Usage:
    python wafer_mapper.py
    python wafer_mapper.py path/to/file.kdf
"""

import sys
import os
import re
import math
import copy
from collections import defaultdict

import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QPushButton, QFileDialog, QTreeWidget,
    QTreeWidgetItem, QGroupBox, QLineEdit, QFormLayout, QScrollArea,
    QFrame, QStatusBar, QComboBox, QCheckBox, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QToolBar, QAction,
    QSizePolicy, QDialog, QDialogButtonBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt5.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QFontMetrics,
    QLinearGradient, QPainterPath, QPixmap, QIcon
)

# ─────────────────────────────────────────────
#  KDF PARSER
# ─────────────────────────────────────────────

def parse_kdf(filepath):
    """
    Parse a KDF V1.2 file.

    Returns:
        header  : dict of header key->value
        sites   : list of dicts, each with:
                    'name'     : str  (e.g. 'Site_p0p0')
                    'x'        : int  wafer X coordinate
                    'y'        : int  wafer Y coordinate
                    'subsites' : dict  subsite_num -> {param@test -> value}
        tests   : list of unique test names found (e.g. 'CV_0V', 'BVr_250uA')
        params  : list of unique param names (e.g. 'Cp', 'Vbr_250uA')
        measurements : list of 'param@test' keys available
    """
    header = {}
    sites = []
    measurements_set = set()
    tests_set = set()

    with open(filepath, 'r', errors='replace') as f:
        content = f.read()

    lines = [l.strip() for l in content.splitlines()]

    # Parse header (before <EOH>)
    in_header = True
    i = 0
    while i < len(lines):
        line = lines[i]
        if line == '<EOH>':
            in_header = False
            i += 1
            break
        if ',' in line:
            key, _, val = line.partition(',')
            header[key.strip()] = val.strip()
        i += 1

    # Skip wafer/lot line (e.g. "Tails_W24_Cj,,1,1")
    if i < len(lines):
        i += 1

    # Parse sites
    current_site = None
    current_subsite = None

    while i < len(lines):
        line = lines[i]
        i += 1

        if not line:
            continue

        if line == '<EOS>':
            if current_site is not None:
                sites.append(current_site)
            current_site = None
            current_subsite = None
            continue

        # Site line: Site_p0p0,0,0,0
        if line.startswith('Site_'):
            if current_site is not None:
                sites.append(current_site)
            parts = line.split(',')
            name = parts[0]
            try:
                x = int(parts[1]) if len(parts) > 1 else 0
                y = int(parts[2]) if len(parts) > 2 else 0
            except ValueError:
                x, y = 0, 0
            current_site = {'name': name, 'x': x, 'y': y, 'subsites': {}}
            current_subsite = None
            continue

        if current_site is None:
            continue

        # Data line: param@test@subsite#N,value
        if '@' in line and ',' in line:
            key_part, _, val_str = line.partition(',')
            parts = key_part.split('@')
            if len(parts) >= 3:
                param = parts[0]
                test  = parts[1]
                sub_part = parts[2]  # e.g. subsite#3
                try:
                    sub_num = int(sub_part.split('#')[1])
                except (IndexError, ValueError):
                    sub_num = 1

                try:
                    value = float(val_str)
                except ValueError:
                    value = None

                if sub_num not in current_site['subsites']:
                    current_site['subsites'][sub_num] = {}

                mkey = f"{param}@{test}"
                current_site['subsites'][sub_num][mkey] = value
                measurements_set.add(mkey)
                tests_set.add(test)

    # Catch last site if no trailing <EOS>
    if current_site is not None:
        sites.append(current_site)

    # Build ordered lists
    tests = sorted(tests_set)
    measurements = sorted(measurements_set)

    return header, sites, tests, measurements


def get_site_value(site, mkey, subsite=None):
    """
    Get the mean value of mkey across all subsites (or a specific one).
    Returns None if no valid data.
    """
    values = []
    for sub_num, data in site['subsites'].items():
        if subsite is not None and sub_num != subsite:
            continue
        v = data.get(mkey)
        if v is not None and math.isfinite(v):
            values.append(v)
    if not values:
        return None
    return float(np.mean(values))


# ─────────────────────────────────────────────
#  WAFER CANVAS WIDGET
# ─────────────────────────────────────────────

PASS_COLOR   = QColor('#2ecc71')
FAIL_COLOR   = QColor('#e74c3c')
NO_DATA_CLR  = QColor('#8e44ad').lighter(130)
WAFER_BG     = QColor('#1a1a2e')
WAFER_EDGE   = QColor('#4fc3f7')
GRID_CLR     = QColor('#2c3e50')
TEXT_CLR     = QColor('#ecf0f1')
SELECTED_CLR = QColor('#f39c12')


class WaferCanvas(QWidget):
    """Custom widget that draws the wafer map."""

    siteClicked = pyqtSignal(dict)   # emits full site dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sites = []
        self.values = {}        # site_name -> float | None
        self.low_limit  = None
        self.high_limit = None
        self.selected_site = None
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._hover_site = None
        self._site_rects = {}   # site_name -> QRectF (screen coords)

        # unit label for display
        self.unit = ''
        self.mkey = ''

    def load(self, sites, values, low_limit, high_limit, unit='', mkey=''):
        self.sites = sites
        self.values = values
        self.low_limit = low_limit
        self.high_limit = high_limit
        self.unit = unit
        self.mkey = mkey
        self.selected_site = None
        self._hover_site = None
        self.update()

    def _grid_bounds(self):
        if not self.sites:
            return -1, 1, -1, 1
        xs = [s['x'] for s in self.sites]
        ys = [s['y'] for s in self.sites]
        return min(xs), max(xs), min(ys), max(ys)

    def _transform(self, xmin, xmax, ymin, ymax, w, h):
        """Return (origin_x, origin_y, cell_size) for painting."""
        cols = xmax - xmin + 1
        rows = ymax - ymin + 1
        padding = 60
        cell_w = (w - 2 * padding) / max(cols, 1)
        cell_h = (h - 2 * padding) / max(rows, 1)
        cell = min(cell_w, cell_h)
        ox = (w - cell * cols) / 2
        oy = (h - cell * rows) / 2
        return ox, oy, cell

    def _site_color(self, site_name):
        v = self.values.get(site_name)
        if v is None:
            return NO_DATA_CLR
        lo = self.low_limit
        hi = self.high_limit
        passed = True
        if lo is not None and v < lo:
            passed = False
        if hi is not None and v > hi:
            passed = False
        return PASS_COLOR if passed else FAIL_COLOR

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, WAFER_BG)

        if not self.sites:
            painter.setPen(TEXT_CLR)
            painter.setFont(QFont('Consolas', 14))
            painter.drawText(self.rect(), Qt.AlignCenter, 'Load a KDF file to begin')
            return

        xmin, xmax, ymin, ymax = self._grid_bounds()
        ox, oy, cell = self._transform(xmin, xmax, ymin, ymax, w, h)

        # Draw wafer circle
        cols = xmax - xmin + 1
        rows = ymax - ymin + 1
        cx = ox + cell * cols / 2
        cy = oy + cell * rows / 2
        radius = min(cell * cols, cell * rows) / 2 + cell * 0.6
        painter.setPen(QPen(WAFER_EDGE, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Draw flat (notch at bottom)
        notch_y = cy + radius - 4
        painter.setPen(QPen(WAFER_EDGE, 4))
        painter.drawLine(int(cx - radius * 0.25), int(notch_y),
                         int(cx + radius * 0.25), int(notch_y))

        # Draw sites
        self._site_rects = {}
        font_size = max(5, int(cell * 0.13))
        painter.setFont(QFont('Consolas', font_size))

        for site in self.sites:
            sx = site['x']
            sy = site['y']
            # Flip Y so +Y is up
            px = ox + (sx - xmin) * cell
            py = oy + (ymax - sy) * cell

            rect = QRectF(px + 1, py + 1, cell - 2, cell - 2)
            self._site_rects[site['name']] = rect

            color = self._site_color(site['name'])

            # Highlight selected
            if self.selected_site and site['name'] == self.selected_site['name']:
                painter.setPen(QPen(SELECTED_CLR, 2))
                painter.setBrush(QBrush(color.lighter(140)))
            elif self._hover_site and site['name'] == self._hover_site['name']:
                painter.setPen(QPen(Qt.white, 1))
                painter.setBrush(QBrush(color.lighter(120)))
            else:
                painter.setPen(QPen(GRID_CLR, 1))
                painter.setBrush(QBrush(color))

            painter.drawRoundedRect(rect, 3, 3)

            # Value label
            v = self.values.get(site['name'])
            if v is not None and cell > 30:
                painter.setPen(TEXT_CLR)
                val_str = self._fmt_value(v)
                painter.drawText(rect, Qt.AlignCenter, val_str)

            # Coord label if large enough
            if cell > 55:
                painter.setPen(QColor(255, 255, 255, 100))
                small_font = QFont('Consolas', max(4, font_size - 2))
                painter.setFont(small_font)
                coord_rect = QRectF(px + 2, py + 2, cell - 4, cell * 0.3)
                painter.drawText(coord_rect, Qt.AlignLeft | Qt.AlignTop,
                                 f'{sx},{sy}')
                painter.setFont(QFont('Consolas', font_size))

        # Legend
        self._draw_legend(painter, w, h)

        painter.end()

    def _fmt_value(self, v):
        """Format a measurement value with appropriate SI prefix."""
        if v is None:
            return 'N/A'
        av = abs(v)
        if av == 0:
            return '0'
        if av >= 1:
            return f'{v:.3g}'
        if av >= 1e-3:
            return f'{v*1e3:.3g}m'
        if av >= 1e-6:
            return f'{v*1e6:.3g}µ'
        if av >= 1e-9:
            return f'{v*1e9:.3g}n'
        if av >= 1e-12:
            return f'{v*1e12:.3g}p'
        return f'{v:.3e}'

    def _draw_legend(self, painter, w, h):
        lx, ly = 12, h - 80
        items = [
            (PASS_COLOR, 'Pass'),
            (FAIL_COLOR, 'Fail'),
            (NO_DATA_CLR, 'No Data'),
        ]
        if self.low_limit is None and self.high_limit is None:
            items = [(NO_DATA_CLR, 'No limits set — set limits to see pass/fail')]

        painter.setFont(QFont('Consolas', 9))
        for color, label in items:
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.white, 1))
            painter.drawRoundedRect(lx, ly, 14, 14, 2, 2)
            painter.setPen(TEXT_CLR)
            painter.drawText(lx + 18, ly + 11, label)
            ly += 22

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        self._hover_site = None
        for site in self.sites:
            r = self._site_rects.get(site['name'])
            if r and r.contains(pos):
                self._hover_site = site
                self.setCursor(Qt.PointingHandCursor)
                break
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = QPointF(event.pos())
            for site in self.sites:
                r = self._site_rects.get(site['name'])
                if r and r.contains(pos):
                    self.selected_site = site
                    self.siteClicked.emit(site)
                    self.update()
                    return

    def leaveEvent(self, event):
        self._hover_site = None
        self.update()


# ─────────────────────────────────────────────
#  LIMITS DIALOG
# ─────────────────────────────────────────────

class LimitsDialog(QDialog):
    def __init__(self, mkey, low=None, high=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Set Limits — {mkey}')
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.low_check  = QCheckBox('Enable Low Limit')
        self.high_check = QCheckBox('Enable High Limit')
        self.low_spin   = QDoubleSpinBox()
        self.high_spin  = QDoubleSpinBox()

        for sp in (self.low_spin, self.high_spin):
            sp.setDecimals(6)
            sp.setRange(-1e18, 1e18)
            sp.setSingleStep(0.001)

        if low is not None:
            self.low_check.setChecked(True)
            self.low_spin.setValue(low)
        if high is not None:
            self.high_check.setChecked(True)
            self.high_spin.setValue(high)

        self.low_check.toggled.connect(self.low_spin.setEnabled)
        self.high_check.toggled.connect(self.high_spin.setEnabled)
        self.low_spin.setEnabled(self.low_check.isChecked())
        self.high_spin.setEnabled(self.high_check.isChecked())

        form.addRow(self.low_check, self.low_spin)
        form.addRow(self.high_check, self.high_spin)
        layout.addLayout(form)

        note = QLabel('<i>Enter raw SI values (e.g. 3.2e-13 for 320 fF)</i>')
        note.setStyleSheet('color: #aaa; font-size: 10px;')
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_limits(self):
        low  = self.low_spin.value()  if self.low_check.isChecked()  else None
        high = self.high_spin.value() if self.high_check.isChecked() else None
        return low, high


# ─────────────────────────────────────────────
#  STATISTICS PANEL
# ─────────────────────────────────────────────

class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Statistic', 'Value'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def update_stats(self, values_dict, low, high):
        vals = [v for v in values_dict.values() if v is not None and math.isfinite(v)]
        if not vals:
            self.table.setRowCount(0)
            return

        arr = np.array(vals)
        passed = sum(
            1 for v in arr
            if (low is None or v >= low) and (high is None or v <= high)
        )
        total = len(arr)
        yield_pct = passed / total * 100 if total > 0 else 0

        rows = [
            ('Count',    f'{total}'),
            ('Mean',     self._fmt(arr.mean())),
            ('Std Dev',  self._fmt(arr.std())),
            ('Min',      self._fmt(arr.min())),
            ('Max',      self._fmt(arr.max())),
            ('Median',   self._fmt(float(np.median(arr)))),
            ('3σ Range', f'{self._fmt(arr.mean()-3*arr.std())} → {self._fmt(arr.mean()+3*arr.std())}'),
            ('Pass',     f'{passed}'),
            ('Fail',     f'{total - passed}'),
            ('Yield',    f'{yield_pct:.1f}%'),
        ]

        self.table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(k))
            item = QTableWidgetItem(v)
            if k == 'Yield':
                color = '#2ecc71' if yield_pct >= 90 else '#e74c3c' if yield_pct < 70 else '#f39c12'
                item.setForeground(QColor(color))
                item.setFont(QFont('Consolas', 9, QFont.Bold))
            self.table.setItem(i, 1, item)

    def _fmt(self, v):
        av = abs(v)
        if av == 0:            return '0'
        if av >= 1:            return f'{v:.5g}'
        if av >= 1e-3:         return f'{v*1e3:.4g} m'
        if av >= 1e-6:         return f'{v*1e6:.4g} µ'
        if av >= 1e-9:         return f'{v*1e9:.4g} n'
        if av >= 1e-12:        return f'{v*1e12:.4g} p'
        return f'{v:.4e}'


# ─────────────────────────────────────────────
#  SITE DETAIL PANEL
# ─────────────────────────────────────────────

class SiteDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title = QLabel('Click a die to inspect')
        self.title.setStyleSheet('font-weight: bold; font-size: 12px; color: #f39c12;')
        layout.addWidget(self.title)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Measurement', 'Subsite', 'Value'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def show_site(self, site):
        self.title.setText(f'  Site {site["name"]}  |  X={site["x"]}, Y={site["y"]}')

        rows = []
        for sub_num in sorted(site['subsites'].keys()):
            data = site['subsites'][sub_num]
            for mkey, val in sorted(data.items()):
                rows.append((mkey, f'#{sub_num}', val))

        self.table.setRowCount(len(rows))
        for i, (mkey, sub, val) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(mkey))
            self.table.setItem(i, 1, QTableWidgetItem(sub))
            if val is None:
                self.table.setItem(i, 2, QTableWidgetItem('N/A'))
            else:
                self.table.setItem(i, 2, QTableWidgetItem(f'{val:.6g}'))


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #12121f;
    color: #ecf0f1;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}
QGroupBox {
    border: 1px solid #2c3e50;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 6px;
    color: #4fc3f7;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
}
QPushButton {
    background-color: #1e3a5f;
    border: 1px solid #4fc3f7;
    border-radius: 4px;
    padding: 5px 12px;
    color: #ecf0f1;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:pressed {
    background-color: #1a6491;
}
QPushButton#actionBtn {
    background-color: #1a5276;
    color: #4fc3f7;
    font-weight: bold;
}
QComboBox {
    background-color: #1e3a5f;
    border: 1px solid #2c3e50;
    border-radius: 3px;
    padding: 3px 6px;
    color: #ecf0f1;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #1a1a2e;
    selection-background-color: #2980b9;
}
QTreeWidget, QTableWidget {
    background-color: #1a1a2e;
    border: 1px solid #2c3e50;
    gridline-color: #2c3e50;
    alternate-background-color: #16213e;
}
QTreeWidget::item:selected, QTableWidget::item:selected {
    background-color: #2980b9;
}
QHeaderView::section {
    background-color: #1e3a5f;
    color: #4fc3f7;
    border: none;
    padding: 4px;
    font-weight: bold;
}
QLineEdit {
    background-color: #1e3a5f;
    border: 1px solid #2c3e50;
    border-radius: 3px;
    padding: 4px;
    color: #ecf0f1;
}
QTabWidget::pane {
    border: 1px solid #2c3e50;
    background-color: #12121f;
}
QTabBar::tab {
    background-color: #1e3a5f;
    color: #bdc3c7;
    padding: 6px 14px;
    border: 1px solid #2c3e50;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #2980b9;
    color: white;
}
QScrollBar:vertical {
    background: #1a1a2e;
    width: 8px;
}
QScrollBar::handle:vertical {
    background: #2c3e50;
    border-radius: 4px;
}
QSplitter::handle {
    background: #2c3e50;
}
QStatusBar {
    background-color: #0d0d1a;
    color: #4fc3f7;
    border-top: 1px solid #2c3e50;
}
QDoubleSpinBox {
    background-color: #1e3a5f;
    border: 1px solid #2c3e50;
    color: #ecf0f1;
    padding: 3px;
}
QCheckBox { color: #ecf0f1; spacing: 6px; }
QLabel { color: #ecf0f1; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Wafer Map Viewer — KDF Analyser')
        self.resize(1300, 850)
        self.setStyleSheet(DARK_STYLE)

        self._header   = {}
        self._sites    = []
        self._tests    = []
        self._mkeys    = []
        self._limits   = {}     # mkey -> (low, high)
        self._current_mkey = None
        self._filepath = None

        self._build_ui()
        self._update_ui_state()

    # ── Build UI ─────────────────────────────

    def _build_ui(self):
        # Toolbar
        tb = QToolBar('Main', self)
        tb.setIconSize(QSize(16, 16))
        tb.setMovable(False)
        self.addToolBar(tb)

        open_act = QAction('📂  Open KDF…', self)
        open_act.triggered.connect(self.open_file)
        tb.addAction(open_act)

        export_act = QAction('💾  Export Map…', self)
        export_act.triggered.connect(self.export_map)
        tb.addAction(export_act)

        tb.addSeparator()
        self.lbl_file = QLabel('  No file loaded')
        self.lbl_file.setStyleSheet('color: #4fc3f7;')
        tb.addWidget(self.lbl_file)

        # Central split layout
        central = QWidget()
        self.setCentralWidget(central)
        main_h = QHBoxLayout(central)
        main_h.setSpacing(6)
        main_h.setContentsMargins(6, 6, 6, 6)

        # ── Left panel ──
        left = QWidget()
        left.setFixedWidth(270)
        left_v = QVBoxLayout(left)
        left_v.setSpacing(6)
        left_v.setContentsMargins(0, 0, 0, 0)

        # File info
        info_box = QGroupBox('File Info')
        info_form = QFormLayout(info_box)
        self.lbl_lot  = QLabel('—')
        self.lbl_sys  = QLabel('—')
        self.lbl_stt  = QLabel('—')
        self.lbl_sites_count = QLabel('—')
        info_form.addRow('Lot:', self.lbl_lot)
        info_form.addRow('System:', self.lbl_sys)
        info_form.addRow('Start:', self.lbl_stt)
        info_form.addRow('Sites:', self.lbl_sites_count)
        left_v.addWidget(info_box)

        # Measurement selector
        meas_box = QGroupBox('Measurement')
        meas_v = QVBoxLayout(meas_box)
        self.mkey_combo = QComboBox()
        self.mkey_combo.currentTextChanged.connect(self._on_mkey_changed)
        meas_v.addWidget(self.mkey_combo)
        left_v.addWidget(meas_box)

        # Limits
        lim_box = QGroupBox('Pass / Fail Limits')
        lim_v = QVBoxLayout(lim_box)

        lim_row = QHBoxLayout()
        self.low_edit  = QLineEdit()
        self.low_edit.setPlaceholderText('Low limit')
        self.high_edit = QLineEdit()
        self.high_edit.setPlaceholderText('High limit')
        lim_row.addWidget(QLabel('Low:'))
        lim_row.addWidget(self.low_edit)
        lim_v.addLayout(lim_row)

        lim_row2 = QHBoxLayout()
        lim_row2.addWidget(QLabel('High:'))
        lim_row2.addWidget(self.high_edit)
        lim_v.addLayout(lim_row2)

        apply_btn = QPushButton('Apply Limits')
        apply_btn.clicked.connect(self._apply_limits)
        lim_v.addWidget(apply_btn)

        clear_btn = QPushButton('Clear Limits')
        clear_btn.clicked.connect(self._clear_limits)
        lim_v.addWidget(clear_btn)

        left_v.addWidget(lim_box)

        # Filter by test type
        filter_box = QGroupBox('Filter Tests')
        filter_v = QVBoxLayout(filter_box)
        self.test_tree = QTreeWidget()
        self.test_tree.setHeaderHidden(True)
        self.test_tree.setFixedHeight(140)
        filter_v.addWidget(self.test_tree)
        left_v.addWidget(filter_box)

        left_v.addStretch()

        main_h.addWidget(left)

        # ── Centre: wafer canvas ──
        self.canvas = WaferCanvas()
        self.canvas.siteClicked.connect(self._on_site_clicked)
        main_h.addWidget(self.canvas, stretch=3)

        # ── Right panel: tabs ──
        right = QWidget()
        right.setFixedWidth(280)
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        right_v.addWidget(tabs)

        self.detail_panel = SiteDetailPanel()
        tabs.addTab(self.detail_panel, '🔍 Die Detail')

        self.stats_panel = StatsPanel()
        tabs.addTab(self.stats_panel, '📊 Statistics')

        main_h.addWidget(right)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage('Ready — open a KDF file to begin')

    # ── File loading ─────────────────────────

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open KDF File', '', 'KDF Files (*.kdf);;All Files (*)')
        if path:
            self._load_file(path)

    def _load_file(self, path):
        try:
            header, sites, tests, mkeys = parse_kdf(path)
        except Exception as e:
            QMessageBox.critical(self, 'Parse Error', f'Failed to read KDF file:\n{e}')
            return

        self._filepath = path
        self._header   = header
        self._sites    = sites
        self._tests    = tests
        self._mkeys    = mkeys
        self._limits   = {}
        self._current_mkey = None

        # Update file info labels
        self.lbl_file.setText(f'  {os.path.basename(path)}')
        self.lbl_lot.setText(header.get('LOT', '—'))
        self.lbl_sys.setText(header.get('SYS', '—'))
        self.lbl_stt.setText(header.get('STT', '—'))
        self.lbl_sites_count.setText(str(len(sites)))

        # Populate measurement combo
        self.mkey_combo.blockSignals(True)
        self.mkey_combo.clear()
        self.mkey_combo.addItems(mkeys)
        self.mkey_combo.blockSignals(False)

        # Populate test filter tree
        self.test_tree.clear()
        test_to_params = defaultdict(list)
        for mk in mkeys:
            parts = mk.split('@')
            if len(parts) >= 2:
                test_to_params[parts[1]].append(parts[0])
        for test in sorted(test_to_params.keys()):
            parent = QTreeWidgetItem(self.test_tree, [test])
            parent.setForeground(0, QColor('#4fc3f7'))
            parent.setExpanded(False)
            for param in sorted(test_to_params[test]):
                child = QTreeWidgetItem(parent, [f'{param}@{test}'])
                child.setForeground(0, QColor('#bdc3c7'))
        self.test_tree.itemDoubleClicked.connect(self._on_tree_double_click)

        # Select first measurement and draw
        if mkeys:
            self._current_mkey = mkeys[0]
            self.mkey_combo.setCurrentText(mkeys[0])
            self._refresh_canvas()

        self._update_ui_state()
        self.status.showMessage(
            f'Loaded {len(sites)} sites, {len(mkeys)} measurements — {os.path.basename(path)}')

    def _on_tree_double_click(self, item, col):
        mk = item.text(0)
        if mk in self._mkeys:
            self.mkey_combo.setCurrentText(mk)

    # ── Measurement & limits ─────────────────

    def _on_mkey_changed(self, mkey):
        if mkey not in self._mkeys:
            return
        self._current_mkey = mkey
        # Restore saved limits for this mkey
        lo, hi = self._limits.get(mkey, (None, None))
        self.low_edit.setText(str(lo) if lo is not None else '')
        self.high_edit.setText(str(hi) if hi is not None else '')
        self._refresh_canvas()

    def _apply_limits(self):
        lo = hi = None
        try:
            txt = self.low_edit.text().strip()
            if txt:
                lo = float(txt)
        except ValueError:
            QMessageBox.warning(self, 'Invalid', 'Low limit must be a number.')
            return
        try:
            txt = self.high_edit.text().strip()
            if txt:
                hi = float(txt)
        except ValueError:
            QMessageBox.warning(self, 'Invalid', 'High limit must be a number.')
            return

        if self._current_mkey:
            self._limits[self._current_mkey] = (lo, hi)
        self._refresh_canvas()

    def _clear_limits(self):
        self.low_edit.clear()
        self.high_edit.clear()
        if self._current_mkey:
            self._limits[self._current_mkey] = (None, None)
        self._refresh_canvas()

    def _refresh_canvas(self):
        if not self._sites or not self._current_mkey:
            return
        mkey = self._current_mkey
        lo, hi = self._limits.get(mkey, (None, None))

        values = {}
        for site in self._sites:
            values[site['name']] = get_site_value(site, mkey)

        self.canvas.load(self._sites, values, lo, hi, mkey=mkey)
        self.stats_panel.update_stats(values, lo, hi)
        self.status.showMessage(
            f'Showing: {mkey}  |  '
            f'Low={lo if lo is not None else "—"}  '
            f'High={hi if hi is not None else "—"}  |  '
            f'{len(self._sites)} sites'
        )

    # ── Site click ────────────────────────────

    def _on_site_clicked(self, site):
        self.detail_panel.show_site(site)

    # ── Export ────────────────────────────────

    def export_map(self):
        if not self._sites:
            QMessageBox.information(self, 'Nothing to export', 'Load a KDF file first.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Wafer Map', 'wafer_map.png',
            'PNG Image (*.png);;JPEG Image (*.jpg)')
        if not path:
            return
        pixmap = self.canvas.grab()
        if pixmap.save(path):
            self.status.showMessage(f'Exported to {path}')
            QMessageBox.information(self, 'Exported', f'Wafer map saved to:\n{path}')
        else:
            QMessageBox.critical(self, 'Error', 'Failed to save image.')

    # ── UI state ──────────────────────────────

    def _update_ui_state(self):
        has_data = bool(self._sites)
        self.mkey_combo.setEnabled(has_data)
        self.low_edit.setEnabled(has_data)
        self.high_edit.setEnabled(has_data)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Wafer Map Viewer')
    app.setStyle('Fusion')

    win = MainWindow()
    win.show()

    # Auto-load if a path was given on command line
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        win._load_file(sys.argv[1])

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()