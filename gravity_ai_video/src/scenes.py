# -*- coding: utf-8 -*-
"""各シーンの描画。draw(c, t, S) -> 任意で {"g": 値} を返す (G-METER 表示用)。
S.L[i] = i行目ナレーション開始(シーン内秒), S.E[i] = 終了, S.dur = シーン長
"""
import math
import numpy as np
import skia
from engine import *

STARS = Stars(320, 11)
STARS2 = Stars(160, 12)
DUST = Dust(60, 5)


# ============================================================
# s00 フック：夜の丘、リンゴが落ちる → 止まる
# ============================================================
def tree(c, x, y, s=1.0):
    with xf(c, x, y, 0, s):
        tr = skia.Path()
        tr.moveTo(-26, 0)
        tr.lineTo(-16, -260)
        tr.lineTo(16, -260)
        tr.lineTo(30, 0)
        tr.close()
        c.drawPath(tr, P("#060912"))
        c.drawLine(0, -200, 120, -330, P("#060912", stroke=22))
        c.drawLine(0, -230, -110, -340, P("#060912", stroke=20))
        for (dx, dy, r) in [(0, -380, 170), (-150, -330, 120), (150, -320, 130), (70, -460, 120), (-80, -470, 110), (210, -390, 90), (-220, -400, 80)]:
            c.drawCircle(dx, dy, r, P("#080C1A"))
        c.drawCircle(-40, -420, 260, P("#3DF5FF", 0.03, blur=60))


def s00_hook(c, t, S):
    bg_grad(c, "#0B1640", "#03050F")
    STARS.draw(c, t, 0.9, dx=-t * 2)
    # 月
    glow(c, 1500, 220, 220, "#BFD8FF", 0.25)
    c.drawCircle(1500, 220, 70, P(shader=rad(1480, 200, 90, ["#FFFFFF", "#C9D6F0"])))
    # 丘
    hill = skia.Path()
    hill.moveTo(0, 860)
    hill.cubicTo(500, 760, 1200, 800, 1920, 880)
    hill.lineTo(1920, 1080)
    hill.lineTo(0, 1080)
    hill.close()
    c.drawPath(hill, P("#060A16"))
    c.drawPath(hill, P("cyan", 0.25, stroke=2))
    zoom = 1.0 + 0.04 * t / S.dur
    c.save()
    c.translate(W / 2, H / 2)
    c.scale(zoom, zoom)
    c.translate(-W / 2, -H / 2)
    tree(c, 640, 830, 1.15)
    # 座る人
    person(c, 860, 800, 0.85, "#111733", "sit", back="#0C1128")
    # 1つ目のリンゴ：落ちて着地
    t1 = 2.2
    ax, ay0, ay1 = 760, 470, 812
    if t < t1:
        apple(c, ax, ay0, 22)
    else:
        tt = t - t1
        y = ay0 + 0.5 * 1400 * tt * tt
        if y >= ay1:
            # バウンド
            tb = tt - math.sqrt(2 * (ay1 - ay0) / 1400)
            y = ay1 - max(0, 90 * math.sin(min(math.pi, tb * 6))) * math.exp(-tb * 2)
            xoff = min(60, tb * 50)
        else:
            xoff = 0
        apple(c, ax + xoff, y, 22, rot=xoff * 2)
    # 2つ目のリンゴ：止まって浮く
    tf_ = S.L[2] + 0.2
    tz = S.L[2] + 0.95
    bx, by0 = 560, 440
    if t < tf_:
        apple(c, bx, by0, 22)
    else:
        tt = min(t, tz) - tf_
        y = by0 + 0.5 * 1400 * tt * tt
        if t > tz:
            k = t - tz
            y = y - 70 * eoc(k / 3) - 8 * math.sin(k * 2)
            ring_pulse(c, bx, y, k, 1.6, 220, "cyan", clamp(k * 2) * 0.9)
            glow(c, bx, y, 140, "cyan", 0.35 * clamp(k * 2))
        apple(c, bx, y, 22, rot=(t - tf_) * 20)
    c.restore()
    # 4行目: 周囲の石や葉が浮かび上がる
    if t > S.L[3] - 0.5:
        k = t - (S.L[3] - 0.5)
        rng = np.random.default_rng(4)
        for i in range(40):
            x = rng.uniform(100, 1800)
            y0 = rng.uniform(820, 1060)
            v = rng.uniform(25, 90)
            d = rng.uniform(0, 1.5)
            kk = max(0, k - d)
            yy = y0 - v * kk - 30 * eoc(kk)
            r = rng.uniform(4, 13)
            rot = kk * rng.uniform(-60, 60)
            with xf(c, x, yy, rot):
                c.drawRect(R(-r, -r * 0.6, 2 * r, 1.2 * r), P(["#2A3150", "#3FAE6A", "#5B4A3A"][i % 3], clamp(kk * 2)))
        # HUD 文字
        with layer(c, ramp(t, S.L[2] + 1.1, 0.4)):
            text(c, "GRAVITY OVERRIDE", 560, 300, 30, "cyan", weight="Bold", spacing=6, glow_col="cyan")
    if S.L[2] + 1.0 < t < S.L[3] - 0.5:
        with layer(c, ramp(t, S.L[2] + 1.1, 0.4)):
            text(c, "GRAVITY OVERRIDE", 560, 300, 30, "cyan", weight="Bold", spacing=6, glow_col="cyan")
    # 冒頭の年号テロップ
    with layer(c, ramp(t, 0.3, 0.6) * (1 - ramp(t, S.L[1] - 0.3, 0.5))):
        text(c, "1666年ごろ ― イングランド", 960, 160, 40, "white", weight="Medium", spacing=4)
    vignette(c, 0.7)


# ============================================================
# s01 タイトル
# ============================================================
def grid_mesh(c, t, mass_x=0.0, mass_z=6.0, depth=1.0, color="cyan", a=0.6, cam_h=2.6, yaw=0.0, n=34,
              wells=None, horizon=300, ripple=0.0, rip_t=0.0):
    """パースつき時空グリッド。wells = [(x, z, depth)]。proj(x, z, y) を返す"""
    if wells is None:
        wells = [(mass_x, mass_z, depth)]
    fx = 900

    def hgt(x, z):
        h = 0
        for (wx, wz, wd) in wells:
            r2 = (x - wx) ** 2 + (z - wz) ** 2
            h -= wd * 1.2 / math.sqrt(r2 + 1.0)
        if ripple:
            r = math.sqrt((x - wells[0][0]) ** 2 + (z - wells[0][1]) ** 2)
            h += ripple * math.sin(r * 2.5 - rip_t * 6) * math.exp(-r * 0.25)
        return h

    def proj(x, z, y):
        zr = z + 1.2
        if zr < 0.3:
            return None
        return (W / 2 + fx * x / zr, horizon + fx * (cam_h - y) / zr)

    grid_mesh.hgt = hgt
    span = 9.0
    pts = []
    xs = np.linspace(-span, span, n)
    zs = np.linspace(0.5, 16, n)
    paint = P(color, a, stroke=1.6)
    for xi in xs:
        pth = skia.Path()
        first = True
        for zi in zs:
            pr = proj(xi, zi, hgt(xi, zi))
            if pr is None:
                continue
            if first:
                pth.moveTo(*pr)
                first = False
            else:
                pth.lineTo(*pr)
        c.drawPath(pth, paint)
    for zi in zs:
        pth = skia.Path()
        first = True
        for xi in np.linspace(-span, span, n * 2):
            pr = proj(xi, zi, hgt(xi, zi))
            if pr is None:
                continue
            if first:
                pth.moveTo(*pr)
                first = False
            else:
                pth.lineTo(*pr)
        fade = 1 - (zi / 16) ** 1.5
        paint2 = P(color, a * fade, stroke=1.6)
        c.drawPath(pth, paint2)
    return proj


def s01_title(c, t, S):
    bg_grad(c, "#0A1236", "#02030A")
    STARS.draw(c, t, 0.7)
    grid_mesh(c, t, 0, 7, 1.4 + 0.2 * math.sin(t), "cyan", 0.35, ripple=0.25, rip_t=t)
    glow(c, W / 2, 600, 330, "#4C7DFF", 0.35)
    earth(c, W / 2, 600, 120, t * 2)
    k = ramp(t, 0.2, 0.9)
    title = "AIが重力を支配した世界"
    f = font(118)
    tw = f.measureText(title)
    x = W / 2 - tw / 2
    for i, ch in enumerate(title):
        kk = eob((t - 0.25 - i * 0.05) / 0.5)
        cw = f.measureText(ch)
        with xf(c, x + cw / 2, 250, 0, max(0.01, kk)), layer(c, clamp(kk)):
            text(c, ch, 0, 40, 118, "white", stroke=14, stroke_col="#0A0F24", glow_col="#3DF5FF", glow_r=24)
        x += cw
    with layer(c, ramp(t, 1.3, 0.6)):
        rrect(c, W / 2 - 430, 340, 860, 64, 32, P(shader=lin(W / 2 - 430, 0, W / 2 + 430, 0, ["#3DF5FF", "#FF4FD8"])))
        text(c, "もしも重力を自由に操れたら｜思考実験", W / 2, 385, 38, "#0A0F24")
    vignette(c, 0.6)


# ============================================================
# s02 重力はとても弱い：磁石とクリップ → 4つの力
# ============================================================
def desk_bg(c):
    c.drawRect(R(0, 0, W, H), P(shader=lin(0, 0, 0, H, ["#1A2552", "#0B1130"])))
    for i in range(0, W, 80):
        c.drawLine(i, 0, i, 760, P("#3DF5FF", 0.05, stroke=1))
    for j in range(0, 760, 80):
        c.drawLine(0, j, W, j, P("#3DF5FF", 0.05, stroke=1))
    c.drawRect(R(0, 760, W, 320), P(shader=lin(0, 760, 0, 1080, ["#5B4632", "#2E2218"])))
    c.drawLine(0, 760, W, 760, P("#8C6E50", stroke=4))


def s02_weak(c, t, S):
    t_chart = S.L[3] - 0.4
    if t < t_chart + 0.5:
        with layer(c, 1 - ramp(t, t_chart, 0.5)):
            desk_bg(c)
            # 磁石が降りてきてクリップを吸い上げる
            down = ramp(t, S.L[1] + 0.3, 1.2)
            my = lerp(250, 470, down)
            magnet(c, 760, my, 1.0)
            snap = ramp(t, S.L[1] + 1.6, 0.25)
            cy = lerp(748, my + 62, snap)
            if snap < 1:
                cy += 0
            paperclip(c, 760 + 2 * math.sin(t * 30) * (1 - snap) * (down > 0.9), cy, 1.0, lerp(0, -8, snap))
            if snap > 0:
                ring_pulse(c, 760, my + 50, t, 1.2, 120, "cyan", 0.6 * snap)
                # 磁力線
                for k in range(-3, 4):
                    pth = skia.Path()
                    pth.moveTo(670, my + 30)
                    pth.cubicTo(670 + k * 10, my + 150 + abs(k) * 30, 850 - k * 10, my + 150 + abs(k) * 30, 850, my + 30)
                    c.drawPath(pth, P("cyan", 0.25 * snap, stroke=2, dash=([8, 10], -t * 40)))
            # 地球との綱引き
            k2 = ramp(t, S.L[2], 0.8)
            if k2 > 0:
                with layer(c, k2):
                    earth(c, 1450, 1150, 380, t)
                    c.drawLine(760, my + 120, 760, 700, P("amber", 0.9, stroke=8))
                    pth = skia.Path()
                    pth.moveTo(740, 680)
                    pth.lineTo(780, 680)
                    pth.lineTo(760, 720)
                    pth.close()
                    c.drawPath(pth, P("amber"))
                    panel(c, 1060, 220, 720, 330, k2)
                    text(c, "磁石 1個", 1230, 330, 54, "cyan")
                    text(c, "VS", 1420, 330, 44, "white")
                    text(c, "地球", 1610, 330, 54, "amber")
                    text(c, "重さ 約0.1kg", 1230, 390, 28, "gray", weight="Bold")
                    text(c, "約6×10²⁴kg" if False else "約 6,000,000,000,000,000,000,000,000 kg", 1610, 390, 20, "gray", weight="Bold")
                    with layer(c, ramp(t, S.L[2] + 1.6, 0.4)):
                        with xf(c, 1230, 480, -8, eob((t - S.L[2] - 1.6) / 0.5)):
                            text(c, "WIN!", 0, 0, 46, "yellow", stroke=8, stroke_col="#0A0F24")
    if t > t_chart:
        k = ramp(t, t_chart, 0.6)
        with layer(c, k):
            bg_grad(c, "#0F1A44", "#050816")
            STARS.draw(c, t, 0.3)
            text(c, "自然界の4つの力（強さの比較・対数スケール）", 960, 170, 44, "white")
            forces = [("強い力", 0, "mag"), ("電磁気力", -2.1, "cyan"), ("弱い力", -6, "green"), ("重力", -38.9, "amber")]
            x0, x1 = 560, 1680
            for i, (nm, lg, cl) in enumerate(forces):
                y = 280 + i * 140
                kk = eoc((t - t_chart - 0.3 - i * 0.35) / 1.0)
                text(c, nm, x0 - 30, y + 52, 46, cl, align="right")
                rrect(c, x0, y + 10, x1 - x0, 56, 12, P("#1A2450", 0.9))
                wfull = (lg + 40) / 40 * (x1 - x0)
                ww = max(14, wfull * kk)
                rrect(c, x0, y + 10, ww, 56, 12, P(shader=lin(x0, 0, x0 + ww, 0, [mix(cl, "#000000", 0.5), PAL[cl] if cl in PAL else cl])))
                lab = {"強い力": "1", "電磁気力": "約 1/137", "弱い力": "約 1/100万", "重力": "約 1/10³⁹ !?"}[nm]
                if nm == "重力":
                    lab = "ほぼ 0（10の39乗分の1）"
                text(c, lab, x0 + ww + 20 if nm == "重力" else x0 + ww - 20, y + 50, 34,
                     "white" if nm != "重力" else "yellow", align="left" if nm == "重力" else "right", stroke=6, stroke_col="#0A0F24")
            with layer(c, ramp(t, t_chart + 3.2, 0.5)):
                with xf(c, 1500, 790, -6, eob((t - t_chart - 3.2) / 0.5)):
                    rrect(c, -170, -50, 340, 80, 16, P("red"))
                    text(c, "ダントツ最弱", 0, 8, 46, "white")
    vignette(c, 0.5)


# ============================================================
# s03 時空のゆがみ・スカイツリーの時計
# ============================================================
def clock(c, x, y, r, t, speed=1.0, color="cyan", label=None, a=1.0):
    with layer(c, a):
        c.drawCircle(x, y, r, P("#0A1230", 0.9))
        c.drawCircle(x, y, r, P(color, stroke=4))
        for k in range(12):
            an = k / 12 * 2 * math.pi
            c.drawLine(x + math.sin(an) * r * 0.8, y - math.cos(an) * r * 0.8, x + math.sin(an) * r * 0.92, y - math.cos(an) * r * 0.92, P(color, stroke=3))
        an = t * speed * 2.0
        c.drawLine(x, y, x + math.sin(an) * r * 0.75, y - math.cos(an) * r * 0.75, P("white", stroke=4))
        an2 = an / 12
        c.drawLine(x, y, x + math.sin(an2) * r * 0.5, y - math.cos(an2) * r * 0.5, P("white", stroke=6))
        c.drawCircle(x, y, 6, P(color))
        if label:
            text(c, label, x, y + r + 50, 32, color, weight="Bold")


def skytree(c, x, ybase, h, a=1.0):
    with layer(c, a):
        pth = skia.Path()
        pth.moveTo(x - 70, ybase)
        pth.lineTo(x - 14, ybase - h * 0.75)
        pth.lineTo(x - 6, ybase - h)
        pth.lineTo(x + 6, ybase - h)
        pth.lineTo(x + 14, ybase - h * 0.75)
        pth.lineTo(x + 70, ybase)
        pth.close()
        c.drawPath(pth, P(shader=lin(x - 70, 0, x + 70, 0, ["#9FB4E8", "#E9F0FF", "#7D90C4"])))
        for k in range(1, 18):
            yy = ybase - h * 0.75 * k / 18
            ww = lerp(70, 14, k / 18)
            c.drawLine(x - ww, yy, x + ww, yy, P("#3E4F80", 0.5, stroke=1.5))
        for (hh, ww) in [(0.36, 44), (0.47, 34)]:
            yy = ybase - h * hh
            rrect(c, x - ww, yy - 14, ww * 2, 28, 8, P("#DDE8FF"))
            rrect(c, x - ww, yy - 6, ww * 2, 8, 3, P("#3DF5FF", 0.8))
        c.drawCircle(x, ybase - h - 6, 5, P("red"))


def s03_spacetime(c, t, S):
    bg_grad(c, "#081030", "#02030A")
    STARS.draw(c, t, 0.6)
    t_tree = S.L[2] - 0.3
    t_back = S.L[3] - 0.3
    if t < t_tree + 0.6 or t > t_back:
        a = 1 - ramp(t, t_tree, 0.6) if t < t_back else ramp(t, t_back, 0.6)
        with layer(c, a):
            mass_in = eoc(t / 3.0)
            mx = lerp(-10, 0, mass_in) if t < t_back else 3 * math.sin((t - t_back) * 0.8)
            dep = 1.6 * mass_in if t < t_back else 1.6 + 0.3 * math.sin(t * 3)
            rip = 0.0 if t < t_back else 0.35 * ramp(t, t_back + 1.0, 1)
            proj = grid_mesh(c, t, mx, 7, dep, "cyan", 0.55, ripple=rip, rip_t=t)
            p = proj(mx, 7, -dep * 1.2)
            if p:
                glow(c, p[0], p[1] - 30, 260, "amber", 0.4)
                c.drawCircle(p[0], p[1] - 30, 90, P(shader=rad(p[0] - 30, p[1] - 60, 130, ["#FFF2C2", "#FFB347", "#B3540E"])))
                # 公転する小天体
                an = t * 1.2
                ox = mx + 3.5 * math.cos(an)
                oz = 7 + 3.5 * math.sin(an)
                q = proj(ox, oz, -1.2 * dep / math.sqrt(3.5 ** 2 + 1.0) + 0.3)
                if q:
                    c.drawCircle(q[0], q[1], 22, P(shader=rad(q[0] - 6, q[1] - 6, 30, ["#DDEBFF", "#6B86C4"])))
            # 2つの時計：重い物体の近くは遅い
            if t < t_back:
                kc = ramp(t, S.L[1] + 0.4, 0.6)
                if kc > 0:
                    clock(c, 330, 330, 90, t, 1.0, "cyan", "遠く：ふつう", kc)
                    clock(c, 1590, 330, 90, t, 0.55, "amber", "重い星のそば：ゆっくり", kc)
            else:
                with layer(c, ramp(t, t_back + 0.6, 0.6)):
                    text(c, "重力を操る ＝ 時空を操る", 960, 210, 72, "white", stroke=10, stroke_col="#0A0F24", glow_col="#3DF5FF")
    if t_tree < t < t_back + 0.6:
        a = ramp(t, t_tree, 0.6) * (1 - ramp(t, t_back, 0.6))
        with layer(c, a):
            c.drawRect(R(0, 0, W, H), P(shader=lin(0, 0, 0, H, ["#1B2E66", "#F39A6B"], [0.0, 1.0])))
            STARS2.draw(c, t, 0.3)
            # 街並み
            rng = np.random.default_rng(9)
            x = 0
            while x < W:
                bw = rng.uniform(40, 120)
                bh = rng.uniform(60, 220)
                c.drawRect(R(x, 880 - bh, bw, bh + 140), P("#1A1F3A"))
                for wy in range(int(880 - bh + 12), 870, 22):
                    for wx in range(int(x + 8), int(x + bw - 8), 18):
                        if rng.random() < 0.4:
                            c.drawRect(R(wx, wy, 8, 10), P("#FFD27A", 0.7))
                x += bw + 4
            k = eoc((t - t_tree) / 2.0)
            skytree(c, 760, 880, 780 * k + 1, 1)
            c.drawRect(R(0, 880, W, 200), P("#0B0F22"))
            # 時計2つ
            kc = ramp(t, t_tree + 1.2, 0.6)
            clock(c, 1060, 400, 70, t, 1.0, "cyan", None, kc)
            clock(c, 1060, 720, 70, t, 1.0, "amber", None, kc)
            with layer(c, kc):
                c.drawLine(810, 515, 990, 420, P("cyan", 0.7, stroke=2, dash=([6, 6],)))
                c.drawLine(840, 860, 990, 750, P("amber", 0.7, stroke=2, dash=([6, 6],)))
                text(c, "展望台（約450m）", 1160, 380, 36, "cyan", align="left", stroke=6, stroke_col="#0A0F24")
                text(c, "地上", 1160, 735, 36, "amber", align="left", stroke=6, stroke_col="#0A0F24")
                ns = min(4.0, max(0, t - t_tree - 1.6) * 0.8)
                text(c, f"+{ns:.1f} ナノ秒 / 1日", 1160, 445, 56, "yellow", align="left", stroke=8, stroke_col="#0A0F24")
                text(c, "地上より速く進む！", 1160, 500, 34, "white", align="left", stroke=6, stroke_col="#0A0F24")
    vignette(c, 0.6)


# ============================================================
# s04 ワールドレポート：浮かぶカエル
# ============================================================
def world_banner(c, t, title, sub, a=1.0):
    with layer(c, a):
        k = eoc(t / 0.6)
        c.drawRect(R(0, 120, 1060 * k, 70), P("red"))
        c.drawRect(R(0, 190, 700 * k, 46), P("#0A0F24", 0.85))
        text(c, "WORLD REPORT", 40, 170, 40, "white", align="left", spacing=4)
        text(c, title, 445, 170, 34, "white", weight="Bold", align="left")
        text(c, sub, 40, 225, 26, "cyan", weight="Medium", align="left")
        c.drawCircle(1030, 155, 10, P("white", 0.5 + 0.5 * math.sin(t * 6)))


def globe_pin(c, cx, cy, r, t, lon, lat, label, a=1.0):
    with layer(c, a):
        glow(c, cx, cy, r * 1.4, "blue", 0.25)
        c.drawCircle(cx, cy, r, P("#0B1C4A"))
        rot = t * 0.15
        for k in range(12):
            ang = k / 12 * math.pi + rot
            w = abs(math.cos(ang)) * r
            c.drawOval(skia.Rect(cx - w, cy - r, cx + w, cy + r), P("cyan", 0.25, stroke=1.5))
        for k in range(1, 6):
            yy = cy - r + 2 * r * k / 6
            ww = math.sqrt(max(0, r * r - (yy - cy) ** 2))
            c.drawLine(cx - ww, yy, cx + ww, yy, P("cyan", 0.25, stroke=1.5))
        c.drawCircle(cx, cy, r, P("cyan", 0.7, stroke=3))
        px = cx + r * 0.25
        py = cy - r * 0.45
        drop = eob((t - 0.8) / 0.6)
        with xf(c, px, py - 60 * (1 - drop)):
            ring_pulse(c, 0, 0, t, 1.5, 70, "red", clamp(drop))
            pin = skia.Path()
            pin.moveTo(0, 0)
            pin.cubicTo(-30, -40, -24, -70, 0, -70)
            pin.cubicTo(24, -70, 30, -40, 0, 0)
            c.drawPath(pin, P("red", clamp(drop * 2)))
            c.drawCircle(0, -48, 9, P("white", clamp(drop * 2)))
        with layer(c, ramp(t, 1.3, 0.5)):
            panel(c, px + 40, py - 120, 420, 110)
            text(c, label[0], px + 70, py - 70, 40, "white", align="left")
            text(c, label[1], px + 70, py - 28, 26, "cyan", weight="Medium", align="left")


def frog(c, x, y, s=1.0, rot=0, a=1.0):
    with xf(c, x, y, rot, s), layer(c, a):
        g1, g2 = "#5FD068", "#2E8A3E"
        # 後ろ足
        for sgn in (-1, 1):
            c.drawLine(sgn * 40, 20, sgn * 95, 40, P(g2, stroke=22))
            c.drawLine(sgn * 95, 40, sgn * 60, 70, P(g2, stroke=18))
            c.drawLine(sgn * 60, 70, sgn * 100, 82, P(g2, stroke=12))
            c.drawLine(sgn * 30, -10, sgn * 70, -40, P(g2, stroke=14))
        c.drawOval(skia.Rect(-62, -45, 62, 50), P(shader=rad(-10, -20, 80, [g1, g2])))
        c.drawOval(skia.Rect(-50, -85, 50, -20), P(g1))
        for sgn in (-1, 1):
            c.drawCircle(sgn * 28, -82, 17, P("#E9FFE0"))
            c.drawCircle(sgn * 28, -82, 8, P("#111111"))
        c.drawArc(skia.Rect(-26, -62, 26, -34), 20, 140, False, P("#1A4A22", stroke=3))
        c.drawOval(skia.Rect(-38, -20, 38, 36), P("#D8F5B0", 0.6))


def s04_frog(c, t, S):
    bg_grad(c, "#0C1438", "#03050F")
    STARS.draw(c, t, 0.35)
    t1 = S.L[1] - 0.2
    t2 = S.L[2] - 0.2
    if t < t1 + 0.5:
        with layer(c, 1 - ramp(t, t1, 0.5)):
            globe_pin(c, 960, 600, 300, t, 5.9, 51.8, ("オランダ・ナイメーヘン", "強磁場研究所 / 1997年"))
    if t1 < t < t2 + 0.5:
        k = ramp(t, t1, 0.5) * (1 - ramp(t, t2, 0.5))
        tt = t - t1
        with layer(c, k):
            # 磁石の筒 (断面)
            cx, cy = 760, 600
            rrect(c, cx - 260, 240, 90, 700, 20, P(shader=lin(cx - 260, 0, cx - 170, 0, ["#3A4570", "#8FA0D0", "#2A3358"])))
            rrect(c, cx + 170, 240, 90, 700, 20, P(shader=lin(cx + 170, 0, cx + 260, 0, ["#2A3358", "#8FA0D0", "#3A4570"])))
            for j in range(10):
                yy = 270 + j * 68
                c.drawRect(R(cx - 260, yy, 90, 16), P("#C77A2E", 0.8))
                c.drawRect(R(cx + 170, yy, 90, 16), P("#C77A2E", 0.8))
            for kx in range(-3, 4):
                pth = skia.Path()
                xx = cx + kx * 40
                pth.moveTo(xx, 940)
                pth.cubicTo(xx + kx * 8, 700, xx - kx * 8, 500, xx, 240)
                c.drawPath(pth, P("cyan", 0.35, stroke=2.5, dash=([12, 10], -tt * 60)))
            fy = cy - 40 * eoc(tt / 2) + 18 * math.sin(tt * 1.6)
            glow(c, cx, fy, 160, "cyan", 0.25)
            frog(c, cx, fy, 1.15, 20 * math.sin(tt * 0.7) + tt * 12)
            with layer(c, ramp(tt, 1.0, 0.5)):
                panel(c, 1180, 360, 560, 360)
                text(c, "反磁性浮上", 1460, 430, 52, "white")
                text(c, "磁場の強さ 約16テスラ", 1460, 510, 38, "cyan", weight="Bold")
                text(c, "（冷蔵庫の磁石の数百倍）", 1460, 560, 30, "gray", weight="Medium")
                text(c, "水を含むものは", 1460, 630, 34, "white", weight="Bold")
                text(c, "ほんのわずかに磁場を嫌う", 1460, 676, 34, "white", weight="Bold")
    if t > t2:
        k = ramp(t, t2, 0.5)
        tt = t - t2
        with layer(c, k):
            # グラフェン(ハニカム)背景
            s_ = 46
            for i in range(-1, 26):
                for j in range(-1, 16):
                    x = i * s_ * 1.5
                    y = j * s_ * 1.732 + (s_ * 0.866 if i % 2 else 0)
                    wv = 0.5 + 0.5 * math.sin(tt * 2 - (x + y) * 0.004)
                    pth = skia.Path()
                    for m in range(7):
                        an = math.pi / 3 * m
                        px, py = x + s_ * math.cos(an), y + s_ * math.sin(an)
                        (pth.moveTo if m == 0 else pth.lineTo)(px, py)
                    c.drawPath(pth, P("cyan", 0.08 + 0.12 * wv, stroke=2))
            panel(c, 460, 300, 1000, 460)
            text(c, "アンドレ・ガイム", 960, 400, 64, "white")
            text(c, "Andre Geim", 960, 455, 34, "gray", weight="Medium")
            for i, (yr, nm, cl) in enumerate([("2000年", "イグノーベル賞（カエル浮上）", "amber"), ("2010年", "ノーベル物理学賞（グラフェン）", "yellow")]):
                kk = eob((tt - 0.6 - i * 0.8) / 0.5)
                with layer(c, clamp(kk)):
                    y = 545 + i * 100
                    c.drawCircle(560, y - 12, 32, P(cl))
                    c.drawCircle(560, y - 12, 20, P("#0A0F24", 0.25))
                    text(c, yr, 620, y, 38, cl, align="left")
                    text(c, nm, 760, y, 38, "white", weight="Bold", align="left")
            text(c, "※両方を受賞したのは史上初", 960, 730, 26, "gray", weight="Medium")
    world_banner(c, t, "生きたカエルが宙に浮いた日", "Diamagnetic levitation ｜ High Field Magnet Laboratory")
    vignette(c, 0.6)


# ============================================================
# s05 AIが核融合炉の磁場を制御
# ============================================================
def s05_tokamak(c, t, S):
    bg_grad(c, "#0A0E2C", "#020309")
    STARS.draw(c, t, 0.25)
    cx, cy = 1150, 560
    c.save()
    c.translate(cx, cy)
    c.scale(0.82, 0.82)
    c.translate(-cx, -cy)
    # 容器 (D形)
    def dshape(scale, tri=0.4, el=1.5):
        pth = skia.Path()
        for i in range(73):
            th = i / 72 * 2 * math.pi
            x = cx + scale * math.cos(th + tri * math.sin(th))
            y = cy + scale * el * math.sin(th)
            (pth.moveTo if i == 0 else pth.lineTo)(x, y)
        pth.close()
        return pth
    c.drawPath(dshape(250, 0.35, 1.45), P("#141C44"))
    c.drawPath(dshape(250, 0.35, 1.45), P("#8FA0D0", stroke=10))
    # 19個のコイル
    act = []
    for i in range(19):
        th = i / 19 * 2 * math.pi
        x = cx + 330 * math.cos(th)
        y = cy + 470 * math.sin(th) * 0.95
        lv = 0.5 + 0.5 * math.sin(t * 5 + i * 1.7 + math.sin(t * 1.3 + i))
        act.append((x, y, lv))
        glow(c, x, y, 50, "amber", 0.5 * lv)
        rrect(c, x - 22, y - 16, 44, 32, 6, P(mix("#5A3A10", "#FFC24B", lv)))
        rrect(c, x - 22, y - 16, 44, 32, 6, P("#FFE6A8", 0.6, stroke=2))
    # プラズマ形状の変化
    ph = (t / 5.0) % 3
    shapes = [(0.0, 1.0), (0.45, 1.6), (-0.35, 1.35)]
    i0 = int(ph) % 3
    i1 = (i0 + 1) % 3
    k = ss(ph - int(ph))
    tri = lerp(shapes[i0][0], shapes[i1][0], k)
    el = lerp(shapes[i0][1], shapes[i1][1], k)
    pl = dshape(140 + 6 * math.sin(t * 7), tri, el)
    c.drawPath(pl, P("mag", 0.5, blur=40))
    c.drawPath(pl, P(shader=rad(cx, cy, 260, ["#FFFFFF", "#FF9AF0", "#FF4FD8", "#6A1F8A"], [0, 0.25, 0.6, 1])))
    c.drawPath(pl, P("white", 0.6, stroke=3))
    text(c, "プラズマ", cx, cy + 14, 40, "#2A0A30", weight="Bold")
    c.restore()
    # ニューラルネット (左)
    layers_ = [5, 8, 8, 6]
    nodes = []
    for li, n in enumerate(layers_):
        col_ = []
        for j in range(n):
            x = 180 + li * 150
            y = 560 + (j - (n - 1) / 2) * 66
            col_.append((x, y))
        nodes.append(col_)
    for li in range(len(nodes) - 1):
        for a_ in nodes[li]:
            for b_ in nodes[li + 1]:
                c.drawLine(a_[0], a_[1], b_[0], b_[1], P("cyan", 0.12, stroke=1.5))
    for li, col_ in enumerate(nodes):
        for j, (x, y) in enumerate(col_):
            lv = 0.5 + 0.5 * math.sin(t * 6 - li * 1.3 + j)
            c.drawCircle(x, y, 16, P(mix("#123060", "#3DF5FF", lv)))
            c.drawCircle(x, y, 16, P("white", 0.5, stroke=2))
    text(c, "AI（強化学習）", 405, 300, 40, "cyan", glow_col="#3DF5FF")
    # 出力からコイルへの信号
    for i, (x, y, lv) in enumerate(act[::3]):
        ox, oy = nodes[-1][i % len(nodes[-1])]
        x, y = cx + (x - cx) * 0.82, cy + (y - cy) * 0.82
        pth = skia.Path()
        pth.moveTo(ox, oy)
        pth.cubicTo(ox + 200, oy, x - 200, y, x, y)
        c.drawPath(pth, P("cyan", 0.35, stroke=2, dash=([4, 14], -t * 120)))
    # 情報パネル
    with layer(c, ramp(t, S.L[1] + 0.3, 0.6)):
        panel(c, 1530, 300, 340, 160)
        text(c, "制御コイル", 1700, 360, 34, "white", weight="Bold")
        text(c, "19個", 1700, 430, 64, "amber")
    with layer(c, ramp(t, S.L[2] + 0.3, 0.6)):
        panel(c, 1530, 520, 340, 230)
        text(c, "制御の速さ", 1700, 580, 34, "white", weight="Bold")
        text(c, "1秒間に", 1700, 640, 34, "gray", weight="Bold")
        n = int(10000 * ramp(t, S.L[2] + 0.5, 1.5))
        text(c, f"{n:,}回", 1700, 715, 60, "cyan")
    world_banner(c, t, "AIが核融合プラズマを操った", "Magnetic control of tokamak plasmas through deep reinforcement learning")
    vignette(c, 0.55)


# ============================================================
# s06 朝のベッド
# ============================================================
def gmeter_big(c, x, y, r, g, label, a=1.0, color="cyan"):
    with layer(c, a):
        c.drawCircle(x, y, r, P("#0A1230", 0.85))
        c.drawArc(skia.Rect(x - r, y - r, x + r, y + r), 135, 270, False, P("#24305E", stroke=14))
        c.drawArc(skia.Rect(x - r, y - r, x + r, y + r), 135, 270 * clamp(g), False, P(color, stroke=14))
        text(c, f"{g:.1f}G", x, y + 22, r * 0.55, "white")
        text(c, label, x, y + r * 0.75, 26, color, weight="Bold")


def room(c, wall_top="#2B2F5E", wall_bot="#4A3D6E", floor="#2A2238"):
    c.drawRect(R(0, 0, W, 820), P(shader=lin(0, 0, 0, 820, [wall_top, wall_bot])))
    c.drawRect(R(0, 820, W, 260), P(shader=lin(0, 820, 0, H, [floor, "#120E1C"])))
    c.drawLine(0, 820, W, 820, P("#000000", 0.4, stroke=4))


def s06_morning(c, t, S):
    sun = ramp(t, 0, S.dur * 0.6)
    room(c, mix("#1B1F45", "#3E3A78", sun), mix("#2C2552", "#8A5A7A", sun), "#2A2238")
    # 窓
    wx, wy, ww, wh = 1220, 170, 460, 400
    c.save()
    c.clipRect(R(wx, wy, ww, wh))
    c.drawRect(R(wx, wy, ww, wh), P(shader=lin(0, wy, 0, wy + wh, [mix("#1A2A6A", "#7FB2FF", sun), mix("#3A2A6A", "#FFB37A", sun)])))
    sy = lerp(wy + wh + 40, wy + 180, eoc(sun))
    glow(c, wx + 300, sy, 220, "#FFD27A", 0.6)
    c.drawCircle(wx + 300, sy, 55, P("#FFE9A8"))
    # 浮かぶ車 (遠景)
    for k in range(3):
        xx = wx + ((t * 60 + k * 170) % (ww + 200)) - 100
        c.drawOval(skia.Rect(xx - 20, wy + 90 + k * 50, xx + 20, wy + 100 + k * 50), P("#1A1A3A", 0.8))
        c.drawCircle(xx + 18, wy + 95 + k * 50, 3, P("#FFF2A8"))
    c.restore()
    c.drawRect(R(wx, wy, ww, wh), P("#E8E0F0", stroke=14))
    c.drawLine(wx + ww / 2, wy, wx + ww / 2, wy + wh, P("#E8E0F0", stroke=8))
    # ライトの差し込み
    c.drawRect(R(0, 0, W, H), P(shader=lin(wx, wy, wx - 600, 1000, [col("#FFD9A0", 0.18 * sun), col("#FFD9A0", 0)])))
    # 時計
    rrect(c, 260, 220, 260, 110, 20, P("#0A0F24", 0.9))
    text(c, "7:00", 390, 300, 70, "cyan", glow_col="#3DF5FF", glow_r=12)
    # ベッド
    bx, by = 480, 700
    rrect(c, bx, by, 760, 120, 20, P("#5A4A7E"))
    rrect(c, bx, by - 30, 760, 60, 26, P("#EDE6FA"))
    rrect(c, bx - 30, by - 190, 40, 340, 14, P("#3A2F5A"))
    rrect(c, bx + 750, by - 90, 40, 240, 14, P("#3A2F5A"))
    # 浮く人
    t_up = S.L[3] + 0.3
    rise = ramp(t, t_up, 2.5)
    hover = 40 + 10 * math.sin(t * 1.4)
    px = lerp(bx + 380, 1380, rise)
    py = lerp(by - 70 - hover, 820 - 0, rise)
    pose = blend_pose(POSES["relax"], POSES["stand"], rise)
    rot = lerp(-90, 0, rise)
    if rise > 0.98:
        py = 820 - 99
    else:
        py = lerp(by - 70 - hover, 820 - 99, ss(rise))
    if rise < 0.02:
        c.drawOval(skia.Rect(px - 260, by - 40, px + 260, by - 20), P("#000000", 0.25, blur=10))
        glow(c, px, py, 260, "cyan", 0.18)
    # 毛布
    person(c, px, py, 0.95, "#F4F1FF", pose, rot=rot, back="#C5BEE6", hair="#3A2A20")
    if rise < 0.05:
        blanket = skia.Path()
        blanket.moveTo(px - 60, py - 40)
        blanket.cubicTo(px - 10, py - 80, px + 140, py - 70, px + 200, py - 30)
        blanket.lineTo(px + 215, py + 25)
        blanket.cubicTo(px + 100, py + 45, px - 20, py + 45, px - 70, py + 20)
        blanket.close()
        c.drawPath(blanket, P("#7FA8FF", 0.92))
        for i in range(3):
            ph = (t * 0.5 + i / 3) % 1
            text(c, "z", px - 220 - ph * 60, py - 120 - ph * 120, 40 + 20 * ph, "white", a=(1 - ph) * (1 - ramp(t, S.L[1], 1)) + 0.0)
    # 圧力マップ
    kp = ramp(t, S.L[2], 0.6) * (1 - ramp(t, t_up + 1.5, 0.6))
    with layer(c, kp):
        panel(c, 1240, 620, 560, 170)
        text(c, "体圧マップ", 1290, 670, 30, "white", weight="Bold", align="left")
        for i in range(24):
            xx = 1290 + i * 20
            lv = 0.15 + 0.1 * math.sin(i * 0.8 + t * 2)
            c.drawRect(R(xx, 700, 16, 60), P(mix("#2244FF", "#FF3B3B", lv)))
        text(c, "負担 ほぼゼロ", 1540, 670, 30, "green", weight="Bold", align="left")
    # 重力メーター
    g = 0.1 if t < t_up else lerp(0.1, 1.0, ramp(t, t_up, 4.0))
    gmeter_big(c, 860, 300, 110, g, "SLEEP MODE" if g < 0.15 else "WAKE UP", ramp(t, S.L[2] - 0.5, 0.6))
    vignette(c, 0.55)
    return {"g": g}


# ============================================================
# s07 家事：ホコリが集まる・冷蔵庫を指一本
# ============================================================
def sofa(c, x, y):
    rrect(c, x, y - 160, 420, 120, 30, P("#3F6FB8"))
    rrect(c, x - 30, y - 90, 480, 100, 30, P("#4F82D0"))
    rrect(c, x - 50, y - 130, 70, 140, 26, P("#3A64A8"))
    rrect(c, x + 400, y - 130, 70, 140, 26, P("#3A64A8"))


def fridge(c, x, y, a=1.0, glowk=0.0):
    with layer(c, a):
        if glowk > 0:
            glow(c, x + 110, y - 240, 360, "cyan", 0.35 * glowk)
        rrect(c, x, y - 480, 220, 480, 22, P(shader=lin(x, 0, x + 220, 0, ["#E6ECF5", "#BFC8D8"])))
        c.drawLine(x + 4, y - 300, x + 216, y - 300, P("#8E98AE", stroke=4))
        rrect(c, x + 180, y - 430, 12, 90, 6, P("#8E98AE"))
        rrect(c, x + 180, y - 270, 12, 120, 6, P("#8E98AE"))
        if glowk > 0:
            rrect(c, x, y - 480, 220, 480, 22, P("cyan", glowk, stroke=4))


def s07_home(c, t, S):
    room(c, "#2E3A5E", "#3B4A70", "#5A4636")
    # 床の木目
    for i in range(12):
        c.drawLine(0, 840 + i * 22, W, 840 + i * 22, P("#000000", 0.08, stroke=2))
    t2 = S.L[2] - 0.3
    # 植物
    rrect(c, 120, 690, 90, 130, 12, P("#B5653A"))
    for k in range(7):
        an = -90 + (k - 3) * 22
        c.drawLine(165, 690, 165 + 120 * math.cos(math.radians(an)), 690 + 120 * math.sin(math.radians(an)), P("#3FAE6A", stroke=18))
    sofa(c, 300, 820)
    # ホコリ
    gx, gy = 960, 600
    k1 = ramp(t, S.L[1] + 0.8, 0.5)
    rng = np.random.default_rng(21)
    pull = clamp((t - S.L[1] - 1.0) / 4.0)
    if t < t2 + 1.0:
        with layer(c, 1 - ramp(t, t2 + 0.2, 0.6)):
            if k1 > 0:
                glow(c, gx, gy, 200, "mag", 0.5 * k1)
                ring_pulse(c, gx, gy, -t, 1.0, 160, "mag", 0.7 * k1)
                c.drawCircle(gx, gy, 10 * k1, P("white"))
            for i in range(150):
                x0 = rng.uniform(80, 1840)
                y0 = rng.uniform(780, 1060) if i % 2 else rng.uniform(120, 760)
                r0 = math.hypot(x0 - gx, y0 - gy)
                a0 = math.atan2(y0 - gy, x0 - gx)
                d = rng.uniform(0, 0.5)
                pk = ss(clamp((pull - d) / (1 - d + 1e-6)))
                rr = r0 * (1 - pk) + 18 * pk * rng.uniform(0.2, 1)
                aa = a0 + pk * 3.0
                x = gx + rr * math.cos(aa)
                y = gy + rr * math.sin(aa)
                sz = rng.uniform(2, 7)
                c.drawCircle(x, y, sz, P(["#9AA0B0", "#C8B89A", "#7A7F8C"][i % 3], 0.9))
            if pull > 0.85:
                c.drawCircle(gx, gy, 26 * ramp(pull, 0.85, 0.15), P("#8E8A90"))
    # 冷蔵庫
    tt = t - t2
    fk = ramp(t, t2, 0.6)
    lift = ramp(tt, 1.2, 0.8)
    slide = ss(clamp((tt - 2.2) / 3.0))
    fx = lerp(1450, 1050, slide)
    fy = 820 - 40 * lift - 6 * math.sin(t * 2) * lift
    if lift > 0:
        c.drawOval(skia.Rect(fx - 10, 815, fx + 230, 835), P("#000000", 0.3 * (1 - lift * 0.5), blur=8))
    fridge(c, fx, fy, 1, lift * fk)
    if fk > 0:
        with layer(c, fk):
            # 指 (手)
            hx = fx + 240 + 10 * math.sin(t * 3) * (1 - slide)
            hy = fy - 220
            c.drawLine(hx + 200, hy + 20, hx + 50, hy, P("#F2C8A8", stroke=50))
            c.drawLine(hx + 50, hy, hx + 5, hy, P("#F2C8A8", stroke=22))
            c.drawLine(hx + 200, hy + 20, hx + 330, hy + 40, P("#4F82D0", stroke=70, cap=False))
            panel(c, 1480, 200, 330, 170)
            wkg = int(lerp(110, 0, ramp(tt, 0.8, 1.2)))
            text(c, "冷蔵庫の重さ", 1645, 255, 30, "white", weight="Bold")
            text(c, f"{wkg} kg", 1645, 335, 70, "cyan" if wkg == 0 else "amber")
    vignette(c, 0.5)
    return {"g": 1.0 if t < t2 + 1 else lerp(1.0, 0.0, ramp(t, t2 + 1.0, 1.2))}


# ============================================================
# s08 立体道路の都市
# ============================================================
class City:
    def __init__(self, seed, n, hmin, hmax, wmin, wmax, color, win):
        rng = np.random.default_rng(seed)
        self.b = []
        x = -200
        while x < W * 2 + 200:
            w = rng.uniform(wmin, wmax)
            h = rng.uniform(hmin, hmax)
            wins = [(rng.uniform(0, 1), rng.uniform(0, 1)) for _ in range(int(w * h / 1800))]
            self.b.append((x, w, h, wins, rng.uniform(0, 1)))
            x += w + rng.uniform(4, 20)
        self.color, self.win = color, win

    def draw(self, c, base, off, a=1.0):
        for (x, w, h, wins, r) in self.b:
            xx = (x - off) % (W * 2 + 400) - 200
            if xx > W + 50 or xx + w < -50:
                continue
            c.drawRect(R(xx, base - h, w, h + 400), P(self.color, a))
            if r > 0.7:
                c.drawLine(xx + w / 2, base - h, xx + w / 2, base - h - 50, P(self.color, a, stroke=4))
                c.drawCircle(xx + w / 2, base - h - 50, 4, P("red", a))
            for (u, v) in wins:
                c.drawRect(R(xx + 6 + u * (w - 16), base - h + 10 + v * (h - 20), 6, 8), P(self.win, a * 0.8))


CITY_FAR = City(31, 0, 200, 520, 50, 140, "#18204A", "#7FA8FF")
CITY_NEAR = City(32, 0, 120, 360, 90, 200, "#0C112C", "#FFD27A")
LANES = [(380, 1, 260, "#FF4FD8", 0.75), (520, -1, 340, "#3DF5FF", 0.9), (690, 1, 430, "#FFC24B", 1.05)]


def s08_city(c, t, S):
    c.drawRect(R(0, 0, W, H), P(shader=lin(0, 0, 0, H, ["#0A0F35", "#3A1F5C", "#B0507A"], [0, 0.65, 1])))
    STARS.draw(c, t, 0.4)
    CITY_FAR.draw(c, 900, t * 15)
    # 空中レーン
    lk = ramp(t, S.L[1], 1.0)
    rng = np.random.default_rng(41)
    for li, (y, d, sp, cl, sc) in enumerate(LANES):
        with layer(c, lk):
            c.drawLine(0, y + 40 * sc, W, y + 40 * sc, P(cl, 0.25, stroke=10, blur=6))
            c.drawLine(0, y + 40 * sc, W, y + 40 * sc, P(cl, 0.6, stroke=2, dash=([40, 30], -t * sp * d)))
        for k in range(6):
            off = rng.uniform(0, W + 400)
            x = (off + d * sp * t) % (W + 400) - 200
            trail = P(shader=lin(x - d * 260 * sc, 0, x, 0, [col(cl, 0), col(cl, 0.6)]), stroke=6 * sc)
            c.drawLine(x - d * 260 * sc, y + 10 * sc, x - d * 70 * sc, y + 10 * sc, trail)
            car(c, x, y + 10 * math.sin(t * 2 + k), 0.75 * sc, ["#FF4FD8", "#4C7DFF", "#FFFFFF", "#41F2A0", "#FFC24B"][(k + li) % 5], d, 1, t)
    CITY_NEAR.draw(c, 1080, t * 40)
    # 3行目: AI ネットワーク
    k2 = ramp(t, S.L[2], 0.6) * (1 - ramp(t, S.L[3] - 0.2, 0.6))
    if k2 > 0:
        with layer(c, k2):
            pts = []
            rng2 = np.random.default_rng(50)
            for i in range(26):
                pts.append((rng2.uniform(100, 1820), rng2.uniform(320, 760)))
            for i, p in enumerate(pts):
                for q in pts[i + 1:i + 4]:
                    c.drawLine(p[0], p[1], q[0], q[1], P("cyan", 0.25, stroke=1.5))
                c.drawCircle(p[0], p[1], 6, P("cyan"))
            panel(c, 560, 150, 800, 150)
            n = int(3_000_000 + 214_567 * ramp(t, S.L[2], 3))
            text(c, f"同期中の車両  {n:,} 台", 960, 210, 44, "white")
            text(c, "渋滞 0 件 ／ 衝突 0 件", 960, 270, 40, "green")
    # 4行目: 輸送 1/4
    k3 = ramp(t, S.L[3], 0.6)
    if k3 > 0:
        with layer(c, k3):
            c.drawRect(R(0, 0, W, H), P("#050816", 0.55))
            cx, cy, r = 700, 560, 220
            c.drawArc(skia.Rect(cx - r, cy - r, cx + r, cy + r), -90, 360, False, P("#24305E", stroke=70))
            c.drawArc(skia.Rect(cx - r, cy - r, cx + r, cy + r), -90, 90 * eoc((t - S.L[3]) / 1.2), False, P("amber", stroke=70, cap=False))
            text(c, "約1/4", cx, cy + 30, 96, "amber")
            text(c, "世界のエネルギー消費のうち", 1300, 470, 42, "white", weight="Bold")
            text(c, "「輸送」に使われる割合", 1300, 540, 52, "amber")
            # 荷物が浮いて運ばれる
            for k in range(4):
                x = 1000 + ((t * 120 + k * 230) % 920)
                cardboard(c, x, 700 + 10 * math.sin(t * 2 + k), 0.9, 5 * math.sin(t + k))
                c.drawOval(skia.Rect(x - 40, 750, x + 40, 760), P("cyan", 0.5, blur=6))
    vignette(c, 0.55)


# ============================================================
# s09 医療・介護
# ============================================================
def s09_care(c, t, S):
    c.drawRect(R(0, 0, W, H), P(shader=lin(0, 0, 0, H, ["#BFE3FF", "#E9F6FF"])))
    # 公園の木
    for i, x in enumerate([200, 520, 1500, 1800]):
        c.drawRect(R(x - 14, 600, 28, 240), P("#6B4A33"))
        c.drawCircle(x, 560, 120, P(["#5FBF6A", "#4FAE5E"][i % 2]))
    c.drawRect(R(0, 820, W, 260), P(shader=lin(0, 820, 0, H, ["#9AD48A", "#6FB063"])))
    c.drawRect(R(0, 840, W, 60), P("#D9C9A8"))
    t_fall = S.L[2] + 0.2
    # 歩く高齢者
    if t < t_fall:
        x = 500 + 60 * t
        pose = walk_pose(t * 3.2, 18)
        rot = 0
        y = 840 - 98
    else:
        tt = t - t_fall
        x = 500 + 60 * t_fall + 40 * eoc(tt / 1.5)
        fk = eoc(tt / 1.4)
        pose = blend_pose(walk_pose(t_fall * 3.2, 18), POSES["fall"], fk)
        rot = 70 * fk
        y = 840 - 98 + 60 * fk
    kg = ramp(t, S.L[1] + 0.3, 0.8)
    if kg > 0:
        glow(c, x, y - 40, 200, "cyan", 0.35 * kg)
    person(c, x, y, 1.0, "#5A6FA8", pose, rot=rot, back="#3E4F80", hair="#E8E8E8", bent=12 if t < t_fall else 0)
    # 杖
    if t < t_fall:
        c.drawLine(x + 70, y - 70, x + 85, 840, P("#6B4A33", stroke=8))
    # 受け止める泡
    if t > t_fall + 0.5:
        bk = ramp(t, t_fall + 0.5, 0.6)
        bx, by = x + 40, y - 20
        c.drawCircle(bx, by, 170 * eob((t - t_fall - 0.5) / 0.6), P("cyan", 0.15 * bk))
        c.drawCircle(bx, by, 170 * eob((t - t_fall - 0.5) / 0.6), P("cyan", 0.9 * bk, stroke=4))
        c.drawCircle(bx - 60, by - 80, 20, P("white", 0.6 * bk))
        with layer(c, ramp(t, t_fall + 1.0, 0.5)):
            panel(c, 1180, 200, 560, 150)
            text(c, "転倒を検知 → 0.05秒で減速", 1460, 265, 34, "white", weight="Bold")
            text(c, "衝撃 ほぼゼロ", 1460, 325, 44, "green")
    # 体重パネル
    with layer(c, kg * (1 - ramp(t, t_fall + 0.5, 0.5))):
        panel(c, 1180, 200, 560, 200)
        text(c, "重力アシスト", 1460, 260, 40, "cyan")
        wv = int(lerp(60, 30, ramp(t, S.L[1] + 0.6, 1.2)))
        text(c, f"体重  60kg → {wv}kg", 1460, 350, 52, "#0A0F24" if False else "white")
    vignette(c, 0.35)
    return {"g": 1.0 if t < S.L[1] else lerp(1.0, 0.5, ramp(t, S.L[1] + 0.6, 1.2))}


# ============================================================
# s10 遊び：低重力バスケ・水の球
# ============================================================
def s10_play(c, t, S):
    t2 = S.L[1] - 0.3
    if t < t2 + 0.6:
        with layer(c, 1 - ramp(t, t2, 0.6)):
            c.drawRect(R(0, 0, W, H), P(shader=lin(0, 0, 0, H, ["#141A3A", "#2A1F4A"])))
            for i in range(8):
                glow(c, 160 + i * 230, 60, 160, "#FFF2C2", 0.25)
            c.drawRect(R(0, 860, W, 220), P(shader=lin(0, 860, 0, H, ["#C9824A", "#8A5530"])))
            c.drawLine(0, 860, W, 860, P("#FFFFFF", 0.6, stroke=4))
            # ゴール
            hx, hy = 1560, 430
            c.drawRect(R(1700, 300, 16, 560), P("#9AA3C8"))
            rrect(c, 1600, 260, 180, 130, 6, P("#FFFFFF", 0.9))
            rrect(c, 1640, 300, 90, 60, 4, P("#FF3B5C", stroke=5))
            c.drawLine(hx - 70, hy, hx + 70, hy, P("#FF6A2A", stroke=8))
            for k in range(6):
                c.drawLine(hx - 70 + k * 28, hy, hx - 55 + k * 22, hy + 90, P("white", 0.7, stroke=2))
            # 選手の放物線 (0.3G)
            T = 3.4
            ph = clamp((t - 0.8) / T)
            x0, x1 = 500, 1480
            x = lerp(x0, x1, ph)
            apex = 520
            y = 760 - apex * 4 * ph * (1 - ph) - 0 if ph < 1 else 760
            # 軌跡
            pth = skia.Path()
            for i in range(41):
                p_ = i / 40
                (pth.moveTo if i == 0 else pth.lineTo)(lerp(x0, x1, p_), 760 - 40 - apex * 4 * p_ * (1 - p_))
            c.drawPath(pth, P("cyan", 0.5 * ramp(t, 0.5, 0.5), stroke=3, dash=([10, 12], -t * 30)))
            if ph < 1:
                rotb = 0
                pose = POSES["jump"] if 0 < ph < 1 else POSES["stand"]
                person(c, x, y, 1.0, "#FFFFFF", pose, back="#C8D0F0", hair="#2A1A10")
                bx, by = x + 40, y - 230
            else:
                k = min(1.0, (t - 0.8 - T) / 0.6)
                person(c, x1 - 60 * k, 760, 1.0, "#FFFFFF", "stand", back="#C8D0F0", hair="#2A1A10")
                bx, by = hx, hy + 60 + 300 * clamp(k)
            c.drawCircle(bx, by, 30, P(shader=rad(bx - 10, by - 10, 40, ["#FFA060", "#D9541A"])))
            c.drawLine(bx - 30, by, bx + 30, by, P("#5A2008", stroke=2))
            c.drawArc(skia.Rect(bx - 20, by - 30, bx + 20, by + 30), 90, 180, False, P("#5A2008", stroke=2))
            if t > 0.8 + T - 0.2:
                with layer(c, ramp(t, 0.8 + T - 0.2, 0.3)):
                    with xf(c, 1100, 300, -6, eob((t - 0.8 - T + 0.2) / 0.4)):
                        text(c, "DUNK!!", 0, 0, 110, "yellow", stroke=14, stroke_col="#0A0F24")
            gmeter_big(c, 260, 280, 110, 0.3, "COURT MODE", 1, "amber")
    if t > t2:
        tt = t - t2
        with layer(c, ramp(t, t2, 0.6)):
            c.drawRect(R(0, 0, W, H), P(shader=lin(0, 0, 0, H, ["#4FA8FF", "#CDEBFF"])))
            # 下の広場
            c.drawRect(R(0, 900, W, 180), P("#D8DCE8"))
            for i in range(0, W, 120):
                c.drawLine(i, 900, i - 200, 1080, P("#B8BED0", stroke=2))
            for (x, hh) in [(120, 400), (300, 300), (1600, 450), (1780, 330)]:
                c.drawRect(R(x - 70, 900 - hh, 140, hh), P("#F2F4FA"))
                for j in range(int(hh / 50)):
                    c.drawRect(R(x - 50, 900 - hh + 20 + j * 50, 100, 22), P("#9FD3FF", 0.8))
            # 水球
            cx, cy, r = 960, 470, 300
            pth = skia.Path()
            for i in range(97):
                an = i / 96 * 2 * math.pi
                rr = r + 12 * math.sin(an * 3 + tt * 1.5) + 8 * math.sin(an * 5 - tt * 2.1)
                (pth.moveTo if i == 0 else pth.lineTo)(cx + rr * math.cos(an), cy + rr * math.sin(an))
            pth.close()
            c.drawOval(skia.Rect(cx - 260, 880, cx + 260, 920), P("#2A6FB0", 0.3, blur=20))
            c.drawPath(pth, P(shader=rad(cx - 80, cy - 100, r * 1.3, ["#BFF3FF", "#3DB4F2", "#1559A8"]), a=0.9))
            c.save()
            c.clipPath(pth, doAntiAlias=True)
            for k in range(14):
                yy = cy - r + k * 45 + 10 * math.sin(tt + k)
                c.drawLine(cx - r, yy, cx + r, yy + 30 * math.sin(tt * 1.3 + k), P("white", 0.12, stroke=6))
            sx = cx - 380 + ((tt * 140) % 760)
            person(c, sx, cy + 30 * math.sin(tt), 0.8, "#FFDDC8", walk_pose(tt * 4, 20) if False else "swim", rot=-90 + 8 * math.sin(tt * 3), back="#E0B8A0", hair="#2A1A10")
            for k in range(8):
                bxx = cx - 200 + k * 55
                byy = cy + 200 - ((tt * 80 + k * 40) % 400)
                c.drawCircle(bxx, byy, 6, P("white", 0.5, stroke=2))
            c.restore()
            c.drawPath(pth, P("white", 0.7, stroke=4))
            c.drawOval(skia.Rect(cx - 200, cy - 250, cx - 60, cy - 170), P("white", 0.55, blur=8))
            # 周りの水滴
            for k in range(12):
                an = k / 12 * 2 * math.pi + tt * 0.3
                rr = r + 70 + 20 * math.sin(tt + k)
                c.drawCircle(cx + rr * math.cos(an), cy + rr * math.sin(an), 10 + 4 * math.sin(k), P("#7FD3FF", 0.85))
            # 外の人物
            person(c, 1450, 300 + 20 * math.sin(tt * 1.3), 0.7, "#FFFFFF", "up", rot=20, back="#D0D8F0", hair="#5A3A20")
    vignette(c, 0.4)
    return {"g": 0.3}


# ============================================================
# s11 宇宙
# ============================================================
def rocket(c, x, y, s=1.0, flame=1.0, t=0):
    with xf(c, x, y, 0, s):
        for k in range(3):
            fl = skia.Path()
            ln = (160 + 40 * math.sin(t * 30 + k)) * flame
            fl.moveTo(-26 + k * 4, 0)
            fl.quadTo(0, ln * (1 - k * 0.25), 26 - k * 4, 0)
            fl.close()
            c.drawPath(fl, P(["#FF6A2A", "#FFC24B", "#FFFFFF"][k], 0.9))
        glow(c, 0, 40, 200, "#FFB347", 0.5 * flame)
        body = skia.Path()
        body.moveTo(-34, 0)
        body.lineTo(-34, -260)
        body.quadTo(0, -380, 34, -260)
        body.lineTo(34, 0)
        body.close()
        c.drawPath(body, P(shader=lin(-34, 0, 34, 0, ["#B8C2D8", "#FFFFFF", "#8E98AE"])))
        for sgn in (-1, 1):
            fin = skia.Path()
            fin.moveTo(sgn * 34, -70)
            fin.lineTo(sgn * 75, 10)
            fin.lineTo(sgn * 34, 0)
            fin.close()
            c.drawPath(fin, P("red"))
        c.drawCircle(0, -230, 16, P("#3DB4F2"))
        c.drawCircle(0, -230, 16, P("#5A6688", stroke=4))


def s11_space(c, t, S):
    bg_grad(c, "#020412", "#000000")
    STARS.draw(c, t, 1.0)
    t1, t2, t3 = S.L[1] - 0.3, S.L[2] - 0.3, S.L[3] - 0.3
    if t < t3 + 0.6:
        with layer(c, 1 - ramp(t, t3, 0.6)):
            # 地平線の地球
            er = 1800
            ex, ey = 960, 1080 + er - 260
            c.drawCircle(ex, ey, er + 40, P(shader=rad(ex, ey, er + 60, [col("#4CC3FF", 0), col("#4CC3FF", 0), col("#7FD8FF", 0.7), col("#4CC3FF", 0)], [0, 0.95, 0.975, 1])))
            c.drawCircle(ex, ey, er, P(shader=rad(ex - 300, ey - er, er * 1.2, ["#4C9BFF", "#1A4FA8", "#061538"])))
            rng = np.random.default_rng(3)
            for i in range(30):
                x = (rng.uniform(0, W) + t * 8) % W
                c.drawOval(skia.Rect(x - 80, 860 + rng.uniform(0, 200), x + 80, 880 + rng.uniform(0, 200)), P("white", 0.3, blur=6))
            if t < t2 + 0.6:
                # ロケット
                with layer(c, ramp(t, t1, 0.6) * (1 - ramp(t, t2, 0.6))):
                    tt = max(0, t - t1)
                    ry = 1000 - 75 * tt
                    rocket(c, 700, ry, 0.9, 1, t)
                    panel(c, 1120, 280, 620, 330)
                    text(c, "ロケットの重さの約9割は", 1430, 350, 36, "white", weight="Bold")
                    text(c, "燃料と推進剤", 1430, 420, 56, "amber")
                    text(c, "打ち上げ費用", 1430, 500, 32, "gray", weight="Bold")
                    text(c, "1kgあたり 数十万円〜", 1430, 565, 46, "yellow")
            if t > t2:
                with layer(c, ramp(t, t2, 0.6)):
                    tt = t - t2
                    c.drawRect(R(940, 0, 40, 1080), P(shader=lin(940, 0, 980, 0, [col("cyan", 0), col("cyan", 0.55), col("cyan", 0)])))
                    c.drawLine(960, 0, 960, 1080, P("white", 0.6, stroke=2))
                    for k in range(12):
                        yy = (k * 100 - tt * 300) % 1100
                        c.drawLine(930, yy, 990, yy, P("cyan", 0.5, stroke=2))
                    py = 820 - 90 * tt
                    glow(c, 960, py, 160, "cyan", 0.5)
                    rrect(c, 900, py - 70, 120, 140, 40, P(shader=lin(900, 0, 1020, 0, ["#CFD8EE", "#FFFFFF", "#9AA6C4"])))
                    rrect(c, 925, py - 45, 70, 50, 16, P("#3DB4F2"))
                    panel(c, 1180, 320, 600, 200)
                    text(c, "燃料ゼロで", 1480, 395, 40, "white", weight="Bold")
                    text(c, "宇宙へ「のぼる」", 1480, 475, 62, "cyan", glow_col="#3DF5FF")
    if t > t3:
        tt = t - t3
        with layer(c, ramp(t, t3, 0.6)):
            ex, ey, er = 760, 560, 260
            earth(c, ex, ey, er, t)
            # ニュートンの大砲
            mt = (ex, ey - er - 70)
            mtn = skia.Path()
            mtn.moveTo(ex - 60, ey - er + 8)
            mtn.lineTo(ex, ey - er - 70)
            mtn.lineTo(ex + 60, ey - er + 8)
            mtn.close()
            c.drawPath(mtn, P("#8A7A6A"))
            c.drawLine(ex, ey - er - 70, ex + 30, ey - er - 76, P("#333333", stroke=8))
            for i, v in enumerate([0.55, 0.75, 0.9, 1.0]):
                pth = skia.Path()
                steps = 160
                x, y = mt[0], mt[1]
                vx, vy = v * 8.6, 0
                pth.moveTo(x, y)
                kk = ramp(tt, 0.3 + i * 0.5, 1.2)
                for s_ in range(int(steps * kk) + 1):
                    for _ in range(4):
                        dx, dy = x - ex, y - ey
                        r2 = dx * dx + dy * dy
                        r_ = math.sqrt(r2)
                        acc = 8.6 * 8.6 * (er + 70) / r2
                        vx -= acc * dx / r_ * 0.25
                        vy -= acc * dy / r_ * 0.25
                        x += vx * 0.25
                        y += vy * 0.25
                    if (x - ex) ** 2 + (y - ey) ** 2 < er * er:
                        break
                    pth.lineTo(x, y)
                c.drawPath(pth, P(["#FF6A2A", "#FFC24B", "#FFE14D", "cyan"][i], 0.9, stroke=3, dash=([10, 8],) if i < 3 else None))
            # ISS 周回
            if tt > 2.6:
                an = (tt - 2.6) * 0.5 - math.pi / 2
                rr = er + 70
                ix, iy = ex + rr * math.cos(an), ey + rr * math.sin(an)
                with xf(c, ix, iy, math.degrees(an) + 90):
                    c.drawRect(R(-40, -8, 80, 16), P("#DDE6F5"))
                    c.drawRect(R(-70, -26, 24, 52), P("#3E6FD8"))
                    c.drawRect(R(46, -26, 24, 52), P("#3E6FD8"))
                gx, gy = ex - ix, ey - iy
                gl = math.hypot(gx, gy)
                c.drawLine(ix, iy, ix + gx / gl * 120, iy + gy / gl * 120, P("red", stroke=6))
                text(c, "重力", ix + gx / gl * 150, iy + gy / gl * 150, 30, "red", stroke=6, stroke_col="#000000")
            panel(c, 1180, 250, 640, 300)
            text(c, "高度 約400km", 1500, 320, 40, "white", weight="Bold")
            text(c, "重力は地上の 約90%", 1500, 400, 52, "yellow")
            with layer(c, ramp(t, S.L[4], 0.6)):
                text(c, "＝ 地球のまわりを", 1500, 470, 36, "cyan", weight="Bold")
                text(c, "「落ち続けている」", 1500, 525, 40, "cyan")
    vignette(c, 0.5)


# ============================================================
# s12 リスク
# ============================================================
def s12_risk(c, t, S):
    bg_grad(c, "#2A0610", "#050008")
    for i in range(0, H, 6):
        c.drawLine(0, i, W, i, P("#000000", 0.18, stroke=2))
    t1, t2, t3 = S.L[1] - 0.3, S.L[2] - 0.3, S.L[3] - 0.3
    # 0: 警告
    if t < t1 + 0.6:
        with layer(c, 1 - ramp(t, t1, 0.6)):
            k = eob(t / 0.6)
            with xf(c, 960, 520, 0, max(0.01, k)):
                tri = skia.Path()
                tri.moveTo(0, -220)
                tri.lineTo(250, 200)
                tri.lineTo(-250, 200)
                tri.close()
                c.drawPath(tri, P("red", 0.3 + 0.2 * math.sin(t * 8), blur=30))
                c.drawPath(tri, P("red", stroke=24))
                text(c, "!", 0, 150, 300, "red")
            text(c, "WARNING", 960, 880, 70, "red", spacing=20, glow_col="#FF3B5C")
    # 1: 骨量グラフ
    if t1 < t < t2 + 0.6:
        tt = t - t1
        with layer(c, ramp(t, t1, 0.6) * (1 - ramp(t, t2, 0.6))):
            # 骨の断面
            cx, cy = 520, 560
            c.drawOval(skia.Rect(cx - 220, cy - 260, cx + 220, cy + 260), P("#F2E8D5"))
            rng = np.random.default_rng(5)
            dens = 1 - 0.45 * ramp(tt, 0.5, 4)
            for i in range(420):
                an = rng.uniform(0, 2 * math.pi)
                rr = math.sqrt(rng.uniform(0, 1))
                if rng.uniform() > dens:
                    continue
                c.drawCircle(cx + rr * 190 * math.cos(an), cy + rr * 230 * math.sin(an), rng.uniform(4, 10), P("#C9B48E"))
            c.drawOval(skia.Rect(cx - 220, cy - 260, cx + 220, cy + 260), P("#FFFFFF", stroke=6))
            text(c, "骨の内部（イメージ）", cx, cy + 320, 32, "gray", weight="Bold")
            # グラフ
            gx, gy, gw, gh = 960, 260, 820, 520
            panel(c, gx - 40, gy - 60, gw + 80, gh + 140, 1, "red")
            text(c, "無重力での骨量の変化", gx + gw / 2, gy, 40, "white")
            c.drawLine(gx, gy + gh, gx + gw, gy + gh, P("white", 0.6, stroke=3))
            c.drawLine(gx, gy + 40, gx, gy + gh, P("white", 0.6, stroke=3))
            pth = skia.Path()
            kk = ramp(tt, 0.5, 4)
            for i in range(int(60 * kk) + 1):
                m = i / 10
                x = gx + m / 6 * gw
                y = gy + 80 + m * 1.2 / 8 * (gh - 120) * 1.0
                (pth.moveTo if i == 0 else pth.lineTo)(x, y)
            c.drawPath(pth, P("red", stroke=8))
            for m in range(7):
                text(c, f"{m}", gx + m / 6 * gw, gy + gh + 45, 28, "gray", weight="Bold")
            text(c, "（か月）", gx + gw - 20, gy + gh + 90, 26, "gray", weight="Bold")
            pct = 7.2 * kk
            text(c, f"−{pct:.1f}%", gx + gw * 0.75, gy + 240, 80, "red", stroke=10, stroke_col="#0A0004")
    # 2: ハッキング
    if t2 < t < t3 + 0.6:
        tt = t - t2
        with layer(c, ramp(t, t2, 0.6) * (1 - ramp(t, t3, 0.6))):
            CITY_FAR.draw(c, 900, 0, 1)
            CITY_NEAR.draw(c, 1080, 300, 1)
            c.drawRect(R(0, 0, W, H), P("red", 0.18 + 0.1 * math.sin(t * 10)))
            rng = np.random.default_rng(8)
            for k in range(10):
                x = rng.uniform(100, 1800)
                y = 800 - rng.uniform(0, 300) - 90 * tt * rng.uniform(0.5, 1.5)
                car(c, x, y, 0.8, "#888CA0", 1 if k % 2 else -1, 1, t)
            # グリッチ帯
            for k in range(6):
                yy = (rng.uniform(0, H) + t * 600 * (k + 1)) % H
                c.drawRect(R(0, yy, W, rng.uniform(4, 30)), P(["cyan", "red", "white"][k % 3], 0.25))
            with xf(c, 960, 420, 2 * math.sin(t * 40)):
                rrect(c, -460, -90, 920, 180, 20, P("#000000", 0.75))
                text(c, "SYSTEM BREACH", 0, 30, 96, "red", spacing=8, glow_col="#FF3B5C")
                text(c, "重力制御システムへの不正アクセスを検知", 0, 75, 30, "white", weight="Bold")
    # 3: ルールづくり
    if t > t3:
        tt = t - t3
        with layer(c, ramp(t, t3, 0.6)):
            bg_grad(c, "#0E1638", "#050816")
            panel(c, 560, 200, 800, 620)
            text(c, "重力社会のルール（案）", 960, 290, 52, "white")
            items = ["重力を管理するのは誰？", "AIにどこまで任せる？", "非常停止ボタンは誰が持つ？", "国をまたぐ重力の使い方は？"]
            for i, it in enumerate(items):
                kk = eoc((tt - 0.5 - i * 0.7) / 0.5)
                with layer(c, kk), xf(c, -40 * (1 - kk), 0):
                    y = 400 + i * 100
                    rrect(c, 640, y - 40, 52, 52, 10, P("cyan", stroke=4))
                    if tt > 1.2 + i * 0.7:
                        c.drawLine(652, y - 14, 664, y, P("cyan", stroke=6))
                        c.drawLine(664, y, 684, y - 32, P("cyan", stroke=6))
                    text(c, it, 720, y, 42, "white", weight="Bold", align="left")
    vignette(c, 0.6)


# ============================================================
# s13 エンディング
# ============================================================
def s13_end(c, t, S):
    bg_grad(c, "#050A24", "#000000")
    STARS.draw(c, t, 1.0, dx=-t * 3)
    t2 = S.L[2] - 0.3
    t3 = S.L[3] - 0.3
    ea = 1 - ramp(t, t3, 0.8) * 0.7
    with layer(c, ea):
        earth(c, 960, 1250, 760, t * 0.5)
        ax, ay = 960, 480 + 15 * math.sin(t * 1.2)
        glow(c, ax, ay, 260, "cyan", 0.3)
        ring_pulse(c, ax, ay, t, 2.2, 260, "cyan", 0.5)
        with layer(c, 1 - ramp(t, t3, 0.5)):
            apple(c, ax, ay, 70, rot=8 * math.sin(t * 0.8))
    if t > t2:
        k = eob((t - t2) / 0.6)
        with layer(c, clamp(k) * (1 - ramp(t, t3, 0.5))), xf(c, 960, 260, 0, max(0.01, k)):
            rrect(c, -520, -80, 1040, 140, 40, P("white"))
            tri = skia.Path()
            tri.moveTo(-60, 58)
            tri.lineTo(-10, 58)
            tri.lineTo(-70, 110)
            tri.close()
            c.drawPath(tri, P("white"))
            text(c, "あなたなら重力を何に使う？", 0, 22, 62, "#0A0F24")
    if t > t3:
        tt = t - t3
        with layer(c, ramp(t, t3, 0.6)):
            text(c, "ご視聴ありがとうございました", 960, 250, 64, "white", glow_col="#3DF5FF")
            k = eob((tt - 0.5) / 0.6)
            with xf(c, 760, 470, 0, max(0.01, k)):
                rrect(c, -230, -60, 460, 120, 60, P("red"))
                text(c, "チャンネル登録", 0, 18, 50, "white")
            k2 = eob((tt - 0.9) / 0.6)
            with xf(c, 1160, 470, 0, max(0.01, k2)):
                c.drawCircle(0, 0, 60, P("#FFFFFF"))
                text(c, "👍", 0, 22, 60, "#0A0F24") if False else None
                # 高評価アイコン (親指風)
                rrect(c, -30, -10, 22, 46, 6, P("#0A0F24"))
                th = skia.Path()
                th.moveTo(-4, 36)
                th.lineTo(-4, -8)
                th.lineTo(10, -40)
                th.quadTo(22, -44, 22, -28)
                th.lineTo(18, -10)
                th.lineTo(34, -10)
                th.quadTo(44, -8, 40, 4)
                th.lineTo(32, 32)
                th.quadTo(28, 38, 20, 38)
                th.close()
                c.drawPath(th, P("#0A0F24"))
            # ベル
            k3 = eob((tt - 1.3) / 0.6)
            with xf(c, 1350, 470, 15 * math.sin(tt * 10) * math.exp(-tt * 0.5), max(0.01, k3)):
                c.drawCircle(0, 0, 50, P("#FFFFFF"))
                bell = skia.Path()
                bell.moveTo(-26, 18)
                bell.quadTo(-22, -30, 0, -30)
                bell.quadTo(22, -30, 26, 18)
                bell.close()
                c.drawPath(bell, P("#0A0F24"))
                c.drawCircle(0, 26, 7, P("#0A0F24"))
            # マウスカーソル
            cx = lerp(1500, 790, eoc((tt - 1.8) / 1.0))
            cy = lerp(800, 500, eoc((tt - 1.8) / 1.0))
            if tt > 1.8:
                cur = skia.Path()
                cur.moveTo(cx, cy)
                cur.lineTo(cx, cy + 50)
                cur.lineTo(cx + 13, cy + 38)
                cur.lineTo(cx + 24, cy + 60)
                cur.lineTo(cx + 32, cy + 56)
                cur.lineTo(cx + 22, cy + 34)
                cur.lineTo(cx + 38, cy + 34)
                cur.close()
                c.drawPath(cur, P("white"))
                c.drawPath(cur, P("#000000", stroke=3))
            text(c, "次回の「もしも」もお楽しみに", 960, 700, 44, "cyan", weight="Bold")
    vignette(c, 0.6)


DRAW = {
    "s00_hook": s00_hook, "s01_title": s01_title, "s02_weak": s02_weak, "s03_spacetime": s03_spacetime,
    "s04_frog": s04_frog, "s05_tokamak": s05_tokamak, "s06_morning": s06_morning, "s07_home": s07_home,
    "s08_city": s08_city, "s09_care": s09_care, "s10_play": s10_play, "s11_space": s11_space,
    "s12_risk": s12_risk, "s13_end": s13_end,
}
