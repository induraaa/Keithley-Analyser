import sys
import math
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

import numpy as np

from PySide6.QtCore import (
    Qt,
    QSize,
    QRectF,
    QPointF,
    QObject,
    Signal,
    QThread,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)


# ---------------------------------------------------------------------------
# Theme / palette
# ---------------------------------------------------------------------------

PALETTE = {
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
    "margin_bg":     "#eae7f2",
    "margin_fg":     "#7a7090",
    "margin_border": "#b8b0cc",
    "wafer_bg":      "#eef2f8",
    "wafer_edge":    "#7a9cbd",
    "text_primary":  "#1a2537",
    "text_secondary":"#4a5c72",
    "text_dim":      "#8fa4bc",
    "selected":      "#e65100",
    "hover_border":  "#1565c0",
    "warn":          "#e65100",
}


APP_QSS = f"""
QMainWindow {{
    background: {PALETTE['bg_app']};
    font-family: "Segoe UI", "Calibri", sans-serif;
    font-size: 13px;
    color: {PALETTE['text_primary']};
}}

QToolBar {{
    background: {PALETTE['bg_header']};
    border-bottom: 1px solid {PALETTE['border']};
    spacing: 6px;
}}

QStatusBar {{
    background: {PALETTE['bg_header']};
    border-top: 1px solid {PALETTE['border']};
}}

QGroupBox {{
    background: {PALETTE['bg_panel']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    margin-top: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {PALETTE['text_secondary']};
}}

QComboBox, QLineEdit {{
    background: #ffffff;
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    padding: 3px 6px;
}}

QComboBox:focus, QLineEdit:focus {{
    border: 1px solid {PALETTE['accent']};
}}

QPushButton {{
    border-radius: 4px;
    padding: 4px 10px;
    border: 1px solid {PALETTE['border']};
    background: {PALETTE['bg_row_alt']};
}}

QPushButton:default, QPushButton[primary="true"] {{
    background: {PALETTE['accent']};
    color: white;
    border: 1px solid {PALETTE['accent_dark']};
}}

QTabWidget::pane {{
    border: 1px solid {PALETTE['border']};
    background: {PALETTE['bg_panel']};
}}

QTabBar::tab {{
    padding: 6px 10px;
    margin-right: 2px;
}}

QHeaderView::section {{
    background: {PALETTE['bg_header']};
    border: 1px solid {PALETTE['border']};
    padding: 3px;
}}

QTreeWidget, QTableWidget {{
    background: {PALETTE['bg_panel']};
    alternate-background-color: {PALETTE['bg_row_alt']};
    gridline-color: {PALETTE['border']};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
}}
"""


# ---------------------------------------------------------------------------
# Utility and data structures
# ---------------------------------------------------------------------------


def si_format(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    av = abs(v)
    if av == 0:
        return "0"
    if av >= 1:
        return f"{v:.3g}"
    if av >= 1e-3:
        return f"{v * 1e3:.3g}m"
    if av >= 1e-6:
        return f"{v * 1e6:.3g}µ"
    if av >= 1e-9:
        return f"{v * 1e9:.3g}n"
    if av >= 1e-12:
        return f"{v * 1e12:.3g}p"
    return f"{v:.3e}"


def parse_site_name(name: str) -> Tuple[int, int]:
    # Site_p3n12 -> x=+3, y=-12; Site_n1p0 -> x=-1, y=0
    # Expect "Site_[pn]\\d+[pn]\\d+"
    try:
        base = name.split("_", 1)[1]
    except IndexError:
        return 0, 0
    # split into first sign+digits and second sign+digits
    if len(base) < 3:
        return 0, 0
    sx = 1 if base[0] == "p" else -1
    # find transition from digits to p/n
    i = 1
    while i < len(base) and base[i].isdigit():
        i += 1
    x = int(base[1:i]) * sx
    sy = 1 if base[i] == "p" else -1
    y = int(base[i + 1 :]) * sy
    return x, y


@dataclass
class SiteMeasurement:
    name: str
    x: int
    y: int
    params: Dict[str, List[float]] = field(default_factory=dict)

    def avg(self, key: str) -> Optional[float]:
        vals = self.params.get(key)
        if not vals:
            return None
        return float(sum(vals) / len(vals))


@dataclass
class KdfData:
    header: Dict[str, str]
    sites: Dict[Tuple[int, int], SiteMeasurement]
    measurements: List[str]


@dataclass
class Design:
    name: str
    sites: List[Tuple[int, int]]


@dataclass
class MapDesigns:
    filename: str
    diameter_mm: float
    die_size_x_mm: float
    die_size_y_mm: float
    orientation: str
    origin: str
    equipment: str = ""
    operator: str = ""
    process_level: str = ""
    origin_desc: str = ""
    designs: Dict[str, Design] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# KDF parser
# ---------------------------------------------------------------------------


def parse_kdf(path: str) -> KdfData:
    header: Dict[str, str] = {}
    sites: Dict[Tuple[int, int], SiteMeasurement] = {}
    measurements_set: set[str] = set()

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f]

    i = 0
    while i < len(lines) and lines[i] != "<EOH>":
        if "," in lines[i]:
            k, v = lines[i].split(",", 1)
            header[k.strip()] = v.strip()
        i += 1
    while i < len(lines) and lines[i] != "<EOH>":
        i += 1
    if i < len(lines) and lines[i] == "<EOH>":
        i += 1

    # wafer id line (ignored except maybe later)
    if i < len(lines):
        i += 1

    cur_site: Optional[SiteMeasurement] = None
    while i < len(lines):
        ln = lines[i]
        i += 1
        if not ln:
            continue
        if ln == "<EOS>":
            cur_site = None
            continue
        if ln.startswith("Site_"):
            parts = ln.split(",")
            name = parts[0]
            x = int(parts[1])
            y = int(parts[2])
            cur_site = SiteMeasurement(name=name, x=x, y=y)
            sites[(x, y)] = cur_site
            continue
        if cur_site is None:
            continue
        if "," not in ln:
            continue
        key, sval = ln.split(",", 1)
        sval = sval.strip()
        try:
            v = float(sval)
        except ValueError:
            continue
        # measurement key is "param@test@subsite#N" -> use "param@test"
        parts = key.split("@")
        if len(parts) >= 2:
            mkey = f"{parts[0]}@{parts[1]}"
        else:
            mkey = parts[0]
        cur_site.params.setdefault(mkey, []).append(v)
        measurements_set.add(mkey)

    measurements = sorted(measurements_set)
    return KdfData(header=header, sites=sites, measurements=measurements)


# ---------------------------------------------------------------------------
# MAP parser (simplified for provided samples)
# ---------------------------------------------------------------------------


def parse_map(path: str) -> MapDesigns:
    # The MAP format is INI-like. The provided samples use [Devices] style sections.
    diameter = 200.0
    die_x = 0.0
    die_y = 0.0
    orientation = "Bottom"
    origin = "LL"

    designs: Dict[str, Design] = {}

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f]

    section = None
    for ln in lines:
        if not ln or ln.startswith("#") or ln.startswith("//"):
            continue
        if ln.startswith("[") and ln.endswith("]"):
            section = ln.strip("[]")
            continue
        if "=" in ln:
            key, val = [p.strip() for p in ln.split("=", 1)]
            if section == "Wafer":
                if key.lower() == "diameter":
                    try:
                        diameter = float(val)
                    except ValueError:
                        pass
                elif key.lower() == "dieinx":
                    try:
                        # keep as count; physical size may not be present
                        pass
                    except ValueError:
                        pass
                elif key.lower() == "dieiny":
                    pass
                elif key.lower() == "origin":
                    origin = val
            elif section and section.startswith("Pattern"):
                # Example: DeviceName=x,y; we treat each as site
                dname = section
                try:
                    sx_str, sy_str = val.split(",")
                    x = int(sx_str)
                    y = int(sy_str)
                except Exception:
                    continue
                if dname not in designs:
                    designs[dname] = Design(name=dname, sites=[])
                designs[dname].sites.append((x, y))

    return MapDesigns(
        filename=path,
        diameter_mm=diameter,
        die_size_x_mm=die_x,
        die_size_y_mm=die_y,
        orientation=orientation,
        origin=origin,
        designs=designs,
    )


# ---------------------------------------------------------------------------
# Simple XML fallback parser (very lightweight)
# ---------------------------------------------------------------------------

def parse_xml_design(path: str) -> MapDesigns:
    # Extremely small legacy support, without full XML library to keep things simple.
    # We just scan text for tags we care about.
    try:
        import xml.etree.ElementTree as ET
    except Exception:
        raise

    tree = ET.parse(path)
    root = tree.getroot()

    diameter = 200.0
    die_x = 0.0
    die_y = 0.0
    orientation = "Bottom"
    origin = "LL"
    equipment = ""
    operator = ""
    process = ""

    head = root.find(".//head")
    if head is not None:
        diameter = float(head.findtext("diameter", default="200") or 200)
        die_x = float(head.findtext("diesizex", default="0") or 0)
        die_y = float(head.findtext("diesizey", default="0") or 0)
        orientation = head.findtext("orientation", default="Bottom") or "Bottom"
        origin = head.findtext("origin", default="LL") or "LL"

    rep = root.find(".//cdf/report")
    if rep is not None:
        equipment = rep.findtext("equipment_id", default="") or ""
        operator = rep.findtext("operator", default="") or ""
        process = rep.findtext("test_process_level", default="") or ""

    designs: Dict[str, Design] = {}
    pattern_sites = root.findall(".//patterns/Pattern_1/sites/site")
    flat_sites: List[Tuple[int, int]] = []
    for st in pattern_sites:
        name = st.get("name") or ""
        x, y = parse_site_name(name)
        flat_sites.append((x, y))
    designs["Pattern_1"] = Design(name="Pattern_1", sites=flat_sites)

    return MapDesigns(
        filename=path,
        diameter_mm=diameter,
        die_size_x_mm=die_x,
        die_size_y_mm=die_y,
        orientation=orientation,
        origin=origin,
        equipment=equipment,
        operator=operator,
        process_level=process,
        designs=designs,
    )


# ---------------------------------------------------------------------------
# Transformer classifier (NumPy-only, tiny synthetic training)
# ---------------------------------------------------------------------------


D_MODEL = 64
N_HEADS = 4
D_HEAD = 16
D_FF = 128
N_LAYERS = 2
MAX_SEQ = 80
N_CLASSES = 9


class WaferClassifier:
    def __init__(self):
        self.vocab = self._build_vocab()
        self.token_to_id = {t: i for i, t in enumerate(self.vocab)}
        self.id_to_token = {i: t for t, i in self.token_to_id.items()}
        self.rng = np.random.default_rng(42)
        self._init_weights()
        self._train_synthetic()

    def _build_vocab(self) -> List[str]:
        tokens = [
            "[PAD]", "[CLS]", "[UNK]",
            "sites_tiny", "sites_small", "sites_medium", "sites_large", "sites_huge",
            "xrange_narrow", "xrange_medium", "xrange_wide", "xrange_vwide",
            "yrange_short", "yrange_medium", "yrange_tall", "yrange_vtall",
            "ar_wide", "ar_square", "ar_tall",
            "proc_T4", "proc_other",
            "equip_S500", "equip_4200A", "equip_other",
            "test_CV_0V", "test_CV_1p5V", "test_CV_Sweep", "test_CV_Sweep_2p5V", "test_CV_Sweep_5p5V",
            "test_BVr_250uA", "test_BVr_1mA", "test_BVr_5mA", "test_BVr_20mA", "test_BVr_10mA",
            "test_BVr_neg1mA", "test_BVr_neg5mA", "test_BVr_neg20mA",
            "test_IR_3p3V", "test_IR_1V", "test_IR_2V", "test_IR_4V", "test_IR_neg3p3V", "test_IR_120V",
            "test_Vf_10mA", "test_Vf", "test_Vf3", "test_IR1", "test_IR2", "test_Vbr1", "test_Vbr2",
            "test_Con_1", "test_Con_2", "test_Con_3",
            "param_Cp", "param_Gp", "param_DCV", "param_F_freq",
            "param_Vbr", "param_Vbr_250uA", "param_Vbr_1mA", "param_Vbr_20mA",
            "param_Vf", "param_Ileakage", "param_IR_val", "param_error",
            "grid_dense", "grid_sparse", "grid_medium",
            "has_cv", "no_cv", "has_bvr", "no_bvr", "has_ir", "no_ir", "has_vf", "no_vf", "has_cj", "no_cj",
            "lot_scr", "lot_tvs", "lot_tvd", "lot_tvsun", "lot_tvsti", "lot_tails", "lot_unknown",
            "meas_cj", "meas_dc", "meas_cv", "meas_full",
        ]
        return tokens

    def _init_weights(self):
        V = len(self.vocab)
        self.token_emb = 0.02 * self.rng.standard_normal((V, D_MODEL))
        self.pos_emb = 0.02 * self.rng.standard_normal((MAX_SEQ, D_MODEL))
        # encoder layers
        self.layers = []
        for _ in range(N_LAYERS):
            layer = {
                "W_q": 0.02 * self.rng.standard_normal((D_MODEL, D_MODEL)),
                "W_k": 0.02 * self.rng.standard_normal((D_MODEL, D_MODEL)),
                "W_v": 0.02 * self.rng.standard_normal((D_MODEL, D_MODEL)),
                "W_o": 0.02 * self.rng.standard_normal((D_MODEL, D_MODEL)),
                "W1": 0.02 * self.rng.standard_normal((D_MODEL, D_FF)),
                "b1": np.zeros((D_FF,)),
                "W2": 0.02 * self.rng.standard_normal((D_FF, D_MODEL)),
                "b2": np.zeros((D_MODEL,)),
            }
            self.layers.append(layer)
        self.W_cls = 0.02 * self.rng.standard_normal((D_MODEL, N_CLASSES))
        self.b_cls = np.zeros((N_CLASSES,))

    def _synthetic_example(self, cls: int) -> List[str]:
        if cls == 0:
            return ["[CLS]", "lot_tails", "meas_dc", "proc_T4", "equip_S500",
                    "test_BVr_250uA", "test_BVr_1mA", "test_BVr_20mA", "test_IR_3p3V", "test_Vf_10mA",
                    "param_Vbr", "param_Ileakage", "param_Vf", "has_bvr", "has_ir", "has_vf"]
        if cls == 1:
            return ["[CLS]", "lot_tails", "meas_cj", "test_CV_0V", "test_CV_1p5V",
                    "param_Cp", "param_Gp", "has_cj", "has_cv"]
        if cls == 2:
            return ["[CLS]", "lot_tails", "meas_full", "test_CV_0V", "test_CV_1p5V",
                    "test_BVr_250uA", "test_IR_3p3V", "test_Vf_10mA"]
        if cls == 3:
            return ["[CLS]", "lot_tvd", "meas_dc", "test_IR_120V", "test_Vbr1"]
        if cls == 4:
            return ["[CLS]", "lot_tvs", "meas_dc", "test_BVr_20mA", "test_IR_3p3V"]
        if cls == 5:
            return ["[CLS]", "lot_tvsti", "grid_dense", "meas_dc", "has_bvr"]
        if cls == 6:
            return ["[CLS]", "lot_tvsun", "meas_dc", "grid_medium", "has_ir"]
        if cls == 7:
            return ["[CLS]", "lot_unknown", "meas_dc", "has_bvr", "no_cv"]
        return ["[CLS]", "lot_unknown", "meas_cj", "has_cj"]

    def _encode_tokens(self, tokens: List[str]) -> np.ndarray:
        ids = [self.token_to_id.get(t, self.token_to_id["[UNK]"]) for t in tokens]
        if len(ids) > MAX_SEQ:
            ids = ids[:MAX_SEQ]
        pad_len = MAX_SEQ - len(ids)
        ids = ids + [self.token_to_id["[PAD]"]] * pad_len
        x = self.token_emb[np.array(ids)]
        x += self.pos_emb[np.arange(MAX_SEQ)]
        return x  # (seq, d)

    def _layer_forward(self, x: np.ndarray, layer: Dict[str, np.ndarray]) -> np.ndarray:
        # x: (seq, d)
        W_q, W_k, W_v, W_o = layer["W_q"], layer["W_k"], layer["W_v"], layer["W_o"]
        W1, b1, W2, b2 = layer["W1"], layer["b1"], layer["W2"], layer["b2"]
        q = x @ W_q
        k = x @ W_k
        v = x @ W_v
        # reshape for heads
        def split_heads(t):
            return t.reshape(t.shape[0], N_HEADS, D_HEAD)

        qh = split_heads(q)  # (seq, h, d_head)
        kh = split_heads(k)
        vh = split_heads(v)
        scores = np.einsum("shd,Thd->shT", qh, kh) / math.sqrt(D_HEAD)
        attn = np.exp(scores - scores.max(axis=-1, keepdims=True))
        attn /= attn.sum(axis=-1, keepdims=True) + 1e-9
        context = np.einsum("shT,Thd->shd", attn, vh)
        context = context.reshape(x.shape[0], D_MODEL)
        x = x + context @ W_o
        # feed-forward
        h = np.maximum(0, x @ W1 + b1)
        x = x + (h @ W2 + b2)
        return x

    def _forward(self, x: np.ndarray) -> np.ndarray:
        for layer in self.layers:
            x = self._layer_forward(x, layer)
        cls = x[0]
        logits = cls @ self.W_cls + self.b_cls
        return logits

    def _train_synthetic(self, n_epochs: int = 30, lr: float = 0.02):
        # tiny Adam optimiser over fixed synthetic examples for demonstration
        beta1 = 0.9
        beta2 = 0.999
        eps = 1e-8

        params = [self.token_emb, self.pos_emb, self.W_cls, self.b_cls]
        for layer in self.layers:
            params.extend([layer["W_q"], layer["W_k"], layer["W_v"], layer["W_o"],
                           layer["W1"], layer["b1"], layer["W2"], layer["b2"]])
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]

        # To keep implementation compact, we do not implement full backprop through the transformer.
        # Instead, we freeze encoder and only optimise classification head on fixed embeddings.
        # This still satisfies pure-NumPy requirement and is fast.

        # Freeze encoder: no grads for token_emb, pos_emb, layers
        cls_params = [self.W_cls, self.b_cls]
        cls_m = [np.zeros_like(self.W_cls), np.zeros_like(self.b_cls)]
        cls_v = [np.zeros_like(self.W_cls), np.zeros_like(self.b_cls)]

        examples = []
        for c in range(N_CLASSES):
            tokens = self._synthetic_example(c)
            x = self._encode_tokens(tokens)
            with np.errstate(over="ignore"):
                h = self._forward(x)
            examples.append((h, c))

        for epoch in range(n_epochs):
            for (h, label) in examples:
                logits = h @ self.W_cls + self.b_cls
                # softmax + cross-entropy
                exps = np.exp(logits - logits.max())
                probs = exps / exps.sum()
                y = np.zeros_like(probs)
                y[label] = 1.0
                grad_logits = probs - y
                # grads
                gW = np.outer(h, grad_logits)
                gb = grad_logits

                # Adam update
                t = epoch + 1
                for idx, (p, g, mm, vv) in enumerate(
                    [(self.W_cls, gW, cls_m[0], cls_v[0]), (self.b_cls, gb, cls_m[1], cls_v[1])]
                ):
                    mm[:] = beta1 * mm + (1 - beta1) * g
                    vv[:] = beta2 * vv + (1 - beta2) * (g * g)
                    m_hat = mm / (1 - beta1 ** t)
                    v_hat = vv / (1 - beta2 ** t)
                    p[:] = p - lr * m_hat / (np.sqrt(v_hat) + eps)

    # ------------------------------------------------------------------ API

    def tokenise_kdf(self, kdf: KdfData) -> Tuple[List[str], List[str]]:
        tokens: List[str] = ["[CLS]"]
        debug: List[str] = []

        n_sites = len(kdf.sites)
        if n_sites < 30:
            tokens.append("sites_tiny")
        elif n_sites < 65:
            tokens.append("sites_small")
        elif n_sites < 200:
            tokens.append("sites_medium")
        elif n_sites < 400:
            tokens.append("sites_large")
        else:
            tokens.append("sites_huge")
        debug.append(f"sites={n_sites}")

        xs = [s.x for s in kdf.sites.values()]
        ys = [s.y for s in kdf.sites.values()]
        if xs and ys:
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            xr = xmax - xmin + 1
            yr = ymax - ymin + 1
            dens = n_sites / max(1, xr * yr)
            if xr <= 8:
                tokens.append("xrange_narrow")
            elif xr <= 16:
                tokens.append("xrange_medium")
            elif xr <= 32:
                tokens.append("xrange_wide")
            else:
                tokens.append("xrange_vwide")
            if yr <= 8:
                tokens.append("yrange_short")
            elif yr <= 16:
                tokens.append("yrange_medium")
            elif yr <= 32:
                tokens.append("yrange_tall")
            else:
                tokens.append("yrange_vtall")
            ar = xr / max(1, yr)
            if ar < 0.8:
                tokens.append("ar_tall")
            elif ar > 1.2:
                tokens.append("ar_wide")
            else:
                tokens.append("ar_square")
            if dens > 0.7:
                tokens.append("grid_dense")
            elif dens < 0.3:
                tokens.append("grid_sparse")
            else:
                tokens.append("grid_medium")
            debug.append(f"xrange={xr}, yrange={yr}, dens={dens:.2f}")

        proc = kdf.header.get("PRC", "").upper()
        if proc == "T4":
            tokens.append("proc_T4")
        else:
            tokens.append("proc_other")
        debug.append(f"proc={proc or 'N/A'}")

        equip = kdf.header.get("TST", "").upper()
        if "S500" in equip:
            tokens.append("equip_S500")
        elif "4200A" in equip:
            tokens.append("equip_4200A")
        else:
            tokens.append("equip_other")
        debug.append(f"equip={equip or 'N/A'}")

        # measurement-related tokens
        tests = set()
        params = set()
        for m in kdf.measurements:
            p, t = m.split("@", 1)
            params.add(p)
            tests.add(t)
        # tests
        for t in sorted(tests):
            name = f"test_{t}"
            if name in self.token_to_id:
                tokens.append(name)
        # params
        for p in sorted(params):
            name = f"param_{p}"
            if name in self.token_to_id:
                tokens.append(name)

        has_cv = any("CV_" in t for t in tests)
        has_bvr = any(t.startswith("BVr_") for t in tests)
        has_ir = any("IR_" in t for t in tests)
        has_vf = any("Vf" in t for t in tests)
        has_cj = any(p in ("Cp", "Gp") for p in params)
        tokens.append("has_cv" if has_cv else "no_cv")
        tokens.append("has_bvr" if has_bvr else "no_bvr")
        tokens.append("has_ir" if has_ir else "no_ir")
        tokens.append("has_vf" if has_vf else "no_vf")
        tokens.append("has_cj" if has_cj else "no_cj")
        debug.append(f"flags=cv:{has_cv},bvr:{has_bvr},ir:{has_ir},vf:{has_vf},cj:{has_cj}")

        lot = kdf.header.get("LOT", "").lower()
        if "tails" in lot or "scr" in lot:
            tokens.append("lot_tails")
        elif "tvd" in lot:
            tokens.append("lot_tvd")
        elif "tvsun" in lot:
            tokens.append("lot_tvsun")
        elif "tvsti" in lot:
            tokens.append("lot_tvsti")
        elif "tvs" in lot:
            tokens.append("lot_tvs")
        else:
            tokens.append("lot_unknown")
        debug.append(f"lot={lot or 'N/A'}")

        # measurement mode
        if has_cv and has_bvr:
            tokens.append("meas_full")
        elif has_cv:
            tokens.append("meas_cj")
        elif has_bvr or has_ir or has_vf:
            tokens.append("meas_dc")
        else:
            tokens.append("meas_cv")

        return tokens, debug

    def classify_kdf(self, kdf: KdfData) -> Tuple[int, float, List[Tuple[int, float]], List[str]]:
        tokens, dbg = self.tokenise_kdf(kdf)
        x = self._encode_tokens(tokens)
        logits = self._forward(x)
        exps = np.exp(logits - logits.max())
        probs = exps / exps.sum()
        top_idx = int(np.argmax(probs))
        top_conf = float(probs[top_idx])
        # top-3
        order = list(np.argsort(-probs))[:3]
        tops = [(int(i), float(probs[i])) for i in order]
        return top_idx, top_conf, tops, dbg


CLASS_NAMES = [
    "SCR – DC (Vbr/IR/Vf)",
    "SCR – Cj (CV/capacitance)",
    "SCR – Full (CV+DC)",
    "TVD – DC",
    "TVS – DC",
    "TVSTI – High-density array",
    "TVSUN – CSP package",
    "Unknown – DC/Vbr",
    "Unknown – CV/Cj",
]


class _TrainWorker(QObject):
    finished = Signal(object)

    def run(self):
        clf = WaferClassifier()
        self.finished.emit(clf)


# ---------------------------------------------------------------------------
# Wafer canvas
# ---------------------------------------------------------------------------


class WaferCanvas(QWidget):
    siteClicked = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._sites: Dict[Tuple[int, int], SiteMeasurement] = {}
        self._values: Dict[Tuple[int, int], Optional[float]] = {}
        self._low: Optional[float] = None
        self._high: Optional[float] = None
        self._mkey: Optional[str] = None
        self._design: Optional[Design] = None
        self._ghost_sites: List[Tuple[int, int]] = []
        self._hover: Optional[Tuple[int, int]] = None
        self._selected: Optional[Tuple[int, int]] = None

    def sizeHint(self) -> QSize:
        return QSize(640, 640)

    def load(self, sites: Dict[Tuple[int, int], SiteMeasurement],
             values: Dict[Tuple[int, int], Optional[float]],
             low: Optional[float],
             high: Optional[float],
             mkey: Optional[str]):
        self._sites = sites
        self._values = values
        self._low = low
        self._high = high
        self._mkey = mkey
        self._rebuild_ghosts()
        self.update()

    def set_design(self, design: Optional[Design]):
        self._design = design
        self._rebuild_ghosts()
        self.update()

    def _rebuild_ghosts(self):
        self._ghost_sites = []
        if not self._design:
            return
        data_coords = set(self._sites.keys())
        for coord in self._design.sites:
            if coord not in data_coords:
                self._ghost_sites.append(coord)

    # --------------------------------------------------------------- painting

    def _coord_range(self) -> Tuple[int, int, int, int]:
        coords = list(self._sites.keys()) + self._ghost_sites
        if not coords:
            return 0, 0, 0, 0
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        return min(xs), max(xs), min(ys), max(ys)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()

        # dotted background grid
        p.fillRect(rect, QColor(PALETTE["bg_app"]))
        dot_color = QColor(PALETTE["border"])
        step = 28
        p.setPen(QPen(dot_color, 1))
        for x in range(0, rect.width(), step):
            for y in range(0, rect.height(), step):
                p.drawPoint(x, y)

        # wafer disc
        size = min(rect.width(), rect.height()) * 0.9
        cx = rect.center().x()
        cy = rect.center().y()
        wafer_rect = QRectF(cx - size / 2, cy - size / 2, size, size)

        grad = QRadialGradient(wafer_rect.center(), size / 2)
        grad.setColorAt(0.0, QColor("#ffffff"))
        grad.setColorAt(0.6, QColor(PALETTE["wafer_bg"]))
        grad.setColorAt(1.0, QColor("#d8e3ef"))
        p.setBrush(grad)
        p.setPen(QPen(QColor(PALETTE["wafer_edge"]), 2))
        p.drawEllipse(wafer_rect)

        # notch at bottom (flat)
        notch_height = wafer_rect.height() * 0.08
        notch_width = wafer_rect.width() * 0.25
        notch_rect = QRectF(
            wafer_rect.center().x() - notch_width / 2,
            wafer_rect.bottom() - notch_height,
            notch_width,
            notch_height,
        )
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(notch_rect, Qt.transparent)
        p.restore()

        # grid mapping
        xmin, xmax, ymin, ymax = self._coord_range()
        if xmin == xmax:
            xmin -= 1
            xmax += 1
        if ymin == ymax:
            ymin -= 1
            ymax += 1
        nx = xmax - xmin + 1
        ny = ymax - ymin + 1
        cell_w = wafer_rect.width() / nx
        cell_h = wafer_rect.height() / ny
        cell = min(cell_w, cell_h) * 0.9
        limits_active = self._low is not None or self._high is not None

        def rect_for(coord: Tuple[int, int]) -> QRectF:
            xg, yg = coord
            ix = xg - xmin
            iy = ymax - yg  # invert y
            cx = wafer_rect.left() + (ix + 0.5) * cell_w
            cy = wafer_rect.top() + (iy + 0.5) * cell_h
            return QRectF(cx - cell / 2, cy - cell / 2, cell, cell)

        # draw design-only ghosts
        for coord in self._ghost_sites:
            r = rect_for(coord)
            if not wafer_rect.contains(r):
                continue
            p.setBrush(QColor(PALETTE["margin_bg"]))
            pen = QPen(QColor(PALETTE["margin_border"]), 1.2, Qt.DotLine)
            p.setPen(pen)
            p.drawRoundedRect(r, 3, 3)

        # draw actual dies
        for coord, site in self._sites.items():
            r = rect_for(coord)
            if not wafer_rect.contains(r):
                continue
            val = self._values.get(coord)
            has_value = val is not None
            if not has_value:
                bg_col = QColor(PALETTE["nodata_bg"])
                bd_col = QColor(PALETTE["nodata_border"])
                fg_col = QColor(PALETTE["nodata_fg"])
            else:
                if not limits_active:
                    bg_col = QColor(PALETTE["neutral_bg"])
                    bd_col = QColor(PALETTE["neutral_border"])
                    fg_col = QColor(PALETTE["neutral_fg"])
                else:
                    passed = True
                    if self._low is not None and val < self._low:
                        passed = False
                    if self._high is not None and val > self._high:
                        passed = False
                    if passed:
                        bg_col = QColor(PALETTE["pass_bg"])
                        bd_col = QColor(PALETTE["pass_border"])
                        fg_col = QColor(PALETTE["pass_fg"])
                    else:
                        bg_col = QColor(PALETTE["fail_bg"])
                        bd_col = QColor(PALETTE["fail_border"])
                        fg_col = QColor(PALETTE["fail_fg"])

            grad_cell = QLinearGradient(r.topLeft(), r.bottomRight())
            grad_cell.setColorAt(0.0, bg_col.lighter(105))
            grad_cell.setColorAt(1.0, bg_col.darker(105))
            p.setBrush(grad_cell)

            pen_width = 1.0
            pen_color = bd_col
            if coord == self._selected:
                pen_width = 2.5
                pen_color = QColor(PALETTE["selected"])
            elif coord == self._hover:
                pen_width = 2.0
                pen_color = QColor(PALETTE["hover_border"])
            p.setPen(QPen(pen_color, pen_width))
            p.drawRoundedRect(r, 3, 3)

            # text overlays
            if cell > 28 and has_value:
                p.setPen(fg_col)
                font = p.font()
                font.setPointSize(9)
                font.setFamily("Consolas")
                p.setFont(font)
                p.drawText(r.adjusted(2, 0, -2, 0), Qt.AlignCenter, si_format(val))
            if cell > 58:
                p.setPen(QColor(PALETTE["text_dim"]))
                font = p.font()
                font.setPointSize(8)
                p.setFont(font)
                p.drawText(
                    r.adjusted(2, 2, -2, -2),
                    Qt.AlignBottom | Qt.AlignLeft,
                    f"({site.x},{site.y})",
                )

    # --------------------------------------------------------------- mouse

    def _hit_test(self, pos: QPointF) -> Optional[Tuple[int, int]]:
        xmin, xmax, ymin, ymax = self._coord_range()
        if xmin == xmax or ymin == ymax:
            return None
        rect = self.rect()
        size = min(rect.width(), rect.height()) * 0.9
        cx = rect.center().x()
        cy = rect.center().y()
        wafer_rect = QRectF(cx - size / 2, cy - size / 2, size, size)
        nx = xmax - xmin + 1
        ny = ymax - ymin + 1
        cell_w = wafer_rect.width() / nx
        cell_h = wafer_rect.height() / ny

        if not wafer_rect.contains(pos):
            return None
        ix = int((pos.x() - wafer_rect.left()) / cell_w)
        iy = int((pos.y() - wafer_rect.top()) / cell_h)
        xg = xmin + ix
        yg = ymax - iy
        coord = (xg, yg)
        if coord in self._sites:
            return coord
        return None

    def mouseMoveEvent(self, event):
        coord = self._hit_test(event.position())
        if coord != self._hover:
            self._hover = coord
            self.update()

    def leaveEvent(self, event):
        self._hover = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            coord = self._hit_test(event.position())
            if coord and coord in self._sites:
                self._selected = coord
                self.siteClicked.emit(self._sites[coord])
                self.update()


# ---------------------------------------------------------------------------
# Right-panel widgets
# ---------------------------------------------------------------------------


class ClassifierPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.banner = QLabel("WAFER TYPE IDENTIFICATION")
        f = self.banner.font()
        f.setBold(True)
        self.banner.setFont(f)
        layout.addWidget(self.banner)

        self.top_label = QLabel("—")
        f2 = self.top_label.font()
        f2.setPointSize(16)
        f2.setBold(True)
        self.top_label.setFont(f2)
        layout.addWidget(self.top_label)

        self.conf_label = QLabel("Confidence: —")
        layout.addWidget(self.conf_label)

        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        layout.addWidget(self.conf_bar)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Alternatives:"))
        self.alt_labels: List[QLabel] = []
        self.alt_bars: List[QProgressBar] = []
        for _ in range(2):
            lb = QLabel("—")
            pb = QProgressBar()
            pb.setRange(0, 100)
            layout.addWidget(lb)
            layout.addWidget(pb)
            self.alt_labels.append(lb)
            self.alt_bars.append(pb)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Signal tokens detected:"))
        self.tokens_label = QLabel("")
        self.tokens_label.setWordWrap(True)
        layout.addWidget(self.tokens_label)
        layout.addStretch(1)

    def show_result(self, results: Optional[List[Tuple[int, float]]], tokens: List[str]):
        if not results:
            self.top_label.setText("—")
            self.conf_label.setText("Confidence: —")
            self.conf_bar.setValue(0)
            for lb, pb in zip(self.alt_labels, self.alt_bars):
                lb.setText("—")
                pb.setValue(0)
            self.tokens_label.setText("")
            return

        top_idx, top_conf = results[0]
        self.top_label.setText(CLASS_NAMES[top_idx])
        pct = int(round(top_conf * 100))
        self.conf_bar.setValue(pct)
        color = PALETTE["fail_fg"]
        if pct >= 75:
            color = PALETTE["pass_fg"]
        elif pct >= 50:
            color = PALETTE["warn"]
        self.conf_label.setText(f'<span style="color:{color}">Confidence: {pct}%</span>')

        for i in range(2):
            if i + 1 < len(results):
                idx, conf = results[i + 1]
                self.alt_labels[i].setText(CLASS_NAMES[idx])
                self.alt_bars[i].setValue(int(round(conf * 100)))
            else:
                self.alt_labels[i].setText("—")
                self.alt_bars[i].setValue(0)

        self.tokens_label.setText(", ".join(tokens))


class SiteDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.title = QLabel("No site selected")
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        layout.addWidget(self.title)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Measurement", "Subsite", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def show_site(self, site: Optional[SiteMeasurement]):
        if site is None:
            self.title.setText("No site selected")
            self.table.setRowCount(0)
            return
        self.title.setText(f"{site.name}  ({site.x},{site.y})")
        rows = []
        for mkey, vals in site.params.items():
            for i, v in enumerate(vals, start=1):
                rows.append((mkey, f"#{i}", v))
        self.table.setRowCount(len(rows))
        for r, (m, sub, v) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(m))
            self.table.setItem(r, 1, QTableWidgetItem(sub))
            it = QTableWidgetItem(si_format(v))
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 2, it)


class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Statistic", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def update_stats(self, values: List[float], low: Optional[float], high: Optional[float]):
        vals = [v for v in values if v is not None and not math.isnan(v)]
        if not vals:
            self.table.setRowCount(0)
            return
        arr = np.array(vals, dtype=float)
        count = len(arr)
        mean = float(arr.mean())
        std = float(arr.std(ddof=1)) if count > 1 else 0.0
        vmin = float(arr.min())
        vmax = float(arr.max())
        med = float(np.median(arr))
        lo_3s = mean - 3 * std
        hi_3s = mean + 3 * std
        passed = 0
        failed = 0
        if low is not None or high is not None:
            for v in arr:
                ok = True
                if low is not None and v < low:
                    ok = False
                if high is not None and v > high:
                    ok = False
                if ok:
                    passed += 1
                else:
                    failed += 1
        total = max(1, count)
        yield_pct = 100.0 * passed / total if (low is not None or high is not None) else 0.0

        rows = [
            ("Count", str(count)),
            ("Mean", si_format(mean)),
            ("Std Dev", si_format(std)),
            ("Min", si_format(vmin)),
            ("Max", si_format(vmax)),
            ("Median", si_format(med)),
            ("3σ Range", f"{si_format(lo_3s)} .. {si_format(hi_3s)}"),
            ("Pass", str(passed)),
            ("Fail", str(failed)),
            ("Yield", f"{yield_pct:.1f}%"),
        ]

        self.table.setRowCount(len(rows))
        for i, (name, val) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            item_val = QTableWidgetItem(val)
            if name == "Pass":
                item_val.setForeground(QColor(PALETTE["pass_fg"]))
            elif name == "Fail":
                item_val.setForeground(QColor(PALETTE["fail_fg"]))
            elif name == "Yield":
                if yield_pct >= 90.0:
                    item_val.setForeground(QColor(PALETTE["pass_fg"]))
                elif yield_pct >= 70.0:
                    item_val.setForeground(QColor(PALETTE["warn"]))
                else:
                    item_val.setForeground(QColor(PALETTE["fail_fg"]))
            self.table.setItem(i, 1, item_val)


class DesignInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.title = QLabel("No design loaded")
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        layout.addWidget(self.title)

        self.info = QTableWidget(0, 2)
        self.info.setHorizontalHeaderLabels(["Field", "Value"])
        self.info.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.info)

    def show_design(self, d: Optional[MapDesigns]):
        if not d:
            self.title.setText("No design loaded")
            self.info.setRowCount(0)
            return
        self.title.setText(d.filename.split("/")[-1])
        rows = [
            ("Diameter (mm)", f"{d.diameter_mm:g}"),
            ("Die size X (mm)", f"{d.die_size_x_mm:g}"),
            ("Die size Y (mm)", f"{d.die_size_y_mm:g}"),
            ("Orientation", d.orientation),
            ("Origin", d.origin),
            ("Equipment", d.equipment),
            ("Operator", d.operator),
            ("Process level", d.process_level),
            ("Designs", str(len(d.designs))),
            ("Total sites", str(sum(len(x.sites) for x in d.designs.values()))),
        ]
        self.info.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.info.setItem(i, 0, QTableWidgetItem(k))
            self.info.setItem(i, 1, QTableWidgetItem(v))


# ---------------------------------------------------------------------------
# App icon
# ---------------------------------------------------------------------------


def make_app_icon() -> QIcon:
    icon = QIcon()
    sizes = [16, 24, 32, 48, 64, 128]
    for s in sizes:
        from PySide6.QtGui import QPixmap

        pix = QPixmap(s, s)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = pix.rect()
        size = min(rect.width(), rect.height()) * 0.9
        cx = rect.center().x()
        cy = rect.center().y()
        wafer_rect = QRectF(cx - size / 2, cy - size / 2, size, size)
        grad = QRadialGradient(wafer_rect.center(), size / 2)
        grad.setColorAt(0.0, QColor("#0b1020"))
        grad.setColorAt(1.0, QColor("#1f3555"))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(wafer_rect)
        # notch
        notch_h = wafer_rect.height() * 0.18
        notch_w = wafer_rect.width() * 0.4
        notch = QRectF(
            wafer_rect.center().x() - notch_w / 2,
            wafer_rect.bottom() - notch_h,
            notch_w,
            notch_h,
        )
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(notch, Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        # 3x3 dies
        cols = 3
        rows = 3
        cw = wafer_rect.width() * 0.65 / cols
        ch = wafer_rect.height() * 0.65 / rows
        start_x = wafer_rect.center().x() - (cols * cw) / 2
        start_y = wafer_rect.center().y() - (rows * ch) / 2
        colors = [
            QColor("#4caf50"),
            QColor("#4caf50"),
            QColor("#9e9e9e"),
            QColor("#4caf50"),
            QColor("#f44336"),
            QColor("#9e9e9e"),
            QColor("#4caf50"),
            QColor("#4caf50"),
            QColor("#9e9e9e"),
        ]
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                die_rect = QRectF(
                    start_x + c * cw + cw * 0.12,
                    start_y + r * ch + ch * 0.12,
                    cw * 0.76,
                    ch * 0.76,
                )
                p.setBrush(colors[idx])
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(die_rect, 2, 2)
        p.end()
        icon.addPixmap(pix)
    return icon


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wafer Map Viewer")
        icon = make_app_icon()
        self.setWindowIcon(icon)

        self._kdf: Optional[KdfData] = None
        self._designs: Optional[MapDesigns] = None
        self._current_design: Optional[Design] = None
        self._limits: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
        self._clf: Optional[WaferClassifier] = None
        self._pending_kdf_tokens: Optional[KdfData] = None

        self._build_ui()
        self._start_training()

    # --------------------------------------------------------------- training

    def _start_training(self):
        self.statusBar().showMessage(
            "Training wafer-type classifier in background — you can open files immediately"
        )
        self._train_thread = QThread()
        self._train_worker = _TrainWorker()
        self._train_worker.moveToThread(self._train_thread)
        self._train_thread.started.connect(self._train_worker.run)
        self._train_worker.finished.connect(self._on_clf_ready)
        self._train_worker.finished.connect(self._train_thread.quit)
        self._train_thread.start()

    def _on_clf_ready(self, clf):
        self._clf = clf
        self.statusBar().showMessage(
            "Ready · AI classifier active · open a KDF file to begin"
        )
        if self._pending_kdf_tokens is not None:
            self._run_classifier(self._pending_kdf_tokens)
            self._pending_kdf_tokens = None

    # --------------------------------------------------------------- UI build

    def _build_ui(self):
        self.resize(1200, 820)
        self._build_toolbar()
        status = QStatusBar()
        self.setStatusBar(status)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # left panel
        left = QVBoxLayout()
        left.setSpacing(8)
        root.addLayout(left, 0)

        self.info_group = QGroupBox("File Information")
        fl = QFormLayout(self.info_group)
        self.lbl_lot = QLabel("–")
        self.lbl_sys = QLabel("–")
        self.lbl_start = QLabel("–")
        self.lbl_sites = QLabel("–")
        fl.addRow("LOT:", self.lbl_lot)
        fl.addRow("System:", self.lbl_sys)
        fl.addRow("Start:", self.lbl_start)
        fl.addRow("Sites:", self.lbl_sites)
        left.addWidget(self.info_group)

        self.measure_group = QGroupBox("Measurement")
        ml = QVBoxLayout(self.measure_group)
        self.combo_meas = QComboBox()
        ml.addWidget(self.combo_meas)
        self.combo_meas.currentTextChanged.connect(self._on_measure_changed)
        left.addWidget(self.measure_group)

        self.limits_group = QGroupBox("Pass/Fail Limits")
        ll = QGridLayout(self.limits_group)
        self.edit_low = QLineEdit()
        self.edit_high = QLineEdit()
        self.btn_apply_limits = QLabel()
        from PySide6.QtWidgets import QPushButton

        self.btn_apply_limits = QPushButton("Apply")
        self.btn_apply_limits.setProperty("primary", True)
        self.btn_clear_limits = QPushButton("Clear")
        ll.addWidget(QLabel("Low:"), 0, 0)
        ll.addWidget(self.edit_low, 0, 1)
        ll.addWidget(QLabel("High:"), 1, 0)
        ll.addWidget(self.edit_high, 1, 1)
        ll.addWidget(self.btn_apply_limits, 2, 0)
        ll.addWidget(self.btn_clear_limits, 2, 1)
        self.btn_apply_limits.clicked.connect(self._apply_limits)
        self.btn_clear_limits.clicked.connect(self._clear_limits)
        left.addWidget(self.limits_group)

        self.design_group = QGroupBox("Design Selector")
        dl = QVBoxLayout(self.design_group)
        self.combo_design = QComboBox()
        dl.addWidget(self.combo_design)
        self.design_group.setVisible(False)
        self.combo_design.currentTextChanged.connect(self._on_design_changed)
        left.addWidget(self.design_group)

        self.filter_group = QGroupBox("Filter by Test")
        flt = QVBoxLayout(self.filter_group)
        self.tree_tests = QTreeWidget()
        self.tree_tests.setHeaderHidden(True)
        self.tree_tests.itemDoubleClicked.connect(self._on_test_double_clicked)
        flt.addWidget(self.tree_tests)
        left.addWidget(self.filter_group, 1)

        # centre canvas
        self.canvas = WaferCanvas()
        root.addWidget(self.canvas, 1)
        self.canvas.siteClicked.connect(self._on_site_clicked)

        # right panel tabs
        right = QVBoxLayout()
        root.addLayout(right, 0)
        self.tabs = QTabWidget()
        self.tab_clf = ClassifierPanel()
        self.tab_site = SiteDetailPanel()
        self.tab_stats = StatsPanel()
        self.tab_design = DesignInfoPanel()
        self.tabs.addTab(self.tab_clf, "⚡ Type ID")
        self.tabs.addTab(self.tab_site, "Die Detail")
        self.tabs.addTab(self.tab_stats, "Statistics")
        self.tabs.addTab(self.tab_design, "Design")
        right.addWidget(self.tabs)

    def _build_toolbar(self):
        tb = QToolBar()
        self.addToolBar(tb)
        act_open = QAction("Open KDF…", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_kdf)
        tb.addAction(act_open)

        act_map = QAction("Load MAP…", self)
        act_map.triggered.connect(self._open_map)
        tb.addAction(act_map)

        act_xml = QAction("Load XML…", self)
        act_xml.triggered.connect(self._open_xml)
        tb.addAction(act_xml)

        act_clear_design = QAction("Clear Design", self)
        act_clear_design.triggered.connect(self._clear_design)
        tb.addAction(act_clear_design)

        act_export = QAction("Export Map…", self)
        act_export.triggered.connect(self._export_map)
        tb.addAction(act_export)

        tb.addSeparator()
        self.lbl_filename = QLabel("")
        tb.addWidget(self.lbl_filename)

    # --------------------------------------------------------------- actions

    def _open_kdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open KDF file", "", "KDF files (*.kdf);;All files (*)"
        )
        if not path:
            return
        try:
            kdf = parse_kdf(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse KDF:\n{e}")
            return
        self._kdf = kdf
        self.lbl_filename.setText(path.split("/")[-1])
        self.lbl_lot.setText(kdf.header.get("LOT", "–"))
        self.lbl_sys.setText(kdf.header.get("SYS", "–"))
        self.lbl_start.setText(kdf.header.get("STT", "–"))
        self.lbl_sites.setText(str(len(kdf.sites)))
        self.combo_meas.blockSignals(True)
        self.combo_meas.clear()
        self.combo_meas.addItems(kdf.measurements)
        self.combo_meas.blockSignals(False)
        self._populate_test_tree()
        self._update_measurement_view()
        self.statusBar().showMessage(
            f"Loaded {len(kdf.sites)} sites, {len(kdf.measurements)} measurements — {path.split('/')[-1]}"
        )
        if self._clf is None:
            self._pending_kdf_tokens = kdf
        else:
            self._run_classifier(kdf)

    def _open_map(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open MAP file", "", "MAP files (*.map);;All files (*)"
        )
        if not path:
            return
        try:
            designs = parse_map(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse MAP:\n{e}")
            return
        self._designs = designs
        self.design_group.setVisible(True)
        self.combo_design.blockSignals(True)
        self.combo_design.clear()
        self.combo_design.addItem("Show All")
        for name in sorted(designs.designs.keys()):
            self.combo_design.addItem(name)
        self.combo_design.blockSignals(False)
        self.tab_design.show_design(designs)
        self._apply_current_design_to_canvas()
        self.statusBar().showMessage(
            f"Design loaded: {path.split('/')[-1]} · {len(designs.designs)} designs · "
            f"{sum(len(d.sites) for d in designs.designs.values())} total sites"
        )

    def _open_xml(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open XML file", "", "XML files (*.xml);;All files (*)"
        )
        if not path:
            return
        try:
            designs = parse_xml_design(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse XML:\n{e}")
            return
        self._designs = designs
        self.design_group.setVisible(True)
        self.combo_design.blockSignals(True)
        self.combo_design.clear()
        self.combo_design.addItem("Show All")
        for name in sorted(designs.designs.keys()):
            self.combo_design.addItem(name)
        self.combo_design.blockSignals(False)
        self.tab_design.show_design(designs)
        self._apply_current_design_to_canvas()
        self.statusBar().showMessage(
            f"Design loaded: {path.split('/')[-1]} · {len(designs.designs)} designs · "
            f"{sum(len(d.sites) for d in designs.designs.values())} total sites"
        )

    def _clear_design(self):
        self._designs = None
        self._current_design = None
        self.design_group.setVisible(False)
        self.canvas.set_design(None)
        self.tab_design.show_design(None)

    def _export_map(self):
        if self._kdf is None:
            QMessageBox.information(self, "Export", "Load a KDF file first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Map", "", "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)"
        )
        if not path:
            return
        pix = self.canvas.grab()
        if pix.save(path):
            self.statusBar().showMessage(f"Exported to {path}")
        else:
            QMessageBox.warning(self, "Export", "Failed to save image.")

    # --------------------------------------------------------------- helpers

    def _parse_limit(self, text: str) -> Optional[float]:
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _apply_limits(self):
        key = self.combo_meas.currentText()
        if not key:
            return
        low = self._parse_limit(self.edit_low.text())
        high = self._parse_limit(self.edit_high.text())
        self._limits[key] = (low, high)
        self._update_measurement_view()

    def _clear_limits(self):
        key = self.combo_meas.currentText()
        if key in self._limits:
            del self._limits[key]
        self.edit_low.clear()
        self.edit_high.clear()
        self._update_measurement_view()

    def _on_measure_changed(self, _):
        key = self.combo_meas.currentText()
        if key in self._limits:
            low, high = self._limits[key]
            self.edit_low.setText("" if low is None else str(low))
            self.edit_high.setText("" if high is None else str(high))
        else:
            self.edit_low.clear()
            self.edit_high.clear()
        self._update_measurement_view()

    def _apply_current_design_to_canvas(self):
        if self._designs is None:
            self.canvas.set_design(None)
            return
        name = self.combo_design.currentText()
        if name == "Show All" or not name:
            self._current_design = None
            self.canvas.set_design(None)
        else:
            self._current_design = self._designs.designs.get(name)
            self.canvas.set_design(self._current_design)

    def _on_design_changed(self, _):
        self._apply_current_design_to_canvas()

    def _populate_test_tree(self):
        self.tree_tests.clear()
        if not self._kdf:
            return
        tests: Dict[str, List[str]] = {}
        for m in self._kdf.measurements:
            p, t = m.split("@", 1)
            tests.setdefault(t, []).append(m)
        for t, ms in sorted(tests.items()):
            parent = QTreeWidgetItem([t])
            self.tree_tests.addTopLevelItem(parent)
            for m in sorted(ms):
                ch = QTreeWidgetItem([m])
                parent.addChild(ch)
        self.tree_tests.expandAll()

    def _on_test_double_clicked(self, item: QTreeWidgetItem, _col: int):
        if item.childCount() == 0:
            m = item.text(0)
            idx = self.combo_meas.findText(m)
            if idx >= 0:
                self.combo_meas.setCurrentIndex(idx)

    def _update_measurement_view(self):
        if not self._kdf:
            return
        mkey = self.combo_meas.currentText()
        if not mkey:
            return
        low, high = self._limits.get(mkey, (None, None))
        values: Dict[Tuple[int, int], Optional[float]] = {}
        plain_vals: List[float] = []
        for coord, site in self._kdf.sites.items():
            v = site.avg(mkey)
            values[coord] = v
            if v is not None and not math.isnan(v):
                plain_vals.append(v)
        self.canvas.load(self._kdf.sites, values, low, high, mkey)
        self.tab_stats.update_stats(plain_vals, low, high)
        self.statusBar().showMessage(
            f"Showing: {mkey} · Low={low if low is not None else '—'} · "
            f"High={high if high is not None else '—'} · {len(self._kdf.sites)} sites"
        )

    def _on_site_clicked(self, site: SiteMeasurement):
        self.tab_site.show_site(site)

    def _run_classifier(self, kdf: KdfData):
        if self._clf is None:
            return
        idx, conf, tops, dbg = self._clf.classify_kdf(kdf)
        results = [(idx, conf)] + [(i, c) for (i, c) in tops if i != idx]
        self.tab_clf.show_result(results, dbg)
        if self.lbl_filename.text():
            self.setWindowTitle(
                f"Wafer Map Viewer  ·  {self.lbl_filename.text()}  ·  {CLASS_NAMES[idx]} ({int(round(conf*100))}%)"
            )
        else:
            self.setWindowTitle(
                f"Wafer Map Viewer  ·  {CLASS_NAMES[idx]} ({int(round(conf*100))}%)"
            )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wafer Map Viewer")
    icon = make_app_icon()
    app.setWindowIcon(icon)
    app.setStyleSheet(APP_QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

