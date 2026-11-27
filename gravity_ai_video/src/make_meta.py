# -*- coding: utf-8 -*-
"""字幕(SRT) と YouTube 概要欄テキスト (チャプター付き) を生成。"""
import json, os, re, sys

WORK = os.environ.get("WORK", "/tmp/gravity_work")
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
TL = json.load(open(f"{WORK}/timeline.json"))


def ts(t, srt=True):
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return f"{m}:{int(s):02d}"


n = 1
with open(f"{OUT}/subtitles_ja.srt", "w", encoding="utf-8") as f:
    for sc in TL:
        for ln in sc["lines"]:
            a = sc["start"] + ln["start"]
            b = a + ln["dur"] + 0.2
            f.write(f"{n}\n{ts(a)} --> {ts(b)}\n{re.sub('[{}]', '', ln['sub'])}\n\n")
            n += 1

CH = [("s00_hook", "オープニング"), ("s02_weak", "重力はじつは“最弱”の力"), ("s03_spacetime", "重力の正体は時空のゆがみ"),
      ("s04_frog", "海外の実験①：宙に浮いたカエル"), ("s05_tokamak", "海外の実験②：AIが核融合プラズマを制御"),
      ("s06_morning", "未来の一日：朝のベッド"), ("s07_home", "未来の一日：家事"), ("s08_city", "未来の一日：通勤・物流"),
      ("s09_care", "未来の一日：医療・介護"), ("s10_play", "未来の一日：あそび"), ("s11_space", "宇宙は「のぼる」場所へ"),
      ("s12_risk", "重力社会のリスク"), ("s13_end", "エンディング")]
start = {s["id"]: s["start"] for s in TL}
chap = "\n".join(f"{ts(start[i], False) if start[i] > 0 else '0:00'} {name}" for i, name in CH)

desc = f"""【もしもAIが重力を操れたら】世界はこう変わる｜思考実験

もしAIが重力をコントロールできるようになったら、私たちの朝・家事・通勤・介護・遊び、そして宇宙開発はどう変わるのか？
実在する海外の研究（磁場で浮いたカエル、AIによる核融合プラズマ制御）や、東京スカイツリーで確かめられた「時間の進み方の違い」もまじえて、本気でシミュレーションしてみました。

▼チャプター
{chap}

▼あなたなら重力を何に使いますか？ コメントで教えてください！

※この動画は思考実験です。現在の物理学では、重力を自在に操る方法は見つかっていません。

▼参考文献・出典
・M. V. Berry & A. K. Geim, "Of flying frogs and levitrons", European Journal of Physics 18 (1997)
・J. Degrave et al., "Magnetic control of tokamak plasmas through deep reinforcement learning", Nature 602 (2022)
・M. Takamoto, H. Katori et al., "Test of general relativity by a pair of transportable optical lattice clocks", Nature Photonics 14 (2020)
・NASA：宇宙飛行士の骨量減少（1か月あたり約1〜1.5%）
・IEA：世界の最終エネルギー消費における輸送部門の割合

▼クレジット
・映像／アニメーション／BGM／効果音：オリジナル制作（プログラムによる自動生成）
・ナレーション音声：Open JTalk ＋ HTS Voice "Mei"（© Nagoya Institute of Technology, CC BY 3.0）
・フォント：Noto Sans CJK JP（SIL Open Font License）

#重力 #AI #もしも #思考実験 #科学 #未来 #宇宙
"""
open(f"{OUT}/youtube_description.txt", "w", encoding="utf-8").write(desc)
print(chap)
