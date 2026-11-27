# もしもAIが重力を操れたら ― YouTube動画（約5分）

知識欲をそそる「思考実験」系のYouTube動画です。映像・BGM・効果音はすべてプログラムで生成したオリジナル素材なので、著作権を気にせず投稿できます。

## 成果物（`output/`）

| ファイル | 内容 |
|---|---|
| `gravity_ai_world.mp4` | 本編（1920×1080 / 30fps / 約5分09秒 / ラウドネス -14 LUFS） |
| `thumbnail.png` | サムネイル（1280×720） |
| `subtitles_ja.srt` | 字幕ファイル（YouTubeにアップロードすれば自動字幕の代わりに使えます） |
| `youtube_description.txt` | 概要欄（チャプター・出典・クレジット付き）。そのまま貼り付けて使えます |

## 構成

| 時間 | パート | 内容 |
|---|---|---|
| 0:00 | オープニング | ニュートンのリンゴが空中で止まる → タイトル |
| 0:25 | 重力は最弱の力 | 磁石とクリップ、4つの力の比較（対数グラフ） |
| 0:50 | 重力の正体 | 時空のゆがみ、東京スカイツリーの光格子時計実験 |
| 1:18 | WORLD REPORT① | オランダ・ナイメーヘンの「浮くカエル」実験（ガイム） |
| 1:35 | WORLD REPORT② | DeepMind×EPFL：AIが核融合プラズマを磁場制御 |
| 2:02 | 未来の一日 | 0.1Gで眠るベッド／ホコリが集まる掃除／冷蔵庫を指一本で |
| 2:48 | 通勤・物流 | 空中の立体道路、輸送エネルギー1/4 |
| 3:12 | 医療・介護 | 体重半分の重力アシスト、転倒をふわりと受け止める |
| 3:26 | あそび | 0.3Gのバスケでダンク、空中に浮かぶ水の球プール |
| 3:40 | 宇宙 | ロケット→宇宙エレベーター、ISSは「落ち続けている」（ニュートンの大砲） |
| 4:12 | リスク | 骨量の減少、重力ハッキング、ルールづくり |
| 4:40 | エンディング | 「あなたなら重力を何に使う？」＋チャンネル登録 |

## 「海外の動画」の扱いについて

他人のYouTube動画を無断で切り抜いて使うと、著作権侵害（Content IDによる収益化停止・削除・チャンネル警告）のリスクが高いため、この版では使っていません。代わりに、**海外の研究そのもの（論文・実験）を「WORLD REPORT」パートとして解説**する形にしています。

本物の映像を入れたいときは、次のような**使用が許されている素材**に差し替えると質がさらに上がります。

- **NASA の映像**（images.nasa.gov など）：原則パブリックドメインです。ISS・ロケット打ち上げのシーン（3:40〜）に最適です。
- **Pexels / Pixabay の動画**：商用利用可・クレジット不要です。
  - 検索キーワードの例：`bedroom morning`（2:02）、`city night aerial`（2:48）、`elderly walking park`（3:12）、`basketball dunk slow motion`（3:26）
- **海外のYouTube動画を引用するとき**：投稿者から許可を得るか、CC BY ライセンスの動画（YouTube検索の「フィルタ → クリエイティブ・コモンズ」で探せます）を使い、概要欄にクレジットを書いてください。

## 作り直す方法

```bash
# 依存: open-jtalk, hts voice "mei" (/opt/voices), ffmpeg, skia-python, numpy, scipy, pillow, Noto Sans CJK
export WORK=/tmp/gravity_work
cd src
python3 tts.py          # 台本(script.py) → ナレーション音声 + タイムライン
python3 render.py       # 全シーンを描画 → 映像
python3 audio.py        # BGM・効果音を合成してミックス
ffmpeg -i $WORK/video_noaudio.mp4 -i $WORK/mix.wav -c:v copy -c:a aac -b:a 192k -shortest ../output/gravity_ai_world.mp4
python3 make_meta.py ../output
python3 thumbnail.py ../output/thumbnail.png
```

台本を変えたいときは `src/script.py` を編集してください。尺と字幕は自動で合わせ直されます。`python3 render.py --test` を使うと、各シーンの確認用静止画だけを書き出せます。

## クレジット

- ナレーション：Open JTalk + HTS Voice "Mei"（© Nagoya Institute of Technology, CC BY 3.0）※概要欄にクレジット表記が必要です
- フォント：Noto Sans CJK JP（SIL Open Font License）
- 映像・BGM・効果音：本リポジトリのコードで生成したオリジナル素材
