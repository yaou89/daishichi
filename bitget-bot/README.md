# Bitget 自動売買ボット（現物・移動平均クロス）

Bitget の現物市場で、**短期移動平均線が長期線を上抜けたら買い、下抜けたら売る**シンプルなボットです。
取引所との通信には [ccxt](https://github.com/ccxt/ccxt) を使っています。

> ⚠️ 暗号資産の自動売買は元本割れのリスクがあります。このボットは利益を保証しません。
> まずは `DRY_RUN=true`（注文を出さないモード）と少額で試してください。

## セットアップ

```bash
cd bitget-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 設定を編集
```

### API キーの作り方

1. Bitget にログイン →「API管理」→「API キーを作成」
2. 権限は **「現物取引（読み取り＋取引）」だけ**。**出金権限は絶対に付けない**
3. 可能なら IP 制限をかける（ボットを動かすサーバーの IP のみ許可）
4. API キー・シークレット・パスフレーズを `.env` に書く（`.env` は Git に上げない）

## 使い方

```bash
python bot.py backtest   # 直近 1000 本の足で戦略を検証（API キー不要）
python bot.py run        # 自動売買を開始
```

- `DRY_RUN=true` の間は注文を出さずログ（`bot.log`）に出すだけです。
  挙動に納得したら `DRY_RUN=false` にすると実際に注文します。
- 保有状態は `state.json` に保存されるので、再起動しても続きから動きます。
- 判定は**確定した足**だけで行い、同じ足で二重に注文しません。

## 設定（.env）

| 項目 | 説明 | 既定値 |
|---|---|---|
| `SYMBOL` | 取引ペア | `BTC/USDT` |
| `TIMEFRAME` | 足の長さ（`15m`, `1h`, `4h`, `1d` など） | `1h` |
| `FAST_MA` / `SLOW_MA` | 短期・長期移動平均の本数 | `9` / `21` |
| `ORDER_USDT` | 1 回の買いに使う USDT | `20` |
| `POLL_SECONDS` | チェック間隔（秒） | `60` |
| `DRY_RUN` | `true` なら注文を出さない | `true` |

## 24 時間動かすには

PC を閉じると止まるので、VPS やクラウドのサーバーで動かすのが一般的です。

```bash
nohup python bot.py run > /dev/null 2>&1 &
```

## 戦略を変えたいとき

売買判断は `strategy.py` の `crossover_signal()` だけにまとまっています。
RSI やボリンジャーバンドなどに差し替える場合もこの関数を書き換えれば OK です。

```bash
python -m unittest test_strategy   # テスト
```

## 補足

- Bitget には公式の「グリッドボット」「積立ボット」などもあり、コードを書かずに使えます。
  自分のロジックで動かしたい場合にこのボットを使ってください。
- 先物（レバレッジ）には対応していません。清算リスクが大きいため、まずは現物で慣れることをおすすめします。
