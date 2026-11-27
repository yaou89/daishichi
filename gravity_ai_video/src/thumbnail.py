# -*- coding: utf-8 -*-
"""YouTube サムネイル (1280x720)"""
import os, sys
import numpy as np
import skia
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import engine
from engine import *
from scenes import grid_mesh, STARS, person, car

OUT = sys.argv[1] if len(sys.argv) > 1 else "thumbnail.png"
arr = np.zeros((H, W, 4), np.uint8)
c = skia.Surface(arr).getCanvas()
bg_grad(c, "#0A1236", "#02030A")
STARS.draw(c, 1.0, 0.9)
grid_mesh(c, 0, 2.5, 7, 2.2, "cyan", 0.45)
glow(c, 1450, 560, 420, "#4C7DFF", 0.45)
earth(c, 1450, 600, 230, 3)
# 浮かぶ人と車
for i, (x, y, r) in enumerate([(1180, 300, -20), (1700, 260, 25), (1600, 880, 160)]):
    glow(c, x, y, 120, "cyan", 0.3)
    person(c, x, y, 0.8, "#FFFFFF", "up" if i % 2 else "swim", rot=r, back="#C8D0F0", hair="#2A1A10")
car(c, 1250, 860, 1.0, "#FF4FD8", 1, 1, 0.3)
apple(c, 1820, 470, 46, rot=20)
# 文字
text(c, "もしもAIが", 60, 250, 120, "white", align="left", stroke=22, stroke_col="#0A0F24")
text(c, "重力を", 60, 450, 210, "yellow", align="left", stroke=28, stroke_col="#0A0F24", glow_col="#FFE14D", glow_r=30)
text(c, "操れたら", 60, 660, 190, "white", align="left", stroke=28, stroke_col="#0A0F24")
rrect(c, 60, 760, 760, 110, 24, P("red"))
text(c, "世界はこう変わる", 440, 845, 76, "white")
text(c, "0.00G", 1870, 140, 90, "cyan", align="right", glow_col="#3DF5FF", stroke=10, stroke_col="#0A0F24")
vignette(c, 0.5)
Image.fromarray(arr[:, :, :3]).resize((1280, 720), Image.LANCZOS).save(OUT)
print(OUT)
