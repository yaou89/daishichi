"""
ラグジュアリー版 オリジナルBGM（ピアノ＋ストリングス＋ハープ＋チェレスタ＋ティンパニ＋クワイア）
・作曲から音源化までこのスクリプトで行う完全オリジナル曲（著作権の心配なし）
・音源: FluidR3_GM サウンドフォント（MITライセンス）を fluidsynth で鳴らす
・75BPM / ニ長調 / 1小節 = 3.2秒。映像のシーン切り替えは小節頭に合わせてある

  python3 music_luxe.py [出力wav]
必要: pip install mido numpy / fluidsynth / FluidR3_GM.sf2
"""
import os
import subprocess
import sys
import tempfile
import wave

import mido
import numpy as np

SF2_CANDIDATES = ["/usr/share/sounds/sf2/FluidR3_GM.sf2", "/usr/share/soundfonts/FluidR3_GM.sf2",
                  os.path.join(os.path.dirname(os.path.abspath(__file__)), "FluidR3_GM.sf2")]
SR = 44100
BPM = 75
BEAT = 60 / BPM
BAR = BEAT * 4
TOTAL = 90.0
CLIMAX = 75.2
TPB = 480

# チャンネルと音色（GM番号）
CH = dict(piano=(0, 0), pad=(1, 49), cello=(2, 42), harp=(3, 46), celesta=(4, 8), vln=(5, 48),
          timp=(6, 47), choir=(7, 52), bass=(8, 43), horn=(10, 60), trem=(11, 44))

events = []  # (秒, 優先度, mido.Message)


def note(inst, m, t, dur, vel):
    ch = CH[inst][0]
    events.append((t, 1, mido.Message("note_on", channel=ch, note=int(m), velocity=int(max(1, min(127, vel))))))
    events.append((t + dur, 0, mido.Message("note_off", channel=ch, note=int(m), velocity=0)))


def cc(inst, num, val, t):
    events.append((t, 0, mido.Message("control_change", channel=CH[inst][0], control=num, value=int(max(0, min(127, val))))))


def expr_ramp(inst, t0, t1, v0, v1, steps=24):
    for i in range(steps + 1):
        u = i / steps
        cc(inst, 11, v0 + (v1 - v0) * u, t0 + (t1 - t0) * u)


# ---------------------------------------------------------------- 和声
# 各小節: (ベース, [和音])
C = {
    "Dadd9": (38, [62, 64, 66, 69]),
    "Gmaj7": (43, [62, 66, 67, 71]),
    "D/F#": (42, [62, 66, 69, 74]),
    "Asus4": (45, [62, 64, 69]),
    "A": (45, [61, 64, 69]),
    "D": (38, [62, 66, 69]),
    "A/C#": (37, [61, 64, 69]),
    "Bm7": (35, [62, 66, 69, 71]),
    "Em7": (40, [62, 64, 67, 71]),
    "Bm": (35, [62, 66, 71]),
    "G": (43, [62, 67, 71]),
    "G/D": (38, [62, 67, 71]),
}
theme_prog = ["D", "A/C#", "Bm7", "Gmaj7", "D/F#", "Em7", "Asus4", "A"]
prog = ["Dadd9", "Gmaj7", "D/F#", "Asus4"] + theme_prog + theme_prog[:6] + ["A", "Bm", "G"]
# bar: 0-3 イントロ / 4-11 テーマ1 / 12-18 テーマ2 / 19-20 盛り上げ / 21〜 カウントダウン

theme = [
    [(69, 1.5), (66, .5), (69, 1), (74, 1)],
    [(73, 2), (71, 1), (69, 1)],
    [(71, 1.5), (69, .5), (71, 1), (78, 1)],
    [(76, 3), (74, 1)],
    [(74, 1.5), (73, .5), (74, 1), (81, 1)],
    [(79, 2), (78, 1), (76, 1)],
    [(74, 2), (76, 2)],
    [(73, 3), (69, 1)],
]


def melody(inst, bars, start_bar, vel, octave=0, legato=0.95, humanize=True):
    rng = np.random.default_rng(start_bar * 7 + octave)
    for i, bar in enumerate(bars):
        t = (start_bar + i) * BAR
        for m, d in bar:
            v = vel + (rng.integers(-5, 6) if humanize else 0)
            note(inst, m + octave, t, d * BEAT * legato, v)
            t += d * BEAT


def piano_arp(b, chord, vel, pattern="flow"):
    root, tri = C[chord]
    t0 = b * BAR
    note("piano", root, t0, BAR * 0.98, vel + 6)
    seq = [root + 12, tri[0], tri[1], tri[-1], tri[1] + 12 if len(tri) > 2 else tri[0] + 12, tri[-1], tri[1], tri[0]]
    for k, m in enumerate(seq):
        note("piano", m, t0 + k * BEAT / 2, BEAT * 1.2, vel - (0 if k % 4 == 0 else 8))


def pad(b0, b1, chord, vel=70, inst="pad"):
    root, tri = C[chord]
    for m in tri:
        note(inst, m, b0 * BAR, (b1 - b0) * BAR * 0.99, vel)


def harp_gliss(t, low=50, high=86, dur=1.2, vel=60):
    scale = [0, 2, 4, 6, 7, 9, 11]  # ニ長調
    notes = [m for m in range(low, high + 1) if (m - 62) % 12 in scale]
    for i, m in enumerate(notes):
        note("harp", m, t + dur * i / len(notes), 1.5, vel + i * 0.5)


def celesta_twinkle(t, notes, step=BEAT / 2, vel=55):
    for i, m in enumerate(notes):
        note("celesta", m, t + i * step, BEAT, vel)


# ---------------------------------------------------------------- 楽譜
for inst, (ch, prog_no) in CH.items():
    events.append((0, -1, mido.Message("program_change", channel=ch, program=prog_no)))
    cc(inst, 7, 100, 0)
    cc(inst, 91, 70, 0)   # リバーブ
    cc(inst, 93, 20, 0)   # コーラス
cc("pad", 7, 88, 0)
cc("vln", 7, 96, 0)
cc("choir", 7, 70, 0)
cc("timp", 7, 110, 0)
cc("celesta", 7, 80, 0)
cc("harp", 7, 92, 0)
cc("bass", 7, 90, 0)
cc("horn", 7, 72, 0)

# イントロ（0〜12.8秒）: 弦のふくらみ＋ハープのグリッサンド＋チェレスタ
expr_ramp("pad", 0, 5, 20, 100)
for b, ch_ in enumerate(prog[:4]):
    pad(b, b + 1, ch_, 72)
    note("bass", C[ch_][0], b * BAR, BAR * 0.98, 55)
harp_gliss(0.4, 50, 86, 2.0, 50)
celesta_twinkle(3.2, [86, 81, 78, 81, 86, 90], BEAT / 2, 50)
celesta_twinkle(6.4, [88, 85, 81, 85], BEAT, 45)
melody("piano", [[(81, 1), (78, 1), (76, 1), (74, 1)], [(76, 2), (73, 2)]], 2, 58)
piano_arp(3, "Asus4", 50)

# テーマ1（12.8〜38.4秒）: ピアノが主役、弦は控えめ
for i, ch_ in enumerate(theme_prog):
    b = 4 + i
    piano_arp(b, ch_, 52)
    pad(b, b + 1, ch_, 55)
    note("bass", C[ch_][0], b * BAR, BAR * 0.98, 50)
melody("piano", theme, 4, 78)
cc("pad", 11, 80, 4 * BAR)
expr_ramp("pad", 9 * BAR, 12 * BAR, 80, 105)
celesta_twinkle(7 * BAR + 2 * BEAT, [90, 86, 81], BEAT / 2, 40)
harp_gliss(11 * BAR + 2 * BEAT, 57, 81, 1.4, 50)

# テーマ2（38.4〜60.8秒）: ストリングスがメロディ、チェロの対旋律、ハープの分散和音
for i, ch_ in enumerate(theme_prog[:6] + ["A"]):
    b = 12 + i
    piano_arp(b, ch_, 50)
    pad(b, b + 1, ch_, 64)
    note("bass", C[ch_][0], b * BAR, BAR * 0.98, 64)
    root, tri = C[ch_]
    for k in range(8):  # ハープ
        m = (tri + [t + 12 for t in tri])[k % (len(tri) * 2)]
        note("harp", m, b * BAR + k * BEAT / 2, BEAT * 2, 46)
theme2 = theme[:6] + [[(76, 2), (73, 2)]]
melody("vln", theme2, 12, 86, 12, 1.0, False)
melody("piano", theme2, 12, 66)
cello_line = [[(50, 2), (52, 2)], [(49, 2), (57, 2)], [(47, 2), (54, 2)], [(43, 2), (47, 1), (50, 1)],
              [(54, 2), (52, 2)], [(52, 2), (55, 2)], [(57, 4)]]
melody("cello", cello_line, 12, 70)
expr_ramp("vln", 12 * BAR, 13 * BAR, 70, 100)
expr_ramp("vln", 17 * BAR, 19 * BAR, 100, 85)

# 盛り上げ（60.8〜67.2秒）: Bm → G、トレモロと弦のクレッシェンド
for b, ch_ in ((19, "Bm"), (20, "G")):
    root, tri = C[ch_]
    for m in tri:
        note("trem", m, b * BAR, BAR, 70)
        note("trem", m + 12, b * BAR, BAR, 60)
    note("bass", root, b * BAR, BAR, 80)
    note("cello", root + 12, b * BAR, BAR, 75)
    piano_arp(b, ch_, 56)
expr_ramp("trem", 19 * BAR, 21 * BAR, 50, 110)
melody("vln", [[(78, 4)], [(79, 2), (81, 2)]], 19, 80, 12, 1.0, False)

# カウントダウン（67.2〜75.2秒）: A のペダル、2拍ごとにティンパニ＋ベル
cd0 = 21 * BAR
for k in range(5):
    t = cd0 + k * 2 * BEAT
    note("timp", 33, t, 1.0, 70 + k * 10)
    note("celesta", 93, t, 0.6, 50 + k * 6)
    note("bass", 33, t, 2 * BEAT * 0.95, 70 + k * 8)
    ch_ = "Asus4" if k < 3 else "A"
    for m in C[ch_][1]:
        note("trem", m + 12, t, 2 * BEAT * 0.98, 70 + k * 7)
        note("pad", m, t, 2 * BEAT * 0.98, 70 + k * 6)
    for j in range(4):  # 8分のピアノの刻み
        note("piano", [57, 64, 69, 64][j] + (12 if k > 2 else 0), t + j * BEAT / 2, BEAT / 2, 50 + k * 6)
expr_ramp("trem", cd0, CLIMAX, 70, 127)
expr_ramp("pad", cd0, CLIMAX, 80, 120)
# 直前のティンパニロール
for i in range(16):
    note("timp", 33, CLIMAX - 0.8 + i * 0.05, 0.05, 50 + i * 4)
harp_gliss(CLIMAX - 1.2, 50, 93, 1.1, 64)

# クライマックス（75.2秒〜）: 全員でニ長調
tc = CLIMAX
for m, v in ((26, 100), (38, 100)):
    note("bass", m + 12, tc, 6.0, v)
note("timp", 38, tc, 2.0, 120)
note("timp", 26 + 12, tc + 0.02, 2.0, 100)
for m in (62, 66, 69, 74):
    note("pad", m, tc, 12.5, 100)
    note("choir", m, tc, 9.0, 78)
for m in (50, 57, 62):
    note("horn", m, tc, 6.0, 80)
cc("vln", 11, 120, tc)
climax_mel = [[(81, 3), (78, 1)], [(79, 2), (83, 2)], [(81, 4)]]
t = tc
for bar in climax_mel:
    for m, d in bar:
        note("vln", m, t, d * BEAT, 100)
        note("piano", m, t, d * BEAT, 88)
        note("piano", m - 12, t, d * BEAT, 70)
        t += d * BEAT
# G/D → D
note("pad", 67, tc + BAR, BAR, 90)
note("pad", 71, tc + BAR, BAR, 90)
for k, m in enumerate([38, 50, 57, 62, 66, 69, 74, 78, 81, 86]):
    note("piano", m, tc + 2 * BAR + k * BEAT / 4, 6.0, 70 - k * 2)
celesta_twinkle(tc + 0.1, [98, 93, 90, 86, 81], BEAT / 4, 60)
harp_gliss(tc + 2 * BAR + 1.0, 62, 98, 2.0, 48)
expr_ramp("pad", tc + 2 * BAR, TOTAL, 120, 40)
expr_ramp("choir", tc + 1 * BAR, tc + 3 * BAR, 110, 30)


# ---------------------------------------------------------------- MIDI 書き出し → fluidsynth
def write_midi(path):
    mid = mido.MidiFile(ticks_per_beat=TPB)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
    last = 0
    for t, _, msg in sorted(events, key=lambda e: (e[0], e[1])):
        tick = int(round(t / BEAT * TPB))
        tr.append(msg.copy(time=max(0, tick - last)))
        last = max(last, tick)
    mid.save(path)


def cymbal_swell(t_end, dur=4.0):
    """ティンパニ前のシンバルのふくらみ（ノイズから合成）"""
    n = int(dur * SR)
    rng = np.random.default_rng(3)
    x = rng.standard_normal(n)
    # 高域寄りに
    x = np.diff(np.concatenate([[0], x]))
    env = (np.arange(n) / n) ** 3
    out = np.zeros((int(TOTAL * SR) + SR * 4, 2))
    i = int((t_end - dur) * SR)
    out[i:i + n, 0] = x * env * 0.10
    out[i:i + n, 1] = np.roll(x, 37) * env * 0.10
    # 頂点のあと短く減衰
    tail = int(2.5 * SR)
    xt = np.diff(np.concatenate([[0], rng.standard_normal(tail)])) * np.exp(-np.arange(tail) / SR * 2.0) * 0.10
    out[i + n:i + n + tail, 0] += xt
    out[i + n:i + n + tail, 1] += np.roll(xt, 41)
    return out


def hall(x, seconds=3.2, seed=1):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-t * 6.9 / seconds)
    ir = np.convolve(ir, np.ones(12) / 12, mode="same")
    ir[: int(0.02 * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    N = 1 << int(np.ceil(np.log2(len(x) + n)))
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[: len(x)]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "bgm_luxe.wav"
    sf2 = next((p for p in SF2_CANDIDATES if os.path.exists(p)), None)
    if not sf2:
        raise SystemExit("FluidR3_GM.sf2 が見つかりません（apt install fluid-soundfont-gm）")
    tmp = tempfile.mkdtemp()
    mid = os.path.join(tmp, "score.mid")
    raw = os.path.join(tmp, "raw.wav")
    write_midi(mid)
    subprocess.run(["fluidsynth", "-ni", "-q", "-g", "0.5", "-r", str(SR), "-F", raw,
                    "-o", "synth.reverb.room-size=0.85", "-o", "synth.reverb.width=1.0",
                    "-o", "synth.reverb.level=0.75", "-o", "synth.reverb.damp=0.35", sf2, mid], check=True)
    with wave.open(raw) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(np.float64) / 32768
    n = int(TOTAL * SR)
    a = np.pad(a, ((0, max(0, n + SR * 4 - len(a))), (0, 0)))[: n + SR * 4]
    sw = cymbal_swell(CLIMAX)[: len(a)]
    a[: len(sw)] += sw
    # 大きなホールの残響を少し足す
    wet = np.stack([hall(a[:, 0], seed=1), hall(a[:, 1], seed=2)], axis=1)
    a = a * 0.82 + wet * 0.22
    a = a[:n]
    fade = np.clip((n - np.arange(n)) / (4.0 * SR), 0, 1)
    a *= fade[:, None]
    a *= np.clip(np.arange(n) / (0.05 * SR), 0, 1)[:, None]
    # 小さい場面も会場で聞こえるよう、音量差をゆるやかに縮める（約1秒で追従するコンプ）
    mono = np.sqrt(np.mean(a ** 2, axis=1))
    win = int(0.8 * SR)
    env = np.sqrt(np.convolve(mono ** 2, np.ones(win) / win, mode="same")) + 1e-6
    target = np.percentile(env, 90)
    g = np.clip((target / env) ** 0.6, 0.6, 3.2)
    g = np.convolve(g, np.ones(SR) / SR, mode="same")
    a *= g[:, None]
    # ゆるいコンプ＋リミッター
    peak = np.max(np.abs(a)) + 1e-9
    a = a / peak
    a = np.tanh(a * 1.6) / np.tanh(1.6) * 0.9
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype("<i2").tobytes())
    print("wrote", out_path, f"{n / SR:.1f}s")


if __name__ == "__main__":
    main()
