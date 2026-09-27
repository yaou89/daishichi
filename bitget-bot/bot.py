"""Bitget 現物の自動売買ボット（移動平均クロス戦略）。

使い方:
    python bot.py backtest   # 過去データで戦略を検証（API キー不要）
    python bot.py run        # 自動売買を開始（DRY_RUN=true の間は注文を出さない）
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import ccxt
from dotenv import load_dotenv

from strategy import crossover_signal

load_dotenv()

SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "1h")
FAST_MA = int(os.getenv("FAST_MA", "9"))
SLOW_MA = int(os.getenv("SLOW_MA", "21"))
ORDER_USDT = float(os.getenv("ORDER_USDT", "20"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() != "false"
FEE_RATE = 0.001  # Bitget 現物の標準手数料 0.1%（バックテスト用の概算）

STATE_FILE = Path(__file__).with_name("state.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(Path(__file__).with_name("bot.log"))],
)
log = logging.getLogger("bitget-bot")


def make_exchange(authenticated):
    config = {"enableRateLimit": True}
    if authenticated:
        config.update(
            apiKey=os.environ["BITGET_API_KEY"],
            secret=os.environ["BITGET_API_SECRET"],
            password=os.environ["BITGET_API_PASSPHRASE"],
        )
    return ccxt.bitget(config)


def fetch_closed_closes(exchange, limit):
    """確定済みの足の終値だけを返す（最後の足は形成中なので捨てる）。"""
    candles = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=limit + 1)
    return [c[4] for c in candles[:-1]], candles[-2][0]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"in_position": False, "amount": 0.0, "last_candle": None}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def buy(exchange, state, price):
    if DRY_RUN:
        amount = ORDER_USDT / price
        log.info("[DRY RUN] 買い %.8f %s @ %.2f", amount, SYMBOL, price)
    else:
        order = exchange.create_market_buy_order_with_cost(SYMBOL, ORDER_USDT)
        order = exchange.fetch_order(order["id"], SYMBOL)
        amount = order.get("filled") or ORDER_USDT / price
        log.info("買い注文 約定: id=%s 数量=%s", order["id"], amount)
    state.update(in_position=True, amount=amount)


def sell(exchange, state, price):
    base = SYMBOL.split("/")[0]
    amount = state["amount"]
    if DRY_RUN:
        log.info("[DRY RUN] 売り %.8f %s @ %.2f", amount, SYMBOL, price)
    else:
        # 手数料で目減りしている可能性があるので、実残高と比べて小さい方を売る
        free = exchange.fetch_balance()["free"].get(base, 0.0)
        amount = float(exchange.amount_to_precision(SYMBOL, min(amount, free)))
        order = exchange.create_market_sell_order(SYMBOL, amount)
        log.info("売り注文 送信: id=%s 数量=%s", order["id"], amount)
    state.update(in_position=False, amount=0.0)


def run():
    exchange = make_exchange(authenticated=not DRY_RUN)
    exchange.load_markets()
    state = load_state()
    log.info(
        "開始: %s %s MA(%d/%d) 1回 %.2f USDT DRY_RUN=%s ポジション=%s",
        SYMBOL, TIMEFRAME, FAST_MA, SLOW_MA, ORDER_USDT, DRY_RUN, state["in_position"],
    )

    while True:
        try:
            closes, candle_time = fetch_closed_closes(exchange, SLOW_MA + 5)
            # 同じ足で二重に判定しない
            if candle_time != state["last_candle"]:
                signal = crossover_signal(closes, FAST_MA, SLOW_MA)
                price = closes[-1]
                if signal == "buy" and not state["in_position"]:
                    buy(exchange, state, price)
                elif signal == "sell" and state["in_position"]:
                    sell(exchange, state, price)
                state["last_candle"] = candle_time
                save_state(state)
        except ccxt.NetworkError as e:
            log.warning("通信エラー（次回リトライ）: %s", e)
        except ccxt.ExchangeError as e:
            log.error("取引所エラー: %s", e)
        time.sleep(POLL_SECONDS)


def backtest_closes(closes, start_usdt=1000.0):
    """終値リストで戦略を検証し、(最終資産, 取引回数) を返す。"""
    usdt, coin, trades = start_usdt, 0.0, 0
    for i in range(SLOW_MA + 1, len(closes) + 1):
        window = closes[:i]
        signal = crossover_signal(window, FAST_MA, SLOW_MA)
        price = window[-1]
        if signal == "buy" and coin == 0:
            coin = usdt * (1 - FEE_RATE) / price
            usdt, trades = 0.0, trades + 1
        elif signal == "sell" and coin > 0:
            usdt = coin * price * (1 - FEE_RATE)
            coin, trades = 0.0, trades + 1
    return usdt + coin * closes[-1], trades


def backtest():
    exchange = make_exchange(authenticated=False)
    closes, _ = fetch_closed_closes(exchange, 1000)
    final, trades = backtest_closes(closes)
    hold = 1000.0 * closes[-1] / closes[0]
    log.info("バックテスト %s %s 足数=%d", SYMBOL, TIMEFRAME, len(closes))
    log.info("戦略: 1000 → %.2f USDT（取引 %d 回）", final, trades)
    log.info("ガチホ: 1000 → %.2f USDT", hold)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command == "backtest":
        backtest()
    elif command == "run":
        run()
    else:
        print(__doc__)
        sys.exit(1)
