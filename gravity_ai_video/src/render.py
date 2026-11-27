# -*- coding: utf-8 -*-
"""タイムライン JSON -> シーン別 mp4 -> 結合。
使い方: python3 render.py [--test]  (--test は各シーン代表フレームの PNG のみ)
"""
import json, os, subprocess, sys, math
from multiprocessing import Pool
import numpy as np
import skia

sys.path.insert(0, os.path.dirname(__file__))
from engine import *
from scenes import DRAW

WORK = os.environ.get("WORK", "/tmp/gravity_work")
TL = json.load(open(f"{WORK}/timeline.json"))


class SceneInfo:
    def __init__(self, sc):
        self.dur = sc["dur"]
        self.L = [ln["start"] for ln in sc["lines"]]
        self.E = [ln["start"] + ln["dur"] for ln in sc["lines"]]


# ---------- 字幕 ----------
def parse_hl(s):
    out, hl = [], False
    for ch in s:
        if ch == "{":
            hl = True
        elif ch == "}":
            hl = False
        else:
            out.append((ch, hl))
    return out


BREAK_AFTER = set("、。？！ 」")
SUB_SIZE = 54
SUB_MAXW = 1640


def wrap(chars, size):
    f = font(size)
    plain = "".join(c for c, _ in chars)
    if f.measureText(plain) <= SUB_MAXW:
        return [chars]
    n = len(chars)
    best, bestscore = n // 2, 1e9
    for i in range(4, n - 3):
        if plain[i - 1] in BREAK_AFTER or plain[i - 1] in "はがをにでもとへのて":
            w1 = f.measureText(plain[:i])
            w2 = f.measureText(plain[i:])
            if max(w1, w2) > SUB_MAXW:
                continue
            score = abs(w1 - w2) + (0 if plain[i - 1] in BREAK_AFTER else 260)
            if score < bestscore:
                best, bestscore = i, score
    return [chars[:best], [x for x in chars[best:] if not (x[0] == " " and False)]]


def draw_runs(c, chars, cx, y, size, a):
    f = font(size)
    w = f.measureText("".join(ch for ch, _ in chars))
    x = cx - w / 2
    runs = []
    for ch, hl in chars:
        if runs and runs[-1][1] == hl:
            runs[-1][0] += ch
        else:
            runs.append([ch, hl])
    # 縁取り → 本体
    xs = []
    xx = x
    for s, hl in runs:
        xs.append(xx)
        xx += f.measureText(s)
    for (s, hl), x0 in zip(runs, xs):
        blob = skia.TextBlob.MakeFromString(s, f)
        c.drawTextBlob(blob, x0 + 3, y + 5, P("#000000", a * 0.5, blur=6))
        c.drawTextBlob(blob, x0, y, P("#0A0F24", a, stroke=13))
    for (s, hl), x0 in zip(runs, xs):
        blob = skia.TextBlob.MakeFromString(s, f)
        c.drawTextBlob(blob, x0, y, P("yellow" if hl else "white", a))


def subtitle(c, s, a):
    chars = parse_hl(s)
    size = SUB_SIZE
    rows = wrap(chars, size)
    while any(font(size).measureText("".join(ch for ch, _ in r)) > SUB_MAXW for r in rows) and size > 40:
        size -= 2
        rows = wrap(chars, size)
    lh = size * 1.3
    y0 = 1030 - lh * (len(rows) - 1)
    for i, r in enumerate(rows):
        draw_runs(c, r, W / 2, y0 + i * lh, size, a)


# ---------- オーバーレイ ----------
def overlay(c, sc, si, t, g):
    # チャプター
    if sc["chapter"]:
        k = eoc((t - 0.2) / 0.6)
        f = font(30, "Bold")
        tw = f.measureText(sc["chapter"])
        x = -tw - 80 + (tw + 120) * k
        rrect(c, x - 40, 34, tw + 80, 58, 29, P("#0A0F24", 0.75))
        c.drawRect(R(x - 40, 34, 10, 58), P("cyan"))
        text(c, sc["chapter"], x, 74, 30, "white", weight="Bold", align="left")
    # G-METER
    if sc["id"] not in ("s01_title",):
        x, y = 1600, 34
        rrect(c, x, y, 284, 70, 14, P("#0A0F24", 0.72))
        rrect(c, x, y, 284, 70, 14, P("cyan", 0.5, stroke=2))
        text(c, "AI-GRAVITY", x + 18, y + 28, 18, "cyan", weight="Bold", align="left", spacing=2)
        c.drawCircle(x + 150, y + 21, 5, P("green", 0.5 + 0.5 * math.sin(t * 4)))
        rrect(c, x + 18, y + 44, 120, 10, 5, P("#24305E"))
        rrect(c, x + 18, y + 44, max(6, 120 * clamp(g)), 10, 5, P("cyan" if g < 0.95 else "amber"))
        text(c, f"{g:.2f}G", x + 268, y + 56, 38, "white", align="right")
    # 注釈
    for nt in sc["notes"]:
        st = si.L[nt["line"]]
        en = si.E[nt["line"]] + 0.8
        if nt["line"] + 1 < len(si.L):
            en = min(en, si.L[nt["line"] + 1] + 1.5)
        else:
            en = si.dur
        a = ramp(t, st, 0.4) * (1 - ramp(t, en, 0.4))
        if a > 0:
            f = font(24, "Medium")
            tw = f.measureText(nt["text"])
            rrect(c, 40, 855 - 44 * 0 - 80, tw + 40, 44, 8, P("#0A0F24", 0.7 * a))
            text(c, nt["text"], 60, 806, 24, "#C8D2F0", a=a, weight="Medium", align="left")
    # 字幕
    for i, ln in enumerate(sc["lines"]):
        st, en = si.L[i] - 0.1, si.E[i] + 0.25
        if st <= t <= en:
            a = ramp(t, st, 0.12) * (1 - ramp(t, en - 0.1, 0.1))
            subtitle(c, ln["sub"], a)
    # フェード
    fin = ramp(t, 0, 0.35)
    fout = 1 - ramp(t, si.dur - 0.3, 0.3)
    k = min(fin, fout)
    if k < 1:
        c.drawRect(R(0, 0, W, H), P("#000000", 1 - k))


def scene_g(idx):
    return TL[idx]["g"]


def render_frame(c, idx, t):
    sc = TL[idx]
    si = SceneInfo(sc)
    c.clear(skia.ColorBLACK)
    res = DRAW[sc["id"]](c, t, si) or {}
    prev_g = scene_g(idx - 1) if idx > 0 else 1.0
    g = res.get("g", lerp(prev_g, sc["g"], ss(t / 1.5)))
    overlay(c, sc, si, t, g)


def render_scene(idx):
    sc = TL[idx]
    out = f"{WORK}/seg_{idx:02d}.mp4"
    n = int(round(sc["dur"] * FPS))
    arr = np.zeros((H, W, 4), np.uint8)
    surf = skia.Surface(arr)
    c = surf.getCanvas()
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                          "-threads", "2", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for f in range(n):
        render_frame(c, idx, f / FPS)
        p.stdin.write(arr.tobytes())
    p.stdin.close()
    p.wait()
    return out, n


def test_frames(ids=None, times=None):
    os.makedirs(f"{WORK}/test", exist_ok=True)
    arr = np.zeros((H, W, 4), np.uint8)
    surf = skia.Surface(arr)
    c = surf.getCanvas()
    for idx, sc in enumerate(TL):
        if ids and sc["id"] not in ids:
            continue
        si = SceneInfo(sc)
        ts = times or [ (si.L[i] + si.E[i]) / 2 for i in range(len(si.L))]
        for j, t in enumerate(ts):
            render_frame(c, idx, t)
            from PIL import Image
            Image.fromarray(arr[:, :, :3]).resize((960, 540)).save(f"{WORK}/test/{sc['id']}_{j}.jpg", quality=85)


if __name__ == "__main__":
    if "--test" in sys.argv:
        ids = [a for a in sys.argv[2:] if a.startswith("s")]
        test_frames(ids or None)
        sys.exit()
    order = sorted(range(len(TL)), key=lambda i: -TL[i]["dur"])
    with Pool(4) as pool:
        res = pool.map(render_scene, order)
    with open(f"{WORK}/concat.txt", "w") as f:
        for i in range(len(TL)):
            f.write(f"file 'seg_{i:02d}.mp4'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f"{WORK}/concat.txt",
                    "-c", "copy", f"{WORK}/video_noaudio.mp4"], check=True)
    print("done", sum(n for _, n in res), "frames")
