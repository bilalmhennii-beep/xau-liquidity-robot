# NAS100 / S&P 500 M5 opening-range research

Status: research implementation, not an MT5 Expert Advisor. No order routing,
credentials, live connection or performance claim. Intended feed: PU Prime MT5
index CFDs. Exact account symbol names and contract specifications remain unverified.

## Frozen entry rule

- Use New York local time (America/New_York), including US daylight saving.
- Freeze high/low of the completed 09:30-09:35 M5 candle.
- A subsequent M5 close strictly above the high signals BUY; strictly below the
  low signals SELL. Wicks and intermediate M1 closes do not trigger signals.
- Enter at the next M1 bar open, adjusted for bid/ask and adverse slippage.
  Earliest entry is 09:40 NY. M1 is execution data, never a signal timeframe.

The following are initial research defaults, not user-verified optimum settings:
stop at the opposite range boundary; target 2R (test 1.5R separately); entries
strictly before 10:30; force exit at 11:00; one trade per symbol per cash session.
No retest requirement, averaging down, trailing stop or re-entry.

## Data required

One CSV per exact broker symbol, with columns:
`time,open,high,low,close,spread_price`.

OHLC must be M1 BID prices. Time is the bar-open timestamp, either Unix seconds
representing verified UTC or ISO timestamps containing an explicit offset.
Do not label a broker-server clock as UTC without checking its historical offset
and daylight-saving convention. Manually compare several winter/summer opening
candles with MT5. Naive timestamps and duplicates are rejected.

`spread_price` is the historical spread in index-price units, not pips or lots.
If MT5 reports spread in points, multiply by that symbol's point size. Zero
spreads are accepted for synthetic tests but must be investigated in real data.
Do not replace missing spreads with zero. OHLC ask prices for shorts are
approximated by bid OHLC plus the M1 spread; tick replay is required later.

Also provide a separate CSV with a `date` column listing verified US cash-session
dates (YYYY-MM-DD), excluding full holidays, covering the desired test interval.
The engine does not infer holidays from CFD trading activity. Every requested
session requires all 91 M1 bars from 09:30 through 11:00 inclusive; missing
sessions are listed in the audit and never silently filled. This strict rule
can exclude valid low-activity minutes; review exclusions before interpreting results.

Get the history through the logged-in PU Prime MT5 terminal or its supported
history export. Do not send passwords. Broker symbol, point/tick size, tick value,
contract size, minimum lot/lot step, commissions and minimum stop distance are
needed before building a lot-sized execution adapter. They are not guessed here.

## Run

Install the repository requirements. From the repository root:

```bash
python -m unittest discover -s tests -p 'test_orb_m5.py' -v
python -m src.orb_m5 data/INDEX_M1_UTC.csv \
  --symbol EXACT_BROKER_SYMBOL --sessions data/us_cash_sessions.csv \
  --reward-r 2 --slippage-price 1 --commission-price 0 \
  --spread-multiplier 1 \
  --validation-start 2025-01-01 --test-start 2026-01-01 \
  --out results/orb_SYMBOL_2r_base
```

The numeric costs and dates above are syntax examples, NOT PU Prime cost estimates.
Set them from the actual symbol/feed. Commission is round-trip cost expressed in
price units per unit exposure. The CSV itself supplies historical spread.
Repeat separately per index and for 1.5R/2R and predeclared spread/slippage stress
scenarios. Use a new output directory each time; overwrites are refused.

Outputs: `trades.csv`, `session_audit.csv`, and `summary.json`. The summary records
data/calendar/engine SHA256 hashes, dependency versions, parameters and separate
train/validation/test metrics. Set chronological boundaries BEFORE comparing
settings; merely labeling a period test does not make it unseen. No parameters
are selected automatically. Do not tune on the final holdout.

## Execution and reporting limits

- BUY entry pays ask; SELL entry receives bid. BUY exits use bid; SELL exits use
  approximated ask. Adverse slippage applies to market entries, stops and time
  exits. Targets are modeled as resting limits without favorable gap improvement.
- If the entry gaps through the stop, the session is skipped. Adverse stop gaps
  fill at opening quote, not the unavailable stop price. When both SL and TP are
  touched within one M1 bar, stop wins unless the bar opens beyond target first.
- Entry-bar exits are allowed: entry occurs at that bar's open, before its range.
- Exit timestamps identify the M1 bar, not an exact intrabar tick.
- R uses entry-to-stop price distance; commission/slippage can make losses exceed
  1R. Realized drawdown starts at zero R and follows exit order.
- There is no compounded account simulation, margin/lot rounding, open-equity
  drawdown, funding, minimum-stop-distance check or cross-symbol risk allocation.
  Results from the two symbols must not be summed as an executable portfolio.
- The terminal and broker feed have not been accessed or validated. No historical
  PU Prime run has been performed. Synthetic unit tests are not profitability evidence.

## Before MT5 demo execution

Verify feed/timezone/specifications; inspect skipped sessions; run fixed-rule
baseline and cost stress tests on a hashed dataset; reserve a genuine holdout.
Then add broker lot rounding, margin/stop checks and a shared risk cap across both
symbols. Reconcile signals and fills against MT5 real-tick Strategy Tester before
enabling any demo orders. Preserve the existing V3 and research fixes independently.
