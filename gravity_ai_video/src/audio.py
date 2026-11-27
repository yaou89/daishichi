# -*- coding: utf-8 -*-
"""オリジナルBGM・効果音をnumpyで合成し、ナレーションとミックスする (著作権フリー)。"""
import json, os, subprocess
import numpy as np

WORK = os.environ.get("WORK", "/tmp/gravity_work")
SR = 48000
TL = json.load(open(f"{WORK}/timeline.json"))
NAR = np.load(f"{WORK}/narration.npy")
TOTAL = sum(s["dur"] for s in TL)
N = int(TOTAL * SR) + SR
rng = np.random.default_rng(0)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def sec(name):
    for s in TL:
        if s["id"] == name:
            return s["start"], s["start"] + s["dur"]


def onepole_lp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x)


try:
    import scipy  # noqa
except ImportError:
    subprocess.run(["pip", "install", "-q", "scipy"], check=True)
from scipy.signal import lfilter, butter, sosfilt

BPM = 88
BEAT = 60 / BPM
BAR = BEAT * 4
# コード進行 (ルート, 構成音)  Am - F - C - G / 危機パートは Dm - Bb - Gm - A
PROG = [(57, [57, 60, 64, 69]), (53, [53, 57, 60, 65]), (48, [55, 60, 64, 67]), (55, [55, 59, 62, 67])]
DARK = [(50, [50, 53, 57, 62]), (46, [46, 50, 53, 58]), (55, [55, 58, 62, 67]), (57, [57, 61, 64, 69])]

t_all = np.arange(N) / SR
pad = np.zeros(N)
bass = np.zeros(N)
arp = np.zeros(N)
drums = np.zeros(N)
risk0, risk1 = sec("s12_risk")
hook1 = sec("s00_hook")[1]
end0 = sec("s13_end")[0]


def env_adsr(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na)
    if nr > 0:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


nbars = int(TOTAL / BAR) + 2
for b in range(nbars):
    t0 = b * BAR
    i0 = int(t0 * SR)
    chord_i = (b // 2) % 4
    dark = risk0 - 0.5 < t0 < risk1 - 1
    root, notes = (DARK if dark else PROG)[chord_i]
    n = int(BAR * SR * 1.15)
    if i0 + n > N:
        n = N - i0
    if n <= 0:
        break
    tt = np.arange(n) / SR
    e = env_adsr(n, 0.8, 0.9)
    # パッド: デチューンした倍音
    for m in notes:
        for det in (-0.12, 0.0, 0.11):
            f = midi(m + 12) * 2 ** (det / 12)
            for h, amp in ((1, 1.0), (2, 0.35), (3, 0.15), (4, 0.07)):
                pad[i0:i0 + n] += amp * np.sin(2 * np.pi * f * h * tt + rng.uniform(0, 6.28)) * e * 0.02
    # ベース
    fb = midi(root - 12)
    nb = int(BAR * SR)
    nb = min(nb, N - i0)
    tb = np.arange(nb) / SR
    for k in range(4):
        s0 = int(k * BEAT * SR)
        if s0 >= nb:
            break
        L = min(int(BEAT * SR * 0.95), nb - s0)
        tk = np.arange(L) / SR
        ek = np.exp(-tk * 2.5) * np.minimum(1, tk * 80)
        bass[i0 + s0:i0 + s0 + L] += (np.sin(2 * np.pi * fb * tk) + 0.25 * np.sin(4 * np.pi * fb * tk)) * ek * 0.22
    # アルペジオ (8分)
    pattern = [0, 1, 2, 3, 2, 1, 2, 3]
    for k in range(8):
        s0 = i0 + int(k * BEAT / 2 * SR)
        L = int(SR * 0.6)
        if s0 + L > N:
            continue
        f = midi(notes[pattern[k]] + 24)
        tk = np.arange(L) / SR
        ek = np.exp(-tk * 7) * np.minimum(1, tk * 300)
        tone = np.sin(2 * np.pi * f * tk) + 0.3 * np.sin(2 * np.pi * 2 * f * tk) * np.exp(-tk * 12)
        arp[s0:s0 + L] += tone * ek * 0.07
    # ドラム (キック・ハイハット)
    for k in range(4):
        s0 = i0 + int(k * BEAT * SR)
        if k in (0, 2):
            L = int(SR * 0.35)
            if s0 + L < N:
                tk = np.arange(L) / SR
                fk = 45 + 90 * np.exp(-tk * 30)
                ph = 2 * np.pi * np.cumsum(fk) / SR
                drums[s0:s0 + L] += np.sin(ph) * np.exp(-tk * 9) * 0.45
        s1 = s0 + int(BEAT / 2 * SR)
        L = int(SR * 0.06)
        if s1 + L < N:
            hh = rng.standard_normal(L) * np.exp(-np.arange(L) / SR * 60)
            drums[s1:s1 + L] += hh * 0.04

# 高域を落としてアンビエントに
sos = butter(2, 3200, "low", fs=SR, output="sos")
pad = sosfilt(sos, pad)
sos2 = butter(2, 6000, "low", fs=SR, output="sos")
arp = sosfilt(sos2, arp)
# アルペジオにディレイ
d = int(BEAT * 0.75 * SR)
arp_d = arp.copy()
for k in range(1, 4):
    arp_d[d * k:] += arp[:-d * k] * (0.35 ** k)
arp = arp_d
sos_hp = butter(2, 9000, "high", fs=SR, output="sos")
drums_hh = drums  # (簡略)


# セクションごとの音量オートメーション
def auto(points):
    xs, ys = zip(*points)
    return np.interp(t_all, xs, ys)


title0 = sec("s01_title")[0]
lvl_drum = auto([(0, 0), (title0 - 0.1, 0), (title0, 0.7), (sec("s02_weak")[0], 0.0), (sec("s06_morning")[0] - 1, 0.0),
                 (sec("s06_morning")[0], 0.55), (risk0 - 0.5, 0.55), (risk0, 0.9), (risk1, 0.9), (end0, 0.0), (TOTAL + 1, 0)])
lvl_arp = auto([(0, 0.2), (title0, 1.0), (risk0, 0.7), (end0, 0.8), (TOTAL - 4, 0.6), (TOTAL + 1, 0)])
lvl_pad = auto([(0, 0.0), (2, 1.0), (TOTAL - 5, 1.0), (TOTAL + 1, 0)])
lvl_bass = auto([(0, 0.0), (title0, 0.9), (TOTAL - 5, 0.6), (TOTAL + 1, 0)])
bgm = pad * lvl_pad + bass * lvl_bass + arp * lvl_arp + drums * lvl_drum

# ---------- 効果音 ----------
sfx = np.zeros(N)


def add(at, x, gain=1.0):
    i = int(at * SR)
    L = min(len(x), N - i)
    if L > 0 and i >= 0:
        sfx[i:i + L] += x[:L] * gain


def whoosh(dur=0.8, up=True):
    L = int(dur * SR)
    x = rng.standard_normal(L)
    tk = np.linspace(0, 1, L)
    out = np.zeros(L)
    # 時間変化するバンドパスを近似: ブロック処理
    blk = 2048
    for s in range(0, L, blk):
        k = tk[s]
        fc = 300 + 4000 * (k if up else 1 - k)
        sos = butter(2, [fc * 0.6, min(fc * 1.6, 20000)], "band", fs=SR, output="sos")
        out[s:s + blk] = sosfilt(sos, x[s:s + blk])
    env = np.sin(np.pi * tk) ** 2
    return out * env * 0.35


def boom():
    L = int(SR * 2.5)
    tk = np.arange(L) / SR
    f = 30 + 60 * np.exp(-tk * 4)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-tk * 1.6) * 0.9


def riser(dur=2.0):
    L = int(dur * SR)
    tk = np.arange(L) / SR
    f = 200 * 2 ** (tk / dur * 3)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * 0.15 + rng.standard_normal(L) * 0.04) * (tk / dur) ** 2


def ping(f=1760):
    L = int(SR * 0.5)
    tk = np.arange(L) / SR
    return (np.sin(2 * np.pi * f * tk) + 0.5 * np.sin(2 * np.pi * f * 1.5 * tk)) * np.exp(-tk * 9) * 0.12


def glitch(dur=0.5):
    L = int(dur * SR)
    x = np.sign(np.sin(2 * np.pi * rng.uniform(80, 400) * np.arange(L) / SR)) * 0.15
    x *= (rng.random(L // 800 + 1).repeat(800)[:L] > 0.4)
    return x


for i, s in enumerate(TL):
    if i == 0:
        continue
    add(s["start"] - 0.35, whoosh(0.8, up=(i % 2 == 0)), 0.8)
add(title0 - 2.0, riser(2.0), 1.0)
add(title0, boom(), 1.0)
# 重力が止まる瞬間
hk = TL[0]
add(hk["start"] + hk["lines"][2]["start"] + 0.95, boom(), 0.6)
add(hk["start"] + hk["lines"][2]["start"] + 0.95, ping(880), 1.5)
# ハッキング
rk = sec("s12_risk")[0]
for k in range(5):
    add(rk + TL[12]["lines"][2]["start"] - 0.3 + k * 0.6, glitch(0.25), 0.6)
add(rk - 0.2, ping(440) * 2, 1.0)
# エンドカードのクリック音
e0 = sec("s13_end")[0] + TL[13]["lines"][3]["start"] - 0.3
add(e0 + 0.5, ping(1320), 1.2)
add(e0 + 0.9, ping(1568), 1.2)
add(e0 + 1.3, ping(1760), 1.2)
add(e0 + 2.8, ping(2093), 1.5)

# ---------- ミックス ----------
nar = np.zeros(N)
nar[:min(N, len(NAR))] = NAR[:N]
env = np.abs(nar)
k = int(0.25 * SR)
env = np.convolve(env, np.ones(k) / k, mode="same")
env = np.clip(env / (env.max() * 0.25 + 1e-9), 0, 1)
duck = 1 - 0.45 * env
bgm_g = bgm / (np.abs(bgm).max() + 1e-9) * 0.30
mix = nar * 1.0 + bgm_g * duck + sfx * 0.8
mix = np.tanh(mix * 1.1) / 1.1
st = np.stack([mix, mix], 1)
# 簡易ステレオ感: アルペジオ成分を左右にずらす
st[:, 0] += (arp * lvl_arp)[:N] / (np.abs(bgm).max() + 1e-9) * 0.30 * duck * 0.25
st[:, 1] -= (arp * lvl_arp)[:N] / (np.abs(bgm).max() + 1e-9) * 0.30 * duck * 0.25
st = st[:int(TOTAL * SR)]
pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
import wave
with wave.open(f"{WORK}/mix_raw.wav", "w") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
# BGMのみ (差し替え用)
bg = (np.clip(np.stack([bgm_g, bgm_g], 1)[:int(TOTAL * SR)], -1, 1) * 32767).astype(np.int16)
with wave.open(f"{WORK}/bgm_only.wav", "w") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(bg.tobytes())
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{WORK}/mix_raw.wav", "-af",
                "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), f"{WORK}/mix.wav"], check=True)
print("audio ok", TOTAL)
