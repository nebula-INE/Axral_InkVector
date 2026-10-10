import os, sys, time
os.environ["QT_QPA_PLATFORM"]="offscreen"
import importlib.util
spec=importlib.util.spec_from_file_location("vs","/tmp/Axral_InkVector/vektorstudio.py"); vs=importlib.util.module_from_spec(spec); spec.loader.exec_module(vs)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QUndoStack
app=QApplication([])
def sq():
    p=vs.VPath()
    for x,y in ((10,10),(290,10),(290,190),(10,190)): p.nodes.append(vs.VNode(QPointF(x,y)))
    p.closed=True; return p
doc=vs.Document(300,200); p=sq(); doc.layers[0].add_path(p)
undo=QUndoStack(); cv=vs.Canvas(doc,undo); cv.resize(800,600); cv._offset=QPointF(0,0); cv._scale=1.0
cv.tool=vs.TOOL_MESH
# 1) 図形をクリック → メッシュ自動作成 + 選択
cv._mesh_press(QPointF(150,100)); assert p.mesh_enabled and len(p.mesh_pts)==9 and cv.selected==[p]
# 色を分かりやすく設定 (中央を赤、他は青)
for i in range(9): p.mesh_colors[i]=QColor("#0000ff")
p.mesh_colors[4]=QColor("#ff0000")
img=vs.render_to_image(doc,1.0); c0=img.pixelColor(150,100); print("center before",c0.name()); assert c0.red()>200
# 2) 中央点(index4)を右下へドラッグ → 赤い領域が移動
t0=time.time(); cv._mesh_press(QPointF(150,100)); assert cv._mesh_drag_i==4
cv._mesh_drag(QPointF(190,130)); cv._mesh_drag(QPointF(260,175)); cv._mesh_release(QPointF(260,175))
print("moved pt",p.mesh_pts[4], "undo stack",undo.count())
img=vs.render_to_image(doc,1.0); a=img.pixelColor(150,100); b=img.pixelColor(190,130); print("after: old center",a.name(),"new center",b.name(),"render s",round(time.time()-t0,2))
assert b.red()>a.red()+60 and b.red()>200
# 3) Undo/Redo
undo.undo(); assert abs(p.mesh_pts[4][0]-0.5)<1e-6 and abs(p.mesh_pts[4][1]-0.5)<1e-6
undo.redo(); assert 0.6<p.mesh_pts[4][0]<0.7
# 4) クリックのみ→色変更 (ダイアログ差し替え)
vs.QColorDialog.getColor=staticmethod(lambda *a,**k:QColor("#00ff00"))
cv._mesh_press(QPointF(10,10)); cv._mesh_release(QPointF(10,10)); assert p.mesh_colors[0].name()=="#00ff00"
undo.undo(); assert p.mesh_colors[0].name()=="#0000ff"
# 5) SVG往復で点位置を保持
svg=vs.document_to_svg(doc); assert 'pts' in svg
d2=vs.svg_to_document(svg); p2=d2.layers[0].paths[0]
assert p2.mesh_enabled and abs(p2.mesh_pts[4][0]-p.mesh_pts[4][0])<1e-4
i2=vs.render_to_image(d2,1.0); assert abs(i2.pixelColor(190,130).red()-b.red())<4
# 6) 旧形式(pts無し)でも読める
import re
svg_old=re.sub(r',\s*"pts":\s*\[\[.*?\]\]','',svg.replace("&quot;",'"'),flags=re.S)
try:
    d3=vs.svg_to_document(svg_old); print("legacy ok",len(d3.layers[0].paths[0].mesh_pts))
except Exception as e: print("legacy parse err",e)
# 7) オーバーレイ描画 + サイズ変更でリサンプル
cv.grab()
w=vs.MainWindow(); pp=w.findChildren(vs.PropsPanel)[0]; pp.set_paths([p]); pp.spin_mesh_c.setValue(4)
assert len(p.mesh_pts)==12 and len(p.mesh_colors)==12 and p.mesh_pts[0]==(0.0,0.0)
pp._reset_mesh_pts(); assert abs(p.mesh_pts[5][0]-1/3)<1e-6
print("mesh2 ALL OK")
