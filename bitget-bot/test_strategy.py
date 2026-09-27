import unittest

from strategy import crossover_signal, sma


class StrategyTest(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4], 2), 3.5)
        self.assertIsNone(sma([1], 2))

    def test_golden_cross(self):
        closes = [10, 10, 10, 10, 10, 9, 8, 7, 20]
        self.assertEqual(crossover_signal(closes, 2, 4), "buy")

    def test_dead_cross(self):
        closes = [10, 10, 10, 10, 10, 11, 12, 13, 1]
        self.assertEqual(crossover_signal(closes, 2, 4), "sell")

    def test_no_signal(self):
        self.assertIsNone(crossover_signal([10] * 10, 2, 4))
        self.assertIsNone(crossover_signal([1, 2], 2, 4))

    def test_invalid_periods(self):
        with self.assertRaises(ValueError):
            crossover_signal([1] * 30, 5, 5)


if __name__ == "__main__":
    unittest.main()
