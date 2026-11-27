# -*- coding: utf-8 -*-
"""台本 -> ナレーション音声 (Open JTalk + HTS voice "Mei") とタイムライン JSON を作る。"""
import json, os, re, subprocess, sys, wave
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from script import SCENES, NOTES

WORK = os.environ.get("WORK", "/tmp/gravity_work")
DIC = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE = os.environ.get("VOICE", "/opt/voices/package/voice/mei/mei_normal.htsvoice")
RATE = float(os.environ.get("RATE", "1.12"))
SR = 48000
LEAD, GAP, TAIL = 0.7, 0.45, 0.7


def synth(text, out):
    txt = out + ".txt"
    with open(txt, "w") as f:
        f.write(text)
    raw = out + ".raw.wav"
    subprocess.run(["open_jtalk", "-x", DIC, "-m", VOICE, "-r", str(RATE), "-fm", "1.0",
                    "-a", "0.55", "-jf", "1.1", "-ow", raw, "-ot", out + ".trace", txt], check=True)
    # 48kHz に変換し、無音をトリム
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af",
                    "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    "highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,volume=1.6",
                    "-ar", str(SR), "-ac", "1", out], check=True)
    with wave.open(out) as w:
        return w.getnframes() / w.getframerate()


def readings(trace):
    """trace からフォネーム列を取り出す (読み確認用)"""
    ph = []
    for line in open(trace, encoding="utf-8", errors="ignore"):
        m = re.search(r"\^([a-zA-Z]+)\-([a-zA-Z]+)\+", line)
        if m:
            p = m.group(2)
            if p not in ("sil",):
                ph.append("_" if p == "pau" else p)
    return "".join(ph)


def main():
    os.makedirs(f"{WORK}/tts", exist_ok=True)
    timeline, t = [], 0.0
    full = []
    for sc in SCENES:
        lead = LEAD
        start = t
        lines = []
        cur = lead
        for i, (sub, tts) in enumerate(sc["lines"]):
            text = tts if tts else re.sub(r"[{}]", "", sub)
            out = f"{WORK}/tts/{sc['id']}_{i:02d}.wav"
            d = synth(text, out)
            lines.append(dict(sub=sub, start=round(cur, 3), dur=round(d, 3), wav=out))
            cur += d + GAP
        dur = cur - GAP + TAIL + sc.get("pad", 0.0)
        notes = [dict(line=li, text=tx) for li, tx in NOTES.get(sc["id"], [])]
        timeline.append(dict(id=sc["id"], chapter=sc["chapter"], g=sc["g"], start=round(start, 3),
                             dur=round(dur, 3), lines=lines, notes=notes))
        t += dur
    json.dump(timeline, open(f"{WORK}/timeline.json", "w"), ensure_ascii=False, indent=1)

    # ナレーション全体トラック
    total = int((t + 1) * SR)
    track = np.zeros(total, np.float32)
    for sc in timeline:
        for ln in sc["lines"]:
            with wave.open(ln["wav"]) as w:
                a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
            s = int((sc["start"] + ln["start"]) * SR)
            track[s:s + len(a)] += a
    np.save(f"{WORK}/narration.npy", track)
    print(f"total {t:.1f}s")
    for sc in timeline:
        print(f"{sc['id']:16s} {sc['start']:7.2f} {sc['dur']:6.2f}")


if __name__ == "__main__":
    main()
