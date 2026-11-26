"""
オリジナルBGM生成（ピアノ＋パッド＋ベル） ― 著作権フリー（このスクリプトで合成した自作曲）
テンポ75BPM / ニ長調 / カノン進行をベースにしたオリジナルメロディ
映像のシーン切り替えは小節頭（3.2秒刻み）に合わせてあります。

使い方: python3 music.py [出力wav]
"""
import sys
import wave
import numpy as np

SR = 44100
BPM = 75
BEAT = 60.0 / BPM          # 0.8 s
BAR = BEAT * 4             # 3.2 s
TOTAL = 80.0               # 映像と同じ長さ

rng = np.random.default_rng(7)


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ------------------------------------------------------------------ 音源
def piano(m, dur, vel=0.6):
    """加算合成の簡易ピアノ（倍音ごとに減衰を変える＋わずかな不協和）"""
    f = midi_hz(m)
    length = dur + 2.5
    t = np.arange(int(length * SR)) / SR
    out = np.zeros_like(t)
    B = 0.00035
    base_decay = 0.9 + (m - 60) * 0.035
    for n in range(1, 11):
        fn = f * n * np.sqrt(1 + B * n * n)
        if fn > SR / 2.2:
            break
        amp = (1.0 / n ** 1.4) * (1.0 if n == 1 else 0.8)
        dec = base_decay * (1 + 0.45 * (n - 1))
        out += amp * np.exp(-t * dec) * np.sin(2 * np.pi * fn * t + rng.uniform(0, 6.28))
    # 打鍵の立ち上がり
    att = np.clip(t / 0.004, 0, 1)
    # 鍵盤を離した後のリリース
    rel = np.ones_like(t)
    r0 = int(dur * SR)
    rel[r0:] = np.exp(-(t[r0:] - dur) * 6.0)
    # 高音ほど少し明るく
    out *= att * rel * vel * (0.9 if m > 72 else 1.0)
    return out


def pad(m, dur, vel=0.18):
    """ストリングス風パッド（デチューン3声・ゆっくり立ち上がり）"""
    f = midi_hz(m)
    length = dur + 1.5
    t = np.arange(int(length * SR)) / SR
    out = np.zeros_like(t)
    for det in (-0.12, 0.0, 0.13):
        ff = f * 2 ** (det / 12)
        for n in range(1, 7):
            out += (0.55 ** (n - 1)) * np.sin(2 * np.pi * ff * n * t + rng.uniform(0, 6.28))
    env = np.clip(t / 0.9, 0, 1) ** 1.5
    r0 = int(dur * SR)
    env[r0:] *= np.exp(-(t[r0:] - dur) * 3.0)
    trem = 1 + 0.05 * np.sin(2 * np.pi * 4.5 * t)
    return out * env * trem * vel / 6


def bell(m, vel=0.25):
    """グロッケン風ベル"""
    f = midi_hz(m)
    t = np.arange(int(3.0 * SR)) / SR
    out = np.zeros_like(t)
    for ratio, amp, dec in ((1, 1.0, 1.6), (2.76, 0.45, 3.5), (5.4, 0.25, 6.0), (8.9, 0.1, 9.0)):
        out += amp * np.exp(-t * dec) * np.sin(2 * np.pi * f * ratio * t)
    return out * np.clip(t / 0.002, 0, 1) * vel


def boom(vel=0.5):
    """カウントダウン用の柔らかい低音"""
    t = np.arange(int(1.6 * SR)) / SR
    f = 70 * np.exp(-t * 3) + 42
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 3.2) * np.clip(t / 0.01, 0, 1) * vel


# ------------------------------------------------------------------ 譜面
L = np.zeros((int((TOTAL + 3) * SR), 2))


def put(sig, start, pan=0.0):
    i = int(start * SR)
    j = min(i + len(sig), len(L))
    sig = sig[: j - i]
    L[i:j, 0] += sig * np.sqrt(0.5 * (1 - pan))
    L[i:j, 1] += sig * np.sqrt(0.5 * (1 + pan))


# コード（ルート, 3和音のMIDI）
CH = {
    "D": (50, [62, 66, 69]),
    "A": (45, [57, 61, 64]),
    "Bm": (47, [59, 62, 66]),
    "F#m": (42, [54, 57, 61]),
    "G": (43, [55, 59, 62]),
    "Asus": (45, [57, 62, 64]),
}

intro = ["D", "G", "D", "A"]
canon = ["D", "A", "Bm", "F#m", "G", "D", "G", "A"]
prog = intro + canon + canon  # 20小節 (0〜64秒)

melA = [
    [(78, 2), (76, 1), (74, 1)],
    [(73, 2), (76, 1), (81, 1)],
    [(78, 3), (74, 1)],
    [(73, 2), (69, 1), (73, 1)],
    [(71, 1), (74, 1), (79, 2)],
    [(78, 2), (76, 1), (74, 1)],
    [(71, 1), (74, 1), (76, 1), (79, 1)],
    [(76, 4)],
]
melB = [
    [(81, 2), (78, 1), (81, 1)],
    [(85, 2), (81, 1), (76, 1)],
    [(83, 2), (86, 1), (83, 1)],
    [(81, 3), (78, 1)],
    [(79, 1), (81, 1), (83, 2)],
    [(81, 2), (78, 1), (74, 1)],
    [(79, 1), (78, 1), (76, 1), (74, 1)],
    [(76, 2), (73, 2)],
]


def arpeggio(bar_i, chord, vel, dense=False):
    root, tri = CH[chord]
    t0 = bar_i * BAR
    put(piano(root - 12, BAR * 0.95, vel * 1.0), t0, -0.25)            # ベース
    pattern = [root, root + 7, tri[0], tri[1], tri[2], tri[1], tri[0], root + 7]
    for k, n in enumerate(pattern):
        if not dense and k % 2 == 1:
            continue
        put(piano(n, BEAT * 0.5, vel * (0.55 if k else 0.7)), t0 + k * BEAT / 2, 0.15 * np.sin(k))


for b, c in enumerate(prog):
    v = 0.28 if b < 4 else (0.32 if b < 12 else 0.36)
    arpeggio(b, c, v, dense=b >= 2)
    if b >= 12:  # 後半はパッドで厚みを足す
        root, tri = CH[c]
        for n in tri:
            put(pad(n, BAR * 0.98, 0.16), b * BAR, rng.uniform(-0.5, 0.5))
        put(pad(root, BAR, 0.10), b * BAR, 0)


def melody(bars, start_bar, vel, octave=0):
    for i, bar in enumerate(bars):
        t = (start_bar + i) * BAR
        for m, d in bar:
            put(piano(m + octave, d * BEAT * 0.95, vel), t, 0.1)
            t += d * BEAT


melody(melA, 4, 0.42)
melody(melB, 12, 0.46)
melody([[(n - 12, d) for n, d in bar] for bar in melB], 12, 0.16)  # 後半はオクターブ下で重ねる

# ---- カウントダウン（64.0〜72.0秒）: G → Asus → A で盛り上げる
cd0 = 20 * BAR  # 64.0
for k in range(10):  # 2拍ごとにカウント、1拍ずつ刻み
    t = cd0 + k * BEAT
    chord = "G" if k < 4 else ("Asus" if k < 8 else "A")
    root, tri = CH[chord]
    cres = 0.18 + 0.03 * k
    for n in tri:
        put(piano(n + 12, BEAT * 0.9, cres * 0.7), t, rng.uniform(-0.3, 0.3))
    put(piano(root, BEAT * 0.9, cres), t, -0.2)
    if k % 2 == 0:
        put(boom(0.35 + 0.03 * k), t, 0)
        put(bell(93, 0.10 + 0.01 * k), t, 0.3)
for n in CH["Asus"][1]:
    put(pad(n + 12, BEAT * 4, 0.12), cd0 + 4 * BEAT, 0)
for n in CH["A"][1]:
    put(pad(n + 12, BEAT * 2, 0.15), cd0 + 8 * BEAT, 0)

# ---- クライマックス（72.0秒〜）
tc = 72.0
for n, v in ((38, 0.5), (50, 0.45), (57, 0.35), (62, 0.35), (66, 0.32), (69, 0.32), (74, 0.3), (78, 0.3)):
    put(piano(n, 5.5, v), tc, rng.uniform(-0.4, 0.4))
for n in (62, 66, 69, 74):
    put(pad(n, 6.0, 0.16), tc, rng.uniform(-0.5, 0.5))
put(piano(86, 2.2, 0.5), tc, 0.1)
for i, (n, d) in enumerate([(85, 1), (83, 1), (81, 2)]):
    put(piano(n, d * BEAT, 0.38), tc + 2 * BEAT + sum([1, 1, 2][:i]) * BEAT, 0.1)
for i, n in enumerate([86, 90, 93, 98]):
    put(bell(n, 0.12), tc + i * 0.12, 0.4)
# エンディングの分散和音
for i, n in enumerate([62, 66, 69, 74, 78, 81, 86]):
    put(piano(n, 3.0, 0.22), tc + 4 * BEAT + i * BEAT / 2, 0.2 * np.sin(i))

# ------------------------------------------------------------------ リバーブ & マスタリング
def reverb(x, seconds=2.4, mix=0.28, seed=1):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-t * 3.0 / seconds * 2.2)
    # 高域を少し丸める
    k = np.ones(8) / 8
    ir = np.convolve(ir, k, mode="same")
    ir[: int(0.012 * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    N = 1
    while N < len(x) + n:
        N *= 2
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[: len(x)]
    return x * (1 - mix) + y * mix * 1.6


out = np.stack([reverb(L[:, 0], seed=1), reverb(L[:, 1], seed=2)], axis=1)
out = out[: int(TOTAL * SR)]
# 全体のフェード
n = len(out)
fade_in = np.clip(np.arange(n) / (0.3 * SR), 0, 1)
fade_out = np.clip((n - np.arange(n)) / (3.0 * SR), 0, 1)
out *= (fade_in * fade_out)[:, None]
out /= np.max(np.abs(out)) + 1e-9
out = np.tanh(out * 1.3) / np.tanh(1.3) * 0.89

path = sys.argv[1] if len(sys.argv) > 1 else "bgm.wav"
with wave.open(path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote", path, f"{len(out)/SR:.1f}s")
