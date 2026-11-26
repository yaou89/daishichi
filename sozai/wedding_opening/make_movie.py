"""
結婚式オープニングムービー ジェネレーター（くすみカラー × ナチュラル）
--------------------------------------------------------------------
  python3 make_movie.py                     # config.json を読んで 1080p の mp4 を書き出す
  python3 make_movie.py --preview 30        # 30秒地点の静止画だけ確認（preview_30.png）
  python3 make_movie.py --stills            # 出品用サムネイル素材（stills/）を書き出す
  python3 make_movie.py --config xxx.json --out xxx.mp4

必要なもの: Python3 / numpy / Pillow / ffmpeg / 明朝体フォント（Noto Serif CJK JP か IPA明朝）
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1920, 1080, 30
DURATION = 80.0
BAR = 3.2  # BGMの1小節（75BPM）

# ---------------------------------------------------------------- カラー（くすみカラー）
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)

IVORY = hexc("#F5F0E9")
TEXT = hexc("#5B4B42")
SUB = hexc("#8C7B70")
GOLD = hexc("#B8975E")
BLUE = hexc("#8797A8")
PINK = hexc("#C49A92")
SAGE = hexc("#9AA893")
WHITE = hexc("#FFFFFF")

# ---------------------------------------------------------------- フォント
FONT_DIR = os.path.join(HERE, "fonts")
MINCHO_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
    ("/System/Library/Fonts/ヒラギノ明朝 ProN.ttc", 0),
    ("C:/Windows/Fonts/yumin.ttf", 0),
    ("/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf", 0),
]
_font_cache = {}


def font(kind, size):
    key = (kind, size)
    if key in _font_cache:
        return _font_cache[key]
    if kind == "mincho":
        for p, idx in MINCHO_CANDIDATES:
            if os.path.exists(p):
                f = ImageFont.truetype(p, size, index=idx)
                break
        else:
            raise SystemExit("明朝体フォントが見つかりません。MINCHO_CANDIDATES にパスを追加してください。")
    else:
        files = {
            "script": "GreatVibes.woff",
            "serif": "Cormorant-400.woff",
            "serif_light": "Cormorant-300.woff",
            "serif_med": "Cormorant-500.woff",
            "serif_it": "Cormorant-400i.woff",
        }
        f = ImageFont.truetype(os.path.join(FONT_DIR, files[kind]), size)
    _font_cache[key] = f
    return f


# ---------------------------------------------------------------- 描画ユーティリティ
def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ramp(t, a, b):
    """t が a→b で 0→1（イージング付き）"""
    if b <= a:
        return 1.0 if t >= a else 0.0
    return ease((t - a) / (b - a))


def text_img(text, kind, size, color, tracking=0.0, pad=None):
    """文字列を RGBA(float32) 配列にする。tracking は文字間隔（em 比）"""
    f = font(kind, size)
    asc, desc = f.getmetrics()
    pad = int(size * (0.6 if kind == "script" else 0.25)) if pad is None else pad
    if tracking:
        widths = [f.getlength(c) for c in text]
        total = sum(widths) + tracking * size * (len(text) - 1)
    else:
        total = f.getlength(text)
    w = int(math.ceil(total)) + pad * 2
    h = asc + desc + pad * 2
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if tracking:
        x = pad
        for c, cw in zip(text, widths):
            d.text((x, pad), c, font=f, fill=255)
            x += cw + tracking * size
    else:
        d.text((pad, pad), text, font=f, fill=255)
    a = np.asarray(m, np.float32) / 255
    # 余白を詰める（左右・上下）
    ys, xs = np.nonzero(a > 0.002)
    if len(xs):
        x0, x1 = max(xs.min() - 4, 0), min(xs.max() + 5, w)
        y0, y1 = max(ys.min() - 4, 0), min(ys.max() + 5, h)
        a = a[y0:y1, x0:x1]
    out = np.empty(a.shape + (4,), np.float32)
    out[..., :3] = color
    out[..., 3] = a
    return out


def vtext_img(text, size, color, gap=0.12):
    """縦書き1列"""
    f = font("mincho", size)
    step = int(size * (1 + gap))
    h = step * len(text) + size
    w = int(size * 1.6)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for i, c in enumerate(text):
        if c == " ":
            continue
        cw = f.getlength(c)
        d.text(((w - cw) / 2, i * step + size * 0.1), c, font=f, fill=255)
    a = np.asarray(m, np.float32) / 255
    ys = np.nonzero(a.max(axis=1) > 0.002)[0]
    a = a[max(ys.min() - 4, 0): ys.max() + 5]
    out = np.empty(a.shape + (4,), np.float32)
    out[..., :3] = color
    out[..., 3] = a
    return out


def pil_rgba(img):
    return np.asarray(img.convert("RGBA"), np.float32) / 255


def blit(dst, src, x, y, alpha=1.0):
    """左上 (x,y) に RGBA を合成"""
    if alpha <= 0.002:
        return
    h, w = src.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4] * alpha
    d = dst[y0:y1, x0:x1]
    d *= 1 - a
    d += s[..., :3] * a


def blit_c(dst, src, cx, cy, alpha=1.0):
    blit(dst, src, cx - src.shape[1] / 2, cy - src.shape[0] / 2, alpha)


def wipe(src, p, axis="x", soft=0.25):
    """文字がふわっと書かれていくようなソフトワイプ"""
    if p >= 1:
        return src
    out = src.copy()
    n = src.shape[1] if axis == "x" else src.shape[0]
    pos = np.arange(n, dtype=np.float32) / n
    edge = p * (1 + soft)
    m = np.clip((edge - pos) / soft, 0, 1)
    m = m * m * (3 - 2 * m)
    if axis == "x":
        out[..., 3] *= m[None, :]
    else:
        out[..., 3] *= m[:, None]
    return out


def blur_in(src, p, max_r=10):
    """ぼかし→くっきり（トレンドの表現）"""
    pad = int(max_r * 2)  # 位置がずれないよう常に同じ余白を付ける
    h, w = src.shape[:2]
    big = np.zeros((h + pad * 2, w + pad * 2, 4), np.float32)
    big[pad:pad + h, pad:pad + w] = src
    r = max_r * (1 - p) ** 1.5
    if r < 0.3:
        return big
    a = Image.fromarray((big[..., 3] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    out = big.copy()
    out[..., 3] = np.asarray(a, np.float32) / 255
    return out


def scale_img(src, s):
    if abs(s - 1) < 0.002:
        return src
    h, w = src.shape[:2]
    im = Image.fromarray((src * 255).astype(np.uint8), "RGBA")
    im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.BICUBIC)
    return pil_rgba(im)


def soft_noise(w, h, cells, seed):
    r = np.random.default_rng(seed)
    small = Image.fromarray((r.random((cells[1], cells[0])) * 255).astype(np.uint8))
    return np.asarray(small.resize((w, h), Image.BICUBIC), np.float32) / 255


# ---------------------------------------------------------------- 背景（和紙のような紙テクスチャ＋水彩のにじみ）
def make_background():
    bw, bh = W + 120, H + 80
    bg = np.ones((bh, bw, 3), np.float32) * IVORY
    n = soft_noise(bw, bh, (12, 8), 1)
    bg *= (0.975 + 0.05 * n)[..., None]
    rng = np.random.default_rng(3)
    layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    blobs = [((0.05, 0.1), PINK, 0.20), ((0.15, 0.0), SAGE, 0.16), ((0.95, 0.9), PINK, 0.18),
             ((0.85, 1.0), SAGE, 0.16), ((0.98, 0.15), hexc("#E3D3C3"), 0.25), ((0.02, 0.95), hexc("#E3D3C3"), 0.25)]
    for (fx, fy), col, a in blobs:
        for _ in range(5):
            cx, cy = fx * bw + rng.normal(0, 90), fy * bh + rng.normal(0, 70)
            rx, ry = rng.uniform(180, 380), rng.uniform(140, 300)
            c = tuple(int(v * 255) for v in col) + (int(255 * a * rng.uniform(0.4, 0.8)),)
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=c)
    layer = layer.filter(ImageFilter.GaussianBlur(90))
    blit(bg, pil_rgba(layer), 0, 0)
    # 周辺減光
    yy, xx = np.mgrid[0:bh, 0:bw].astype(np.float32)
    v = ((xx / bw - 0.5) ** 2 + (yy / bh - 0.5) ** 2)
    bg *= (1 - 0.10 * v * 2)[..., None]
    # 紙の粒子感
    bg += (np.random.default_rng(5).standard_normal((bh, bw, 1)).astype(np.float32) * 0.008)
    return np.clip(bg, 0, 1)


# ---------------------------------------------------------------- ボタニカル（ユーカリ・オリーブ・小花）
def leaf_sprite(length, width, color, pointed, rng):
    S = int(length * 1.2) + 8
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    pts = []
    for i in range(60):
        th = 2 * math.pi * i / 60
        x = math.cos(th)
        y = math.sin(th)
        if pointed:
            y = math.copysign(abs(1 - x * x) ** 0.75, y)
        pts.append((S / 2 + x * length / 2, S / 2 + y * width / 2))
    d.polygon(pts, fill=255)
    a = np.asarray(m, np.float32) / 255
    ab = np.asarray(m.filter(ImageFilter.GaussianBlur(max(2, width * 0.12))), np.float32) / 255
    edge = np.clip((a - ab) * 2.5, 0, 1)
    tex = soft_noise(S, S, (4, 4), int(rng.integers(1e6)))
    col = color[None, None, :] * (0.92 + 0.16 * tex[..., None])
    col = col * (1 - 0.28 * edge[..., None])
    # 葉脈
    vein = Image.new("L", (S, S), 0)
    ImageDraw.Draw(vein).line([(S / 2 - length * 0.42, S / 2), (S / 2 + length * 0.42, S / 2)], fill=90, width=max(1, int(width * 0.05)))
    vv = np.asarray(vein.filter(ImageFilter.GaussianBlur(1)), np.float32)[..., None] / 255
    col = col * (1 - vv) + np.minimum(col * 1.18, 1) * vv
    out = np.concatenate([col, (a * 0.88)[..., None]], axis=2)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def flower_sprite(r, color, rng):
    S = int(r * 2.6)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = S / 2
    rot = rng.uniform(0, 72)
    for k in range(5):
        ang = math.radians(rot + k * 72)
        px, py = c + math.cos(ang) * r * 0.55, c + math.sin(ang) * r * 0.55
        pet = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        col = tuple(int(v * 255) for v in color * rng.uniform(0.95, 1.05)) + (215,)
        ImageDraw.Draw(pet).ellipse([px - r * 0.52, py - r * 0.52, px + r * 0.52, py + r * 0.52], fill=col)
        img = Image.alpha_composite(img, pet)
    d = ImageDraw.Draw(img)
    d.ellipse([c - r * 0.2, c - r * 0.2, c + r * 0.2, c + r * 0.2], fill=(204, 172, 112, 255))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def bezier(p0, p1, p2, t):
    return ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])


def make_bouquet(seed, size=900):
    ss = 2
    S = size * ss
    rng = np.random.default_rng(seed)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sage_cols = [hexc("#9EAD98"), hexc("#B7C2AE"), hexc("#82957F"), hexc("#A9B3A0")]
    angles = np.linspace(8, 82, 6) + rng.normal(0, 4, 6)
    for i, ang in enumerate(angles):
        a = math.radians(ang)
        length = rng.uniform(0.55, 0.85) * S
        p0 = (S * 0.02, S * 0.02)
        p2 = (p0[0] + math.cos(a) * length, p0[1] + math.sin(a) * length)
        bend = rng.uniform(-0.18, 0.18) * length
        p1 = ((p0[0] + p2[0]) / 2 - math.sin(a) * bend, (p0[1] + p2[1]) / 2 + math.cos(a) * bend)
        pointed = i % 2 == 1
        col = sage_cols[i % len(sage_cols)]
        # 茎
        d = ImageDraw.Draw(canvas)
        pts = [bezier(p0, p1, p2, t) for t in np.linspace(0, 1, 40)]
        d.line(pts, fill=(130, 140, 118, 200), width=int(5 * ss))
        # 葉
        nleaf = 11 if pointed else 9
        for k in range(nleaf):
            t = 0.12 + 0.86 * k / (nleaf - 1)
            x, y = bezier(p0, p1, p2, t)
            x2, y2 = bezier(p0, p1, p2, min(t + 0.01, 1))
            tang = math.degrees(math.atan2(y2 - y, x2 - x))
            side = 1 if k % 2 else -1
            sc = 1 - 0.5 * t
            if pointed:
                L, Wd = 130 * ss * sc, 38 * ss * sc
                rot = tang + side * 38
            else:
                L, Wd = 92 * ss * sc, 84 * ss * sc
                rot = tang + side * 60
            lf = leaf_sprite(L, Wd, col * rng.uniform(0.94, 1.06), pointed, rng)
            lf = lf.rotate(-rot, resample=Image.BICUBIC, expand=True)
            off = L * 0.42
            cx = x + math.cos(math.radians(rot)) * off
            cy = y + math.sin(math.radians(rot)) * off
            canvas.alpha_composite(lf, (int(cx - lf.width / 2), int(cy - lf.height / 2)))
    # 小花（くすみピンク・クリーム）とかすみ草
    for _ in range(9):
        rr = rng.uniform(0.08, 0.38) * S
        aa = math.radians(rng.uniform(10, 80))
        col = [PINK, hexc("#E8D7C8"), hexc("#D9B8AE")][int(rng.integers(3))]
        fl = flower_sprite(rng.uniform(22, 40) * ss, col, rng)
        canvas.alpha_composite(fl, (int(math.cos(aa) * rr - fl.width / 2), int(math.sin(aa) * rr - fl.height / 2)))
    d = ImageDraw.Draw(canvas)
    for _ in range(70):
        rr = rng.uniform(0.1, 0.6) * S
        aa = math.radians(rng.uniform(5, 85))
        x, y = math.cos(aa) * rr, math.sin(aa) * rr
        r = rng.uniform(3, 7) * ss
        d.ellipse([x - r, y - r, x + r, y + r], fill=(250, 246, 238, 230))
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.8)).resize((size, size), Image.LANCZOS)
    return pil_rgba(canvas)


# ---------------------------------------------------------------- サンプル写真（実写の代わりに自動生成するボケ風イメージ）
def bokeh(img, n, cols, rmin, rmax, alpha, rng, blur=2):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(n):
        x, y = rng.uniform(0, img.width), rng.uniform(0, img.height)
        r = rng.uniform(rmin, rmax)
        c = cols[int(rng.integers(len(cols)))]
        a = int(255 * alpha * rng.uniform(0.4, 1))
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v * 255) for v in c) + (a,))
        d.ellipse([x - r, y - r, x + r, y + r], outline=tuple(int(min(v * 1.1, 1) * 255) for v in c) + (min(255, a + 30),), width=2)
    lay = lay.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img.convert("RGBA"), lay)


def vgrad(w, h, stops):
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, w, 3), np.float32)
    pos = [s[0] for s in stops]
    for c in range(3):
        out[..., c] = np.interp(ys, pos, [s[1][c] for s in stops])[:, None]
    return out


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def sample_photo(kind, w=1500, h=1000, seed=0):
    rng = np.random.default_rng(seed + hash(kind) % 1000)
    if kind == "sunset":
        a = vgrad(w, h, [(0, hexc("#9C93B5")), (0.35, hexc("#E7B3A6")), (0.6, hexc("#FAD9B5")), (0.62, hexc("#C9A8A8")), (1, hexc("#6F7491"))])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        sx, sy = w * 0.62, h * 0.55
        dist = np.hypot(xx - sx, yy - sy)
        a += (np.exp(-(dist / (h * 0.25)) ** 2) * 0.35)[..., None] * hexc("#FFE6C0")
        a += (np.clip(1 - dist / (h * 0.06), 0, 1) ** 0.5 * 0.5)[..., None]
        sea = yy > h * 0.6
        streak = (np.random.default_rng(1).random((h, 1)) > 0.6) * np.exp(-((xx - sx) / (w * 0.12)) ** 2) * 0.35
        a += (streak * sea)[..., None] * hexc("#FFE9CC")
        img = to_img(a).filter(ImageFilter.GaussianBlur(3))
        img = bokeh(img, 40, [hexc("#FFE3C2"), hexc("#FFD1C2")], 10, 40, 0.35, rng, 3)
    elif kind == "night":
        a = vgrad(w, h, [(0, hexc("#2C2F4A")), (0.6, hexc("#4E3F5E")), (1, hexc("#6B4A5A"))])
        img = to_img(a)
        cols = [hexc("#FFD59A"), hexc("#FFB8A8"), hexc("#F7E6C4"), hexc("#B7C6FF")]
        img = bokeh(img, 70, cols, 30, 80, 0.45, rng, 8)
        img = bokeh(img, 120, cols, 8, 26, 0.6, rng, 2)
    elif kind == "flowers":
        a = vgrad(w, h, [(0, hexc("#E9EFE3")), (0.5, hexc("#C8D3BA")), (1, hexc("#8FA184"))])
        img = to_img(a)
        img = bokeh(img, 60, [hexc("#F6F1EA"), hexc("#E9C9C3")], 40, 110, 0.5, rng, 18)
        img = bokeh(img, 80, [hexc("#F3D3CD"), hexc("#FFFFFF"), hexc("#E8B7AE")], 18, 45, 0.85, rng, 4)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        for _ in range(22):
            fl = flower_sprite(rng.uniform(40, 90), [PINK, hexc("#F4E9E0"), hexc("#E2B9B1")][int(rng.integers(3))], rng)
            lay.alpha_composite(fl, (int(rng.uniform(-50, w)), int(rng.uniform(h * 0.45, h))))
        img = Image.alpha_composite(img, lay.filter(ImageFilter.GaussianBlur(1.5)))
    elif kind == "sakura":
        a = vgrad(w, h, [(0, hexc("#CFDDEB")), (1, hexc("#F3E9EC"))])
        img = to_img(a).convert("RGBA")
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for _ in range(5):
            p0 = (rng.uniform(-200, 0), rng.uniform(0, h * 0.6))
            p2 = (rng.uniform(w * 0.4, w * 1.1), rng.uniform(-100, h * 0.4))
            p1 = ((p0[0] + p2[0]) / 2, min(p0[1], p2[1]) + rng.uniform(100, 300))
            pts = [bezier(p0, p1, p2, t) for t in np.linspace(0, 1, 30)]
            d.line(pts, fill=(105, 80, 76, 200), width=int(rng.uniform(8, 18)))
        img = Image.alpha_composite(img, lay.filter(ImageFilter.GaussianBlur(5)))
        img = bokeh(img, 120, [hexc("#F7D5DC"), hexc("#F2BFCB"), hexc("#FFF2F4")], 14, 40, 0.8, rng, 3)
        img = bokeh(img, 40, [hexc("#F7D5DC"), hexc("#FFFFFF")], 50, 120, 0.4, rng, 16)
    else:  # light（プロフィール用のやわらかな光）
        a = vgrad(w, h, [(0, hexc("#F6EFE6")), (1, hexc("#E2D3C5"))])
        img = to_img(a)
        img = bokeh(img, 50, [hexc("#FFFFFF"), hexc("#F6E2D3")], 20, 70, 0.5, rng, 10)
    img = img.convert("RGB")
    arr = np.asarray(img, np.float32) / 255
    # フィルム調の色味（少し褪せた感じ）
    arr = arr * 0.92 + 0.06
    arr = arr * np.array([1.02, 1.0, 0.97], np.float32)
    arr += np.random.default_rng(seed + 9).standard_normal(arr.shape[:2] + (1,)).astype(np.float32) * 0.012
    return to_img(arr)


def profile_placeholder(initial, tint, w=900, h=1200):
    img = sample_photo("light", w, h, seed=ord(initial))
    arr = np.asarray(img, np.float32) / 255
    arr = arr * 0.75 + tint * 0.25 + 0.05
    img = to_img(arr)
    f = font("script", 520)
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).text((w / 2, h * 0.47), initial, font=f, fill=255, anchor="mm")
    lay = Image.new("RGB", img.size, (255, 255, 255))
    img = Image.composite(lay, img, m.point(lambda v: v * 0.85))
    f2 = font("serif_med", 34)
    d = ImageDraw.Draw(img)
    d.text((w / 2, h * 0.80), "Y O U R   P H O T O", font=f2, fill=(255, 255, 255), anchor="mm")
    return img


def load_photo(path, fallback):
    if path:
        p = path if os.path.isabs(path) else os.path.join(HERE, path)
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
        print("写真が見つかりません:", p, "→ サンプル画像を使用します")
    return fallback()


def cover_crop(img, w, h):
    """img を w:h の比率に中央クロップ"""
    r = w / h
    iw, ih = img.size
    if iw / ih > r:
        nw = int(ih * r)
        img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw / r)
        img = img.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    return img


def kenburns(img, w, h, z, dx=0.0, dy=0.0):
    """img（w:h比率）を z 倍ズームして w×h に（dx,dy は -1..1 のパン）"""
    iw, ih = img.size
    cw, ch = iw / z, ih / z
    cx = iw / 2 + dx * (iw - cw) / 2
    cy = ih / 2 + dy * (ih - ch) / 2
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return np.asarray(img.resize((w, h), Image.BICUBIC, box=box), np.float32) / 255


def arch_mask(w, h, ss=3):
    m = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(m)
    r = w * ss / 2
    d.rectangle([0, r, w * ss, h * ss], fill=255)
    d.ellipse([0, 0, w * ss - 1, 2 * r], fill=255)
    return np.asarray(m.resize((w, h), Image.LANCZOS), np.float32) / 255


def arch_outline(w, h, color, width=2, ss=3):
    m = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(m)
    r = w * ss / 2
    lw = width * ss
    d.arc([lw / 2, lw / 2, w * ss - lw / 2, 2 * r - lw / 2], 180, 360, fill=255, width=lw)
    d.line([(lw / 2, r), (lw / 2, h * ss - lw / 2)], fill=255, width=lw)
    d.line([(w * ss - lw / 2, r), (w * ss - lw / 2, h * ss - lw / 2)], fill=255, width=lw)
    d.line([(0, h * ss - lw / 2), (w * ss, h * ss - lw / 2)], fill=255, width=lw)
    a = np.asarray(m.resize((w, h), Image.LANCZOS), np.float32) / 255
    out = np.empty((h, w, 4), np.float32)
    out[..., :3] = color
    out[..., 3] = a
    return out


def shadow(mask, blur=26, strength=0.28, pad=60):
    h, w = mask.shape
    big = np.zeros((h + pad * 2, w + pad * 2), np.float32)
    big[pad:pad + h, pad:pad + w] = mask
    b = np.asarray(Image.fromarray((big * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
    out = np.zeros(b.shape + (4,), np.float32)
    out[..., :3] = hexc("#6A584C")
    out[..., 3] = b * strength
    return out


def hline(w, color, thick=2):
    a = np.ones((thick + 2, w), np.float32)
    a[0] = a[-1] = 0.35
    x = np.linspace(-1, 1, w)
    a *= np.clip((1 - np.abs(x)) * 6, 0, 1)[None, :]
    out = np.empty(a.shape + (4,), np.float32)
    out[..., :3] = color
    out[..., 3] = a
    return out


def dot_sprite(r, color):
    S = int(r * 8) | 1
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - S // 2
    d = np.hypot(xx, yy)
    a = np.clip(1 - (d - r * 0.6) / (r * 0.6), 0, 1) + np.exp(-(d / (r * 2.2)) ** 2) * 0.45
    out = np.empty((S, S, 4), np.float32)
    out[..., :3] = color
    out[..., 3] = np.clip(a, 0, 1)
    return out


# ---------------------------------------------------------------- アセット構築
A = {}


def build_assets(cfg):
    print("素材を準備中…")
    A["bg"] = make_background()
    A["bq1"] = make_bouquet(11)
    A["bq2"] = np.ascontiguousarray(make_bouquet(23)[::-1, ::-1])
    A["dots"] = [dot_sprite(r, GOLD) for r in (1.4, 2.0, 2.8, 3.6)]
    A["dot_white"] = [dot_sprite(r, hexc("#FFF8EA")) for r in (2.0, 3.0, 4.0)]
    rng = np.random.default_rng(42)
    N = 70
    A["pt"] = dict(x=rng.uniform(0, W, N), y=rng.uniform(0, H, N), vy=rng.uniform(8, 26, N),
                   ph=rng.uniform(0, 6.28, N), sz=rng.integers(0, 4, N), sp=rng.uniform(0.6, 1.6, N))
    NB = 110
    ang = rng.uniform(0, 6.28, NB)
    A["burst"] = dict(ang=ang, sp=rng.uniform(250, 900, NB), sz=rng.integers(0, 3, NB), ph=rng.uniform(0, 6.28, NB))

    # --- イントロ
    A["welcome"] = text_img("Welcome to our wedding", "script", 150, TEXT)
    A["caps"] = text_img(cfg["couple_caps"], "serif_med", 34, SUB, tracking=0.45)
    A["date_s"] = text_img(cfg["date"], "serif", 34, GOLD, tracking=0.3)

    # --- メッセージ（縦書き）
    A["msg1"] = [vtext_img(s, 50, TEXT) for s in cfg["message1"]]
    A["msg2"] = [vtext_img(s, 50, TEXT) for s in cfg["message2"]]
    A["msg3"] = [text_img(s, "mincho", 52, TEXT, tracking=0.12) for s in cfg["message3"]]
    A["coming"] = [text_img(cfg["coming"][0], "mincho", 58, TEXT, tracking=0.14),
                   text_img(cfg["coming"][1], "mincho", 36, SUB, tracking=0.14)]
    A["coming_en"] = text_img("Coming soon", "script", 120, GOLD)
    A["thank_en"] = text_img("Thank you", "script", 96, GOLD)
    A["message_en"] = text_img("Message", "script", 96, GOLD)

    # --- プロフィール
    PW, PH = 560, 760
    A["arch_mask"] = arch_mask(PW, PH)
    A["arch_shadow"] = shadow(A["arch_mask"])
    A["arch_line"] = arch_outline(PW + 44, PH + 44, GOLD, 2)
    for who, tint in (("groom", BLUE), ("bride", PINK)):
        p = cfg[who]
        ph = load_photo(p.get("photo"), lambda p=p, tint=tint: profile_placeholder(p["initial"], tint))
        A[who + "_photo"] = cover_crop(ph, PW * 2, PH * 2).resize((PW * 2, PH * 2), Image.LANCZOS)
        A[who + "_label"] = text_img(p["label"], "script", 130, tint * 0.85)
        A[who + "_name"] = text_img(p["name_ja"], "mincho", 74, TEXT, tracking=0.12)
        A[who + "_en"] = text_img(p["name_en"], "serif_it", 40, SUB, tracking=0.05)
        A[who + "_items"] = [(text_img(k, "mincho", 24, GOLD, tracking=0.2), text_img(v, "mincho", 34, TEXT, tracking=0.06))
                             for k, v in p["profile"]]
    A["line"] = hline(520, GOLD, 1)

    # --- ストーリー
    SW, SH = 900, 600
    A["story"] = []
    for i, s in enumerate(cfg["story"]):
        ph = load_photo(s.get("photo"), lambda s=s, i=i: sample_photo(s.get("sample", "light"), seed=i))
        ph = cover_crop(ph, SW * 2, SH * 2).resize((SW * 2, SH * 2), Image.LANCZOS)
        A["story"].append(dict(photo=ph,
                               date=text_img(s["date"], "serif_med", 46, GOLD, tracking=0.25),
                               title=text_img(s["title"], "mincho", 60, TEXT, tracking=0.12),
                               en=text_img(s["en"], "script", 84, PINK * 0.9)))
    frame = np.ones((SH + 28, SW + 28), np.float32)
    A["story_shadow"] = shadow(frame, 22, 0.25)
    A["our_story"] = text_img("Our Story", "script", 92, TEXT)

    # --- カウントダウン
    S = 600
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - S / 2
    A["cd_r"] = np.hypot(xx, yy)
    A["cd_ang"] = ((np.arctan2(xx, -yy) / (2 * np.pi)) % 1.0)
    A["cd_num"] = {n: text_img(str(n), "serif_light", 300, TEXT) for n in range(1, 6)}

    # --- エンディング
    A["fin_names"] = text_img(cfg["couple_en"], "script", 200, TEXT)
    A["fin_event"] = text_img(cfg["event_en"], "serif_med", 36, SUB, tracking=0.5)
    A["fin_date"] = text_img(cfg["date"], "serif", 46, GOLD, tracking=0.3)
    A["fin_close"] = text_img(cfg["closing"], "mincho", 36, TEXT, tracking=0.16)
    A["fin_line"] = hline(700, GOLD, 1)

    wm = cfg.get("watermark")
    A["wm"] = text_img(wm, "serif_med", 30, TEXT, tracking=0.5) if wm else None
    A["cfg"] = cfg


# ---------------------------------------------------------------- シーン
def env(t, a, b, fi=0.6, fo=0.6):
    """シーンの出現・消失"""
    if t < a or t > b:
        return 0.0
    return min(ramp(t, a, a + fi), 1 - ramp(t, b - fo, b))


def draw_particles(fr, t, amount=1.0):
    p = A["pt"]
    for i in range(len(p["x"])):
        y = (p["y"][i] - p["vy"][i] * t) % (H + 40) - 20
        x = p["x"][i] + 18 * math.sin(t * 0.4 * p["sp"][i] + p["ph"][i])
        tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.2 * p["sp"][i] + p["ph"][i]))
        blit_c(fr, A["dots"][p["sz"][i]], x, y, tw * 0.75 * amount)


def draw_botanicals(fr, t, a):
    if a <= 0:
        return
    sway = math.sin(t * 0.5) * 6
    k = ease_out(ramp(t, 0.0, 2.4) if t < 3 else 1.0)
    # プロフィール〜ストーリーの間は植物を少し画面外へ逃がして主役を広く見せる
    retreat = min(ramp(t, 6 * BAR - 0.8, 6 * BAR + 0.6), 1 - ramp(t, 16 * BAR - 0.6, 16 * BAR + 0.8))
    a *= 1 - 0.25 * retreat
    off = (1 - k) * 120 + retreat * 190
    blit(fr, A["bq1"], -70 - off + sway, -90 - off + sway * 0.5, a * k)
    bq = A["bq2"]
    blit(fr, bq, W - bq.shape[1] + 70 + off - sway, H - bq.shape[0] + 90 + off - sway * 0.5, a * k)


def sc_intro(fr, t):
    a = env(t, 0, 6.4, 0.01, 0.7)
    w = A["welcome"]
    blit_c(fr, wipe(w, ease((t - 0.8) / 2.6), "x", 0.18), W / 2, H / 2 - 40, a)
    a2 = a * ramp(t, 3.0, 4.2)
    blit_c(fr, A["caps"], W / 2, H / 2 + 110 - 10 * a2, a2)
    blit_c(fr, A["date_s"], W / 2, H / 2 + 170 - 10 * a2, a * ramp(t, 3.5, 4.7))


def sc_vertical(fr, t, cols, t0, t1, en_img):
    a = env(t, t0, t1, 0.4, 0.7)
    if a <= 0:
        return
    lt = t - t0
    gap = 96
    n = len(cols)
    total_w = gap * (n - 1)
    x_right = W / 2 + total_w / 2
    top = H / 2 - 260
    for i, c in enumerate(cols):
        p = (lt - 0.5 - i * 0.75) / 1.3
        if p <= 0:
            continue
        x = x_right - i * gap
        blit(fr, wipe(c, ease(p), "y", 0.3), x - c.shape[1] / 2, top, a)
    if en_img is not None:
        blit_c(fr, en_img, W / 2, top - 90, a * ramp(lt, 0.2, 1.2) * 0.9)


def sc_profile(fr, t, who, t0, t1, photo_left):
    a = env(t, t0, t1, 0.7, 0.7)
    if a <= 0:
        return
    lt = t - t0
    PW, PH = 560, 760
    px = 640 if photo_left else W - 640
    py = H / 2 + 10
    # 写真（アーチフレーム）
    k = ease_out((lt) / 1.4)
    slide = (1 - k) * (-60 if photo_left else 60)
    pa = a * k
    blit_c(fr, A["arch_shadow"], px + slide + 10, py + 18, pa)
    img = kenburns(A[who + "_photo"], PW, PH, 1.0 + 0.07 * (lt / (t1 - t0)), 0, -0.3)
    rgba = np.concatenate([img, A["arch_mask"][..., None]], axis=2)
    blit_c(fr, rgba, px + slide, py, pa)
    blit_c(fr, A["arch_line"], px + slide * 0.6 + 16, py + 16, pa * ramp(lt, 0.6, 1.6))
    # テキスト（ブロック全体を上下中央に配置）
    tx = 1060 if photo_left else 360
    lab = A[who + "_label"]
    items = A[who + "_items"]
    block = (lab.shape[0] + 24 + A[who + "_name"].shape[0] + 18 + A[who + "_en"].shape[0] + 18 + 52
             + sum(k_.shape[0] + v_.shape[0] + 38 for k_, v_ in items) - 38)
    y = H / 2 - block / 2 + 10
    blit(fr, wipe(lab, ease((lt - 0.7) / 1.3), "x", 0.2), tx - 14, y, a)
    y += lab.shape[0] + 24
    for img_, dt in ((A[who + "_name"], 1.4), (A[who + "_en"], 1.7)):
        q = ramp(lt, dt, dt + 0.8)
        pad = int(8 * 2)
        blit(fr, blur_in(img_, q, 8), tx - 16 * (1 - q) - pad, y - pad, a * q)
        y += img_.shape[0] + 18
    blit(fr, wipe(A["line"], ease((lt - 2.0) / 0.9), "x", 0.4), tx, y + 14, a)
    y += 52
    for i, (k_, v_) in enumerate(items):
        q = ramp(lt, 2.4 + i * 0.45, 3.2 + i * 0.45)
        yy = y + (1 - q) * 14
        blit(fr, k_, tx, yy, a * q)
        blit(fr, v_, tx, yy + k_.shape[0] + 8, a * q)
        y += k_.shape[0] + v_.shape[0] + 38


def sc_story(fr, t):
    t0 = 12 * BAR
    n = len(A["story"])
    t1 = t0 + 4 * BAR
    a_all = env(t, t0, t1, 0.6, 0.6)
    if a_all <= 0:
        return
    blit_c(fr, A["our_story"], W / 2, 110, a_all * 0.9)
    seg = (t1 - t0) / n
    SW, SH = 900, 600
    for i, s in enumerate(A["story"]):
        s0, s1 = t0 + i * seg, t0 + (i + 1) * seg
        a = env(t, s0, s1, 0.5, 0.45)
        if a <= 0:
            continue
        lt = t - s0
        left = i % 2 == 0
        px = 690 if left else W - 690
        py = H / 2 + 40
        k = ease_out(lt / 1.0)
        slide = (1 - k) * (70 if left else -70)
        blit_c(fr, A["story_shadow"], px + slide + 8, py + 14, a)
        card = np.ones((SH + 28, SW + 28, 4), np.float32)
        card[..., :3] = hexc("#FFFDF9")
        card[14:14 + SH, 14:14 + SW, :3] = kenburns(s["photo"], SW, SH, 1.02 + 0.06 * lt / seg, (-0.4 if left else 0.4) * lt / seg, 0)
        blit_c(fr, card, px + slide, py, a)
        cx = W - 420 if left else 420
        for j, (img_, dy) in enumerate(((s["date"], -110), (s["title"], -20), (s["en"], 80))):
            q = ramp(lt, 0.4 + j * 0.25, 1.1 + j * 0.25)
            if j == 2:
                blit_c(fr, wipe(img_, q, "x", 0.25), cx, py + dy, a)
            else:
                blit_c(fr, img_, cx, py + dy + (1 - q) * 14, a * q)


def sc_message3(fr, t, t0, t1):
    a = env(t, t0, t1, 0.4, 0.7)
    if a <= 0:
        return
    lt = t - t0
    blit_c(fr, A["thank_en"], W / 2, H / 2 - 210, a * ramp(lt, 0.2, 1.2) * 0.9)
    for i, img_ in enumerate(A["msg3"]):
        q = ramp(lt, 0.6 + i * 0.7, 1.6 + i * 0.7)
        blit_c(fr, blur_in(img_, q, 10), W / 2, H / 2 - 60 + i * 100, a * q)


def sc_coming(fr, t, t0, t1):
    a = env(t, t0, t1, 0.4, 0.5)
    if a <= 0:
        return
    lt = t - t0
    blit_c(fr, wipe(A["coming_en"], ease((lt - 0.2) / 1.6), "x", 0.2), W / 2, H / 2 - 150, a)
    q = ramp(lt, 1.0, 2.0)
    blit_c(fr, blur_in(A["coming"][0], q, 10), W / 2, H / 2 + 20, a * q)
    q = ramp(lt, 1.8, 2.8)
    blit_c(fr, A["coming"][1], W / 2, H / 2 + 120 + (1 - q) * 12, a * q)


def sc_countdown(fr, t, t0):
    if t < t0 or t >= t0 + 8.0:
        return
    lt = t - t0
    idx = int(lt / 1.6)
    n = 5 - idx
    u = (lt - idx * 1.6) / 1.6
    S = 600
    cx, cy = W / 2, H / 2
    R = 230
    r, ang = A["cd_r"], A["cd_ang"]
    ring_a = np.clip(2.4 - np.abs(r - R), 0, 1)
    base = ring_a * 0.3
    prog = ring_a * np.clip((ease(u) * 1.0 - ang) * 300, 0, 1)
    a_in = ramp(lt, 0, 0.4)
    lay = np.empty((S, S, 4), np.float32)
    lay[..., :3] = GOLD
    lay[..., 3] = np.maximum(base, prog)
    blit_c(fr, lay, cx, cy, a_in)
    # 数字
    q = ease_out(u / 0.3)
    num = scale_img(A["cd_num"][n], 1.12 - 0.12 * q)
    fade = min(q, 1 - ramp(u, 0.85, 1.0))
    blit_c(fr, num, cx, cy - 8, fade)
    # 外周の小さな光
    a0 = 2 * math.pi * ease(u)
    blit_c(fr, A["dot_white"][2], cx + R * math.sin(a0), cy - R * math.cos(a0), 0.9 * a_in)
    blit_c(fr, A["dots"][3], cx + R * math.sin(a0), cy - R * math.cos(a0), 0.9 * a_in)
    blit_c(fr, A["caps"], W / 2, H - 150, ramp(lt, 0, 0.6) * 0.8)


def sc_final(fr, t, t0):
    if t < t0:
        return
    lt = t - t0
    # 光のバースト
    b = A["burst"]
    if lt < 4.0:
        for i in range(len(b["ang"])):
            dist = b["sp"][i] * (1 - math.exp(-lt * 1.6)) / 1.6
            x = W / 2 + math.cos(b["ang"][i]) * dist
            y = H / 2 + math.sin(b["ang"][i]) * dist * 0.7 + lt * 18
            al = (1 - ramp(lt, 1.2, 4.0)) * (0.5 + 0.5 * math.sin(lt * 9 + b["ph"][i]))
            blit_c(fr, A["dots"][b["sz"][i] + 1], x, y, al)
    flash = math.exp(-lt * 3.0) * 0.55
    if flash > 0.01:
        fr *= 1 - flash
        fr += flash * hexc("#FFFBF2")
    blit_c(fr, A["fin_event"], W / 2, H / 2 - 175 - 10 * ramp(lt, 0.4, 1.4), ramp(lt, 0.4, 1.4))
    blit_c(fr, wipe(A["fin_names"], ease((lt - 0.2) / 2.4), "x", 0.15), W / 2, H / 2 - 30, 1)
    blit_c(fr, wipe(A["fin_line"], ease((lt - 1.6) / 1.0), "x", 0.4), W / 2, H / 2 + 105, 1)
    blit_c(fr, A["fin_date"], W / 2, H / 2 + 165, ramp(lt, 2.0, 3.0))
    q = ramp(lt, 2.8, 3.8)
    blit_c(fr, blur_in(A["fin_close"], q, 8), W / 2, H / 2 + 255, q)


def render_frame(t):
    cfg = A["cfg"]
    # 背景はゆっくり流れる
    ox = int(60 + 50 * math.sin(t * 0.05))
    oy = int(40 + 30 * math.cos(t * 0.04))
    fr = A["bg"][oy:oy + H, ox:ox + W].copy()
    draw_botanicals(fr, t, 1.0)
    draw_particles(fr, t, 1.0 if t < 72 else 1.0 - 0.5 * ramp(t, 72, 74))

    sc_intro(fr, t)
    sc_vertical(fr, t, A["msg1"], 2 * BAR, 4 * BAR, A["message_en"])
    sc_vertical(fr, t, A["msg2"], 4 * BAR, 6 * BAR, None)
    sc_profile(fr, t, "groom", 6 * BAR, 9 * BAR, True)
    sc_profile(fr, t, "bride", 9 * BAR, 12 * BAR, False)
    sc_story(fr, t)
    sc_message3(fr, t, 16 * BAR, 18 * BAR)
    sc_coming(fr, t, 18 * BAR, 20 * BAR)
    sc_countdown(fr, t, 20 * BAR)
    sc_final(fr, t, 72.0)

    # 最後は白へフェード
    wf = ramp(t, 78.2, 80.0)
    if wf > 0:
        fr *= 1 - wf
        fr += wf * hexc("#FFFDF8")
    if A["wm"] is not None:
        blit(fr, A["wm"], W - A["wm"].shape[1] - 48, 40, 0.35)
    return (np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8)


# ---------------------------------------------------------------- 書き出し
def encode_segment(args):
    idx, f0, f1, path = args
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-g", str(FPS * 2), path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(render_frame(f / FPS).tobytes())
        if idx == 0 and (f - f0) % 60 == 0:
            print(f"  レンダリング中… {100 * (f - f0) / (f1 - f0):.0f}%", flush=True)
    p.stdin.close()
    p.wait()
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "wedding_opening_sample.mp4"))
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    build_assets(cfg)

    if args.preview is not None:
        for t in args.preview:
            out = os.path.join(HERE, f"preview_{t:g}.png")
            Image.fromarray(render_frame(t)).save(out)
            print("wrote", out)
        return
    if args.stills:
        d = os.path.join(HERE, "stills")
        os.makedirs(d, exist_ok=True)
        for name, t in (("01_welcome", 5.2), ("02_message", 12.2), ("03_groom", 27.5), ("04_bride", 37.0),
                        ("05_story", 44.0), ("06_thankyou", 56.5), ("07_countdown", 66.5), ("08_final", 77.0)):
            Image.fromarray(render_frame(t)).save(os.path.join(d, name + ".jpg"), quality=92)
        print("wrote", d)
        return

    total = int(DURATION * FPS)
    tmp = tempfile.mkdtemp()
    n = max(1, args.workers)
    bounds = [round(total * i / n) for i in range(n + 1)]
    jobs = [(i, bounds[i], bounds[i + 1], os.path.join(tmp, f"seg{i}.mp4")) for i in range(n)]
    print(f"{total}フレームを{n}並列でレンダリングします")
    with Pool(n) as pool:
        segs = pool.map(encode_segment, jobs)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")

    bgm = cfg.get("bgm")
    if bgm and not os.path.isabs(bgm):
        bgm = os.path.join(HERE, bgm)
    if not bgm or not os.path.exists(bgm):
        bgm = os.path.join(tmp, "bgm.wav")
        subprocess.run([sys.executable, os.path.join(HERE, "music.py"), bgm], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", bgm,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", f"afade=t=out:st={DURATION - 2.5}:d=2.5", "-t", str(DURATION), "-movflags", "+faststart", args.out],
                   check=True)
    print("完成:", args.out)


if __name__ == "__main__":
    main()
