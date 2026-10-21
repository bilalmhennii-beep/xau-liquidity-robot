import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.orb_m5 import Settings, backtest, load_bars, summarize


def fixture(day="2026-07-06", side=1, spread=0):
    idx = pd.date_range(day + " 09:30", periods=91, freq="min", tz="America/New_York").tz_convert("UTC")
    d = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5,
                      "close": 100.0, "spread_price": float(spread)}, index=idx)
    d.iloc[0, d.columns.get_loc("high")] = 101
    d.iloc[0, d.columns.get_loc("low")] = 99
    price = 102 if side == 1 else 98
    d.loc[idx[9], ["high", "low", "close"]] = [max(100.5, price), min(99.5, price), price]
    d.loc[idx[10]:, ["open", "high", "low", "close"]] = [price, price + .5, price - .5, price]
    return d


class OrbTests(unittest.TestCase):
    def trade(self, d, cfg=Settings(), day="2026-07-06"):
        t, audit = backtest(d, [day], cfg)
        self.assertEqual(audit[0]["status"], "traded")
        self.assertEqual(len(t), 1)
        return t.iloc[0]

    def test_buy_waits_for_m5_close_and_next_open(self):
        d = fixture()
        d.loc[d.index[10], ["open", "high"]] = [103, 103.5]
        t = self.trade(d)
        self.assertEqual(t.entry_time, str(d.index[10]))
        self.assertEqual(t.entry, 103)
        self.assertEqual(t.stop, 99)
        self.assertEqual(t.target, 111)

    def test_wick_and_m1_close_are_not_signals(self):
        d = fixture()
        d.loc[d.index[5]:, ["open", "high", "low", "close"]] = [100, 103, 99.5, 100]
        d.loc[d.index[6], "close"] = 102  # an M1 close, not an M5 close
        t, audit = backtest(d, ["2026-07-06"], Settings())
        self.assertTrue(t.empty)
        self.assertEqual(audit[0]["status"], "no_breakout")

    def test_close_exactly_on_boundary_is_not_breakout(self):
        d = fixture()
        d.loc[d.index[5]:, ["open", "high", "low", "close"]] = [100, 101, 99.5, 101]
        self.assertTrue(backtest(d, ["2026-07-06"], Settings())[0].empty)

    def test_sell_uses_ask_for_exit(self):
        d = fixture(side=-1, spread=.2)
        t = self.trade(d, Settings(slippage_price=.1, commission_price=.1))
        self.assertEqual(t.side, "SELL")
        self.assertAlmostEqual(t.entry, 97.9)
        self.assertAlmostEqual(t.exit, 98.3)
        self.assertAlmostEqual(t.net_r, -.5 / 3.1)

    def test_buy_costs_on_time_exit(self):
        t = self.trade(fixture(spread=.2), Settings(slippage_price=.1, commission_price=.1))
        self.assertAlmostEqual(t.entry, 102.3)
        self.assertAlmostEqual(t.exit, 101.9)
        self.assertAlmostEqual(t.net_r, -.5 / 3.3)
        self.assertEqual(t.reason, "TIME")

    def test_ambiguous_bar_is_stop_first(self):
        d = fixture()
        d.loc[d.index[10], ["high", "low"]] = [109, 98]
        t = self.trade(d)
        self.assertEqual(t.reason, "SL")
        self.assertAlmostEqual(t.net_r, -1)

    def test_stop_gap_fills_at_open(self):
        d = fixture()
        d.loc[d.index[11], ["open", "high", "low", "close"]] = [97, 98, 96, 97]
        t = self.trade(d, Settings(slippage_price=.1))
        self.assertEqual(t.reason, "SL_GAP")
        self.assertAlmostEqual(t.exit, 96.9)

    def test_target_limit_and_one_trade(self):
        d = fixture()
        d.loc[d.index[12], "high"] = 109
        t = self.trade(d)
        self.assertEqual(t.reason, "TP")
        self.assertAlmostEqual(t.net_r, 2)

    def test_entry_gap_through_stop_is_skipped(self):
        d = fixture()
        d.loc[d.index[10], ["open", "high", "low", "close"]] = [98, 98.5, 97, 98]
        t, audit = backtest(d, ["2026-07-06"], Settings())
        self.assertTrue(t.empty)
        self.assertEqual(audit[0]["status"], "entry_gap_through_stop")

    def test_missing_minute_is_audited(self):
        d = fixture().drop(fixture().index[3])
        t, audit = backtest(d, ["2026-07-06"], Settings())
        self.assertTrue(t.empty)
        self.assertEqual(audit[0]["status"], "incomplete_0930_1100")

    def test_no_entry_at_cutoff(self):
        d = fixture()
        d.loc[d.index[5]:, ["open", "high", "low", "close"]] = [100, 100.5, 99.5, 100]
        d.loc[d.index[59], ["high", "close"]] = [102, 102]
        self.assertTrue(backtest(d, ["2026-07-06"], Settings())[0].empty)

    def test_dst_changes_utc_not_ny_entry(self):
        for day, hour in [("2026-03-06", 14), ("2026-03-09", 13),
                          ("2026-10-30", 13), ("2026-11-02", 14)]:
            t = self.trade(fixture(day), day=day)
            self.assertEqual(pd.Timestamp(t.entry_time).hour, hour)
            self.assertEqual(pd.Timestamp(t.entry_time).minute, 40)

    def test_only_calendar_sessions_are_used(self):
        d = pd.concat([fixture("2026-07-03"), fixture()])
        t, audit = backtest(d, ["2026-07-06"], Settings())
        self.assertEqual(len(t), 1)
        self.assertEqual(len(audit), 1)

    def test_drawdown_includes_first_loss(self):
        d = pd.DataFrame({"exit_bar_time": ["2026-07-06", "2026-07-07"], "net_r": [-1., 2.]})
        self.assertEqual(summarize(d)["max_drawdown_r"], -1)

    def test_rejects_naive_input_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bars.csv"
            d = fixture()
            d.index = d.index.tz_localize(None)
            d.to_csv(path, index_label="time")
            with self.assertRaises(ValueError):
                load_bars(path)
        with self.assertRaises(ValueError):
            backtest(pd.concat([fixture(), fixture()]).sort_index(), ["2026-07-06"], Settings())

    def test_cost_stress_reduces_same_time_exit_result(self):
        d = fixture(spread=.2)
        normal = self.trade(d).net_r
        stressed = self.trade(d, Settings(slippage_price=.2, spread_multiplier=2)).net_r
        self.assertLess(stressed, normal)


if __name__ == "__main__":
    unittest.main()
