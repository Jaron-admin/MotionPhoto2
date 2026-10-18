# 生成 App 图标：python assets/make_icon.py  →  assets/icon.png / assets/icon.icns
from PIL import Image, ImageDraw, ImageFilter
import math, os
D=os.path.dirname(os.path.abspath(__file__))
S=4; W=1024*S
img=Image.new('RGBA',(W,W),(0,0,0,0))
# 渐变背景（macOS 图标网格：824 内容区，圆角 ~185）
m=100*S; size=W-2*m; r=185*S
grad=Image.new('RGBA',(W,W))
gd=ImageDraw.Draw(grad)
c1=(255,159,67); c2=(238,82,120)  # 暖橙 → 玫红
for y in range(W):
    t=y/W
    gd.line([(0,y),(W,y)],fill=tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))+(255,))
mask=Image.new('L',(W,W),0)
ImageDraw.Draw(mask).rounded_rectangle([m,m,W-m,W-m],radius=r,fill=255)
# 阴影
sh=Image.new('RGBA',(W,W),(0,0,0,0))
ImageDraw.Draw(sh).rounded_rectangle([m,m+12*S,W-m,W-m+12*S],radius=r,fill=(0,0,0,70))
sh=sh.filter(ImageFilter.GaussianBlur(18*S))
img=Image.alpha_composite(img,sh)
img.paste(grad,(0,0),mask)
d=ImageDraw.Draw(img)
cx=cy=W//2; white=(255,255,255,255)
# 实心圆点
d.ellipse([cx-70*S,cy-70*S,cx+70*S,cy+70*S],fill=white)
# 实线圆环
R=165*S; w=34*S
d.ellipse([cx-R,cy-R,cx+R,cy+R],outline=white,width=w)
# 外圈点阵（Live 图意象）
R2=270*S; n=28
for k in range(n):
    a=2*math.pi*k/n
    x=cx+R2*math.cos(a); y=cy+R2*math.sin(a); rr=15*S
    d.ellipse([x-rr,y-rr,x+rr,y+rr],fill=white)
img=img.resize((1024,1024),Image.LANCZOS)
img.save(os.path.join(D,'icon.png'))
img.save(os.path.join(D,'icon.icns'),sizes=[(16,16),(32,32),(64,64),(128,128),(256,256),(512,512),(1024,1024)])
