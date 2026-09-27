"""売買ロジック（移動平均線のゴールデンクロス / デッドクロス）。

取引所には依存しない純粋な関数だけを置いているので、単体でテストやバックテストができる。
"""


def sma(values, period):
    """単純移動平均。データが足りないときは None。"""
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def crossover_signal(closes, fast, slow):
    """確定済みの終値リストから売買シグナルを返す。

    直前の足では短期線 <= 長期線 → 今回の足で短期線 > 長期線 なら "buy"（ゴールデンクロス）
    直前の足では短期線 >= 長期線 → 今回の足で短期線 < 長期線 なら "sell"（デッドクロス）
    それ以外は None。
    """
    if fast >= slow:
        raise ValueError("FAST_MA は SLOW_MA より小さくしてください")
    if len(closes) < slow + 1:
        return None

    prev_fast, prev_slow = sma(closes[:-1], fast), sma(closes[:-1], slow)
    cur_fast, cur_slow = sma(closes, fast), sma(closes, slow)

    if prev_fast <= prev_slow and cur_fast > cur_slow:
        return "buy"
    if prev_fast >= prev_slow and cur_fast < cur_slow:
        return "sell"
    return None
