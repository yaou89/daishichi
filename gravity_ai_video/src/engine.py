# -*- coding: utf-8 -*-
"""描画ヘルパー (skia-python)。"""
import math
import numpy as np
import skia

W, H, FPS = 1920, 1080, 30
FONT_DIR = "/usr/share/fonts/opentype/noto/"
_TF = {}


def tf(weight="Black"):
    if weight not in _TF:
        _TF[weight] = skia.Typeface.MakeFromFile(f"{FONT_DIR}NotoSansCJK-{weight}.ttc", 0)
    return _TF[weight]


# ---------- 色・数値 ----------
PAL = dict(
    bg0="#050816", bg1="#0E1638", cyan="#3DF5FF", blue="#4C7DFF", mag="#FF4FD8",
    amber="#FFC24B", red="#FF3B5C", green="#41F2A0", white="#FFFFFF", yellow="#FFE14D",
    gray="#8A93B8", dark="#0A0F24",
)


def col(h, a=1.0):
    if h in PAL:
        h = PAL[h]
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return skia.ColorSetARGB(int(max(0, min(1, a)) * 255), r, g, b)


def mix(h1, h2, k, a=1.0):
    h1 = PAL.get(h1, h1).lstrip("#")
    h2 = PAL.get(h2, h2).lstrip("#")
    c1 = [int(h1[i:i + 2], 16) for i in (0, 2, 4)]
    c2 = [int(h2[i:i + 2], 16) for i in (0, 2, 4)]
    c = [int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3)]
    return skia.ColorSetARGB(int(a * 255), *c)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, k):
    return a + (b - a) * k


def ss(x):  # smoothstep 0..1
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ramp(t, t0, d=0.6):
    return ss((t - t0) / d) if d > 0 else float(t >= t0)


def eob(x):  # ease out back
    x = clamp(x)
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def eoc(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


# ---------- ペイント ----------
def P(c="white", a=1.0, stroke=None, blur=None, shader=None, cap=True, dash=None):
    p = skia.Paint(AntiAlias=True)
    p.setColor(col(c, a) if isinstance(c, str) else c)
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        if cap:
            p.setStrokeCap(skia.Paint.kRound_Cap)
            p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if shader is not None:
        p.setShader(shader)
        if not isinstance(c, str) or True:
            p.setAlphaf(a)
    if dash:
        p.setPathEffect(skia.DashPathEffect.Make(dash[0], dash[1] if len(dash) > 1 else 0))
    return p


def lin(x0, y0, x1, y1, cols, pos=None):
    return skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(x1, y1)],
                                          [col(x) if isinstance(x, str) else x for x in cols], pos)


def rad(x, y, r, cols, pos=None):
    return skia.GradientShader.MakeRadial(skia.Point(x, y), max(r, 0.1),
                                          [col(x) if isinstance(x, str) else x for x in cols], pos)


def R(x, y, w, h):
    return skia.Rect.MakeXYWH(x, y, w, h)


def rrect(c, x, y, w, h, r, paint):
    c.drawRRect(skia.RRect.MakeRectXY(R(x, y, w, h), r, r), paint)


def glow(c, x, y, r, color="cyan", a=1.0):
    c.drawCircle(x, y, r, P(shader=rad(x, y, r, [col(color, a), col(color, a * 0.35), col(color, 0)], [0, 0.35, 1])))


class layer:
    """with layer(c, alpha): ... グループ不透明度"""

    def __init__(self, c, alpha=1.0):
        self.c, self.a = c, alpha

    def __enter__(self):
        self.c.saveLayer(None, skia.Paint(Alphaf=clamp(self.a)))
        return self.c

    def __exit__(self, *a):
        self.c.restore()


class xf:
    """with xf(c, tx, ty, rot=0, sc=1): 座標変換"""

    def __init__(self, c, tx=0, ty=0, rot=0, sc=1.0, sy=None):
        self.c, self.args = c, (tx, ty, rot, sc, sy)

    def __enter__(self):
        tx, ty, rot, sc, sy = self.args
        self.c.save()
        self.c.translate(tx, ty)
        if rot:
            self.c.rotate(rot)
        if sc != 1 or sy is not None:
            self.c.scale(sc, sy if sy is not None else sc)
        return self.c

    def __exit__(self, *a):
        self.c.restore()


# ---------- テキスト ----------
def font(size, weight="Black"):
    f = skia.Font(tf(weight), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def text_w(s, size, weight="Black"):
    return font(size, weight).measureText(s)


def text(c, s, x, y, size, color="white", a=1.0, weight="Black", align="center",
         stroke=0, stroke_col="#000000", glow_col=None, glow_r=18, spacing=0):
    if not s or a <= 0:
        return 0
    f = font(size, weight)
    w = f.measureText(s) + spacing * (len(s) - 1)
    if align == "center":
        x0 = x - w / 2
    elif align == "right":
        x0 = x - w
    else:
        x0 = x
    if spacing:
        blobs = []
        cx = x0
        for ch in s:
            blobs.append((ch, cx))
            cx += f.measureText(ch) + spacing
    else:
        blobs = [(s, x0)]
    for ch, cx in blobs:
        blob = skia.TextBlob.MakeFromString(ch, f)
        if blob is None:
            continue
        if glow_col:
            c.drawTextBlob(blob, cx, y, P(glow_col, a * 0.8, blur=glow_r))
        if stroke:
            c.drawTextBlob(blob, cx, y, P(stroke_col, a, stroke=stroke))
        c.drawTextBlob(blob, cx, y, P(color, a) if isinstance(color, str) else _pa(color, a))
    return w


def _pa(colint, a):
    p = skia.Paint(AntiAlias=True)
    p.setColor(colint)
    p.setAlphaf(a)
    return p


# ---------- 背景・共通オブジェクト ----------
def bg_grad(c, top="bg1", bottom="bg0"):
    c.drawRect(R(0, 0, W, H), P(shader=lin(0, 0, 0, H, [top, bottom])))


def vignette(c, a=0.65):
    c.drawRect(R(0, 0, W, H), P(shader=rad(W / 2, H / 2, W * 0.75, [col("#000000", 0), col("#000000", 0), col("#000000", a)], [0, 0.55, 1])))


class Stars:
    def __init__(self, n=260, seed=1, w=W, h=H):
        rng = np.random.default_rng(seed)
        self.x = rng.uniform(0, w, n)
        self.y = rng.uniform(0, h, n)
        self.r = rng.uniform(0.6, 2.2, n) ** 1.5
        self.ph = rng.uniform(0, 6.28, n)
        self.sp = rng.uniform(0.5, 2.5, n)

    def draw(self, c, t, a=1.0, dx=0.0, dy=0.0, w=W, h=H):
        p = P("white")
        for i in range(len(self.x)):
            tw = 0.55 + 0.45 * math.sin(self.ph[i] + t * self.sp[i])
            p.setAlphaf(clamp(a * tw))
            c.drawCircle((self.x[i] + dx * self.r[i]) % w, (self.y[i] + dy * self.r[i]) % h, self.r[i], p)


class Dust:
    """ふわふわ漂う光の粒"""

    def __init__(self, n=70, seed=3, color="cyan"):
        rng = np.random.default_rng(seed)
        self.x = rng.uniform(0, W, n)
        self.y = rng.uniform(0, H, n)
        self.r = rng.uniform(1.5, 4.5, n)
        self.v = rng.uniform(8, 30, n)
        self.ph = rng.uniform(0, 6.28, n)
        self.color = color

    def draw(self, c, t, a=0.6, up=1.0):
        for i in range(len(self.x)):
            x = (self.x[i] + 20 * math.sin(t * 0.5 + self.ph[i])) % W
            y = (self.y[i] - up * self.v[i] * t) % H
            c.drawCircle(x, y, self.r[i] * 2.5, P(self.color, a * 0.25, blur=self.r[i] * 1.5))
            c.drawCircle(x, y, self.r[i] * 0.6, P("white", a * 0.8))


def hud_corners(c, x, y, w, h, color="cyan", a=0.8, L=30, sw=3):
    p = P(color, a, stroke=sw)
    for (px, py, dx, dy) in [(x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)]:
        c.drawLine(px, py, px + dx * L, py, p)
        c.drawLine(px, py, px, py + dy * L, p)


def panel(c, x, y, w, h, a=1.0, color="cyan", fill="#0A1230", fa=0.72, r=14):
    rrect(c, x, y, w, h, r, P(fill, fa * a))
    rrect(c, x, y, w, h, r, P(color, 0.55 * a, stroke=2))
    hud_corners(c, x - 6, y - 6, w + 12, h + 12, color, 0.9 * a, L=22, sw=3)


def ring_pulse(c, x, y, t, period=1.4, rmax=160, color="cyan", a=1.0, n=3):
    for k in range(n):
        ph = ((t / period) + k / n) % 1.0
        c.drawCircle(x, y, 10 + rmax * ph, P(color, a * (1 - ph) * 0.8, stroke=3 + 3 * (1 - ph)))


# ---------- 人物ピクトグラム ----------
POSES = {
    "stand": dict(la1=8, la2=4, ra1=-8, ra2=-4, ll1=4, ll2=0, rl1=-4, rl2=0),
    "relax": dict(la1=30, la2=60, ra1=-30, ra2=-60, ll1=10, ll2=-10, rl1=-10, rl2=10),
    "up": dict(la1=160, la2=170, ra1=-160, ra2=-170, ll1=10, ll2=0, rl1=-10, rl2=0),
    "jump": dict(la1=150, la2=175, ra1=120, ra2=140, ll1=30, ll2=-40, rl1=-20, rl2=-60),
    "sit": dict(la1=20, la2=70, ra1=10, ra2=60, ll1=90, ll2=0, rl1=85, rl2=-5),
    "push": dict(la1=75, la2=85, ra1=65, ra2=80, ll1=-25, ll2=-10, rl1=20, rl2=5),
    "swim": dict(la1=170, la2=175, ra1=110, ra2=100, ll1=-10, ll2=-20, rl1=10, rl2=20),
    "fall": dict(la1=120, la2=150, ra1=-110, ra2=-140, ll1=40, ll2=10, rl1=-30, rl2=-10),
}


def walk_pose(ph, amp=28):
    s = math.sin(ph)
    return dict(la1=-amp * s, la2=-amp * s + 25, ra1=amp * s, ra2=amp * s + 25,
                ll1=amp * s, ll2=amp * s - max(0, 30 * math.sin(ph + 1.2)),
                rl1=-amp * s, rl2=-amp * s - max(0, 30 * math.sin(ph + 1.2 + math.pi)))


def blend_pose(p1, p2, k):
    return {key: lerp(p1[key], p2[key], k) for key in p1}


def person(c, x, y, s=1.0, color="#E8ECFF", pose="stand", rot=0, a=1.0, back="#9AA3C8", hair=None, bent=0):
    """(x,y) = 腰の位置。rot = 全身の回転(度)。s=1 で身長約190px"""
    pz = POSES[pose] if isinstance(pose, str) else pose
    U = 38 * s
    with xf(c, x, y, rot), layer(c, a):
        def limb(a1, a2, ox, oy, l1, l2, colr):
            r1 = math.radians(a1)
            r2 = math.radians(a2)
            x1, y1 = ox + math.sin(r1) * l1, oy + math.cos(r1) * l1
            x2, y2 = x1 + math.sin(r2) * l2, y1 + math.cos(r2) * l2
            pth = skia.Path()
            pth.moveTo(ox, oy)
            pth.lineTo(x1, y1)
            pth.lineTo(x2, y2)
            c.drawPath(pth, P(colr, stroke=0.55 * U))
        sh = (math.sin(math.radians(bent)) * 2.0 * U, -2.0 * U * math.cos(math.radians(bent)))
        limb(pz["ra1"], pz["ra2"], sh[0], sh[1], 1.05 * U, 0.95 * U, back)
        limb(pz["rl1"], pz["rl2"], 0, 0, 1.3 * U, 1.3 * U, back)
        c.drawLine(0, 0, sh[0], sh[1], P(color, stroke=0.95 * U))
        hx = math.sin(math.radians(bent)) * 3.0 * U
        hy = -3.0 * U * math.cos(math.radians(bent))
        c.drawCircle(hx, hy, 0.62 * U, P(color))
        if hair:
            c.drawArc(skia.Rect(hx - 0.66 * U, hy - 0.66 * U, hx + 0.66 * U, hy + 0.66 * U), 180, 180, True, P(hair))
        limb(pz["ll1"], pz["ll2"], 0, 0, 1.3 * U, 1.3 * U, color)
        limb(pz["la1"], pz["la2"], sh[0], sh[1], 1.05 * U, 0.95 * U, color)


# ---------- その他オブジェクト ----------
def apple(c, x, y, r=26, a=1.0, rot=0):
    with xf(c, x, y, rot), layer(c, a):
        c.drawCircle(-r * 0.32, 0, r * 0.82, P(shader=rad(-r * 0.5, -r * 0.4, r * 1.3, ["#FF6B6B", "#D81E2C", "#7A0A16"])))
        c.drawCircle(r * 0.32, 0, r * 0.82, P(shader=rad(0, -r * 0.4, r * 1.3, ["#FF6B6B", "#D81E2C", "#7A0A16"])))
        c.drawLine(0, -r * 0.6, r * 0.15, -r * 1.15, P("#5A3A1A", stroke=r * 0.14))
        leaf = skia.Path()
        leaf.moveTo(r * 0.1, -r * 0.95)
        leaf.quadTo(r * 0.7, -r * 1.5, r * 0.95, -r * 0.95)
        leaf.quadTo(r * 0.5, -r * 0.7, r * 0.1, -r * 0.95)
        c.drawPath(leaf, P("#3FBF5A"))
        c.drawCircle(-r * 0.45, -r * 0.35, r * 0.18, P("white", 0.5))


def earth(c, x, y, r, t=0, a=1.0, atm=True):
    with layer(c, a):
        if atm:
            c.drawCircle(x, y, r * 1.12, P(shader=rad(x, y, r * 1.12, [col("#4CC3FF", 0.0), col("#4CC3FF", 0.0), col("#4CC3FF", 0.45), col("#4CC3FF", 0)], [0, 0.86, 0.9, 1])))
        c.save()
        pth = skia.Path()
        pth.addCircle(x, y, r)
        c.clipPath(pth, doAntiAlias=True)
        c.drawCircle(x, y, r, P(shader=rad(x - r * 0.3, y - r * 0.3, r * 1.5, ["#3E8BFF", "#1546A8", "#061538"])))
        # 大陸 (簡易) - 横に流れる
        rng = np.random.default_rng(7)
        for k in range(14):
            bx = rng.uniform(-1.2, 1.2)
            by = rng.uniform(-0.8, 0.8)
            br = rng.uniform(0.12, 0.32)
            px = ((bx + t * 0.04) % 2.4) - 1.2
            cxp = x + px * r
            sq = math.sqrt(max(0.05, 1 - px * px))
            c.drawOval(skia.Rect(cxp - br * r * sq, y + by * r - br * r * 0.7, cxp + br * r * sq, y + by * r + br * r * 0.7), P("#3FAE6A", 0.85))
        for k in range(10):
            bx = rng.uniform(-1.2, 1.2)
            by = rng.uniform(-0.9, 0.9)
            px = ((bx + t * 0.06) % 2.4) - 1.2
            c.drawOval(skia.Rect(x + px * r - r * 0.25, y + by * r - r * 0.04, x + px * r + r * 0.25, y + by * r + r * 0.04), P("white", 0.45, blur=r * 0.02))
        # 夜側の影
        c.drawCircle(x, y, r, P(shader=rad(x - r * 0.45, y - r * 0.45, r * 2.0, [col("#000000", 0), col("#000000", 0.15), col("#000000", 0.85)], [0, 0.5, 1])))
        c.restore()


def magnet(c, x, y, s=1.0, a=1.0):
    with xf(c, x, y, 0, s), layer(c, a):
        pth = skia.Path()
        pth.moveTo(-90, 0)
        pth.lineTo(-90, -60)
        pth.arcTo(skia.Rect(-90, -150, 90, 30), 180, 180, False)
        pth.lineTo(90, 0)
        c.drawPath(pth, P("#D9303F", stroke=56, cap=False))
        c.drawRect(R(-118, -10, 56, 50), P("#C9D2E6"))
        c.drawRect(R(62, -10, 56, 50), P("#C9D2E6"))
        c.drawRect(R(-118, 30, 56, 6), P("#7C88A8"))
        c.drawRect(R(62, 30, 56, 6), P("#7C88A8"))
        text(c, "N", -90, 30, 30, "#1A2240")
        text(c, "S", 90, 30, 30, "#1A2240")


def paperclip(c, x, y, s=1.0, rot=0, a=1.0):
    with xf(c, x, y, rot, s), layer(c, a):
        pth = skia.Path()
        pth.moveTo(-40, 10)
        pth.lineTo(40, 10)
        pth.arcTo(skia.Rect(25, -10, 55, 20), 90, -180, False)
        pth.lineTo(-30, -10)
        pth.arcTo(skia.Rect(-48, -10, -24, 10), 270, -180, False)
        pth.lineTo(30, 0)
        c.drawPath(pth, P("#DDE6F5", stroke=5))


def car(c, x, y, s=1.0, color="#FF4FD8", dirn=1, a=1.0, t=0):
    with xf(c, x, y, 0, s * dirn, s), layer(c, a):
        c.drawOval(skia.Rect(-70, 26, 70, 46), P("cyan", 0.55, blur=10))
        rrect(c, -80, -16, 160, 42, 21, P(shader=lin(0, -16, 0, 26, [color, mix(color, "#000000", 0.55)])))
        body = skia.Path()
        body.moveTo(-42, -14)
        body.quadTo(-20, -44, 18, -42)
        body.quadTo(44, -40, 56, -14)
        body.close()
        c.drawPath(body, P(mix(color, "#FFFFFF", 0.2)))
        c.drawPath(body, P("#9FEAFF", 0.55))
        c.drawCircle(78, 4, 6, P("#FFF7C2"))
        c.drawCircle(78, 4, 22, P("#FFF7C2", 0.35, blur=12))
        c.drawCircle(-78, 4, 5, P("#FF3B5C"))
        for k in (-40, 40):
            c.drawOval(skia.Rect(k - 26, 22, k + 26, 32), P("cyan", 0.7 + 0.3 * math.sin(t * 8 + k)))


def cardboard(c, x, y, s=1.0, rot=0, a=1.0):
    with xf(c, x, y, rot, s), layer(c, a):
        c.drawRect(R(-40, -32, 80, 64), P("#C8955A"))
        c.drawRect(R(-40, -32, 80, 14), P("#B07E46"))
        c.drawRect(R(-7, -32, 14, 64), P("#E6C79A", 0.8))
        c.drawRect(R(-40, -32, 80, 64), P("#7A5530", stroke=2))
