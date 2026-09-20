"""
VektorStudio MVP — ベクターエディター
Phase 1: ペン描画 + Reshape + レイヤー + SVG入出力
"""

import sys
import math
import uuid
from copy import deepcopy
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QStatusBar, QFileDialog, QMessageBox, QLabel,
    QSplitter, QScrollArea, QFrame, QListWidget, QListWidgetItem,
    QPushButton, QSlider, QColorDialog, QDockWidget, QSizePolicy,
    QAbstractItemView, QSpinBox, QDoubleSpinBox, QGroupBox,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor, QKeySequence,
    QAction, QIcon, QPixmap, QCursor, QUndoStack, QUndoCommand,
    QFont, QFontDatabase, QTransform, QPainterPathStroker,
    QLinearGradient, QRadialGradient,
)
from PySide6.QtCore import (
    Qt, QPointF, QRectF, QSizeF, QTimer, Signal, QObject,
    QLineF, QSize, QByteArray,
)
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtSvgWidgets import QSvgWidget
import lxml.etree as ET

# ─────────────────────────────────────────────
#  カラーパレット (VO-SE系ダークUI)
# ─────────────────────────────────────────────
C = {
    "bg":         "#0E0F11",
    "surface":    "#16181C",
    "panel":      "#1C1F24",
    "border":     "#2A2D35",
    "accent":     "#5B8CFF",
    "accent2":    "#A78BFA",
    "fg":         "#E8EAF0",
    "fg_dim":     "#6B7280",
    "node_fill":  "#5B8CFF",
    "node_sel":   "#A78BFA",
    "node_border":"#FFFFFF",
    "stroke_def": "#E8EAF0",
    "canvas_bg":  "#1A1D22",
    "canvas_grid":"#23262E",
    "danger":     "#FF5B6B",
    "success":    "#4ADE80",
}

STYLESHEET = f"""
QMainWindow, QWidget {{
    background: {C['bg']};
    color: {C['fg']};
    font-family: 'Inter', 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
    font-size: 12px;
}}
QToolBar {{
    background: {C['surface']};
    border-bottom: 1px solid {C['border']};
    spacing: 4px;
    padding: 4px 8px;
}}
QToolBar QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 8px;
    color: {C['fg']};
    font-size: 13px;
    min-width: 32px;
}}
QToolBar QToolButton:hover {{
    background: {C['panel']};
    border-color: {C['border']};
}}
QToolBar QToolButton:checked {{
    background: {C['accent']};
    color: white;
    border-color: {C['accent']};
}}
QDockWidget {{
    background: {C['panel']};
    color: {C['fg']};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background: {C['surface']};
    padding: 6px 10px;
    border-bottom: 1px solid {C['border']};
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
    color: {C['fg_dim']};
}}
QListWidget {{
    background: {C['panel']};
    border: none;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {C['border']};
    border-radius: 4px;
    margin: 1px 4px;
}}
QListWidget::item:selected {{
    background: {C['accent']};
    color: white;
}}
QListWidget::item:hover:!selected {{
    background: {C['surface']};
}}
QPushButton {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 6px 14px;
    color: {C['fg']};
}}
QPushButton:hover {{
    background: {C['panel']};
    border-color: {C['accent']};
}}
QPushButton:pressed {{
    background: {C['accent']};
    color: white;
}}
QPushButton#accent {{
    background: {C['accent']};
    border-color: {C['accent']};
    color: white;
    font-weight: 600;
}}
QPushButton#accent:hover {{
    background: #4A7AEE;
}}
QPushButton#danger {{
    background: transparent;
    border-color: {C['danger']};
    color: {C['danger']};
}}
QPushButton#danger:hover {{
    background: {C['danger']};
    color: white;
}}
QSlider::groove:horizontal {{
    background: {C['border']};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C['accent']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {C['accent']};
    border-radius: 2px;
}}
QStatusBar {{
    background: {C['surface']};
    border-top: 1px solid {C['border']};
    color: {C['fg_dim']};
    font-size: 11px;
}}
QGroupBox {{
    border: 1px solid {C['border']};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    font-size: 11px;
    color: {C['fg_dim']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
QSpinBox, QDoubleSpinBox {{
    background: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 3px 6px;
    color: {C['fg']};
}}
QScrollBar:vertical {{
    background: {C['surface']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

# ─────────────────────────────────────────────
#  データモデル
# ─────────────────────────────────────────────

class VNode:
    """ベジェ曲線のアンカーノード"""
    def __init__(self, pos: QPointF, cp_in: QPointF = None, cp_out: QPointF = None):
        self.id = str(uuid.uuid4())[:8]
        self.pos = QPointF(pos)
        self.cp_in  = QPointF(cp_in)  if cp_in  else QPointF(pos)
        self.cp_out = QPointF(cp_out) if cp_out else QPointF(pos)
        self.smooth = True  # スムーズノード

    def set_pos(self, p: QPointF):
        dx = p.x() - self.pos.x()
        dy = p.y() - self.pos.y()
        self.pos = QPointF(p)
        self.cp_in  = QPointF(self.cp_in.x()  + dx, self.cp_in.y()  + dy)
        self.cp_out = QPointF(self.cp_out.x() + dx, self.cp_out.y() + dy)


class VPath:
    """ベクターパス (複数ノードからなる曲線)"""
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.nodes: list[VNode] = []
        self.closed = False
        self.stroke_color = QColor(C["stroke_def"])
        self.stroke_width = 2.0
        self.fill_color = QColor(Qt.transparent)
        self.fill_rule = Qt.WindingFill
        self.opacity = 1.0
        self.visible = True

    def to_qpainter_path(self) -> QPainterPath:
        path = QPainterPath()
        if not self.nodes:
            return path
        n0 = self.nodes[0]
        path.moveTo(n0.pos)
        for i in range(1, len(self.nodes)):
            prev = self.nodes[i - 1]
            curr = self.nodes[i]
            path.cubicTo(prev.cp_out, curr.cp_in, curr.pos)
        if self.closed and len(self.nodes) >= 2:
            last = self.nodes[-1]
            first = self.nodes[0]
            path.cubicTo(last.cp_out, first.cp_in, first.pos)
            path.closeSubpath()
        return path

    def hit_test(self, pt: QPointF, radius: float = 8.0) -> bool:
        """ストロークまたは塗りへのヒット判定"""
        qpath = self.to_qpainter_path()
        # ストローク判定
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.stroke_width, radius * 2))
        stroked = stroker.createStroke(qpath)
        if stroked.contains(pt):
            return True
        # 塗り判定
        if self.fill_color.alpha() > 0:
            return qpath.contains(pt)
        return False

    def node_at(self, pt: QPointF, radius: float = 8.0) -> Optional['VNode']:
        for n in self.nodes:
            if QLineF(n.pos, pt).length() < radius:
                return n
        return None

    def cp_at(self, pt: QPointF, radius: float = 7.0):
        """コントロールポイントヒット → (node, 'in'|'out') or None"""
        for n in self.nodes:
            if QLineF(n.cp_in, pt).length() < radius and n.cp_in != n.pos:
                return (n, 'in')
            if QLineF(n.cp_out, pt).length() < radius and n.cp_out != n.pos:
                return (n, 'out')
        return None

    def bounding_rect(self) -> QRectF:
        return self.to_qpainter_path().boundingRect()


class Layer:
    def __init__(self, name: str = "レイヤー"):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.paths: list[VPath] = []
        self.visible = True
        self.locked = False
        self.opacity = 1.0


class Document:
    def __init__(self, w=1200, h=800):
        self.width = w
        self.height = h
        self.layers: list[Layer] = [Layer("レイヤー 1")]
        self.active_layer_idx = 0

    @property
    def active_layer(self) -> Layer:
        return self.layers[self.active_layer_idx]

    def all_paths(self):
        for layer in self.layers:
            for p in layer.paths:
                yield (layer, p)

    def find_path(self, path_id: str):
        for layer, p in self.all_paths():
            if p.id == path_id:
                return (layer, p)
        return (None, None)


# ─────────────────────────────────────────────
#  Undo コマンド
# ─────────────────────────────────────────────

class AddPathCommand(QUndoCommand):
    def __init__(self, doc: Document, layer: Layer, path: VPath):
        super().__init__("パスを追加")
        self.doc = doc
        self.layer = layer
        self.path = path

    def redo(self):
        self.layer.paths.append(self.path)

    def undo(self):
        if self.path in self.layer.paths:
            self.layer.paths.remove(self.path)


class MoveNodeCommand(QUndoCommand):
    def __init__(self, node: VNode, old_pos: QPointF, new_pos: QPointF,
                 old_cpi: QPointF, old_cpo: QPointF, new_cpi: QPointF, new_cpo: QPointF):
        super().__init__("ノードを移動")
        self.node = node
        self.old_pos, self.new_pos = old_pos, new_pos
        self.old_cpi, self.old_cpo = old_cpi, old_cpo
        self.new_cpi, self.new_cpo = new_cpi, new_cpo

    def redo(self):
        self.node.pos    = QPointF(self.new_pos)
        self.node.cp_in  = QPointF(self.new_cpi)
        self.node.cp_out = QPointF(self.new_cpo)

    def undo(self):
        self.node.pos    = QPointF(self.old_pos)
        self.node.cp_in  = QPointF(self.old_cpi)
        self.node.cp_out = QPointF(self.old_cpo)


class DeletePathCommand(QUndoCommand):
    def __init__(self, layer: Layer, path: VPath):
        super().__init__("パスを削除")
        self.layer = layer
        self.path = path

    def redo(self):
        if self.path in self.layer.paths:
            self.layer.paths.remove(self.path)

    def undo(self):
        self.layer.paths.append(self.path)


# ─────────────────────────────────────────────
#  SVG 入出力
# ─────────────────────────────────────────────

def path_to_svg_d(vpath: VPath) -> str:
    """VPath → SVG dアトリビュート文字列"""
    nodes = vpath.nodes
    if not nodes:
        return ""
    parts = [f"M {nodes[0].pos.x():.2f},{nodes[0].pos.y():.2f}"]
    for i in range(1, len(nodes)):
        prev = nodes[i - 1]
        curr = nodes[i]
        parts.append(
            f"C {prev.cp_out.x():.2f},{prev.cp_out.y():.2f} "
            f"{curr.cp_in.x():.2f},{curr.cp_in.y():.2f} "
            f"{curr.pos.x():.2f},{curr.pos.y():.2f}"
        )
    if vpath.closed and len(nodes) >= 2:
        last = nodes[-1]
        first = nodes[0]
        parts.append(
            f"C {last.cp_out.x():.2f},{last.cp_out.y():.2f} "
            f"{first.cp_in.x():.2f},{first.cp_in.y():.2f} "
            f"{first.pos.x():.2f},{first.pos.y():.2f} Z"
        )
    return " ".join(parts)


def color_to_svg(c: QColor) -> str:
    if c.alpha() == 0:
        return "none"
    return c.name()


def document_to_svg(doc: Document) -> str:
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(doc.width),
        "height": str(doc.height),
        "viewBox": f"0 0 {doc.width} {doc.height}",
        "data-vektorstudio": "1",
    })
    for layer in doc.layers:
        if not layer.paths:
            continue
        g = ET.SubElement(root, "g", {
            "id": f"layer-{layer.id}",
            "data-name": layer.name,
            "opacity": str(layer.opacity),
        })
        if not layer.visible:
            g.set("display", "none")
        for vp in layer.paths:
            d = path_to_svg_d(vp)
            if not d:
                continue
            ET.SubElement(g, "path", {
                "id": f"path-{vp.id}",
                "d": d,
                "stroke": color_to_svg(vp.stroke_color),
                "stroke-width": str(vp.stroke_width),
                "fill": color_to_svg(vp.fill_color),
                "opacity": str(vp.opacity),
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            })
    return ET.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode()


def svg_d_to_vpath(d: str, attrs: dict) -> Optional[VPath]:
    """SVGのdアトリビュートをVPathに変換（基本的なM/C/Z対応）"""
    import re
    vp = VPath()
    tokens = re.findall(r'[MCZmcz]|[-+]?\d*\.?\d+', d)
    i = 0
    last_pos = QPointF(0, 0)
    nodes = []

    def read_float():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        cmd = tokens[i]; i += 1
        if cmd in ('M', 'm'):
            x, y = read_float(), read_float()
            if cmd == 'm':
                x += last_pos.x(); y += last_pos.y()
            n = VNode(QPointF(x, y))
            nodes.append(n)
            last_pos = QPointF(x, y)
        elif cmd in ('C', 'c'):
            while i < len(tokens) and tokens[i] not in list('MCZmcz'):
                cp1x, cp1y = read_float(), read_float()
                cp2x, cp2y = read_float(), read_float()
                ex, ey     = read_float(), read_float()
                if cmd == 'c':
                    cp1x += last_pos.x(); cp1y += last_pos.y()
                    cp2x += last_pos.x(); cp2y += last_pos.y()
                    ex   += last_pos.x(); ey   += last_pos.y()
                if nodes:
                    nodes[-1].cp_out = QPointF(cp1x, cp1y)
                n = VNode(QPointF(ex, ey), QPointF(cp2x, cp2y))
                nodes.append(n)
                last_pos = QPointF(ex, ey)
        elif cmd in ('Z', 'z'):
            vp.closed = True

    if not nodes:
        return None
    vp.nodes = nodes
    stroke = attrs.get("stroke", C["stroke_def"])
    if stroke != "none":
        vp.stroke_color = QColor(stroke)
    else:
        vp.stroke_color = QColor(Qt.transparent)
    try:
        vp.stroke_width = float(attrs.get("stroke-width", "2"))
    except ValueError:
        vp.stroke_width = 2.0
    fill = attrs.get("fill", "none")
    if fill != "none":
        vp.fill_color = QColor(fill)
    try:
        vp.opacity = float(attrs.get("opacity", "1"))
    except ValueError:
        vp.opacity = 1.0
    return vp


def svg_to_document(svg_text: str) -> Document:
    root = ET.fromstring(svg_text.encode())
    ns = {"svg": "http://www.w3.org/2000/svg"}
    w = int(root.get("width", 1200))
    h = int(root.get("height", 800))
    doc = Document(w, h)
    doc.layers = []
    for g in root.findall(".//svg:g", ns) + root.findall(".//g"):
        name = g.get("data-name", g.get("id", "レイヤー"))
        layer = Layer(name)
        for path_el in list(g):
            tag = path_el.tag.split("}")[-1]
            if tag == "path":
                d = path_el.get("d", "")
                vp = svg_d_to_vpath(d, dict(path_el.attrib))
                if vp:
                    layer.paths.append(vp)
        doc.layers.append(layer)
    # 最低1レイヤー
    if not doc.layers:
        doc.layers = [Layer("レイヤー 1")]
    doc.active_layer_idx = 0
    return doc


# ─────────────────────────────────────────────
#  ツール定数
# ─────────────────────────────────────────────
TOOL_PEN    = "pen"
TOOL_RESHAPE= "reshape"
TOOL_SELECT = "select"
TOOL_HAND   = "hand"
TOOL_ERASER = "eraser"


# ─────────────────────────────────────────────
#  キャンバスウィジェット
# ─────────────────────────────────────────────

class Canvas(QWidget):
    status_changed = Signal(str)
    selection_changed = Signal(object)  # VPath or None
    document_changed = Signal()

    def __init__(self, doc: Document, undo_stack: QUndoStack):
        super().__init__()
        self.doc = doc
        self.undo_stack = undo_stack
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # ビュー変換
        self._scale = 1.0
        self._offset = QPointF(0, 0)
        self._pan_start = None
        self._pan_offset = None

        # ツール状態
        self.current_tool = TOOL_PEN
        self._pen_path: Optional[VPath] = None
        self._pen_drawing = False
        self._last_pen_pos: Optional[QPointF] = None

        # 選択・Reshape
        self.selected_path: Optional[VPath] = None
        self.selected_node: Optional[VNode] = None
        self.selected_cp: Optional[tuple] = None  # (node, 'in'/'out')
        self._drag_start: Optional[QPointF] = None
        self._node_snap_before = None  # (pos, cp_in, cp_out)
        self._path_drag_start_positions = {}

        # ホバー
        self._hover_node: Optional[VNode] = None
        self._hover_path: Optional[VPath] = None

        # ペン設定
        self.pen_color = QColor(C["stroke_def"])
        self.pen_width = 2.0

        # カーソル
        self._cursors = {
            TOOL_PEN:     Qt.CrossCursor,
            TOOL_RESHAPE: Qt.ArrowCursor,
            TOOL_SELECT:  Qt.ArrowCursor,
            TOOL_HAND:    Qt.OpenHandCursor,
            TOOL_ERASER:  Qt.CrossCursor,
        }

        self.setMinimumSize(600, 400)
        self._center_canvas()

    def _center_canvas(self):
        # キャンバスを中央に配置
        self._offset = QPointF(40, 40)

    # ── 座標変換 ──

    def to_doc(self, screen_pt: QPointF) -> QPointF:
        return QPointF(
            (screen_pt.x() - self._offset.x()) / self._scale,
            (screen_pt.y() - self._offset.y()) / self._scale,
        )

    def to_screen(self, doc_pt: QPointF) -> QPointF:
        return QPointF(
            doc_pt.x() * self._scale + self._offset.x(),
            doc_pt.y() * self._scale + self._offset.y(),
        )

    def set_tool(self, tool: str):
        self.current_tool = tool
        self.setCursor(self._cursors.get(tool, Qt.ArrowCursor))
        if tool != TOOL_RESHAPE and tool != TOOL_SELECT:
            self.selected_path = None
            self.selected_node = None
            self.selection_changed.emit(None)
        self.update()

    def set_pen_color(self, c: QColor):
        self.pen_color = c

    def set_pen_width(self, w: float):
        self.pen_width = w

    # ── ペイント ──

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景
        painter.fillRect(self.rect(), QColor(C["bg"]))

        # グリッド
        self._draw_grid(painter)

        # キャンバス背景
        painter.save()
        painter.translate(self._offset)
        painter.scale(self._scale, self._scale)
        canvas_rect = QRectF(0, 0, self.doc.width, self.doc.height)
        # キャンバス影
        shadow_rect = canvas_rect.adjusted(4, 4, 4, 4)
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 80))
        painter.fillRect(canvas_rect, QColor(C["canvas_bg"]))

        # パスを描画
        for layer in self.doc.layers:
            if not layer.visible:
                continue
            painter.setOpacity(layer.opacity)
            for vpath in layer.paths:
                self._draw_path(painter, vpath)
            painter.setOpacity(1.0)

        # 描画中のペンパス
        if self._pen_path and self._pen_drawing:
            self._draw_path(painter, self._pen_path, is_preview=True)

        painter.restore()

        # Reshape オーバーレイ（スクリーン座標）
        if self.current_tool in (TOOL_RESHAPE, TOOL_SELECT) and self.selected_path:
            self._draw_reshape_overlay(painter)

        # 選択パスのバウンディングボックス (Selectツール)
        if self.current_tool == TOOL_SELECT and self.selected_path:
            self._draw_selection_box(painter)

    def _draw_grid(self, painter: QPainter):
        step = 40 * self._scale
        if step < 10:
            return
        painter.setPen(QPen(QColor(C["canvas_grid"]), 0.5))
        w, h = self.width(), self.height()
        ox = self._offset.x() % step
        oy = self._offset.y() % step
        x = ox
        while x < w:
            painter.drawLine(QPointF(x, 0), QPointF(x, h))
            x += step
        y = oy
        while y < h:
            painter.drawLine(QPointF(0, y), QPointF(w, y))
            y += step

    def _draw_path(self, painter: QPainter, vpath: VPath, is_preview=False):
        if not vpath.visible:
            return
        qpath = vpath.to_qpainter_path()
        painter.setOpacity(vpath.opacity)

        # 塗り
        if vpath.fill_color.alpha() > 0:
            painter.fillPath(qpath, QBrush(vpath.fill_color))

        # ストローク
        pen = QPen(vpath.stroke_color, vpath.stroke_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        if is_preview:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawPath(qpath)

        # 選択ハイライト
        if vpath is self.selected_path and not is_preview:
            hi_pen = QPen(QColor(C["accent"]), max(vpath.stroke_width + 2, 3))
            hi_pen.setCapStyle(Qt.RoundCap)
            hi_pen.setJoinStyle(Qt.RoundJoin)
            hi_pen_outer = QPen(QColor(C["accent"] + "40"), max(vpath.stroke_width + 8, 10))
            painter.setPen(hi_pen_outer)
            painter.drawPath(qpath)
            painter.setPen(hi_pen)
            painter.drawPath(qpath)

        painter.setOpacity(1.0)

    def _draw_reshape_overlay(self, painter: QPainter):
        vpath = self.selected_path
        if not vpath:
            return

        painter.save()
        painter.translate(self._offset)
        painter.scale(self._scale, self._scale)

        node_r = 5.0 / self._scale
        cp_r   = 4.0 / self._scale

        for i, node in enumerate(vpath.nodes):
            is_sel = (node is self.selected_node)

            # コントロールポイントの線とハンドル
            if is_sel or self.current_tool == TOOL_RESHAPE:
                # in handle
                if node.cp_in != node.pos:
                    pen_cp = QPen(QColor(C["fg_dim"]), 1.0 / self._scale)
                    pen_cp.setStyle(Qt.DotLine)
                    painter.setPen(pen_cp)
                    painter.drawLine(node.pos, node.cp_in)
                    cp_rect = QRectF(
                        node.cp_in.x() - cp_r, node.cp_in.y() - cp_r,
                        cp_r * 2, cp_r * 2
                    )
                    painter.setBrush(QBrush(QColor(C["accent2"])))
                    painter.setPen(QPen(QColor("white"), 0.8 / self._scale))
                    painter.drawEllipse(cp_rect)

                # out handle
                if node.cp_out != node.pos:
                    pen_cp = QPen(QColor(C["fg_dim"]), 1.0 / self._scale)
                    pen_cp.setStyle(Qt.DotLine)
                    painter.setPen(pen_cp)
                    painter.drawLine(node.pos, node.cp_out)
                    cp_rect = QRectF(
                        node.cp_out.x() - cp_r, node.cp_out.y() - cp_r,
                        cp_r * 2, cp_r * 2
                    )
                    painter.setBrush(QBrush(QColor(C["accent2"])))
                    painter.setPen(QPen(QColor("white"), 0.8 / self._scale))
                    painter.drawEllipse(cp_rect)

            # アンカーノード
            nr = node_r * (1.3 if is_sel else 1.0)
            node_rect = QRectF(node.pos.x() - nr, node.pos.y() - nr, nr*2, nr*2)
            if is_sel:
                painter.setBrush(QBrush(QColor(C["node_sel"])))
                painter.setPen(QPen(QColor("white"), 1.5 / self._scale))
            elif node is self._hover_node:
                painter.setBrush(QBrush(QColor(C["accent"])))
                painter.setPen(QPen(QColor("white"), 1.0 / self._scale))
            else:
                painter.setBrush(QBrush(QColor(C["node_fill"])))
                painter.setPen(QPen(QColor("white"), 1.0 / self._scale))
            painter.drawRect(node_rect)  # 四角ノード（Illustrator風）

        painter.restore()

    def _draw_selection_box(self, painter: QPainter):
        if not self.selected_path:
            return
        br = self.selected_path.bounding_rect()
        # スクリーン座標に変換
        tl = self.to_screen(br.topLeft())
        br2 = self.to_screen(br.bottomRight())
        rect = QRectF(tl, br2)
        pen = QPen(QColor(C["accent"]), 1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect.adjusted(-4, -4, 4, 4))

    # ── マウスイベント ──

    def mousePressEvent(self, event):
        pos = event.position()
        doc_pos = self.to_doc(pos)

        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier
        ):
            self._pan_start  = pos
            self._pan_offset = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)
            return

        if event.button() == Qt.LeftButton:
            if self.current_tool == TOOL_PEN:
                self._pen_press(doc_pos, event.modifiers())
            elif self.current_tool == TOOL_RESHAPE:
                self._reshape_press(doc_pos)
            elif self.current_tool == TOOL_SELECT:
                self._select_press(doc_pos)
            elif self.current_tool == TOOL_ERASER:
                self._eraser_press(doc_pos)

    def mouseMoveEvent(self, event):
        pos = event.position()
        doc_pos = self.to_doc(pos)

        # パン
        if self._pan_start is not None:
            delta = pos - self._pan_start
            self._offset = self._pan_offset + delta
            self.update()
            return

        if event.buttons() & Qt.LeftButton:
            if self.current_tool == TOOL_PEN:
                self._pen_drag(doc_pos, event.modifiers())
            elif self.current_tool == TOOL_RESHAPE:
                self._reshape_drag(doc_pos)
            elif self.current_tool == TOOL_SELECT:
                self._select_drag(doc_pos)
        else:
            # ホバー更新
            self._update_hover(doc_pos)

        x, y = doc_pos.x(), doc_pos.y()
        self.status_changed.emit(f"  X: {x:.1f}  Y: {y:.1f}  |  ズーム: {self._scale*100:.0f}%")

    def mouseReleaseEvent(self, event):
        if self._pan_start is not None:
            self._pan_start = None
            self.setCursor(self._cursors.get(self.current_tool, Qt.ArrowCursor))
            return

        if event.button() == Qt.LeftButton:
            if self.current_tool == TOOL_PEN:
                self._pen_release(self.to_doc(event.position()), event.modifiers())
            elif self.current_tool == TOOL_RESHAPE:
                self._reshape_release(self.to_doc(event.position()))
            elif self.current_tool == TOOL_SELECT:
                self._select_release()

    def mouseDoubleClickEvent(self, event):
        if self.current_tool == TOOL_PEN:
            self._pen_finish()
        elif self.current_tool == TOOL_RESHAPE:
            # パスを閉じる/開く
            if self.selected_path:
                self.selected_path.closed = not self.selected_path.closed
                self.update()

    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        pivot = event.position()
        # ピボット周りでスケール
        self._offset = QPointF(
            pivot.x() - (pivot.x() - self._offset.x()) * factor,
            pivot.y() - (pivot.y() - self._offset.y()) * factor,
        )
        self._scale *= factor
        self._scale = max(0.05, min(self._scale, 32.0))
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        # ノード削除
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.selected_node and self.selected_path:
                if self.selected_node in self.selected_path.nodes:
                    self.selected_path.nodes.remove(self.selected_node)
                    self.selected_node = None
                    self.update()
            elif self.selected_path:
                layer, _ = self.doc.find_path(self.selected_path.id)
                if layer:
                    self.undo_stack.push(DeletePathCommand(layer, self.selected_path))
                    self.selected_path = None
                    self.selection_changed.emit(None)
                    self.update()
        # Escape でツールをリセット
        elif key == Qt.Key_Escape:
            if self._pen_drawing:
                self._pen_finish()
            else:
                self.selected_path = None
                self.selected_node = None
                self.selection_changed.emit(None)
                self.update()

    # ── ペンツール ──

    def _pen_press(self, doc_pos: QPointF, mods):
        if not self._pen_drawing:
            # 新しいパス開始
            self._pen_path = VPath()
            self._pen_path.stroke_color = QColor(self.pen_color)
            self._pen_path.stroke_width = self.pen_width
            self._pen_drawing = True
        # ノード追加
        n = VNode(doc_pos)
        self._pen_path.nodes.append(n)
        self._last_pen_pos = doc_pos
        self.update()

    def _pen_drag(self, doc_pos: QPointF, mods):
        """ドラッグでコントロールポイントを設定"""
        if not self._pen_drawing or not self._pen_path.nodes:
            return
        n = self._pen_path.nodes[-1]
        dx = doc_pos.x() - n.pos.x()
        dy = doc_pos.y() - n.pos.y()
        n.cp_out = doc_pos
        n.cp_in  = QPointF(n.pos.x() - dx, n.pos.y() - dy)
        self.update()

    def _pen_release(self, doc_pos: QPointF, mods):
        pass

    def _pen_finish(self):
        if self._pen_path and len(self._pen_path.nodes) >= 2:
            layer = self.doc.active_layer
            self.undo_stack.push(AddPathCommand(self.doc, layer, self._pen_path))
            self.selected_path = self._pen_path
            self.selection_changed.emit(self._pen_path)
            self.document_changed.emit()
        self._pen_path = None
        self._pen_drawing = False
        self.update()

    # ── Reshape ──

    def _reshape_press(self, doc_pos: QPointF):
        # まずコントロールポイント確認
        if self.selected_path:
            cp_hit = self.selected_path.cp_at(doc_pos, 7.0 / self._scale)
            if cp_hit:
                self.selected_cp = cp_hit
                self._drag_start = doc_pos
                return
            # ノードヒット
            n = self.selected_path.node_at(doc_pos, 8.0 / self._scale)
            if n:
                self.selected_node = n
                self.selected_cp = None
                self._drag_start = doc_pos
                self._node_snap_before = (
                    QPointF(n.pos), QPointF(n.cp_in), QPointF(n.cp_out)
                )
                return

        # パス選択
        hit = self._hit_test_paths(doc_pos)
        if hit:
            self.selected_path = hit
            self.selected_node = None
            self.selected_cp = None
            self.selection_changed.emit(hit)
            # 直近ノード選択
            nearest = min(hit.nodes, key=lambda n: QLineF(n.pos, doc_pos).length(), default=None)
            self.selected_node = nearest
            self._drag_start = doc_pos
            if nearest:
                self._node_snap_before = (
                    QPointF(nearest.pos), QPointF(nearest.cp_in), QPointF(nearest.cp_out)
                )
        else:
            self.selected_path = None
            self.selected_node = None
            self.selection_changed.emit(None)
        self.update()

    def _reshape_drag(self, doc_pos: QPointF):
        if not self._drag_start:
            return
        if self.selected_cp:
            node, which = self.selected_cp
            if which == 'in':
                node.cp_in = doc_pos
                if node.smooth:
                    dx = node.cp_in.x() - node.pos.x()
                    dy = node.cp_in.y() - node.pos.y()
                    node.cp_out = QPointF(node.pos.x() - dx, node.pos.y() - dy)
            else:
                node.cp_out = doc_pos
                if node.smooth:
                    dx = node.cp_out.x() - node.pos.x()
                    dy = node.cp_out.y() - node.pos.y()
                    node.cp_in = QPointF(node.pos.x() - dx, node.pos.y() - dy)
            self.update()
        elif self.selected_node:
            self.selected_node.set_pos(doc_pos)
            self.update()

    def _reshape_release(self, doc_pos: QPointF):
        if self.selected_node and self._node_snap_before and self._drag_start:
            before = self._node_snap_before
            n = self.selected_node
            if before[0] != n.pos:
                self.undo_stack.push(MoveNodeCommand(
                    n,
                    before[0], QPointF(n.pos),
                    before[1], before[2],
                    QPointF(n.cp_in), QPointF(n.cp_out)
                ))
                self.document_changed.emit()
        self.selected_cp = None
        self._drag_start = None
        self._node_snap_before = None
        self.update()

    # ── Selectツール ──

    def _select_press(self, doc_pos: QPointF):
        hit = self._hit_test_paths(doc_pos)
        if hit:
            self.selected_path = hit
            self.selection_changed.emit(hit)
            self._drag_start = doc_pos
            # パス全体をドラッグ用に保存
            self._path_drag_start_positions = {
                n.id: (QPointF(n.pos), QPointF(n.cp_in), QPointF(n.cp_out))
                for n in hit.nodes
            }
        else:
            self.selected_path = None
            self.selection_changed.emit(None)
        self.update()

    def _select_drag(self, doc_pos: QPointF):
        if self.selected_path and self._drag_start:
            delta = doc_pos - self._drag_start
            for n in self.selected_path.nodes:
                if n.id in self._path_drag_start_positions:
                    sp, sci, sco = self._path_drag_start_positions[n.id]
                    n.pos    = sp + delta
                    n.cp_in  = sci + delta
                    n.cp_out = sco + delta
            self.update()

    def _select_release(self):
        self._drag_start = None
        self._path_drag_start_positions = {}
        self.document_changed.emit()

    # ── 消しゴム ──

    def _eraser_press(self, doc_pos: QPointF):
        hit = self._hit_test_paths(doc_pos)
        if hit:
            layer, _ = self.doc.find_path(hit.id)
            if layer:
                self.undo_stack.push(DeletePathCommand(layer, hit))
                if self.selected_path is hit:
                    self.selected_path = None
                    self.selection_changed.emit(None)
                self.document_changed.emit()
                self.update()

    # ── ユーティリティ ──

    def _hit_test_paths(self, doc_pos: QPointF) -> Optional[VPath]:
        radius = 6.0 / self._scale
        # 上のレイヤーから順に判定
        for layer in reversed(self.doc.layers):
            if not layer.visible or layer.locked:
                continue
            for vpath in reversed(layer.paths):
                if vpath.hit_test(doc_pos, radius):
                    return vpath
        return None

    def _update_hover(self, doc_pos: QPointF):
        prev_hn = self._hover_node
        prev_hp = self._hover_path
        self._hover_node = None
        self._hover_path = None
        if self.selected_path and self.current_tool == TOOL_RESHAPE:
            n = self.selected_path.node_at(doc_pos, 8.0 / self._scale)
            self._hover_node = n
        if not self._hover_node:
            self._hover_path = self._hit_test_paths(doc_pos)
        if prev_hn != self._hover_node or prev_hp != self._hover_path:
            self.update()

    def fit_canvas(self):
        """キャンバスをウィンドウにフィット"""
        w_ratio = (self.width() - 80) / self.doc.width
        h_ratio = (self.height() - 80) / self.doc.height
        self._scale = min(w_ratio, h_ratio)
        self._offset = QPointF(
            (self.width()  - self.doc.width  * self._scale) / 2,
            (self.height() - self.doc.height * self._scale) / 2,
        )
        self.update()

    def zoom_to(self, scale: float):
        center = QPointF(self.width() / 2, self.height() / 2)
        self._offset = QPointF(
            center.x() - (self.doc.width  / 2) * scale,
            center.y() - (self.doc.height / 2) * scale,
        )
        self._scale = scale
        self.update()


# ─────────────────────────────────────────────
#  レイヤーパネル
# ─────────────────────────────────────────────

class LayerPanel(QWidget):
    layer_selected = Signal(int)
    layer_changed = Signal()

    def __init__(self, doc: Document):
        super().__init__()
        self.doc = doc
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ボタンバー
        btn_bar = QWidget()
        btn_bar.setStyleSheet(f"background: {C['surface']}; border-bottom: 1px solid {C['border']};")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(6, 6, 6, 6)
        btn_layout.setSpacing(4)

        self.btn_add = QPushButton("＋")
        self.btn_add.setFixedSize(28, 28)
        self.btn_add.clicked.connect(self._add_layer)
        self.btn_del = QPushButton("－")
        self.btn_del.setFixedSize(28, 28)
        self.btn_del.setObjectName("danger")
        self.btn_del.clicked.connect(self._del_layer)
        self.btn_up = QPushButton("↑")
        self.btn_up.setFixedSize(28, 28)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_dn = QPushButton("↓")
        self.btn_dn.setFixedSize(28, 28)
        self.btn_dn.clicked.connect(self._move_down)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_dn)

        # リスト
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)

        layout.addWidget(btn_bar)
        layout.addWidget(self.list_widget, 1)

    def refresh(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for layer in reversed(self.doc.layers):  # 上が先頭
            item = QListWidgetItem(f"  {'👁' if layer.visible else '🚫'}  {layer.name}")
            item.setData(Qt.UserRole, layer.id)
            self.list_widget.addItem(item)
        # アクティブ選択
        idx = len(self.doc.layers) - 1 - self.doc.active_layer_idx
        self.list_widget.setCurrentRow(idx)
        self.list_widget.blockSignals(False)

    def _on_row_changed(self, row):
        if row < 0:
            return
        # reversedで表示しているので逆算
        actual_idx = len(self.doc.layers) - 1 - row
        self.doc.active_layer_idx = actual_idx
        self.layer_selected.emit(actual_idx)

    def _add_layer(self):
        n = len(self.doc.layers) + 1
        layer = Layer(f"レイヤー {n}")
        self.doc.layers.append(layer)
        self.doc.active_layer_idx = len(self.doc.layers) - 1
        self.refresh()
        self.layer_changed.emit()

    def _del_layer(self):
        if len(self.doc.layers) <= 1:
            return
        self.doc.layers.pop(self.doc.active_layer_idx)
        self.doc.active_layer_idx = max(0, self.doc.active_layer_idx - 1)
        self.refresh()
        self.layer_changed.emit()

    def _move_up(self):
        idx = self.doc.active_layer_idx
        if idx < len(self.doc.layers) - 1:
            self.doc.layers[idx], self.doc.layers[idx+1] = \
                self.doc.layers[idx+1], self.doc.layers[idx]
            self.doc.active_layer_idx = idx + 1
            self.refresh()
            self.layer_changed.emit()

    def _move_down(self):
        idx = self.doc.active_layer_idx
        if idx > 0:
            self.doc.layers[idx], self.doc.layers[idx-1] = \
                self.doc.layers[idx-1], self.doc.layers[idx]
            self.doc.active_layer_idx = idx - 1
            self.refresh()
            self.layer_changed.emit()


# ─────────────────────────────────────────────
#  プロパティパネル
# ─────────────────────────────────────────────

class PropertiesPanel(QWidget):
    path_changed = Signal()

    def __init__(self, canvas: 'Canvas'):
        super().__init__()
        self.canvas = canvas
        self._current_path: Optional[VPath] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ストロークカラー
        stroke_group = QGroupBox("ストローク")
        sg_layout = QVBoxLayout(stroke_group)
        self.btn_stroke_color = QPushButton("　　　　　")
        self.btn_stroke_color.setFixedHeight(28)
        self.btn_stroke_color.clicked.connect(self._pick_stroke_color)
        sg_layout.addWidget(self.btn_stroke_color)

        w_row = QHBoxLayout()
        w_row.addWidget(QLabel("太さ"))
        self.spin_stroke_w = QDoubleSpinBox()
        self.spin_stroke_w.setRange(0.1, 100.0)
        self.spin_stroke_w.setSingleStep(0.5)
        self.spin_stroke_w.setValue(2.0)
        self.spin_stroke_w.valueChanged.connect(self._on_stroke_w)
        w_row.addWidget(self.spin_stroke_w)
        sg_layout.addLayout(w_row)

        # 塗り
        fill_group = QGroupBox("塗り")
        fg_layout = QVBoxLayout(fill_group)
        self.btn_fill_color = QPushButton("なし")
        self.btn_fill_color.setFixedHeight(28)
        self.btn_fill_color.clicked.connect(self._pick_fill_color)
        fg_layout.addWidget(self.btn_fill_color)

        # 不透明度
        op_group = QGroupBox("不透明度")
        og_layout = QVBoxLayout(op_group)
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.valueChanged.connect(self._on_opacity)
        self.lbl_opacity = QLabel("100%")
        self.lbl_opacity.setAlignment(Qt.AlignRight)
        og_layout.addWidget(self.slider_opacity)
        og_layout.addWidget(self.lbl_opacity)

        # 閉じたパス
        self.btn_close_path = QPushButton("パスを閉じる / 開く")
        self.btn_close_path.clicked.connect(self._toggle_close)

        # ノード情報
        self.lbl_node_info = QLabel("パスを選択してください")
        self.lbl_node_info.setWordWrap(True)
        self.lbl_node_info.setStyleSheet(f"color: {C['fg_dim']}; font-size: 11px;")

        layout.addWidget(stroke_group)
        layout.addWidget(fill_group)
        layout.addWidget(op_group)
        layout.addWidget(self.btn_close_path)
        layout.addWidget(self.lbl_node_info)
        layout.addStretch()

        self.setEnabled(False)

    def set_path(self, vpath: Optional[VPath]):
        self._current_path = vpath
        self.setEnabled(vpath is not None)
        if not vpath:
            self.lbl_node_info.setText("パスを選択してください")
            return
        # ストローク
        c = vpath.stroke_color
        self.btn_stroke_color.setStyleSheet(
            f"background: {c.name()}; border: 1px solid {C['border']}; border-radius: 4px;"
        )
        self.spin_stroke_w.blockSignals(True)
        self.spin_stroke_w.setValue(vpath.stroke_width)
        self.spin_stroke_w.blockSignals(False)
        # 塗り
        if vpath.fill_color.alpha() > 0:
            fc = vpath.fill_color
            self.btn_fill_color.setText("")
            self.btn_fill_color.setStyleSheet(
                f"background: {fc.name()}; border: 1px solid {C['border']}; border-radius: 4px;"
            )
        else:
            self.btn_fill_color.setText("なし")
            self.btn_fill_color.setStyleSheet("")
        # 不透明度
        self.slider_opacity.blockSignals(True)
        self.slider_opacity.setValue(int(vpath.opacity * 100))
        self.slider_opacity.blockSignals(False)
        self.lbl_opacity.setText(f"{int(vpath.opacity*100)}%")
        # 情報
        n_count = len(vpath.nodes)
        self.lbl_node_info.setText(
            f"ノード数: {n_count}  |  {'閉じたパス' if vpath.closed else '開いたパス'}"
        )

    def _pick_stroke_color(self):
        if not self._current_path:
            return
        c = QColorDialog.getColor(self._current_path.stroke_color, self, "ストロークカラー")
        if c.isValid():
            self._current_path.stroke_color = c
            self.canvas.set_pen_color(c)
            self.set_path(self._current_path)
            self.canvas.update()
            self.path_changed.emit()

    def _pick_fill_color(self):
        if not self._current_path:
            return
        init = self._current_path.fill_color if self._current_path.fill_color.alpha() > 0 \
               else QColor(Qt.white)
        c = QColorDialog.getColor(init, self, "塗りカラー",
                                  QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self._current_path.fill_color = c
            self.set_path(self._current_path)
            self.canvas.update()
            self.path_changed.emit()

    def _on_stroke_w(self, val: float):
        if self._current_path:
            self._current_path.stroke_width = val
            self.canvas.set_pen_width(val)
            self.canvas.update()
            self.path_changed.emit()

    def _on_opacity(self, val: int):
        self.lbl_opacity.setText(f"{val}%")
        if self._current_path:
            self._current_path.opacity = val / 100.0
            self.canvas.update()
            self.path_changed.emit()

    def _toggle_close(self):
        if self._current_path:
            self._current_path.closed = not self._current_path.closed
            self.set_path(self._current_path)
            self.canvas.update()
            self.path_changed.emit()


# ─────────────────────────────────────────────
#  メインウィンドウ
# ─────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VektorStudio — MVP")
        self.resize(1400, 900)

        self.doc = Document()
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(100)

        self._filepath: Optional[str] = None
        self._modified = False

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_status()

        self.canvas.fit_canvas()

    def _build_ui(self):
        # 中央キャンバス
        self.canvas = Canvas(self.doc, self.undo_stack)
        self.canvas.status_changed.connect(self._on_status)
        self.canvas.selection_changed.connect(self._on_selection)
        self.canvas.document_changed.connect(self._mark_modified)
        self.setCentralWidget(self.canvas)

        # レイヤードック（右）
        self.layer_panel = LayerPanel(self.doc)
        self.layer_panel.layer_changed.connect(self.canvas.update)

        layer_dock = QDockWidget("レイヤー", self)
        layer_dock.setWidget(self.layer_panel)
        layer_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, layer_dock)

        # プロパティドック（右）
        self.props_panel = PropertiesPanel(self.canvas)
        self.props_panel.path_changed.connect(self.canvas.update)

        props_dock = QDockWidget("プロパティ", self)
        props_dock.setWidget(self.props_panel)
        props_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, props_dock)

        self.resizeDocks([layer_dock, props_dock], [250, 250], Qt.Horizontal)

    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(f"""
            QMenuBar {{
                background: {C['surface']};
                color: {C['fg']};
                border-bottom: 1px solid {C['border']};
                padding: 2px 4px;
            }}
            QMenuBar::item:selected {{ background: {C['accent']}; border-radius: 4px; }}
            QMenu {{
                background: {C['panel']};
                color: {C['fg']};
                border: 1px solid {C['border']};
            }}
            QMenu::item:selected {{ background: {C['accent']}; }}
            QMenu::separator {{ background: {C['border']}; height: 1px; margin: 3px 6px; }}
        """)

        # ファイル
        file_menu = mb.addMenu("ファイル")
        act_new   = file_menu.addAction("新規作成"); act_new.setShortcut("Ctrl+N")
        act_open  = file_menu.addAction("開く…");   act_open.setShortcut("Ctrl+O")
        file_menu.addSeparator()
        act_save  = file_menu.addAction("保存");    act_save.setShortcut("Ctrl+S")
        act_saveas= file_menu.addAction("別名保存…");act_saveas.setShortcut("Ctrl+Shift+S")
        file_menu.addSeparator()
        act_export= file_menu.addAction("SVGとして書き出し…")
        act_new.triggered.connect(self._new_doc)
        act_open.triggered.connect(self._open_svg)
        act_save.triggered.connect(self._save)
        act_saveas.triggered.connect(self._save_as)
        act_export.triggered.connect(self._export_svg)

        # 編集
        edit_menu = mb.addMenu("編集")
        act_undo = self.undo_stack.createUndoAction(self, "元に戻す")
        act_undo.setShortcut("Ctrl+Z")
        act_redo = self.undo_stack.createRedoAction(self, "やり直し")
        act_redo.setShortcut("Ctrl+Y")
        edit_menu.addAction(act_undo)
        edit_menu.addAction(act_redo)
        edit_menu.addSeparator()
        act_selall = edit_menu.addAction("すべて選択")
        act_selall.setShortcut("Ctrl+A")
        act_desel = edit_menu.addAction("選択解除")
        act_desel.setShortcut("Escape")
        act_selall.triggered.connect(self._select_all)
        act_desel.triggered.connect(lambda: self.canvas.keyPressEvent(
            type('E', (), {'key': lambda s: Qt.Key_Escape, 'modifiers': lambda s: Qt.NoModifier})()
        ))

        # 表示
        view_menu = mb.addMenu("表示")
        act_fit   = view_menu.addAction("キャンバスにフィット"); act_fit.setShortcut("Ctrl+0")
        act_100   = view_menu.addAction("100%");                 act_100.setShortcut("Ctrl+1")
        act_200   = view_menu.addAction("200%")
        act_fit.triggered.connect(self.canvas.fit_canvas)
        act_100.triggered.connect(lambda: self.canvas.zoom_to(1.0))
        act_200.triggered.connect(lambda: self.canvas.zoom_to(2.0))

    def _build_toolbar(self):
        tb = self.addToolBar("ツール")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))

        def tool_btn(label: str, shortcut: str, tool: str, tooltip: str):
            act = QAction(label, self)
            act.setShortcut(shortcut)
            act.setToolTip(f"{tooltip}  [{shortcut}]")
            act.setCheckable(True)
            act.triggered.connect(lambda checked: self._set_tool(tool))
            return act

        self._tool_actions = {}
        tools = [
            ("✏️",  "P", TOOL_PEN,     "ペン"),
            ("↗",  "A", TOOL_RESHAPE, "Reshape"),
            ("⬚",  "V", TOOL_SELECT,  "選択"),
            ("✋",  "H", TOOL_HAND,    "手のひら"),
            ("⌫",  "E", TOOL_ERASER,  "消しゴム"),
        ]
        for label, key, tool, tip in tools:
            act = tool_btn(label, key, tool, tip)
            self._tool_actions[tool] = act
            tb.addAction(act)

        tb.addSeparator()

        # ペンカラー
        self.lbl_pen_color = QLabel()
        self.lbl_pen_color.setFixedSize(24, 24)
        self.lbl_pen_color.setStyleSheet(
            f"background: {C['stroke_def']}; border: 2px solid {C['border']}; border-radius: 4px;"
        )
        self.lbl_pen_color.setCursor(Qt.PointingHandCursor)
        self.lbl_pen_color.mousePressEvent = lambda e: self._pick_pen_color()
        tb.addWidget(QLabel("  "))
        tb.addWidget(self.lbl_pen_color)
        tb.addWidget(QLabel("  色  "))

        # ペン太さ
        self.spin_pen_w = QDoubleSpinBox()
        self.spin_pen_w.setRange(0.1, 100.0)
        self.spin_pen_w.setValue(2.0)
        self.spin_pen_w.setSingleStep(0.5)
        self.spin_pen_w.setSuffix("px")
        self.spin_pen_w.setFixedWidth(80)
        self.spin_pen_w.setStyleSheet(f"""
            QDoubleSpinBox {{
                background: {C['surface']};
                border: 1px solid {C['border']};
                border-radius: 4px;
                padding: 2px 4px;
                color: {C['fg']};
            }}
        """)
        self.spin_pen_w.valueChanged.connect(self.canvas.set_pen_width)
        tb.addWidget(self.spin_pen_w)

        tb.addSeparator()

        # Undo/Redo
        act_undo = self.undo_stack.createUndoAction(self, "↩")
        act_redo = self.undo_stack.createRedoAction(self, "↪")
        act_undo.setShortcut("Ctrl+Z")
        act_redo.setShortcut("Ctrl+Y")
        tb.addAction(act_undo)
        tb.addAction(act_redo)

        # デフォルトツール選択
        self._set_tool(TOOL_PEN)

    def _build_status(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_status = QLabel("  VektorStudio MVP  |  Ctrl+Z: 元に戻す  |  ダブルクリック: パスを確定")
        self.status.addWidget(self.lbl_status)
        self.lbl_tool = QLabel()
        self.lbl_tool.setStyleSheet(f"color: {C['accent']}; padding-right: 10px;")
        self.status.addPermanentWidget(self.lbl_tool)

    def _set_tool(self, tool: str):
        for t, act in self._tool_actions.items():
            act.setChecked(t == tool)
        self.canvas.set_tool(tool)
        tool_names = {
            TOOL_PEN:     "ペンツール (P)",
            TOOL_RESHAPE: "Reshape (A)",
            TOOL_SELECT:  "選択 (V)",
            TOOL_HAND:    "手のひら (H)",
            TOOL_ERASER:  "消しゴム (E)",
        }
        self.lbl_tool.setText(tool_names.get(tool, tool))

    def _pick_pen_color(self):
        c = QColorDialog.getColor(self.canvas.pen_color, self, "ペンカラー")
        if c.isValid():
            self.canvas.set_pen_color(c)
            self.lbl_pen_color.setStyleSheet(
                f"background: {c.name()}; border: 2px solid {C['border']}; border-radius: 4px;"
            )

    def _on_status(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_selection(self, vpath):
        self.props_panel.set_path(vpath)

    def _mark_modified(self):
        self._modified = True
        title = f"VektorStudio — {'*' if self._modified else ''}"
        if self._filepath:
            title += self._filepath.split("/")[-1]
        else:
            title += "無題"
        self.setWindowTitle(title)

    def _new_doc(self):
        if self._modified:
            r = QMessageBox.question(self, "新規作成", "変更を保存しますか？",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Save:
                self._save()
            elif r == QMessageBox.Cancel:
                return
        self.doc = Document()
        self.canvas.doc = self.doc
        self.canvas.selected_path = None
        self.canvas.selected_node = None
        self.undo_stack.clear()
        self.layer_panel.doc = self.doc
        self.layer_panel.refresh()
        self._filepath = None
        self._modified = False
        self.canvas.fit_canvas()
        self.setWindowTitle("VektorStudio — 無題")

    def _open_svg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "SVGを開く", "", "SVG Files (*.svg);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                svg_text = f.read()
            doc = svg_to_document(svg_text)
            self.doc = doc
            self.canvas.doc = doc
            self.canvas.selected_path = None
            self.canvas.selected_node = None
            self.undo_stack.clear()
            self.layer_panel.doc = doc
            self.layer_panel.refresh()
            self._filepath = path
            self._modified = False
            self.canvas.fit_canvas()
            self.setWindowTitle(f"VektorStudio — {path.split('/')[-1]}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"SVGを読み込めませんでした:\n{e}")

    def _save(self):
        if self._filepath:
            self._write_svg(self._filepath)
        else:
            self._save_as()

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "SVGとして保存", "untitled.svg", "SVG Files (*.svg)"
        )
        if path:
            self._write_svg(path)
            self._filepath = path

    def _export_svg(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "SVGとして書き出し", "export.svg", "SVG Files (*.svg)"
        )
        if path:
            self._write_svg(path)

    def _write_svg(self, path: str):
        try:
            svg_text = document_to_svg(self.doc)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(svg_text)
            self._modified = False
            self.setWindowTitle(f"VektorStudio — {path.split('/')[-1]}")
            self.status.showMessage(f"保存しました: {path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")

    def _select_all(self):
        # 全パスをまとめて選択（最後のパスを選択状態に）
        all_paths = list(self.doc.active_layer.paths)
        if all_paths:
            self.canvas.selected_path = all_paths[-1]
            self.canvas.selection_changed.emit(all_paths[-1])
            self.canvas.update()


# ─────────────────────────────────────────────
#  エントリポイント
# ─────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VektorStudio")
    app.setOrganizationName("VOSE")
    app.setStyleSheet(STYLESHEET)

    # Retina対応
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
