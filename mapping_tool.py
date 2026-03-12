"""
Wafer Map Viewer — KDF File Analyser (Tkinter port)
Reads Keithley ACS KDF V1.2 files and displays an interactive wafer map.

Requirements:
    pip install numpy

Usage:
    python wafer_mapper_tk.py
    python wafer_mapper_tk.py path/to/file.kdf
"""

import sys
import os
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from collections import defaultdict

import numpy as np

# ─────────────────────────────────────────────
#  COLOUR PALETTE
# ─────────────────────────────────────────────

C_BG        = '#12121f'
C_BG2       = '#1a1a2e'
C_BG3       = '#16213e'
C_PANEL     = '#1e3a5f'
C_ACCENT    = '#4fc3f7'
C_TEXT      = '#ecf0f1'
C_TEXT_DIM  = '#bdc3c7'
C_PASS      = '#2ecc71'
C_FAIL      = '#e74c3c'
C_NODATA    = '#9b59b6'
C_SELECTED  = '#f39c12'
C_HOVER     = '#3498db'
C_BORDER    = '#2c3e50'
C_STATUS_BG = '#0d0d1a'

# ─────────────────────────────────────────────
#  KDF PARSER
# ─────────────────────────────────────────────

def parse_kdf(filepath):
    header = {}
    sites = []
    measurements_set = set()
    tests_set = set()

    with open(filepath, 'r', errors='replace') as f:
        content = f.read()

    lines = [l.strip() for l in content.splitlines()]

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

    # Skip wafer/lot line
    if i < len(lines):
        i += 1

    current_site = None

    while i < len(lines):
        line = lines[i]
        i += 1

        if not line:
            continue

        if line == '<EOS>':
            if current_site is not None:
                sites.append(current_site)
            current_site = None
            continue

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
            continue

        if current_site is None:
            continue

        if '@' in line and ',' in line:
            key_part, _, val_str = line.partition(',')
            parts = key_part.split('@')
            if len(parts) >= 3:
                param = parts[0]
                test  = parts[1]
                sub_part = parts[2]
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

    if current_site is not None:
        sites.append(current_site)

    tests = sorted(tests_set)
    measurements = sorted(measurements_set)
    return header, sites, tests, measurements


def get_site_value(site, mkey, subsite=None):
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
#  FORMATTING HELPERS
# ─────────────────────────────────────────────

def fmt_value(v):
    if v is None:
        return 'N/A'
    av = abs(v)
    if av == 0:       return '0'
    if av >= 1:       return f'{v:.3g}'
    if av >= 1e-3:    return f'{v*1e3:.3g}m'
    if av >= 1e-6:    return f'{v*1e6:.3g}µ'
    if av >= 1e-9:    return f'{v*1e9:.3g}n'
    if av >= 1e-12:   return f'{v*1e12:.3g}p'
    return f'{v:.3e}'


def fmt_stat(v):
    av = abs(v)
    if av == 0:       return '0'
    if av >= 1:       return f'{v:.5g}'
    if av >= 1e-3:    return f'{v*1e3:.4g} m'
    if av >= 1e-6:    return f'{v*1e6:.4g} µ'
    if av >= 1e-9:    return f'{v*1e9:.4g} n'
    if av >= 1e-12:   return f'{v*1e12:.4g} p'
    return f'{v:.4e}'


def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def blend_color(base_hex, factor):
    """Lighten a hex colour by blending toward white."""
    r, g, b = hex_to_rgb(base_hex)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f'#{r:02x}{g:02x}{b:02x}'


# ─────────────────────────────────────────────
#  WAFER CANVAS
# ─────────────────────────────────────────────

class WaferCanvas(tk.Canvas):
    def __init__(self, master, on_site_click=None, **kw):
        super().__init__(master, bg=C_BG, highlightthickness=0, **kw)
        self.on_site_click = on_site_click

        self.sites        = []
        self.values       = {}
        self.low_limit    = None
        self.high_limit   = None
        self.selected_site = None
        self._hover_site  = None
        self._site_rects  = {}   # name -> (x1,y1,x2,y2)

        self.bind('<Configure>', lambda e: self._redraw())
        self.bind('<Motion>',    self._on_motion)
        self.bind('<Button-1>',  self._on_click)
        self.bind('<Leave>',     self._on_leave)

    def load(self, sites, values, low_limit, high_limit, mkey=''):
        self.sites        = sites
        self.values       = values
        self.low_limit    = low_limit
        self.high_limit   = high_limit
        self.mkey         = mkey
        self.selected_site = None
        self._hover_site  = None
        self._redraw()

    def _grid_bounds(self):
        if not self.sites:
            return -1, 1, -1, 1
        xs = [s['x'] for s in self.sites]
        ys = [s['y'] for s in self.sites]
        return min(xs), max(xs), min(ys), max(ys)

    def _transform(self, xmin, xmax, ymin, ymax):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 2 or h < 2:
            return 30, 30, 20
        cols = xmax - xmin + 1
        rows = ymax - ymin + 1
        padding = 55
        cell_w = (w - 2*padding) / max(cols, 1)
        cell_h = (h - 2*padding) / max(rows, 1)
        cell   = min(cell_w, cell_h)
        ox = (w - cell*cols) / 2
        oy = (h - cell*rows) / 2
        return ox, oy, cell

    def _site_color(self, name, hover=False, selected=False):
        v = self.values.get(name)
        if v is None:
            base = C_NODATA
        else:
            lo, hi = self.low_limit, self.high_limit
            passed = True
            if lo is not None and v < lo: passed = False
            if hi is not None and v > hi: passed = False
            base = C_PASS if passed else C_FAIL

        if selected:
            return blend_color(base, 0.45), C_SELECTED, 2
        if hover:
            return blend_color(base, 0.25), '#ffffff', 1
        return base, C_BORDER, 1

    def _redraw(self):
        self.delete('all')
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 2 or h < 2:
            return

        if not self.sites:
            self.create_text(w//2, h//2, text='Load a KDF file to begin',
                             fill=C_TEXT_DIM, font=('Courier', 13))
            return

        xmin, xmax, ymin, ymax = self._grid_bounds()
        ox, oy, cell = self._transform(xmin, xmax, ymin, ymax)

        # Wafer circle
        cols = xmax - xmin + 1
        rows = ymax - ymin + 1
        cx = ox + cell*cols/2
        cy = oy + cell*rows/2
        radius = min(cell*cols, cell*rows)/2 + cell*0.55
        self.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                         outline=C_ACCENT, width=2)
        # Notch
        nx1 = cx - radius*0.22
        nx2 = cx + radius*0.22
        ny  = cy + radius - 3
        self.create_line(nx1, ny, nx2, ny, fill=C_ACCENT, width=4)

        # Sites
        self._site_rects = {}
        font_size = max(5, int(cell * 0.13))
        font      = ('Courier', font_size)
        font_small = ('Courier', max(4, font_size-2))

        for site in self.sites:
            sx, sy = site['x'], site['y']
            px = ox + (sx - xmin) * cell
            py = oy + (ymax - sy) * cell
            x1, y1 = px+1, py+1
            x2, y2 = px+cell-1, py+cell-1

            is_sel   = self.selected_site and site['name'] == self.selected_site['name']
            is_hover = self._hover_site and site['name'] == self._hover_site['name']

            fill, outline, width = self._site_color(site['name'],
                                                     hover=is_hover,
                                                     selected=is_sel)
            tag = f'site_{site["name"]}'
            self.create_rectangle(x1, y1, x2, y2,
                                  fill=fill, outline=outline,
                                  width=width, tags=(tag,))

            self._site_rects[site['name']] = (x1, y1, x2, y2)

            # Value label
            v = self.values.get(site['name'])
            if v is not None and cell > 28:
                self.create_text((x1+x2)/2, (y1+y2)/2,
                                 text=fmt_value(v),
                                 fill=C_TEXT, font=font)

            # Coord label
            if cell > 55:
                self.create_text(x1+3, y1+3,
                                 text=f'{sx},{sy}',
                                 fill='#ffffff66',
                                 font=font_small, anchor='nw')

        # Legend
        self._draw_legend(w, h)

    def _draw_legend(self, w, h):
        lx, ly = 10, h - 78
        if self.low_limit is None and self.high_limit is None:
            items = [(C_NODATA, 'No limits set')]
        else:
            items = [(C_PASS, 'Pass'), (C_FAIL, 'Fail'), (C_NODATA, 'No Data')]

        for color, label in items:
            self.create_rectangle(lx, ly, lx+13, ly+13,
                                  fill=color, outline='#ffffff', width=1)
            self.create_text(lx+17, ly+6, text=label, fill=C_TEXT,
                             font=('Courier', 9), anchor='w')
            ly += 20

    def _site_at(self, x, y):
        for site in self.sites:
            r = self._site_rects.get(site['name'])
            if r and r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                return site
        return None

    def _on_motion(self, event):
        site = self._site_at(event.x, event.y)
        if site != self._hover_site:
            self._hover_site = site
            self.configure(cursor='hand2' if site else '')
            self._redraw()

    def _on_click(self, event):
        site = self._site_at(event.x, event.y)
        if site:
            self.selected_site = site
            self._redraw()
            if self.on_site_click:
                self.on_site_click(site)

    def _on_leave(self, event):
        self._hover_site = None
        self._redraw()


# ─────────────────────────────────────────────
#  STYLED HELPERS
# ─────────────────────────────────────────────

def styled_label(parent, text='', bold=False, color=C_TEXT, size=10, **kw):
    weight = 'bold' if bold else 'normal'
    return tk.Label(parent, text=text, bg=C_BG, fg=color,
                    font=('Courier', size, weight), **kw)


def styled_button(parent, text, command, **kw):
    btn = tk.Button(parent, text=text, command=command,
                    bg=C_PANEL, fg=C_TEXT,
                    activebackground=C_HOVER, activeforeground=C_TEXT,
                    relief='flat', bd=0, padx=10, pady=4,
                    font=('Courier', 10), cursor='hand2',
                    highlightbackground=C_ACCENT, highlightthickness=1,
                    **kw)
    return btn


def styled_entry(parent, **kw):
    e = tk.Entry(parent, bg=C_PANEL, fg=C_TEXT,
                 insertbackground=C_TEXT,
                 relief='flat', bd=3,
                 font=('Courier', 10), **kw)
    return e


def make_separator(parent, orient='horizontal'):
    return ttk.Separator(parent, orient=orient)


# ─────────────────────────────────────────────
#  STATS PANEL
# ─────────────────────────────────────────────

class StatsPanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=C_BG2, **kw)

        cols = ('Statistic', 'Value')
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Stats.Treeview',
                        background=C_BG2,
                        foreground=C_TEXT,
                        fieldbackground=C_BG2,
                        rowheight=22,
                        font=('Courier', 10))
        style.configure('Stats.Treeview.Heading',
                        background=C_PANEL,
                        foreground=C_ACCENT,
                        font=('Courier', 10, 'bold'),
                        relief='flat')
        style.map('Stats.Treeview', background=[('selected', C_HOVER)])

        self.tree = ttk.Treeview(self, columns=cols, show='headings',
                                 style='Stats.Treeview', selectmode='none')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=120, anchor='w')
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

    def update_stats(self, values_dict, low, high):
        for row in self.tree.get_children():
            self.tree.delete(row)

        vals = [v for v in values_dict.values()
                if v is not None and math.isfinite(v)]
        if not vals:
            return

        arr = np.array(vals)
        passed = sum(
            1 for v in arr
            if (low is None or v >= low) and (high is None or v <= high)
        )
        total = len(arr)
        yield_pct = passed / total * 100 if total else 0
        sigma3 = (f'{fmt_stat(arr.mean()-3*arr.std())} → '
                  f'{fmt_stat(arr.mean()+3*arr.std())}')

        rows = [
            ('Count',    str(total)),
            ('Mean',     fmt_stat(arr.mean())),
            ('Std Dev',  fmt_stat(arr.std())),
            ('Min',      fmt_stat(arr.min())),
            ('Max',      fmt_stat(arr.max())),
            ('Median',   fmt_stat(float(np.median(arr)))),
            ('3σ Range', sigma3),
            ('Pass',     str(passed)),
            ('Fail',     str(total - passed)),
            ('Yield',    f'{yield_pct:.1f}%'),
        ]

        for k, v in rows:
            iid = self.tree.insert('', 'end', values=(k, v))
            if k == 'Yield':
                color = (C_PASS if yield_pct >= 90
                         else C_FAIL if yield_pct < 70
                         else C_SELECTED)
                self.tree.tag_configure('yield', foreground=color,
                                         font=('Courier', 10, 'bold'))
                self.tree.item(iid, tags=('yield',))


# ─────────────────────────────────────────────
#  SITE DETAIL PANEL
# ─────────────────────────────────────────────

class SiteDetailPanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=C_BG2, **kw)

        self.title_lbl = tk.Label(self, text='Click a die to inspect',
                                  bg=C_BG2, fg=C_SELECTED,
                                  font=('Courier', 11, 'bold'),
                                  anchor='w')
        self.title_lbl.pack(fill='x', padx=4, pady=(4, 2))

        style = ttk.Style()
        style.configure('Detail.Treeview',
                        background=C_BG2, foreground=C_TEXT,
                        fieldbackground=C_BG2, rowheight=20,
                        font=('Courier', 9))
        style.configure('Detail.Treeview.Heading',
                        background=C_PANEL, foreground=C_ACCENT,
                        font=('Courier', 9, 'bold'), relief='flat')
        style.map('Detail.Treeview', background=[('selected', C_HOVER)])

        cols = ('Measurement', 'Subsite', 'Value')
        self.tree = ttk.Treeview(self, columns=cols, show='headings',
                                 style='Detail.Treeview', selectmode='browse')
        self.tree.heading('Measurement', text='Measurement')
        self.tree.heading('Subsite',     text='Subsite')
        self.tree.heading('Value',       text='Value')
        self.tree.column('Measurement', width=160)
        self.tree.column('Subsite',     width=55,  anchor='center')
        self.tree.column('Value',       width=90,  anchor='e')

        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

    def show_site(self, site):
        self.title_lbl.config(
            text=f'  {site["name"]}  |  X={site["x"]}, Y={site["y"]}')
        for row in self.tree.get_children():
            self.tree.delete(row)
        for sub_num in sorted(site['subsites'].keys()):
            for mkey, val in sorted(site['subsites'][sub_num].items()):
                vstr = f'{val:.6g}' if val is not None else 'N/A'
                self.tree.insert('', 'end', values=(mkey, f'#{sub_num}', vstr))


# ─────────────────────────────────────────────
#  LIMITS DIALOG
# ─────────────────────────────────────────────

class LimitsDialog(tk.Toplevel):
    def __init__(self, parent, mkey, low=None, high=None):
        super().__init__(parent)
        self.title(f'Set Limits — {mkey}')
        self.configure(bg=C_BG)
        self.resizable(False, False)
        self.result = None

        tk.Label(self, text=f'Limits for: {mkey}',
                 bg=C_BG, fg=C_ACCENT,
                 font=('Courier', 11, 'bold')).grid(
            row=0, column=0, columnspan=3, padx=14, pady=(12,6), sticky='w')

        self._low_var  = tk.BooleanVar(value=low is not None)
        self._high_var = tk.BooleanVar(value=high is not None)
        self._low_ent  = tk.StringVar(value=str(low) if low is not None else '')
        self._high_ent = tk.StringVar(value=str(high) if high is not None else '')

        for row, (label, bvar, evar) in enumerate([
                ('Low limit:',  self._low_var,  self._low_ent),
                ('High limit:', self._high_var, self._high_ent),
        ], start=1):
            cb = tk.Checkbutton(self, text=label, variable=bvar,
                                bg=C_BG, fg=C_TEXT, selectcolor=C_PANEL,
                                font=('Courier', 10),
                                activebackground=C_BG, activeforeground=C_TEXT)
            cb.grid(row=row, column=0, padx=(14,4), pady=4, sticky='w')
            ent = tk.Entry(self, textvariable=evar,
                           bg=C_PANEL, fg=C_TEXT,
                           insertbackground=C_TEXT, relief='flat', bd=3,
                           font=('Courier', 10), width=18)
            ent.grid(row=row, column=1, padx=(0,14), pady=4)

        note = tk.Label(self,
                        text='Use raw SI values (e.g. 3.2e-13 for 320 fF)',
                        bg=C_BG, fg='#888888', font=('Courier', 8))
        note.grid(row=3, column=0, columnspan=2, padx=14, pady=(0,8))

        btn_frame = tk.Frame(self, bg=C_BG)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(0,12))
        styled_button(btn_frame, '  OK  ', self._ok).pack(side='left', padx=6)
        styled_button(btn_frame, 'Cancel', self.destroy).pack(side='left', padx=6)

        self.grab_set()
        self.wait_window()

    def _ok(self):
        low = high = None
        if self._low_var.get():
            try:   low = float(self._low_ent.get())
            except ValueError:
                messagebox.showwarning('Invalid', 'Low limit must be a number.',
                                       parent=self)
                return
        if self._high_var.get():
            try:   high = float(self._high_ent.get())
            except ValueError:
                messagebox.showwarning('Invalid', 'High limit must be a number.',
                                       parent=self)
                return
        self.result = (low, high)
        self.destroy()


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Wafer Map Viewer — KDF Analyser')
        self.geometry('1300x850')
        self.configure(bg=C_BG)

        self._header   = {}
        self._sites    = []
        self._tests    = []
        self._mkeys    = []
        self._limits   = {}
        self._current_mkey = None
        self._filepath = None

        self._apply_ttk_style()
        self._build_ui()
        self._update_ui_state()

    # ── TTK global style ─────────────────────

    def _apply_ttk_style(self):
        s = ttk.Style(self)
        s.theme_use('default')
        s.configure('TNotebook',
                    background=C_BG, borderwidth=0)
        s.configure('TNotebook.Tab',
                    background=C_PANEL, foreground=C_TEXT_DIM,
                    padding=[12, 5], font=('Courier', 10))
        s.map('TNotebook.Tab',
              background=[('selected', C_HOVER)],
              foreground=[('selected', '#ffffff')])
        s.configure('Vertical.TScrollbar',
                    background=C_BG2, troughcolor=C_BG,
                    arrowcolor=C_ACCENT, bordercolor=C_BG)

    # ── Build UI ─────────────────────────────

    def _build_ui(self):
        # ── Top toolbar ──
        toolbar = tk.Frame(self, bg=C_BG3, height=36)
        toolbar.pack(side='top', fill='x')
        toolbar.pack_propagate(False)

        styled_button(toolbar, '📂  Open KDF…', self.open_file).pack(
            side='left', padx=6, pady=4)
        styled_button(toolbar, '💾  Export Map…', self.export_map).pack(
            side='left', padx=2, pady=4)

        tk.Frame(toolbar, bg=C_BORDER, width=1).pack(
            side='left', fill='y', padx=8, pady=6)

        self.lbl_file = tk.Label(toolbar, text='  No file loaded',
                                 bg=C_BG3, fg=C_ACCENT,
                                 font=('Courier', 10))
        self.lbl_file.pack(side='left')

        # ── Status bar ──
        self.status_var = tk.StringVar(
            value='Ready — open a KDF file to begin')
        status = tk.Label(self, textvariable=self.status_var,
                          bg=C_STATUS_BG, fg=C_ACCENT,
                          font=('Courier', 9), anchor='w', padx=8,
                          relief='flat', bd=0,
                          borderwidth=1)
        status.pack(side='bottom', fill='x')

        # ── Main content area ──
        content = tk.Frame(self, bg=C_BG)
        content.pack(fill='both', expand=True, padx=6, pady=6)

        # Left panel
        left = tk.Frame(content, bg=C_BG, width=270)
        left.pack(side='left', fill='y', padx=(0, 6))
        left.pack_propagate(False)
        self._build_left_panel(left)

        # Centre: wafer canvas
        self.canvas = WaferCanvas(content, on_site_click=self._on_site_clicked)
        self.canvas.pack(side='left', fill='both', expand=True)

        # Right panel: tabs
        right = tk.Frame(content, bg=C_BG, width=285)
        right.pack(side='right', fill='y', padx=(6, 0))
        right.pack_propagate(False)

        tabs = ttk.Notebook(right)
        tabs.pack(fill='both', expand=True)

        self.detail_panel = SiteDetailPanel(tabs)
        tabs.add(self.detail_panel, text='🔍  Die Detail')

        self.stats_panel = StatsPanel(tabs)
        tabs.add(self.stats_panel, text='📊  Statistics')

    def _build_left_panel(self, parent):

        def section(label):
            f = tk.LabelFrame(parent, text=f'  {label}  ',
                              bg=C_BG, fg=C_ACCENT,
                              font=('Courier', 9, 'bold'),
                              relief='groove', bd=1,
                              labelanchor='n')
            f.pack(fill='x', padx=2, pady=(0, 6))
            return f

        # ── File Info ──
        info = section('File Info')
        self.lbl_lot  = self._info_row(info, 'Lot:',    '—')
        self.lbl_sys  = self._info_row(info, 'System:', '—')
        self.lbl_stt  = self._info_row(info, 'Start:',  '—')
        self.lbl_nst  = self._info_row(info, 'Sites:',  '—')

        # ── Measurement ──
        meas = section('Measurement')
        self.mkey_combo = ttk.Combobox(meas, state='disabled',
                                       font=('Courier', 10))
        self._style_combobox()
        self.mkey_combo.pack(fill='x', padx=6, pady=6)
        self.mkey_combo.bind('<<ComboboxSelected>>', self._on_mkey_changed)

        # ── Limits ──
        lim = section('Pass / Fail Limits')

        for label, attr in [('Low:', 'low_edit'), ('High:', 'high_edit')]:
            row = tk.Frame(lim, bg=C_BG)
            row.pack(fill='x', padx=6, pady=2)
            tk.Label(row, text=label, bg=C_BG, fg=C_TEXT,
                     font=('Courier', 10), width=6, anchor='w').pack(side='left')
            ent = styled_entry(row, width=14)
            ent.pack(side='left', fill='x', expand=True)
            setattr(self, attr, ent)

        btn_row = tk.Frame(lim, bg=C_BG)
        btn_row.pack(fill='x', padx=6, pady=(4, 6))
        styled_button(btn_row, 'Apply Limits', self._apply_limits).pack(
            side='left', padx=(0, 4))
        styled_button(btn_row, 'Clear',        self._clear_limits).pack(
            side='left')

        # ── Test Tree ──
        filter_box = section('Filter Tests')

        tree_frame = tk.Frame(filter_box, bg=C_BG)
        tree_frame.pack(fill='both', expand=True, padx=4, pady=4)

        style = ttk.Style()
        style.configure('Filter.Treeview',
                        background=C_BG2, foreground=C_TEXT,
                        fieldbackground=C_BG2, rowheight=20,
                        font=('Courier', 9))
        style.configure('Filter.Treeview.Heading',
                        background=C_PANEL, foreground=C_ACCENT,
                        font=('Courier', 9, 'bold'), relief='flat')
        style.map('Filter.Treeview', background=[('selected', C_HOVER)])

        self.test_tree = ttk.Treeview(tree_frame, show='tree',
                                      style='Filter.Treeview',
                                      selectmode='browse', height=8)
        sb = ttk.Scrollbar(tree_frame, orient='vertical',
                           command=self.test_tree.yview)
        self.test_tree.configure(yscrollcommand=sb.set)
        self.test_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.test_tree.bind('<Double-1>', self._on_tree_double_click)

    def _info_row(self, parent, label, value):
        row = tk.Frame(parent, bg=C_BG)
        row.pack(fill='x', padx=6, pady=1)
        tk.Label(row, text=label, bg=C_BG, fg=C_TEXT_DIM,
                 font=('Courier', 9), width=8, anchor='w').pack(side='left')
        lbl = tk.Label(row, text=value, bg=C_BG, fg=C_TEXT,
                       font=('Courier', 9), anchor='w')
        lbl.pack(side='left', fill='x', expand=True)
        return lbl

    def _style_combobox(self):
        s = ttk.Style()
        s.configure('TCombobox',
                    fieldbackground=C_PANEL,
                    background=C_PANEL,
                    foreground=C_TEXT,
                    selectbackground=C_HOVER,
                    selectforeground=C_TEXT,
                    font=('Courier', 10))
        s.map('TCombobox', fieldbackground=[('readonly', C_PANEL)])

    # ── File loading ─────────────────────────

    def open_file(self):
        path = filedialog.askopenfilename(
            title='Open KDF File',
            filetypes=[('KDF Files', '*.kdf'), ('All Files', '*.*')])
        if path:
            self._load_file(path)

    def _load_file(self, path):
        try:
            header, sites, tests, mkeys = parse_kdf(path)
        except Exception as e:
            messagebox.showerror('Parse Error', f'Failed to read KDF file:\n{e}')
            return

        self._filepath = path
        self._header   = header
        self._sites    = sites
        self._tests    = tests
        self._mkeys    = mkeys
        self._limits   = {}
        self._current_mkey = None

        self.lbl_file.config(text=f'  {os.path.basename(path)}')
        self.lbl_lot.config(text=header.get('LOT', '—'))
        self.lbl_sys.config(text=header.get('SYS', '—'))
        self.lbl_stt.config(text=header.get('STT', '—'))
        self.lbl_nst.config(text=str(len(sites)))

        self.mkey_combo['values'] = mkeys
        self.mkey_combo.state(['!disabled'])

        # Populate test filter tree
        for item in self.test_tree.get_children():
            self.test_tree.delete(item)

        test_to_params = defaultdict(list)
        for mk in mkeys:
            parts = mk.split('@')
            if len(parts) >= 2:
                test_to_params[parts[1]].append(parts[0])

        for test in sorted(test_to_params):
            parent_id = self.test_tree.insert('', 'end', text=test,
                                              tags=('test',))
            for param in sorted(test_to_params[test]):
                self.test_tree.insert(parent_id, 'end',
                                      text=f'{param}@{test}',
                                      tags=('mkey',))

        self.test_tree.tag_configure('test', foreground=C_ACCENT)
        self.test_tree.tag_configure('mkey', foreground=C_TEXT_DIM)

        if mkeys:
            self._current_mkey = mkeys[0]
            self.mkey_combo.set(mkeys[0])
            self._refresh_canvas()

        self._update_ui_state()
        self.status_var.set(
            f'Loaded {len(sites)} sites, {len(mkeys)} measurements — '
            f'{os.path.basename(path)}')

    def _on_tree_double_click(self, event):
        item = self.test_tree.focus()
        text = self.test_tree.item(item, 'text')
        if text in self._mkeys:
            self.mkey_combo.set(text)
            self._on_mkey_changed(None)

    # ── Measurement & limits ─────────────────

    def _on_mkey_changed(self, event):
        mkey = self.mkey_combo.get()
        if mkey not in self._mkeys:
            return
        self._current_mkey = mkey
        lo, hi = self._limits.get(mkey, (None, None))
        self.low_edit.delete(0, 'end')
        self.high_edit.delete(0, 'end')
        if lo is not None: self.low_edit.insert(0, str(lo))
        if hi is not None: self.high_edit.insert(0, str(hi))
        self._refresh_canvas()

    def _apply_limits(self):
        lo = hi = None
        try:
            txt = self.low_edit.get().strip()
            if txt: lo = float(txt)
        except ValueError:
            messagebox.showwarning('Invalid', 'Low limit must be a number.')
            return
        try:
            txt = self.high_edit.get().strip()
            if txt: hi = float(txt)
        except ValueError:
            messagebox.showwarning('Invalid', 'High limit must be a number.')
            return
        if self._current_mkey:
            self._limits[self._current_mkey] = (lo, hi)
        self._refresh_canvas()

    def _clear_limits(self):
        self.low_edit.delete(0, 'end')
        self.high_edit.delete(0, 'end')
        if self._current_mkey:
            self._limits[self._current_mkey] = (None, None)
        self._refresh_canvas()

    def _refresh_canvas(self):
        if not self._sites or not self._current_mkey:
            return
        mkey = self._current_mkey
        lo, hi = self._limits.get(mkey, (None, None))
        values = {s['name']: get_site_value(s, mkey) for s in self._sites}
        self.canvas.load(self._sites, values, lo, hi, mkey=mkey)
        self.stats_panel.update_stats(values, lo, hi)
        self.status_var.set(
            f'Showing: {mkey}  |  '
            f'Low={lo if lo is not None else "—"}  '
            f'High={hi if hi is not None else "—"}  |  '
            f'{len(self._sites)} sites')

    # ── Site click ────────────────────────────

    def _on_site_clicked(self, site):
        self.detail_panel.show_site(site)

    # ── Export ────────────────────────────────

    def export_map(self):
        if not self._sites:
            messagebox.showinfo('Nothing to export', 'Load a KDF file first.')
            return
        path = filedialog.asksaveasfilename(
            title='Export Wafer Map',
            defaultextension='.ps',
            filetypes=[('PostScript', '*.ps'), ('All Files', '*.*')],
            initialfile='wafer_map.ps')
        if not path:
            return
        try:
            self.canvas.postscript(file=path, colormode='color')
            self.status_var.set(f'Exported to {path}')
            messagebox.showinfo('Exported', f'Wafer map saved to:\n{path}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save: {e}')

    # ── UI state ──────────────────────────────

    def _update_ui_state(self):
        has_data = bool(self._sites)
        state = 'normal' if has_data else 'disabled'
        self.low_edit.config(state=state)
        self.high_edit.config(state=state)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    win = MainWindow()

    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        win.after(100, lambda: win._load_file(sys.argv[1]))

    win.mainloop()


if __name__ == '__main__':
    main()
