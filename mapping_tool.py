"""
Wafer Map Viewer  —  Keithley ACS KDF V1.2
Displays any KDF file as an interactive wafer map.
Subsite number = design number; switch designs via the Design selector.

Requirements:  pip install PySide6
Usage:         python wafer_mapper_light.py [file.kdf]
"""

import sys, os, re, math, statistics
from collections import defaultdict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QTreeWidget, QTreeWidgetItem, QGroupBox,
    QLineEdit, QFormLayout, QStatusBar, QComboBox,
    QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QToolBar, QSizePolicy, QPushButton, QSpinBox
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSize
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont,
    QLinearGradient, QRadialGradient, QPixmap, QIcon, QAction
)

# ─────────────────────────────────────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────────────────────────────────────

T = {
    "bg_app":        "#f0f3f7",
    "bg_panel":      "#ffffff",
    "bg_header":     "#e8edf4",
    "bg_row_alt":    "#f3f6fa",
    "border":        "#cdd6e3",
    "border_hi":     "#a0b4cc",
    "accent":        "#1565c0",
    "accent_dim":    "#dce8fb",
    "accent_dark":   "#0d47a1",
    "pass_bg":       "#e3f6ec",
    "pass_fg":       "#1b6b3a",
    "pass_border":   "#5cb87a",
    "neutral_bg":    "#dfe8f3",
    "neutral_fg":    "#2c4a6e",
    "neutral_border":"#90a8c4",
    "fail_bg":       "#fce8e8",
    "fail_fg":       "#b71c1c",
    "fail_border":   "#e57373",
    "nodata_bg":     "#eeecf5",
    "nodata_fg":     "#7060a0",
    "nodata_border": "#b0a8d0",
    "wafer_bg":      "#eef2f8",
    "wafer_edge":    "#7a9cbd",
    "text_primary":  "#1a2537",
    "text_secondary":"#4a5c72",
    "text_dim":      "#8fa4bc",
    "selected":      "#e65100",
    "hover_border":  "#1565c0",
    "warn":          "#e65100",
}

SS = """
QMainWindow,QWidget{background-color:""" + T['bg_app'] + """;color:""" + T['text_primary'] + """;
    font-family:'Segoe UI','Calibri',sans-serif;font-size:13px;}
QGroupBox{background-color:""" + T['bg_panel'] + """;border:1px solid """ + T['border'] + """;
    border-radius:6px;margin-top:22px;padding:8px 6px 6px 6px;font-weight:bold;font-size:11px;}
QGroupBox::title{subcontrol-origin:margin;left:10px;padding:2px 6px;
    background:""" + T['bg_panel'] + """;color:""" + T['accent'] + """;font-size:11px;font-weight:bold;}
QLabel{background:transparent;color:""" + T['text_primary'] + """;font-size:13px;}
QPushButton{background-color:""" + T['bg_panel'] + """;border:1px solid """ + T['border_hi'] + """;
    border-radius:5px;padding:6px 16px;color:""" + T['text_primary'] + """;font-weight:600;
    font-size:13px;min-height:28px;}
QPushButton:hover{background-color:""" + T['accent_dim'] + """;border:1px solid """ + T['accent'] + """;
    color:""" + T['accent_dark'] + """;}
QPushButton:pressed{background-color:""" + T['accent'] + """;color:white;}
QPushButton#primary{background-color:""" + T['accent'] + """;border:1px solid """ + T['accent_dark'] + """;
    color:white;font-weight:bold;}
QPushButton#primary:hover{background-color:""" + T['accent_dark'] + """;}
QComboBox{background-color:""" + T['bg_panel'] + """;border:1px solid """ + T['border'] + """;
    border-radius:5px;padding:5px 10px;color:""" + T['text_primary'] + """;font-size:13px;min-height:28px;}
QComboBox::drop-down{border:none;width:24px;}
QComboBox::down-arrow{width:9px;height:7px;border-left:5px solid transparent;
    border-right:5px solid transparent;border-top:7px solid """ + T['accent'] + """;}
QComboBox QAbstractItemView{background:""" + T['bg_panel'] + """;border:1px solid """ + T['border_hi'] + """;
    selection-background-color:""" + T['accent_dim'] + """;color:""" + T['text_primary'] + """;font-size:13px;}
QLineEdit,QSpinBox{background-color:""" + T['bg_panel'] + """;border:1px solid """ + T['border'] + """;
    border-radius:5px;padding:5px 10px;color:""" + T['text_primary'] + """;font-size:13px;min-height:28px;}
QLineEdit:focus,QSpinBox:focus{border:1px solid """ + T['accent'] + """;}
QSpinBox::up-button,QSpinBox::down-button{width:20px;background:""" + T['bg_header'] + """;
    border:none;}
QTreeWidget,QTableWidget{background-color:""" + T['bg_panel'] + """;border:1px solid """ + T['border'] + """;
    border-radius:4px;alternate-background-color:""" + T['bg_row_alt'] + """;outline:none;font-size:13px;}
QTreeWidget::item,QTableWidget::item{padding:4px 5px;border:none;}
QTreeWidget::item:hover,QTableWidget::item:hover{background-color:""" + T['accent_dim'] + """;}
QTreeWidget::item:selected,QTableWidget::item:selected{background-color:""" + T['accent_dim'] + """;
    color:""" + T['accent_dark'] + """;}
QHeaderView::section{background-color:""" + T['bg_header'] + """;color:""" + T['accent_dark'] + """;
    border:none;border-right:1px solid """ + T['border'] + """;border-bottom:1px solid """ + T['border'] + """;
    padding:6px 10px;font-size:12px;font-weight:bold;}
QScrollBar:vertical{background:""" + T['bg_app'] + """;width:9px;border:none;border-radius:4px;}
QScrollBar::handle:vertical{background:""" + T['border_hi'] + """;border-radius:4px;min-height:24px;}
QScrollBar::handle:vertical:hover{background:""" + T['accent'] + """;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QScrollBar:horizontal{background:""" + T['bg_app'] + """;height:9px;border-radius:4px;}
QScrollBar::handle:horizontal{background:""" + T['border_hi'] + """;border-radius:4px;}
QTabWidget::pane{border:1px solid """ + T['border'] + """;background:""" + T['bg_panel'] + """;
    border-radius:0 5px 5px 5px;}
QTabBar::tab{background:""" + T['bg_header'] + """;color:""" + T['text_secondary'] + """;
    padding:7px 18px;border:1px solid """ + T['border'] + """;border-bottom:none;
    border-radius:5px 5px 0 0;margin-right:2px;font-size:12px;}
QTabBar::tab:selected{background:""" + T['bg_panel'] + """;color:""" + T['accent'] + """;
    border-top:2px solid """ + T['accent'] + """;font-weight:bold;font-size:13px;}
QStatusBar{background:""" + T['bg_header'] + """;color:""" + T['text_secondary'] + """;
    border-top:1px solid """ + T['border'] + """;font-size:12px;padding:3px 6px;}
QToolBar{background:""" + T['bg_panel'] + """;border-bottom:1px solid """ + T['border'] + """;
    spacing:4px;padding:5px 10px;}
QToolBar::separator{background:""" + T['border'] + """;width:1px;margin:4px 8px;}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  APP ICON
# ─────────────────────────────────────────────────────────────────────────────

def make_app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128):
        pix = QPixmap(sz, sz)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        cx = cy = sz / 2.0
        r  = sz / 2.0 - 1.0
        disc = QRadialGradient(cx - r*0.2, cy - r*0.25, r*1.35)
        disc.setColorAt(0, QColor("#2d5490"))
        disc.setColorAt(0.65, QColor("#1a3460"))
        disc.setColorAt(1.0, QColor("#0c1e3a"))
        p.setBrush(QBrush(disc))
        p.setPen(QPen(QColor("#5588cc"), max(1.0, sz/18.0)))
        p.drawEllipse(QPointF(cx, cy), r, r)
        nw = r*0.36; nh = max(2.0, sz*0.05)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.setPen(Qt.NoPen); p.setBrush(Qt.transparent)
        p.drawRect(QRectF(cx-nw/2, cy+r-nh, nw, nh+1))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setPen(QPen(QColor("#5588cc"), max(1.0, sz/20.0)))
        p.drawLine(QPointF(cx-nw/2, cy+r-nh), QPointF(cx+nw/2, cy+r-nh))
        colors = [QColor("#3dba6f"), QColor("#3dba6f"), QColor("#8a98b0"),
                  QColor("#3dba6f"), QColor("#3dba6f"), QColor("#d95555"),
                  QColor("#8a98b0"), QColor("#3dba6f"), QColor("#3dba6f")]
        ge = r*1.08; cs = ge/3.0; gap = max(0.6, cs*0.12)
        gx0 = cx - ge/2; gy0 = cy - ge/2
        p.setPen(QPen(QColor("#0c1e3a"), max(0.5, gap*0.4)))
        for row in range(3):
            for col in range(3):
                rx = gx0 + col*cs + gap; ry = gy0 + row*cs + gap
                rw = rh = cs - gap*2
                if rw > 0:
                    p.setBrush(QBrush(colors[row*3+col]))
                    p.drawRoundedRect(QRectF(rx, ry, rw, rh),
                                      max(0.5, rw*0.18), max(0.5, rw*0.18))
        p.end()
        icon.addPixmap(pix)
    return icon

# ─────────────────────────────────────────────────────────────────────────────
#  KDF PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_kdf(filepath: str):
    """
    Parse a Keithley ACS KDF V1.2 file.

    Returns
    -------
    header  : dict
    sites   : list of { 'name', 'x', 'y',
                        'subsites': { sub_num: { 'param@test': float } } }
    params  : sorted list of unique 'param@test' keys
    tests   : sorted list of unique test names
    """
    header: dict = {}
    sites:  list = []
    mkeys:  set  = set()
    tkeys:  set  = set()

    with open(filepath, 'r', errors='replace') as fh:
        lines = [l.rstrip('\r\n') for l in fh]

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s == '<EOH>':
            i += 1
            break
        if ',' in s:
            k, _, v = s.partition(',')
            header[k.strip()] = v.strip()
        i += 1

    # skip optional wafer-identification line
    if i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('Site_'):
        i += 1

    current = None
    while i < len(lines):
        s = lines[i].strip(); i += 1
        if not s:
            continue
        if s == '<EOS>':
            if current is not None:
                sites.append(current)
            current = None
            continue
        if s.startswith('Site_'):
            if current is not None:
                sites.append(current)
            parts = s.split(',')
            name  = parts[0].strip()
            try:
                x = int(parts[1].strip())
                y = int(parts[2].strip())
            except (IndexError, ValueError):
                m = re.match(r'Site_([pn])(\d+)([pn])(\d+)', name)
                if m:
                    xs, xv, ys, yv = m.groups()
                    x = int(xv) * (1 if xs == 'p' else -1)
                    y = int(yv) * (1 if ys == 'p' else -1)
                else:
                    x = y = 0
            current = {'name': name, 'x': x, 'y': y, 'subsites': {}}
            continue
        if current is None:
            continue
        if '@' in s and ',' in s:
            kp, _, vs = s.partition(',')
            parts = kp.split('@')
            if len(parts) >= 3:
                param, test, sub_raw = parts[0].strip(), parts[1].strip(), parts[2].strip()
                try:
                    sub_num = int(sub_raw.split('#')[1])
                except (IndexError, ValueError):
                    sub_num = 1
                try:
                    value = float(vs.strip())
                except ValueError:
                    value = None
                mkey = f"{param}@{test}"
                mkeys.add(mkey); tkeys.add(test)
                if sub_num not in current['subsites']:
                    current['subsites'][sub_num] = {}
                current['subsites'][sub_num][mkey] = value

    if current is not None:
        sites.append(current)

    return header, sites, sorted(mkeys), sorted(tkeys)


def get_site_value(site: dict, mkey: str, subsite: int | None = None) -> float | None:
    """
    Return the value for a measurement key on a site.
    If subsite is None  → average across all subsites (designs).
    If subsite is given → return that specific design's value only.
    Ignores non-finite values (e.g. 7e+22 instrument error codes).
    """
    if subsite is not None:
        v = site['subsites'].get(subsite, {}).get(mkey)
        return v if (v is not None and math.isfinite(v)) else None

    values = [
        v for sub in site['subsites'].values()
        for k, v in sub.items()
        if k == mkey and v is not None and math.isfinite(v)
    ]
    return statistics.mean(values) if values else None


def all_subsites(sites: list) -> list[int]:
    """Return sorted list of all unique subsite numbers across all sites."""
    s = set()
    for site in sites:
        s.update(site['subsites'].keys())
    return sorted(s)


def si_fmt(v: float | None) -> str:
    """
    Format a float using the largest SI prefix where |scaled| is in [0.1, 1000).
    Never uses scientific notation.
    Examples: 3e-13 → '0.3p',  14.3e-12 → '14.3p',  25e-15 → '25f'
    """
    if v is None or not math.isfinite(v):
        return 'N/A'
    if v == 0:
        return '0'

    prefixes = [
        (1e15,'P'), (1e12,'T'), (1e9,'G'),  (1e6,'M'),  (1e3,'k'),
        (1e0,''),   (1e-3,'m'),(1e-6,'µ'),  (1e-9,'n'), (1e-12,'p'),
        (1e-15,'f'),(1e-18,'a'),
    ]
    av = abs(v)
    best_factor, best_suffix = prefixes[-1]
    for factor, suffix in prefixes:
        if 0.1 <= av / factor < 1000.0:
            best_factor = factor; best_suffix = suffix; break

    scaled = v / best_factor
    if abs(scaled) >= 100:   text = f"{scaled:.1f}"
    elif abs(scaled) >= 10:  text = f"{scaled:.2f}"
    else:                    text = f"{scaled:.3f}"
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return f"{text}{best_suffix}"

# ─────────────────────────────────────────────────────────────────────────────
#  WAFER CANVAS
# ─────────────────────────────────────────────────────────────────────────────

class WaferCanvas(QWidget):
    siteClicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sites         = []
        self.values        = {}    # site_name → float | None
        self.low_limit     = None
        self.high_limit    = None
        self.mkey          = ''
        self.selected_site = None
        self._hover        = None
        self._rects        = {}    # site_name → QRectF

        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def load(self, sites, values, lo, hi, mkey=''):
        self.sites = sites; self.values = values
        self.low_limit = lo; self.high_limit = hi; self.mkey = mkey
        self.selected_site = None; self._hover = None
        self.update()

    @property
    def _limits_active(self):
        return self.low_limit is not None or self.high_limit is not None

    def _bounds(self):
        if not self.sites:
            return -1, 1, -1, 1
        xs = [s['x'] for s in self.sites]
        ys = [s['y'] for s in self.sites]
        return min(xs), max(xs), min(ys), max(ys)

    def _layout(self, x0, x1, y0, y1, w, h):
        n_cols = x1 - x0 + 1
        n_rows = y1 - y0 + 1

        # Wafer circle is treated as fixed (fits the screen). We size the
        # tiles to fit *inside* the fixed circle based on the number of
        # columns/rows.
        cx = w / 2.0
        cy = h / 2.0
        radius_max = min(cx, w - cx, cy, h - cy) - 0.5
        disc_margin = 6.0  # small breathing room for pen + notch
        radius = max(1.0, radius_max - disc_margin)

        # Upper bound so the die grid never exceeds widget bounds.
        cell_hi = min(w / max(n_cols, 1), h / max(n_rows, 1))
        cell_lo = 1.0

        def fits(cell: float) -> bool:
            # This must match how die rectangles are inset in paintEvent().
            mg = max(1.5, cell * 0.04)
            half_grid_w = cell * n_cols / 2.0 - mg
            half_grid_h = cell * n_rows / 2.0 - mg
            half_grid_w = max(0.0, half_grid_w)
            half_grid_h = max(0.0, half_grid_h)

            # distance from circle center to the farthest die corner
            dist = math.hypot(half_grid_w, half_grid_h)

            # keep a tiny clearance so rounded corners + stroke don't clip
            return dist <= (radius - 0.8)

        # Binary search for largest `cell` that fits in the fixed disc.
        for _ in range(24):
            cell_mid = (cell_lo + cell_hi) / 2.0
            if fits(cell_mid):
                cell_lo = cell_mid
            else:
                cell_hi = cell_mid

        cell = cell_lo

        ox = (w - cell * n_cols) / 2.0
        oy = (h - cell * n_rows) / 2.0
        return ox, oy, cell

    def _die_color(self, name):
        v = self.values.get(name)
        if v is None:
            return QColor(T['nodata_bg']), QColor(T['nodata_fg']), QColor(T['nodata_border'])
        if not self._limits_active:
            return QColor(T['neutral_bg']), QColor(T['neutral_fg']), QColor(T['neutral_border'])
        lo, hi  = self.low_limit, self.high_limit
        passed  = (lo is None or v >= lo) and (hi is None or v <= hi)
        if passed:
            return QColor(T['pass_bg']), QColor(T['pass_fg']), QColor(T['pass_border'])
        return QColor(T['fail_bg']), QColor(T['fail_fg']), QColor(T['fail_border'])

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()

        # ── background ────────────────────────────────────────────────────────
        p.fillRect(0, 0, w, h, QColor(T['bg_app']))
        p.setPen(QPen(QColor(T['border']), 1.0))
        for gx in range(0, w + 28, 28):
            for gy in range(0, h + 28, 28):
                p.drawPoint(gx, gy)

        if not self.sites:
            p.setPen(QColor(T['text_dim']))
            p.setFont(QFont('Segoe UI', 14))
            p.drawText(self.rect(), Qt.AlignCenter, 'Open a KDF file to begin')
            return

        x0, x1, y0, y1 = self._bounds()
        ox, oy, cell    = self._layout(x0, x1, y0, y1, w, h)
        n_cols = x1 - x0 + 1
        n_rows = y1 - y0 + 1

        # Fixed wafer circle (does not depend on how many tiles there are).
        cx = w / 2.0
        cy = h / 2.0
        radius_max = min(cx, w - cx, cy, h - cy) - 0.5
        disc_margin = 6.0
        radius = max(1.0, radius_max - disc_margin)

        # ── disc shadow ───────────────────────────────────────────────────────
        shad = QRadialGradient(cx+4, cy+4, radius+4)
        shad.setColorAt(0,   QColor(0, 0, 0, 24))
        shad.setColorAt(0.8, QColor(0, 0, 0,  8))
        shad.setColorAt(1.0, QColor(0, 0, 0,  0))
        p.setBrush(QBrush(shad)); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx+4, cy+4), radius+4, radius+4)

        # ── wafer disc ────────────────────────────────────────────────────────
        wg = QRadialGradient(cx - radius*0.15, cy - radius*0.2, radius*1.3)
        wg.setColorAt(0,    QColor('#ffffff'))
        wg.setColorAt(0.5,  QColor(T['wafer_bg']))
        wg.setColorAt(1.0,  QColor('#cfd9e8'))
        p.setBrush(QBrush(wg))
        p.setPen(QPen(QColor(T['wafer_edge']), 1.5))
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # ── flat notch at bottom ──────────────────────────────────────────────
        nw = radius * 0.22
        p.setPen(Qt.NoPen); p.setBrush(QColor(T['bg_app']))
        # Keep the notch inside the disc edge so the disc won't need
        # extra "padding" to avoid clipping.
        p.drawRect(QRectF(cx - nw/2, cy + radius - 6, nw, 6))
        p.setPen(QPen(QColor(T['wafer_edge']), 2))
        p.drawLine(QPointF(cx - nw/2, cy + radius - 4),
                   QPointF(cx + nw/2, cy + radius - 4))

        # ── die cells ─────────────────────────────────────────────────────────
        fs   = max(7, int(cell * 0.15))
        vfnt = QFont('Consolas', fs, QFont.Bold)
        cfnt = QFont('Consolas', max(6, fs - 2))
        self._rects = {}

        for site in self.sites:
            mg   = max(1.5, cell * 0.04)
            px_  = ox + (site['x'] - x0) * cell
            py_  = oy + (y1 - site['y']) * cell
            rect = QRectF(px_ + mg, py_ + mg, cell - 2*mg, cell - 2*mg)
            self._rects[site['name']] = rect

            bg, fg, bc = self._die_color(site['name'])
            is_sel = self.selected_site and site['name'] == self.selected_site['name']
            is_hov = self._hover         and site['name'] == self._hover['name']

            # soft drop shadow on larger cells
            if cell > 30:
                p.setBrush(QColor(0,0,0,12)); p.setPen(Qt.NoPen)
                p.drawRoundedRect(
                    QRectF(rect.x()+2, rect.y()+2, rect.width(), rect.height()), 3, 3)

            # gradient fill
            cg = QLinearGradient(rect.topLeft(), rect.bottomRight())
            cg.setColorAt(0, bg.lighter(108)); cg.setColorAt(1, bg)
            p.setBrush(QBrush(cg))
            p.setPen(QPen(QColor(T['selected']), 2.5) if is_sel
                     else QPen(QColor(T['hover_border']), 2) if is_hov
                     else QPen(bc, 1))
            p.drawRoundedRect(rect, 3, 3)

            # value label
            v = self.values.get(site['name'])
            if v is not None and cell > 28:
                p.setFont(vfnt); p.setPen(fg)
                p.drawText(rect, Qt.AlignCenter, si_fmt(v))

            # coordinate overlay at high zoom
            if cell > 58:
                p.setFont(cfnt); p.setPen(QColor(T['text_dim']))
                cr = QRectF(px_+mg+2, py_+mg+1, cell-2*mg-2, cell*0.28)
                p.drawText(cr, Qt.AlignLeft | Qt.AlignTop,
                           f"{site['x']},{site['y']}")

        self._draw_legend(p, w, h)

    def _draw_legend(self, p, w, h):
        items = ([(T['pass_bg'],    T['pass_fg'],    'Pass'),
                  (T['fail_bg'],    T['fail_fg'],    'Fail'),
                  (T['nodata_bg'],  T['nodata_fg'],  'No data')]
                 if self._limits_active else
                 [(T['neutral_bg'], T['neutral_fg'], 'No limits set'),
                  (T['nodata_bg'],  T['nodata_fg'],  'No data')])

        bh = len(items) * 22 + 16
        lx = 14; ly = h - bh - 10
        p.setBrush(QColor(255, 255, 255, 215))
        p.setPen(QPen(QColor(T['border']), 1))
        p.drawRoundedRect(QRectF(lx-6, ly-8, 178, bh), 5, 5)
        p.setFont(QFont('Segoe UI', 11))
        for bg_hex, fg_hex, label in items:
            p.setBrush(QBrush(QColor(bg_hex)))
            p.setPen(QPen(QColor(fg_hex), 1))
            p.drawRoundedRect(QRectF(lx, ly, 14, 14), 2, 2)
            p.setPen(QColor(T['text_primary']))
            p.drawText(int(lx+20), int(ly+11), label)
            ly += 22

    def mouseMoveEvent(self, e):
        pos = QPointF(e.position()); self._hover = None
        for site in self.sites:
            r = self._rects.get(site['name'])
            if r and r.contains(pos):
                self._hover = site
                self.setCursor(Qt.PointingHandCursor)
                break
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            pos = QPointF(e.position())
            for site in self.sites:
                r = self._rects.get(site['name'])
                if r and r.contains(pos):
                    self.selected_site = site
                    self.siteClicked.emit(site)
                    self.update()
                    return

    def leaveEvent(self, _e):
        self._hover = None; self.update()

# ─────────────────────────────────────────────────────────────────────────────
#  DIE DETAIL PANEL
# ─────────────────────────────────────────────────────────────────────────────

class SiteDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self); lo.setContentsMargins(8, 8, 8, 8); lo.setSpacing(8)

        self.title = QLabel('Click a die to inspect')
        self.title.setWordWrap(True)
        self.title.setStyleSheet(
            f'font-weight:bold;font-size:13px;color:{T["accent_dark"]};'
            f'padding:5px 8px;background:{T["accent_dim"]};'
            f'border-radius:5px;border-left:3px solid {T["accent"]};')
        lo.addWidget(self.title)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Measurement', 'Design #', 'Value'])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        lo.addWidget(self.table)

    def show_site(self, site: dict):
        self.title.setText(
            f'  {site["name"]}   ·   X = {site["x"]},  Y = {site["y"]}')

        rows = []
        for sub_num in sorted(site['subsites']):
            for mkey, val in sorted(site['subsites'][sub_num].items()):
                rows.append((mkey, sub_num, val))

        self.table.setRowCount(len(rows))
        for i, (mkey, sub, val) in enumerate(rows):
            mi = QTableWidgetItem(mkey)
            mi.setFont(QFont('Segoe UI', 12))
            self.table.setItem(i, 0, mi)

            si = QTableWidgetItem(str(sub))
            si.setTextAlignment(Qt.AlignCenter)
            si.setForeground(QColor(T['text_secondary']))
            si.setFont(QFont('Segoe UI', 12))
            self.table.setItem(i, 1, si)

            # show N/A for non-finite values (instrument error codes)
            display = si_fmt(val) if (val is not None and math.isfinite(val)) else 'N/A'
            vi = QTableWidgetItem(display)
            vi.setForeground(QColor(T['accent_dark']))
            vi.setFont(QFont('Consolas', 12, QFont.Bold))
            self.table.setItem(i, 2, vi)

# ─────────────────────────────────────────────────────────────────────────────
#  STATISTICS PANEL
# ─────────────────────────────────────────────────────────────────────────────

class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self); lo.setContentsMargins(8, 8, 8, 8); lo.setSpacing(6)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Statistic', 'Value'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        lo.addWidget(self.table)

    def update_stats(self, values_dict: dict, lo, hi):
        vals = [v for v in values_dict.values()
                if v is not None and math.isfinite(v)]
        if not vals:
            self.table.setRowCount(0)
            return

        n      = len(vals)
        mean_v = statistics.mean(vals)
        std_v  = statistics.pstdev(vals)
        med_v  = statistics.median(vals)
        min_v  = min(vals)
        max_v  = max(vals)
        passed = sum(1 for v in vals
                     if (lo is None or v >= lo) and (hi is None or v <= hi))
        yld    = passed / n * 100

        rows = [
            ('Count',   str(n)),
            ('Mean',    si_fmt(mean_v)),
            ('Std Dev', si_fmt(std_v)),
            ('Min',     si_fmt(min_v)),
            ('Max',     si_fmt(max_v)),
            ('Median',  si_fmt(med_v)),
            ('3σ',      f'{si_fmt(mean_v - 3*std_v)}  →  {si_fmt(mean_v + 3*std_v)}'),
            ('Pass',    str(passed)),
            ('Fail',    str(n - passed)),
            ('Yield',   f'{yld:.1f}%'),
        ]
        self.table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            ki = QTableWidgetItem(k)
            ki.setForeground(QColor(T['text_secondary']))
            ki.setFont(QFont('Segoe UI', 12))
            self.table.setItem(i, 0, ki)

            vi = QTableWidgetItem(v)
            vi.setFont(QFont('Consolas', 12))
            if k == 'Yield':
                col = (T['pass_fg'] if yld >= 90
                       else T['fail_fg'] if yld < 70
                       else T['warn'])
                vi.setForeground(QColor(col))
                vi.setFont(QFont('Segoe UI', 13, QFont.Bold))
            elif k == 'Pass': vi.setForeground(QColor(T['pass_fg']))
            elif k == 'Fail': vi.setForeground(QColor(T['fail_fg']))
            else:             vi.setForeground(QColor(T['text_primary']))
            self.table.setItem(i, 1, vi)

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Wafer Map Viewer')
        self.resize(1300, 840)
        self.setStyleSheet(SS)
        self.setWindowIcon(make_app_icon())

        self._header:       dict      = {}
        self._sites:        list      = []
        self._mkeys:        list[str] = []
        self._limits:       dict      = {}   # mkey → (lo, hi)
        self._current_mkey: str | None = None
        self._filepath:     str | None = None
        self._all_subsites: list[int]  = []  # sorted subsite numbers found
        self._current_sub:  int | None = None  # None = average all

        self._build_ui()
        self._update_ui_state()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        tb = QToolBar('Main', self)
        tb.setIconSize(QSize(18, 18)); tb.setMovable(False)
        self.addToolBar(tb)

        open_act = QAction('  Open KDF…', self)
        open_act.triggered.connect(self.open_file)
        tb.addAction(open_act)
        tb.addSeparator()

        exp_act = QAction('  Export Map…', self)
        exp_act.triggered.connect(self.export_map)
        tb.addAction(exp_act)
        tb.addSeparator()

        sp = QWidget(); sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(sp)
        self.lbl_file = QLabel('No file loaded  ')
        self.lbl_file.setStyleSheet(
            f'color:{T["text_secondary"]};font-size:12px;padding-right:10px;')
        tb.addWidget(self.lbl_file)

        # ── central ───────────────────────────────────────────────────────────
        cw = QWidget(); self.setCentralWidget(cw)
        mh = QHBoxLayout(cw); mh.setSpacing(10); mh.setContentsMargins(10, 10, 10, 10)

        # ── left panel ────────────────────────────────────────────────────────
        left = QWidget(); left.setFixedWidth(282)
        lv = QVBoxLayout(left); lv.setSpacing(10); lv.setContentsMargins(0, 0, 0, 0)

        # file info
        ib = QGroupBox('File Information')
        iform = QFormLayout(ib); iform.setSpacing(6)
        iform.setLabelAlignment(Qt.AlignRight)

        def mkval():
            l = QLabel('—')
            l.setStyleSheet(
                f'color:{T["text_primary"]};font-weight:600;font-size:13px;')
            return l

        self.lbl_lot   = mkval(); self.lbl_sys   = mkval()
        self.lbl_stt   = mkval(); self.lbl_cnt   = mkval()
        self.lbl_tests = mkval(); self.lbl_dsn   = mkval()

        for lbl_txt, wid in [
            ('Lot',     self.lbl_lot),
            ('System',  self.lbl_sys),
            ('Start',   self.lbl_stt),
            ('Sites',   self.lbl_cnt),
            ('Tests',   self.lbl_tests),
            ('Designs', self.lbl_dsn),
        ]:
            kl = QLabel(lbl_txt)
            kl.setStyleSheet(f'color:{T["text_secondary"]};font-size:12px;')
            iform.addRow(kl, wid)
        lv.addWidget(ib)

        # design (subsite) selector
        db = QGroupBox('Design')
        dv = QVBoxLayout(db); dv.setSpacing(6)

        desc = QLabel(
            'Each die may contain multiple designs.\n'
            'Select which design to display.')
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f'color:{T["text_secondary"]};font-size:11px;')
        dv.addWidget(desc)

        self.design_combo = QComboBox()
        self.design_combo.currentIndexChanged.connect(self._on_design_changed)
        dv.addWidget(self.design_combo)
        lv.addWidget(db)

        # measurement selector
        mb = QGroupBox('Measurement')
        mv = QVBoxLayout(mb); mv.setSpacing(6)
        self.mkey_combo = QComboBox()
        self.mkey_combo.currentTextChanged.connect(self._on_mkey_changed)
        mv.addWidget(self.mkey_combo)
        lv.addWidget(mb)

        # pass/fail limits
        lb = QGroupBox('Pass / Fail Limits')
        lbv = QVBoxLayout(lb); lbv.setSpacing(8)
        for lbl_txt, attr in [('Low', 'low_edit'), ('High', 'high_edit')]:
            row = QHBoxLayout()
            rl = QLabel(lbl_txt)
            rl.setStyleSheet(
                f'color:{T["text_secondary"]};font-size:12px;min-width:36px;')
            row.addWidget(rl)
            en = QLineEdit(); en.setPlaceholderText('no limit')
            setattr(self, attr, en); row.addWidget(en); lbv.addLayout(row)
        br = QHBoxLayout(); br.setSpacing(6)
        ab = QPushButton('Apply'); ab.setObjectName('primary')
        ab.clicked.connect(self._apply_limits)
        cb = QPushButton('Clear'); cb.clicked.connect(self._clear_limits)
        br.addWidget(ab); br.addWidget(cb); lbv.addLayout(br)
        lv.addWidget(lb)

        # test filter tree
        fb = QGroupBox('Filter by Test')
        fv = QVBoxLayout(fb); fv.setSpacing(6)
        self.test_tree = QTreeWidget()
        self.test_tree.setHeaderHidden(True)
        self.test_tree.setFixedHeight(180)
        self.test_tree.itemDoubleClicked.connect(self._tree_double_click)
        fv.addWidget(self.test_tree)
        lv.addWidget(fb)

        lv.addStretch()
        mh.addWidget(left)

        # ── centre canvas ─────────────────────────────────────────────────────
        canvas_wrap = QWidget()
        canvas_wrap.setStyleSheet(
            f'background:{T["bg_panel"]};border:1px solid {T["border"]};'
            f'border-radius:7px;')
        cl = QVBoxLayout(canvas_wrap); cl.setContentsMargins(4, 4, 4, 4)
        self.canvas = WaferCanvas()
        self.canvas.siteClicked.connect(self._on_die_clicked)
        cl.addWidget(self.canvas)
        mh.addWidget(canvas_wrap, stretch=3)

        # ── right panel ───────────────────────────────────────────────────────
        right = QWidget(); right.setFixedWidth(310)
        rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget(); rv.addWidget(tabs)

        self.detail_panel = SiteDetailPanel()
        tabs.addTab(self.detail_panel, 'Die Detail')

        self.stats_panel = StatsPanel()
        tabs.addTab(self.stats_panel, 'Statistics')

        mh.addWidget(right)

        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.status.showMessage('  Ready  ·  open a KDF file to begin')

    # ── file loading ──────────────────────────────────────────────────────────

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open KDF File', '',
            'KDF Files (*.kdf *.KDF);;All Files (*)')
        if path:
            self._load_kdf(path)

    def _load_kdf(self, path: str):
        try:
            header, sites, params, tests = parse_kdf(path)
        except Exception as e:
            QMessageBox.critical(self, 'Parse Error',
                                 f'Could not read KDF file:\n{e}')
            return

        self._filepath     = path
        self._header       = header
        self._sites        = sites
        self._mkeys        = params
        self._limits       = {}
        self._current_mkey = None

        # Discover all subsite (design) numbers
        subs = all_subsites(sites)
        self._all_subsites = subs
        self._current_sub  = subs[0] if len(subs) == 1 else None  # None = average

        # header labels
        self.lbl_file.setText(f'  {os.path.basename(path)}  ')
        self.lbl_lot.setText(header.get('LOT', '—'))
        self.lbl_sys.setText(header.get('SYS', '—') or header.get('TST', '—'))
        self.lbl_stt.setText(header.get('STT', '—'))
        self.lbl_cnt.setText(str(len(sites)))
        self.lbl_tests.setText(str(len(tests)))
        self.lbl_dsn.setText(str(len(subs)))

        self.setWindowTitle(f'Wafer Map Viewer  ·  {header.get("LOT", os.path.basename(path))}')

        # populate design selector
        self.design_combo.blockSignals(True)
        self.design_combo.clear()
        if len(subs) > 1:
            self.design_combo.addItem('All designs (average)', None)
        for sn in subs:
            self.design_combo.addItem(f'Design {sn}', sn)
        # default: first specific design (shows real single-design values)
        default_idx = 1 if len(subs) > 1 else 0
        self.design_combo.setCurrentIndex(default_idx)
        self._current_sub = self.design_combo.itemData(default_idx)
        self.design_combo.blockSignals(False)

        # populate measurement combo
        self.mkey_combo.blockSignals(True)
        self.mkey_combo.clear()
        self.mkey_combo.addItems(params)
        self.mkey_combo.blockSignals(False)

        # populate test filter tree
        self.test_tree.clear()
        groups: dict[str, list[str]] = defaultdict(list)
        for mk in params:
            pts  = mk.split('@')
            test = pts[1] if len(pts) >= 2 else 'Other'
            groups[test].append(pts[0])

        for test in sorted(groups):
            parent = QTreeWidgetItem(self.test_tree, [test])
            parent.setForeground(0, QColor(T['accent_dark']))
            parent.setFont(0, QFont('Segoe UI', 12, QFont.Bold))
            parent.setExpanded(True)
            for param in sorted(groups[test]):
                child = QTreeWidgetItem(parent, [f'{param}@{test}'])
                child.setForeground(0, QColor(T['text_secondary']))
                child.setFont(0, QFont('Segoe UI', 12))

        # auto-select first measurement
        if params:
            self._current_mkey = params[0]
            self.mkey_combo.setCurrentText(params[0])
            self._refresh_canvas()

        self._update_ui_state()
        self.status.showMessage(
            f'  Loaded {len(sites)} sites  ·  '
            f'{len(params)} measurements  ·  '
            f'{len(tests)} tests  ·  '
            f'{len(subs)} design(s)  ·  {os.path.basename(path)}')

    # ── design / measurement / limits ─────────────────────────────────────────

    def _on_design_changed(self, idx: int):
        if idx < 0:
            return
        self._current_sub = self.design_combo.itemData(idx)
        self._refresh_canvas()
        sub = self._current_sub
        label = 'All designs (average)' if sub is None else f'Design {sub}'
        if self._current_mkey:
            self.status.showMessage(
                f'  {self._current_mkey}  ·  {label}  ·  {len(self._sites)} sites')

    def _tree_double_click(self, item, _col):
        mk = item.text(0)
        if mk in self._mkeys:
            self.mkey_combo.setCurrentText(mk)

    def _on_mkey_changed(self, mkey: str):
        if mkey not in self._mkeys:
            return
        if self._current_mkey:
            lo = self._parse_limit(self.low_edit.text())
            hi = self._parse_limit(self.high_edit.text())
            self._limits[self._current_mkey] = (lo, hi)

        self._current_mkey = mkey
        lo, hi = self._limits.get(mkey, (None, None))
        self.low_edit.setText('' if lo is None else str(lo))
        self.high_edit.setText('' if hi is None else str(hi))
        self._refresh_canvas()

    def _apply_limits(self):
        lo = self._parse_limit(self.low_edit.text(),  'Low')
        hi = self._parse_limit(self.high_edit.text(), 'High')
        if lo is None and self.low_edit.text().strip():
            return
        if hi is None and self.high_edit.text().strip():
            return
        if self._current_mkey:
            self._limits[self._current_mkey] = (lo, hi)
        self._refresh_canvas()

    def _clear_limits(self):
        self.low_edit.clear(); self.high_edit.clear()
        if self._current_mkey:
            self._limits[self._current_mkey] = (None, None)
        self._refresh_canvas()

    def _parse_limit(self, text: str, label: str = '') -> float | None:
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            if label:
                QMessageBox.warning(self, 'Invalid value',
                                    f'{label} limit must be a number (e.g. 9.5 or 1e-12).')
            return None

    def _refresh_canvas(self):
        if not self._sites or not self._current_mkey:
            return
        mkey   = self._current_mkey
        sub    = self._current_sub
        lo, hi = self._limits.get(mkey, (None, None))

        values = {s['name']: get_site_value(s, mkey, sub) for s in self._sites}

        self.canvas.load(self._sites, values, lo, hi, mkey=mkey)
        self.stats_panel.update_stats(values, lo, hi)

        sub_label = 'avg' if sub is None else f'design {sub}'
        lo_s = '—' if lo is None else str(lo)
        hi_s = '—' if hi is None else str(hi)
        self.status.showMessage(
            f'  {mkey}  ·  {sub_label}'
            f'  ·  Low = {lo_s}  High = {hi_s}'
            f'  ·  {len(self._sites)} sites')

    def _on_die_clicked(self, site: dict):
        self.detail_panel.show_site(site)

    # ── export ────────────────────────────────────────────────────────────────

    def export_map(self):
        if not self._sites:
            QMessageBox.information(self, 'Nothing to export',
                                    'Load a KDF file first.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Wafer Map', 'wafer_map.png',
            'PNG Image (*.png);;JPEG Image (*.jpg)')
        if not path:
            return
        px = self.canvas.grab()
        if px.save(path):
            self.status.showMessage(f'  Exported  ·  {path}')
        else:
            QMessageBox.critical(self, 'Export Error', 'Failed to save image.')

    # ── ui state ──────────────────────────────────────────────────────────────

    def _update_ui_state(self):
        has = bool(self._sites)
        self.design_combo.setEnabled(has)
        self.mkey_combo.setEnabled(has)
        self.low_edit.setEnabled(has)
        self.high_edit.setEnabled(has)

# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Wafer Map Viewer')
    app.setStyle('Fusion')
    app.setWindowIcon(make_app_icon())
    win = MainWindow()
    win.show()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        win._load_kdf(sys.argv[1])
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
