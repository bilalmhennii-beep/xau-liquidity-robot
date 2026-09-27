# XAU Liquidity Robot

Research-first XAUUSD liquidity/FVG trading system for backtesting and eventual MT5 demo execution.

## Goal
Find high-quality XAUUSD setups from multi-timeframe structure and test them without look-ahead bias before enabling execution.

## Architecture
- `src/data.py` — OHLC normalization and timeframe aggregation
- `src/zones.py` — FVG/liquidity/displacement zone detection
- `src/backtest.py` — event-driven zone/trade backtester
- `src/metrics.py` — expectancy, profit factor, drawdown, MAE/MFE
- `config.py` — research parameters
- `mt5/` — MQL5 EA after research rules are frozen

## Research principles
1. Completed candles only for higher-timeframe signals.
2. No future bars used to construct a historical signal.
3. Separate zone quality from position sizing.
4. Include spread/slippage in execution tests.
5. Validate on unseen/out-of-sample periods before demo deployment.
6. Demo execution before any live deployment.

## Data format
CSV columns:
`time,open,high,low,close,volume`

Use 1-minute XAUUSD data where possible. The engine resamples it into 5m, 30m, 1H, 2H, 3H, 4H, daily and weekly bars.
