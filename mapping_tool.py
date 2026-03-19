"""
Wafer Map Viewer  —  Keithley ACS KDF V1.2
Displays any KDF file as an interactive wafer map.

Requirements:  pip install PySide6
Usage:         python wafer_mapper_light.py [file.kdf]
"""

import sys, os, re, math, statistics, xml.etree.ElementTree as ET
from collections import defaultdict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QTreeWidget, QTreeWidgetItem, QGroupBox,
    QLineEdit, QFormLayout, QFrame, QStatusBar, QComboBox,
    QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QToolBar, QSizePolicy, QPushButton
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
    "neutral_bg":    "#dfe8f3",   # shown when no limits set — NOT green/red
    "neutral_fg":    "#2c4a6e",
    "neutral_border":"#90a8c4",
    "fail_bg":       "#fce8e8",
    "fail_fg":       "#b71c1c",
    "fail_border":   "#e57373",
    "nodata_bg":     "#eeecf5",
    "nodata_fg":     "#7060a0",
    "nodata_border": "#b0a8d0",
    "ghost_bg":      "#eae7f2",
    "ghost_fg":      "#7a7090",
    "ghost_border":  "#b8b0cc",
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
QLineEdit{background-color:""" + T['bg_panel'] + """;border:1px solid """ + T['border'] + """;
    border-radius:5px;padding:5px 10px;color:""" + T['text_primary'] + """;font-size:13px;min-height:28px;}
QLineEdit:focus{border:1px solid """ + T['accent'] + """;}
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
#  APP ICON  (generated, no image file needed)
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
        disc = QRadialGradient(cx - r * 0.2, cy - r * 0.25, r * 1.35)
        disc.setColorAt(0,    QColor("#2d5490"))
        disc.setColorAt(0.65, QColor("#1a3460"))
        disc.setColorAt(1.0,  QColor("#0c1e3a"))
        p.setBrush(QBrush(disc))
        p.setPen(QPen(QColor("#5588cc"), max(1.0, sz / 18.0)))
        p.drawEllipse(QPointF(cx, cy), r, r)
        nw = r * 0.36; nh = max(2.0, sz * 0.05)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.setPen(Qt.NoPen); p.setBrush(Qt.transparent)
        p.drawRect(QRectF(cx - nw/2, cy + r - nh, nw, nh + 1))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setPen(QPen(QColor("#5588cc"), max(1.0, sz / 20.0)))
        p.drawLine(QPointF(cx - nw/2, cy + r - nh), QPointF(cx + nw/2, cy + r - nh))
        colors = [QColor("#3dba6f"), QColor("#3dba6f"), QColor("#8a98b0"),
                  QColor("#3dba6f"), QColor("#3dba6f"), QColor("#d95555"),
                  QColor("#8a98b0"), QColor("#3dba6f"), QColor("#3dba6f")]
        ge = r * 1.08; cs = ge / 3.0; gap = max(0.6, cs * 0.12)
        gx0 = cx - ge / 2; gy0 = cy - ge / 2
        p.setPen(QPen(QColor("#0c1e3a"), max(0.5, gap * 0.4)))
        for row in range(3):
            for col in range(3):
                rx = gx0 + col*cs + gap; ry = gy0 + row*cs + gap
                rw = rh = cs - gap * 2
                if rw > 0:
                    p.setBrush(QBrush(colors[row*3+col]))
                    p.drawRoundedRect(QRectF(rx, ry, rw, rh),
                                      max(0.5, rw*0.18), max(0.5, rw*0.18))
        p.end()
        icon.addPixmap(pix)
    return icon

# ─────────────────────────────────────────────────────────────────────────────
#  KDF PARSER  — handles any KDF V1.2 file generically
# ─────────────────────────────────────────────────────────────────────────────

def parse_kdf(filepath: str):
    """
    Parse a Keithley ACS KDF V1.2 file.

    Returns
    -------
    header  : dict  — key/value pairs from the file header
    sites   : list  — each entry is a dict:
                        { 'name': str, 'x': int, 'y': int,
                          'subsites': { sub_num: { 'param@test': float } } }
    params  : list[str] — sorted unique 'param@test' measurement keys
    tests   : list[str] — sorted unique test names
    """
    header: dict = {}
    sites:  list = []
    mkeys:  set  = set()
    tkeys:  set  = set()

    with open(filepath, 'r', errors='replace') as fh:
        lines = [l.rstrip('\r\n') for l in fh]

    # ── header ────────────────────────────────────────────────────────────────
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == '<EOH>':
            i += 1
            break
        if ',' in stripped:
            k, _, v = stripped.partition(',')
            header[k.strip()] = v.strip()
        i += 1

    # skip the optional wafer-identification line (e.g. "Tails_W24_DC,,1,1")
    if i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('Site_'):
        i += 1

    # ── site blocks ───────────────────────────────────────────────────────────
    current = None
    while i < len(lines):
        raw = lines[i]; i += 1
        stripped = raw.strip()
        if not stripped:
            continue

        if stripped == '<EOS>':
            if current is not None:
                sites.append(current)
            current = None
            continue

        if stripped.startswith('Site_'):
            if current is not None:
                sites.append(current)
            parts = stripped.split(',')
            name  = parts[0].strip()
            try:
                x = int(parts[1].strip())
                y = int(parts[2].strip())
            except (IndexError, ValueError):
                # fall back to decoding name: Site_p3n12 → x=3, y=-12
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

        # measurement line:  param@test@subsite#N,value
        if '@' in stripped and ',' in stripped:
            key_part, _, val_str = stripped.partition(',')
            parts = key_part.split('@')
            if len(parts) >= 3:
                param    = parts[0].strip()
                test     = parts[1].strip()
                sub_raw  = parts[2].strip()
                try:
                    sub_num = int(sub_raw.split('#')[1])
                except (IndexError, ValueError):
                    sub_num = 1
                try:
                    value = float(val_str.strip())
                except ValueError:
                    value = None

                mkey = f"{param}@{test}"
                mkeys.add(mkey)
                tkeys.add(test)

                if sub_num not in current['subsites']:
                    current['subsites'][sub_num] = {}
                current['subsites'][sub_num][mkey] = value

    if current is not None:
        sites.append(current)

    return header, sites, sorted(mkeys), sorted(tkeys)


def get_site_value(site: dict, mkey: str) -> float | None:
    """Average a measurement across all subsites of a site."""
    values = [
        v for sub in site['subsites'].values()
        for k, v in sub.items()
        if k == mkey and v is not None and math.isfinite(v)
    ]
    return statistics.mean(values) if values else None


def si_fmt(v: float | None) -> str:
    """Format a float with SI prefix (p, n, µ, m, k, M …)."""
    if v is None or not math.isfinite(v):
        return 'N/A'
    if v == 0:
        return '0'
    av = abs(v)
    for factor, suffix in ((1e12,'T'),(1e9,'G'),(1e6,'M'),(1e3,'k'),
                           (1,''),  (1e-3,'m'),(1e-6,'µ'),(1e-9,'n'),
                           (1e-12,'p'),(1e-15,'f')):
        if av >= factor * 0.9999:
            scaled = v / factor
            fmt = '.3g' if abs(scaled) >= 10 else '.4g'
            return f"{scaled:{fmt}}{suffix}"
    return f"{v:.3e}"

# ─────────────────────────────────────────────────────────────────────────────
#  XML DESIGN PARSER  (optional overlay)
# ─────────────────────────────────────────────────────────────────────────────

class XMLDesign:
    __slots__ = ('diameter_in','die_size_x_mm','die_size_y_mm','orientation',
                 'origin_x','origin_y','equipment_id','operator','process_level',
                 'project','slots','site_names','site_coords','margin_count',
                 'raw_filename')
    def __init__(self):
        self.diameter_in = 8.0; self.die_size_x_mm = 0.0; self.die_size_y_mm = 0.0
        self.orientation = ''; self.origin_x = 0; self.origin_y = 0
        self.equipment_id = ''; self.operator = ''; self.process_level = ''
        self.project = ''; self.slots = []; self.site_names = []
        self.site_coords = {}; self.margin_count = 0; self.raw_filename = ''


def _decode_site_name(name: str):
    m = re.match(r'Site_([pn])(\d+)([pn])(\d+)$', name.strip())
    if m:
        xs, xv, ys, yv = m.groups()
        return int(xv)*(1 if xs=='p' else -1), int(yv)*(1 if ys=='p' else -1)
    return None, None


def load_xml_design(path: str) -> XMLDesign:
    d = XMLDesign(); d.raw_filename = os.path.basename(path)
    root = ET.parse(path).getroot()
    head = root.find('head')
    if head is not None:
        try:   d.diameter_in   = float(head.findtext('diameter','8'))
        except: pass
        try:   d.die_size_x_mm = float(head.findtext('diesizex','0'))
        except: pass
        try:   d.die_size_y_mm = float(head.findtext('diesizey','0'))
        except: pass
        d.orientation  = (head.findtext('orientation') or '').strip()
        d.project      = (head.findtext('project')     or '').strip()
        try:   d.margin_count = int(head.findtext('margin','0'))
        except: pass
        try:
            ox, oy = (head.findtext('origin','0,0') or '0,0').split(',')
            d.origin_x, d.origin_y = int(ox.strip()), int(oy.strip())
        except: pass
    cdf = root.find('cdf')
    if cdf is not None:
        rep = cdf.find('report')
        if rep is not None:
            d.equipment_id  = (rep.findtext('equipment_id')       or '').strip()
            d.operator      = (rep.findtext('operator')           or '').strip()
            d.process_level = (rep.findtext('test_process_level') or '').strip()
        for slot in (cdf.find('slots') or []):
            parts = (slot.text or '').split(',')
            if len(parts) >= 2:
                d.slots.append((parts[0].strip(), parts[1].strip()))
    pat = root.find('patterns')
    if pat is not None:
        p1 = pat.find('Pattern_1')
        if p1 is not None:
            raw = p1.findtext('sites','')
            names = [s.strip() for s in re.split(r'[,\n\r]+', raw) if s.strip()]
            d.site_names = names
            for name in names:
                x, y = _decode_site_name(name)
                if x is not None:
                    d.site_coords[name] = (x, y)
    return d

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
        self._rects        = {}    # site_name → QRectF  (screen coords)
        self.design        = None  # XMLDesign | None
        self._ghost        = {}    # name → fake site dict

        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    # ── public interface ─────────────────────────────────────────────────────

    def load(self, sites, values, lo, hi, mkey=''):
        self.sites = sites; self.values = values
        self.low_limit = lo; self.high_limit = hi; self.mkey = mkey
        self.selected_site = None; self._hover = None
        self._rebuild_ghosts(); self.update()

    def set_design(self, design):
        self.design = design; self._rebuild_ghosts(); self.update()

    def _rebuild_ghosts(self):
        self._ghost = {}
        if self.design is None:
            return
        kdf_names = {s['name'] for s in self.sites}
        for name in self.design.site_names:
            if name not in kdf_names and name in self.design.site_coords:
                x, y = self.design.site_coords[name]
                self._ghost[name] = {'name': name, 'x': x, 'y': y}

    # ── helpers ──────────────────────────────────────────────────────────────

    @property
    def _limits_active(self):
        return self.low_limit is not None or self.high_limit is not None

    def _bounds(self):
        all_s = self.sites + list(self._ghost.values())
        if not all_s:
            return -1, 1, -1, 1
        xs = [s['x'] for s in all_s]; ys = [s['y'] for s in all_s]
        return min(xs), max(xs), min(ys), max(ys)

    def _layout(self, x0, x1, y0, y1, w, h):
        pad = 64
        cell = min((w - 2*pad) / max(x1-x0+1, 1),
                   (h - 2*pad) / max(y1-y0+1, 1))
        ox = (w - cell*(x1-x0+1)) / 2
        oy = (h - cell*(y1-y0+1)) / 2
        return ox, oy, cell

    def _die_color(self, name, ghost=False):
        """Returns (bg, fg, border) QColors."""
        if ghost:
            return QColor(T['ghost_bg']), QColor(T['ghost_fg']), QColor(T['ghost_border'])
        v = self.values.get(name)
        if v is None:
            return QColor(T['nodata_bg']), QColor(T['nodata_fg']), QColor(T['nodata_border'])
        if not self._limits_active:
            return QColor(T['neutral_bg']), QColor(T['neutral_fg']), QColor(T['neutral_border'])
        lo, hi = self.low_limit, self.high_limit
        passed = (lo is None or v >= lo) and (hi is None or v <= hi)
        if passed:
            return QColor(T['pass_bg']), QColor(T['pass_fg']), QColor(T['pass_border'])
        return QColor(T['fail_bg']), QColor(T['fail_fg']), QColor(T['fail_border'])

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()

        # background
        p.fillRect(0, 0, w, h, QColor(T['bg_app']))
        p.setPen(QPen(QColor(T['border']), 1.0))
        for gx in range(0, w + 28, 28):
            for gy in range(0, h + 28, 28):
                p.drawPoint(gx, gy)

        all_s = self.sites + list(self._ghost.values())
        if not all_s:
            p.setPen(QColor(T['text_dim']))
            p.setFont(QFont('Segoe UI', 14))
            p.drawText(self.rect(), Qt.AlignCenter, 'Open a KDF file to begin')
            return

        x0, x1, y0, y1 = self._bounds()
        ox, oy, cell   = self._layout(x0, x1, y0, y1, w, h)
        cols = x1 - x0 + 1; rows = y1 - y0 + 1
        cx   = ox + cell * cols / 2
        cy   = oy + cell * rows / 2

        # wafer radius — physical if design loaded, estimated otherwise
        if self.design and self.design.die_size_x_mm > 0:
            ppm    = cell / max(self.design.die_size_x_mm, self.design.die_size_y_mm)
            radius = (self.design.diameter_in * 25.4 / 2) * ppm
        else:
            radius = min(cell * cols, cell * rows) / 2 + cell * 0.6

        # disc shadow
        shad = QRadialGradient(cx+5, cy+5, radius+8)
        shad.setColorAt(0,   QColor(0,0,0, 28))
        shad.setColorAt(0.8, QColor(0,0,0, 10))
        shad.setColorAt(1.0, QColor(0,0,0,  0))
        p.setBrush(QBrush(shad)); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx+5, cy+5), radius+8, radius+8)

        # disc
        wg = QRadialGradient(cx - radius*0.2, cy - radius*0.25, radius*1.4)
        wg.setColorAt(0,    QColor('#ffffff'))
        wg.setColorAt(0.55, QColor(T['wafer_bg']))
        wg.setColorAt(1.0,  QColor('#d8e3ef'))
        p.setBrush(QBrush(wg))
        p.setPen(QPen(QColor(T['wafer_edge']), 1.5))
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # flat notch at bottom
        nw = radius * 0.24
        p.setPen(Qt.NoPen); p.setBrush(QColor(T['bg_app']))
        p.drawRect(QRectF(cx - nw/2, cy + radius - 6, nw, 10))
        p.setPen(QPen(QColor(T['wafer_edge']), 2))
        p.drawLine(QPointF(cx - nw/2, cy + radius - 4),
                   QPointF(cx + nw/2, cy + radius - 4))

        # fonts
        fs   = max(7, int(cell * 0.15))
        vfnt = QFont('Consolas', fs, QFont.Bold)
        cfnt = QFont('Consolas', max(6, fs - 2))
        self._rects = {}

        # ghost dies (behind data dies)
        for name, gs in self._ghost.items():
            rect = self._cell_rect(gs['x'], gs['y'], x0, y1, ox, oy, cell)
            bg, _, bc = self._die_color(name, ghost=True)
            p.setBrush(QBrush(bg))
            p.setPen(QPen(bc, 0.5, Qt.DotLine))
            p.drawRoundedRect(rect, 3, 3)

        # data dies
        for site in self.sites:
            rect = self._cell_rect(site['x'], site['y'], x0, y1, ox, oy, cell)
            self._rects[site['name']] = rect
            bg, fg, bc = self._die_color(site['name'])

            is_sel = self.selected_site and site['name'] == self.selected_site['name']
            is_hov = self._hover and site['name'] == self._hover['name']

            # cell shadow
            if cell > 30:
                p.setBrush(QColor(0,0,0,14)); p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(rect.x()+2, rect.y()+2, rect.width(), rect.height()), 3, 3)

            # cell fill
            cg = QLinearGradient(rect.topLeft(), rect.bottomRight())
            cg.setColorAt(0, bg.lighter(108)); cg.setColorAt(1, bg)
            p.setBrush(QBrush(cg))
            p.setPen(QPen(QColor(T['selected']), 2.5) if is_sel
                     else QPen(QColor(T['hover_border']), 2) if is_hov
                     else QPen(bc, 1))
            p.drawRoundedRect(rect, 3, 3)

            # value text
            v = self.values.get(site['name'])
            if v is not None and cell > 28:
                p.setFont(vfnt); p.setPen(fg)
                p.drawText(rect, Qt.AlignCenter, si_fmt(v))

            # coordinate label at large zoom
            if cell > 58:
                p.setFont(cfnt); p.setPen(QColor(T['text_dim']))
                px_ = ox + (site['x'] - x0) * cell
                py_ = oy + (y1 - site['y']) * cell
                mg  = max(1.5, cell * 0.04)
                cr  = QRectF(px_+mg+2, py_+mg+1, cell-2*mg-2, cell*0.28)
                p.drawText(cr, Qt.AlignLeft | Qt.AlignTop,
                           f"{site['x']},{site['y']}")

        self._draw_legend(p, w, h)
        if self.design:
            self._draw_badge(p, w)

    def _cell_rect(self, sx, sy, x0, y1, ox, oy, cell) -> QRectF:
        mg = max(1.5, cell * 0.04)
        px = ox + (sx - x0) * cell
        py = oy + (y1 - sy) * cell
        return QRectF(px + mg, py + mg, cell - 2*mg, cell - 2*mg)

    def _draw_legend(self, p, w, h):
        if self._limits_active:
            items = [(T['pass_bg'], T['pass_fg'], 'Pass'),
                     (T['fail_bg'], T['fail_fg'], 'Fail'),
                     (T['nodata_bg'], T['nodata_fg'], 'No data')]
        else:
            items = [(T['neutral_bg'], T['neutral_fg'], 'No limits set'),
                     (T['nodata_bg'],  T['nodata_fg'],  'No data')]
        if self._ghost:
            items.append((T['ghost_bg'], T['ghost_fg'], 'Design only'))

        bh = len(items) * 22 + 16; lx = 14; ly = h - bh - 10
        p.setBrush(QColor(255,255,255,215)); p.setPen(QPen(QColor(T['border']),1))
        p.drawRoundedRect(QRectF(lx-6, ly-8, 178, bh), 5, 5)
        p.setFont(QFont('Segoe UI', 11))
        for bg_hex, fg_hex, label in items:
            p.setBrush(QBrush(QColor(bg_hex))); p.setPen(QPen(QColor(fg_hex), 1))
            p.drawRoundedRect(QRectF(lx, ly, 14, 14), 2, 2)
            p.setPen(QColor(T['text_primary']))
            p.drawText(int(lx+20), int(ly+11), label)
            ly += 22

    def _draw_badge(self, p, w):
        d = self.design
        lines = [f"\u2300 {d.diameter_in}\"  {d.die_size_x_mm:.2f}\u00d7{d.die_size_y_mm:.2f} mm"]
        if d.equipment_id:
            lines.append(d.equipment_id)
        bw = 210; bh = len(lines) * 18 + 12
        rx = w - bw - 12; ry = 10
        p.setBrush(QColor(255,255,255,200)); p.setPen(QPen(QColor(T['border']),1))
        p.drawRoundedRect(QRectF(rx, ry, bw, bh), 5, 5)
        p.setFont(QFont('Segoe UI', 10)); p.setPen(QColor(T['text_secondary']))
        for i, line in enumerate(lines):
            p.drawText(int(rx+8), int(ry+16+i*18), line)

    # ── mouse ─────────────────────────────────────────────────────────────────

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
        lo = QVBoxLayout(self); lo.setContentsMargins(8,8,8,8); lo.setSpacing(8)

        self.title = QLabel('Click a die to inspect')
        self.title.setWordWrap(True)
        self.title.setStyleSheet(
            f'font-weight:bold;font-size:13px;color:{T["accent_dark"]};'
            f'padding:5px 8px;background:{T["accent_dim"]};'
            f'border-radius:5px;border-left:3px solid {T["accent"]};')
        lo.addWidget(self.title)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Measurement', 'Subsite', 'Value'])
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
            f'  {site["name"]}   \u00b7   X\u202f=\u202f{site["x"]},  Y\u202f=\u202f{site["y"]}')

        # collect all subsite rows, sorted by (mkey, sub_num)
        rows = []
        for sub_num in sorted(site['subsites']):
            for mkey, val in sorted(site['subsites'][sub_num].items()):
                rows.append((mkey, f'#{sub_num}', val))

        self.table.setRowCount(len(rows))
        for i, (mkey, sub, val) in enumerate(rows):
            mi = QTableWidgetItem(mkey)
            mi.setFont(QFont('Segoe UI', 12))
            self.table.setItem(i, 0, mi)

            si = QTableWidgetItem(sub)
            si.setForeground(QColor(T['text_secondary']))
            si.setFont(QFont('Segoe UI', 12))
            self.table.setItem(i, 1, si)

            vi = QTableWidgetItem(si_fmt(val) if val is not None else 'N/A')
            vi.setForeground(QColor(T['accent_dark']))
            vi.setFont(QFont('Consolas', 12, QFont.Bold))
            self.table.setItem(i, 2, vi)

# ─────────────────────────────────────────────────────────────────────────────
#  STATISTICS PANEL
# ─────────────────────────────────────────────────────────────────────────────

class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self); lo.setContentsMargins(8,8,8,8); lo.setSpacing(6)
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

        n       = len(vals)
        mean_v  = statistics.mean(vals)
        std_v   = statistics.pstdev(vals)          # population stdev
        med_v   = statistics.median(vals)
        min_v   = min(vals)
        max_v   = max(vals)
        passed  = sum(1 for v in vals
                      if (lo is None or v >= lo) and (hi is None or v <= hi))
        failed  = n - passed
        yld     = passed / n * 100 if n else 0.0

        rows = [
            ('Count',     str(n)),
            ('Mean',      si_fmt(mean_v)),
            ('Std Dev',   si_fmt(std_v)),
            ('Min',       si_fmt(min_v)),
            ('Max',       si_fmt(max_v)),
            ('Median',    si_fmt(med_v)),
            ('3\u03c3',   f'{si_fmt(mean_v - 3*std_v)}  \u2192  {si_fmt(mean_v + 3*std_v)}'),
            ('Pass',      str(passed)),
            ('Fail',      str(failed)),
            ('Yield',     f'{yld:.1f}%'),
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
            elif k == 'Pass':
                vi.setForeground(QColor(T['pass_fg']))
            elif k == 'Fail':
                vi.setForeground(QColor(T['fail_fg']))
            else:
                vi.setForeground(QColor(T['text_primary']))
            self.table.setItem(i, 1, vi)

# ─────────────────────────────────────────────────────────────────────────────
#  DESIGN INFO PANEL
# ─────────────────────────────────────────────────────────────────────────────

class DesignInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self); lo.setContentsMargins(8,8,8,8); lo.setSpacing(8)

        self.title = QLabel('No design file loaded')
        self.title.setStyleSheet(
            f'font-weight:bold;font-size:13px;color:{T["accent_dark"]};'
            f'padding:5px 8px;background:{T["accent_dim"]};'
            f'border-radius:5px;border-left:3px solid {T["accent"]};')
        lo.addWidget(self.title)

        lo.addWidget(self._section('Wafer / Equipment'))
        self.info_table = self._make_table(['Field','Value'])
        lo.addWidget(self.info_table)

        lo.addWidget(self._section('Cassette Slots'))
        self.slots_table = self._make_table(['Cassette','Wafer ID'])
        self.slots_table.setMaximumHeight(160)
        lo.addWidget(self.slots_table)
        lo.addStretch()

    def _section(self, text):
        l = QLabel(text)
        l.setStyleSheet(f'color:{T["text_secondary"]};font-size:11px;font-weight:bold;')
        return l

    def _make_table(self, headers):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        t.setShowGrid(False)
        return t

    def show_design(self, d: XMLDesign | None):
        if d is None:
            self.title.setText('No design file loaded')
            self.info_table.setRowCount(0)
            self.slots_table.setRowCount(0)
            return

        self.title.setText(f'  {d.raw_filename}')
        rows = [
            ('Diameter',      f'{d.diameter_in}"'),
            ('Die size',      f'{d.die_size_x_mm:.3g} \u00d7 {d.die_size_y_mm:.3g} mm'),
            ('Orientation',   d.orientation),
            ('Project',       d.project),
            ('Equipment',     d.equipment_id),
            ('Operator',      d.operator),
            ('Process level', d.process_level),
            ('Origin (X,Y)',  f'{d.origin_x}, {d.origin_y}'),
            ('Design sites',  str(len(d.site_names))),
        ]
        self.info_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            ki = QTableWidgetItem(k)
            ki.setForeground(QColor(T['text_secondary']))
            ki.setFont(QFont('Segoe UI', 12))
            self.info_table.setItem(i, 0, ki)
            vi = QTableWidgetItem(v)
            vi.setFont(QFont('Segoe UI', 12))
            self.info_table.setItem(i, 1, vi)

        self.slots_table.setRowCount(len(d.slots))
        for i, (cas, wid) in enumerate(d.slots):
            self.slots_table.setItem(i, 0, QTableWidgetItem(cas))
            self.slots_table.setItem(i, 1, QTableWidgetItem(wid))

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Wafer Map Viewer')
        self.resize(1380, 860)
        self.setStyleSheet(SS)
        self.setWindowIcon(make_app_icon())

        self._header:  dict       = {}
        self._sites:   list       = []
        self._mkeys:   list[str]  = []   # 'param@test' keys
        self._limits:  dict       = {}   # mkey → (lo, hi)
        self._current_mkey: str | None = None
        self._filepath: str | None     = None
        self._design:  XMLDesign | None = None

        self._build_ui()
        self._update_ui_state()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # toolbar
        tb = QToolBar('Main', self)
        tb.setIconSize(QSize(18,18)); tb.setMovable(False)
        self.addToolBar(tb)

        for label, slot in [('  Open KDF\u2026', self.open_file),
                             ('  Load XML Design\u2026', self.open_xml)]:
            a = QAction(label, self); a.triggered.connect(slot); tb.addAction(a)
        tb.addSeparator()
        for label, slot in [('  Clear Design', self.clear_design),
                             ('  Export Map\u2026', self.export_map)]:
            a = QAction(label, self); a.triggered.connect(slot); tb.addAction(a)
        tb.addSeparator()

        sp = QWidget(); sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(sp)
        self.lbl_file = QLabel('No file loaded  ')
        self.lbl_file.setStyleSheet(
            f'color:{T["text_secondary"]};font-size:12px;padding-right:10px;')
        tb.addWidget(self.lbl_file)
        self.lbl_xml = QLabel('')
        self.lbl_xml.setStyleSheet(
            'color:#7a5800;font-size:11px;background:#fff8e1;'
            'border-radius:3px;padding:2px 8px;')
        self.lbl_xml.setVisible(False); tb.addWidget(self.lbl_xml)

        # central widget
        cw = QWidget(); self.setCentralWidget(cw)
        mh = QHBoxLayout(cw); mh.setSpacing(10); mh.setContentsMargins(10,10,10,10)

        # ── left panel ────────────────────────────────────────────────────────
        left = QWidget(); left.setFixedWidth(282)
        lv = QVBoxLayout(left); lv.setSpacing(10); lv.setContentsMargins(0,0,0,0)

        # file info
        ib = QGroupBox('File Information')
        iform = QFormLayout(ib); iform.setSpacing(6)
        iform.setLabelAlignment(Qt.AlignRight)

        def mkval():
            l = QLabel('\u2014')
            l.setStyleSheet(
                f'color:{T["text_primary"]};font-weight:600;font-size:13px;')
            return l

        self.lbl_lot   = mkval(); self.lbl_sys  = mkval()
        self.lbl_stt   = mkval(); self.lbl_cnt  = mkval()
        self.lbl_tests = mkval()

        for label_text, widget in [
                ('Lot',      self.lbl_lot),
                ('System',   self.lbl_sys),
                ('Start',    self.lbl_stt),
                ('Sites',    self.lbl_cnt),
                ('Tests',    self.lbl_tests),
        ]:
            kl = QLabel(label_text)
            kl.setStyleSheet(f'color:{T["text_secondary"]};font-size:12px;')
            iform.addRow(kl, widget)
        lv.addWidget(ib)

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
        for label_text, attr in [('Low', 'low_edit'), ('High', 'high_edit')]:
            row = QHBoxLayout()
            rl = QLabel(label_text)
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
        cl = QVBoxLayout(canvas_wrap); cl.setContentsMargins(4,4,4,4)
        self.canvas = WaferCanvas()
        self.canvas.siteClicked.connect(self._on_die_clicked)
        cl.addWidget(self.canvas)
        mh.addWidget(canvas_wrap, stretch=3)

        # ── right panel ───────────────────────────────────────────────────────
        right = QWidget(); right.setFixedWidth(310)
        rv = QVBoxLayout(right); rv.setContentsMargins(0,0,0,0)
        tabs = QTabWidget(); rv.addWidget(tabs)

        self.detail_panel = SiteDetailPanel()
        tabs.addTab(self.detail_panel, 'Die Detail')

        self.stats_panel = StatsPanel()
        tabs.addTab(self.stats_panel, 'Statistics')

        self.design_panel = DesignInfoPanel()
        tabs.addTab(self.design_panel, 'Design')

        mh.addWidget(right)

        # status bar
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.status.showMessage('  Ready  \u00b7  open a KDF file to begin')

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

        self._filepath      = path
        self._header        = header
        self._sites         = sites
        self._mkeys         = params
        self._limits        = {}
        self._current_mkey  = None

        # header labels
        self.lbl_file.setText(f'  {os.path.basename(path)}  ')
        self.lbl_lot.setText(header.get('LOT', '\u2014'))
        self.lbl_sys.setText(header.get('SYS', '\u2014')
                             or header.get('TST', '\u2014'))
        self.lbl_stt.setText(header.get('STT', '\u2014'))
        self.lbl_cnt.setText(str(len(sites)))
        self.lbl_tests.setText(str(len(tests)))

        # update window title
        lot = header.get('LOT', os.path.basename(path))
        self.setWindowTitle(f'Wafer Map Viewer  \u00b7  {lot}')

        # measurement combo
        self.mkey_combo.blockSignals(True)
        self.mkey_combo.clear()
        self.mkey_combo.addItems(params)
        self.mkey_combo.blockSignals(False)

        # test filter tree  (group params by test name)
        self.test_tree.clear()
        groups: dict[str, list[str]] = defaultdict(list)
        for mk in params:
            parts = mk.split('@')
            test  = parts[1] if len(parts) >= 2 else 'Other'
            groups[test].append(parts[0])

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
            f'  Loaded {len(sites)} sites  \u00b7  '
            f'{len(params)} measurements  \u00b7  '
            f'{len(tests)} tests  \u00b7  {os.path.basename(path)}')

    def open_xml(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Load XML Design File', '',
            'ACS XML Files (*.xml);;All Files (*)')
        if path:
            self._load_xml(path)

    def _load_xml(self, path: str):
        try:
            d = load_xml_design(path)
        except Exception as e:
            QMessageBox.critical(self, 'XML Error',
                                 f'Could not read XML file:\n{e}')
            return
        self._design = d
        self.canvas.set_design(d)
        self.design_panel.show_design(d)
        fn = os.path.basename(path)
        self.lbl_xml.setText(f'  XML: {fn}  ')
        self.lbl_xml.setVisible(True)
        ghost_n = len(self.canvas._ghost)
        self.status.showMessage(
            f'  Design loaded: {fn}  \u00b7  '
            f'{len(d.site_names)} sites  \u00b7  '
            f'{ghost_n} design-only dies')

    def clear_design(self):
        self._design = None
        self.canvas.set_design(None)
        self.design_panel.show_design(None)
        self.lbl_xml.setVisible(False)
        self.status.showMessage('  Design cleared')

    # ── measurement / limits ──────────────────────────────────────────────────

    def _tree_double_click(self, item, _col):
        mk = item.text(0)
        if mk in self._mkeys:
            self.mkey_combo.setCurrentText(mk)

    def _on_mkey_changed(self, mkey: str):
        if mkey not in self._mkeys:
            return
        # save current limits before switching
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
            return   # parse error already shown
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
                                    f'{label} limit must be a number '
                                    f'(e.g. 9.5 or 1e-12).')
            return None

    # ── canvas refresh ────────────────────────────────────────────────────────

    def _refresh_canvas(self):
        if not self._sites or not self._current_mkey:
            return
        mkey   = self._current_mkey
        lo, hi = self._limits.get(mkey, (None, None))
        values = {s['name']: get_site_value(s, mkey) for s in self._sites}
        self.canvas.load(self._sites, values, lo, hi, mkey=mkey)
        self.stats_panel.update_stats(values, lo, hi)
        lo_str = '\u2014' if lo is None else str(lo)
        hi_str = '\u2014' if hi is None else str(hi)
        self.status.showMessage(
            f'  {mkey}   \u00b7   Low\u202f=\u202f{lo_str}'
            f'   High\u202f=\u202f{hi_str}'
            f'   \u00b7   {len(self._sites)} sites')

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
            self.status.showMessage(f'  Exported  \u00b7  {path}')
        else:
            QMessageBox.critical(self, 'Export Error', 'Failed to save image.')

    # ── ui state ──────────────────────────────────────────────────────────────

    def _update_ui_state(self):
        has = bool(self._sites)
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
