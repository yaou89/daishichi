"""
結婚式オープニングムービー ラグジュアリー版（ミッドナイトネイビー × ゴールド箔）
--------------------------------------------------------------------
  python3 make_movie_luxe.py                  # config.json → wedding_opening_luxe_sample.mp4
  python3 make_movie_luxe.py --preview 5 30   # 指定秒の静止画だけ確認
  python3 make_movie_luxe.py --stills         # 出品用の静止画（stills/）
  python3 make_movie_luxe.py --config 田中様.json --out 田中様.mp4

必要: Python3 / numpy / Pillow / ffmpeg / 明朝体（Noto Serif CJK JP Light 推奨）
BGM: config の bgm が空なら music_luxe.py（fluidsynth）で自動生成
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
DURATION = 90.0
BAR = 3.2
CLIMAX = 75.2


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


NAVY_C = hexc("#1A2640")
NAVY_E = hexc("#04070D")
IVORY = hexc("#F2EADB")
CHAMP = hexc("#D9C9A8")
GOLD = hexc("#C9A560")
GOLD_L = hexc("#F1DFAE")
WARM = hexc("#FFD9A0")

GOLD_STOPS = [(0.00, "#6E4F22"), (0.16, "#B08640"), (0.30, "#E9CF8E"), (0.38, "#FFF3CC"), (0.48, "#D2AC5E"),
              (0.64, "#8A6630"), (0.80, "#D6B46C"), (0.90, "#F4E2AA"), (1.00, "#6E4F22")]

# ---------------------------------------------------------------- フォント
FONT_DIR = os.path.join(HERE, "fonts")
MINCHO = {
    "light": [("/usr/share/fonts/opentype/noto/NotoSerifCJK-Light.ttc", 0),
              ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
              ("/System/Library/Fonts/ヒラギノ明朝 ProN.ttc", 0), ("C:/Windows/Fonts/yumin.ttf", 0),
              ("/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf", 0)],
    "regular": [("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
                ("/System/Library/Fonts/ヒラギノ明朝 ProN.ttc", 0), ("C:/Windows/Fonts/yumin.ttf", 0),
                ("/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf", 0)],
}
LATIN = {"cinzel": "Cinzel-400.woff", "cinzel_m": "Cinzel-500.woff", "script": "PinyonScript.woff",
         "serif": "Cormorant-400.woff", "serif_l": "Cormorant-300.woff", "serif_it": "Cormorant-400i.woff"}
_fc = {}


def font(kind, size):
    k = (kind, size)
    if k not in _fc:
        if kind.startswith("mincho"):
            w = kind.split("_")[1] if "_" in kind else "light"
            for p, i in MINCHO[w]:
                if os.path.exists(p):
                    _fc[k] = ImageFont.truetype(p, size, index=i)
                    break
            else:
                raise SystemExit("明朝体フォントが見つかりません。MINCHO にパスを追加してください。")
        else:
            _fc[k] = ImageFont.truetype(os.path.join(FONT_DIR, LATIN[kind]), size)
    return _fc[k]


# ---------------------------------------------------------------- 基本ユーティリティ
def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ramp(t, a, b):
    return (1.0 if t >= a else 0.0) if b <= a else ease((t - a) / (b - a))


def env(t, a, b, fi=0.6, fo=0.6):
    if t < a or t > b:
        return 0.0
    return min(ramp(t, a, a + fi), 1 - ramp(t, b - fo, b))


def soft_noise(w, h, cells, seed):
    r = np.random.default_rng(seed)
    small = Image.fromarray((r.random((cells[1], cells[0])) * 255).astype(np.uint8))
    return np.asarray(small.resize((w, h), Image.BICUBIC), np.float32) / 255


def gblur(a, r):
    """float 配列（2D）のガウスぼかし"""
    if r <= 0:
        return a
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255


def gblur_f(a, r):
    """精度を保つため 0..1 を 16bit 相当で扱うぼかし（大きい値用）"""
    m = max(a.max(), 1e-6)
    im = Image.fromarray((a / m * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255 * m


def mask_text(text, kind, size, tracking=0.0, pad=None):
    f = font(kind, size)
    asc, desc = f.getmetrics()
    pad = int(size * (0.7 if kind == "script" else 0.3)) if pad is None else pad
    if tracking:
        widths = [f.getlength(c) for c in text]
        total = sum(widths) + tracking * size * (len(text) - 1)
    else:
        total = f.getlength(text)
    w, h = int(math.ceil(total)) + pad * 2, asc + desc + pad * 2
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
    ys, xs = np.nonzero(a > 0.002)
    return a[max(ys.min() - 2, 0):ys.max() + 3, max(xs.min() - 2, 0):xs.max() + 3]


def mask_vtext(text, size, gap=0.14):
    f = font("mincho", size)
    step = int(size * (1 + gap))
    h, w = step * len(text) + size, int(size * 1.6)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for i, c in enumerate(text):
        if c != " ":
            d.text(((w - f.getlength(c)) / 2, i * step + size * 0.1), c, font=f, fill=255)
    a = np.asarray(m, np.float32) / 255
    ys = np.nonzero(a.max(axis=1) > 0.002)[0]
    return a[max(ys.min() - 2, 0):ys.max() + 3]


def pad_mask(a, p):
    return np.pad(a, p)


def colorize(a, color):
    out = np.empty(a.shape + (4,), np.float32)
    out[..., :3] = color
    out[..., 3] = a
    return out


def blit(dst, src, x, y, alpha=1.0):
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


def add(dst, src_rgb, x, y, k=1.0):
    """加算合成（光の表現）"""
    if k <= 0.002:
        return
    h, w = src_rgb.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    dst[y0:y1, x0:x1] += src_rgb[y0 - y:y1 - y, x0 - x:x1 - x] * k


def add_c(dst, src, cx, cy, k=1.0):
    add(dst, src, cx - src.shape[1] / 2, cy - src.shape[0] / 2, k)


def wipe(src, p, axis="x", soft=0.25, reverse=False):
    if p >= 1:
        return src
    out = src.copy()
    n = src.shape[1] if axis == "x" else src.shape[0]
    pos = np.arange(n, dtype=np.float32) / n
    if reverse:
        pos = 1 - pos
    m = np.clip((p * (1 + soft) - pos) / soft, 0, 1)
    m = m * m * (3 - 2 * m)
    out[..., 3] *= m[None, :] if axis == "x" else m[:, None]
    return out


def wipe_center(src, p, soft=0.2):
    if p >= 1:
        return src
    out = src.copy()
    n = src.shape[1]
    pos = np.abs(np.arange(n, dtype=np.float32) / n - 0.5) * 2
    m = np.clip((p * (1 + soft) - pos) / soft, 0, 1)
    out[..., 3] *= (m * m * (3 - 2 * m))[None, :]
    return out


def blur_in(src, p, max_r=10):
    pad = int(max_r * 2)
    big = np.pad(src, ((pad, pad), (pad, pad), (0, 0)))
    r = max_r * (1 - clamp01(p)) ** 1.5
    if r >= 0.3:
        big = big.copy()
        big[..., 3] = gblur(big[..., 3], r)
    return big


def scale_img(src, s):
    if abs(s - 1) < 0.002:
        return src
    h, w = src.shape[:2]
    im = Image.fromarray((np.clip(src, 0, 1) * 255).astype(np.uint8), "RGBA")
    return np.asarray(im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.BICUBIC), np.float32) / 255


# ---------------------------------------------------------------- 金箔
FOIL = None


def make_foil(w=2600, h=1600, seed=4):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    n = soft_noise(w, h, (9, 6), seed) * 0.45 + soft_noise(w, h, (40, 25), seed + 1) * 0.08
    u = ((xx * 0.82 + yy * 0.57) / 560 + n) % 1.0
    pos = [s[0] for s in GOLD_STOPS]
    cols = np.array([hexc(s[1]) for s in GOLD_STOPS])
    rgb = np.stack([np.interp(u, pos, cols[:, c]) for c in range(3)], axis=2).astype(np.float32)
    rng = np.random.default_rng(seed)
    rgb *= (1 + rng.standard_normal((h, w, 1)).astype(np.float32) * 0.03)
    spark = (rng.random((h, w)) ** 40).astype(np.float32)
    rgb += spark[..., None] * np.array([0.6, 0.55, 0.4], np.float32)
    return np.clip(rgb, 0, 1.2)


_foil_ofs = [0]


def gold(mask, glow=True, bevel=1.0, glow_r=None, glow_k=0.45):
    """文字・図形のマスクを、立体感のある金箔＋やわらかな光に変換"""
    size = max(mask.shape)
    p = int(min(60, max(18, size * 0.05))) if glow else 2
    m = np.pad(mask, p)
    h, w = m.shape
    _foil_ofs[0] = (_foil_ofs[0] + 337) % 900
    oy, ox = (_foil_ofs[0] * 7) % (FOIL.shape[0] - h) if FOIL.shape[0] > h else 0, _foil_ofs[0] % max(1, FOIL.shape[1] - w)
    rgb = FOIL[oy:oy + h, ox:ox + w].copy()
    # エンボス（左上からの光）
    r = max(1.0, min(h, w) * 0.012)
    mb = gblur_f(m, r)
    gy, gx = np.gradient(mb)
    shade = (-gx * 0.7 - gy * 0.7) * (8.0 / max(1e-3, mb.max())) * bevel
    rgb *= (1 + np.clip(shade, -0.45, 0.6))[..., None]
    out = np.empty((h, w, 4), np.float32)
    out[..., :3] = np.clip(rgb, 0, 1)
    out[..., 3] = m
    if glow:
        gr = glow_r or max(6, size * 0.012)
        g = gblur_f(m, gr) * glow_k
        a_t = m
        a_g = g * (1 - a_t)
        a = a_t + a_g
        out[..., :3] = (out[..., :3] * a_t[..., None] + GOLD * a_g[..., None]) / np.maximum(a, 1e-4)[..., None]
        out[..., 3] = a
    return out


def sheen(src, p, width=0.12, k=0.9):
    """金箔の上を光がすっと流れる"""
    if p <= 0 or p >= 1:
        return src
    h, w = src.shape[:2]
    out = src.copy()
    xs = np.arange(w, dtype=np.float32)[None, :] / max(w, h)
    ys = np.arange(h, dtype=np.float32)[:, None] / max(w, h)
    pos = -0.3 + p * (w / max(w, h) + 0.6)
    band = np.exp(-(((xs + ys * 0.45) - pos) / width) ** 2)
    out[..., :3] += band[..., None] * np.array([1.0, 0.96, 0.85], np.float32) * k * np.clip(out[..., 3:4] * 1.4, 0, 1)
    out[..., :3] = np.clip(out[..., :3], 0, 1)
    return out


# ---------------------------------------------------------------- 光の素材
def glow_sprite(r, color, core=1.0):
    S = int(r * 6) | 1
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - S // 2
    d = np.hypot(xx, yy)
    a = np.exp(-(d / r) ** 2) * core + np.exp(-(d / (r * 2.5)) ** 2) * 0.25
    return a[..., None] * color


def star_sprite(r, color):
    """きらめき（十字の光）"""
    S = int(r * 10) | 1
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - S // 2
    d = np.hypot(xx, yy) + 1e-3
    core = np.exp(-(d / (r * 0.6)) ** 2)
    arms = (np.exp(-(yy / (r * 0.12)) ** 2) + np.exp(-(xx / (r * 0.12)) ** 2)) * np.exp(-d / (r * 2.2))
    halo = np.exp(-(d / (r * 1.8)) ** 2) * 0.25
    return np.clip(core + arms * 0.8 + halo, 0, 1.5)[..., None] * color


def flare_sprite(length=1500, height=70):
    """アナモルフィックレンズフレア（横に伸びる光）"""
    xx = np.linspace(-1, 1, length, dtype=np.float32)[None, :]
    yy = np.linspace(-1, 1, height, dtype=np.float32)[:, None]
    streak = np.exp(-(yy / 0.10) ** 2) * (1 - np.abs(xx)) ** 2.5
    soft = np.exp(-(yy / 0.5) ** 2) * (1 - np.abs(xx)) ** 4 * 0.3
    a = streak + soft
    col = np.array([0.75, 0.85, 1.0], np.float32) * 0.6 + WARM * 0.4
    return a[..., None] * col


def disk_field(w, h, n, rmin, rmax, cols, kmin, kmax, seed, blur=0, edge=1.5):
    """光のボケ（加算）を敷き詰めた RGB 配列"""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w, 3), np.float32)
    for _ in range(n):
        r = rng.uniform(rmin, rmax)
        cx, cy = rng.uniform(-r, w + r), rng.uniform(-r, h + r)
        k = rng.uniform(kmin, kmax)
        col = cols[int(rng.integers(len(cols)))] * rng.uniform(0.85, 1.1)
        x0, x1 = int(max(cx - r - 3, 0)), int(min(cx + r + 4, w))
        y0, y1 = int(max(cy - r - 3, 0)), int(min(cy + r + 4, h))
        if x1 <= x0 or y1 <= y0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        d = np.hypot(xx - cx, yy - cy)
        disk = np.clip((r - d) / edge + 0.5, 0, 1)
        rim = np.exp(-((d - r * 0.9) / (r * 0.09 + 0.5)) ** 2) * 0.45 * (d < r + 1)
        out[y0:y1, x0:x1] += ((0.75 + rim) * disk)[..., None] * col * k
    if blur:
        for c in range(3):
            out[..., c] = gblur_f(out[..., c], blur)
    return out


def make_background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.hypot((xx - W * 0.5) / W, (yy - H * 0.42) / H * 0.9)
    k = np.clip(d / 0.75, 0, 1) ** 1.2
    bg = NAVY_C[None, None, :] * (1 - k[..., None]) + NAVY_E[None, None, :] * k[..., None]
    velvet = soft_noise(W, H, (14, 9), 2) * 0.6 + soft_noise(W, H, (60, 34), 3) * 0.4
    bg *= (0.86 + 0.28 * velvet)[..., None]
    return bg.astype(np.float32)


def make_rays(seed):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ox, oy = -250, -420
    ang = np.arctan2(yy - oy, xx - ox)
    dist = np.hypot(xx - ox, yy - oy)
    rng = np.random.default_rng(seed)
    a = np.zeros((H, W), np.float32)
    for _ in range(9):
        c = rng.uniform(0.35, 1.15)
        wdt = rng.uniform(0.01, 0.045)
        a += np.exp(-((ang - c) / wdt) ** 2) * rng.uniform(0.4, 1.0)
    a *= np.exp(-dist / 1500) * np.clip((dist - 300) / 500, 0, 1)
    a = gblur_f(a, 6)
    return (a[..., None] * WARM * 0.11).astype(np.float32)


# ---------------------------------------------------------------- 紋章（月桂樹リース＋イニシャル）
def leaf_poly(bx, by, dx, dy, L, Wd):
    nx, ny = -dy, dx
    left, right = [], []
    for i in range(16):
        s = i / 15
        w = Wd * math.sin(math.pi * s) ** 0.75 * (1 - 0.25 * s)
        px, py = bx + dx * L * s, by + dy * L * s
        left.append((px + nx * w / 2, py + ny * w / 2))
        right.append((px - nx * w / 2, py - ny * w / 2))
    return left + right[::-1]


def make_wreath(D=620, ss=3):
    S = D * ss
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    cx = cy = S / 2
    R = S * 0.41
    span = math.radians(140)
    for side in (-1, 1):
        pts = [(cx + side * R * math.sin(th), cy + R * math.cos(th)) for th in np.linspace(0.06, span, 80)]
        d.line(pts, fill=255, width=int(2.2 * ss))
        nn = 13
        for k in range(nn):
            th = 0.16 + (span - 0.2) * k / (nn - 1)
            x, y = cx + side * R * math.sin(th), cy + R * math.cos(th)
            tx, ty = side * math.cos(th), -math.sin(th)          # 成長方向（上へ）
            ox_, oy_ = side * math.sin(th), math.cos(th)          # 外向き
            sc = 1 - 0.38 * (th / span)
            L, Wd = 74 * ss * sc, 25 * ss * sc
            for out_dir in (1, -1):
                a = 0.62
                dx = tx * math.cos(a) + ox_ * out_dir * math.sin(a)
                dy = ty * math.cos(a) + oy_ * out_dir * math.sin(a)
                nrm = math.hypot(dx, dy)
                dx, dy = dx / nrm, dy / nrm
                d.polygon(leaf_poly(x, y, dx, dy, L, Wd), fill=255)
                d.line([(x + dx * L * 0.08, y + dy * L * 0.08), (x + dx * L * 0.8, y + dy * L * 0.8)], fill=0, width=max(1, int(1.6 * ss)))
            if k % 3 == 1:
                bx, by = x + ox_ * 16 * ss, y + oy_ * 16 * ss + 0
                r = 6 * ss * sc
                d.ellipse([bx - r, by - r, bx + r, by + r], fill=255)
        # 先端の葉
        th = span + 0.06
        x, y = cx + side * R * math.sin(th), cy + R * math.cos(th)
        d.polygon(leaf_poly(x, y, side * math.cos(th), -math.sin(th), 56 * ss, 18 * ss), fill=255)
    # 下のリボン（交差する茎）
    for side in (-1, 1):
        d.line([(cx, cy + R + 4 * ss), (cx + side * 46 * ss, cy + R + 40 * ss)], fill=255, width=int(2.2 * ss))
    d.ellipse([cx - 7 * ss, cy + R - 3 * ss, cx + 7 * ss, cy + R + 11 * ss], fill=255)
    a = np.asarray(m.resize((D, D), Image.LANCZOS), np.float32) / 255
    yy, xx = np.mgrid[0:D, 0:D].astype(np.float32) - D / 2
    th = np.arctan2(np.abs(xx), yy)  # 下=0, 上=π
    return a, th / math.pi


def make_monogram(initials, size=170):
    a = mask_text(initials[0], "cinzel", size)
    amp = mask_text("&", "script", int(size * 0.95))
    b = mask_text(initials[1], "cinzel", size)
    h = max(a.shape[0], b.shape[0])
    gap = int(size * 0.10)
    w = a.shape[1] + amp.shape[1] + b.shape[1] + gap * 2
    out = np.zeros((h + 20, w), np.float32)
    out[(h + 20 - a.shape[0]) // 2:(h + 20 - a.shape[0]) // 2 + a.shape[0], :a.shape[1]] = a
    x = a.shape[1] + gap
    y = int((h + 20) * 0.55 - amp.shape[0] / 2)
    out[y:y + amp.shape[0], x:x + amp.shape[1]] = np.maximum(out[y:y + amp.shape[0], x:x + amp.shape[1]], amp)
    x += amp.shape[1] + gap
    out[(h + 20 - b.shape[0]) // 2:(h + 20 - b.shape[0]) // 2 + b.shape[0], x:x + b.shape[1]] = b
    return out


def ornament_line(w=640):
    """中央にひし形のある細い飾り罫"""
    ss = 3
    m = Image.new("L", (w * ss, 30 * ss), 0)
    d = ImageDraw.Draw(m)
    c, cy = w * ss / 2, 15 * ss
    d.line([(0, cy), (c - 26 * ss, cy)], fill=255, width=int(1.3 * ss))
    d.line([(c + 26 * ss, cy), (w * ss, cy)], fill=255, width=int(1.3 * ss))
    r = 9 * ss
    d.polygon([(c, cy - r), (c + r, cy), (c, cy + r), (c - r, cy)], outline=255, width=int(1.3 * ss))
    r2 = 3.5 * ss
    d.polygon([(c, cy - r2), (c + r2, cy), (c, cy + r2), (c - r2, cy)], fill=255)
    for s in (-1, 1):
        x = c + s * 18 * ss
        d.ellipse([x - 2 * ss, cy - 2 * ss, x + 2 * ss, cy + 2 * ss], fill=255)
    a = np.asarray(m.resize((w, 30), Image.LANCZOS), np.float32) / 255
    fade = np.clip((1 - np.abs(np.linspace(-1, 1, w))) * 5, 0, 1)
    return a * fade[None, :]


def deco_frame(w, h, off=18, corner=46):
    """写真のまわりの細い金の二重枠＋アールデコ風の角飾り"""
    ss = 3
    W2, H2 = (w + off * 2 + 20) * ss, (h + off * 2 + 20) * ss
    m = Image.new("L", (W2, H2), 0)
    d = ImageDraw.Draw(m)
    o = 10 * ss
    d.rectangle([o, o, W2 - o, H2 - o], outline=255, width=int(1.2 * ss))
    o2 = o + 7 * ss
    d.rectangle([o2, o2, W2 - o2, H2 - o2], outline=150, width=int(0.8 * ss))
    c = corner * ss
    for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        x = o if sx == 0 else W2 - o
        y = o if sy == 0 else H2 - o
        dx = 1 if sx == 0 else -1
        dy = 1 if sy == 0 else -1
        r = 7 * ss
        d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=255)
        d.line([(x + dx * 14 * ss, y + dy * 14 * ss), (x + dx * c, y + dy * 14 * ss)], fill=255, width=int(1.2 * ss))
        d.line([(x + dx * 14 * ss, y + dy * 14 * ss), (x + dx * 14 * ss, y + dy * c)], fill=255, width=int(1.2 * ss))
    a = np.asarray(m.resize((W2 // ss, H2 // ss), Image.LANCZOS), np.float32) / 255
    return a


# ---------------------------------------------------------------- サンプル写真（実写の代わりの自動生成イメージ）
def vgrad(w, h, stops):
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, w, 3), np.float32)
    for c in range(3):
        out[..., c] = np.interp(ys, [s[0] for s in stops], [hexc(s[1])[c] for s in stops])[:, None]
    return out


def grade(a, seed):
    """映画のような色調（暗部はわずかに青、明部は暖色）＋粒子"""
    lum = a.mean(axis=2, keepdims=True)
    a = a + (1 - lum) * np.array([-0.01, 0.0, 0.025], np.float32) * 0.8 + lum * np.array([0.03, 0.01, -0.03], np.float32)
    a = np.clip(a, 0, None)
    a = a / (1 + a * 0.35) * 1.3          # ハイライトをなめらかに
    a = 0.03 + a * 0.95
    a += np.random.default_rng(seed).standard_normal(a.shape[:2] + (1,)).astype(np.float32) * 0.01
    return np.clip(a, 0, 1)


def branch_mask(w, h, seed, n=5, width=(8, 20)):
    rng = np.random.default_rng(seed)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for _ in range(n):
        p0 = (rng.uniform(-300, -50), rng.uniform(0, h * 0.5))
        p2 = (rng.uniform(w * 0.5, w * 1.1), rng.uniform(-150, h * 0.25))
        p1 = ((p0[0] + p2[0]) / 2, min(p0[1], p2[1]) + rng.uniform(120, 320))
        pts = []
        for t in np.linspace(0, 1, 40):
            pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                        (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
        wd = rng.uniform(*width)
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=255, width=int(wd * (1 - 0.7 * i / len(pts))) + 1)
    return np.asarray(m, np.float32) / 255


def sample_photo(kind, w=2200, h=1000, seed=0):
    if kind == "sakura":
        a = vgrad(w, h, [(0, "#3E4C72"), (0.55, "#B58AA0"), (1, "#E7B6A8")])
        a += disk_field(w, h, 50, 60, 150, [hexc("#F4C6CF"), hexc("#FFE4E8")], 0.05, 0.12, seed + 1, 10)
        br = gblur(branch_mask(w, h, seed + 2, 4, (16, 34)), 6)
        a = a * (1 - br[..., None] * 0.8) + br[..., None] * hexc("#2A2030") * 0.8
        a += disk_field(w, h, 140, 12, 36, [hexc("#FFD3DC"), hexc("#F7B8C6"), hexc("#FFF0F2")], 0.2, 0.5, seed + 3, 2.0)
    elif kind == "sea":
        a = vgrad(w, h, [(0, "#2E3557"), (0.32, "#B0748A"), (0.5, "#F2B27E"), (0.56, "#FFDDA8"), (0.57, "#8B6A78"), (1, "#1E2544")])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        sx, sy = w * 0.58, h * 0.53
        dist = np.hypot(xx - sx, (yy - sy) * 1.1)
        a += (np.exp(-(dist / (h * 0.32)) ** 2) * 0.55)[..., None] * WARM
        a += (np.clip(1 - dist / (h * 0.05), 0, 1) ** 0.5 * 0.7)[..., None]
        rng = np.random.default_rng(seed)
        rows = (rng.random((h, 1)) ** 3) * (yy > h * 0.57)
        streak = rows * np.exp(-((xx - sx) / (w * (0.05 + 0.25 * np.clip(yy - h * 0.57, 0, None) / h))) ** 2)
        a += gblur_f(streak.astype(np.float32), 1.5)[..., None] * WARM * 0.9
        a += disk_field(w, h, 40, 20, 60, [WARM, hexc("#FFC6A8")], 0.05, 0.15, seed + 4, 2)
    elif kind == "city":
        a = vgrad(w, h, [(0, "#0B0F22"), (0.6, "#1D1A33"), (1, "#2B1E2E")])
        cols = [hexc("#FFC77A"), hexc("#FFB08A"), hexc("#FFE6B5"), hexc("#9FB6FF"), hexc("#FF9FA8")]
        a += disk_field(w, h, 90, 50, 120, cols, 0.08, 0.25, seed + 5, 6)
        a += disk_field(w, h, 220, 12, 40, cols, 0.25, 0.7, seed + 6, 1.2)
    else:  # candle
        a = vgrad(w, h, [(0, "#100B0A"), (0.6, "#24160F"), (1, "#3A2416")])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        a += (np.exp(-(((xx - w * 0.5) / (w * 0.4)) ** 2 + ((yy - h * 0.85) / (h * 0.5)) ** 2)) * 0.25)[..., None] * WARM
        cols = [hexc("#FFC46E"), hexc("#FFDDA0"), hexc("#FFAE5C")]
        a += disk_field(w, h, 70, 40, 110, cols, 0.1, 0.35, seed + 7, 5)
        a += disk_field(w, h, 140, 8, 26, cols, 0.3, 0.8, seed + 8, 1)
    return Image.fromarray((grade(a, seed) * 255).astype(np.uint8))


def profile_placeholder(initial, tint, w=1200, h=1600, seed=0):
    a = vgrad(w, h, [(0, "#1B2238"), (1, "#0C1020")]) * 0.9 + tint * 0.08
    a += disk_field(w, h, 60, 40, 130, [WARM, hexc("#FFE9C4"), tint * 1.4], 0.06, 0.18, seed, 8)
    a = grade(a, seed)
    img = Image.fromarray((a * 255).astype(np.uint8)).convert("RGBA")
    m = mask_text(initial, "script", 640)
    g = gold(m, glow=True, glow_k=0.6)
    gi = Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8), "RGBA")
    img.alpha_composite(gi, ((w - gi.width) // 2, int(h * 0.42 - gi.height / 2)))
    lab = colorize(mask_text("YOUR PHOTO", "cinzel", 38, tracking=0.5), CHAMP)
    li = Image.fromarray((lab * 255).astype(np.uint8), "RGBA")
    img.alpha_composite(li, ((w - li.width) // 2, int(h * 0.8)))
    return img.convert("RGB")


def load_photo(path, fallback):
    if path:
        p = path if os.path.isabs(path) else os.path.join(HERE, path)
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
        print("写真が見つかりません:", p, "→ サンプル画像を使用します")
    return fallback()


def cover(img, w, h):
    r = w / h
    iw, ih = img.size
    if iw / ih > r:
        nw = int(ih * r)
        img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw / r)
        img = img.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    return img.resize((w, h), Image.LANCZOS)


def kenburns(img, w, h, z, dx=0.0, dy=0.0):
    iw, ih = img.size
    cw, ch = iw / z, ih / z
    cx = iw / 2 + dx * (iw - cw) / 2
    cy = ih / 2 + dy * (ih - ch) / 2
    return np.asarray(img.resize((w, h), Image.BICUBIC, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)), np.float32) / 255


def shadow(w, h, blur=30, k=0.6, pad=70):
    m = np.zeros((h + pad * 2, w + pad * 2), np.float32)
    m[pad:pad + h, pad:pad + w] = 1
    return colorize(gblur(m, blur) * k, np.zeros(3, np.float32))


# ---------------------------------------------------------------- 素材の準備
A = {}


def build(cfg):
    global FOIL
    print("素材を準備中…（30秒ほどかかります）")
    FOIL = make_foil()
    A["cfg"] = cfg
    A["bg"] = make_background()
    A["rays"] = [make_rays(11), make_rays(23)]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    A["vig"] = (1 - 0.55 * np.clip(v - 0.45, 0, 1) ** 1.6)[..., None].astype(np.float32)
    rng = np.random.default_rng(9)
    A["grain"] = [rng.standard_normal((H, W, 1)).astype(np.float32) for _ in range(6)]
    amber = [hexc("#E8B86A"), hexc("#F3D49A"), hexc("#C98F4A")]
    A["bok_far"] = disk_field(W + 500, H + 300, 45, 50, 120, amber, 0.03, 0.07, 31, 10)
    A["bok_mid"] = disk_field(W + 900, H + 300, 70, 10, 30, amber, 0.05, 0.12, 32, 2.5)
    N = 60
    A["pt"] = dict(x=rng.uniform(0, W, N), y=rng.uniform(0, H, N), vy=rng.uniform(6, 22, N), ph=rng.uniform(0, 6.28, N),
                   sp=rng.uniform(0.5, 1.5, N), big=rng.random(N) < 0.18)
    A["dot"] = glow_sprite(2.2, GOLD_L)
    A["star"] = star_sprite(4.0, GOLD_L)
    A["star_big"] = star_sprite(9.0, hexc("#FFF4DA"))
    A["flare"] = flare_sprite(1700, 80)
    A["flare_core"] = glow_sprite(60, WARM * 0.8)
    NB = 140
    A["burst"] = dict(ang=rng.uniform(0, 6.28, NB), sp=rng.uniform(200, 1100, NB), ph=rng.uniform(0, 6.28, NB),
                      star=rng.random(NB) < 0.25)

    # 紋章
    wr, th = make_wreath(620)
    A["wreath"] = gold(wr, glow=True, glow_k=0.35)
    pad = (A["wreath"].shape[0] - wr.shape[0]) // 2
    A["wreath_th"] = np.pad(th, pad, mode="edge")
    A["mono"] = gold(make_monogram(cfg["initials"], 150))
    A["wreath_s"] = scale_img(A["wreath"], 0.42)
    A["mono_s"] = scale_img(A["mono"], 0.42)
    A["the_wedding"] = colorize(mask_text("THE WEDDING OF", "cinzel", 26, tracking=0.6), CHAMP)
    A["caps"] = gold(mask_text(cfg["couple_caps"], "cinzel", 46, tracking=0.32), glow_k=0.3)
    A["date"] = colorize(mask_text(cfg["date"], "cinzel", 30, tracking=0.4), CHAMP)
    A["orn"] = gold(ornament_line(560), glow=True, glow_k=0.3, bevel=0.3)
    A["orn_s"] = gold(ornament_line(380), glow=True, glow_k=0.3, bevel=0.3)

    # メッセージ
    A["msg1"] = [colorize(mask_vtext(s, 46), IVORY) for s in cfg["message1"]]
    A["msg2"] = [colorize(mask_vtext(s, 46), IVORY) for s in cfg["message2"]]
    A["msg_en"] = gold(mask_text("Message", "script", 120))
    A["vrule"] = colorize(np.clip(1 - np.abs(np.linspace(-1, 1, 560)) ** 4, 0, 1)[:, None] * np.ones((1, 2), np.float32) * 0.7, GOLD)
    A["msg3"] = [colorize(mask_text(s, "mincho", 48, tracking=0.14), IVORY) for s in cfg["message3"]]
    A["thank"] = gold(mask_text("Thank you", "script", 170))
    A["coming_en"] = gold(mask_text("The Grand Entrance", "script", 140))
    A["coming"] = [colorize(mask_text(cfg["coming"][0], "mincho", 56, tracking=0.16), IVORY),
                   colorize(mask_text(cfg["coming"][1], "mincho", 32, tracking=0.2), CHAMP)]

    # プロフィール
    PW, PH = 600, 800
    A["pshadow"] = shadow(PW, PH)
    A["pframe"] = gold(deco_frame(PW, PH), glow=False, bevel=0.2)
    for who, tint, sd in (("groom", hexc("#6F86B8"), 1), ("bride", hexc("#C98C9C"), 2)):
        p = cfg[who]
        ph = load_photo(p.get("photo"), lambda p=p, tint=tint, sd=sd: profile_placeholder(p["name_en"][0], tint, seed=sd))
        A[who + "_photo"] = cover(ph, int(PW * 1.6), int(PH * 1.6))
        A[who + "_label"] = colorize(mask_text(p["label"], "cinzel", 28, tracking=0.6), GOLD)
        A[who + "_name"] = colorize(mask_text(p["name_ja"], "mincho", 86, tracking=0.14), IVORY)
        A[who + "_en"] = gold(mask_text(p["name_en"], "script", 82), glow_k=0.3)
        A[who + "_items"] = [(colorize(mask_text(k, "mincho_regular", 22, tracking=0.3), GOLD),
                              colorize(mask_text(v, "mincho", 34, tracking=0.08), IVORY)) for k, v in p["profile"]]
    A["thin"] = colorize(np.clip((1 - np.abs(np.linspace(-1, 1, 560))) * 4, 0, 1)[None, :] * np.ones((1, 1), np.float32) * 0.6, GOLD)

    # ストーリー（シネマスコープ）
    A["story"] = []
    for i, s in enumerate(cfg["story"]):
        ph = load_photo(s.get("photo"), lambda s=s, i=i: sample_photo(s.get("sample", "city"), seed=i * 10 + 1))
        A["story"].append(dict(photo=cover(ph, 2240, 1000),
                               en=gold(mask_text(s["en"], "script", 110), glow_k=0.4),
                               date=colorize(mask_text(s["date"], "cinzel", 30, tracking=0.4), GOLD_L),
                               title=colorize(mask_text(s["title"], "mincho", 42, tracking=0.18), IVORY)))
    A["our_story"] = colorize(mask_text("OUR STORY", "cinzel", 26, tracking=0.8), CHAMP)
    gy = np.linspace(0, 1, 520, dtype=np.float32)[:, None]
    gx = np.clip(1.25 - np.linspace(0, 1, W, dtype=np.float32)[None, :] * 1.1, 0.35, 1)
    A["story_shade"] = colorize(np.clip(gy ** 1.3 * 0.88 * gx, 0, 0.9), NAVY_E)

    # カウントダウン
    S = 760
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - S / 2
    A["cd_r"] = np.hypot(xx, yy)
    A["cd_ang"] = (np.arctan2(xx, -yy) / (2 * np.pi)) % 1.0
    ss = 3
    m = Image.new("L", (S * ss, S * ss), 0)
    d = ImageDraw.Draw(m)
    c = S * ss / 2
    for R, wd, val in ((270, 1.2, 160), (300, 1.0, 110)):
        d.ellipse([c - R * ss, c - R * ss, c + R * ss, c + R * ss], outline=val, width=int(wd * ss))
    for k in range(60):
        a = 2 * math.pi * k / 60
        r0, r1 = (306, 326) if k % 5 == 0 else (306, 314)
        d.line([(c + r0 * ss * math.sin(a), c - r0 * ss * math.cos(a)), (c + r1 * ss * math.sin(a), c - r1 * ss * math.cos(a))],
               fill=220 if k % 5 == 0 else 130, width=int((1.6 if k % 5 == 0 else 1.0) * ss))
    A["cd_ring"] = gold(np.asarray(m.resize((S, S), Image.LANCZOS), np.float32) / 255, glow=False, bevel=0.2)
    A["cd_num"] = {n: gold(mask_text(str(n), "cinzel", 330), glow_k=0.35) for n in range(1, 6)}
    A["cd_foil"] = FOIL[200:200 + S, 300:300 + S].copy()

    # エンディング
    A["fin_event"] = colorize(mask_text(cfg["event_en"], "cinzel", 30, tracking=0.6), CHAMP)
    A["fin_names"] = gold(mask_text(cfg["couple_en"], "script", 210), glow_k=0.4)
    A["fin_date"] = gold(mask_text(cfg["date"], "cinzel", 44, tracking=0.35), glow_k=0.3)
    A["fin_close"] = colorize(mask_text(cfg["closing"], "mincho", 34, tracking=0.2), IVORY)

    wm = cfg.get("watermark")
    A["wm"] = colorize(mask_text(wm, "cinzel", 24, tracking=0.6), CHAMP) if wm else None


# ---------------------------------------------------------------- 共通レイヤー
def draw_atmos(fr, t, k=1.0):
    w0, w1 = 0.5 + 0.5 * math.sin(t * 0.21), 0.5 - 0.5 * math.sin(t * 0.21)
    fr += A["rays"][0] * (w0 * k) + A["rays"][1] * (w1 * k)
    bf, bm = A["bok_far"], A["bok_mid"]
    ox = int(150 + 140 * math.sin(t * 0.03))
    oy = int(120 + 100 * math.cos(t * 0.025))
    add(fr, bf[oy:oy + H, ox:ox + W], 0, 0, k)
    ox2 = int((t * 14) % 800)
    oy2 = int(150 + 130 * math.sin(t * 0.05))
    add(fr, bm[oy2:oy2 + H, ox2:ox2 + W], 0, 0, k)


def draw_particles(fr, t, k=1.0):
    p = A["pt"]
    for i in range(len(p["x"])):
        y = (p["y"][i] - p["vy"][i] * t) % (H + 60) - 30
        x = p["x"][i] + 22 * math.sin(t * 0.35 * p["sp"][i] + p["ph"][i])
        tw = 0.5 + 0.5 * math.sin(t * 2.0 * p["sp"][i] + p["ph"][i])
        if p["big"][i]:
            add_c(fr, A["star"], x, y, (tw ** 3) * 0.9 * k)
        else:
            add_c(fr, A["dot"], x, y, (0.25 + 0.6 * tw) * 0.6 * k)


def flare(fr, x, y, k):
    if k > 0.003:
        add_c(fr, A["flare"], x, y, k)
        add_c(fr, A["flare_core"], x, y, k * 0.8)


def gold_draw(fr, g, cx, cy, a=1.0, sh=None, wp=None, axis="x"):
    img = g
    if wp is not None:
        img = wipe(img, wp, axis, 0.2)
    if sh is not None:
        img = sheen(img, sh)
    blit_c(fr, img, cx, cy, a)


# ---------------------------------------------------------------- シーン
def sc_prologue(fr, t):
    a = env(t, 0, 3 * BAR, 0.01, 0.8)
    if a <= 0:
        return
    cx, cy = W / 2, 430
    # リースが下から伸びていく
    p = ease_io((t - 1.0) / 3.2)
    if p > 0:
        wr = A["wreath"]
        if p < 1:
            m = np.clip((p * 1.08 - A["wreath_th"]) / 0.08, 0, 1)
            wr = wr.copy()
            wr[..., 3] *= m
        blit_c(fr, sheen(wr, (t - 5.2) / 1.6), cx, cy, a)
    q = ramp(t, 2.6, 4.2)
    if q > 0:
        mono = blur_in(A["mono"], q, 12)
        blit_c(fr, sheen(mono, (t - 4.6) / 1.4), cx, cy + 6, a * q)
    blit_c(fr, A["the_wedding"], W / 2, 795, a * ramp(t, 4.4, 5.6))
    gold_draw(fr, A["caps"], W / 2, 860, a * ramp(t, 4.8, 6.0), sh=(t - 6.2) / 1.4)
    blit_c(fr, A["date"], W / 2, 925, a * ramp(t, 5.4, 6.6))
    # 光が横切る
    fx = -300 + (W + 600) * ease_io((t - 0.3) / 2.6)
    flare(fr, fx, cy, 0.55 * (1 - ramp(t, 2.0, 2.9)) * ramp(t, 0.3, 0.8))


def sc_vertical(fr, t, cols, t0, t1, head):
    a = env(t, t0, t1, 0.5, 0.8)
    if a <= 0:
        return
    lt = t - t0
    gap = 92
    n = len(cols)
    xr = W / 2 + gap * (n - 1) / 2
    top = H / 2 - 230
    for i, c in enumerate(cols):
        p = (lt - 0.5 - i * 0.7) / 1.5
        if p > 0:
            blit(fr, wipe(c, ease(p), "y", 0.3), xr - i * gap - c.shape[1] / 2, top, a)
    # 左右の縦罫
    vr = A["vrule"]
    q = ease((lt - 0.2) / 1.6)
    for s in (-1, 1):
        blit_c(fr, wipe(vr, q, "y", 0.4), W / 2 + s * (gap * n / 2 + 90), H / 2 + 40, a * 0.9)
    if head:
        gold_draw(fr, A["msg_en"], W / 2, top - 110, a * ramp(lt, 0.1, 1.0), sh=(lt - 1.0) / 1.6)


def sc_profile(fr, t, who, t0, t1, left):
    a = env(t, t0, t1, 0.8, 0.8)
    if a <= 0:
        return
    lt = t - t0
    PW, PH = 600, 800
    px = 590 if left else W - 590
    py = H / 2 + 4
    k = ease_out(lt / 1.6)
    sl = (1 - k) * (-50 if left else 50)
    blit_c(fr, A["pshadow"], px + sl, py + 22, a * k)
    img = kenburns(A[who + "_photo"], PW, PH, 1.0 + 0.08 * lt / (t1 - t0), 0, -0.2)
    blit_c(fr, np.concatenate([img, np.ones((PH, PW, 1), np.float32)], axis=2), px + sl, py, a * k)
    fq = ease((lt - 0.8) / 1.4)
    blit_c(fr, wipe_center(A["pframe"], fq), px + sl, py, a)
    # テキスト
    tx = 1010 if left else 330
    items = A[who + "_items"]
    blocks = [A[who + "_label"], A[who + "_name"], A[who + "_en"]]
    total = sum(b.shape[0] for b in blocks) + 30 + 40 + 60 + sum(kk.shape[0] + vv.shape[0] + 40 for kk, vv in items)
    y = H / 2 - total / 2
    q = ramp(lt, 0.6, 1.4)
    blit(fr, A[who + "_label"], tx + (1 - q) * 20, y, a * q)
    y += blocks[0].shape[0] + 30
    q = ramp(lt, 1.0, 2.0)
    nm = blur_in(A[who + "_name"], q, 10)
    blit(fr, nm, tx - 20, y - 20, a * q)
    y += blocks[1].shape[0] + 34
    en = A[who + "_en"]
    pe = (en.shape[0] - blocks[2].shape[0]) // 2
    blit(fr, sheen(wipe(en, ease((lt - 1.6) / 1.4), "x", 0.2), (lt - 3.4) / 1.6), tx - 30, y - 30, a)
    y += blocks[2].shape[0] + 30
    blit(fr, wipe(A["thin"], ease((lt - 2.2) / 1.0), "x", 0.4), tx, y, a)
    y += 40
    for i, (kk, vv) in enumerate(items):
        q = ramp(lt, 2.6 + i * 0.4, 3.5 + i * 0.4)
        yy = y + (1 - q) * 16
        blit(fr, kk, tx, yy, a * q)
        blit(fr, vv, tx, yy + kk.shape[0] + 10, a * q)
        y += kk.shape[0] + vv.shape[0] + 40


def letterbox(t, t0, t1):
    return min(ease((t - t0) / 0.9), 1 - ease((t - (t1 - 0.9)) / 0.9))


def sc_story(fr, t):
    t0, t1 = 13 * BAR, 17 * BAR
    if t < t0 - 0.1 or t > t1 + 0.1:
        return
    n = len(A["story"])
    seg = (t1 - t0) / n
    lb = letterbox(t, t0, t1)
    bar = int(138 * lb)
    for i, s in enumerate(A["story"]):
        s0, s1 = t0 + i * seg, t0 + (i + 1) * seg
        fi = 0.8 if i == 0 else 0.35
        fo = 0.8 if i == n - 1 else 0.35
        a = env(t, s0 - (0 if i == 0 else 0.35), s1 + (0 if i == n - 1 else 0.35), fi, fo)
        if a <= 0:
            continue
        lt = t - s0
        u = (t - s0 + 0.35) / (seg + 0.7)
        img = kenburns(s["photo"], W, H, 1.04 + 0.08 * u, (-0.5 + u) * (1 if i % 2 == 0 else -1), 0.1)
        rgba = np.concatenate([img, np.ones((H, W, 1), np.float32)], axis=2)
        blit(fr, rgba, 0, 0, a)
        blit(fr, A["story_shade"], 0, H - 520, a)
        # キャプション（左下）
        cx = 170
        by = H - 138 - 115
        q = ramp(lt, 0.3, 1.0)
        en = s["en"]
        blit(fr, sheen(wipe(en, ease((lt - 0.2) / 1.2), "x", 0.2), (lt - 1.4) / 1.4), cx - 40, by - en.shape[0] - 10 + 40, a)
        blit(fr, s["date"], cx, by + 46 + (1 - q) * 10, a * q)
        blit(fr, s["title"], cx + s["date"].shape[1] + 34, by + 40 + (1 - q) * 10, a * q)
    # 写真が切り替わる瞬間の光
    for i in range(1, n):
        tc = t0 + i * seg
        k = math.exp(-((t - tc) / 0.25) ** 2)
        flare(fr, W * 0.5 + (t - tc) * 900, H * 0.45, 0.5 * k)
    if bar > 0:
        fr[:bar] *= 0.0
        fr[H - bar:] *= 0.0
        fr[:bar] += NAVY_E * 0.5
        fr[H - bar:] += NAVY_E * 0.5
        blit_c(fr, A["our_story"], W / 2, bar / 2, lb * 0.9)


def sc_thanks(fr, t, t0, t1):
    a = env(t, t0, t1, 0.5, 0.8)
    if a <= 0:
        return
    lt = t - t0
    gold_draw(fr, A["thank"], W / 2, H / 2 - 190, a, sh=(lt - 1.8) / 1.5, wp=ease((lt - 0.2) / 1.8))
    for i, im in enumerate(A["msg3"]):
        q = ramp(lt, 1.0 + i * 0.6, 2.0 + i * 0.6)
        blit_c(fr, blur_in(im, q, 10), W / 2, H / 2 + i * 92, a * q)


def sc_coming(fr, t, t0, t1):
    a = env(t, t0, t1, 0.5, 0.6)
    if a <= 0:
        return
    lt = t - t0
    gold_draw(fr, A["coming_en"], W / 2, H / 2 - 150, a, sh=(lt - 2.0) / 1.5, wp=ease((lt - 0.2) / 2.0))
    gold_draw(fr, A["orn"], W / 2, H / 2 - 40, a, wp=None)
    q = ramp(lt, 1.2, 2.2)
    blit_c(fr, blur_in(A["coming"][0], q, 10), W / 2, H / 2 + 50, a * q)
    q = ramp(lt, 2.0, 3.0)
    blit_c(fr, A["coming"][1], W / 2, H / 2 + 140 + (1 - q) * 12, a * q)


def sc_countdown(fr, t, t0):
    if t < t0 - 0.5 or t >= CLIMAX:
        return
    lt = t - t0
    a_in = ramp(lt, -0.4, 0.5)
    cx, cy = W / 2, H / 2
    S = A["cd_r"].shape[0]
    ring = A["cd_ring"]
    blit_c(fr, ring, cx, cy, a_in * 0.85)
    if lt < 0:
        return
    idx = min(int(lt / 1.6), 4)
    n = 5 - idx
    u = (lt - idx * 1.6) / 1.6
    # 進む金の弧
    r, ang = A["cd_r"], A["cd_ang"]
    band = np.clip(2.6 - np.abs(r - 285) / 1.0, 0, 1) * (np.abs(r - 285) < 3.2)
    pg = ease_io(u)
    prog = band * np.clip((pg - ang) * 400, 0, 1)
    arc = np.empty((S, S, 4), np.float32)
    arc[..., :3] = np.minimum(A["cd_foil"] * 1.25, 1)
    arc[..., 3] = prog
    blit_c(fr, arc, cx, cy, a_in)
    a0 = 2 * math.pi * pg
    hx, hy = cx + 285 * math.sin(a0), cy - 285 * math.cos(a0)
    add_c(fr, A["star_big"], hx, hy, 0.9 * a_in)
    # 数字
    q = ease_out(u / 0.35)
    num = sheen(A["cd_num"][n], (u - 0.15) / 0.6)
    num = scale_img(num, 1.10 - 0.10 * q)
    fade = min(q, 1 - ramp(u, 0.86, 1.0))
    blit_c(fr, num, cx, cy - 6, fade)
    # カウントの瞬間にほのかに明るく
    pulse = math.exp(-u * 6) * 0.10
    if pulse > 0.003:
        add_c(fr, A["flare_core"], cx, cy, pulse * 3)


def sc_final(fr, t):
    if t < CLIMAX:
        return
    lt = t - CLIMAX
    # 光のはじけ
    b = A["burst"]
    if lt < 5:
        for i in range(len(b["ang"])):
            dist = b["sp"][i] * (1 - math.exp(-lt * 1.4)) / 1.4
            x = W / 2 + math.cos(b["ang"][i]) * dist
            y = H / 2 + math.sin(b["ang"][i]) * dist * 0.75 + lt * 20
            al = (1 - ramp(lt, 1.5, 5.0)) * (0.55 + 0.45 * math.sin(lt * 8 + b["ph"][i]))
            if b["star"][i]:
                add_c(fr, A["star"], x, y, al)
            else:
                add_c(fr, A["dot"], x, y, al * 0.9)
    flash = math.exp(-lt * 2.6)
    if flash > 0.01:
        fr += flash * 0.55 * WARM
        flare(fr, W / 2, H / 2, flash * 1.2)
    a = 1 - ramp(t, 87.6, 89.6)
    gold_draw(fr, A["wreath_s"], W / 2, 205, a * ramp(lt, 0.3, 1.5), sh=(lt - 3.5) / 1.5)
    blit_c(fr, A["mono_s"], W / 2, 207, a * ramp(lt, 0.6, 1.8))
    blit_c(fr, A["fin_event"], W / 2, 400, a * ramp(lt, 0.8, 2.0))
    gold_draw(fr, A["fin_names"], W / 2, 535, a, sh=(lt - 3.0) / 1.8, wp=ease((lt - 0.4) / 2.6))
    blit_c(fr, wipe_center(A["orn"], ease((lt - 1.8) / 1.2)), W / 2, 665, a)
    gold_draw(fr, A["fin_date"], W / 2, 735, a * ramp(lt, 2.4, 3.4), sh=(lt - 4.2) / 1.4)
    q = ramp(lt, 3.4, 4.6)
    blit_c(fr, blur_in(A["fin_close"], q, 10), W / 2, 825, a * q)


def render(t):
    fr = A["bg"].copy()
    lb_story = letterbox(t, 13 * BAR, 17 * BAR) if 13 * BAR - 0.1 <= t <= 17 * BAR + 0.1 else 0
    atm = 1.0 - 0.6 * lb_story
    draw_atmos(fr, t, atm)
    sc_prologue(fr, t)
    sc_vertical(fr, t, A["msg1"], 3 * BAR, 5 * BAR, True)
    sc_vertical(fr, t, A["msg2"], 5 * BAR, 7 * BAR, False)
    sc_profile(fr, t, "groom", 7 * BAR, 10 * BAR, True)
    sc_profile(fr, t, "bride", 10 * BAR, 13 * BAR, False)
    sc_story(fr, t)
    sc_thanks(fr, t, 17 * BAR, 19 * BAR)
    sc_coming(fr, t, 19 * BAR, 21 * BAR)
    sc_countdown(fr, t, 21 * BAR)
    sc_final(fr, t)
    draw_particles(fr, t, 1.0 - 0.5 * lb_story)
    fr *= A["vig"]
    fr += A["grain"][int(t * FPS) % 6] * 0.018
    # 冒頭は暗闇から、最後は暗闇へ
    k = ramp(t, 0, 1.6) * (1 - ramp(t, 88.4, 90.0))
    if k < 1:
        fr *= k
    if A["wm"] is not None:
        blit(fr, A["wm"], W - A["wm"].shape[1] - 50, 42, 0.45)
    return (np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8)


# ---------------------------------------------------------------- 書き出し
def encode(args):
    idx, f0, f1, path = args
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-tune", "film", "-pix_fmt", "yuv420p",
           "-g", str(FPS * 2), path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(render(f / FPS).tobytes())
        if idx == 0 and (f - f0) % 90 == 0:
            print(f"  レンダリング中… {100 * (f - f0) / (f1 - f0):.0f}%", flush=True)
    p.stdin.close()
    p.wait()
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "wedding_opening_luxe_sample.mp4"))
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--preview-dir", default=HERE)
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    build(cfg)
    if args.preview is not None:
        for t in args.preview:
            p = os.path.join(args.preview_dir, f"preview_{t:g}.png")
            Image.fromarray(render(t)).save(p)
            print("wrote", p)
        return
    if args.stills:
        d = os.path.join(HERE, "stills")
        os.makedirs(d, exist_ok=True)
        for name, t in (("01_crest", 8.4), ("02_message", 15.0), ("03_groom", 31.0), ("04_bride", 40.6),
                        ("05_story", 47.4), ("06_thankyou", 59.6), ("07_entrance", 66.0), ("08_countdown", 70.6),
                        ("09_final", 84.0)):
            Image.fromarray(render(t)).save(os.path.join(d, name + ".jpg"), quality=93)
        print("wrote", d)
        return
    total = int(DURATION * FPS)
    tmp = tempfile.mkdtemp()
    n = max(1, args.workers)
    b = [round(total * i / n) for i in range(n + 1)]
    jobs = [(i, b[i], b[i + 1], os.path.join(tmp, f"seg{i}.mp4")) for i in range(n)]
    print(f"{total}フレームを{n}並列でレンダリングします")
    with Pool(n) as pool:
        segs = pool.map(encode, jobs)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{s}'\n" for s in segs)
    bgm = cfg.get("bgm")
    if bgm and not os.path.isabs(bgm):
        bgm = os.path.join(HERE, bgm)
    if not bgm or not os.path.exists(bgm):
        bgm = os.path.join(tmp, "bgm.wav")
        subprocess.run([sys.executable, os.path.join(HERE, "music_luxe.py"), bgm], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", bgm,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                    "-af", f"afade=t=out:st={DURATION - 3}:d=3", "-t", str(DURATION), "-movflags", "+faststart", args.out],
                   check=True)
    print("完成:", args.out)


if __name__ == "__main__":
    main()
