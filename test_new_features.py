import os, sys
os.environ["QT_QPA_PLATFORM"]="offscreen"
sys.path.insert(0,"/tmp/Axral_InkVector")
import importlib.util
spec=importlib.util.spec_from_file_location("vs","/tmp/Axral_InkVector/vektorstudio.py"); vs=importlib.util.module_from_spec(spec); spec.loader.exec_module(vs)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QUndoStack
app=QApplication([])
def line(pts):
    p=vs.VPath()
    for x,y in pts: p.nodes.append(vs.VNode(QPointF(x,y)))
    return p
# 1) 開いたパスの交差点消しゴム: 水平線が縦線を越えてはみ出す
h=line([(0,100),(300,100)]); v=line([(200,0),(200,200)])
r=vs.trim_at_intersections(h,[v],QPointF(250,100))   # はみ出し側をクリック
assert len(r)==1 and abs(r[0].nodes[-1].pos.x()-200)<1.5, [ (n.pos.x()) for n in r[0].nodes]
r=vs.trim_at_intersections(h,[v],QPointF(50,100)); assert len(r)==1 and abs(r[0].nodes[0].pos.x()-200)<1.5
# 中間区間 (2本の縦線の間) → 2分割
v2=line([(100,0),(100,200)])
r=vs.trim_at_intersections(h,[v,v2],QPointF(150,100)); assert len(r)==2, len(r)
assert vs.trim_at_intersections(h,[line([(0,300),(300,300)])],QPointF(50,100)) is None
print("trim open OK")
# 曲線(ベジェ)でも交点位置が正しい
c=vs.VPath(); c.nodes=[vs.VNode(QPointF(0,0),QPointF(0,0),QPointF(100,0)),vs.VNode(QPointF(200,100),QPointF(200,0),QPointF(200,100))]
cut=line([(120,-50),(120,150)])
r=vs.trim_at_intersections(c,[cut],QPointF(190,95)); assert len(r)==1
print("curve piece end",r[0].nodes[0].pos.x(),r[0].nodes[-1].pos.x())
# 2) 閉パス(矩形)を縦線2本で → 外側を消す/内側を消す
rect=line([(0,0),(200,0),(200,100),(0,100)]); rect.closed=True
a=line([(50,-20),(50,120)]); b=line([(150,-20),(150,120)])
r=vs.trim_at_intersections(rect,[a,b],QPointF(100,0))   # 上辺の内側区間を消す
assert len(r)==1, len(r); print("closed trim nodes",len(r[0].nodes))
r2=vs.trim_at_intersections(rect,[a,b],QPointF(100,100)); assert len(r2)==1
# 3) アンカー軽量化
import math
dense=vs.VPath()
for i in range(61):
    x=i*5; dense.nodes.append(vs.VNode(QPointF(x,50+30*math.sin(x/60))))
nodes,pres,removed=vs.simplify_vpath(dense,1.0); print("simplify",len(dense.nodes),"->",len(nodes))
assert removed>20 and len(nodes)>=2
# 誤差検証
d=vs.VPath(); d.nodes=nodes
pts,_=vs._flatten_vpath(d,24); ref,_=vs._flatten_vpath(dense,24)
err=max(vs._dist_to_polyline(p,pts) for p in ref); print("max err",round(err,2)); assert err<2.5
# 4) メッシュ描画 + SVG往復
doc=vs.Document(300,200); sq=line([(10,10),(290,10),(290,190),(10,190)]); sq.closed=True
sq.mesh_enabled=True; sq.mesh_cols=3; sq.mesh_rows=2
sq.mesh_colors=[QColor("#ff0000"),QColor("#00ff00"),QColor("#0000ff"),QColor("#ffff00"),QColor("#00ffff"),QColor("#ff00ff")]
doc.layers[0].add_path(sq)
img=vs.render_to_image(doc,1.0)
tl=img.pixelColor(20,20); br=img.pixelColor(280,180); print("TL",tl.name(),"BR",br.name())
assert tl.red()>200 and tl.green()<60 and br.blue()>200
svg=vs.document_to_svg(doc); assert "data-mesh" in svg
d2=vs.svg_to_document(svg); p2=d2.layers[0].paths[0]; assert p2.mesh_enabled and len(p2.mesh_colors)==6 and p2.mesh_cols==3
img2=vs.render_to_image(d2,1.0); assert abs(img2.pixelColor(20,20).red()-tl.red())<3
print("mesh+svg OK")
# 5) Canvas: 回転付き座標往復・Undo・交差点消しゴム経由
undo=QUndoStack(); cv=vs.Canvas(doc,undo); cv.resize(800,600)
cv._rot=30; cv._scale=1.7; cv._offset=QPointF(120,80)
for p in (QPointF(10,20),QPointF(250,150)):
    q=cv.to_scr(p); back=cv.to_doc(q); assert abs(back.x()-p.x())<1e-6 and abs(back.y()-p.y())<1e-6
cv._rot=0; cv._scale=1.0; cv._offset=QPointF(0,0)
doc2=vs.Document(400,300); hh=line([(0,100),(300,100)]); vv=line([(200,0),(200,200)])
doc2.layers[0].add_path(hh); doc2.layers[0].add_path(vv)
cv2=vs.Canvas(doc2,undo); cv2.resize(800,600); cv2._offset=QPointF(0,0)
cv2._trim_press(QPointF(260,100))
assert len(doc2.layers[0].paths)==2 and any(abs(p.nodes[-1].pos.x()-200)<1.5 for p in doc2.layers[0].paths if p is not vv), "trim via canvas"
undo.undo(); assert any(abs(p.nodes[-1].pos.x()-300)<1e-6 for p in doc2.layers[0].paths); print("canvas trim+undo OK")
# 6) 配色提案 / バルーン配置
pal=vs.suggest_palettes(QColor("#3a7bd5")); assert len(pal)==6 and len(pal["補色"])==2
pan=vs.make_panel(QRectF(0,0,400,300)); doc3=vs.Document(500,400); doc3.layers[0].add_path(pan)
obj=line([(280,40),(380,40),(380,120),(280,120)]); obj.closed=True; doc3.layers[0].add_path(obj)
rc=vs.suggest_balloon_rect(doc3,pan); print("balloon rect",rc); assert not rc.intersects(QRectF(280,40,100,80))
print("ALL OK")
