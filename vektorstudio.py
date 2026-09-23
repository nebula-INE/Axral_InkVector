"""
VektorStudio v2 — 次世代ベクタークリエイティブスタジオ
Phase 1-3 完全版 + Phase 4 一部

バグ修正 (v2.0):
  ✓ 右クリック削除 TypeError → _delete_selected() に分離
  ✓ CmdInsertNode.undo が不完全 → 前後ノードCP含む完全スナップショット
  ✓ バケツ塗り既存パス更新にUndoなし → CmdSetFillColor 追加
  ✓ sym_cp_mirror 未使用 → ペンドラッグ時に正しく呼び出し
  ✓ SVGパーサ M/C/L/Z のみ → S/Q/T/A/H/V/s/q/t/a/h/v 追加

バグ修正 (v2.1):
  ✓ 手ブレ補正Chaikin: zip打ち切りでストローク終端が収縮 → resample_pts で正確にリサンプリング
  ✓ 手ブレ補正CP式: dx/tang_len*tang_len*0.33 のキャンセル → 正規化ベクトルで正確に計算
  ✓ 集中線二重描画: 単一VPathによるジグザグ+正描画の重複 → List[VPath]に分割し drawLine で直接描画
  ✓ 集中線PNG書き出し: _draw_focus_lines 未呼び出し → _render_path に drawLine 追加
  ✓ 効果線ツール死亡: mouseReleaseEvent ディスパッチなし → _speed_release 実装・ドラッグ方向自動判定
  ✓ _add_node_press エッジケース: node_b_actual=None → 閉じたパスラップアラウンド対応・デッドコード除去
  ✓ get_persp_snap 未実装スタブ → 最近傍透視ガイド線へのスナップ実装
  ✓ _export_svg デッドコード → 削除
  ✓ insert_node_at 型注釈 → Optional[Tuple] に修正

新機能:
  Phase 2:
    - ブラシスタジオ完全版（カスタムブラシ作成・数値編集・プリセット保存）
    - ベクター塗り完全版（隙間検知・輪郭トレース・閉鎖アルゴリズム）
    - パース定規（1点透視・2点透視）
    - グラデーションメッシュ（線形グラデーション）
    - 手ブレ補正（Chaikin スムージング + ローパスフィルタ）
  Phase 3:
    - フキダシジェネレーター（楕円/矩形/クラウド）
    - コマ割り（クリック＆ドラッグでコマ生成）
    - 集中線ジェネレーター
    - 効果線ジェネレーター（スピード線）
    - Webtoonモード（縦スクロール・ストリップレイアウト）
    - ベクタートーン（ドット・ライン・クロス）
  出力:
    - PNG / JPEG / WebP 書き出し（QImage経由レンダリング）
"""

import sys, math, uuid, json, re
from copy import deepcopy
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QStatusBar, QFileDialog, QMessageBox, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSlider, QColorDialog,
    QDockWidget, QAbstractItemView, QSpinBox, QDoubleSpinBox,
    QGroupBox, QComboBox, QDialog, QDialogButtonBox, QLineEdit,
    QCheckBox, QTabWidget, QSizePolicy, QScrollArea, QFrame,
    QMenu, QInputDialog, QRadioButton, QButtonGroup, QGridLayout,
    QScrollBar,
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor, QAction,
    QUndoStack, QUndoCommand, QTransform, QPainterPathStroker,
    QLinearGradient, QRadialGradient, QFont, QCursor, QKeySequence,
    QPixmap, QImage, QConicalGradient, QGradient,
)
from PySide6.QtCore import (
    Qt, QPointF, QRectF, QSizeF, QTimer, Signal, QLineF, QSize, QMarginsF,
)
import lxml.etree as ET

# ══════════════════════════════════════════════════════════════
#  テーマ
# ══════════════════════════════════════════════════════════════
C = {
    "bg":          "#0E0F11",
    "surface":     "#16181C",
    "panel":       "#1C1F24",
    "border":      "#2A2D35",
    "accent":      "#5B8CFF",
    "accent2":     "#A78BFA",
    "accent3":     "#34D399",
    "fg":          "#E8EAF0",
    "fg_dim":      "#6B7280",
    "node_fill":   "#5B8CFF",
    "node_sel":    "#A78BFA",
    "stroke_def":  "#E8EAF0",
    "canvas_bg":   "#1A1D22",
    "canvas_grid": "#1E2128",
    "danger":      "#FF5B6B",
    "warn":        "#FBBF24",
    "success":     "#4ADE80",
    "sym_line":    "#FF5B6B55",
    "persp_line":  "#FFD70055",
}

SS = f"""
* {{ box-sizing: border-box; }}
QMainWindow, QWidget {{
    background:{C['bg']}; color:{C['fg']};
    font-family:'Inter','Hiragino Kaku Gothic Pro','Meiryo','Yu Gothic UI',sans-serif;
    font-size:12px;
}}
QToolBar {{
    background:{C['surface']}; border-bottom:1px solid {C['border']};
    spacing:2px; padding:3px 6px;
}}
QToolBar QToolButton {{
    background:transparent; border:1px solid transparent;
    border-radius:6px; padding:5px 7px; color:{C['fg']};
    font-size:14px; min-width:30px; min-height:28px;
}}
QToolBar QToolButton:hover {{ background:{C['panel']}; border-color:{C['border']}; }}
QToolBar QToolButton:checked {{ background:{C['accent']}; color:#fff; border-color:{C['accent']}; }}
QMenuBar {{ background:{C['surface']}; color:{C['fg']}; border-bottom:1px solid {C['border']}; padding:2px 4px; }}
QMenuBar::item {{ padding:4px 8px; border-radius:4px; }}
QMenuBar::item:selected {{ background:{C['accent']}; }}
QMenu {{ background:{C['panel']}; color:{C['fg']}; border:1px solid {C['border']}; border-radius:6px; padding:4px; }}
QMenu::item {{ padding:5px 20px 5px 10px; border-radius:4px; }}
QMenu::item:selected {{ background:{C['accent']}; }}
QMenu::separator {{ background:{C['border']}; height:1px; margin:3px 6px; }}
QDockWidget {{ background:{C['panel']}; }}
QDockWidget::title {{ background:{C['surface']}; padding:6px 10px; border-bottom:1px solid {C['border']}; font-weight:600; font-size:11px; letter-spacing:0.5px; color:{C['fg_dim']}; }}
QListWidget {{ background:{C['panel']}; border:none; outline:none; }}
QListWidget::item {{ padding:7px 10px; border-bottom:1px solid {C['border']}; border-radius:4px; margin:1px 4px; }}
QListWidget::item:selected {{ background:{C['accent']}; color:#fff; }}
QListWidget::item:hover:!selected {{ background:{C['surface']}; }}
QPushButton {{ background:{C['surface']}; border:1px solid {C['border']}; border-radius:6px; padding:5px 12px; color:{C['fg']}; min-height:24px; }}
QPushButton:hover {{ background:{C['panel']}; border-color:{C['accent']}; }}
QPushButton:pressed {{ background:{C['accent']}; color:#fff; }}
QPushButton#accent {{ background:{C['accent']}; border-color:{C['accent']}; color:#fff; font-weight:600; }}
QPushButton#accent:hover {{ background:#4A7AEE; }}
QPushButton#danger {{ background:transparent; border-color:{C['danger']}; color:{C['danger']}; }}
QPushButton#danger:hover {{ background:{C['danger']}; color:#fff; }}
QPushButton#success {{ background:{C['accent3']}; border-color:{C['accent3']}; color:#000; font-weight:600; }}
QSlider::groove:horizontal {{ background:{C['border']}; height:4px; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{C['accent']}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QSlider::sub-page:horizontal {{ background:{C['accent']}; border-radius:2px; }}
QStatusBar {{ background:{C['surface']}; border-top:1px solid {C['border']}; color:{C['fg_dim']}; font-size:11px; }}
QGroupBox {{ border:1px solid {C['border']}; border-radius:6px; margin-top:10px; padding-top:10px; font-size:11px; color:{C['fg_dim']}; }}
QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}
QSpinBox, QDoubleSpinBox, QLineEdit {{ background:{C['surface']}; border:1px solid {C['border']}; border-radius:4px; padding:3px 6px; color:{C['fg']}; }}
QComboBox {{ background:{C['surface']}; border:1px solid {C['border']}; border-radius:4px; padding:3px 8px; color:{C['fg']}; min-height:24px; }}
QComboBox QAbstractItemView {{ background:{C['panel']}; color:{C['fg']}; border:1px solid {C['border']}; }}
QTabWidget::pane {{ border:1px solid {C['border']}; border-radius:4px; }}
QTabBar::tab {{ background:{C['surface']}; color:{C['fg_dim']}; padding:6px 14px; border-bottom:2px solid transparent; }}
QTabBar::tab:selected {{ color:{C['fg']}; border-bottom:2px solid {C['accent']}; }}
QScrollBar:vertical {{ background:{C['surface']}; width:7px; border-radius:3px; }}
QScrollBar::handle:vertical {{ background:{C['border']}; border-radius:3px; min-height:20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:{C['surface']}; height:7px; border-radius:3px; }}
QScrollBar::handle:horizontal {{ background:{C['border']}; border-radius:3px; min-width:20px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QDialog {{ background:{C['panel']}; }}
QCheckBox {{ color:{C['fg']}; spacing:6px; }}
QCheckBox::indicator {{ width:14px; height:14px; border:1px solid {C['border']}; border-radius:3px; background:{C['surface']}; }}
QCheckBox::indicator:checked {{ background:{C['accent']}; border-color:{C['accent']}; }}
QRadioButton {{ color:{C['fg']}; spacing:6px; }}
QRadioButton::indicator {{ width:14px; height:14px; border:1px solid {C['border']}; border-radius:7px; background:{C['surface']}; }}
QRadioButton::indicator:checked {{ background:{C['accent']}; border-color:{C['accent']}; }}
"""

# ══════════════════════════════════════════════════════════════
#  定数
# ══════════════════════════════════════════════════════════════
TOOL_PEN        = "pen"
TOOL_RESHAPE    = "reshape"
TOOL_SELECT     = "select"
TOOL_HAND       = "hand"
TOOL_ERASER     = "eraser"
TOOL_ADD_NODE   = "add_node"
TOOL_DEL_NODE   = "del_node"
TOOL_WIDTH      = "width"
TOOL_BUCKET     = "bucket"
TOOL_SCISSORS   = "scissors"
TOOL_BALLOON    = "balloon"   # フキダシ
TOOL_PANEL      = "panel"     # コマ割り
TOOL_FOCUS_LINE = "focus"     # 集中線
TOOL_SPEED_LINE = "speed"     # 効果線

BLEND_MODES = ["通常","乗算","スクリーン","オーバーレイ","ソフトライト"]
BLEND_MAP   = {
    "通常":         QPainter.CompositionMode_SourceOver,
    "乗算":         QPainter.CompositionMode_Multiply,
    "スクリーン":   QPainter.CompositionMode_Screen,
    "オーバーレイ": QPainter.CompositionMode_Overlay,
    "ソフトライト": QPainter.CompositionMode_SoftLight,
}
SYM_NONE  = "なし"
SYM_H     = "左右"
SYM_V     = "上下"
SYM_CROSS = "4方向"

PERSP_NONE = "なし"
PERSP_1PT  = "1点透視"
PERSP_2PT  = "2点透視"

TONE_NONE  = "なし"
TONE_DOT   = "ドット"
TONE_LINE  = "ライン"
TONE_CROSS = "クロス"

BALLOON_ELLIPSE = "楕円"
BALLOON_RECT    = "矩形"
BALLOON_CLOUD   = "クラウド"
BALLOON_SPIKY   = "ギザギザ"

# デフォルトブラシプリセット
DEFAULT_BRUSHES: Dict[str,Dict] = {
    "Gペン":     {"pressure_width":True,  "opacity_var":0.0, "scatter":0.0, "tip":"round",  "smoothing":0.3, "taper":0.1},
    "鉛筆":      {"pressure_width":True,  "opacity_var":0.3, "scatter":1.5, "tip":"round",  "smoothing":0.5, "taper":0.0},
    "マーカー":  {"pressure_width":False, "opacity_var":0.0, "scatter":0.0, "tip":"flat",   "smoothing":0.2, "taper":0.0},
    "水彩":      {"pressure_width":True,  "opacity_var":0.5, "scatter":2.5, "tip":"round",  "smoothing":0.6, "taper":0.2},
    "エアブラシ":{"pressure_width":False, "opacity_var":0.6, "scatter":6.0, "tip":"soft",   "smoothing":0.4, "taper":0.0},
    "カリグラフィ":{"pressure_width":True,"opacity_var":0.1, "scatter":0.0, "tip":"angle",  "smoothing":0.3, "taper":0.3},
}

# ══════════════════════════════════════════════════════════════
#  ユーティリティ
# ══════════════════════════════════════════════════════════════
def _lerp(a: QPointF, b: QPointF, t: float) -> QPointF:
    return QPointF(a.x()*(1-t)+b.x()*t, a.y()*(1-t)+b.y()*t)

def _cubic(p0,p1,p2,p3,t) -> QPointF:
    u=1-t
    return QPointF(u**3*p0.x()+3*u**2*t*p1.x()+3*u*t**2*p2.x()+t**3*p3.x(),
                   u**3*p0.y()+3*u**2*t*p1.y()+3*u*t**2*p2.y()+t**3*p3.y())

def _rotate_pt(p: QPointF, c: QPointF, deg: float) -> QPointF:
    r=math.radians(deg); dx=p.x()-c.x(); dy=p.y()-c.y()
    return QPointF(c.x()+dx*math.cos(r)-dy*math.sin(r),
                   c.y()+dx*math.sin(r)+dy*math.cos(r))

def chaikin_smooth(pts: List[QPointF], iterations: int=2) -> List[QPointF]:
    """Chaikinアルゴリズムによる手ブレ補正（点数が増える）"""
    for _ in range(iterations):
        if len(pts)<3: break
        new_pts=[pts[0]]
        for i in range(len(pts)-1):
            a,b=pts[i],pts[i+1]
            new_pts.append(_lerp(a,b,0.25))
            new_pts.append(_lerp(a,b,0.75))
        new_pts.append(pts[-1])
        pts=new_pts
    return pts

def resample_pts(pts: List[QPointF], target_n: int) -> List[QPointF]:
    """点列を target_n 点に均等リサンプリング（Chaikin後の点数合わせに使用）"""
    if len(pts)==0: return pts
    if len(pts)==1: return [pts[0]]*target_n
    if target_n<=1: return [pts[0]]
    step=(len(pts)-1)/(target_n-1)
    return [pts[min(int(round(i*step)),len(pts)-1)] for i in range(target_n)]

def lowpass_smooth(pts: List[QPointF], alpha: float=0.4) -> List[QPointF]:
    """ローパスフィルタによる手ブレ補正"""
    if len(pts)<2: return pts
    result=[pts[0]]
    for i in range(1,len(pts)):
        prev=result[-1]
        result.append(QPointF(prev.x()+alpha*(pts[i].x()-prev.x()),
                              prev.y()+alpha*(pts[i].y()-prev.y())))
    return result

def sym_points(doc, pt: QPointF) -> List[QPointF]:
    cx,cy=doc.sym_cx,doc.sym_cy; x,y=pt.x(),pt.y()
    if doc.symmetry==SYM_H:     return [QPointF(2*cx-x,y)]
    elif doc.symmetry==SYM_V:   return [QPointF(x,2*cy-y)]
    elif doc.symmetry==SYM_CROSS: return [QPointF(2*cx-x,y),QPointF(x,2*cy-y),QPointF(2*cx-x,2*cy-y)]
    return []

def sym_mirror_cp(doc, node_pos: QPointF, cp_out: QPointF, sym_pos: QPointF, sym_type: str) -> Tuple[QPointF,QPointF]:
    """シンメトリーCPミラー: (sym_cp_in, sym_cp_out) を返す"""
    dx=cp_out.x()-node_pos.x(); dy=cp_out.y()-node_pos.y()
    if sym_type==SYM_H:
        return (QPointF(sym_pos.x()+dx,sym_pos.y()-dy), QPointF(sym_pos.x()-dx,sym_pos.y()+dy))
    elif sym_type==SYM_V:
        return (QPointF(sym_pos.x()-dx,sym_pos.y()+dy), QPointF(sym_pos.x()+dx,sym_pos.y()-dy))
    else:
        return (QPointF(sym_pos.x()-dx,sym_pos.y()-dy), QPointF(sym_pos.x()+dx,sym_pos.y()+dy))

# ══════════════════════════════════════════════════════════════
#  データモデル
# ══════════════════════════════════════════════════════════════
class VNode:
    __slots__=("id","pos","cp_in","cp_out","smooth")
    def __init__(self,pos,cp_in=None,cp_out=None):
        self.id=uuid.uuid4().hex[:8]; self.pos=QPointF(pos)
        self.cp_in=QPointF(cp_in) if cp_in else QPointF(pos)
        self.cp_out=QPointF(cp_out) if cp_out else QPointF(pos)
        self.smooth=True
    def set_pos(self,p):
        dx=p.x()-self.pos.x(); dy=p.y()-self.pos.y(); self.pos=QPointF(p)
        self.cp_in=QPointF(self.cp_in.x()+dx,self.cp_in.y()+dy)
        self.cp_out=QPointF(self.cp_out.x()+dx,self.cp_out.y()+dy)
    def clone(self): return VNode(self.pos,self.cp_in,self.cp_out)
    def snapshot(self): return (QPointF(self.pos),QPointF(self.cp_in),QPointF(self.cp_out))
    def restore(self,s): self.pos=QPointF(s[0]); self.cp_in=QPointF(s[1]); self.cp_out=QPointF(s[2])

class VPath:
    def __init__(self):
        self.id=uuid.uuid4().hex[:8]; self.nodes:List[VNode]=[]
        self.closed=False
        self.stroke_color=QColor(C["stroke_def"]); self.stroke_width=2.0
        self.fill_color=QColor(Qt.transparent); self.opacity=1.0; self.visible=True
        self.brush_name="Gペン"; self.pressure:List[float]=[]
        # グラデーション
        self.gradient_enabled=False
        self.gradient_start=QColor("#5B8CFF"); self.gradient_end=QColor("#A78BFA")
        self.gradient_angle=0.0
        # トーン
        self.tone_type=TONE_NONE; self.tone_freq=20.0; self.tone_size=3.0
        # メタ (フキダシ/コマなど)
        self.meta: Dict[str,Any]={}

    def to_qpath(self) -> QPainterPath:
        p=QPainterPath()
        if not self.nodes: return p
        p.moveTo(self.nodes[0].pos)
        for i in range(1,len(self.nodes)):
            a,b=self.nodes[i-1],self.nodes[i]; p.cubicTo(a.cp_out,b.cp_in,b.pos)
        if self.closed and len(self.nodes)>=2:
            a,b=self.nodes[-1],self.nodes[0]; p.cubicTo(a.cp_out,b.cp_in,b.pos)
            p.closeSubpath()
        return p

    def hit_test(self,pt,r=8.0):
        qp=self.to_qpath(); st=QPainterPathStroker(); st.setWidth(max(self.stroke_width,r*2))
        if st.createStroke(qp).contains(pt): return True
        if self.fill_color.alpha()>0: return qp.contains(pt)
        return False

    def node_at(self,pt,r=8.0):
        for n in self.nodes:
            if QLineF(n.pos,pt).length()<r: return n
        return None

    def cp_at(self,pt,r=7.0):
        for n in self.nodes:
            if n.cp_in!=n.pos and QLineF(n.cp_in,pt).length()<r: return (n,'in')
            if n.cp_out!=n.pos and QLineF(n.cp_out,pt).length()<r: return (n,'out')
        return None

    def bounding_rect(self): return self.to_qpath().boundingRect()

    def insert_node_at(self,pt) -> Optional[Tuple['VNode',int,QPointF,QPointF]]:
        if len(self.nodes)<2: return None
        best_i,best_t,best_d=0,0.5,float('inf')
        segs=len(self.nodes)-(0 if self.closed else 1)
        for i in range(segs):
            a=self.nodes[i]; b=self.nodes[(i+1)%len(self.nodes)]
            for t_step in range(1,20):
                t=t_step/20
                pp=_cubic(a.pos,a.cp_out,b.cp_in,b.pos,t); d=QLineF(pp,pt).length()
                if d<best_d: best_d=d; best_i=i; best_t=t
        if best_d>30: return None
        i=best_i; a=self.nodes[i]; b=self.nodes[(i+1)%len(self.nodes)]; t=best_t
        p0,p1,p2,p3=a.pos,a.cp_out,b.cp_in,b.pos
        q0=_lerp(p0,p1,t); q1=_lerp(p1,p2,t); q2=_lerp(p2,p3,t)
        r0=_lerp(q0,q1,t); r1=_lerp(q1,q2,t); s=_lerp(r0,r1,t)
        # 前後ノードのCP変化を記録 (Undo用)
        old_a_out=QPointF(a.cp_out); old_b_in=QPointF(b.cp_in)
        a.cp_out=q0; b.cp_in=q2
        new_node=VNode(s,r0,r1)
        self.nodes.insert(i+1,new_node)
        return new_node,i+1,old_a_out,old_b_in

    def clone(self):
        vp=VPath(); vp.nodes=[n.clone() for n in self.nodes]; vp.closed=self.closed
        vp.stroke_color=QColor(self.stroke_color); vp.stroke_width=self.stroke_width
        vp.fill_color=QColor(self.fill_color); vp.opacity=self.opacity
        vp.visible=self.visible; vp.brush_name=self.brush_name; vp.pressure=list(self.pressure)
        vp.gradient_enabled=self.gradient_enabled
        vp.gradient_start=QColor(self.gradient_start); vp.gradient_end=QColor(self.gradient_end)
        vp.gradient_angle=self.gradient_angle
        vp.tone_type=self.tone_type; vp.tone_freq=self.tone_freq; vp.tone_size=self.tone_size
        vp.meta=dict(self.meta)
        return vp

class VGroup:
    def __init__(self,name="グループ"):
        self.id=uuid.uuid4().hex[:8]; self.name=name
        self.items:List[VPath]=[]; self.opacity=1.0; self.visible=True
    def bounding_rect(self):
        r=QRectF()
        for p in self.items: r=r.united(p.bounding_rect())
        return r

class Layer:
    def __init__(self,name="レイヤー"):
        self.id=uuid.uuid4().hex[:8]; self.name=name
        self.items:List=[];  self.visible=True; self.locked=False
        self.opacity=1.0; self.blend="通常"
    @property
    def paths(self) -> List[VPath]:
        r=[]
        for item in self.items:
            if isinstance(item,VPath): r.append(item)
            elif isinstance(item,VGroup): r.extend(item.items)
        return r
    def add_path(self,vp): self.items.append(vp)
    def remove_path(self,vp):
        if vp in self.items: self.items.remove(vp); return
        for item in self.items:
            if isinstance(item,VGroup) and vp in item.items:
                item.items.remove(vp); return

class Document:
    def __init__(self,w=1200,h=800):
        self.width=w; self.height=h
        self.layers:List[Layer]=[Layer("レイヤー 1")]
        self.active_layer_idx=0
        self.symmetry=SYM_NONE; self.sym_cx=w/2; self.sym_cy=h/2
        self.perspective=PERSP_NONE
        self.persp_vp1=QPointF(w/2,h/2)    # 消失点1
        self.persp_vp2=QPointF(w*3/4,h/2)  # 消失点2
        self.horizon_y=h/2
        self.webtoon_mode=False
        self.webtoon_strip_height=400
        self.brush_presets:Dict[str,Dict]=dict(DEFAULT_BRUSHES)
    @property
    def active_layer(self): return self.layers[self.active_layer_idx]
    def all_paths(self):
        for layer in self.layers:
            for p in layer.paths: yield (layer,p)
    def find_path(self,pid):
        for layer in self.layers:
            for item in layer.items:
                if isinstance(item,VPath) and item.id==pid: return (layer,item)
                elif isinstance(item,VGroup):
                    for p in item.items:
                        if p.id==pid: return (layer,p)
        return (None,None)
    def find_group_of(self,vp):
        for layer in self.layers:
            for item in layer.items:
                if isinstance(item,VGroup) and vp in item.items: return (layer,item)
        return (None,None)

# ══════════════════════════════════════════════════════════════
#  Undo コマンド
# ══════════════════════════════════════════════════════════════
class CmdAddPath(QUndoCommand):
    def __init__(self,layer,vp): super().__init__("パス追加"); self.l=layer; self.vp=vp
    def redo(self): self.l.add_path(self.vp)
    def undo(self): self.l.remove_path(self.vp)

class CmdDeletePaths(QUndoCommand):
    def __init__(self,pairs): super().__init__("削除"); self.pairs=pairs
    def redo(self):
        for l,vp in self.pairs: l.remove_path(vp)
    def undo(self):
        for l,vp in self.pairs: l.add_path(vp)

class CmdMoveNode(QUndoCommand):
    def __init__(self,node,snap_before,snap_after):
        super().__init__("ノード移動"); self.n=node; self.b=snap_before; self.a=snap_after
    def redo(self): self.n.restore(self.a)
    def undo(self): self.n.restore(self.b)

class CmdMovePaths(QUndoCommand):
    def __init__(self,before,after): super().__init__("移動"); self.b=before; self.a=after
    def _apply(self,snaps):
        for vp,states in snaps.items():
            for n,(pos,cpi,cpo) in zip(vp.nodes,states):
                n.pos=QPointF(pos); n.cp_in=QPointF(cpi); n.cp_out=QPointF(cpo)
    def redo(self): self._apply(self.a)
    def undo(self): self._apply(self.b)

class CmdGroupPaths(QUndoCommand):
    def __init__(self,layer,paths,grp): super().__init__("グループ化"); self.l=layer; self.paths=paths; self.grp=grp
    def redo(self):
        for vp in self.paths:
            if vp in self.l.items: self.l.items.remove(vp)
        self.l.items.append(self.grp)
    def undo(self):
        if self.grp in self.l.items: self.l.items.remove(self.grp)
        for vp in self.paths: self.l.items.append(vp)

class CmdUngroupPaths(QUndoCommand):
    def __init__(self,layer,grp): super().__init__("グループ解除"); self.l=layer; self.grp=grp
    def redo(self):
        if self.grp in self.l.items: self.l.items.remove(self.grp)
        for vp in self.grp.items: self.l.items.append(vp)
    def undo(self):
        for vp in self.grp.items:
            if vp in self.l.items: self.l.items.remove(vp)
        self.l.items.append(self.grp)

class CmdSetStrokeWidth(QUndoCommand):
    def __init__(self,vp,old,new): super().__init__("線幅変更"); self.vp=vp; self.o=old; self.n=new
    def redo(self): self.vp.stroke_width=self.n
    def undo(self): self.vp.stroke_width=self.o

class CmdSetFillColor(QUndoCommand):
    """バグ修正3: バケツ塗りUndoコマンド"""
    def __init__(self,vp,old,new): super().__init__("塗り変更"); self.vp=vp; self.o=old; self.n=new
    def redo(self): self.vp.fill_color=QColor(self.n)
    def undo(self): self.vp.fill_color=QColor(self.o)

class CmdInsertNode(QUndoCommand):
    """バグ修正2: 前後ノードのCP変化も完全Undo"""
    def __init__(self,vp,new_node,idx,node_a,node_b,old_a_out,old_b_in,new_a_out,new_b_in):
        super().__init__("ノード追加")
        self.vp=vp; self.new_node=new_node; self.idx=idx
        self.node_a=node_a; self.node_b=node_b
        self.old_a_out=old_a_out; self.old_b_in=old_b_in
        self.new_a_out=new_a_out; self.new_b_in=new_b_in
    def redo(self):
        if self.new_node not in self.vp.nodes:
            self.vp.nodes.insert(self.idx,self.new_node)
        self.node_a.cp_out=QPointF(self.new_a_out)
        self.node_b.cp_in=QPointF(self.new_b_in)
    def undo(self):
        if self.new_node in self.vp.nodes: self.vp.nodes.remove(self.new_node)
        self.node_a.cp_out=QPointF(self.old_a_out)
        self.node_b.cp_in=QPointF(self.old_b_in)

class CmdDeleteNode(QUndoCommand):
    def __init__(self,vp,node,idx): super().__init__("ノード削除"); self.vp=vp; self.n=node; self.idx=idx
    def redo(self):
        if self.n in self.vp.nodes: self.vp.nodes.remove(self.n)
    def undo(self): self.vp.nodes.insert(self.idx,self.n)

# ══════════════════════════════════════════════════════════════
#  SVG 入出力 (S/Q/T/A/H/V 対応)
# ══════════════════════════════════════════════════════════════
def _pt(p): return f"{p.x():.3f},{p.y():.3f}"
def _col(c): return "none" if c.alpha()==0 else c.name()

def path_to_d(vp: VPath) -> str:
    ns=vp.nodes
    if not ns: return ""
    parts=[f"M {_pt(ns[0].pos)}"]
    for i in range(1,len(ns)):
        a,b=ns[i-1],ns[i]; parts.append(f"C {_pt(a.cp_out)} {_pt(b.cp_in)} {_pt(b.pos)}")
    if vp.closed and len(ns)>=2:
        a,b=ns[-1],ns[0]; parts.append(f"C {_pt(a.cp_out)} {_pt(b.cp_in)} {_pt(b.pos)} Z")
    return " ".join(parts)

def document_to_svg(doc: Document) -> str:
    root=ET.Element("svg",{
        "xmlns":"http://www.w3.org/2000/svg",
        "width":str(doc.width),"height":str(doc.height),
        "viewBox":f"0 0 {doc.width} {doc.height}",
        "data-app":"VektorStudio","data-version":"2",
        "data-symmetry":doc.symmetry,"data-perspective":doc.perspective,
    })
    for layer in doc.layers:
        g=ET.SubElement(root,"g",{
            "id":f"layer-{layer.id}","data-name":layer.name,
            "data-blend":layer.blend,"opacity":str(layer.opacity),
        })
        if not layer.visible: g.set("display","none")
        if layer.locked:      g.set("data-locked","1")
        for item in layer.items:
            if isinstance(item,VPath): _vpath_to_el(g,item)
            elif isinstance(item,VGroup):
                gg=ET.SubElement(g,"g",{
                    "id":f"group-{item.id}","data-name":item.name,
                    "opacity":str(item.opacity),"data-group":"1",
                })
                if not item.visible: gg.set("display","none")
                for vp in item.items: _vpath_to_el(gg,vp)
    return ET.tostring(root,pretty_print=True,xml_declaration=True,encoding="UTF-8").decode()

def _vpath_to_el(parent,vp:VPath):
    d=path_to_d(vp)
    if not d: return
    attrs={
        "id":f"path-{vp.id}","d":d,
        "stroke":_col(vp.stroke_color),"stroke-width":str(vp.stroke_width),
        "fill":_col(vp.fill_color),"opacity":str(vp.opacity),
        "stroke-linecap":"round","stroke-linejoin":"round",
        "data-brush":vp.brush_name,
        "data-tone":vp.tone_type,"data-tone-freq":str(vp.tone_freq),"data-tone-size":str(vp.tone_size),
    }
    if vp.gradient_enabled:
        attrs["data-grad"]="1"
        attrs["data-grad-start"]=vp.gradient_start.name()
        attrs["data-grad-end"]=vp.gradient_end.name()
        attrs["data-grad-angle"]=str(vp.gradient_angle)
    if vp.meta: attrs["data-meta"]=json.dumps(vp.meta)
    if not vp.visible: attrs["display"]="none"
    ET.SubElement(parent,"path",attrs)

def svg_to_document(svg_text: str) -> Document:
    root=ET.fromstring(svg_text.encode())
    def sn(tag): return tag.split("}")[-1]
    w=float(root.get("width",1200)); h=float(root.get("height",800))
    doc=Document(int(w),int(h))
    doc.symmetry=root.get("data-symmetry",SYM_NONE)
    doc.perspective=root.get("data-perspective",PERSP_NONE)
    doc.layers=[]
    def parse_path_el(el):
        d=el.get("d","")
        if not d: return None
        return _d_to_vpath(d,dict(el.attrib))
    def parse_g(g_el):
        name=g_el.get("data-name",g_el.get("id","レイヤー"))
        layer=Layer(name)
        try: layer.opacity=float(g_el.get("opacity","1"))
        except: pass
        layer.blend=g_el.get("data-blend","通常")
        layer.visible=g_el.get("display","")!="none"
        layer.locked=g_el.get("data-locked","0")=="1"
        for child in g_el:
            tag=sn(child.tag)
            if tag=="path":
                vp=parse_path_el(child)
                if vp: layer.items.append(vp)
            elif tag=="g":
                if child.get("data-group")=="1":
                    grp=VGroup(child.get("data-name","グループ"))
                    try: grp.opacity=float(child.get("opacity","1"))
                    except: pass
                    grp.visible=child.get("display","")!="none"
                    for sub in child:
                        if sn(sub.tag)=="path":
                            vp=parse_path_el(sub)
                            if vp: grp.items.append(vp)
                    layer.items.append(grp)
        return layer
    gs=[c for c in root if sn(c.tag)=="g"]
    if gs:
        for g_el in gs: doc.layers.append(parse_g(g_el))
    else:
        layer=Layer("レイヤー 1")
        for el in root:
            if sn(el.tag)=="path":
                vp=parse_path_el(el)
                if vp: layer.items.append(vp)
        doc.layers.append(layer)
    if not doc.layers: doc.layers=[Layer("レイヤー 1")]
    doc.active_layer_idx=0
    return doc

def _d_to_vpath(d: str, attrs: dict) -> Optional[VPath]:
    """拡張SVGパーサ: M/C/L/Z/S/Q/T/A/H/V 対応 (バグ修正5)"""
    vp=VPath()
    toks=re.findall(r'[MCZmczLlHhVvSsQqTtAa]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?',d)
    i=0; last=QPointF(0,0); nodes=[]; last_cmd='M'; last_cp=None
    def rf():
        nonlocal i; v=float(toks[i]); i+=1; return v
    def is_cmd(): return i<len(toks) and toks[i] in 'MCZmczLlHhVvSsQqTtAa'
    def has_n(n): return i+n-1<len(toks)
    while i<len(toks):
        cmd=toks[i]; i+=1; last_cmd=cmd
        if cmd in('M','m'):
            x,y=rf(),rf()
            if cmd=='m': x+=last.x(); y+=last.y()
            n=VNode(QPointF(x,y)); nodes.append(n); last=QPointF(x,y); last_cp=None
        elif cmd in('C','c'):
            while not is_cmd() and has_n(6):
                try: x1,y1,x2,y2,ex,ey=rf(),rf(),rf(),rf(),rf(),rf()
                except: break
                if cmd=='c': x1+=last.x();y1+=last.y();x2+=last.x();y2+=last.y();ex+=last.x();ey+=last.y()
                if nodes: nodes[-1].cp_out=QPointF(x1,y1)
                n=VNode(QPointF(ex,ey),QPointF(x2,y2)); nodes.append(n)
                last=QPointF(ex,ey); last_cp=QPointF(x2,y2)
        elif cmd in('S','s'):
            while not is_cmd() and has_n(4):
                try: x2,y2,ex,ey=rf(),rf(),rf(),rf()
                except: break
                if cmd=='s': x2+=last.x();y2+=last.y();ex+=last.x();ey+=last.y()
                # 対称CP
                if last_cp and nodes:
                    x1=2*last.x()-last_cp.x(); y1=2*last.y()-last_cp.y()
                else:
                    x1,y1=last.x(),last.y()
                if nodes: nodes[-1].cp_out=QPointF(x1,y1)
                n=VNode(QPointF(ex,ey),QPointF(x2,y2)); nodes.append(n)
                last=QPointF(ex,ey); last_cp=QPointF(x2,y2)
        elif cmd in('Q','q'):
            while not is_cmd() and has_n(4):
                try: x1,y1,ex,ey=rf(),rf(),rf(),rf()
                except: break
                if cmd=='q': x1+=last.x();y1+=last.y();ex+=last.x();ey+=last.y()
                # 二次→三次変換
                qx1=last.x()+2/3*(x1-last.x()); qy1=last.y()+2/3*(y1-last.y())
                qx2=ex+2/3*(x1-ex);             qy2=ey+2/3*(y1-ey)
                if nodes: nodes[-1].cp_out=QPointF(qx1,qy1)
                n=VNode(QPointF(ex,ey),QPointF(qx2,qy2)); nodes.append(n)
                last=QPointF(ex,ey); last_cp=QPointF(x1,y1)
        elif cmd in('T','t'):
            while not is_cmd() and has_n(2):
                try: ex,ey=rf(),rf()
                except: break
                if cmd=='t': ex+=last.x(); ey+=last.y()
                if last_cp:
                    x1=2*last.x()-last_cp.x(); y1=2*last.y()-last_cp.y()
                else:
                    x1,y1=last.x(),last.y()
                if nodes: nodes[-1].cp_out=QPointF(x1,y1)
                n=VNode(QPointF(ex,ey)); nodes.append(n)
                last=QPointF(ex,ey); last_cp=QPointF(x1,y1)
        elif cmd in('L','l'):
            while not is_cmd() and has_n(2):
                try: x,y=rf(),rf()
                except: break
                if cmd=='l': x+=last.x(); y+=last.y()
                n=VNode(QPointF(x,y)); nodes.append(n); last=QPointF(x,y); last_cp=None
        elif cmd in('H','h'):
            while not is_cmd() and has_n(1):
                try: x=rf()
                except: break
                if cmd=='h': x+=last.x()
                n=VNode(QPointF(x,last.y())); nodes.append(n); last=QPointF(x,last.y()); last_cp=None
        elif cmd in('V','v'):
            while not is_cmd() and has_n(1):
                try: y=rf()
                except: break
                if cmd=='v': y+=last.y()
                n=VNode(QPointF(last.x(),y)); nodes.append(n); last=QPointF(last.x(),y); last_cp=None
        elif cmd in('A','a'):
            # 楕円弧 → 直線近似
            while not is_cmd() and has_n(7):
                try: rx,ry,rot,laf,sf,ex,ey=rf(),rf(),rf(),rf(),rf(),rf(),rf()
                except: break
                if cmd=='a': ex+=last.x(); ey+=last.y()
                n=VNode(QPointF(ex,ey)); nodes.append(n); last=QPointF(ex,ey); last_cp=None
        elif cmd in('Z','z'):
            vp.closed=True
    if not nodes: return None
    vp.nodes=nodes
    s=attrs.get("stroke","none")
    vp.stroke_color=QColor(s) if s not in("none","") else QColor(Qt.transparent)
    try: vp.stroke_width=float(attrs.get("stroke-width","2"))
    except: vp.stroke_width=2.0
    f=attrs.get("fill","none")
    vp.fill_color=QColor(f) if f not in("none","") else QColor(Qt.transparent)
    try: vp.opacity=float(attrs.get("opacity","1"))
    except: vp.opacity=1.0
    vp.brush_name=attrs.get("data-brush","Gペン")
    vp.visible=attrs.get("display","")!="none"
    vp.tone_type=attrs.get("data-tone",TONE_NONE)
    try: vp.tone_freq=float(attrs.get("data-tone-freq","20"))
    except: pass
    try: vp.tone_size=float(attrs.get("data-tone-size","3"))
    except: pass
    if attrs.get("data-grad")=="1":
        vp.gradient_enabled=True
        vp.gradient_start=QColor(attrs.get("data-grad-start","#5B8CFF"))
        vp.gradient_end=QColor(attrs.get("data-grad-end","#A78BFA"))
        try: vp.gradient_angle=float(attrs.get("data-grad-angle","0"))
        except: pass
    try:
        m=attrs.get("data-meta","")
        if m: vp.meta=json.loads(m)
    except: pass
    return vp

# ══════════════════════════════════════════════════════════════
#  ブラシエンジン
# ══════════════════════════════════════════════════════════════
def apply_brush_stroke(painter: QPainter, vp: VPath, brush_defs: Dict):
    if len(vp.nodes)<2:
        pen=QPen(vp.stroke_color,vp.stroke_width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawPath(vp.to_qpath()); return
    bdef=brush_defs.get(vp.brush_name,brush_defs.get("Gペン",DEFAULT_BRUSHES["Gペン"]))
    if vp.gradient_enabled:
        _draw_gradient_stroke(painter,vp); return
    if not bdef.get("pressure_width",True) or not vp.pressure:
        pen=QPen(vp.stroke_color,vp.stroke_width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawPath(vp.to_qpath()); return
    # 筆圧対応 (セグメントごと)
    n=len(vp.nodes); pres=vp.pressure if len(vp.pressure)==n else [1.0]*n
    taper=bdef.get("taper",0.0)
    for i in range(n-1):
        a,b=vp.nodes[i],vp.nodes[i+1]
        tp=min(i/(max(n*taper,1)),1.0)*(1-min((n-1-i)/(max(n*taper,1)),1.0)) if taper>0 else 1.0
        w=vp.stroke_width*((pres[i]+pres[i+1])/2)*tp
        pen=QPen(vp.stroke_color,max(0.3,w),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)
        seg=QPainterPath(); seg.moveTo(a.pos); seg.cubicTo(a.cp_out,b.cp_in,b.pos)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawPath(seg)

def _draw_gradient_stroke(painter: QPainter, vp: VPath):
    br=vp.bounding_rect()
    if br.isNull(): return
    cx,cy=br.center().x(),br.center().y()
    angle=math.radians(vp.gradient_angle)
    hw,hh=br.width()/2,br.height()/2
    grad=QLinearGradient(
        QPointF(cx-math.cos(angle)*hw,cy-math.sin(angle)*hh),
        QPointF(cx+math.cos(angle)*hw,cy+math.sin(angle)*hh)
    )
    grad.setColorAt(0,vp.gradient_start); grad.setColorAt(1,vp.gradient_end)
    pen=QPen(QBrush(grad),vp.stroke_width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)
    painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawPath(vp.to_qpath())

def draw_tone(painter: QPainter, vp: VPath):
    """ベクタートーン描画"""
    if vp.tone_type==TONE_NONE: return
    br=vp.bounding_rect()
    if br.isNull(): return
    clip=vp.to_qpath(); painter.save(); painter.setClipPath(clip)
    freq=max(1,vp.tone_freq); sz=max(0.5,vp.tone_size)
    c=QColor(vp.stroke_color); c.setAlpha(180)
    pen=QPen(c,sz*0.5,Qt.SolidLine,Qt.RoundCap); painter.setPen(pen)
    if vp.tone_type==TONE_DOT:
        painter.setBrush(QBrush(c))
        x=br.left()
        row=0
        while x<br.right()+freq:
            y=br.top()+(row%2)*(freq/2)
            while y<br.bottom()+freq:
                painter.drawEllipse(QPointF(x,y),sz/2,sz/2); y+=freq
            x+=freq; row+=1
    elif vp.tone_type==TONE_LINE:
        painter.setBrush(Qt.NoBrush)
        y=br.top()
        while y<br.bottom()+freq:
            painter.drawLine(QPointF(br.left(),y),QPointF(br.right(),y)); y+=freq
    elif vp.tone_type==TONE_CROSS:
        painter.setBrush(Qt.NoBrush)
        y=br.top()
        while y<br.bottom()+freq:
            painter.drawLine(QPointF(br.left(),y),QPointF(br.right(),y)); y+=freq
        x=br.left()
        while x<br.right()+freq:
            painter.drawLine(QPointF(x,br.top()),QPointF(x,br.bottom())); x+=freq
    painter.restore()

# ══════════════════════════════════════════════════════════════
#  ベクター塗り完全版 (隙間検知)
# ══════════════════════════════════════════════════════════════
def vector_bucket_fill(doc: Document, pt: QPointF, fill_color: QColor) -> List[Tuple]:
    """
    完全版ベクターバケツ塗り:
    1. クリック点を含む最小の閉パスを探す
    2. 閉パスなし → 近傍の開パスから輪郭を推定して閉鎖
    3. 既存パスに塗りを設定
    戻り値: [(cmd_type, data), ...] コマンドリスト
    """
    results = []
    candidates_closed = []
    candidates_open   = []
    for layer, vp in doc.all_paths():
        if not layer.visible or layer.locked: continue
        br=vp.bounding_rect()
        if not br.contains(pt): continue
        if vp.closed and vp.to_qpath().contains(pt):
            candidates_closed.append((layer,vp))
        elif not vp.closed:
            candidates_open.append((layer,vp))

    if candidates_closed:
        best_l,best_vp=min(candidates_closed,
            key=lambda x: x[1].bounding_rect().width()*x[1].bounding_rect().height())
        old_c=QColor(best_vp.fill_color)
        best_vp.fill_color=QColor(fill_color)
        results.append(("set_fill",(best_l,best_vp,old_c,QColor(fill_color))))
        return results

    # 閉パスなし: 近傍の開パスの端点を接続して閉鎖パスを生成
    if candidates_open:
        # 端点接続アルゴリズム:
        #   1. 各開パスの始点・終点を収集
        #   2. 最近傍の端点ペアを貪欲法で接続
        #   3. 繋がったチェーンを閉じる
        chains=_connect_open_paths(candidates_open)
        for chain_pts in chains:
            if len(chain_pts)<3: continue
            new_vp=VPath()
            for i,p in enumerate(chain_pts):
                n=VNode(p)
                # 簡易CP: 前後点からタンジェントを設定
                if 0<i<len(chain_pts)-1:
                    prev=chain_pts[i-1]; nxt=chain_pts[i+1]
                    dx=nxt.x()-prev.x(); dy=nxt.y()-prev.y()
                    seg=math.hypot(dx,dy)
                    if seg>0.001:
                        ux,uy=dx/seg,dy/seg; cl=seg*0.25
                        n.cp_in =QPointF(p.x()-ux*cl,p.y()-uy*cl)
                        n.cp_out=QPointF(p.x()+ux*cl,p.y()+uy*cl)
                new_vp.nodes.append(n)
            new_vp.closed=True
            new_vp.fill_color=QColor(fill_color)
            new_vp.stroke_color=QColor(Qt.transparent)
            results.append(("add_path",(doc.active_layer,new_vp)))
    return results

def _connect_open_paths(pairs: List[Tuple]) -> List[List[QPointF]]:
    """
    開パス群の端点を貪欲法で最近傍接続し、閉じたポリラインのリストを返す。
    pairs: [(layer, VPath), ...]
    """
    # 各パスの点列を収集（始点が前・終点が後）
    segs=[]
    for _,vp in pairs:
        if len(vp.nodes)<2: continue
        pts=[n.pos for n in vp.nodes]
        segs.append(pts)
    if not segs: return []
    # 連結リストを構築
    chains=[]
    used=[False]*len(segs)
    for start_i in range(len(segs)):
        if used[start_i]: continue
        chain=list(segs[start_i]); used[start_i]=True
        changed=True
        while changed:
            changed=False
            best_j,best_dist,best_mode=-1,float('inf'),None
            for j in range(len(segs)):
                if used[j]: continue
                pts=segs[j]
                for mode,ep in [('fwd_start',chain[-1]),('rev_start',chain[-1]),
                                 ('fwd_end',chain[0]), ('rev_end',chain[0])]:
                    cand=pts[0] if 'start' in mode else pts[-1]
                    d=math.hypot(cand.x()-ep.x(),cand.y()-ep.y())
                    if d<best_dist: best_dist=d; best_j=j; best_mode=mode
            if best_j>=0 and best_dist<200:  # 200px 以内なら接続
                pts=segs[best_j]; used[best_j]=True
                if best_mode=='fwd_start':   chain.extend(pts)
                elif best_mode=='rev_start': chain.extend(reversed(pts))
                elif best_mode=='fwd_end':   chain=list(pts)+chain
                elif best_mode=='rev_end':   chain=list(reversed(pts))+chain
                changed=True
        chains.append(chain)
    return chains

def _convex_hull(pts: List[QPointF]) -> List[QPointF]:
    """Grahamスキャンによる凸包"""
    if len(pts)<3: return pts
    def cross(o,a,b): return (a.x()-o.x())*(b.y()-o.y())-(a.y()-o.y())*(b.x()-o.x())
    pts=sorted(pts,key=lambda p:(p.x(),p.y())); hull=[]
    for p in pts:
        while len(hull)>=2 and cross(hull[-2],hull[-1],p)<=0: hull.pop()
        hull.append(p)
    lower=len(hull)
    for p in reversed(pts):
        while len(hull)>lower and cross(hull[-2],hull[-1],p)<=0: hull.pop()
        hull.append(p)
    return hull[:-1]

# ══════════════════════════════════════════════════════════════
#  漫画ツール生成関数
# ══════════════════════════════════════════════════════════════
def make_balloon(center: QPointF, rx: float, ry: float,
                 btype: str, tail_pt: Optional[QPointF]=None) -> VPath:
    """フキダシVPath生成"""
    vp=VPath()
    vp.stroke_color=QColor("#000000"); vp.stroke_width=2.0
    vp.fill_color=QColor("#FFFFFF"); vp.closed=True
    vp.meta={"type":"balloon","btype":btype}
    N=32
    if btype==BALLOON_ELLIPSE:
        for i in range(N):
            angle=2*math.pi*i/N
            p=QPointF(center.x()+math.cos(angle)*rx, center.y()+math.sin(angle)*ry)
            node=VNode(p)
            # スムーズハンドル
            da=2*math.pi/N
            tang_x=-math.sin(angle)*rx*(4/3)*math.tan(da/4)
            tang_y= math.cos(angle)*ry*(4/3)*math.tan(da/4)
            node.cp_out=QPointF(p.x()-tang_x, p.y()-tang_y)
            node.cp_in =QPointF(p.x()+tang_x, p.y()+tang_y)
            vp.nodes.append(node)
    elif btype==BALLOON_RECT:
        corners=[QPointF(center.x()-rx,center.y()-ry),
                 QPointF(center.x()+rx,center.y()-ry),
                 QPointF(center.x()+rx,center.y()+ry),
                 QPointF(center.x()-rx,center.y()+ry)]
        r=min(rx,ry)*0.15  # 角丸
        for j,c in enumerate(corners):
            nxt=corners[(j+1)%4]; prv=corners[(j-1)%4]
            dx_n=(nxt.x()-c.x()); dy_n=(nxt.y()-c.y()); ln=math.hypot(dx_n,dy_n)
            dx_p=(prv.x()-c.x()); dy_p=(prv.y()-c.y())
            p1=QPointF(c.x()+dx_p/ln*r if ln>0 else c.x(), c.y()+dy_p/ln*r if ln>0 else c.y())
            p2=QPointF(c.x()+dx_n/ln*r if ln>0 else c.x(), c.y()+dy_n/ln*r if ln>0 else c.y())
            vp.nodes.append(VNode(p1)); vp.nodes.append(VNode(p2))
    elif btype==BALLOON_CLOUD:
        bumps=8
        for i in range(N):
            angle=2*math.pi*i/N
            bump=math.sin(bumps*angle)*0.15
            r_eff=1.0+bump
            p=QPointF(center.x()+math.cos(angle)*rx*r_eff, center.y()+math.sin(angle)*ry*r_eff)
            vp.nodes.append(VNode(p))
    elif btype==BALLOON_SPIKY:
        spikes=12
        for i in range(spikes*2):
            angle=2*math.pi*i/(spikes*2)
            r_eff=rx if i%2==0 else rx*0.7
            ry_eff=ry if i%2==0 else ry*0.7
            p=QPointF(center.x()+math.cos(angle)*r_eff, center.y()+math.sin(angle)*ry_eff)
            vp.nodes.append(VNode(p))
    # しっぽ追加
    if tail_pt and vp.nodes:
        mid_idx=len(vp.nodes)//2
        t1=VNode(_lerp(vp.nodes[mid_idx].pos, tail_pt, 0.3)+QPointF(-10,0))
        t2=VNode(tail_pt)
        t3=VNode(_lerp(vp.nodes[mid_idx].pos, tail_pt, 0.3)+QPointF(10,0))
        vp.nodes.insert(mid_idx+1,t1); vp.nodes.insert(mid_idx+2,t2); vp.nodes.insert(mid_idx+3,t3)
    return vp

def make_panel(rect: QRectF, border_w: float=3.0) -> VPath:
    """コマ割りVPath生成"""
    vp=VPath()
    vp.stroke_color=QColor("#000000"); vp.stroke_width=border_w
    vp.fill_color=QColor(Qt.transparent); vp.closed=True
    vp.meta={"type":"panel"}
    pts=[rect.topLeft(),rect.topRight(),rect.bottomRight(),rect.bottomLeft()]
    for p in pts: vp.nodes.append(VNode(p))
    return vp

def _seg_intersect(p1:QPointF,p2:QPointF,p3:QPointF,p4:QPointF):
    """線分(p1-p2)と線分(p3-p4)の交点を返す (なければNone)"""
    d1=QPointF(p2.x()-p1.x(),p2.y()-p1.y())
    d2=QPointF(p4.x()-p3.x(),p4.y()-p3.y())
    cross=d1.x()*d2.y()-d1.y()*d2.x()
    if abs(cross)<1e-10: return None
    dx=p3.x()-p1.x(); dy=p3.y()-p1.y()
    t=(dx*d2.y()-dy*d2.x())/cross
    u=(dx*d1.y()-dy*d1.x())/cross
    if 0<=t<=1 and 0<=u<=1:
        return QPointF(p1.x()+t*d1.x(),p1.y()+t*d1.y())
    return None

def split_panel_by_line(panel_vp: VPath, line_start: QPointF, line_end: QPointF,
                         border_w: float=3.0) -> List[VPath]:
    """
    矩形コマ(panel_vp)をドラッグ線で2分割し、新しい2つのコマVPathを返す。
    分割できない場合は空リストを返す。
    """
    if panel_vp.meta.get("type")!="panel" or len(panel_vp.nodes)<4:
        return []
    nodes=panel_vp.nodes
    n=len(nodes)
    # コマの辺との交点を全て求める
    hits=[]
    for i in range(n):
        a=nodes[i].pos; b=nodes[(i+1)%n].pos
        pt=_seg_intersect(line_start,line_end,a,b)
        if pt is not None: hits.append((i,pt))
    if len(hits)<2: return []
    # 交点が2つの場合: コマを2分割
    hits.sort(key=lambda x:x[0])
    i0,p0=hits[0]; i1,p1=hits[1]
    # サイド1: nodes[0..i0] + p0 + p1 + nodes[i1+1..n]
    def make_sub(pts):
        vp=VPath(); vp.stroke_color=QColor("#000000"); vp.stroke_width=border_w
        vp.fill_color=QColor(Qt.transparent); vp.closed=True; vp.meta={"type":"panel"}
        for p in pts: vp.nodes.append(VNode(p))
        return vp
    side1=[nodes[j].pos for j in range(i0+1)]+[p0,p1]+[nodes[j].pos for j in range(i1+1,n)]
    side2=[p0]+[nodes[j].pos for j in range(i0+1,i1+1)]+[p1]
    result=[]
    if len(side1)>=3: result.append(make_sub(side1))
    if len(side2)>=3: result.append(make_sub(side2))
    return result

def make_focus_lines(center: QPointF, outer_r: float, inner_r: float,
                     count: int=64,
                     stroke_color: QColor=None, stroke_width: float=1.0) -> List['VPath']:
    """
    集中線を独立した VPath のリストとして生成。
    Fix5: 未使用の jitter 引数を除去。
    角度・内径・外径・太さにランダム変化を加えて自然な集中線を生成。
    """
    import random; rng=random.Random(42)
    if stroke_color is None: stroke_color=QColor("#000000")
    paths=[]
    # 各線の角度ゆらぎ・内径ゆらぎ・外径ゆらぎを引数から自動導出
    angle_jitter=0.05           # rad
    inner_jitter=inner_r*0.2   # 内径のゆらぎ幅
    outer_jitter=0.01           # rad (外側の角度ゆらぎ)
    for i in range(count):
        angle=2*math.pi*i/count+rng.uniform(-angle_jitter,angle_jitter)
        ix=center.x()+math.cos(angle)*(inner_r+rng.uniform(0,inner_jitter))
        iy=center.y()+math.sin(angle)*(inner_r+rng.uniform(0,inner_jitter))
        ox=center.x()+math.cos(angle+rng.uniform(-outer_jitter,outer_jitter))*outer_r
        oy=center.y()+math.sin(angle+rng.uniform(-outer_jitter,outer_jitter))*outer_r
        w=stroke_width*(0.5+rng.uniform(0,1.0))  # 太さに奥行き感
        vp=VPath()
        vp.stroke_color=QColor(stroke_color); vp.stroke_width=w
        vp.fill_color=QColor(Qt.transparent)
        n1=VNode(QPointF(ix,iy)); n2=VNode(QPointF(ox,oy))
        n1.cp_out=QPointF(n1.pos); n2.cp_in=QPointF(n2.pos)
        vp.nodes=[n1,n2]; vp.meta={"type":"focus_line_single"}
        paths.append(vp)
    return paths

def make_speed_lines(rect: QRectF, direction: str="right",
                     count: int=20, density: float=0.7) -> List[VPath]:
    """効果線(スピード線)生成"""
    import random; rng=random.Random(0)
    paths=[]
    for i in range(count):
        if direction in("right","left"):
            y=rect.top()+rng.uniform(0,rect.height())
            x_start=rect.left() if direction=="right" else rect.right()
            x_end=rect.right() if direction=="right" else rect.left()
            gap=rng.uniform(0,rect.height()*0.02)
            vp=VPath(); vp.stroke_color=QColor("#000000")
            vp.stroke_width=rng.uniform(0.5,2.0)
            n1=VNode(QPointF(x_start,y-gap)); n2=VNode(QPointF(x_end,y+gap))
            vp.nodes=[n1,n2]; vp.meta={"type":"speed_line"}
            paths.append(vp)
        else:  # up/down
            x=rect.left()+rng.uniform(0,rect.width())
            y_start=rect.top() if direction=="down" else rect.bottom()
            y_end=rect.bottom() if direction=="down" else rect.top()
            gap=rng.uniform(0,rect.width()*0.02)
            vp=VPath(); vp.stroke_color=QColor("#000000")
            vp.stroke_width=rng.uniform(0.5,2.0)
            n1=VNode(QPointF(x-gap,y_start)); n2=VNode(QPointF(x+gap,y_end))
            vp.nodes=[n1,n2]; vp.meta={"type":"speed_line"}
            paths.append(vp)
    return paths

# ══════════════════════════════════════════════════════════════
#  パース定規
# ══════════════════════════════════════════════════════════════
def get_persp_snap(doc: Document, pt: QPointF, snap_radius: float=20.0) -> QPointF:
    """
    透視グリッドに沿った点スナップ。
    消失点から伸びる最近傍のガイド線上に pt を射影する。
    Fix4: 距離計算を chord長(不正)→ dist*sin(Δangle)(正確な垂直距離) に修正。
    snap_radius はスクリーン距離と同単位のドキュメント座標。
    """
    if doc.perspective==PERSP_NONE: return pt
    def snap_to_vp(vp_pt: QPointF, guide_step_deg: float=15.0) -> Tuple[QPointF,float]:
        """
        消失点 vp_pt から pt の角度を最近傍のガイド角に丸め、
        そのガイド線上で pt に最も近い点を返す。
        垂直距離 = dist_to_vp * |sin(Δangle)| (正確な弦の高さ)。
        """
        dx=pt.x()-vp_pt.x(); dy=pt.y()-vp_pt.y()
        dist_to_vp=math.hypot(dx,dy)
        if dist_to_vp<0.001: return (QPointF(pt),float('inf'))
        angle_rad=math.atan2(dy,dx)
        step_rad=math.radians(guide_step_deg)
        snapped_angle=round(angle_rad/step_rad)*step_rad
        delta_angle=angle_rad-snapped_angle
        # Fix4: 正確な垂直距離 = dist * |sin(Δangle)|
        perp_dist=dist_to_vp*abs(math.sin(delta_angle))
        # 射影点: 消失点から snapped_angle 方向に dist_to_vp
        sx=vp_pt.x()+math.cos(snapped_angle)*dist_to_vp
        sy=vp_pt.y()+math.sin(snapped_angle)*dist_to_vp
        return (QPointF(sx,sy), perp_dist)
    best_pt=pt; best_dist=snap_radius
    for vp_pt in ([doc.persp_vp1] + ([doc.persp_vp2] if doc.perspective==PERSP_2PT else [])):
        sp,d=snap_to_vp(vp_pt)
        if d<best_dist: best_dist=d; best_pt=sp
    return best_pt

# ══════════════════════════════════════════════════════════════
#  画像書き出し
# ══════════════════════════════════════════════════════════════
def render_to_image(doc: Document, scale: float=1.0, brush_defs: Dict=None) -> QImage:
    """ドキュメントをQImageにレンダリング"""
    if brush_defs is None: brush_defs=DEFAULT_BRUSHES
    w=int(doc.width*scale); h=int(doc.height*scale)
    img=QImage(w,h,QImage.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    painter=QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(scale,scale)
    for layer in doc.layers:
        if not layer.visible: continue
        painter.setOpacity(layer.opacity)
        mode=BLEND_MAP.get(layer.blend,QPainter.CompositionMode_SourceOver)
        painter.setCompositionMode(mode)
        for item in layer.items:
            if isinstance(item,VPath):
                _render_path(painter,item,brush_defs)
            elif isinstance(item,VGroup):
                painter.setOpacity(layer.opacity*item.opacity)
                for vp in item.items: _render_path(painter,vp,brush_defs)
                painter.setOpacity(layer.opacity)
        painter.setOpacity(1.0)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    painter.end()
    return img

def _render_path(painter: QPainter, vp: VPath, brush_defs: Dict):
    if not vp.visible: return
    painter.setOpacity(vp.opacity)
    # 集中線/効果線の単一線分は drawLine で直接描画（Bug2修正: PNG書き出し対応）
    if vp.meta.get("type") in ("focus_line_single","speed_line") and len(vp.nodes)==2:
        pen=QPen(vp.stroke_color,vp.stroke_width,Qt.SolidLine,Qt.FlatCap)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush)
        painter.drawLine(vp.nodes[0].pos,vp.nodes[1].pos)
        painter.setOpacity(1.0); return
    qpath=vp.to_qpath()
    if vp.fill_color.alpha()>0:
        painter.fillPath(qpath,QBrush(vp.fill_color))
    apply_brush_stroke(painter,vp,brush_defs)
    draw_tone(painter,vp)
    painter.setOpacity(1.0)

# ══════════════════════════════════════════════════════════════
#  キャンバス
# ══════════════════════════════════════════════════════════════
class Canvas(QWidget):
    status_changed    = Signal(str)
    selection_changed = Signal(list)
    document_changed  = Signal()

    def __init__(self,doc:Document,undo:QUndoStack):
        super().__init__()
        self.doc=doc; self.undo=undo
        self.setMouseTracking(True); self.setFocusPolicy(Qt.StrongFocus)
        # ビュー
        self._scale=1.0; self._offset=QPointF(40,40)
        self._pan_start=None; self._pan_off=None
        # ツール
        self.tool=TOOL_PEN
        self.pen_color=QColor(C["stroke_def"]); self.pen_width=2.0
        self.fill_color=QColor(Qt.transparent); self.brush_name="Gペン"
        self.smoothing=0.3   # 手ブレ補正強度
        # 選択
        self.selected:List[VPath]=[]
        self._rubber_start:Optional[QPointF]=None; self._rubber_rect:Optional[QRectF]=None
        # Reshape
        self.sel_node:Optional[VNode]=None; self.sel_cp=None
        self._node_before=None; self._drag_start:Optional[QPointF]=None
        self._drag_snaps={}
        # ペン
        self._pen_path:Optional[VPath]=None; self._pen_drawing=False
        self._pen_sym_paths:List[VPath]=[]
        self._raw_pts:List[QPointF]=[]   # 生ストローク点列 (手ブレ補正用)
        # BB変形
        self._bb_handle=None; self._bb_before={}; self._bb_start_pt=None
        self._bb_start_rect=None; self._bb_start_angle=0.0; self._bb_rot_c=None
        # 漫画ツール
        self._balloon_start:Optional[QPointF]=None
        self._panel_start:Optional[QPointF]=None
        self._focus_center:Optional[QPointF]=None
        # ホバー
        self._hover_node=None; self._hover_path=None
        # 線幅
        self._width_old=2.0
        # スタイラス筆圧
        self._tablet_pressure=1.0   # 現在の筆圧 (0.0-1.0)
        self._is_tablet=False       # タブレットデバイス使用中フラグ
        self.setAttribute(Qt.WA_TabletTracking, True)
        self.setMinimumSize(400,300)

    def to_doc(self,p): return QPointF((p.x()-self._offset.x())/self._scale,(p.y()-self._offset.y())/self._scale)
    def to_scr(self,p): return QPointF(p.x()*self._scale+self._offset.x(),p.y()*self._scale+self._offset.y())

    def set_tool(self,t):
        self.tool=t
        cur={TOOL_PEN:Qt.CrossCursor,TOOL_RESHAPE:Qt.ArrowCursor,TOOL_SELECT:Qt.ArrowCursor,
             TOOL_HAND:Qt.OpenHandCursor,TOOL_ERASER:Qt.CrossCursor,
             TOOL_ADD_NODE:Qt.CrossCursor,TOOL_DEL_NODE:Qt.CrossCursor,
             TOOL_WIDTH:Qt.SizeHorCursor,TOOL_BUCKET:Qt.CrossCursor,
             TOOL_SCISSORS:Qt.CrossCursor,TOOL_BALLOON:Qt.CrossCursor,
             TOOL_PANEL:Qt.CrossCursor,TOOL_FOCUS_LINE:Qt.CrossCursor,
             TOOL_SPEED_LINE:Qt.CrossCursor}.get(t,Qt.ArrowCursor)
        self.setCursor(cur)
        if t not in(TOOL_RESHAPE,TOOL_SELECT):
            self.selected=[]; self.sel_node=None; self.selection_changed.emit([])
        self._pen_path=None; self._pen_drawing=False; self._pen_sym_paths=[]; self._raw_pts=[]
        self.update()

    # ─── Paint ───
    def paintEvent(self,ev):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor(C["bg"]))
        self._draw_grid(p)
        p.save(); p.translate(self._offset); p.scale(self._scale,self._scale)
        # キャンバス
        p.fillRect(QRectF(4,4,self.doc.width+4,self.doc.height+4),QColor(0,0,0,60))
        p.fillRect(QRectF(0,0,self.doc.width,self.doc.height),QColor(C["canvas_bg"]))
        # Webtoonストリップガイド
        if self.doc.webtoon_mode: self._draw_webtoon_guide(p)
        # シンメトリーガイド
        self._draw_sym_guide(p)
        # パース定規ガイド
        self._draw_persp_guide(p)
        # レイヤー
        for layer in self.doc.layers:
            if not layer.visible: continue
            p.setOpacity(layer.opacity)
            mode=BLEND_MAP.get(layer.blend,QPainter.CompositionMode_SourceOver)
            p.setCompositionMode(mode)
            for item in layer.items:
                if isinstance(item,VPath): self._draw_path(p,item)
                elif isinstance(item,VGroup):
                    p.setOpacity(layer.opacity*item.opacity)
                    for vp in item.items: self._draw_path(p,vp)
                    p.setOpacity(layer.opacity)
            p.setOpacity(1.0); p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        # プレビュー
        if self._pen_path and self._pen_drawing:
            self._draw_path(p,self._pen_path,preview=True)
            for sp in self._pen_sym_paths: self._draw_path(p,sp,preview=True,sym=True)
        if self._balloon_start:
            self._draw_balloon_preview(p)
        if self._panel_start:
            self._draw_panel_preview(p)
        p.restore()
        # Reshape overlay
        if self.tool in(TOOL_RESHAPE,TOOL_ADD_NODE,TOOL_DEL_NODE):
            self._draw_reshape_overlay(p)
        # BB
        if self.tool==TOOL_SELECT and self.selected:
            self._draw_bounding_box(p)
        # ラバーバンド
        if self._rubber_rect:
            p.setPen(QPen(QColor(C["accent"]),1,Qt.DashLine))
            p.setBrush(QColor(C["accent"]+"22"))
            p.drawRect(self._rubber_rect)
        # 効果線ドラッグプレビュー（方向矢印）Fix2
        if (self.tool==TOOL_SPEED_LINE and hasattr(self,"_speed_start")
                and self._speed_start and hasattr(self,"_speed_cur")):
            self._draw_speed_preview(p)

    def _draw_grid(self,p):
        step=40*self._scale
        if step<8: return
        p.setPen(QPen(QColor(C["canvas_grid"]),0.5))
        w,h=self.width(),self.height()
        ox=self._offset.x()%step; oy=self._offset.y()%step
        x=ox
        while x<w: p.drawLine(QPointF(x,0),QPointF(x,h)); x+=step
        y=oy
        while y<h: p.drawLine(QPointF(0,y),QPointF(w,y)); y+=step

    def _draw_webtoon_guide(self,p):
        sh=self.doc.webtoon_strip_height
        p.setPen(QPen(QColor(C["accent"]+"44"),1/self._scale,Qt.DashLine))
        y=0
        while y<self.doc.height:
            p.drawLine(QPointF(0,y),QPointF(self.doc.width,y)); y+=sh

    def _draw_sym_guide(self,p):
        sym=self.doc.symmetry
        if sym==SYM_NONE: return
        pen=QPen(QColor(C["sym_line"]),1/self._scale,Qt.DashLine); p.setPen(pen)
        cx,cy=self.doc.sym_cx,self.doc.sym_cy; W,H=self.doc.width,self.doc.height
        if sym in(SYM_H,SYM_CROSS): p.drawLine(QPointF(cx,0),QPointF(cx,H))
        if sym in(SYM_V,SYM_CROSS): p.drawLine(QPointF(0,cy),QPointF(W,cy))

    def _draw_persp_guide(self,p):
        if self.doc.perspective==PERSP_NONE: return
        pen=QPen(QColor(C["persp_line"]),0.8/self._scale,Qt.DashLine); p.setPen(pen)
        vp1=self.doc.persp_vp1; W,H=self.doc.width,self.doc.height
        # 消失点1からのガイド線
        for angle_step in range(0,360,15):
            angle=math.radians(angle_step)
            ex=vp1.x()+math.cos(angle)*max(W,H)*2
            ey=vp1.y()+math.sin(angle)*max(W,H)*2
            p.drawLine(vp1,QPointF(ex,ey))
        # 消失点1 マーカー
        p.setPen(QPen(QColor(C["warn"]),2/self._scale))
        p.setBrush(QBrush(QColor(C["warn"]))); r=6/self._scale
        p.drawEllipse(QRectF(vp1.x()-r,vp1.y()-r,r*2,r*2))
        if self.doc.perspective==PERSP_2PT:
            vp2=self.doc.persp_vp2
            p.setPen(QPen(QColor(C["persp_line"]),0.8/self._scale,Qt.DashLine))
            for angle_step in range(0,360,15):
                angle=math.radians(angle_step)
                ex=vp2.x()+math.cos(angle)*max(W,H)*2
                ey=vp2.y()+math.sin(angle)*max(W,H)*2
                p.drawLine(vp2,QPointF(ex,ey))
            p.setPen(QPen(QColor(C["accent2"]),2/self._scale))
            p.setBrush(QBrush(QColor(C["accent2"])))
            p.drawEllipse(QRectF(vp2.x()-r,vp2.y()-r,r*2,r*2))

    def _draw_path(self,p,vp:VPath,preview=False,sym=False):
        if not vp.visible: return
        p.setOpacity(vp.opacity)
        # 集中線・効果線の単一線分はジグザグ防止のため drawLine で直接描画（Bug2修正）
        is_line_seg=(vp.meta.get("type") in ("focus_line_single","speed_line")
                     and len(vp.nodes)==2)
        if is_line_seg and not preview:
            pen=QPen(vp.stroke_color,vp.stroke_width,Qt.SolidLine,Qt.FlatCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawLine(vp.nodes[0].pos,vp.nodes[1].pos)
            if vp in self.selected:
                hi=QPen(QColor(C["accent"]),vp.stroke_width+2,Qt.SolidLine,Qt.FlatCap)
                p.setPen(hi); p.drawLine(vp.nodes[0].pos,vp.nodes[1].pos)
            p.setOpacity(1.0); return
        qpath=vp.to_qpath()
        if vp.fill_color.alpha()>0: p.fillPath(qpath,QBrush(vp.fill_color))
        # トーン
        if vp.tone_type!=TONE_NONE and not preview: draw_tone(p,vp)
        if not preview:
            apply_brush_stroke(p,vp,self.doc.brush_presets)
        else:
            c=QColor(C["accent2"] if sym else C["accent"]); c.setAlpha(160)
            p.setPen(QPen(c,vp.stroke_width,Qt.DashLine,Qt.RoundCap,Qt.RoundJoin))
            p.setBrush(Qt.NoBrush); p.drawPath(qpath)
        # 選択ハイライト
        if vp in self.selected and not preview:
            glow=QPen(QColor(C["accent"]+"30"),max(vp.stroke_width+10,14),Qt.SolidLine,Qt.RoundCap)
            p.setPen(glow); p.setBrush(Qt.NoBrush); p.drawPath(qpath)
            hi=QPen(QColor(C["accent"]),max(vp.stroke_width+2,3),Qt.SolidLine,Qt.RoundCap)
            p.setPen(hi); p.drawPath(qpath)
        p.setOpacity(1.0)

    def _draw_balloon_preview(self,p):
        if not hasattr(self,'_balloon_cur'): return
        c=QColor(C["accent"]); c.setAlpha(120)
        p.setPen(QPen(c,2,Qt.DashLine)); p.setBrush(QColor(C["accent"]+"22"))
        start=self._balloon_start; end=self._balloon_cur
        rx=abs(end.x()-start.x())/2; ry=abs(end.y()-start.y())/2
        cx=start.x(); cy=start.y()
        p.drawEllipse(QRectF(cx-rx,cy-ry,rx*2,ry*2))

    def _draw_panel_preview(self,p):
        if not hasattr(self,'_panel_cur'): return
        c=QColor(C["accent"]); c.setAlpha(120)
        p.setPen(QPen(c,3,Qt.DashLine)); p.setBrush(QColor(C["accent"]+"11"))
        start=self._panel_start; end=self._panel_cur
        p.drawRect(QRectF(start,end).normalized())

    def _draw_speed_preview(self,p):
        """Fix2: 効果線ドラッグ中の方向矢印プレビュー（スクリーン座標）"""
        start=self.to_scr(self._speed_start)
        end=self.to_scr(self._speed_cur) if hasattr(self,"_speed_cur") else start
        dx=end.x()-start.x(); dy=end.y()-start.y(); dist=math.hypot(dx,dy)
        if dist<3: return
        c=QColor(C["accent"]); c.setAlpha(200)
        # 方向ライン
        p.setPen(QPen(c,2,Qt.DashLine,Qt.RoundCap))
        p.drawLine(start,end)
        # 矢印ヘッド
        angle=math.atan2(dy,dx)
        ah=12
        p.setPen(QPen(c,2,Qt.SolidLine,Qt.RoundCap))
        for a_off in [2.5,-2.5]:
            ax=end.x()-math.cos(angle+a_off)*ah
            ay=end.y()-math.sin(angle+a_off)*ah
            p.drawLine(end,QPointF(ax,ay))
        # 方向ラベル (簡略化)
        if abs(dy)>abs(dx): lbl="↓" if dy>0 else "↑"
        else:               lbl="→" if dx>0 else "←"
        p.setPen(QPen(c,1)); p.setFont(QFont("monospace",14,QFont.Bold))
        p.drawText(QPointF(end.x()+10,end.y()-10), lbl)

    def _draw_reshape_overlay(self,p):
        if not self.selected: return
        vp=self.selected[0]; p.save()
        p.translate(self._offset); p.scale(self._scale,self._scale)
        nr=5/self._scale; cr=4/self._scale
        for node in vp.nodes:
            is_sel=node is self.sel_node
            # CP handles
            for cp,which in[(node.cp_in,'in'),(node.cp_out,'out')]:
                if cp!=node.pos:
                    dash=QPen(QColor(C["fg_dim"]),0.8/self._scale,Qt.DotLine)
                    p.setPen(dash); p.drawLine(node.pos,cp)
                    is_cp_sel=self.sel_cp and self.sel_cp[0] is node and self.sel_cp[1]==which
                    cr2=cr*1.3 if is_cp_sel else cr
                    p.setBrush(QBrush(QColor(C["accent2"])))
                    p.setPen(QPen(QColor("white"),0.8/self._scale))
                    p.drawEllipse(QRectF(cp.x()-cr2,cp.y()-cr2,cr2*2,cr2*2))
            # アンカー
            is_hov=node is self._hover_node
            r=nr*(1.4 if is_sel else 1.1 if is_hov else 1.0)
            rect=QRectF(node.pos.x()-r,node.pos.y()-r,r*2,r*2)
            if self.tool==TOOL_DEL_NODE and is_hov: bc=C["danger"]
            elif is_sel: bc=C["node_sel"]
            elif is_hov: bc=C["accent"]
            else: bc=C["node_fill"]
            p.setBrush(QBrush(QColor(bc)))
            p.setPen(QPen(QColor("white"),1.0/self._scale))
            p.drawRect(rect)
        p.restore()

    def _draw_bounding_box(self,p):
        br=self._get_sel_rect()
        if br.isNull(): return
        tl=self.to_scr(br.topLeft()); br2=self.to_scr(br.bottomRight())
        rect=QRectF(tl,br2).adjusted(-4,-4,4,4)
        p.setPen(QPen(QColor(C["accent"]),1,Qt.DashLine))
        p.setBrush(Qt.NoBrush); p.drawRect(rect)
        hs=7
        for c2 in[rect.topLeft(),rect.topRight(),rect.bottomLeft(),rect.bottomRight()]:
            p.setBrush(QBrush(QColor(C["accent"]))); p.setPen(QPen(QColor("white"),1))
            p.drawRect(QRectF(c2.x()-hs/2,c2.y()-hs/2,hs,hs))
        rot=QPointF(rect.center().x(),rect.top()-20)
        p.setPen(QPen(QColor(C["accent"]),1))
        p.drawLine(QPointF(rect.center().x(),rect.top()),rot)
        p.setBrush(QBrush(QColor(C["accent2"]))); p.setPen(QPen(QColor("white"),1))
        p.drawEllipse(QRectF(rot.x()-5,rot.y()-5,10,10))

    # ─── ヒットテスト ───
    def _hit_paths(self,dp):
        r=6/self._scale
        for layer in reversed(self.doc.layers):
            if not layer.visible or layer.locked: continue
            for item in reversed(layer.items):
                if isinstance(item,VGroup):
                    for vp in reversed(item.items):
                        if vp.hit_test(dp,r): return vp
                elif isinstance(item,VPath):
                    if item.hit_test(dp,r): return item
        return None

    def _get_sel_rect(self):
        r=QRectF()
        for vp in self.selected: r=r.united(vp.bounding_rect())
        return r

    def _bb_handle_at(self,scr_pos):
        if not self.selected: return None
        br=self._get_sel_rect()
        tl=self.to_scr(br.topLeft()); br2=self.to_scr(br.bottomRight())
        rect=QRectF(tl,br2).adjusted(-4,-4,4,4)
        hs=10
        for nm,c2 in[('tl',rect.topLeft()),('tr',rect.topRight()),('bl',rect.bottomLeft()),('br',rect.bottomRight())]:
            if QRectF(c2.x()-hs/2,c2.y()-hs/2,hs,hs).contains(scr_pos): return nm
        rot=QPointF(rect.center().x(),rect.top()-20)
        if QLineF(rot,scr_pos).length()<8: return 'rot'
        return None

    def _snap_before(self):
        return {vp:[(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out)) for n in vp.nodes] for vp in self.selected}

    # ─── マウス ───
    def tabletEvent(self,ev):
        """スタイラス筆圧・傾き対応。筆圧を _tablet_pressure に記録しマウスイベントへ転送"""
        from PySide6.QtGui import QTabletEvent
        self._is_tablet=True
        self._tablet_pressure=max(0.0,min(1.0,ev.pressure()))
        # タブレットイベントをマウスイベントとして処理（ツール動作を共有）
        ev.accept()
        pos=ev.position()
        dp=self.to_doc(pos)
        from PySide6.QtCore import QEvent
        etype=ev.type()
        if etype==QEvent.TabletPress:
            if   self.tool==TOOL_PEN:      self._pen_press(dp)
            elif self.tool==TOOL_RESHAPE:  self._reshape_press(dp)
            elif self.tool==TOOL_SELECT:   self._select_press(pos,dp,ev.modifiers())
            elif self.tool==TOOL_ERASER:   self._eraser_press(dp)
            elif self.tool==TOOL_ADD_NODE: self._add_node_press(dp)
            elif self.tool==TOOL_DEL_NODE: self._del_node_press(dp)
            elif self.tool==TOOL_WIDTH:    self._width_press(dp)
            elif self.tool==TOOL_BUCKET:   self._bucket_press(dp)
            elif self.tool==TOOL_BALLOON:  self._balloon_press(dp)
            elif self.tool==TOOL_PANEL:    self._panel_press(dp)
            elif self.tool==TOOL_FOCUS_LINE: self._focus_press(dp)
            elif self.tool==TOOL_SPEED_LINE: self._speed_press(dp)
        elif etype==QEvent.TabletMove:
            if   self.tool==TOOL_PEN:
                dp_snap=get_persp_snap(self.doc,dp,snap_radius=20/self._scale)
                self._pen_drag(dp_snap)
            elif self.tool==TOOL_RESHAPE:  self._reshape_drag(dp)
            elif self.tool==TOOL_SELECT:   self._select_drag(pos,dp)
            elif self.tool==TOOL_WIDTH:    self._width_drag(dp)
            elif self.tool==TOOL_BALLOON:  self._balloon_drag(dp)
            elif self.tool==TOOL_PANEL:    self._panel_drag(dp)
            elif self.tool==TOOL_SPEED_LINE: self._speed_drag(dp)
            self._update_hover(dp)
        elif etype in(QEvent.TabletRelease,):
            if   self.tool==TOOL_PEN:        self._pen_release(dp)
            elif self.tool==TOOL_RESHAPE:    self._reshape_release(dp)
            elif self.tool==TOOL_SELECT:     self._select_release(dp)
            elif self.tool==TOOL_WIDTH:      self._width_release(dp)
            elif self.tool==TOOL_BALLOON:    self._balloon_release(dp)
            elif self.tool==TOOL_PANEL:      self._panel_release(dp)
            elif self.tool==TOOL_FOCUS_LINE: self._focus_release(dp)
            elif self.tool==TOOL_SPEED_LINE: self._speed_release(dp)

    def mousePressEvent(self,ev):
        pos=ev.position(); dp=self.to_doc(pos)
        if ev.button()==Qt.MiddleButton or (ev.button()==Qt.LeftButton and ev.modifiers()&Qt.AltModifier):
            self._pan_start=pos; self._pan_off=QPointF(self._offset); self.setCursor(Qt.ClosedHandCursor); return
        if ev.button()==Qt.LeftButton:
            m=ev.modifiers()
            if   self.tool==TOOL_PEN:       self._pen_press(dp)
            elif self.tool==TOOL_RESHAPE:   self._reshape_press(dp)
            elif self.tool==TOOL_SELECT:    self._select_press(pos,dp,m)
            elif self.tool==TOOL_ERASER:    self._eraser_press(dp)
            elif self.tool==TOOL_ADD_NODE:  self._add_node_press(dp)
            elif self.tool==TOOL_DEL_NODE:  self._del_node_press(dp)
            elif self.tool==TOOL_WIDTH:     self._width_press(dp)
            elif self.tool==TOOL_BUCKET:    self._bucket_press(dp)
            elif self.tool==TOOL_SCISSORS:  self._scissors_press(dp)
            elif self.tool==TOOL_BALLOON:   self._balloon_press(dp)
            elif self.tool==TOOL_PANEL:     self._panel_press(dp)
            elif self.tool==TOOL_FOCUS_LINE:self._focus_press(dp)
            elif self.tool==TOOL_SPEED_LINE:self._speed_press(dp)
        elif ev.button()==Qt.RightButton:
            self._show_context_menu(ev.globalPosition().toPoint())

    def mouseMoveEvent(self,ev):
        pos=ev.position(); dp=self.to_doc(pos)
        if self._pan_start:
            self._offset=self._pan_off+(pos-self._pan_start); self.update(); return
        if ev.buttons()&Qt.LeftButton:
            if   self.tool==TOOL_PEN:
                # Fix7: ドラッグ中のCPにもパーススナップを適用
                dp_snap=get_persp_snap(self.doc,dp,snap_radius=20/self._scale)
                self._pen_drag(dp_snap)
            elif self.tool==TOOL_RESHAPE:  self._reshape_drag(dp)
            elif self.tool==TOOL_SELECT:   self._select_drag(pos,dp)
            elif self.tool==TOOL_WIDTH:    self._width_drag(dp)
            elif self.tool==TOOL_BALLOON:  self._balloon_drag(dp)
            elif self.tool==TOOL_PANEL:    self._panel_drag(dp)
            elif self.tool==TOOL_SPEED_LINE: self._speed_drag(dp)  # Fix2: dispatch追加
        else:
            self._update_hover(dp)
        x,y=dp.x(),dp.y()
        self.status_changed.emit(f"  X:{x:.1f}  Y:{y:.1f}  |  ズーム:{self._scale*100:.0f}%")

    def mouseReleaseEvent(self,ev):
        if self._pan_start:
            self._pan_start=None
            self.setCursor(Qt.OpenHandCursor if self.tool==TOOL_HAND else Qt.ArrowCursor); return
        if ev.button()==Qt.LeftButton:
            dp=self.to_doc(ev.position())
            if   self.tool==TOOL_PEN:        self._pen_release(dp)
            elif self.tool==TOOL_RESHAPE:    self._reshape_release(dp)
            elif self.tool==TOOL_SELECT:     self._select_release(dp)
            elif self.tool==TOOL_WIDTH:      self._width_release(dp)
            elif self.tool==TOOL_BALLOON:    self._balloon_release(dp)
            elif self.tool==TOOL_PANEL:      self._panel_release(dp)
            elif self.tool==TOOL_FOCUS_LINE: self._focus_release(dp)
            elif self.tool==TOOL_SPEED_LINE: self._speed_release(dp)  # Bug3修正

    def mouseDoubleClickEvent(self,ev):
        if self.tool==TOOL_PEN: self._pen_finish()
        elif self.tool==TOOL_RESHAPE and self.selected:
            self.selected[0].closed=not self.selected[0].closed; self.update()

    def wheelEvent(self,ev):
        f=1.12 if ev.angleDelta().y()>0 else 1/1.12; pv=ev.position()
        self._offset=QPointF(pv.x()-(pv.x()-self._offset.x())*f,pv.y()-(pv.y()-self._offset.y())*f)
        self._scale=max(0.02,min(self._scale*f,64.0)); self.update()

    def keyPressEvent(self,ev):
        k=ev.key(); m=ev.modifiers()
        if k in(Qt.Key_Delete,Qt.Key_Backspace):
            self._delete_selected()  # バグ修正1
        elif k==Qt.Key_Escape:
            if self._pen_drawing: self._pen_finish()
            else:
                self.selected=[]; self.sel_node=None; self.selection_changed.emit([]); self.update()
        elif k==Qt.Key_G and m==Qt.ControlModifier:       self._group_selection()
        elif k==Qt.Key_G and m==(Qt.ControlModifier|Qt.ShiftModifier): self._ungroup_selection()
        elif k==Qt.Key_A and m==Qt.ControlModifier:       self._select_all()
        elif k in(Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down):
            step=10 if m&Qt.ShiftModifier else 1
            dx=(-step if k==Qt.Key_Left else step if k==Qt.Key_Right else 0)
            dy=(-step if k==Qt.Key_Up else step if k==Qt.Key_Down else 0)
            before=self._snap_before()
            for vp in self.selected:
                for n in vp.nodes:
                    n.pos+=QPointF(dx,dy); n.cp_in+=QPointF(dx,dy); n.cp_out+=QPointF(dx,dy)
            self.undo.push(CmdMovePaths(before,self._snap_before()))
            self.document_changed.emit(); self.update()

    def contextMenuEvent(self,ev):
        self._show_context_menu(ev.globalPos())

    def _show_context_menu(self,gpos):
        menu=QMenu(self)
        if self.selected:
            menu.addAction("グループ化  Ctrl+G",self._group_selection)
            if len(self.selected)==1:
                _,grp=self.doc.find_group_of(self.selected[0])
                if grp: menu.addAction("グループ解除  Ctrl+Shift+G",self._ungroup_selection)
            menu.addSeparator()
            menu.addAction("削除  Del",self._delete_selected)  # バグ修正1
            menu.addSeparator()
            menu.addAction("最前面へ  Ctrl+]",self._bring_to_front)
            menu.addAction("最背面へ  Ctrl+[",self._send_to_back)
            menu.addSeparator()
            menu.addAction("複製  Ctrl+D",self._duplicate_selected)
        else:
            menu.addAction("すべて選択  Ctrl+A",self._select_all)
        menu.exec(gpos)

    # ─── バグ修正1: 削除メソッドを独立 ───
    def _delete_selected(self):
        if self.sel_node and self.selected:
            vp=self.selected[0]
            if self.sel_node in vp.nodes:
                idx=vp.nodes.index(self.sel_node)
                self.undo.push(CmdDeleteNode(vp,self.sel_node,idx))
                self.sel_node=None; self.document_changed.emit(); self.update()
        elif self.selected:
            pairs=[]
            for vp in self.selected:
                layer,_=self.doc.find_path(vp.id)
                if layer: pairs.append((layer,vp))
            if pairs:
                self.undo.push(CmdDeletePaths(pairs))
                self.selected=[]; self.selection_changed.emit([])
                self.document_changed.emit(); self.update()

    # ─── ペン ───
    def _pen_press(self,dp):
        # パース定規スナップ適用
        dp=get_persp_snap(self.doc, dp, snap_radius=20/self._scale)
        if not self._pen_drawing:
            vp=VPath(); vp.stroke_color=QColor(self.pen_color)
            vp.stroke_width=self.pen_width; vp.fill_color=QColor(self.fill_color)
            vp.brush_name=self.brush_name; self._pen_path=vp; self._pen_drawing=True
            self._raw_pts=[dp]
            self._pen_sym_paths=[]
            for _ in sym_points(self.doc,dp):
                sp=VPath(); sp.stroke_color=QColor(self.pen_color)
                sp.stroke_color.setAlpha(140); sp.stroke_width=self.pen_width
                sp.brush_name=self.brush_name; self._pen_sym_paths.append(sp)
        p_val=self._tablet_pressure if self._is_tablet else 1.0
        n=VNode(dp); self._pen_path.nodes.append(n); self._pen_path.pressure.append(p_val)
        for sp,spt in zip(self._pen_sym_paths,sym_points(self.doc,dp)):
            sn=VNode(spt); sp.nodes.append(sn); sp.pressure.append(p_val)
        self.update()

    def _pen_drag(self,dp):
        if not self._pen_drawing or not self._pen_path.nodes: return
        self._raw_pts.append(dp)
        # 筆圧を最後ノードに更新
        p_val=self._tablet_pressure if self._is_tablet else 1.0
        if self._pen_path.pressure: self._pen_path.pressure[-1]=p_val
        for sp in self._pen_sym_paths:
            if sp.pressure: sp.pressure[-1]=p_val
        n=self._pen_path.nodes[-1]
        dx,dy=dp.x()-n.pos.x(),dp.y()-n.pos.y()
        n.cp_out=dp; n.cp_in=QPointF(n.pos.x()-dx,n.pos.y()-dy)
        # Fix3: sym_pt/syms のデッドコード除去、sym_points(doc, n.pos) のみ使用
        for spath,orig_spt in zip(self._pen_sym_paths, sym_points(self.doc,n.pos)):
            if not spath.nodes: continue
            sn=spath.nodes[-1]
            cpi,cpo=sym_mirror_cp(self.doc,n.pos,dp,orig_spt,self.doc.symmetry)
            sn.cp_in=cpi; sn.cp_out=cpo
        self.update()

    def _pen_release(self,dp): pass

    def _pen_finish(self):
        if self._pen_path and len(self._pen_path.nodes)>=2:
            # 手ブレ補正（Fix1: メインパスとsymパスを同じ処理で統一）
            if self.smoothing>0:
                def _smooth_vpath(vp: VPath):
                    """VPathのノード座標にスムージングを適用してCPを再計算"""
                    nodes=vp.nodes
                    if len(nodes)<2: return
                    raw_pos=[n.pos for n in nodes]
                    sm=lowpass_smooth(raw_pos, max(0.1, 1-self.smoothing))
                    sm=chaikin_smooth(sm, int(self.smoothing*2)+1)
                    sm=resample_pts(sm, len(nodes))  # 元ノード数に合わせる
                    for i,(n,sp) in enumerate(zip(nodes,sm)):
                        n.pos=QPointF(sp)
                        prev_p=sm[i-1] if i>0 else sp
                        next_p=sm[i+1] if i<len(sm)-1 else sp
                        dx=next_p.x()-prev_p.x(); dy=next_p.y()-prev_p.y()
                        seg_len=math.hypot(dx,dy)
                        if seg_len>0.001:
                            cp_len=seg_len*0.33
                            ux=dx/seg_len; uy=dy/seg_len
                            n.cp_in =QPointF(sp.x()-ux*cp_len, sp.y()-uy*cp_len)
                            n.cp_out=QPointF(sp.x()+ux*cp_len, sp.y()+uy*cp_len)
                        else:
                            n.cp_in=QPointF(sp); n.cp_out=QPointF(sp)
                # メインパスをスムージング
                _smooth_vpath(self._pen_path)
                # symパスも同じ処理（Fix1: これが抜けていた）
                for sp in self._pen_sym_paths:
                    if len(sp.nodes)>=2:
                        _smooth_vpath(sp)
            layer=self.doc.active_layer
            self.undo.beginMacro("ペン描画")
            self.undo.push(CmdAddPath(layer,self._pen_path))
            for sp in self._pen_sym_paths:
                if len(sp.nodes)>=2: self.undo.push(CmdAddPath(layer,sp))
            self.undo.endMacro()
            self.selected=[self._pen_path]; self.selection_changed.emit(self.selected)
            self.document_changed.emit()
        self._pen_path=None; self._pen_drawing=False; self._pen_sym_paths=[]; self._raw_pts=[]
        self.update()

    # ─── Reshape ───
    def _reshape_press(self,dp):
        if self.selected:
            vp=self.selected[0]
            cp=vp.cp_at(dp,7/self._scale)
            if cp:
                self.sel_cp=cp; self._drag_start=dp; self.sel_node=cp[0]; return
            n=vp.node_at(dp,8/self._scale)
            if n:
                self.sel_node=n; self.sel_cp=None; self._drag_start=dp
                self._node_before=n.snapshot(); return
        hit=self._hit_paths(dp)
        if hit:
            self.selected=[hit]; self.selection_changed.emit(self.selected)
            nearest=min(hit.nodes,key=lambda x:QLineF(x.pos,dp).length(),default=None)
            self.sel_node=nearest; self._drag_start=dp
            if nearest: self._node_before=nearest.snapshot()
        else:
            self.selected=[]; self.sel_node=None; self.selection_changed.emit([])
        self.update()

    def _reshape_drag(self,dp):
        if not self._drag_start: return
        if self.sel_cp:
            node,which=self.sel_cp
            if which=='in':
                node.cp_in=dp
                if node.smooth:
                    dx,dy=dp.x()-node.pos.x(),dp.y()-node.pos.y()
                    node.cp_out=QPointF(node.pos.x()-dx,node.pos.y()-dy)
            else:
                node.cp_out=dp
                if node.smooth:
                    dx,dy=dp.x()-node.pos.x(),dp.y()-node.pos.y()
                    node.cp_in=QPointF(node.pos.x()-dx,node.pos.y()-dy)
        elif self.sel_node: self.sel_node.set_pos(dp)
        self.update()

    def _reshape_release(self,dp):
        if self.sel_node and self._node_before and self._drag_start:
            b=self._node_before; n=self.sel_node; a=n.snapshot()
            if b[0]!=a[0]:
                self.undo.push(CmdMoveNode(n,b,a)); self.document_changed.emit()
        self.sel_cp=None; self._drag_start=None; self._node_before=None; self.update()

    # ─── Select ───
    def _select_press(self,scr,dp,mods):
        hndl=self._bb_handle_at(scr)
        if hndl and self.selected:
            self._bb_handle=hndl; self._bb_start_pt=dp
            self._bb_before=self._snap_before()
            self._bb_start_rect=self._get_sel_rect()
            if hndl=='rot':
                c=self._bb_start_rect.center(); self._bb_rot_c=c
                self._bb_start_angle=math.degrees(math.atan2(dp.y()-c.y(),dp.x()-c.x()))
            return
        hit=self._hit_paths(dp)
        if hit:
            if mods&Qt.ShiftModifier:
                if hit in self.selected: self.selected.remove(hit)
                else: self.selected.append(hit)
            else:
                if hit not in self.selected: self.selected=[hit]
            self.selection_changed.emit(self.selected)
            self._drag_start=dp; self._drag_snaps=self._snap_before()
            self._rubber_start=None
        else:
            if not(mods&Qt.ShiftModifier): self.selected=[]; self.selection_changed.emit([])
            self._rubber_start=scr; self._rubber_rect=None
        self.update()

    def _select_drag(self,scr,dp):
        if self._bb_handle and self._bb_start_rect:
            self._apply_bb(dp); self.update(); return
        if self._drag_start and self.selected and self._drag_snaps:
            delta=dp-self._drag_start
            for vp,states in self._drag_snaps.items():
                for n,(pos,cpi,cpo) in zip(vp.nodes,states):
                    n.pos=pos+delta; n.cp_in=cpi+delta; n.cp_out=cpo+delta
            self.update(); return
        if self._rubber_start:
            self._rubber_rect=QRectF(self._rubber_start,scr).normalized(); self.update()

    def _apply_bb(self,dp):
        hndl=self._bb_handle; sr=self._bb_start_rect; sp=self._bb_start_pt
        if hndl=='rot':
            c=self._bb_rot_c
            ca=math.degrees(math.atan2(dp.y()-c.y(),dp.x()-c.x()))
            da=ca-self._bb_start_angle
            for vp,states in self._bb_before.items():
                for n,(pos,cpi,cpo) in zip(vp.nodes,states):
                    n.pos=_rotate_pt(pos,c,da); n.cp_in=_rotate_pt(cpi,c,da); n.cp_out=_rotate_pt(cpo,c,da)
            return
        dx,dy=dp.x()-sp.x(),dp.y()-sp.y()
        ow=max(sr.width(),1); oh=max(sr.height(),1)
        if   hndl=='br': sx=(ow+dx)/ow; sy=(oh+dy)/oh
        elif hndl=='tr': sx=(ow+dx)/ow; sy=(oh-dy)/oh
        elif hndl=='bl': sx=(ow-dx)/ow; sy=(oh+dy)/oh
        elif hndl=='tl': sx=(ow-dx)/ow; sy=(oh-dy)/oh
        else: sx=sy=1.0
        ox,oy=sr.left(),sr.top()
        for vp,states in self._bb_before.items():
            for n,(pos,cpi,cpo) in zip(vp.nodes,states):
                n.pos=QPointF(ox+(pos.x()-ox)*sx,oy+(pos.y()-oy)*sy)
                n.cp_in=QPointF(ox+(cpi.x()-ox)*sx,oy+(cpi.y()-oy)*sy)
                n.cp_out=QPointF(ox+(cpo.x()-ox)*sx,oy+(cpo.y()-oy)*sy)

    def _select_release(self,dp):
        if self._bb_handle:
            self.undo.push(CmdMovePaths(self._bb_before,self._snap_before()))
            self._bb_handle=None; self.document_changed.emit(); self.update(); return
        if self._drag_start and self.selected and self._drag_snaps:
            after=self._snap_before()
            moved=any(any(n.pos!=s[0] for n,s in zip(vp.nodes,states)) for vp,states in self._drag_snaps.items())
            if moved:
                self.undo.push(CmdMovePaths(self._drag_snaps,after)); self.document_changed.emit()
            self._drag_start=None; self._drag_snaps={}; self.update(); return
        if self._rubber_rect:
            for layer in self.doc.layers:
                if not layer.visible or layer.locked: continue
                for vp in layer.paths:
                    br=QRectF(self.to_scr(vp.bounding_rect().topLeft()),self.to_scr(vp.bounding_rect().bottomRight()))
                    if self._rubber_rect.intersects(br) and vp not in self.selected: self.selected.append(vp)
            self.selection_changed.emit(self.selected)
            self._rubber_rect=None; self._rubber_start=None; self.update()

    # ─── 消しゴム ───
    def _eraser_press(self,dp):
        hit=self._hit_paths(dp)
        if hit:
            layer,_=self.doc.find_path(hit.id)
            if layer:
                self.undo.push(CmdDeletePaths([(layer,hit)]))
                if hit in self.selected: self.selected.remove(hit)
                self.selection_changed.emit(self.selected)
                self.document_changed.emit(); self.update()

    # ─── アンカー追加 (バグ修正2) ───
    def _add_node_press(self,dp):
        """Bug4修正: 閉じたパス末尾セグメント等のエッジケースも完全Undo対応"""
        hit=self._hit_paths(dp)
        if not hit and self.selected: hit=self.selected[0]
        if not hit: return
        # insert_node_at は (new_node, idx, old_a_out, old_b_in) のタプルを返す
        result=hit.insert_node_at(dp)
        if result is None: return
        new_node, idx, old_a_out, old_b_in = result
        # 挿入後の前後ノード参照（閉じたパスのラップアラウンドも考慮）
        n_total=len(hit.nodes)  # new_node 挿入済み状態
        node_a=hit.nodes[(idx-1) % n_total]
        node_b=hit.nodes[(idx+1) % n_total]
        new_a_out=QPointF(node_a.cp_out); new_b_in=QPointF(node_b.cp_in)
        # 一旦元の状態に戻してからコマンド経由で適用（Undo対応）
        hit.nodes.remove(new_node)
        node_a.cp_out=QPointF(old_a_out); node_b.cp_in=QPointF(old_b_in)
        self.undo.push(CmdInsertNode(hit, new_node, idx,
                                     node_a, node_b,
                                     old_a_out, old_b_in,
                                     new_a_out, new_b_in))
        self.selected=[hit]; self.sel_node=new_node
        self.selection_changed.emit(self.selected)
        self.document_changed.emit(); self.update()

    # ─── アンカー削除 ───
    def _del_node_press(self,dp):
        for vp in(self.selected or []):
            n=vp.node_at(dp,8/self._scale)
            if n and n in vp.nodes:
                idx=vp.nodes.index(n)
                self.undo.push(CmdDeleteNode(vp,n,idx))
                if self.sel_node is n: self.sel_node=None
                self.document_changed.emit(); self.update(); return
        hit=self._hit_paths(dp)
        if hit:
            n=hit.node_at(dp,8/self._scale)
            if n:
                idx=hit.nodes.index(n)
                self.undo.push(CmdDeleteNode(hit,n,idx))
                self.document_changed.emit(); self.update()

    # ─── 線幅 ───
    def _width_press(self,dp):
        hit=self._hit_paths(dp)
        if hit:
            self.selected=[hit]; self._drag_start=dp; self._width_old=hit.stroke_width
            self.selection_changed.emit(self.selected)
        self.update()

    def _width_drag(self,dp):
        if not self.selected or not self._drag_start: return
        vp=self.selected[0]
        vp.stroke_width=max(0.1,self._width_old+(dp.x()-self._drag_start.x())*0.05)
        self.update()

    def _width_release(self,dp):
        if self.selected and self._drag_start:
            vp=self.selected[0]; new_w=vp.stroke_width
            if new_w!=self._width_old:
                vp.stroke_width=self._width_old
                self.undo.push(CmdSetStrokeWidth(vp,self._width_old,new_w))
                self.document_changed.emit()
        self._drag_start=None

    # ─── バケツ (バグ修正3) ───
    def _bucket_press(self,dp):
        cmds=vector_bucket_fill(self.doc,dp,self.fill_color)
        if not cmds: return
        self.undo.beginMacro("バケツ塗り")
        for cmd_type,data in cmds:
            if cmd_type=="set_fill":
                layer,vp,old_c,new_c=data
                self.undo.push(CmdSetFillColor(vp,old_c,new_c))
            elif cmd_type=="add_path":
                layer,vp=data
                self.undo.push(CmdAddPath(layer,vp))
        self.undo.endMacro()
        self.document_changed.emit(); self.update()

    # ─── 交差点切断 ───
    def _scissors_press(self,dp):
        r=10/self._scale
        for layer in self.doc.layers:
            if not layer.visible or layer.locked: continue
            for vp in layer.paths:
                if not vp.hit_test(dp,r): continue
                if len(vp.nodes)<3 or vp.closed: continue
                best_i=min(range(len(vp.nodes)),key=lambda i:QLineF(vp.nodes[i].pos,dp).length())
                if QLineF(vp.nodes[best_i].pos,dp).length()>r*2: continue
                if best_i in(0,len(vp.nodes)-1): continue
                vp1=VPath(); vp1.nodes=[n.clone() for n in vp.nodes[:best_i+1]]
                vp1.stroke_color=QColor(vp.stroke_color); vp1.stroke_width=vp.stroke_width
                vp2=VPath(); vp2.nodes=[n.clone() for n in vp.nodes[best_i:]]
                vp2.stroke_color=QColor(vp.stroke_color); vp2.stroke_width=vp.stroke_width
                self.undo.beginMacro("パスを切断")
                self.undo.push(CmdDeletePaths([(layer,vp)]))
                self.undo.push(CmdAddPath(layer,vp1)); self.undo.push(CmdAddPath(layer,vp2))
                self.undo.endMacro()
                if vp in self.selected: self.selected.remove(vp)
                self.selected.extend([vp1,vp2])
                self.selection_changed.emit(self.selected)
                self.document_changed.emit(); self.update(); return

    # ─── フキダシ ───
    def _balloon_press(self,dp):
        self._balloon_start=QPointF(dp); self._balloon_cur=QPointF(dp); self.update()

    def _balloon_drag(self,dp):
        self._balloon_cur=QPointF(dp); self.update()

    def _balloon_release(self,dp):
        if not self._balloon_start: return
        start=self._balloon_start
        rx=abs(dp.x()-start.x())/2; ry=abs(dp.y()-start.y())/2
        if rx<5 or ry<5: self._balloon_start=None; self.update(); return
        btype=getattr(self,'_balloon_type',BALLOON_ELLIPSE)
        vp=make_balloon(start,rx,ry,btype)
        layer=self.doc.active_layer
        self.undo.push(CmdAddPath(layer,vp))
        self.selected=[vp]; self.selection_changed.emit(self.selected)
        self.document_changed.emit()
        self._balloon_start=None; self.update()

    # ─── コマ割り ───
    def _panel_press(self,dp):
        self._panel_start=QPointF(dp); self._panel_cur=QPointF(dp); self.update()

    def _panel_drag(self,dp):
        self._panel_cur=QPointF(dp); self.update()

    def _panel_release(self,dp):
        if not self._panel_start: return
        start=self._panel_start; self._panel_start=None
        border_w=getattr(self,'_panel_border_w',3.0)
        rect=QRectF(start,dp).normalized()
        line_len=QLineF(start,dp).length()
        # ドラッグが細長い(aspect>4)か短形か で分割/新規を切り替え
        is_split_line=(rect.width()<15 or rect.height()<15) and line_len>20
        if is_split_line:
            # 既存のコマパスを線で分割
            split_done=False
            for layer in self.doc.layers:
                if not layer.visible or layer.locked: continue
                for vp in layer.paths:
                    if vp.meta.get("type")!="panel": continue
                    parts=split_panel_by_line(vp,start,dp,border_w)
                    if parts:
                        self.undo.beginMacro("コマ分割")
                        self.undo.push(CmdDeletePaths([(layer,vp)]))
                        for p in parts: self.undo.push(CmdAddPath(layer,p))
                        self.undo.endMacro()
                        self.selected=parts; self.selection_changed.emit(self.selected)
                        self.document_changed.emit(); split_done=True; break
                if split_done: break
            if not split_done:
                # 分割対象なし → 新規コマ(線として)
                vp=VPath(); vp.stroke_color=QColor("#000000"); vp.stroke_width=border_w
                vp.nodes=[VNode(start),VNode(dp)]; vp.meta={"type":"panel_line"}
                self.undo.push(CmdAddPath(self.doc.active_layer,vp))
                self.selected=[vp]; self.selection_changed.emit(self.selected)
                self.document_changed.emit()
        else:
            # 矩形コマを新規作成
            if rect.width()<10 or rect.height()<10: self.update(); return
            vp=make_panel(rect,border_w)
            self.undo.push(CmdAddPath(self.doc.active_layer,vp))
            self.selected=[vp]; self.selection_changed.emit(self.selected)
            self.document_changed.emit()
        self.update()

    # ─── 集中線 ───
    def _focus_press(self,dp):
        self._focus_center=QPointF(dp); self.update()

    def _focus_release(self,dp):
        if not self._focus_center: return
        center=self._focus_center
        outer_r=QLineF(center,dp).length()
        if outer_r<5: self._focus_center=None; self.update(); return
        inner_r=outer_r*0.2
        count=getattr(self,'_focus_count',64)
        # Bug2修正: List[VPath] を返す新バージョンを使用
        paths=make_focus_lines(center,outer_r,inner_r,count,
                               stroke_color=QColor(self.pen_color),
                               stroke_width=self.pen_width)
        layer=self.doc.active_layer
        self.undo.beginMacro("集中線")
        for vp in paths: self.undo.push(CmdAddPath(layer,vp))
        self.undo.endMacro()
        self.selected=paths; self.selection_changed.emit(self.selected)
        self.document_changed.emit()
        self._focus_center=None; self.update()

    # ─── 効果線 ───
    def _speed_press(self,dp):
        """ドラッグ開始点を記録"""
        self._speed_start=QPointF(dp); self._speed_cur=QPointF(dp)

    def _speed_drag(self,dp):
        """Fix2: dispatch追加済み。ドラッグ中に方向プレビューを表示"""
        self._speed_cur=QPointF(dp); self.update()

    def _speed_release(self,dp):
        """Bug3修正: ドラッグ方向からスピード線方向を自動判定して生成"""
        if not hasattr(self,'_speed_start'): return
        start=self._speed_start; end=QPointF(dp)
        dx=end.x()-start.x(); dy=end.y()-start.y()
        dist=math.hypot(dx,dy)
        if dist<5:
            # 短いクリックはパネルの選択方向で生成
            direction=getattr(self,'_speed_dir','right')
        else:
            if abs(dx)>=abs(dy):
                direction="right" if dx>0 else "left"
            else:
                direction="down" if dy>0 else "up"
        self._speed_release_dir(direction)
        self._speed_start=None

    def _speed_release_dir(self,direction):
        """ToolOptionsPanel の「効果線を生成」ボタンからも呼ばれる"""
        rect=QRectF(0,0,self.doc.width,self.doc.height)
        count=getattr(self,'_speed_count',20)
        paths=make_speed_lines(rect,direction,count)
        layer=self.doc.active_layer
        self.undo.beginMacro("効果線")
        for vp in paths:
            vp.stroke_color=QColor(self.pen_color)
            self.undo.push(CmdAddPath(layer,vp))
        self.undo.endMacro()
        self.document_changed.emit(); self.update()

    # ─── グループ ───
    def _group_selection(self):
        if len(self.selected)<2: return
        layer=self.doc.active_layer
        grp=VGroup(); grp.items=list(self.selected)
        self.undo.push(CmdGroupPaths(layer,list(self.selected),grp))
        self.selected=grp.items[:]; self.selection_changed.emit(self.selected)
        self.document_changed.emit(); self.update()

    def _ungroup_selection(self):
        if not self.selected: return
        vp=self.selected[0]; layer,grp=self.doc.find_group_of(vp)
        if not grp: return
        self.undo.push(CmdUngroupPaths(layer,grp))
        self.selected=list(grp.items); self.selection_changed.emit(self.selected)
        self.document_changed.emit(); self.update()

    def _duplicate_selected(self):
        layer=self.doc.active_layer
        new_paths=[]
        self.undo.beginMacro("複製")
        for vp in self.selected:
            new_vp=vp.clone()
            for n in new_vp.nodes: n.set_pos(n.pos+QPointF(10,10))
            self.undo.push(CmdAddPath(layer,new_vp)); new_paths.append(new_vp)
        self.undo.endMacro()
        self.selected=new_paths; self.selection_changed.emit(self.selected)
        self.document_changed.emit(); self.update()

    def _bring_to_front(self):
        layer=self.doc.active_layer
        for vp in self.selected:
            if vp in layer.items: layer.items.remove(vp); layer.items.append(vp)
        self.update()

    def _send_to_back(self):
        layer=self.doc.active_layer
        for vp in self.selected:
            if vp in layer.items: layer.items.remove(vp); layer.items.insert(0,vp)
        self.update()

    def _select_all(self):
        self.selected=list(self.doc.active_layer.paths)
        self.selection_changed.emit(self.selected); self.update()

    def _update_hover(self,dp):
        prev_n=self._hover_node; prev_p=self._hover_path
        self._hover_node=None; self._hover_path=None
        if self.selected and self.tool in(TOOL_RESHAPE,TOOL_ADD_NODE,TOOL_DEL_NODE):
            n=self.selected[0].node_at(dp,8/self._scale); self._hover_node=n
        if not self._hover_node: self._hover_path=self._hit_paths(dp)
        if prev_n!=self._hover_node or prev_p!=self._hover_path: self.update()

    def fit_canvas(self):
        wr=(self.width()-80)/self.doc.width; hr=(self.height()-80)/self.doc.height
        self._scale=min(wr,hr)
        self._offset=QPointF((self.width()-self.doc.width*self._scale)/2,
                             (self.height()-self.doc.height*self._scale)/2)
        self.update()

    def zoom_to(self,s):
        c=QPointF(self.width()/2,self.height()/2)
        self._offset=QPointF(c.x()-self.doc.width/2*s,c.y()-self.doc.height/2*s)
        self._scale=s; self.update()

# ══════════════════════════════════════════════════════════════
#  ブラシスタジオ (完全版)
# ══════════════════════════════════════════════════════════════
class BrushStudioDialog(QDialog):
    brush_applied=Signal(str,dict)

    def __init__(self,parent,doc:Document,current:str):
        super().__init__(parent)
        self.setWindowTitle("ブラシスタジオ")
        self.setMinimumSize(560,480)
        self.doc=doc; self.current=current
        self._editing: Optional[str]=None
        self._build()

    def _build(self):
        lay=QHBoxLayout(self)
        # 左: プリセットリスト
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0)
        lbl=QLabel("プリセット"); lbl.setStyleSheet(f"font-weight:600;color:{C['fg_dim']};font-size:11px;")
        self.list=QListWidget()
        self._refresh_list()
        btn_bar=QHBoxLayout()
        self.btn_new=QPushButton("＋ 新規"); self.btn_del=QPushButton("削除")
        self.btn_del.setObjectName("danger")
        self.btn_new.clicked.connect(self._new_brush)
        self.btn_del.clicked.connect(self._del_brush)
        btn_bar.addWidget(self.btn_new); btn_bar.addWidget(self.btn_del)
        ll.addWidget(lbl); ll.addWidget(self.list,1); ll.addLayout(btn_bar)
        self.list.currentTextChanged.connect(self._on_sel)
        # 右: パラメータ編集
        right=QWidget(); rl=QVBoxLayout(right)
        self.name_edit=QLineEdit(); self.name_edit.setPlaceholderText("ブラシ名")
        rl.addWidget(QLabel("ブラシ名")); rl.addWidget(self.name_edit)
        params_grp=QGroupBox("パラメータ"); pg=QGridLayout(params_grp)
        self._param_widgets={}
        params=[
            ("pressure_width","筆圧→太さ","bool"),
            ("opacity_var","不透明度ばらつき","float",0.0,1.0),
            ("scatter","散布量","float",0.0,20.0),
            ("smoothing","手ブレ補正","float",0.0,1.0),
            ("taper","テーパー","float",0.0,1.0),
        ]
        for row,(key,label,typ,*args) in enumerate(params):
            pg.addWidget(QLabel(label),row,0)
            if typ=="bool":
                w=QCheckBox(); self._param_widgets[key]=w
            else:
                lo,hi=args[0],args[1]
                w=QDoubleSpinBox(); w.setRange(lo,hi); w.setSingleStep(0.05)
                self._param_widgets[key]=w
            pg.addWidget(w,row,1)
        rl.addWidget(params_grp)
        # 視覚プレビュー (QPainter でサンプルストロークを描画)
        self.preview_lbl=QLabel()
        self.preview_lbl.setFixedHeight(80)
        self.preview_lbl.setMinimumWidth(200)
        self.preview_lbl.setStyleSheet(f"background:{C['canvas_bg']};border:1px solid {C['border']};border-radius:4px;")
        rl.addWidget(QLabel("プレビュー")); rl.addWidget(self.preview_lbl)
        # ボタン
        btns=QDialogButtonBox()
        btn_apply=QPushButton("このブラシを使用"); btn_apply.setObjectName("accent")
        btn_save=QPushButton("保存"); btn_close=QPushButton("閉じる")
        btn_apply.clicked.connect(self._apply); btn_save.clicked.connect(self._save)
        btn_close.clicked.connect(self.reject)
        btns.addButton(btn_apply,QDialogButtonBox.AcceptRole)
        btns.addButton(btn_save,QDialogButtonBox.ApplyRole)
        btns.addButton(btn_close,QDialogButtonBox.RejectRole)
        rl.addWidget(btns); rl.addStretch()
        lay.addWidget(left,2); lay.addWidget(right,3)
        # 初期選択
        if self.current in self.doc.brush_presets:
            items=self.list.findItems(self.current,Qt.MatchExactly)
            if items: self.list.setCurrentItem(items[0])

    def _refresh_list(self):
        self.list.clear()
        for name in self.doc.brush_presets: self.list.addItem(name)

    def _on_sel(self,name):
        if not name or name not in self.doc.brush_presets: return
        self._editing=name; b=self.doc.brush_presets[name]
        self.name_edit.setText(name)
        for key,w in self._param_widgets.items():
            val=b.get(key,False)
            if isinstance(w,QCheckBox): w.setChecked(bool(val))
            elif isinstance(w,QDoubleSpinBox): w.setValue(float(val) if val else 0.0)
        self._draw_brush_preview(name, b)

    def _draw_brush_preview(self,name:str,bdef:dict):
        """ブラシのサンプルストロークをQPixmapに描画してプレビュー表示"""
        import math as _m, random as _r
        W=max(self.preview_lbl.width() if self.preview_lbl.width()>10 else 300, 200)
        H=80
        pix=QPixmap(W,H); pix.fill(QColor(C["canvas_bg"]))
        p=QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
        # S字カーブのサンプルストローク (20点)
        pts=[QPointF(W*0.05+W*0.9*i/19, H*0.5+_m.sin(i/19*_m.pi*2)*H*0.28)
             for i in range(20)]
        pressures=[_m.sin(_m.pi*i/19) for i in range(20)]
        base_w=max(2.0, min(H*0.18, 14.0))
        pressure_on=bdef.get("pressure_width",True)
        taper=bdef.get("taper",0.0)
        scatter=bdef.get("scatter",0.0)
        stroke_c=QColor(C["fg"])
        rng=_r.Random(42)
        for i in range(len(pts)-1):
            a,b2=pts[i],pts[i+1]
            pres=(pressures[i]+pressures[i+1])/2
            tp=1.0
            if taper>0:
                t_in =min(i/(max(len(pts)*taper,1)),1.0)
                t_out=min((len(pts)-1-i)/(max(len(pts)*taper,1)),1.0)
                tp=min(t_in,t_out)
            w=base_w*(pres if pressure_on else 0.85)*tp
            if scatter>0:
                for _ in range(3):
                    ox=rng.uniform(-scatter,scatter)*0.5
                    oy=rng.uniform(-scatter,scatter)*0.5
                    sc=QColor(stroke_c); sc.setAlpha(80)
                    p.setPen(QPen(sc,max(0.5,w*0.4),Qt.SolidLine,Qt.RoundCap))
                    p.drawLine(QPointF(a.x()+ox,a.y()+oy),QPointF(b2.x()+ox,b2.y()+oy))
            p.setPen(QPen(stroke_c,max(0.3,w),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
            p.drawLine(a,b2)
        p.setPen(QPen(QColor(C["fg_dim"]))); p.setFont(QFont("monospace",9))
        p.drawText(4,H-4,name); p.end()
        self.preview_lbl.setPixmap(pix)

    def _new_brush(self):
        name,ok=QInputDialog.getText(self,"新規ブラシ","ブラシ名:")
        if ok and name and name not in self.doc.brush_presets:
            self.doc.brush_presets[name]=dict(DEFAULT_BRUSHES["Gペン"])
            self._refresh_list()
            items=self.list.findItems(name,Qt.MatchExactly)
            if items: self.list.setCurrentItem(items[0])

    def _del_brush(self):
        name=self.list.currentItem()
        if name and name.text() in self.doc.brush_presets and name.text() not in DEFAULT_BRUSHES:
            del self.doc.brush_presets[name.text()]; self._refresh_list()

    def _save(self):
        if not self._editing: return
        old_name=self._editing; new_name=self.name_edit.text().strip()
        if not new_name: return
        b={}
        for key,w in self._param_widgets.items():
            if isinstance(w,QCheckBox): b[key]=w.isChecked()
            elif isinstance(w,QDoubleSpinBox): b[key]=w.value()
        b["tip"]=self.doc.brush_presets.get(old_name,{}).get("tip","round")
        if new_name!=old_name and old_name in self.doc.brush_presets:
            del self.doc.brush_presets[old_name]
        self.doc.brush_presets[new_name]=b; self._editing=new_name
        self._refresh_list()
        items=self.list.findItems(new_name,Qt.MatchExactly)
        if items: self.list.setCurrentItem(items[0])

    def _apply(self):
        name=self.list.currentItem()
        if name:
            self.brush_applied.emit(name.text(),self.doc.brush_presets[name.text()])
            self.accept()

# ══════════════════════════════════════════════════════════════
#  Webtoonダイアログ
# ══════════════════════════════════════════════════════════════
class WebtoonPreviewWidget(QWidget):
    """Webtoonストリップをスクロール表示するプレビューウィジェット"""
    def __init__(self,doc:Document,parent=None):
        super().__init__(parent)
        self.doc=doc; self._img=None; self._scale=0.25
        self.setMinimumSize(240,200)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)

    def set_scale(self,s): self._scale=s; self.update()

    def refresh(self,brush_defs=None):
        if brush_defs is None: brush_defs=DEFAULT_BRUSHES
        self._img=render_to_image(self.doc,scale=self._scale,brush_defs=brush_defs)
        total_h=int(self.doc.height*self._scale)
        self.setMinimumHeight(min(total_h+20,600))
        self.update()

    def paintEvent(self,ev):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor(C["panel"]))
        if self._img is None:
            p.setPen(QPen(QColor(C["fg_dim"]))); p.drawText(self.rect(),Qt.AlignCenter,"プレビュー更新ボタンを押してください")
            return
        x=(self.width()-self._img.width())//2; y=10
        p.drawImage(x,y,self._img)
        if self.doc.webtoon_mode:
            sh=max(1,int(self.doc.webtoon_strip_height*self._scale))
            pen=QPen(QColor(C["danger"]),1,Qt.DashLine); p.setPen(pen)
            strip_y=y
            strip_n=1
            while strip_y<y+self._img.height():
                p.drawLine(x,strip_y,x+self._img.width(),strip_y)
                p.setFont(QFont("monospace",8))
                p.setPen(QPen(QColor(C["warn"])))
                p.drawText(x+2,strip_y+12,f"Strip {strip_n}")
                p.setPen(pen); strip_y+=sh; strip_n+=1


class WebtoonDialog(QDialog):
    def __init__(self,parent,doc:Document,brush_defs=None):
        super().__init__(parent); self.setWindowTitle("Webtoonモード設定")
        self.doc=doc; self.brush_defs=brush_defs or DEFAULT_BRUSHES
        self.setMinimumSize(520,540); self._build()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(8)
        # 設定
        settings=QGroupBox("設定"); sl=QGridLayout(settings)
        self.chk_mode=QCheckBox("Webtoonモードを有効にする")
        self.chk_mode.setChecked(self.doc.webtoon_mode)
        sl.addWidget(self.chk_mode,0,0,1,2)
        sl.addWidget(QLabel("ストリップ高さ (px)"),1,0)
        self.spin_sh=QSpinBox(); self.spin_sh.setRange(100,5000)
        self.spin_sh.setValue(self.doc.webtoon_strip_height)
        sl.addWidget(self.spin_sh,1,1)
        sl.addWidget(QLabel("プレビュー倍率"),2,0)
        self.spin_scale=QDoubleSpinBox(); self.spin_scale.setRange(0.05,1.0)
        self.spin_scale.setSingleStep(0.05); self.spin_scale.setValue(0.25)
        sl.addWidget(self.spin_scale,2,1)
        lay.addWidget(settings)
        # プレビュー
        self.preview=WebtoonPreviewWidget(self.doc)
        scroll=QScrollArea(); scroll.setWidget(self.preview)
        scroll.setWidgetResizable(True); scroll.setMinimumHeight(260)
        scroll.setStyleSheet(f"background:{C['canvas_bg']};border:1px solid {C['border']};")
        lay.addWidget(scroll,1)
        # ボタン行
        btn_row=QHBoxLayout()
        btn_preview=QPushButton("プレビュー更新"); btn_preview.clicked.connect(self._refresh_preview)
        btn_export=QPushButton("ストリップ書き出し…"); btn_export.setObjectName("success")
        btn_export.clicked.connect(self._export_strips)
        btn_row.addWidget(btn_preview); btn_row.addWidget(btn_export); btn_row.addStretch()
        lay.addLayout(btn_row)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        btns.accepted.connect(self._ok); btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        QTimer.singleShot(150,self._refresh_preview)

    def _refresh_preview(self):
        self.preview.set_scale(self.spin_scale.value())
        self.preview.refresh(self.brush_defs)

    def _export_strips(self):
        """各Webtoonストリップを個別PNGとして書き出し"""
        import os
        dir_path=QFileDialog.getExistingDirectory(self,"書き出し先フォルダを選択")
        if not dir_path: return
        sh=self.spin_sh.value()
        full_img=render_to_image(self.doc,scale=2.0,brush_defs=self.brush_defs)
        full_h=full_img.height(); strip_w=full_img.width()
        idx=1; y=0
        while y<full_h:
            crop_h=min(sh*2,full_h-y)
            strip=full_img.copy(0,y,strip_w,crop_h)
            path=os.path.join(dir_path,f"strip_{idx:03d}.png")
            strip.save(path,"PNG"); y+=crop_h; idx+=1
        QMessageBox.information(self,"完了",f"{idx-1}枚のストリップを書き出しました\n{dir_path}")

    def _ok(self):
        self.doc.webtoon_mode=self.chk_mode.isChecked()
        self.doc.webtoon_strip_height=self.spin_sh.value()
        self.accept()

# ══════════════════════════════════════════════════════════════
#  パース定規ダイアログ
# ══════════════════════════════════════════════════════════════
class PerspDialog(QDialog):
    def __init__(self,parent,doc:Document):
        super().__init__(parent); self.setWindowTitle("パース定規")
        self.doc=doc; self._build()

    def _build(self):
        lay=QVBoxLayout(self)
        bg=QButtonGroup(self)
        self.r_none=QRadioButton("なし"); self.r_1pt=QRadioButton("1点透視"); self.r_2pt=QRadioButton("2点透視")
        for r in[self.r_none,self.r_1pt,self.r_2pt]: bg.addButton(r)
        {"なし":self.r_none,"1点透視":self.r_1pt,"2点透視":self.r_2pt}.get(self.doc.perspective,self.r_none).setChecked(True)
        # 消失点座標
        grp=QGroupBox("消失点1"); gl=QGridLayout(grp)
        gl.addWidget(QLabel("X"),0,0); self.sp_vp1x=QDoubleSpinBox(); self.sp_vp1x.setRange(-9999,9999); self.sp_vp1x.setValue(self.doc.persp_vp1.x()); gl.addWidget(self.sp_vp1x,0,1)
        gl.addWidget(QLabel("Y"),1,0); self.sp_vp1y=QDoubleSpinBox(); self.sp_vp1y.setRange(-9999,9999); self.sp_vp1y.setValue(self.doc.persp_vp1.y()); gl.addWidget(self.sp_vp1y,1,1)
        grp2=QGroupBox("消失点2（2点透視のみ）"); gl2=QGridLayout(grp2)
        gl2.addWidget(QLabel("X"),0,0); self.sp_vp2x=QDoubleSpinBox(); self.sp_vp2x.setRange(-9999,9999); self.sp_vp2x.setValue(self.doc.persp_vp2.x()); gl2.addWidget(self.sp_vp2x,0,1)
        gl2.addWidget(QLabel("Y"),1,0); self.sp_vp2y=QDoubleSpinBox(); self.sp_vp2y.setRange(-9999,9999); self.sp_vp2y.setValue(self.doc.persp_vp2.y()); gl2.addWidget(self.sp_vp2y,1,1)
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        btns.accepted.connect(self._ok); btns.rejected.connect(self.reject)
        for r in[self.r_none,self.r_1pt,self.r_2pt]: lay.addWidget(r)
        lay.addWidget(grp); lay.addWidget(grp2); lay.addWidget(btns)

    def _ok(self):
        self.doc.perspective=("なし" if self.r_none.isChecked() else "1点透視" if self.r_1pt.isChecked() else "2点透視")
        self.doc.persp_vp1=QPointF(self.sp_vp1x.value(),self.sp_vp1y.value())
        self.doc.persp_vp2=QPointF(self.sp_vp2x.value(),self.sp_vp2y.value())
        self.accept()

# ══════════════════════════════════════════════════════════════
#  レイヤーパネル
# ══════════════════════════════════════════════════════════════
class LayerPanel(QWidget):
    changed=Signal()
    def __init__(self,doc):
        super().__init__(); self.doc=doc; self._build(); self.refresh()

    def _build(self):
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        bar=QWidget(); bar.setStyleSheet(f"background:{C['surface']};border-bottom:1px solid {C['border']};")
        bl=QHBoxLayout(bar); bl.setContentsMargins(6,6,6,6); bl.setSpacing(3)
        for txt,fn,nm in[("＋",self._add,""),("－",self._del,"danger"),("↑",self._up,""),("↓",self._dn,"")]:
            b=QPushButton(txt); b.setFixedSize(26,26)
            if nm: b.setObjectName(nm)
            b.clicked.connect(fn); bl.addWidget(b)
        bl.addStretch()
        self.list=QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.currentRowChanged.connect(self._row_changed)
        self.list.itemDoubleClicked.connect(self._rename)
        # Fix6: D&D 並び替えをモデルに反映
        self.list.model().rowsMoved.connect(self._rows_moved)
        ctrl=QWidget(); ctrl.setStyleSheet(f"background:{C['surface']};border-top:1px solid {C['border']};")
        cl=QVBoxLayout(ctrl); cl.setContentsMargins(8,6,8,6); cl.setSpacing(4)
        op_row=QHBoxLayout(); op_row.addWidget(QLabel("不透明度"))
        self.sl_op=QSlider(Qt.Horizontal); self.sl_op.setRange(0,100); self.sl_op.setValue(100)
        self.sl_op.valueChanged.connect(self._op_changed)
        self.lbl_op=QLabel("100%"); self.lbl_op.setFixedWidth(36)
        op_row.addWidget(self.sl_op,1); op_row.addWidget(self.lbl_op)
        cl.addLayout(op_row)
        bl2=QHBoxLayout(); bl2.addWidget(QLabel("ブレンド"))
        self.combo_blend=QComboBox()
        for m in BLEND_MODES: self.combo_blend.addItem(m)
        self.combo_blend.currentTextChanged.connect(self._blend_changed)
        bl2.addWidget(self.combo_blend,1); cl.addLayout(bl2)
        vr=QHBoxLayout()
        self.chk_vis=QCheckBox("表示"); self.chk_vis.setChecked(True)
        self.chk_lock=QCheckBox("ロック")
        self.chk_vis.toggled.connect(self._vis_changed); self.chk_lock.toggled.connect(self._lock_changed)
        vr.addWidget(self.chk_vis); vr.addWidget(self.chk_lock); vr.addStretch()
        cl.addLayout(vr)
        lay.addWidget(bar); lay.addWidget(self.list,1); lay.addWidget(ctrl)

    def refresh(self):
        self.list.blockSignals(True); self.list.clear()
        for layer in reversed(self.doc.layers):
            v="👁" if layer.visible else "🚫"; lk="🔒" if layer.locked else ""
            item=QListWidgetItem(f"  {v}{lk}  {layer.name}  ({len(layer.paths)})")
            item.setData(Qt.UserRole,layer.id); self.list.addItem(item)
        idx=len(self.doc.layers)-1-self.doc.active_layer_idx
        self.list.setCurrentRow(idx); self.list.blockSignals(False)
        layer=self.doc.active_layer
        self.sl_op.blockSignals(True); self.sl_op.setValue(int(layer.opacity*100)); self.sl_op.blockSignals(False)
        self.lbl_op.setText(f"{int(layer.opacity*100)}%")
        self.combo_blend.blockSignals(True); self.combo_blend.setCurrentText(layer.blend); self.combo_blend.blockSignals(False)
        self.chk_vis.blockSignals(True); self.chk_vis.setChecked(layer.visible); self.chk_vis.blockSignals(False)
        self.chk_lock.blockSignals(True); self.chk_lock.setChecked(layer.locked); self.chk_lock.blockSignals(False)

    def _row_changed(self,row):
        if row<0: return
        self.doc.active_layer_idx=len(self.doc.layers)-1-row; self.refresh(); self.changed.emit()

    def _rows_moved(self,parent,src,end,dst_parent,dst):
        """
        Fix6: QListWidget の D&D 完了後に doc.layers を UI の順序と同期する。
        リストは reversed(doc.layers) で表示しているので逆順変換が必要。
        """
        # UI上の現在の並び順から layer.id を取得
        ui_ids=[self.list.item(r).data(Qt.UserRole) for r in range(self.list.count())]
        # UI は上が最新レイヤー (reversed) → 逆順が doc.layers 順
        id_to_layer={layer.id:layer for layer in self.doc.layers}
        new_layers=[id_to_layer[lid] for lid in reversed(ui_ids) if lid in id_to_layer]
        if len(new_layers)==len(self.doc.layers):
            self.doc.layers=new_layers
            # アクティブレイヤーのインデックスを維持
            cur_row=self.list.currentRow()
            if cur_row>=0:
                cur_id=self.list.item(cur_row).data(Qt.UserRole)
                cur_layer=id_to_layer.get(cur_id)
                if cur_layer and cur_layer in self.doc.layers:
                    self.doc.active_layer_idx=self.doc.layers.index(cur_layer)
                else:
                    self.doc.active_layer_idx=0
        self.changed.emit()

    def _add(self):
        self.doc.layers.append(Layer(f"レイヤー {len(self.doc.layers)+1}"))
        self.doc.active_layer_idx=len(self.doc.layers)-1; self.refresh(); self.changed.emit()
    def _del(self):
        if len(self.doc.layers)<=1: return
        self.doc.layers.pop(self.doc.active_layer_idx)
        self.doc.active_layer_idx=max(0,self.doc.active_layer_idx-1); self.refresh(); self.changed.emit()
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
    def _rename(self,item):
        name,ok=QInputDialog.getText(self,"レイヤー名","新しい名前:",text=self.doc.active_layer.name)
        if ok and name: self.doc.active_layer.name=name; self.refresh(); self.changed.emit()
    def _op_changed(self,v): self.lbl_op.setText(f"{v}%"); self.doc.active_layer.opacity=v/100; self.changed.emit()
    def _blend_changed(self,t): self.doc.active_layer.blend=t; self.changed.emit()
    def _vis_changed(self,v): self.doc.active_layer.visible=v; self.changed.emit()
    def _lock_changed(self,v): self.doc.active_layer.locked=v; self.changed.emit()

# ══════════════════════════════════════════════════════════════
#  プロパティパネル
# ══════════════════════════════════════════════════════════════
class PropsPanel(QWidget):
    changed=Signal()
    def __init__(self,canvas:Canvas):
        super().__init__(); self.canvas=canvas; self._paths:List[VPath]=[]; self._build(); self.setEnabled(False)

    def _build(self):
        lay=QVBoxLayout(self); lay.setContentsMargins(8,8,8,8); lay.setSpacing(6)
        tabs=QTabWidget(); lay.addWidget(tabs,1)
        # ── スタイル ──
        t1=QWidget(); t1l=QVBoxLayout(t1); t1l.setSpacing(6)
        sg=QGroupBox("ストローク"); sgl=QVBoxLayout(sg)
        self.btn_stroke=QPushButton(); self.btn_stroke.setFixedHeight(26)
        self.btn_stroke.clicked.connect(self._pick_stroke)
        wr=QHBoxLayout(); wr.addWidget(QLabel("太さ"))
        self.spin_w=QDoubleSpinBox(); self.spin_w.setRange(0.1,200); self.spin_w.setSingleStep(0.5)
        self.spin_w.valueChanged.connect(self._on_w); wr.addWidget(self.spin_w)
        sgl.addWidget(self.btn_stroke); sgl.addLayout(wr)
        fg=QGroupBox("塗り"); fgl=QVBoxLayout(fg)
        self.btn_fill=QPushButton("なし"); self.btn_fill.setFixedHeight(26)
        self.btn_fill.clicked.connect(self._pick_fill)
        self.btn_no_fill=QPushButton("塗りなし"); self.btn_no_fill.clicked.connect(self._clear_fill)
        fgl.addWidget(self.btn_fill); fgl.addWidget(self.btn_no_fill)
        og=QGroupBox("不透明度"); ogl=QVBoxLayout(og)
        op_r=QHBoxLayout()
        self.sl_op=QSlider(Qt.Horizontal); self.sl_op.setRange(0,100); self.sl_op.setValue(100)
        self.sl_op.valueChanged.connect(self._on_op)
        self.lbl_op=QLabel("100%"); self.lbl_op.setFixedWidth(36)
        op_r.addWidget(self.sl_op,1); op_r.addWidget(self.lbl_op); ogl.addLayout(op_r)
        self.btn_close_path=QPushButton("パスを閉じる / 開く")
        self.btn_close_path.clicked.connect(self._toggle_close)
        t1l.addWidget(sg); t1l.addWidget(fg); t1l.addWidget(og); t1l.addWidget(self.btn_close_path); t1l.addStretch()
        tabs.addTab(t1,"スタイル")
        # ── トーン ──
        t2=QWidget(); t2l=QVBoxLayout(t2); t2l.setSpacing(6)
        tg=QGroupBox("ベクタートーン"); tgl=QVBoxLayout(tg)
        self.combo_tone=QComboBox()
        for tn in[TONE_NONE,TONE_DOT,TONE_LINE,TONE_CROSS]: self.combo_tone.addItem(tn)
        self.combo_tone.currentTextChanged.connect(self._on_tone_type)
        fr=QHBoxLayout(); fr.addWidget(QLabel("周波数"))
        self.spin_tone_freq=QDoubleSpinBox(); self.spin_tone_freq.setRange(2,200); self.spin_tone_freq.setValue(20)
        self.spin_tone_freq.valueChanged.connect(self._on_tone_freq); fr.addWidget(self.spin_tone_freq)
        sr=QHBoxLayout(); sr.addWidget(QLabel("サイズ"))
        self.spin_tone_size=QDoubleSpinBox(); self.spin_tone_size.setRange(0.5,30); self.spin_tone_size.setValue(3)
        self.spin_tone_size.valueChanged.connect(self._on_tone_size); sr.addWidget(self.spin_tone_size)
        tgl.addWidget(self.combo_tone); tgl.addLayout(fr); tgl.addLayout(sr)
        t2l.addWidget(tg); t2l.addStretch()
        tabs.addTab(t2,"トーン")
        # ── グラデーション ──
        t3=QWidget(); t3l=QVBoxLayout(t3); t3l.setSpacing(6)
        gg=QGroupBox("グラデーション"); ggl=QVBoxLayout(gg)
        self.chk_grad=QCheckBox("グラデーション有効")
        self.chk_grad.toggled.connect(self._on_grad_toggle)
        self.btn_gstart=QPushButton("　開始色　"); self.btn_gstart.clicked.connect(self._pick_gstart)
        self.btn_gend=QPushButton("　終了色　"); self.btn_gend.clicked.connect(self._pick_gend)
        ar=QHBoxLayout(); ar.addWidget(QLabel("角度"))
        self.spin_grad_angle=QDoubleSpinBox(); self.spin_grad_angle.setRange(0,360); self.spin_grad_angle.setValue(0)
        self.spin_grad_angle.valueChanged.connect(self._on_grad_angle); ar.addWidget(self.spin_grad_angle)
        for w in[self.chk_grad,self.btn_gstart,self.btn_gend]: ggl.addWidget(w)
        ggl.addLayout(ar)
        t3l.addWidget(gg); t3l.addStretch()
        tabs.addTab(t3,"グラデ")
        # ── 情報/変形 ──
        t4=QWidget(); t4l=QVBoxLayout(t4); t4l.setSpacing(6)
        self.lbl_info=QLabel("パスを選択してください")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(f"color:{C['fg_dim']};font-size:11px;line-height:1.6;")
        xg=QGroupBox("変形"); xgl=QGridLayout(xg)
        self._tx_spin=QDoubleSpinBox(); self._ty_spin=QDoubleSpinBox()
        self._tw_spin=QDoubleSpinBox(); self._th_spin=QDoubleSpinBox()
        for spin in[self._tx_spin,self._ty_spin,self._tw_spin,self._th_spin]:
            spin.setRange(-99999,99999); spin.setSingleStep(1)
        for row,(lbl,spin) in enumerate([("X",self._tx_spin),("Y",self._ty_spin),("W",self._tw_spin),("H",self._th_spin)]):
            xgl.addWidget(QLabel(lbl),row,0); xgl.addWidget(spin,row,1)
        btn_apply=QPushButton("変形を適用"); btn_apply.setObjectName("accent")
        btn_apply.clicked.connect(self._apply_transform); xgl.addWidget(btn_apply,4,0,1,2)
        t4l.addWidget(self.lbl_info); t4l.addWidget(xg); t4l.addStretch()
        tabs.addTab(t4,"情報/変形")

    def set_paths(self,paths):
        self._paths=list(paths); self.setEnabled(bool(paths))
        if not paths: self.lbl_info.setText("パスを選択してください"); return
        vp=paths[0]
        c=vp.stroke_color
        self.btn_stroke.setStyleSheet(f"background:{c.name()};border:1px solid {C['border']};border-radius:4px;")
        self.spin_w.blockSignals(True); self.spin_w.setValue(vp.stroke_width); self.spin_w.blockSignals(False)
        if vp.fill_color.alpha()>0:
            self.btn_fill.setText(""); self.btn_fill.setStyleSheet(f"background:{vp.fill_color.name()};border:1px solid {C['border']};border-radius:4px;")
        else:
            self.btn_fill.setText("なし"); self.btn_fill.setStyleSheet("")
        self.sl_op.blockSignals(True); self.sl_op.setValue(int(vp.opacity*100)); self.sl_op.blockSignals(False)
        self.lbl_op.setText(f"{int(vp.opacity*100)}%")
        self.combo_tone.blockSignals(True); self.combo_tone.setCurrentText(vp.tone_type); self.combo_tone.blockSignals(False)
        self.spin_tone_freq.blockSignals(True); self.spin_tone_freq.setValue(vp.tone_freq); self.spin_tone_freq.blockSignals(False)
        self.spin_tone_size.blockSignals(True); self.spin_tone_size.setValue(vp.tone_size); self.spin_tone_size.blockSignals(False)
        self.chk_grad.blockSignals(True); self.chk_grad.setChecked(vp.gradient_enabled); self.chk_grad.blockSignals(False)
        self.btn_gstart.setStyleSheet(f"background:{vp.gradient_start.name()};border:1px solid {C['border']};border-radius:4px;")
        self.btn_gend.setStyleSheet(f"background:{vp.gradient_end.name()};border:1px solid {C['border']};border-radius:4px;")
        self.spin_grad_angle.blockSignals(True); self.spin_grad_angle.setValue(vp.gradient_angle); self.spin_grad_angle.blockSignals(False)
        br=vp.bounding_rect()
        self.lbl_info.setText(f"ノード数: {len(vp.nodes)}\n状態: {'閉じたパス' if vp.closed else '開いたパス'}\nブラシ: {vp.brush_name}\nX:{br.x():.1f}  Y:{br.y():.1f}\nW:{br.width():.1f}  H:{br.height():.1f}")
        for spin,val in[(self._tx_spin,br.x()),(self._ty_spin,br.y()),(self._tw_spin,br.width()),(self._th_spin,br.height())]:
            spin.blockSignals(True); spin.setValue(val); spin.blockSignals(False)

    def _pick_stroke(self):
        if not self._paths: return
        c=QColorDialog.getColor(self._paths[0].stroke_color,self,"ストロークカラー")
        if c.isValid():
            for vp in self._paths: vp.stroke_color=QColor(c)
            self.canvas.pen_color=QColor(c); self.set_paths(self._paths); self.canvas.update(); self.changed.emit()

    def _pick_fill(self):
        if not self._paths: return
        init=self._paths[0].fill_color if self._paths[0].fill_color.alpha()>0 else QColor(Qt.white)
        c=QColorDialog.getColor(init,self,"塗りカラー",QColorDialog.ShowAlphaChannel)
        if c.isValid():
            for vp in self._paths: vp.fill_color=QColor(c)
            self.canvas.fill_color=QColor(c); self.set_paths(self._paths); self.canvas.update(); self.changed.emit()

    def _clear_fill(self):
        for vp in self._paths: vp.fill_color=QColor(Qt.transparent)
        self.set_paths(self._paths); self.canvas.update(); self.changed.emit()

    def _on_w(self,v):
        for vp in self._paths: vp.stroke_width=v
        self.canvas.pen_width=v; self.canvas.update(); self.changed.emit()

    def _on_op(self,v):
        self.lbl_op.setText(f"{v}%")
        for vp in self._paths: vp.opacity=v/100
        self.canvas.update(); self.changed.emit()

    def _toggle_close(self):
        for vp in self._paths: vp.closed=not vp.closed
        self.set_paths(self._paths); self.canvas.update(); self.changed.emit()

    def _on_tone_type(self,t):
        for vp in self._paths: vp.tone_type=t
        self.canvas.update(); self.changed.emit()

    def _on_tone_freq(self,v):
        for vp in self._paths: vp.tone_freq=v
        self.canvas.update(); self.changed.emit()

    def _on_tone_size(self,v):
        for vp in self._paths: vp.tone_size=v
        self.canvas.update(); self.changed.emit()

    def _on_grad_toggle(self,v):
        for vp in self._paths: vp.gradient_enabled=v
        self.canvas.update(); self.changed.emit()

    def _pick_gstart(self):
        if not self._paths: return
        c=QColorDialog.getColor(self._paths[0].gradient_start,self,"開始色")
        if c.isValid():
            for vp in self._paths: vp.gradient_start=QColor(c)
            self.btn_gstart.setStyleSheet(f"background:{c.name()};border:1px solid {C['border']};border-radius:4px;")
            self.canvas.update(); self.changed.emit()

    def _pick_gend(self):
        if not self._paths: return
        c=QColorDialog.getColor(self._paths[0].gradient_end,self,"終了色")
        if c.isValid():
            for vp in self._paths: vp.gradient_end=QColor(c)
            self.btn_gend.setStyleSheet(f"background:{c.name()};border:1px solid {C['border']};border-radius:4px;")
            self.canvas.update(); self.changed.emit()

    def _on_grad_angle(self,v):
        for vp in self._paths: vp.gradient_angle=v
        self.canvas.update(); self.changed.emit()

    def _apply_transform(self):
        if not self._paths: return
        vp=self._paths[0]; br=vp.bounding_rect()
        nx,ny=self._tx_spin.value(),self._ty_spin.value()
        nw,nh=self._tw_spin.value(),self._th_spin.value()
        ow,oh=max(br.width(),1),max(br.height(),1); sx,sy=nw/ow,nh/oh
        ox,oy=br.left(),br.top()
        before={vp:[(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out)) for n in vp.nodes]}
        for n in vp.nodes:
            n.pos=QPointF(nx+(n.pos.x()-ox)*sx,ny+(n.pos.y()-oy)*sy)
            n.cp_in=QPointF(nx+(n.cp_in.x()-ox)*sx,ny+(n.cp_in.y()-oy)*sy)
            n.cp_out=QPointF(nx+(n.cp_out.x()-ox)*sx,ny+(n.cp_out.y()-oy)*sy)
        after={vp:[(QPointF(n.pos),QPointF(n.cp_in),QPointF(n.cp_out)) for n in vp.nodes]}
        self.canvas.undo.push(CmdMovePaths(before,after))
        self.set_paths(self._paths); self.canvas.update(); self.changed.emit()

# ══════════════════════════════════════════════════════════════
#  ツールオプションパネル
# ══════════════════════════════════════════════════════════════
class ToolOptionsPanel(QWidget):
    changed=Signal()
    def __init__(self,canvas:Canvas,doc:Document):
        super().__init__(); self.canvas=canvas; self.doc=doc; self._build()

    def _build(self):
        lay=QVBoxLayout(self); lay.setContentsMargins(8,8,8,8); lay.setSpacing(8)
        # ブラシ
        bg=QGroupBox("ブラシ"); bgl=QVBoxLayout(bg)
        self.combo_brush=QComboBox()
        for name in self.doc.brush_presets: self.combo_brush.addItem(name)
        self.combo_brush.currentTextChanged.connect(self._on_brush)
        btn_studio=QPushButton("ブラシスタジオ…"); btn_studio.clicked.connect(self._open_studio)
        bgl.addWidget(self.combo_brush); bgl.addWidget(btn_studio)
        # 手ブレ補正
        smg=QGroupBox("手ブレ補正"); smgl=QVBoxLayout(smg)
        sr=QHBoxLayout(); sr.addWidget(QLabel("強度"))
        self.sl_smooth=QSlider(Qt.Horizontal); self.sl_smooth.setRange(0,10); self.sl_smooth.setValue(3)
        self.sl_smooth.valueChanged.connect(lambda v: setattr(self.canvas,'smoothing',v/10))
        self.lbl_smooth=QLabel("0.3"); self.lbl_smooth.setFixedWidth(28)
        self.sl_smooth.valueChanged.connect(lambda v: self.lbl_smooth.setText(f"{v/10:.1f}"))
        sr.addWidget(self.sl_smooth,1); sr.addWidget(self.lbl_smooth); smgl.addLayout(sr)
        # シンメトリー
        syg=QGroupBox("シンメトリー定規"); sygl=QVBoxLayout(syg)
        self.combo_sym=QComboBox()
        for s in[SYM_NONE,SYM_H,SYM_V,SYM_CROSS]: self.combo_sym.addItem(s)
        self.combo_sym.setCurrentText(self.doc.symmetry)
        self.combo_sym.currentTextChanged.connect(lambda t: (setattr(self.doc,'symmetry',t),self.canvas.update()))
        cx_r=QHBoxLayout(); cx_r.addWidget(QLabel("中心X"))
        self.sp_cx=QDoubleSpinBox(); self.sp_cx.setRange(0,9999); self.sp_cx.setValue(self.doc.sym_cx)
        self.sp_cx.valueChanged.connect(lambda v: setattr(self.doc,'sym_cx',v))
        cx_r.addWidget(self.sp_cx)
        cy_r=QHBoxLayout(); cy_r.addWidget(QLabel("中心Y"))
        self.sp_cy=QDoubleSpinBox(); self.sp_cy.setRange(0,9999); self.sp_cy.setValue(self.doc.sym_cy)
        self.sp_cy.valueChanged.connect(lambda v: setattr(self.doc,'sym_cy',v))
        cy_r.addWidget(self.sp_cy)
        sygl.addWidget(self.combo_sym); sygl.addLayout(cx_r); sygl.addLayout(cy_r)
        # 漫画ツール設定
        mg=QGroupBox("漫画ツール"); mgl=QVBoxLayout(mg)
        btype_r=QHBoxLayout(); btype_r.addWidget(QLabel("フキダシ"))
        self.combo_balloon=QComboBox()
        for bt in[BALLOON_ELLIPSE,BALLOON_RECT,BALLOON_CLOUD,BALLOON_SPIKY]:
            self.combo_balloon.addItem(bt)
        self.combo_balloon.currentTextChanged.connect(lambda t: setattr(self.canvas,'_balloon_type',t))
        btype_r.addWidget(self.combo_balloon)
        fl_r=QHBoxLayout(); fl_r.addWidget(QLabel("集中線本数"))
        self.sp_focus=QSpinBox(); self.sp_focus.setRange(8,256); self.sp_focus.setValue(64)
        self.sp_focus.valueChanged.connect(lambda v: setattr(self.canvas,'_focus_count',v))
        fl_r.addWidget(self.sp_focus)
        # 効果線方向
        sl_r=QHBoxLayout(); sl_r.addWidget(QLabel("効果線方向"))
        self.combo_speed=QComboBox()
        for d in["right","left","down","up"]: self.combo_speed.addItem(d)
        sl_r.addWidget(self.combo_speed)
        btn_speed=QPushButton("効果線を生成"); btn_speed.clicked.connect(self._gen_speed)
        pw_r=QHBoxLayout(); pw_r.addWidget(QLabel("コマ枠幅"))
        self.sp_panel_w=QDoubleSpinBox(); self.sp_panel_w.setRange(0.5,20); self.sp_panel_w.setValue(3)
        self.sp_panel_w.valueChanged.connect(lambda v: setattr(self.canvas,'_panel_border_w',v))
        pw_r.addWidget(self.sp_panel_w)
        for w in[btype_r,fl_r,sl_r,pw_r]: mgl.addLayout(w)
        mgl.addWidget(btn_speed)
        for grp in[bg,smg,syg,mg]: lay.addWidget(grp)
        lay.addStretch()

    def refresh_brushes(self):
        self.combo_brush.blockSignals(True); self.combo_brush.clear()
        for name in self.doc.brush_presets: self.combo_brush.addItem(name)
        self.combo_brush.setCurrentText(self.canvas.brush_name)
        self.combo_brush.blockSignals(False)

    def _on_brush(self,name):
        self.canvas.brush_name=name

    def _open_studio(self):
        dlg=BrushStudioDialog(self,self.doc,self.canvas.brush_name)
        dlg.brush_applied.connect(lambda name,_: (setattr(self.canvas,'brush_name',name),
                                                   self.refresh_brushes()))
        dlg.exec()

    def _gen_speed(self):
        self.canvas._speed_release_dir(self.combo_speed.currentText())

# ══════════════════════════════════════════════════════════════
#  メインウィンドウ
# ══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VektorStudio v2")
        self.resize(1480,940)
        self.doc=Document()
        self.undo=QUndoStack(self); self.undo.setUndoLimit(200)
        self._filepath=None; self._modified=False
        self._build_ui(); self._build_menu(); self._build_toolbar(); self._build_status()
        self.canvas.fit_canvas()

    def _build_ui(self):
        self.canvas=Canvas(self.doc,self.undo)
        self.canvas.status_changed.connect(lambda m: self.lbl_status.setText(m))
        self.canvas.selection_changed.connect(self._on_sel)
        self.canvas.document_changed.connect(self._mark_mod)
        self.setCentralWidget(self.canvas)
        # 左ドック: ツールオプション
        self.tool_opts=ToolOptionsPanel(self.canvas,self.doc)
        ld=QDockWidget("ツールオプション",self); ld.setWidget(self.tool_opts)
        ld.setFeatures(QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea,ld)
        # 右ドック: レイヤー
        self.layer_panel=LayerPanel(self.doc)
        self.layer_panel.changed.connect(self.canvas.update)
        self.layer_panel.changed.connect(self.layer_panel.refresh)
        rd=QDockWidget("レイヤー",self); rd.setWidget(self.layer_panel)
        rd.setFeatures(QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea,rd)
        # 右ドック: プロパティ
        self.props=PropsPanel(self.canvas)
        self.props.changed.connect(self.canvas.update)
        self.props.changed.connect(self._mark_mod)
        pd=QDockWidget("プロパティ",self); pd.setWidget(self.props)
        pd.setFeatures(QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea,pd)
        self.resizeDocks([rd,pd],[260,260],Qt.Horizontal)
        self.resizeDocks([ld],[210],Qt.Horizontal)

    def _build_menu(self):
        mb=self.menuBar()
        # ファイル
        fm=mb.addMenu("ファイル")
        def fa(lbl,sc,fn): a=fm.addAction(lbl); a.setShortcut(sc); a.triggered.connect(fn)
        fa("新規作成","Ctrl+N",self._new_doc)
        fa("開く…","Ctrl+O",self._open_svg)
        fm.addSeparator()
        fa("保存","Ctrl+S",self._save)
        fa("別名保存…","Ctrl+Shift+S",self._save_as)
        fm.addSeparator()
        exp=fm.addMenu("書き出し")
        for fmt in["SVG","PNG","JPEG","WebP","PSD"]:
            a=exp.addAction(f"{fmt}として書き出し…")
            a.triggered.connect(lambda c=False,f=fmt: self._export(f))
        fm.addSeparator()
        fa("終了","Ctrl+Q",self.close)
        # 編集
        em=mb.addMenu("編集")
        u=self.undo.createUndoAction(self,"元に戻す"); u.setShortcut("Ctrl+Z"); em.addAction(u)
        r=self.undo.createRedoAction(self,"やり直し"); r.setShortcut("Ctrl+Y"); em.addAction(r)
        em.addSeparator()
        def ea(lbl,sc,fn): a=em.addAction(lbl); a.setShortcut(sc); a.triggered.connect(fn)
        ea("すべて選択","Ctrl+A",self.canvas._select_all)
        ea("複製","Ctrl+D",self.canvas._duplicate_selected)
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
        # 漫画
        cm=mb.addMenu("漫画")
        a_wt=cm.addAction("Webtoonモード設定…"); a_wt.triggered.connect(self._webtoon_settings)
        a_pp=cm.addAction("パース定規…");          a_pp.triggered.connect(self._persp_settings)
        cm.addSeparator()
        a_fl=cm.addAction("集中線ツールへ"); a_fl.triggered.connect(lambda: self._set_tool(TOOL_FOCUS_LINE))
        a_sl=cm.addAction("効果線を生成");   a_sl.triggered.connect(self.tool_opts._gen_speed)

    def _build_toolbar(self):
        tb=self.addToolBar("ツール"); tb.setMovable(False)
        self._tool_acts={}
        tools=[
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
            ("💬","F2",TOOL_BALLOON,"フキダシ"),
            ("⬜","F3",TOOL_PANEL,"コマ割り"),
            ("⭐","F4",TOOL_FOCUS_LINE,"集中線"),
            ("⚡","F5",TOOL_SPEED_LINE,"効果線"),
        ]
        for lbl,key,tool,tip in tools:
            act=QAction(lbl,self); act.setShortcut(key)
            act.setToolTip(f"{tip} [{key}]"); act.setCheckable(True)
            act.triggered.connect(lambda c=False,t=tool: self._set_tool(t))
            self._tool_acts[tool]=act; tb.addAction(act)
        tb.addSeparator()
        # ペンカラー
        self.lbl_pc=QLabel(); self.lbl_pc.setFixedSize(22,22)
        self.lbl_pc.setStyleSheet(f"background:{C['stroke_def']};border:2px solid {C['border']};border-radius:4px;")
        self.lbl_pc.setCursor(Qt.PointingHandCursor)
        self.lbl_pc.mousePressEvent=lambda e:self._pick_pen_color()
        self.lbl_fc=QLabel(); self.lbl_fc.setFixedSize(22,22)
        self.lbl_fc.setStyleSheet(f"background:transparent;border:2px solid {C['border']};border-radius:4px;")
        self.lbl_fc.setCursor(Qt.PointingHandCursor)
        self.lbl_fc.mousePressEvent=lambda e:self._pick_fill_color()
        tb.addWidget(QLabel(" ")); tb.addWidget(self.lbl_pc); tb.addWidget(QLabel(" 線 "))
        tb.addWidget(self.lbl_fc); tb.addWidget(QLabel(" 塗 "))
        tb.addSeparator()
        self.spin_w=QDoubleSpinBox(); self.spin_w.setRange(0.1,200); self.spin_w.setValue(2.0)
        self.spin_w.setSingleStep(0.5); self.spin_w.setSuffix("px"); self.spin_w.setFixedWidth(76)
        self.spin_w.valueChanged.connect(lambda v: setattr(self.canvas,'pen_width',v))
        tb.addWidget(self.spin_w); tb.addSeparator()
        u=self.undo.createUndoAction(self,"↩"); u.setShortcut("Ctrl+Z"); tb.addAction(u)
        r=self.undo.createRedoAction(self,"↪"); r.setShortcut("Ctrl+Y"); tb.addAction(r)
        self._set_tool(TOOL_PEN)

    def _build_status(self):
        self.status_bar=QStatusBar(); self.setStatusBar(self.status_bar)
        self.lbl_status=QLabel("  VektorStudio v2  |  P:ペン  A:Reshape  V:選択  B:バケツ  F2:フキダシ  F3:コマ割り  F4:集中線")
        self.status_bar.addWidget(self.lbl_status)
        self.lbl_tool=QLabel()
        self.lbl_tool.setStyleSheet(f"color:{C['accent']};padding-right:12px;")
        self.status_bar.addPermanentWidget(self.lbl_tool)

    def _set_tool(self,t):
        for k,a in self._tool_acts.items(): a.setChecked(k==t)
        self.canvas.set_tool(t)
        names={
            TOOL_PEN:"ペン (P)",TOOL_RESHAPE:"Reshape (A)",TOOL_SELECT:"選択 (V)",
            TOOL_HAND:"手のひら (H)",TOOL_ERASER:"消しゴム (E)",
            TOOL_ADD_NODE:"アンカー追加",TOOL_DEL_NODE:"アンカー削除",
            TOOL_WIDTH:"線幅編集 (W)",TOOL_BUCKET:"バケツ (B)",TOOL_SCISSORS:"切断 (C)",
            TOOL_BALLOON:"フキダシ (F2)",TOOL_PANEL:"コマ割り (F3)",
            TOOL_FOCUS_LINE:"集中線 (F4)",TOOL_SPEED_LINE:"効果線 (F5)",
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

    def _on_sel(self,paths): self.props.set_paths(paths)
    def _mark_mod(self):
        self._modified=True
        f=self._filepath.split("/")[-1] if self._filepath else "無題"
        self.setWindowTitle(f"VektorStudio v2* — {f}")

    def _new_doc(self):
        if self._modified:
            r=QMessageBox.question(self,"新規","変更を保存しますか？",
                                   QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
            if r==QMessageBox.Save: self._save()
            elif r==QMessageBox.Cancel: return
        self.doc=Document(); self.canvas.doc=self.doc; self.canvas.selected=[]; self.undo.clear()
        self.layer_panel.doc=self.doc; self.layer_panel.refresh()
        self.tool_opts.doc=self.doc; self.tool_opts.refresh_brushes()
        self._filepath=None; self._modified=False
        self.canvas.fit_canvas(); self.setWindowTitle("VektorStudio v2 — 無題")

    def _open_svg(self):
        path,_=QFileDialog.getOpenFileName(self,"SVGを開く","","SVG Files (*.svg);;All Files (*)")
        if not path: return
        try:
            doc=svg_to_document(open(path,'r',encoding='utf-8').read())
            self.doc=doc; self.canvas.doc=doc; self.canvas.selected=[]; self.undo.clear()
            self.layer_panel.doc=doc; self.layer_panel.refresh()
            self.tool_opts.doc=doc; self.tool_opts.refresh_brushes()
            self._filepath=path; self._modified=False
            self.canvas.fit_canvas()
            self.setWindowTitle(f"VektorStudio v2 — {path.split('/')[-1]}")
        except Exception as e:
            QMessageBox.critical(self,"エラー",f"読み込み失敗:\n{e}")

    def _save(self):
        if self._filepath: self._write_svg(self._filepath)
        else: self._save_as()

    def _save_as(self):
        path,_=QFileDialog.getSaveFileName(self,"保存","untitled.svg","SVG Files (*.svg)")
        if path: self._write_svg(path); self._filepath=path

    def _export(self,fmt: str):
        ext_map={"SVG":"svg","PNG":"png","JPEG":"jpg","WebP":"webp","PSD":"psd"}
        ext=ext_map.get(fmt,"svg")
        filter_map={
            "SVG":"SVG (*.svg)","PNG":"PNG (*.png)",
            "JPEG":"JPEG (*.jpg)","WebP":"WebP (*.webp)","PSD":"Photoshop (*.psd)",
        }
        path,_=QFileDialog.getSaveFileName(self,f"{fmt}として書き出し",f"export.{ext}",filter_map[fmt])
        if not path: return
        if fmt=="SVG":
            self._write_svg(path); return
        if fmt=="PSD":
            self._export_psd(path); return
        # ラスター書き出し (PNG/JPEG/WebP)
        try:
            img=render_to_image(self.doc,scale=2.0,brush_defs=self.doc.brush_presets)
            q_fmt={"PNG":"PNG","JPEG":"JPEG","WebP":"WebP"}.get(fmt,"PNG")
            if not img.save(path,q_fmt,90):
                raise RuntimeError("画像の保存に失敗しました")
            self.status_bar.showMessage(f"書き出し完了: {path}",3000)
        except Exception as e:
            QMessageBox.critical(self,"エラー",f"書き出し失敗:\n{e}")

    def _export_psd(self,path:str):
        """PSD書き出し: レイヤーごとにレンダリングしてPSD形式で保存"""
        def _qimg_to_pil(qimg):
            import numpy as np
            from PIL import Image as PILImage
            qimg=qimg.convertToFormat(qimg.Format_RGBA8888)
            ptr=qimg.bits(); ptr.setsize(qimg.byteCount())
            arr=np.frombuffer(ptr,dtype=np.uint8).reshape(
                (qimg.height(),qimg.width(),4)).copy()
            return PILImage.fromarray(arr,"RGBA")
        try:
            from PIL import Image as PILImage
        except ImportError:
            QMessageBox.critical(self,"エラー",
                "PSD書き出しには Pillow が必要です。\n"
                "pip install Pillow --break-system-packages")
            return
        try:
            from psd_tools import PSDImage
            psd=PSDImage.new("RGBA",(self.doc.width,self.doc.height))
            for layer in self.doc.layers:
                if not layer.visible: continue
                temp=Document(self.doc.width,self.doc.height)
                temp.layers=[layer]
                pil=_qimg_to_pil(render_to_image(temp,scale=1.0,
                                                 brush_defs=self.doc.brush_presets))
                try:
                    pl=psd.make_layer(pil,name=layer.name)
                    pl.opacity=int(layer.opacity*255)
                except Exception:
                    pass  # psd-tools APIバージョン差異は無視
            psd.save(path)
        except Exception:
            # フォールバック: 全合成をPIL経由でPSD保存
            try:
                full=_qimg_to_pil(render_to_image(self.doc,scale=1.0,
                                                  brush_defs=self.doc.brush_presets))
                full.save(path)
            except Exception as e2:
                QMessageBox.critical(self,"エラー",f"PSD書き出し失敗:\n{e2}"); return
        self.status_bar.showMessage(f"PSD書き出し完了: {path}",3000)

    def _write_svg(self,path):
        try:
            open(path,'w',encoding='utf-8').write(document_to_svg(self.doc))
            self._modified=False
            self.setWindowTitle(f"VektorStudio v2 — {path.split('/')[-1]}")
            self.status_bar.showMessage(f"保存: {path}",3000)
        except Exception as e:
            QMessageBox.critical(self,"エラー",f"保存失敗:\n{e}")

    def _webtoon_settings(self):
        dlg=WebtoonDialog(self,self.doc,brush_defs=self.doc.brush_presets)
        if dlg.exec()==QDialog.Accepted: self.canvas.update()

    def _persp_settings(self):
        dlg=PerspDialog(self,self.doc)
        if dlg.exec()==QDialog.Accepted: self.canvas.update()

# ══════════════════════════════════════════════════════════════
#  エントリポイント
# ══════════════════════════════════════════════════════════════
def main():
    app=QApplication(sys.argv)
    app.setApplicationName("VektorStudio"); app.setOrganizationName("VOSE")
    app.setStyleSheet(SS); app.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
    win=MainWindow(); win.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
