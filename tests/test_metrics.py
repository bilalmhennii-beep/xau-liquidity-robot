"""Regression tests for account-level realized drawdown in R units."""

import unittest

import pandas as pd

from src.metrics import summarize


class MetricsTests(unittest.TestCase):
    def trades(self, rs, exits=None):
        rows = {"r": rs}
        if exits is not None:
            rows["exit"] = pd.to_datetime(exits, utc=True)
        return pd.DataFrame(rows)

    def test_initial_loss_is_counted_from_zero_equity(self):
        result = summarize(self.trades([-1.0, 2.0]))
        self.assertEqual(result["trades"], 2)
        self.assertAlmostEqual(result["max_drawdown_r"], -1.0)
        self.assertAlmostEqual(result["net_r"], 1.0)

    def test_realized_drawdown_uses_exit_order_not_signal_order(self):
        # Rows are in signal order; realized P&L is +4, -3, -2.
        trades = self.trades(
            [-3.0, 4.0, -2.0],
            ["2026-01-01 12:00", "2026-01-01 11:00", "2026-01-01 13:00"],
        )
        result = summarize(trades)
        self.assertAlmostEqual(result["net_r"], -1.0)
        self.assertAlmostEqual(result["max_drawdown_r"], -5.0)

    def test_simultaneous_exits_form_one_equity_event(self):
        # There is no known order between exits at the same timestamp.
        trades = self.trades(
            [5.0, -7.0],
            ["2026-01-01 11:00", "2026-01-01 11:00"],
        )
        result = summarize(trades)
        self.assertAlmostEqual(result["max_drawdown_r"], -2.0)

    def test_all_winners_have_zero_drawdown(self):
        result = summarize(self.trades([1.0, 2.0, 0.5]))
        self.assertAlmostEqual(result["max_drawdown_r"], 0.0)
        self.assertAlmostEqual(result["win_rate"], 1.0)

    def test_empty_trades(self):
        self.assertEqual(summarize(pd.DataFrame()), {"trades": 0})


if __name__ == "__main__":
    unittest.main()
