"""
VektorStudio — 次世代ベクタークリエイティブスタジオ
Full Edition: Phase 1-4 統合版

機能:
  ツール     : ペン / Reshape / 選択 / 手のひら / 消しゴム /
               アンカー追加 / アンカー削除 / 線幅編集 / 交差点消しゴム
  ブラシ     : Gペン / 鉛筆 / マーカー / 水彩 (ストロークシミュレーション)
  ブラシスタジオ: カスタムブラシ作成・管理
  ベクター塗り: バケツ塗り (隙間検知・クローズパス自動生成)
  シンメトリー: 左右/上下/4方向対称定規
  グループ化  : グループ / グループ解除
  複数選択   : ラバーバンド選択 / Shift追加
  変形       : 移動 / 回転 / スケール (バウンディングボックスハンドル)
  レイヤー   : 可視/ロック/不透明度/ブレンドモード
  SVG        : 完全な読み書き (data-* でレイヤー/グループ情報保持)
  Undo/Redo  : 無制限
"""

import sys, math, uuid, json
from copy import deepcopy
from typing import Optional, List, Tuple, Set
from enum import Enum, auto

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QStatusBar, QFileDialog, QMessageBox, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSlider, QColorDialog,
    QDockWidget, QAbstractItemView, QSpinBox, QDoubleSpinBox,
    QGroupBox, QComboBox, QDialog, QDialogButtonBox, QLineEdit,
    QCheckBox, QTabWidget, QSizePolicy, QScrollArea, QFrame,
    QMenu, QInputDialog,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor, QAction,
    QUndoStack, QUndoCommand, QTransform, QPainterPathStroker,
    QLinearGradient, QFont, QCursor, QKeySequence, QPixmap, QImage,
)
from PySide6.QtCore import (
    Qt, QPointF, QRectF, QSizeF, QTimer, Signal, QLineF, QSize,
)
import lxml.etree as ET

# ══════════════════════════════════════════════
#  テーマ
# ══════════════════════════════════════════════
C = {
    "bg":          "#0E0F11",
    "surface":     "#16181C",
    "panel":       "#1C1F24",
    "panel2":      "#22262E",
    "border":      "#2A2D35",
    "accent":      "#5B8CFF",
    "accent2":     "#A78BFA",
    "accent3":     "#34D399",
    "fg":          "#E8EAF0",
    "fg_dim":      "#6B7280",
    "fg_muted":    "#3D4148",
    "node_fill":   "#5B8CFF",
    "node_sel":    "#A78BFA",
    "stroke_def":  "#E8EAF0",
    "canvas_bg":   "#1A1D22",
    "canvas_grid": "#1E2128",
    "danger":      "#FF5B6B",
    "warn":        "#FBBF24",
    "success":     "#4ADE80",
    "sym_line":    "#FF5B6B44",
}

SS = f"""
* {{ box-sizing: border-box; }}
QMainWindow, QWidget {{
    background: {C['bg']}; color: {C['fg']};
    font-family: 'Inter','Hiragino Kaku Gothic Pro','Meiryo','Yu Gothic UI',sans-serif;
    font-size: 12px;
}}
QToolBar {{
    background: {C['surface']}; border-bottom: 1px solid {C['border']};
    spacing: 2px; padding: 3px 6px;
}}
QToolBar QToolButton {{
    background: transparent; border: 1px solid transparent;
    border-radius: 6px; padding: 5px 7px; color: {C['fg']};
    font-size: 14px; min-width: 30px; min-height: 28px;
}}
QToolBar QToolButton:hover {{ background:{C['panel']}; border-color:{C['border']}; }}
QToolBar QToolButton:checked {{ background:{C['accent']}; color:#fff; border-color:{C['accent']}; }}
QMenuBar {{ background:{C['surface']}; color:{C['fg']}; border-bottom:1px solid {C['border']}; padding:2px 4px; }}
QMenuBar::item:selected {{ background:{C['accent']}; border-radius:4px; }}
QMenu {{ background:{C['panel']}; color:{C['fg']}; border:1px solid {C['border']}; border-radius:6px; padding:4px; }}
QMenu::item {{ padding:5px 20px 5px 10px; border-radius:4px; }}
QMenu::item:selected {{ background:{C['accent']}; }}
QMenu::separator {{ background:{C['border']}; height:1px; margin:3px 6px; }}
QDockWidget {{ background:{C['panel']}; }}
QDockWidget::title {{
    background:{C['surface']}; padding:6px 10px;
    border-bottom:1px solid {C['border']}; font-weight:600;
    font-size:11px; letter-spacing:0.5px; color:{C['fg_dim']};
}}
QListWidget {{ background:{C['panel']}; border:none; outline:none; }}
QListWidget::item {{
    padding:7px 10px; border-bottom:1px solid {C['border']};
    border-radius:4px; margin:1px 4px;
}}
QListWidget::item:selected {{ background:{C['accent']}; color:#fff; }}
QListWidget::item:hover:!selected {{ background:{C['surface']}; }}
QPushButton {{
    background:{C['surface']}; border:1px solid {C['border']};
    border-radius:6px; padding:5px 12px; color:{C['fg']};
    min-height:24px;
}}
QPushButton:hover {{ background:{C['panel']}; border-color:{C['accent']}; }}
QPushButton:pressed {{ background:{C['accent']}; color:#fff; }}
QPushButton#accent {{ background:{C['accent']}; border-color:{C['accent']}; color:#fff; font-weight:600; }}
QPushButton#accent:hover {{ background:#4A7AEE; }}
QPushButton#danger {{ background:transparent; border-color:{C['danger']}; color:{C['danger']}; }}
QPushButton#danger:hover {{ background:{C['danger']}; color:#fff; }}
QPushButton#success {{ background:{C['accent3']}; border-color:{C['accent3']}; color:#000; font-weight:600; }}
QSlider::groove:horizontal {{ background:{C['border']}; height:4px; border-radius:2px; }}
QSlider::handle:horizontal {{
    background:{C['accent']}; width:14px; height:14px;
    margin:-5px 0; border-radius:7px;
}}
QSlider::sub-page:horizontal {{ background:{C['accent']}; border-radius:2px; }}
QStatusBar {{ background:{C['surface']}; border-top:1px solid {C['border']}; color:{C['fg_dim']}; font-size:11px; }}
QGroupBox {{
    border:1px solid {C['border']}; border-radius:6px;
    margin-top:10px; padding-top:10px; font-size:11px; color:{C['fg_dim']};
}}
QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}
QSpinBox, QDoubleSpinBox, QLineEdit {{
    background:{C['surface']}; border:1px solid {C['border']};
    border-radius:4px; padding:3px 6px; color:{C['fg']};
}}
QComboBox {{
    background:{C['surface']}; border:1px solid {C['border']};
    border-radius:4px; padding:3px 8px; color:{C['fg']};
    min-height:24px;
}}
QComboBox QAbstractItemView {{ background:{C['panel']}; color:{C['fg']}; border:1px solid {C['border']}; }}
QTabWidget::pane {{ border:1px solid {C['border']}; border-radius:4px; }}
QTabBar::tab {{
    background:{C['surface']}; color:{C['fg_dim']};
    padding:6px 14px; border-bottom:2px solid transparent;
}}
QTabBar::tab:selected {{ color:{C['fg']}; border-bottom:2px solid {C['accent']}; }}
QScrollBar:vertical {{ background:{C['surface']}; width:7px; border-radius:3px; }}
QScrollBar::handle:vertical {{ background:{C['border']}; border-radius:3px; min-height:20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:{C['surface']}; height:7px; border-radius:3px; }}
QScrollBar::handle:horizontal {{ background:{C['border']}; border-radius:3px; min-width:20px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QDialog {{ background:{C['panel']}; border:1px solid {C['border']}; border-radius:8px; }}
QCheckBox {{ color:{C['fg']}; spacing:6px; }}
QCheckBox::indicator {{
    width:14px; height:14px; border:1px solid {C['border']};
    border-radius:3px; background:{C['surface']};
}}
QCheckBox::indicator:checked {{ background:{C['accent']}; border-color:{C['accent']}; }}
"""

# ══════════════════════════════════════════════
#  定数
# ══════════════════════════════════════════════
TOOL_PEN       = "pen"
TOOL_RESHAPE   = "reshape"
TOOL_SELECT    = "select"
TOOL_HAND      = "hand"
TOOL_ERASER    = "eraser"
TOOL_ADD_NODE  = "add_node"
TOOL_DEL_NODE  = "del_node"
TOOL_WIDTH     = "width"
TOOL_BUCKET    = "bucket"
TOOL_SCISSORS  = "scissors"

BLEND_MODES = ["通常", "乗算", "スクリーン", "オーバーレイ", "明度"]
BLEND_MAP   = {
    "通常":         QPainter.CompositionMode_SourceOver,
    "乗算":         QPainter.CompositionMode_Multiply,
    "スクリーン":   QPainter.CompositionMode_Screen,
    "オーバーレイ": QPainter.CompositionMode_Overlay,
    "明度":         QPainter.CompositionMode_SoftLight,
}

SYM_NONE   = "なし"
SYM_H      = "左右"
SYM_V      = "上下"
SYM_CROSS  = "4方向"

# ブラシ定義
BRUSHES = {
    "Gペン":   {"pressure_width": True,  "opacity_var": 0.0, "scatter": 0.0,  "tip": "round"},
    "鉛筆":    {"pressure_width": True,  "opacity_var": 0.3, "scatter": 1.2,  "tip": "round"},
    "マーカー":{"pressure_width": False, "opacity_var": 0.0, "scatter": 0.0,  "tip": "flat"},
    "水彩":    {"pressure_width": True,  "opacity_var": 0.5, "scatter": 2.0,  "tip": "round"},
    "エアブラシ":{"pressure_width": False,"opacity_var":0.6, "scatter": 5.0,  "tip": "soft"},
}

# ══════════════════════════════════════════════
#  データモデル
# ══════════════════════════════════════════════

class VNode:
    __slots__ = ("id","pos","cp_in","cp_out","smooth")
    def __init__(self, pos: QPointF, cp_in=None, cp_out=None):
        self.id      = uuid.uuid4().hex[:8]
        self.pos     = QPointF(pos)
        self.cp_in   = QPointF(cp_in)  if cp_in  else QPointF(pos)
        self.cp_out  = QPointF(cp_out) if cp_out else QPointF(pos)
        self.smooth  = True

    def set_pos(self, p: QPointF):
        dx = p.x()-self.pos.x(); dy = p.y()-self.pos.y()
        self.pos    = QPointF(p)
        self.cp_in  = QPointF(self.cp_in.x()+dx,  self.cp_in.y()+dy)
        self.cp_out = QPointF(self.cp_out.x()+dx, self.cp_out.y()+dy)

    def clone(self):
        return VNode(self.pos, self.cp_in, self.cp_out)


class VPath:
    def __init__(self):
        self.id           = uuid.uuid4().hex[:8]
        self.nodes: List[VNode] = []
        self.closed       = False
        self.stroke_color = QColor(C["stroke_def"])
        self.stroke_width = 2.0
        self.fill_color   = QColor(Qt.transparent)
        self.opacity      = 1.0
        self.visible      = True
        self.brush_name   = "Gペン"
        # ブラシストローク用の幅プロファイル [0..1] 各ノードの筆圧相当
        self.pressure: List[float] = []

    # ─── QPainterPath変換 ───
    def to_qpath(self) -> QPainterPath:
        p = QPainterPath()
        if not self.nodes: return p
        p.moveTo(self.nodes[0].pos)
        for i in range(1, len(self.nodes)):
            prev, curr = self.nodes[i-1], self.nodes[i]
            p.cubicTo(prev.cp_out, curr.cp_in, curr.pos)
        if self.closed and len(self.nodes) >= 2:
            last, first = self.nodes[-1], self.nodes[0]
            p.cubicTo(last.cp_out, first.cp_in, first.pos)
            p.closeSubpath()
        return p

    def hit_test(self, pt: QPointF, r: float=8.0) -> bool:
        qp = self.to_qpath()
        st = QPainterPathStroker(); st.setWidth(max(self.stroke_width, r*2))
        if st.createStroke(qp).contains(pt): return True
        if self.fill_color.alpha() > 0: return qp.contains(pt)
        return False

    def node_at(self, pt: QPointF, r: float=8.0) -> Optional[VNode]:
        for n in self.nodes:
            if QLineF(n.pos, pt).length() < r: return n
        return None

    def cp_at(self, pt: QPointF, r: float=7.0):
        for n in self.nodes:
            if n.cp_in != n.pos and QLineF(n.cp_in, pt).length() < r:   return (n,'in')
            if n.cp_out != n.pos and QLineF(n.cp_out,pt).length() < r:  return (n,'out')
        return None

    def bounding_rect(self) -> QRectF:
        return self.to_qpath().boundingRect()

    def segment_at_t(self, t: float) -> QPointF:
        """パス全体の正規化パラメータtに対応する点"""
        qp = self.to_qpath()
        return qp.pointAtPercent(t)

    def insert_node_at(self, pt: QPointF) -> Optional[VNode]:
        """ptに最も近いセグメントにノードを挿入"""
        if len(self.nodes) < 2:
            return None
        best_i, best_t, best_dist = 0, 0.5, float('inf')
        n = len(self.nodes) + (1 if self.closed else 0)
        segs = len(self.nodes) - (0 if self.closed else 1)
        for i in range(segs):
            a = self.nodes[i]
            b = self.nodes[(i+1) % len(self.nodes)]
            for t in [j/20 for j in range(1,20)]:
                p = _cubic(a.pos, a.cp_out, b.cp_in, b.pos, t)
                d = QLineF(p, pt).length()
                if d < best_dist:
                    best_dist = d; best_i = i; best_t = t
        if best_dist > 30:
            return None
        # de Casteljau 分割
        i = best_i
        a = self.nodes[i]; b = self.nodes[(i+1)%len(self.nodes)]
        t = best_t
        p0,p1,p2,p3 = a.pos, a.cp_out, b.cp_in, b.pos
        q0 = _lerp(p0,p1,t); q1 = _lerp(p1,p2,t); q2 = _lerp(p2,p3,t)
        r0 = _lerp(q0,q1,t); r1 = _lerp(q1,q2,t)
        s  = _lerp(r0,r1,t)
        new_node = VNode(s, r0, r1)
        a.cp_out = q0; b.cp_in = q2
        self.nodes.insert(i+1, new_node)
        return new_node

    def clone(self) -> 'VPath':
        vp = VPath()
        vp.nodes       = [n.clone() for n in self.nodes]
        vp.closed      = self.closed
        vp.stroke_color= QColor(self.stroke_color)
        vp.stroke_width= self.stroke_width
        vp.fill_color  = QColor(self.fill_color)
        vp.opacity     = self.opacity
        vp.visible     = self.visible
        vp.brush_name  = self.brush_name
        vp.pressure    = list(self.pressure)
        return vp


class VGroup:
    """パスのグループ"""
    def __init__(self, name="グループ"):
        self.id      = uuid.uuid4().hex[:8]
        self.name    = name
        self.items: List[VPath] = []   # グループ内のパス (再帰グループ非対応・今後拡張)
        self.opacity = 1.0
        self.visible = True

    def bounding_rect(self) -> QRectF:
        r = QRectF()
        for p in self.items:
            r = r.united(p.bounding_rect())
        return r


# Layer の items は VPath または VGroup
LayerItem = object  # VPath | VGroup

class Layer:
    def __init__(self, name="レイヤー"):
        self.id      = uuid.uuid4().hex[:8]
        self.name    = name
        self.items:  List[LayerItem] = []
        self.visible = True
        self.locked  = False
        self.opacity = 1.0
        self.blend   = "通常"

    @property
    def paths(self) -> List[VPath]:
        """全VPathをフラットに返す"""
        result = []
        for item in self.items:
            if isinstance(item, VPath):
                result.append(item)
            elif isinstance(item, VGroup):
                result.extend(item.items)
        return result

    def add_path(self, vp: VPath):
        self.items.append(vp)

    def remove_path(self, vp: VPath):
        if vp in self.items:
            self.items.remove(vp)
        else:
            for item in self.items:
                if isinstance(item, VGroup) and vp in item.items:
                    item.items.remove(vp)
                    return


class Document:
    def __init__(self, w=1200, h=800):
        self.width  = w
        self.height = h
        self.layers: List[Layer] = [Layer("レイヤー 1")]
        self.active_layer_idx = 0
        self.symmetry = SYM_NONE
        self.sym_cx   = w / 2
        self.sym_cy   = h / 2

    @property
    def active_layer(self) -> Layer:
        return self.layers[self.active_layer_idx]

    def all_paths(self):
        for layer in self.layers:
            for p in layer.paths:
                yield (layer, p)

    def find_path(self, pid: str):
        for layer in self.layers:
            for item in layer.items:
                if isinstance(item, VPath) and item.id == pid:
                    return (layer, item)
                elif isinstance(item, VGroup):
                    for p in item.items:
                        if p.id == pid: return (layer, p)
        return (None, None)

    def find_group_of(self, vp: VPath):
        for layer in self.layers:
            for item in layer.items:
                if isinstance(item, VGroup) and vp in item.items:
                    return (layer, item)
        return (None, None)


# ══════════════════════════════════════════════
#  ユーティリティ
# ══════════════════════════════════════════════

def _lerp(a: QPointF, b: QPointF, t: float) -> QPointF:
    return QPointF(a.x()*(1-t)+b.x()*t, a.y()*(1-t)+b.y()*t)

def _cubic(p0,p1,p2,p3,t) -> QPointF:
    u = 1-t
    return QPointF(
        u**3*p0.x() + 3*u**2*t*p1.x() + 3*u*t**2*p2.x() + t**3*p3.x(),
        u**3*p0.y() + 3*u**2*t*p1.y() + 3*u*t**2*p2.y() + t**3*p3.y(),
    )

def sym_points(doc: Document, pt: QPointF) -> List[QPointF]:
    """シンメトリー設定に基づく対称点リストを返す (元の点は含まない)"""
    cx, cy = doc.sym_cx, doc.sym_cy
    x, y   = pt.x(), pt.y()
    if doc.symmetry == SYM_H:
        return [QPointF(2*cx - x, y)]
    elif doc.symmetry == SYM_V:
        return [QPointF(x, 2*cy - y)]
    elif doc.symmetry == SYM_CROSS:
        return [QPointF(2*cx-x, y), QPointF(x, 2*cy-y), QPointF(2*cx-x, 2*cy-y)]
    return []

def sym_cp_mirror(doc: Document, node: VNode, orig_out: QPointF,
                  sym_node: VNode, which: str):
    """シンメトリー対称ノードのCPをミラーリング"""
    cx, cy = doc.sym_cx, doc.sym_cy
    dx = orig_out.x() - node.pos.x()
    dy = orig_out.y() - node.pos.y()
    if which == 'h':
        sym_node.cp_out = QPointF(sym_node.pos.x()-dx, sym_node.pos.y()+dy)
        sym_node.cp_in  = QPointF(sym_node.pos.x()+dx, sym_node.pos.y()-dy)
    elif which == 'v':
        sym_node.cp_out = QPointF(sym_node.pos.x()+dx, sym_node.pos.y()-dy)
        sym_node.cp_in  = QPointF(sym_node.pos.x()-dx, sym_node.pos.y()+dy)


# ══════════════════════════════════════════════
#  SVG 入出力
# ══════════════════════════════════════════════

def _pt(p: QPointF) -> str:
    return f"{p.x():.3f},{p.y():.3f}"

def path_to_d(vp: VPath) -> str:
    ns = vp.nodes
    if not ns: return ""
    parts = [f"M {_pt(ns[0].pos)}"]
    for i in range(1, len(ns)):
        a,b = ns[i-1], ns[i]
        parts.append(f"C {_pt(a.cp_out)} {_pt(b.cp_in)} {_pt(b.pos)}")
    if vp.closed and len(ns)>=2:
        a,b = ns[-1], ns[0]
        parts.append(f"C {_pt(a.cp_out)} {_pt(b.cp_in)} {_pt(b.pos)} Z")
    return " ".join(parts)

def col(c: QColor) -> str:
    return "none" if c.alpha()==0 else c.name()

def document_to_svg(doc: Document) -> str:
    root = ET.Element("svg", {
        "xmlns":  "http://www.w3.org/2000/svg",
        "width":  str(doc.width),
        "height": str(doc.height),
        "viewBox": f"0 0 {doc.width} {doc.height}",
        "data-app": "VektorStudio",
        "data-symmetry": doc.symmetry,
    })
    for layer in doc.layers:
        g = ET.SubElement(root, "g", {
            "id": f"layer-{layer.id}",
            "data-name": layer.name,
            "data-blend": layer.blend,
            "opacity": str(layer.opacity),
        })
        if not layer.visible: g.set("display","none")
        if layer.locked:      g.set("data-locked","1")
        for item in layer.items:
            if isinstance(item, VPath):
                _path_to_svg_el(g, item)
            elif isinstance(item, VGroup):
                gg = ET.SubElement(g, "g", {
                    "id": f"group-{item.id}",
                    "data-name": item.name,
                    "opacity": str(item.opacity),
                    "data-group": "1",
                })
                if not item.visible: gg.set("display","none")
                for vp in item.items:
                    _path_to_svg_el(gg, vp)
    return ET.tostring(root, pretty_print=True, xml_declaration=True,
                       encoding="UTF-8").decode()

def _path_to_svg_el(parent, vp: VPath):
    d = path_to_d(vp)
    if not d: return
    attrs = {
        "id": f"path-{vp.id}",
        "d":  d,
        "stroke": col(vp.stroke_color),
        "stroke-width": str(vp.stroke_width),
        "fill":   col(vp.fill_color),
        "opacity": str(vp.opacity),
        "stroke-linecap":  "round",
        "stroke-linejoin": "round",
        "data-brush": vp.brush_name,
    }
    if not vp.visible: attrs["display"] = "none"
    ET.SubElement(parent, "path", attrs)

def svg_to_document(svg_text: str) -> Document:
    import re
    root   = ET.fromstring(svg_text.encode())
    ns_map = {"svg": "http://www.w3.org/2000/svg"}

    def strip_ns(tag): return tag.split("}")[-1]

    w = float(root.get("width",1200))
    h = float(root.get("height",800))
    doc = Document(int(w), int(h))
    doc.symmetry = root.get("data-symmetry", SYM_NONE)
    doc.layers = []

    def parse_path_el(el) -> Optional[VPath]:
        d = el.get("d","")
        if not d: return None
        return _d_to_vpath(d, dict(el.attrib))

    def parse_g(g_el) -> Layer:
        name  = g_el.get("data-name", g_el.get("id","レイヤー"))
        layer = Layer(name)
        try: layer.opacity = float(g_el.get("opacity","1"))
        except: pass
        layer.blend   = g_el.get("data-blend","通常")
        layer.visible = g_el.get("display","") != "none"
        layer.locked  = g_el.get("data-locked","0") == "1"
        for child in g_el:
            tag = strip_ns(child.tag)
            if tag == "path":
                vp = parse_path_el(child)
                if vp: layer.items.append(vp)
            elif tag == "g":
                if child.get("data-group") == "1":
                    grp = VGroup(child.get("data-name","グループ"))
                    try: grp.opacity = float(child.get("opacity","1"))
                    except: pass
                    grp.visible = child.get("display","") != "none"
                    for sub in child:
                        if strip_ns(sub.tag) == "path":
                            vp = parse_path_el(sub)
                            if vp: grp.items.append(vp)
                    layer.items.append(grp)
        return layer

    # 最上位のg → レイヤー扱い
    gs = [c for c in root if strip_ns(c.tag)=="g"]
    if gs:
        for g_el in gs:
            doc.layers.append(parse_g(g_el))
    else:
        # gなし → 直接pathがある
        layer = Layer("レイヤー 1")
        for el in root:
            if strip_ns(el.tag)=="path":
                vp = parse_path_el(el)
                if vp: layer.items.append(vp)
        doc.layers.append(layer)

    if not doc.layers: doc.layers = [Layer("レイヤー 1")]
    doc.active_layer_idx = 0
    return doc

def _d_to_vpath(d: str, attrs: dict) -> Optional[VPath]:
    import re
    vp = VPath()
    toks = re.findall(r'[MCZmczLlHhVvSsQqTtAa]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', d)
    i = 0; last = QPointF(0,0); nodes = []
    def rf():
        nonlocal i; v=float(toks[i]); i+=1; return v
    def is_cmd(): return i<len(toks) and toks[i] in 'MCZmczLlHhVvSsQqTtAa'
    while i<len(toks):
        cmd=toks[i]; i+=1
        if cmd in('M','m'):
            x,y=rf(),rf()
            if cmd=='m': x+=last.x(); y+=last.y()
            n=VNode(QPointF(x,y)); nodes.append(n); last=QPointF(x,y)
        elif cmd in('C','c'):
            while not is_cmd() and i+5<len(toks)+1:
                try:
                    x1,y1=rf(),rf(); x2,y2=rf(),rf(); ex,ey=rf(),rf()
                except: break
                if cmd=='c': x1+=last.x();y1+=last.y();x2+=last.x();y2+=last.y();ex+=last.x();ey+=last.y()
                if nodes: nodes[-1].cp_out=QPointF(x1,y1)
                n=VNode(QPointF(ex,ey),QPointF(x2,y2)); nodes.append(n); last=QPointF(ex,ey)
        elif cmd in('L','l'):
            while not is_cmd() and i+1<len(toks)+1:
                try: x,y=rf(),rf()
                except: break
                if cmd=='l': x+=last.x(); y+=last.y()
                n=VNode(QPointF(x,y)); nodes.append(n); last=QPointF(x,y)
        elif cmd in('Z','z'):
            vp.closed=True
    if not nodes: return None
    vp.nodes = nodes
    s = attrs.get("stroke","none")
    vp.stroke_color = QColor(s) if s not in("none","") else QColor(Qt.transparent)
    try: vp.stroke_width = float(attrs.get("stroke-width","2"))
    except: vp.stroke_width = 2.0
    f = attrs.get("fill","none")
    vp.fill_color = QColor(f) if f not in("none","") else QColor(Qt.transparent)
    try: vp.opacity = float(attrs.get("opacity","1"))
    except: vp.opacity = 1.0
    vp.brush_name = attrs.get("data-brush","Gペン")
    vp.visible = attrs.get("display","") != "none"
    return vp


# ══════════════════════════════════════════════
#  Undo コマンド群
# ══════════════════════════════════════════════

class CmdAddPath(QUndoCommand):
    def __init__(self, layer, vp):
        super().__init__("パス追加"); self.layer=layer; self.vp=vp
    def redo(self): self.layer.add_path(self.vp)
    def undo(self): self.layer.remove_path(self.vp)

class CmdDeletePaths(QUndoCommand):
    def __init__(self, pairs):  # [(layer, vp), ...]
        super().__init__("削除"); self.pairs=pairs
    def redo(self):
        for layer, vp in self.pairs: layer.remove_path(vp)
    def undo(self):
        for layer, vp in self.pairs: layer.add_path(vp)

class CmdMoveNode(QUndoCommand):
    def __init__(self, node, op, np_, oci, oco, nci, nco):
        super().__init__("ノード移動")
        self.node=node; self.op=op; self.np_=np_
        self.oci=oci; self.oco=oco; self.nci=nci; self.nco=nco
    def redo(self): self.node.pos=QPointF(self.np_); self.node.cp_in=QPointF(self.nci); self.node.cp_out=QPointF(self.nco)
    def undo(self): self.node.pos=QPointF(self.op);  self.node.cp_in=QPointF(self.oci); self.node.cp_out=QPointF(self.oco)

class CmdMovePaths(QUndoCommand):
    def __init__(self, snapshots_before, snapshots_after):
        super().__init__("移動")
        self.before = snapshots_before  # {vp: [(pos,cpi,cpo),...]}
        self.after  = snapshots_after
    def _apply(self, snaps):
        for vp, node_states in snaps.items():
            for n, (pos,cpi,cpo) in zip(vp.nodes, node_states):
                n.pos=QPointF(pos); n.cp_in=QPointF(cpi); n.cp_out=QPointF(cpo)
    def redo(self): self._apply(self.after)
    def undo(self): self._apply(self.before)

class CmdGroupPaths(QUndoCommand):
    def __init__(self, layer, paths, group):
        super().__init__("グループ化")
        self.layer=layer; self.paths=paths; self.group=group
    def redo(self):
        for vp in self.paths:
            if vp in self.layer.items: self.layer.items.remove(vp)
        self.layer.items.append(self.group)
    def undo(self):
        if self.group in self.layer.items: self.layer.items.remove(self.group)
        for vp in self.paths: self.layer.items.append(vp)

class CmdUngroupPaths(QUndoCommand):
    def __init__(self, layer, group):
        super().__init__("グループ解除")
        self.layer=layer; self.group=group
    def redo(self):
        if self.group in self.layer.items: self.layer.items.remove(self.group)
        for vp in self.group.items: self.layer.items.append(vp)
    def undo(self):
        for vp in self.group.items:
            if vp in self.layer.items: self.layer.items.remove(vp)
        self.layer.items.append(self.group)

class CmdSetStrokeWidth(QUndoCommand):
    def __init__(self, vp, old_w, new_w):
        super().__init__("線幅変更"); self.vp=vp; self.old=old_w; self.new=new_w
    def redo(self): self.vp.stroke_width=self.new
    def undo(self): self.vp.stroke_width=self.old

class CmdInsertNode(QUndoCommand):
    def __init__(self, vp, node, idx):
        super().__init__("ノード追加"); self.vp=vp; self.node=node; self.idx=idx
    def redo(self): self.vp.nodes.insert(self.idx, self.node)
    def undo(self): self.vp.nodes.remove(self.node)

class CmdDeleteNode(QUndoCommand):
    def __init__(self, vp, node, idx):
        super().__init__("ノード削除"); self.vp=vp; self.node=node; self.idx=idx
    def redo(self):
        if self.node in self.vp.nodes: self.vp.nodes.remove(self.node)
    def undo(self): self.vp.nodes.insert(self.idx, self.node)


# ══════════════════════════════════════════════
#  ブラシエンジン
# ══════════════════════════════════════════════

def apply_brush_stroke(painter: QPainter, vp: VPath):
    """ブラシプロファイルに基づいてストロークを描画"""
    if len(vp.nodes) < 2:
        pen = QPen(vp.stroke_color, vp.stroke_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(vp.to_qpath()); return

    brush_def = BRUSHES.get(vp.brush_name, BRUSHES["Gペン"])
    if not brush_def["pressure_width"] or not vp.pressure:
        # 標準ストローク
        pen = QPen(vp.stroke_color, vp.stroke_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(vp.to_qpath()); return

    # 筆圧対応：セグメントごとに幅変化
    n = len(vp.nodes)
    pressures = vp.pressure if len(vp.pressure)==n else [1.0]*n
    for i in range(n-1):
        a, b = vp.nodes[i], vp.nodes[i+1]
        w = vp.stroke_width * ((pressures[i]+pressures[i+1])/2)
        pen = QPen(vp.stroke_color, max(0.5, w), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        seg = QPainterPath()
        seg.moveTo(a.pos)
        seg.cubicTo(a.cp_out, b.cp_in, b.pos)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(seg)


# ══════════════════════════════════════════════
#  バケツ塗り（ベクター）
# ══════════════════════════════════════════════

def bucket_fill(doc: Document, pt: QPointF, fill_color: QColor) -> Optional[VPath]:
    """クリック点を囲む閉じたパスを自動生成して塗る（簡易版）"""
    # クリック点付近の全パスを探し、最小の閉じ領域を推定
    candidates = []
    for layer, vp in doc.all_paths():
        if not layer.visible or layer.locked: continue
        br = vp.bounding_rect()
        if br.contains(pt): candidates.append(vp)

    if not candidates: return None

    # 最小バウンディングのパスを選択
    best = min(candidates, key=lambda p: p.bounding_rect().width()*p.bounding_rect().height())
    if best.fill_color.alpha() == 0:
        new_vp = best.clone()
        new_vp.fill_color = QColor(fill_color)
        new_vp.stroke_color = QColor(Qt.transparent)
        new_vp.closed = True
        return new_vp
    else:
        best.fill_color = QColor(fill_color)
        return None  # 既存パスを更新したことをNoneで示す (caller側で対処)


# ══════════════════════════════════════════════
#  交差点消しゴム
# ══════════════════════════════════════════════

def scissors_cut(vp: VPath, pt: QPointF, radius: float=10.0) -> List[VPath]:
    """パスを指定点付近で切断し、2つのパスに分割"""
    if len(vp.nodes) < 3 or vp.closed:
        return []
    # 最も近いノードインデックスを探す
    best_i = min(range(len(vp.nodes)), key=lambda i: QLineF(vp.nodes[i].pos, pt).length())
    if QLineF(vp.nodes[best_i].pos, pt).length() > radius*2:
        return []
    if best_i == 0 or best_i == len(vp.nodes)-1:
        return []

    vp1 = VPath()
    vp1.nodes = [n.clone() for n in vp.nodes[:best_i+1]]
    vp1.stroke_color = QColor(vp.stroke_color)
    vp1.stroke_width = vp.stroke_width
    vp1.fill_color   = QColor(vp.fill_color)
    vp1.brush_name   = vp.brush_name

    vp2 = VPath()
    vp2.nodes = [n.clone() for n in vp.nodes[best_i:]]
    vp2.stroke_color = QColor(vp.stroke_color)
    vp2.stroke_width = vp.stroke_width
    vp2.fill_color   = QColor(vp.fill_color)
    vp2.brush_name   = vp.brush_name

    return [vp1, vp2]


# ══════════════════════════════════════════════
#  キャンバス
# ══════════════════════════════════════════════

class Canvas(QWidget):
    status_changed    = Signal(str)
    selection_changed = Signal(list)   # List[VPath]
    document_changed  = Signal()

    def __init__(self, doc: Document, undo: QUndoStack):
        super().__init__()
        self.doc   = doc
        self.undo  = undo
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # ビュー
        self._scale  = 1.0
        self._offset = QPointF(40,40)
        self._pan_start = None; self._pan_off = None

        # ツール
        self.tool = TOOL_PEN
        self.pen_color  = QColor(C["stroke_def"])
        self.pen_width  = 2.0
        self.fill_color = QColor(Qt.transparent)
        self.brush_name = "Gペン"

        # 選択
        self.selected: List[VPath] = []   # 複数選択対応
        self._rubber_band_start: Optional[QPointF] = None
        self._rubber_band_rect:  Optional[QRectF]  = None

        # Reshape
        self.sel_node: Optional[VNode] = None
        self.sel_cp  = None
        self._node_before = None
        self._drag_start: Optional[QPointF] = None
        self._drag_path_snaps = {}

        # ペン描画
        self._pen_path: Optional[VPath]   = None
        self._pen_drawing  = False
        self._pen_sym_paths: List[VPath]  = []   # シンメトリー対応パス

        # ホバー
        self._hover_node: Optional[VNode] = None
        self._hover_path: Optional[VPath] = None

        # バウンディングボックス変形
        self._bb_handle: Optional[str] = None   # 'tl','tr','bl','br','rot'
        self._bb_before_snaps = {}
        self._bb_start_pt: Optional[QPointF] = None
        self._bb_start_rect: Optional[QRectF] = None
        self._bb_start_angle: float = 0.0
        self._bb_rot_center: Optional[QPointF] = None

        self.setMinimumSize(400, 300)

    # ─── 座標変換 ───
    def to_doc(self, p: QPointF) -> QPointF:
        return QPointF((p.x()-self._offset.x())/self._scale,
                       (p.y()-self._offset.y())/self._scale)
    def to_scr(self, p: QPointF) -> QPointF:
        return QPointF(p.x()*self._scale+self._offset.x(),
                       p.y()*self._scale+self._offset.y())

    def set_tool(self, t: str):
        self.tool = t
        cur = {
            TOOL_PEN:Qt.CrossCursor, TOOL_RESHAPE:Qt.ArrowCursor,
            TOOL_SELECT:Qt.ArrowCursor, TOOL_HAND:Qt.OpenHandCursor,
            TOOL_ERASER:Qt.CrossCursor, TOOL_ADD_NODE:Qt.CrossCursor,
            TOOL_DEL_NODE:Qt.CrossCursor, TOOL_WIDTH:Qt.SizeHorCursor,
            TOOL_BUCKET:Qt.CrossCursor, TOOL_SCISSORS:Qt.CrossCursor,
        }.get(t, Qt.ArrowCursor)
        self.setCursor(cur)
        if t not in (TOOL_RESHAPE, TOOL_SELECT):
            self.selected = []; self.sel_node=None; self.selection_changed.emit([])
        self._pen_path=None; self._pen_drawing=False; self._pen_sym_paths=[]
        self.update()

    # ─── Paint ───
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 背景
        p.fillRect(self.rect(), QColor(C["bg"]))
        self._draw_grid(p)
        p.save()
        p.translate(self._offset); p.scale(self._scale, self._scale)
        # キャンバス影
        p.fillRect(QRectF(4,4,self.doc.width+4,self.doc.height+4), QColor(0,0,0,70))
        p.fillRect(QRectF(0,0,self.doc.width,self.doc.height), QColor(C["canvas_bg"]))
        # シンメトリーガイド
        self._draw_sym_guide(p)
        # レイヤー描画
        for layer in self.doc.layers:
            if not layer.visible: continue
            p.setOpacity(layer.opacity)
            mode = BLEND_MAP.get(layer.blend, QPainter.CompositionMode_SourceOver)
            p.setCompositionMode(mode)
            for item in layer.items:
                if isinstance(item, VPath):   self._draw_path(p, item)
                elif isinstance(item, VGroup):
                    p.setOpacity(layer.opacity * item.opacity)
                    for vp in item.items: self._draw_path(p, vp)
                    p.setOpacity(layer.opacity)
            p.setOpacity(1.0)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        # ペン描画中プレビュー
        if self._pen_path and self._pen_drawing:
            self._draw_path(p, self._pen_path, preview=True)
            for sp in self._pen_sym_paths:
                self._draw_path(p, sp, preview=True, sym=True)
        p.restore()
        # Reshape オーバーレイ
        if self.tool in (TOOL_RESHAPE, TOOL_ADD_NODE, TOOL_DEL_NODE):
            self._draw_reshape_overlay(p)
        # バウンディングボックス
        if self.tool == TOOL_SELECT and self.selected:
            self._draw_bounding_box(p)
        # ラバーバンド
        if self._rubber_band_rect:
            pen = QPen(QColor(C["accent"]),1,Qt.DashLine)
            p.setPen(pen); p.setBrush(QColor(C["accent"]+"22"))
            p.drawRect(self._rubber_band_rect)

    def _draw_grid(self, p: QPainter):
        step = 40 * self._scale
        if step < 8: return
        p.setPen(QPen(QColor(C["canvas_grid"]), 0.5))
        w,h = self.width(), self.height()
        ox = self._offset.x() % step; oy = self._offset.y() % step
        x=ox
        while x<w: p.drawLine(QPointF(x,0),QPointF(x,h)); x+=step
        y=oy
        while y<h: p.drawLine(QPointF(0,y),QPointF(w,y)); y+=step

    def _draw_sym_guide(self, p: QPainter):
        sym = self.doc.symmetry
        if sym == SYM_NONE: return
        pen = QPen(QColor(C["sym_line"]), 1.0/self._scale, Qt.DashLine)
        p.setPen(pen)
        cx,cy = self.doc.sym_cx, self.doc.sym_cy
        W,H   = self.doc.width, self.doc.height
        if sym in (SYM_H, SYM_CROSS):
            p.drawLine(QPointF(cx,0), QPointF(cx,H))
        if sym in (SYM_V, SYM_CROSS):
            p.drawLine(QPointF(0,cy), QPointF(W,cy))

    def _draw_path(self, p: QPainter, vp: VPath, preview=False, sym=False):
        if not vp.visible: return
        p.setOpacity(vp.opacity)
        qpath = vp.to_qpath()
        # 塗り
        if vp.fill_color.alpha() > 0:
            p.fillPath(qpath, QBrush(vp.fill_color))
        # ストローク
        if not preview:
            apply_brush_stroke(p, vp)
        else:
            c = QColor(C["accent2"] if sym else C["accent"])
            c.setAlpha(160)
            pen = QPen(c, vp.stroke_width, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawPath(qpath)
        # 選択ハイライト
        if vp in self.selected and not preview:
            glow = QPen(QColor(C["accent"]+"30"), max(vp.stroke_width+10,14), Qt.SolidLine, Qt.RoundCap)
            p.setPen(glow); p.setBrush(Qt.NoBrush); p.drawPath(qpath)
            hi   = QPen(QColor(C["accent"]), max(vp.stroke_width+2,3), Qt.SolidLine, Qt.RoundCap)
            p.setPen(hi);   p.drawPath(qpath)
        p.setOpacity(1.0)

    def _draw_reshape_overlay(self, p: QPainter):
        if not self.selected: return
        vp = self.selected[0]
        p.save()
        p.translate(self._offset); p.scale(self._scale, self._scale)
        nr = 5/self._scale; cr = 4/self._scale

        # CP lines for selected node
        show_cp = (self.sel_node is not None)
        for i, node in enumerate(vp.nodes):
            is_sel = node is self.sel_node
            if is_sel or show_cp:
                for cp, cp_other in [(node.cp_in,'in'),(node.cp_out,'out')]:
                    if cp != node.pos:
                        dash = QPen(QColor(C["fg_dim"]), 0.8/self._scale, Qt.DotLine)
                        p.setPen(dash); p.drawLine(node.pos, cp)
                        cr2 = cr*(1.2 if (self.sel_cp and self.sel_cp[0] is node and self.sel_cp[1]==cp_other) else 1)
                        p.setBrush(QBrush(QColor(C["accent2"])))
                        p.setPen(QPen(QColor("white"),0.8/self._scale))
                        p.drawEllipse(QRectF(cp.x()-cr2,cp.y()-cr2,cr2*2,cr2*2))
            # アンカーノード
            is_hov = node is self._hover_node
            r = nr*(1.4 if is_sel else 1.1 if is_hov else 1.0)
            rect = QRectF(node.pos.x()-r, node.pos.y()-r, r*2, r*2)
            brush_c = C["node_sel"] if is_sel else (C["accent"] if is_hov else C["node_fill"])
            if self.tool == TOOL_DEL_NODE and is_hov:
                brush_c = C["danger"]
            p.setBrush(QBrush(QColor(brush_c)))
            p.setPen(QPen(QColor("white"),1.0/self._scale))
            p.drawRect(rect)
        p.restore()

    def _draw_bounding_box(self, p: QPainter):
        br = self._get_selection_rect()
        if br.isNull(): return
        tl = self.to_scr(br.topLeft()); br2 = self.to_scr(br.bottomRight())
        rect = QRectF(tl, br2).adjusted(-4,-4,4,4)
        pen = QPen(QColor(C["accent"]),1,Qt.DashLine)
        p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawRect(rect)
        # ハンドル
        hs = 7
        corners = [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()]
        for c in corners:
            p.setBrush(QBrush(QColor(C["accent"])))
            p.setPen(QPen(QColor("white"),1))
            p.drawRect(QRectF(c.x()-hs/2, c.y()-hs/2, hs, hs))
        # 回転ハンドル
        rot_pt = QPointF(rect.center().x(), rect.top()-20)
        p.setPen(QPen(QColor(C["accent"]),1))
        p.drawLine(QPointF(rect.center().x(), rect.top()), rot_pt)
        p.setBrush(QBrush(QColor(C["accent2"])))
        p.setPen(QPen(QColor("white"),1))
        p.drawEllipse(QRectF(rot_pt.x()-5, rot_pt.y()-5, 10, 10))

    # ─── ヒットテスト ───
    def _hit_paths(self, doc_pos: QPointF) -> Optional[VPath]:
        r = 6/self._scale
        for layer in reversed(self.doc.layers):
            if not layer.visible or layer.locked: continue
            for item in reversed(layer.items):
                if isinstance(item, VGroup):
                    for vp in reversed(item.items):
                        if vp.hit_test(doc_pos, r): return vp
                elif isinstance(item, VPath):
                    if item.hit_test(doc_pos, r): return item
        return None

    def _get_selection_rect(self) -> QRectF:
        r = QRectF()
        for vp in self.selected: r = r.united(vp.bounding_rect())
        return r

    def _bb_handle_at(self, scr_pos: QPointF) -> Optional[str]:
        if not self.selected: return None
        br = self._get_selection_rect()
        tl = self.to_scr(br.topLeft()); br2 = self.to_scr(br.bottomRight())
        rect = QRectF(tl, br2).adjusted(-4,-4,4,4)
        hs = 10
        corners = {
            'tl': rect.topLeft(), 'tr': rect.topRight(),
            'bl': rect.bottomLeft(), 'br': rect.bottomRight()
        }
        for name, c in corners.items():
            if QRectF(c.x()-hs/2, c.y()-hs/2, hs, hs).contains(scr_pos): return name
        rot_pt = QPointF(rect.center().x(), rect.top()-20)
        if QLineF(rot_pt, scr_pos).length() < 8: return 'rot'
        return None

    def _snap_before(self):
        snaps = {}
        for vp in self.selected:
            snaps[vp] = [(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out)) for n in vp.nodes]
        return snaps

    # ─── マウス ───
    def mousePressEvent(self, ev):
        pos = ev.position(); doc_pos = self.to_doc(pos)
        if ev.button()==Qt.MiddleButton or (ev.button()==Qt.LeftButton and ev.modifiers()&Qt.AltModifier):
            self._pan_start=pos; self._pan_off=QPointF(self._offset); self.setCursor(Qt.ClosedHandCursor); return
        if ev.button()==Qt.LeftButton:
            mods = ev.modifiers()
            if   self.tool==TOOL_PEN:      self._pen_press(doc_pos)
            elif self.tool==TOOL_RESHAPE:  self._reshape_press(doc_pos)
            elif self.tool==TOOL_SELECT:   self._select_press(pos, doc_pos, mods)
            elif self.tool==TOOL_ERASER:   self._eraser_press(doc_pos)
            elif self.tool==TOOL_ADD_NODE: self._add_node_press(doc_pos)
            elif self.tool==TOOL_DEL_NODE: self._del_node_press(doc_pos)
            elif self.tool==TOOL_WIDTH:    self._width_press(doc_pos)
            elif self.tool==TOOL_BUCKET:   self._bucket_press(doc_pos)
            elif self.tool==TOOL_SCISSORS: self._scissors_press(doc_pos)
        elif ev.button()==Qt.RightButton:
            self._context_menu(ev.globalPosition().toPoint())

    def mouseMoveEvent(self, ev):
        pos=ev.position(); doc_pos=self.to_doc(pos)
        if self._pan_start:
            delta=pos-self._pan_start; self._offset=self._pan_off+delta; self.update(); return
        if ev.buttons()&Qt.LeftButton:
            if   self.tool==TOOL_PEN:     self._pen_drag(doc_pos)
            elif self.tool==TOOL_RESHAPE: self._reshape_drag(doc_pos)
            elif self.tool==TOOL_SELECT:  self._select_drag(pos, doc_pos)
            elif self.tool==TOOL_WIDTH:   self._width_drag(doc_pos)
        else:
            self._update_hover(doc_pos)
        x,y=doc_pos.x(),doc_pos.y()
        self.status_changed.emit(f"  X:{x:.1f}  Y:{y:.1f}  |  ズーム:{self._scale*100:.0f}%")

    def mouseReleaseEvent(self, ev):
        if self._pan_start:
            self._pan_start=None; self.setCursor(Qt.ArrowCursor if self.tool!=TOOL_HAND else Qt.OpenHandCursor); return
        if ev.button()==Qt.LeftButton:
            doc_pos = self.to_doc(ev.position())
            if   self.tool==TOOL_PEN:     self._pen_release(doc_pos)
            elif self.tool==TOOL_RESHAPE: self._reshape_release(doc_pos)
            elif self.tool==TOOL_SELECT:  self._select_release(doc_pos)
            elif self.tool==TOOL_WIDTH:   self._width_release(doc_pos)

    def mouseDoubleClickEvent(self, ev):
        if self.tool==TOOL_PEN: self._pen_finish()
        elif self.tool==TOOL_RESHAPE and self.selected:
            self.selected[0].closed = not self.selected[0].closed; self.update()

    def wheelEvent(self, ev):
        f = 1.12 if ev.angleDelta().y()>0 else 1/1.12
        pv = ev.position()
        self._offset = QPointF(pv.x()-(pv.x()-self._offset.x())*f,
                               pv.y()-(pv.y()-self._offset.y())*f)
        self._scale = max(0.02, min(self._scale*f, 64.0))
        self.update()

    def keyPressEvent(self, ev):
        k=ev.key(); mods=ev.modifiers()
        if k in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.sel_node and self.selected:
                vp = self.selected[0]
                idx = vp.nodes.index(self.sel_node) if self.sel_node in vp.nodes else -1
                if idx>=0:
                    self.undo.push(CmdDeleteNode(vp, self.sel_node, idx))
                    self.sel_node=None; self.update()
            elif self.selected:
                pairs = []
                for vp in self.selected:
                    layer, _ = self.doc.find_path(vp.id)
                    if layer: pairs.append((layer,vp))
                if pairs:
                    self.undo.push(CmdDeletePaths(pairs))
                    self.selected=[]; self.selection_changed.emit([])
                    self.document_changed.emit(); self.update()
        elif k==Qt.Key_Escape:
            if self._pen_drawing: self._pen_finish()
            else:
                self.selected=[]; self.sel_node=None; self.selection_changed.emit([])
                self.update()
        elif k==Qt.Key_G and mods==Qt.ControlModifier:
            self._group_selection()
        elif k==Qt.Key_G and mods==(Qt.ControlModifier|Qt.ShiftModifier):
            self._ungroup_selection()
        elif k==Qt.Key_A and mods==Qt.ControlModifier:
            self._select_all()
        # 矢印キーで移動
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 10 if mods&Qt.ShiftModifier else 1
            dx = (-step if k==Qt.Key_Left else step if k==Qt.Key_Right else 0)
            dy = (-step if k==Qt.Key_Up   else step if k==Qt.Key_Down  else 0)
            before = self._snap_before()
            for vp in self.selected:
                for n in vp.nodes:
                    n.pos    = n.pos    + QPointF(dx,dy)
                    n.cp_in  = n.cp_in  + QPointF(dx,dy)
                    n.cp_out = n.cp_out + QPointF(dx,dy)
            after = self._snap_before()
            self.undo.push(CmdMovePaths(before, after))
            self.document_changed.emit(); self.update()

    def contextMenuEvent(self, ev):
        self._context_menu(ev.globalPos())

    def _context_menu(self, gpos):
        menu = QMenu(self)
        if self.selected:
            menu.addAction("グループ化  Ctrl+G", self._group_selection)
            if len(self.selected)==1:
                layer,grp = self.doc.find_group_of(self.selected[0])
                if grp:
                    menu.addAction("グループ解除  Ctrl+Shift+G", self._ungroup_selection)
            menu.addSeparator()
            menu.addAction("削除  Del", lambda: self.keyPressEvent(
                type('E',(object,),{'key':lambda s:Qt.Key_Delete,'modifiers':lambda s:Qt.NoModifier})()))
            menu.addSeparator()
            menu.addAction("最前面へ", self._bring_to_front)
            menu.addAction("最背面へ", self._send_to_back)
        else:
            menu.addAction("すべて選択  Ctrl+A", self._select_all)
        menu.exec(gpos)

    # ─── ペンツール ───
    def _pen_press(self, dp: QPointF):
        if not self._pen_drawing:
            vp = VPath()
            vp.stroke_color = QColor(self.pen_color)
            vp.stroke_width = self.pen_width
            vp.fill_color   = QColor(self.fill_color)
            vp.brush_name   = self.brush_name
            self._pen_path  = vp
            self._pen_drawing = True
            # シンメトリー対応パスを初期化
            sym_pts = sym_points(self.doc, dp)
            self._pen_sym_paths = []
            for _ in sym_pts:
                sp = VPath()
                sp.stroke_color = QColor(self.pen_color); sp.stroke_color.setAlpha(140)
                sp.stroke_width = self.pen_width
                self._pen_sym_paths.append(sp)
        n = VNode(dp)
        self._pen_path.nodes.append(n)
        self._pen_path.pressure.append(1.0)
        # シンメトリーノード追加
        for sp, sym_pt in zip(self._pen_sym_paths, sym_points(self.doc, dp)):
            sn = VNode(sym_pt); sp.nodes.append(sn); sp.pressure.append(1.0)
        self.update()

    def _pen_drag(self, dp: QPointF):
        if not self._pen_drawing or not self._pen_path.nodes: return
        n = self._pen_path.nodes[-1]
        dx,dy = dp.x()-n.pos.x(), dp.y()-n.pos.y()
        n.cp_out = dp
        n.cp_in  = QPointF(n.pos.x()-dx, n.pos.y()-dy)
        # シンメトリー
        for sp, sym_pt in zip(self._pen_sym_paths, sym_points(self.doc, dp)):
            if not sp.nodes: continue
            sn = sp.nodes[-1]
            sdx,sdy = sym_pt.x()-sn.pos.x(), sym_pt.y()-sn.pos.y()
            sn.cp_out = sym_pt
            sn.cp_in  = QPointF(sn.pos.x()-sdx, sn.pos.y()-sdy)
        self.update()

    def _pen_release(self, dp: QPointF): pass

    def _pen_finish(self):
        if self._pen_path and len(self._pen_path.nodes)>=2:
            layer = self.doc.active_layer
            self.undo.beginMacro("ペン描画")
            self.undo.push(CmdAddPath(layer, self._pen_path))
            for sp in self._pen_sym_paths:
                if len(sp.nodes)>=2:
                    self.undo.push(CmdAddPath(layer, sp))
            self.undo.endMacro()
            self.selected = [self._pen_path]
            self.selection_changed.emit(self.selected)
            self.document_changed.emit()
        self._pen_path=None; self._pen_drawing=False; self._pen_sym_paths=[]
        self.update()

    # ─── Reshape ───
    def _reshape_press(self, dp: QPointF):
        if self.selected:
            vp = self.selected[0]
            cp = vp.cp_at(dp, 7/self._scale)
            if cp:
                self.sel_cp=cp; self._drag_start=dp; self.sel_node=cp[0]; return
            n = vp.node_at(dp, 8/self._scale)
            if n:
                self.sel_node=n; self.sel_cp=None; self._drag_start=dp
                self._node_before=(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out)); return
        hit = self._hit_paths(dp)
        if hit:
            self.selected=[hit]; self.selection_changed.emit(self.selected)
            n = min(hit.nodes, key=lambda x: QLineF(x.pos,dp).length(), default=None)
            self.sel_node=n; self._drag_start=dp
            if n: self._node_before=(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out))
        else:
            self.selected=[]; self.sel_node=None; self.selection_changed.emit([])
        self.update()

    def _reshape_drag(self, dp: QPointF):
        if not self._drag_start: return
        if self.sel_cp:
            node, which = self.sel_cp
            if which=='in':
                node.cp_in = dp
                if node.smooth:
                    dx,dy=dp.x()-node.pos.x(),dp.y()-node.pos.y()
                    node.cp_out=QPointF(node.pos.x()-dx,node.pos.y()-dy)
            else:
                node.cp_out=dp
                if node.smooth:
                    dx,dy=dp.x()-node.pos.x(),dp.y()-node.pos.y()
                    node.cp_in=QPointF(node.pos.x()-dx,node.pos.y()-dy)
        elif self.sel_node:
            self.sel_node.set_pos(dp)
        self.update()

    def _reshape_release(self, dp: QPointF):
        if self.sel_node and self._node_before and self._drag_start:
            n=self.sel_node; b=self._node_before
            if b[0]!=n.pos:
                self.undo.push(CmdMoveNode(n,b[0],QPointF(n.pos),b[1],b[2],QPointF(n.cp_in),QPointF(n.cp_out)))
                self.document_changed.emit()
        self.sel_cp=None; self._drag_start=None; self._node_before=None; self.update()

    # ─── Select ───
    def _select_press(self, scr_pos: QPointF, doc_pos: QPointF, mods):
        # バウンディングボックスハンドル?
        hndl = self._bb_handle_at(scr_pos)
        if hndl and self.selected:
            self._bb_handle=hndl; self._bb_start_pt=doc_pos
            self._bb_before_snaps=self._snap_before()
            self._bb_start_rect=self._get_selection_rect()
            if hndl=='rot':
                c=self._bb_start_rect.center()
                self._bb_rot_center=c
                self._bb_start_angle=math.degrees(math.atan2(doc_pos.y()-c.y(),doc_pos.x()-c.x()))
            return

        hit = self._hit_paths(doc_pos)
        if hit:
            if mods & Qt.ShiftModifier:
                if hit in self.selected: self.selected.remove(hit)
                else: self.selected.append(hit)
            else:
                if hit not in self.selected: self.selected=[hit]
            self.selection_changed.emit(self.selected)
            self._drag_start = doc_pos
            self._drag_path_snaps = self._snap_before()
            self._rubber_band_start=None
        else:
            if not (mods&Qt.ShiftModifier): self.selected=[]; self.selection_changed.emit([])
            self._rubber_band_start=scr_pos; self._rubber_band_rect=None
        self.update()

    def _select_drag(self, scr_pos: QPointF, doc_pos: QPointF):
        # バウンディングボックス変形
        if self._bb_handle and self._bb_start_rect:
            self._apply_bb_transform(doc_pos); self.update(); return
        # パス移動
        if self._drag_start and self.selected and self._drag_path_snaps:
            delta = doc_pos - self._drag_start
            for vp, states in self._drag_path_snaps.items():
                for n, (pos,cpi,cpo) in zip(vp.nodes, states):
                    n.pos=pos+delta; n.cp_in=cpi+delta; n.cp_out=cpo+delta
            self.update(); return
        # ラバーバンド
        if self._rubber_band_start:
            self._rubber_band_rect = QRectF(self._rubber_band_start, scr_pos).normalized()
            self.update()

    def _apply_bb_transform(self, doc_pos: QPointF):
        hndl = self._bb_handle
        sr   = self._bb_start_rect
        sp   = self._bb_start_pt
        if hndl=='rot':
            c=self._bb_rot_center
            cur_a=math.degrees(math.atan2(doc_pos.y()-c.y(),doc_pos.x()-c.x()))
            da = cur_a - self._bb_start_angle
            for vp, states in self._bb_before_snaps.items():
                for n,(pos,cpi,cpo) in zip(vp.nodes, states):
                    n.pos=_rotate_pt(pos,c,da); n.cp_in=_rotate_pt(cpi,c,da); n.cp_out=_rotate_pt(cpo,c,da)
            return
        # スケール
        dx,dy=doc_pos.x()-sp.x(),doc_pos.y()-sp.y()
        orig_w=max(sr.width(),1); orig_h=max(sr.height(),1)
        if   hndl=='br': sx=(orig_w+dx)/orig_w; sy=(orig_h+dy)/orig_h
        elif hndl=='tr': sx=(orig_w+dx)/orig_w; sy=(orig_h-dy)/orig_h
        elif hndl=='bl': sx=(orig_w-dx)/orig_w; sy=(orig_h+dy)/orig_h
        elif hndl=='tl': sx=(orig_w-dx)/orig_w; sy=(orig_h-dy)/orig_h
        else: sx=sy=1.0
        ox,oy = sr.left(),sr.top()
        for vp, states in self._bb_before_snaps.items():
            for n,(pos,cpi,cpo) in zip(vp.nodes, states):
                n.pos   =QPointF(ox+(pos.x()-ox)*sx, oy+(pos.y()-oy)*sy)
                n.cp_in =QPointF(ox+(cpi.x()-ox)*sx, oy+(cpi.y()-oy)*sy)
                n.cp_out=QPointF(ox+(cpo.x()-ox)*sx, oy+(cpo.y()-oy)*sy)

    def _select_release(self, doc_pos: QPointF):
        if self._bb_handle:
            after = self._snap_before()
            self.undo.push(CmdMovePaths(self._bb_before_snaps, after))
            self._bb_handle=None; self.document_changed.emit(); self.update(); return
        if self._drag_start and self.selected and self._drag_path_snaps:
            after = self._snap_before()
            # 実際に動いたか確認
            moved = any(
                any(n.pos != s[0] for n,s in zip(vp.nodes,states))
                for vp,states in self._drag_path_snaps.items()
            )
            if moved:
                self.undo.push(CmdMovePaths(self._drag_path_snaps, after))
                self.document_changed.emit()
            self._drag_start=None; self._drag_path_snaps={}; self.update(); return
        if self._rubber_band_rect:
            rect = self._rubber_band_rect
            for layer in self.doc.layers:
                if not layer.visible or layer.locked: continue
                for vp in layer.paths:
                    br_scr = QRectF(self.to_scr(vp.bounding_rect().topLeft()),
                                    self.to_scr(vp.bounding_rect().bottomRight()))
                    if rect.intersects(br_scr) and vp not in self.selected:
                        self.selected.append(vp)
            self.selection_changed.emit(self.selected)
            self._rubber_band_rect=None; self._rubber_band_start=None; self.update()

    # ─── 消しゴム ───
    def _eraser_press(self, dp: QPointF):
        hit = self._hit_paths(dp)
        if hit:
            layer, _ = self.doc.find_path(hit.id)
            if layer:
                self.undo.push(CmdDeletePaths([(layer,hit)]))
                if hit in self.selected: self.selected.remove(hit)
                self.selection_changed.emit(self.selected)
                self.document_changed.emit(); self.update()

    # ─── アンカー追加 ───
    def _add_node_press(self, dp: QPointF):
        hit = self._hit_paths(dp)
        if not hit:
            if self.selected: hit=self.selected[0]
        if not hit: return
        old_nodes = list(hit.nodes)
        new_node = hit.insert_node_at(dp)
        if new_node:
            idx = hit.nodes.index(new_node)
            # insertは既にdone済みなので rollback してコマンド経由で
            hit.nodes = old_nodes
            self.undo.push(CmdInsertNode(hit, new_node, idx))
            self.selected=[hit]; self.sel_node=new_node
            self.selection_changed.emit(self.selected)
            self.document_changed.emit(); self.update()

    # ─── アンカー削除 ───
    def _del_node_press(self, dp: QPointF):
        for vp in (self.selected or []):
            n = vp.node_at(dp, 8/self._scale)
            if n and n in vp.nodes:
                idx = vp.nodes.index(n)
                self.undo.push(CmdDeleteNode(vp, n, idx))
                if self.sel_node is n: self.sel_node=None
                self.document_changed.emit(); self.update(); return
        hit = self._hit_paths(dp)
        if hit:
            n = hit.node_at(dp, 8/self._scale)
            if n:
                idx = hit.nodes.index(n)
                self.undo.push(CmdDeleteNode(hit, n, idx))
                self.document_changed.emit(); self.update()

    # ─── 線幅編集 ───
    def _width_press(self, dp: QPointF):
        hit = self._hit_paths(dp)
        if hit:
            self.selected=[hit]; self._drag_start=dp
            self._width_old = hit.stroke_width
            self.selection_changed.emit(self.selected)
        self.update()

    def _width_drag(self, dp: QPointF):
        if not self.selected or not self._drag_start: return
        vp = self.selected[0]
        delta = dp.x() - self._drag_start.x()
        vp.stroke_width = max(0.1, self._width_old + delta*0.05)
        self.update()

    def _width_release(self, dp: QPointF):
        if self.selected and hasattr(self,'_width_old'):
            vp = self.selected[0]
            new_w = vp.stroke_width
            if new_w != self._width_old:
                # 現在の値を一旦元に戻してからコマンド経由で適用
                vp.stroke_width = self._width_old
                self.undo.push(CmdSetStrokeWidth(vp, self._width_old, new_w))
                self.document_changed.emit()
            self._drag_start=None

    # ─── バケツ ───
    def _bucket_press(self, dp: QPointF):
        result = bucket_fill(self.doc, dp, self.fill_color)
        if result:
            layer = self.doc.active_layer
            self.undo.push(CmdAddPath(layer, result))
            self.selected=[result]; self.selection_changed.emit(self.selected)
            self.document_changed.emit(); self.update()
        else:
            # 既存パスの塗りが更新された
            self.document_changed.emit(); self.update()

    # ─── 交差点消しゴム ───
    def _scissors_press(self, dp: QPointF):
        for layer in self.doc.layers:
            if not layer.visible or layer.locked: continue
            for vp in layer.paths:
                r = 10/self._scale
                if not vp.hit_test(dp, r): continue
                parts = scissors_cut(vp, dp, r)
                if parts:
                    self.undo.beginMacro("パスを切断")
                    self.undo.push(CmdDeletePaths([(layer,vp)]))
                    for p in parts: self.undo.push(CmdAddPath(layer, p))
                    self.undo.endMacro()
                    if vp in self.selected: self.selected.remove(vp)
                    self.selected.extend(parts)
                    self.selection_changed.emit(self.selected)
                    self.document_changed.emit(); self.update(); return

    # ─── グループ ───
    def _group_selection(self):
        if len(self.selected)<2: return
        layer = self.doc.active_layer
        grp = VGroup()
        grp.items = list(self.selected)
        self.undo.push(CmdGroupPaths(layer, list(self.selected), grp))
        self.selected=grp.items[:]; self.selection_changed.emit(self.selected)
        self.document_changed.emit(); self.update()

    def _ungroup_selection(self):
        if not self.selected: return
        vp = self.selected[0]
        layer, grp = self.doc.find_group_of(vp)
        if not grp: return
        self.undo.push(CmdUngroupPaths(layer, grp))
        self.selected=list(grp.items); self.selection_changed.emit(self.selected)
        self.document_changed.emit(); self.update()

    # ─── 整列 ───
    def _bring_to_front(self):
        layer = self.doc.active_layer
        for vp in self.selected:
            if vp in layer.items:
                layer.items.remove(vp); layer.items.append(vp)
        self.update()

    def _send_to_back(self):
        layer = self.doc.active_layer
        for vp in self.selected:
            if vp in layer.items:
                layer.items.remove(vp); layer.items.insert(0, vp)
        self.update()

    def _select_all(self):
        self.selected = list(self.doc.active_layer.paths)
        self.selection_changed.emit(self.selected)
        self.update()

    def _update_hover(self, dp: QPointF):
        prev_hn=self._hover_node; prev_hp=self._hover_path
        self._hover_node=None; self._hover_path=None
        if self.selected and self.tool in (TOOL_RESHAPE,TOOL_ADD_NODE,TOOL_DEL_NODE):
            n=self.selected[0].node_at(dp, 8/self._scale)
            self._hover_node=n
        if not self._hover_node:
            self._hover_path=self._hit_paths(dp)
        if prev_hn!=self._hover_node or prev_hp!=self._hover_path: self.update()

    # ─── ビュー操作 ───
    def fit_canvas(self):
        wr=(self.width()-80)/self.doc.width; hr=(self.height()-80)/self.doc.height
        self._scale=min(wr,hr)
        self._offset=QPointF((self.width()-self.doc.width*self._scale)/2,
                             (self.height()-self.doc.height*self._scale)/2)
        self.update()

    def zoom_to(self, s: float):
        c=QPointF(self.width()/2, self.height()/2)
        self._offset=QPointF(c.x()-self.doc.width/2*s, c.y()-self.doc.height/2*s)
        self._scale=s; self.update()


def _rotate_pt(p: QPointF, center: QPointF, deg: float) -> QPointF:
    r=math.radians(deg)
    dx=p.x()-center.x(); dy=p.y()-center.y()
    return QPointF(center.x()+dx*math.cos(r)-dy*math.sin(r),
                   center.y()+dx*math.sin(r)+dy*math.cos(r))


# ══════════════════════════════════════════════
#  ブラシスタジオダイアログ
# ══════════════════════════════════════════════

class BrushStudioDialog(QDialog):
    brush_selected = Signal(str)

    def __init__(self, parent, current_brush: str):
        super().__init__(parent)
        self.setWindowTitle("ブラシスタジオ")
        self.setMinimumSize(480, 360)
        self.current = current_brush
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16,16,16,16)

        lbl = QLabel("ブラシを選択")
        lbl.setStyleSheet(f"font-size:14px;font-weight:600;color:{C['fg']};")
        lay.addWidget(lbl)

        # プリセットリスト
        self.list = QListWidget()
        for name, b in BRUSHES.items():
            item = QListWidgetItem(f"  {name}")
            item.setData(Qt.UserRole, name)
            self.list.addItem(item)
            if name==self.current:
                self.list.setCurrentItem(item)
        lay.addWidget(self.list)

        # プレビュー
        self.preview = QLabel()
        self.preview.setFixedHeight(80)
        self.preview.setStyleSheet(f"background:{C['canvas_bg']};border:1px solid {C['border']};border-radius:4px;")
        lay.addWidget(self.preview)
        self.list.currentItemChanged.connect(self._on_sel)

        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept); btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._on_sel(self.list.currentItem(), None)

    def _on_sel(self, cur, prev):
        if not cur: return
        self.current=cur.data(Qt.UserRole)
        b = BRUSHES[self.current]
        info = f"筆圧対応: {'あり' if b['pressure_width'] else 'なし'}  |  散布: {b['scatter']:.1f}"
        self.preview.setText(f"  {self.current}  —  {info}")

    def _accept(self):
        self.brush_selected.emit(self.current); self.accept()


# ══════════════════════════════════════════════
#  レイヤーパネル
# ══════════════════════════════════════════════

class LayerPanel(QWidget):
    changed = Signal()

    def __init__(self, doc: Document):
        super().__init__()
        self.doc = doc
        self._build()
        self.refresh()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        bar = QWidget()
        bar.setStyleSheet(f"background:{C['surface']};border-bottom:1px solid {C['border']};")
        bl  = QHBoxLayout(bar); bl.setContentsMargins(6,6,6,6); bl.setSpacing(3)

        for txt, fn, name in [("＋",self._add,""),("－",self._del,"danger"),
                               ("↑",self._up,""),("↓",self._dn,"")]:
            b=QPushButton(txt); b.setFixedSize(26,26)
            if name: b.setObjectName(name)
            b.clicked.connect(fn); bl.addWidget(b)
        bl.addStretch()

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.currentRowChanged.connect(self._row_changed)
        self.list.itemDoubleClicked.connect(self._rename)

        # 不透明度 & ブレンド
        ctrl = QWidget()
        ctrl.setStyleSheet(f"background:{C['surface']};border-top:1px solid {C['border']};padding:4px;")
        cl = QVBoxLayout(ctrl); cl.setContentsMargins(8,6,8,6); cl.setSpacing(4)

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("不透明度"))
        self.sl_op = QSlider(Qt.Horizontal); self.sl_op.setRange(0,100); self.sl_op.setValue(100)
        self.sl_op.valueChanged.connect(self._op_changed)
        self.lbl_op = QLabel("100%"); self.lbl_op.setFixedWidth(36)
        op_row.addWidget(self.sl_op,1); op_row.addWidget(self.lbl_op)
        cl.addLayout(op_row)

        bl2 = QHBoxLayout()
        bl2.addWidget(QLabel("ブレンド"))
        self.combo_blend = QComboBox()
        for m in BLEND_MODES: self.combo_blend.addItem(m)
        self.combo_blend.currentTextChanged.connect(self._blend_changed)
        bl2.addWidget(self.combo_blend,1)
        cl.addLayout(bl2)

        vis_row = QHBoxLayout()
        self.chk_vis  = QCheckBox("表示"); self.chk_vis.setChecked(True)
        self.chk_lock = QCheckBox("ロック")
        self.chk_vis.toggled.connect(self._vis_changed)
        self.chk_lock.toggled.connect(self._lock_changed)
        vis_row.addWidget(self.chk_vis); vis_row.addWidget(self.chk_lock); vis_row.addStretch()
        cl.addLayout(vis_row)

        lay.addWidget(bar); lay.addWidget(self.list,1); lay.addWidget(ctrl)

    def refresh(self):
        self.list.blockSignals(True); self.list.clear()
        for layer in reversed(self.doc.layers):
            vis = "👁" if layer.visible else "🚫"
            lck = "🔒" if layer.locked  else ""
            cnt = len(layer.paths)
            item = QListWidgetItem(f"  {vis}{lck}  {layer.name}  ({cnt})")
            item.setData(Qt.UserRole, layer.id)
            self.list.addItem(item)
        idx = len(self.doc.layers)-1-self.doc.active_layer_idx
        self.list.setCurrentRow(idx)
        self.list.blockSignals(False)
        # 制御更新
        layer = self.doc.active_layer
        self.sl_op.blockSignals(True); self.sl_op.setValue(int(layer.opacity*100)); self.sl_op.blockSignals(False)
        self.lbl_op.setText(f"{int(layer.opacity*100)}%")
        self.combo_blend.blockSignals(True)
        self.combo_blend.setCurrentText(layer.blend)
        self.combo_blend.blockSignals(False)
        self.chk_vis.blockSignals(True);  self.chk_vis.setChecked(layer.visible);  self.chk_vis.blockSignals(False)
        self.chk_lock.blockSignals(True); self.chk_lock.setChecked(layer.locked);  self.chk_lock.blockSignals(False)

    def _row_changed(self, row):
        if row<0: return
        self.doc.active_layer_idx = len(self.doc.layers)-1-row
        self.refresh(); self.changed.emit()

    def _add(self):
        layer=Layer(f"レイヤー {len(self.doc.layers)+1}")
        self.doc.layers.append(layer); self.doc.active_layer_idx=len(self.doc.layers)-1
        self.refresh(); self.changed.emit()

    def _del(self):
        if len(self.doc.layers)<=1: return
        self.doc.layers.pop(self.doc.active_layer_idx)
        self.doc.active_layer_idx=max(0,self.doc.active_layer_idx-1)
        self.refresh(); self.changed.emit()

    def _up(self):
        i=self.doc.active_layer_idx
        if i<len(self.doc.layers)-1:
            self.doc.layers[i],self.doc.layers[i+1]=self.doc.layers[i+1],self.doc.layers[i]
            self.doc.active_layer_idx=i+1; self.refresh(); self.changed.emit()

    def _dn(self):
        i=self.doc.active_layer_idx
        if i>0:
            self.doc.layers[i],self.doc.layers[i-1]=self.doc.layers[i-1],self.doc.layers[i]
            self.doc.active_layer_idx=i-1; self.refresh(); self.changed.emit()

    def _rename(self, item):
        name,ok = QInputDialog.getText(self,"レイヤー名","新しい名前:",text=self.doc.active_layer.name)
        if ok and name: self.doc.active_layer.name=name; self.refresh(); self.changed.emit()

    def _op_changed(self, v):
        self.lbl_op.setText(f"{v}%"); self.doc.active_layer.opacity=v/100
        self.changed.emit()

    def _blend_changed(self, txt):
        self.doc.active_layer.blend=txt; self.changed.emit()

    def _vis_changed(self, v):
        self.doc.active_layer.visible=v; self.changed.emit()

    def _lock_changed(self, v):
        self.doc.active_layer.locked=v; self.changed.emit()


# ══════════════════════════════════════════════
#  プロパティパネル
# ══════════════════════════════════════════════

class PropsPanel(QWidget):
    changed = Signal()

    def __init__(self, canvas: Canvas):
        super().__init__()
        self.canvas = canvas
        self._paths: List[VPath] = []
        self._build()
        self.setEnabled(False)

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(8)
        tabs = QTabWidget(); lay.addWidget(tabs,1)

        # ── ストローク/塗り ──
        tab1 = QWidget(); t1l = QVBoxLayout(tab1); t1l.setSpacing(8)

        sg = QGroupBox("ストローク"); sgl=QVBoxLayout(sg)
        self.btn_stroke = QPushButton()
        self.btn_stroke.setFixedHeight(28); self.btn_stroke.clicked.connect(self._pick_stroke)
        w_row=QHBoxLayout(); w_row.addWidget(QLabel("太さ"))
        self.spin_w = QDoubleSpinBox(); self.spin_w.setRange(0.1,200); self.spin_w.setSingleStep(0.5)
        self.spin_w.valueChanged.connect(self._on_w)
        w_row.addWidget(self.spin_w)
        sgl.addWidget(self.btn_stroke); sgl.addLayout(w_row)

        fg = QGroupBox("塗り"); fgl=QVBoxLayout(fg)
        self.btn_fill = QPushButton("なし")
        self.btn_fill.setFixedHeight(28); self.btn_fill.clicked.connect(self._pick_fill)
        self.btn_no_fill = QPushButton("塗りなし")
        self.btn_no_fill.clicked.connect(self._clear_fill)
        fgl.addWidget(self.btn_fill); fgl.addWidget(self.btn_no_fill)

        og = QGroupBox("不透明度"); ogl=QVBoxLayout(og)
        op_row=QHBoxLayout()
        self.sl_op=QSlider(Qt.Horizontal); self.sl_op.setRange(0,100); self.sl_op.setValue(100)
        self.sl_op.valueChanged.connect(self._on_op)
        self.lbl_op=QLabel("100%"); self.lbl_op.setFixedWidth(36)
        op_row.addWidget(self.sl_op,1); op_row.addWidget(self.lbl_op)
        ogl.addLayout(op_row)

        self.btn_close = QPushButton("パスを閉じる / 開く")
        self.btn_close.clicked.connect(self._toggle_close)

        t1l.addWidget(sg); t1l.addWidget(fg); t1l.addWidget(og)
        t1l.addWidget(self.btn_close); t1l.addStretch()
        tabs.addTab(tab1, "スタイル")

        # ── ノード情報 ──
        tab2 = QWidget(); t2l = QVBoxLayout(tab2); t2l.setSpacing(6)
        self.lbl_info = QLabel("パスを選択してください")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(f"color:{C['fg_dim']};font-size:11px;line-height:1.6;")
        t2l.addWidget(self.lbl_info); t2l.addStretch()
        tabs.addTab(tab2, "情報")

        # ── 変形 ──
        tab3 = QWidget(); t3l = QVBoxLayout(tab3); t3l.setSpacing(8)
        xg = QGroupBox("位置・サイズ"); xgl=QVBoxLayout(xg)
        for lbl in [("X","_tx"),("Y","_ty"),("W","_tw"),("H","_th")]:
            row=QHBoxLayout(); row.addWidget(QLabel(lbl[0]))
            spin=QDoubleSpinBox(); spin.setRange(-99999,99999); spin.setSingleStep(1)
            setattr(self, lbl[1]+"_spin", spin)
            row.addWidget(spin); xgl.addLayout(row)
        btn_apply=QPushButton("変形を適用"); btn_apply.setObjectName("accent")
        btn_apply.clicked.connect(self._apply_transform)
        xgl.addWidget(btn_apply)
        t3l.addWidget(xg); t3l.addStretch()
        tabs.addTab(tab3, "変形")

    def set_paths(self, paths: List[VPath]):
        self._paths=list(paths)
        self.setEnabled(bool(paths))
        if not paths:
            self.lbl_info.setText("パスを選択してください"); return
        vp = paths[0]
        # ストローク
        c=vp.stroke_color
        self.btn_stroke.setStyleSheet(
            f"background:{c.name()};border:1px solid {C['border']};border-radius:4px;")
        self.spin_w.blockSignals(True); self.spin_w.setValue(vp.stroke_width); self.spin_w.blockSignals(False)
        # 塗り
        if vp.fill_color.alpha()>0:
            self.btn_fill.setText("")
            self.btn_fill.setStyleSheet(
                f"background:{vp.fill_color.name()};border:1px solid {C['border']};border-radius:4px;")
        else:
            self.btn_fill.setText("なし"); self.btn_fill.setStyleSheet("")
        # 不透明度
        self.sl_op.blockSignals(True); self.sl_op.setValue(int(vp.opacity*100)); self.sl_op.blockSignals(False)
        self.lbl_op.setText(f"{int(vp.opacity*100)}%")
        # 情報
        br=vp.bounding_rect()
        self.lbl_info.setText(
            f"ノード数: {len(vp.nodes)}\n"
            f"状態: {'閉じたパス' if vp.closed else '開いたパス'}\n"
            f"ブラシ: {vp.brush_name}\n"
            f"X:{br.x():.1f}  Y:{br.y():.1f}\n"
            f"W:{br.width():.1f}  H:{br.height():.1f}"
        )
        # 変形スピン
        for attr,val in [("_tx",br.x()),("_ty",br.y()),("_tw",br.width()),("_th",br.height())]:
            sp=getattr(self,attr+"_spin"); sp.blockSignals(True); sp.setValue(val); sp.blockSignals(False)

    def _pick_stroke(self):
        if not self._paths: return
        c=QColorDialog.getColor(self._paths[0].stroke_color, self,"ストロークカラー")
        if c.isValid():
            for vp in self._paths: vp.stroke_color=QColor(c)
            self.canvas.pen_color=QColor(c); self.set_paths(self._paths)
            self.canvas.update(); self.changed.emit()

    def _pick_fill(self):
        if not self._paths: return
        init=self._paths[0].fill_color if self._paths[0].fill_color.alpha()>0 else QColor(Qt.white)
        c=QColorDialog.getColor(init, self,"塗りカラー", QColorDialog.ShowAlphaChannel)
        if c.isValid():
            for vp in self._paths: vp.fill_color=QColor(c)
            self.canvas.fill_color=QColor(c); self.set_paths(self._paths)
            self.canvas.update(); self.changed.emit()

    def _clear_fill(self):
        for vp in self._paths: vp.fill_color=QColor(Qt.transparent)
        self.set_paths(self._paths); self.canvas.update(); self.changed.emit()

    def _on_w(self, v):
        for vp in self._paths: vp.stroke_width=v
        self.canvas.pen_width=v; self.canvas.update(); self.changed.emit()

    def _on_op(self, v):
        self.lbl_op.setText(f"{v}%")
        for vp in self._paths: vp.opacity=v/100
        self.canvas.update(); self.changed.emit()

    def _toggle_close(self):
        for vp in self._paths: vp.closed=not vp.closed
        self.set_paths(self._paths); self.canvas.update(); self.changed.emit()

    def _apply_transform(self):
        if not self._paths: return
        vp = self._paths[0]
        br = vp.bounding_rect()
        nx=self._tx_spin.value(); ny=self._ty_spin.value()
        nw=self._tw_spin.value(); nh=self._th_spin.value()
        ow=max(br.width(),1); oh=max(br.height(),1)
        sx=nw/ow; sy=nh/oh
        ox,oy=br.left(),br.top()
        before={}; before[vp]=[(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out)) for n in vp.nodes]
        for n in vp.nodes:
            n.pos   =QPointF(nx+(n.pos.x()-ox)*sx,   ny+(n.pos.y()-oy)*sy)
            n.cp_in =QPointF(nx+(n.cp_in.x()-ox)*sx,  ny+(n.cp_in.y()-oy)*sy)
            n.cp_out=QPointF(nx+(n.cp_out.x()-ox)*sx, ny+(n.cp_out.y()-oy)*sy)
        after={}; after[vp]=[(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out)) for n in vp.nodes]
        self.canvas.undo.push(CmdMovePaths(before,after))
        self.set_paths(self._paths); self.canvas.update(); self.changed.emit()


# ══════════════════════════════════════════════
#  シンメトリーパネル
# ══════════════════════════════════════════════

class SymmetryPanel(QGroupBox):
    changed = Signal()

    def __init__(self, doc: Document):
        super().__init__("シンメトリー定規")
        self.doc = doc
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(4)
        self.combo = QComboBox()
        for m in [SYM_NONE, SYM_H, SYM_V, SYM_CROSS]:
            self.combo.addItem(m)
        self.combo.setCurrentText(self.doc.symmetry)
        self.combo.currentTextChanged.connect(self._on_change)
        lay.addWidget(self.combo)
        cx_row=QHBoxLayout(); cx_row.addWidget(QLabel("中心X"))
        self.spin_cx=QDoubleSpinBox(); self.spin_cx.setRange(0,9999); self.spin_cx.setValue(self.doc.sym_cx)
        self.spin_cx.valueChanged.connect(lambda v: setattr(self.doc,'sym_cx',v) or self.changed.emit())
        cx_row.addWidget(self.spin_cx); lay.addLayout(cx_row)
        cy_row=QHBoxLayout(); cy_row.addWidget(QLabel("中心Y"))
        self.spin_cy=QDoubleSpinBox(); self.spin_cy.setRange(0,9999); self.spin_cy.setValue(self.doc.sym_cy)
        self.spin_cy.valueChanged.connect(lambda v: setattr(self.doc,'sym_cy',v) or self.changed.emit())
        cy_row.addWidget(self.spin_cy); lay.addLayout(cy_row)

    def _on_change(self, txt):
        self.doc.symmetry=txt; self.changed.emit()

    def refresh(self, doc: Document):
        self.doc=doc
        self.combo.blockSignals(True); self.combo.setCurrentText(doc.symmetry); self.combo.blockSignals(False)
        self.spin_cx.blockSignals(True); self.spin_cx.setValue(doc.sym_cx); self.spin_cx.blockSignals(False)
        self.spin_cy.blockSignals(True); self.spin_cy.setValue(doc.sym_cy); self.spin_cy.blockSignals(False)


# ══════════════════════════════════════════════
#  メインウィンドウ
# ══════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VektorStudio")
        self.resize(1440, 920)
        self.doc = Document()
        self.undo = QUndoStack(self); self.undo.setUndoLimit(200)
        self._filepath = None; self._modified = False
        self._build_ui(); self._build_menu(); self._build_toolbar(); self._build_status()
        self.canvas.fit_canvas()

    def _build_ui(self):
        self.canvas = Canvas(self.doc, self.undo)
        self.canvas.status_changed.connect(lambda m: self.lbl_status.setText(m))
        self.canvas.selection_changed.connect(self._on_sel)
        self.canvas.document_changed.connect(self._mark_mod)
        self.setCentralWidget(self.canvas)

        # 左ドック: ツールオプション + シンメトリー
        left_w = QWidget()
        left_l = QVBoxLayout(left_w); left_l.setContentsMargins(6,8,6,8); left_l.setSpacing(8)

        # ブラシ選択
        bg = QGroupBox("ブラシ")
        bgl = QVBoxLayout(bg)
        self._combo_brush = QComboBox()
        for name in BRUSHES: self._combo_brush.addItem(name)
        self._combo_brush.currentTextChanged.connect(self._on_brush)
        btn_studio = QPushButton("ブラシスタジオ…")
        btn_studio.clicked.connect(self._open_brush_studio)
        bgl.addWidget(self._combo_brush); bgl.addWidget(btn_studio)

        # シンメトリー
        self.sym_panel = SymmetryPanel(self.doc)
        self.sym_panel.changed.connect(self.canvas.update)

        left_l.addWidget(bg); left_l.addWidget(self.sym_panel); left_l.addStretch()

        left_dock = QDockWidget("ツールオプション", self)
        left_dock.setWidget(left_w)
        left_dock.setFeatures(QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, left_dock)

        # 右ドック: レイヤー
        self.layer_panel = LayerPanel(self.doc)
        self.layer_panel.changed.connect(self.canvas.update)
        self.layer_panel.changed.connect(lambda: self.layer_panel.refresh())

        layer_dock = QDockWidget("レイヤー", self)
        layer_dock.setWidget(self.layer_panel)
        layer_dock.setFeatures(QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, layer_dock)

        # 右ドック: プロパティ
        self.props_panel = PropsPanel(self.canvas)
        self.props_panel.changed.connect(self.canvas.update)
        self.props_panel.changed.connect(self._mark_mod)

        props_dock = QDockWidget("プロパティ", self)
        props_dock.setWidget(self.props_panel)
        props_dock.setFeatures(QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, props_dock)

        self.resizeDocks([layer_dock, props_dock], [260,260], Qt.Horizontal)
        self.resizeDocks([left_dock], [200], Qt.Horizontal)

    def _build_menu(self):
        mb = self.menuBar()
        # ファイル
        fm=mb.addMenu("ファイル")
        def fa(lbl,sc,fn): a=fm.addAction(lbl); a.setShortcut(sc); a.triggered.connect(fn); return a
        fa("新規作成","Ctrl+N",self._new_doc)
        fa("開く…","Ctrl+O",self._open_svg)
        fm.addSeparator()
        fa("保存","Ctrl+S",self._save)
        fa("別名保存…","Ctrl+Shift+S",self._save_as)
        fm.addSeparator()
        fa("SVGとして書き出し…","Ctrl+E",self._export_svg)
        fm.addSeparator()
        fa("終了","Ctrl+Q",self.close)

        # 編集
        em=mb.addMenu("編集")
        u=self.undo.createUndoAction(self,"元に戻す"); u.setShortcut("Ctrl+Z"); em.addAction(u)
        r=self.undo.createRedoAction(self,"やり直し"); r.setShortcut("Ctrl+Y"); em.addAction(r)
        em.addSeparator()
        def ea(lbl,sc,fn): a=em.addAction(lbl); a.setShortcut(sc); a.triggered.connect(fn)
        ea("すべて選択","Ctrl+A",self.canvas._select_all)
        ea("グループ化","Ctrl+G",self.canvas._group_selection)
        ea("グループ解除","Ctrl+Shift+G",self.canvas._ungroup_selection)
        em.addSeparator()
        ea("最前面へ","Ctrl+]",self.canvas._bring_to_front)
        ea("最背面へ","Ctrl+[",self.canvas._send_to_back)

        # 表示
        vm=mb.addMenu("表示")
        def va(lbl,sc,fn): a=vm.addAction(lbl); a.setShortcut(sc); a.triggered.connect(fn)
        va("フィット","Ctrl+0",self.canvas.fit_canvas)
        va("100%","Ctrl+1",lambda:self.canvas.zoom_to(1.0))
        va("200%","Ctrl+2",lambda:self.canvas.zoom_to(2.0))
        va("50%","Ctrl+5",lambda:self.canvas.zoom_to(0.5))

    def _build_toolbar(self):
        tb = self.addToolBar("ツール"); tb.setMovable(False)
        self._tool_acts = {}
        tools = [
            ("✏","P",TOOL_PEN,"ペン"),
            ("↗","A",TOOL_RESHAPE,"Reshape"),
            ("⬚","V",TOOL_SELECT,"選択"),
            ("✋","H",TOOL_HAND,"手のひら"),
            ("⌫","E",TOOL_ERASER,"消しゴム"),
            ("+","Shift+A",TOOL_ADD_NODE,"アンカー追加"),
            ("−","Shift+D",TOOL_DEL_NODE,"アンカー削除"),
            ("↔","W",TOOL_WIDTH,"線幅編集"),
            ("🪣","B",TOOL_BUCKET,"バケツ塗り"),
            ("✂","C",TOOL_SCISSORS,"交差点切断"),
        ]
        for lbl,key,tool,tip in tools:
            act=QAction(lbl,self); act.setShortcut(key)
            act.setToolTip(f"{tip} [{key}]"); act.setCheckable(True)
            act.triggered.connect(lambda c,t=tool: self._set_tool(t))
            self._tool_acts[tool]=act; tb.addAction(act)

        tb.addSeparator()
        # ペンカラー
        self.lbl_pc=QLabel(); self.lbl_pc.setFixedSize(22,22)
        self.lbl_pc.setStyleSheet(f"background:{C['stroke_def']};border:2px solid {C['border']};border-radius:4px;")
        self.lbl_pc.setCursor(Qt.PointingHandCursor)
        self.lbl_pc.mousePressEvent=lambda e:self._pick_pen_color()
        tb.addWidget(QLabel(" ")); tb.addWidget(self.lbl_pc); tb.addWidget(QLabel(" 線 "))

        # 塗りカラー
        self.lbl_fc=QLabel(); self.lbl_fc.setFixedSize(22,22)
        self.lbl_fc.setStyleSheet(f"background:transparent;border:2px solid {C['border']};border-radius:4px;")
        self.lbl_fc.setCursor(Qt.PointingHandCursor)
        self.lbl_fc.mousePressEvent=lambda e:self._pick_fill_color()
        tb.addWidget(self.lbl_fc); tb.addWidget(QLabel(" 塗 "))

        tb.addSeparator()
        self.spin_w=QDoubleSpinBox(); self.spin_w.setRange(0.1,200); self.spin_w.setValue(2.0)
        self.spin_w.setSingleStep(0.5); self.spin_w.setSuffix("px"); self.spin_w.setFixedWidth(76)
        self.spin_w.valueChanged.connect(lambda v: setattr(self.canvas,'pen_width',v))
        tb.addWidget(self.spin_w)
        tb.addSeparator()

        u=self.undo.createUndoAction(self,"↩"); u.setShortcut("Ctrl+Z"); tb.addAction(u)
        r=self.undo.createRedoAction(self,"↪"); r.setShortcut("Ctrl+Y"); tb.addAction(r)

        self._set_tool(TOOL_PEN)

    def _build_status(self):
        self.status_bar=QStatusBar(); self.setStatusBar(self.status_bar)
        self.lbl_status=QLabel("  VektorStudio — Phase 1-4 Full  |  P:ペン  A:Reshape  V:選択  B:バケツ  C:切断")
        self.status_bar.addWidget(self.lbl_status)
        self.lbl_tool=QLabel()
        self.lbl_tool.setStyleSheet(f"color:{C['accent']};padding-right:12px;")
        self.status_bar.addPermanentWidget(self.lbl_tool)

    def _set_tool(self, t: str):
        for k,a in self._tool_acts.items(): a.setChecked(k==t)
        self.canvas.set_tool(t)
        names={
            TOOL_PEN:"ペン (P)", TOOL_RESHAPE:"Reshape (A)",
            TOOL_SELECT:"選択 (V)", TOOL_HAND:"手のひら (H)",
            TOOL_ERASER:"消しゴム (E)", TOOL_ADD_NODE:"アンカー追加 (+)",
            TOOL_DEL_NODE:"アンカー削除 (−)", TOOL_WIDTH:"線幅編集 (W)",
            TOOL_BUCKET:"バケツ (B)", TOOL_SCISSORS:"切断 (C)",
        }
        self.lbl_tool.setText(names.get(t,t))

    def _pick_pen_color(self):
        c=QColorDialog.getColor(self.canvas.pen_color,self,"ペンカラー")
        if c.isValid():
            self.canvas.pen_color=c
            self.lbl_pc.setStyleSheet(f"background:{c.name()};border:2px solid {C['border']};border-radius:4px;")

    def _pick_fill_color(self):
        c=QColorDialog.getColor(self.canvas.fill_color,self,"塗りカラー",QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self.canvas.fill_color=c
            self.lbl_fc.setStyleSheet(f"background:{c.name()};border:2px solid {C['border']};border-radius:4px;")

    def _on_brush(self, name: str):
        self.canvas.brush_name=name

    def _open_brush_studio(self):
        dlg=BrushStudioDialog(self, self.canvas.brush_name)
        dlg.brush_selected.connect(lambda n: (setattr(self.canvas,'brush_name',n),
                                              self._combo_brush.setCurrentText(n)))
        dlg.exec()

    def _on_sel(self, paths: List[VPath]):
        self.props_panel.set_paths(paths)

    def _mark_mod(self):
        self._modified=True
        f=self._filepath.split("/")[-1] if self._filepath else "無題"
        self.setWindowTitle(f"VektorStudio* — {f}")

    def _new_doc(self):
        if self._modified:
            r=QMessageBox.question(self,"新規","変更を保存しますか？",
                                   QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
            if r==QMessageBox.Save: self._save()
            elif r==QMessageBox.Cancel: return
        self.doc=Document()
        self.canvas.doc=self.doc; self.canvas.selected=[]; self.undo.clear()
        self.layer_panel.doc=self.doc; self.layer_panel.refresh()
        self.sym_panel.refresh(self.doc)
        self._filepath=None; self._modified=False
        self.canvas.fit_canvas(); self.setWindowTitle("VektorStudio — 無題")

    def _open_svg(self):
        path,_=QFileDialog.getOpenFileName(self,"SVGを開く","","SVG Files (*.svg);;All (*)")
        if not path: return
        try:
            doc=svg_to_document(open(path,'r',encoding='utf-8').read())
            self.doc=doc; self.canvas.doc=doc; self.canvas.selected=[]; self.undo.clear()
            self.layer_panel.doc=doc; self.layer_panel.refresh()
            self.sym_panel.refresh(doc)
            self._filepath=path; self._modified=False
            self.canvas.fit_canvas()
            self.setWindowTitle(f"VektorStudio — {path.split('/')[-1]}")
        except Exception as e:
            QMessageBox.critical(self,"エラー",f"読み込み失敗:\n{e}")

    def _save(self):
        if self._filepath: self._write(self._filepath)
        else: self._save_as()

    def _save_as(self):
        path,_=QFileDialog.getSaveFileName(self,"保存","untitled.svg","SVG Files (*.svg)")
        if path: self._write(path); self._filepath=path

    def _export_svg(self):
        path,_=QFileDialog.getSaveFileName(self,"SVG書き出し","export.svg","SVG Files (*.svg)")
        if path: self._write(path)

    def _write(self, path: str):
        try:
            open(path,'w',encoding='utf-8').write(document_to_svg(self.doc))
            self._modified=False
            self.setWindowTitle(f"VektorStudio — {path.split('/')[-1]}")
            self.status_bar.showMessage(f"保存: {path}",3000)
        except Exception as e:
            QMessageBox.critical(self,"エラー",f"保存失敗:\n{e}")


# ══════════════════════════════════════════════
#  エントリポイント
# ══════════════════════════════════════════════

def main():
    app=QApplication(sys.argv)
    app.setApplicationName("VektorStudio")
    app.setOrganizationName("VOSE")
    app.setStyleSheet(SS)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    win=MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
