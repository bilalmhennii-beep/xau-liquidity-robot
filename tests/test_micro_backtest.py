import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src import micro_backtest


class MicroBacktestTests(unittest.TestCase):
    def run_one(self, side, next_low, next_high, next_close):
        idx = pd.date_range("2026-01-01", periods=2, freq="min")
        bars = pd.DataFrame(
            {
                "open": [100.0, 100.0],
                "high": [102.0, next_high],
                "low": [98.0, next_low],
                "close": [100.0, next_close],
            },
            index=idx,
        )
        zone = SimpleNamespace(
            score=75, created=idx[0], key=100.0,
            side=side, tf="1h", kind="test",
        )
        captured = io.StringIO()
        with patch.object(micro_backtest, "load_ohlc", return_value=bars), \
             patch.object(micro_backtest, "build_timeframes", return_value={"1m": bars}), \
             patch.object(micro_backtest, "build_zones", return_value=[zone]), \
             patch.object(pd.DataFrame, "to_csv"), \
             contextlib.redirect_stdout(captured):
            result = micro_backtest.run_micro("unused.csv")
        return result, captured.getvalue()

    def test_buy_pnl_and_no_entry_bar_stop(self):
        # The entry/touch candle spans both SL and TP; it must not be used for exit.
        trades, _ = self.run_one("BUY", 100.1, 101.5, 101.0)
        self.assertEqual(int(trades.iloc[0].outcome), 1)
        self.assertAlmostEqual(float(trades.iloc[0].pnl_usd), 95.0)

    def test_sell_pnl_direction(self):
        trades, _ = self.run_one("SELL", 98.5, 99.9, 99.0)
        self.assertEqual(int(trades.iloc[0].outcome), 1)
        self.assertAlmostEqual(float(trades.iloc[0].pnl_usd), 95.0)

    def test_time_exit_included_in_win_rate(self):
        trades, printed = self.run_one("BUY", 100.1, 100.6, 100.2)
        self.assertEqual(int(trades.iloc[0].outcome), 0)
        self.assertGreater(float(trades.iloc[0].pnl_usd), 0)
        self.assertIn("'win_rate': 1.0", printed)

    def test_initial_loss_counts_as_drawdown(self):
        trades, printed = self.run_one("BUY", 98.5, 100.2, 99.0)
        self.assertEqual(int(trades.iloc[0].outcome), -1)
        self.assertLess(float(trades.iloc[0].pnl_usd), 0)
        self.assertIn("'max_drawdown_usd': -", printed)


if __name__ == "__main__":
    unittest.main()
