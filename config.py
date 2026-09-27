from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    symbol: str = "XAUUSD"
    base_tf: str = "1min"
    higher_tfs: tuple[str, ...] = ("30min", "1h", "2h", "3h", "4h", "1D", "1W")
    atr_period: int = 14
    swing_left: int = 3
    swing_right: int = 3
    min_fvg_atr: float = 0.12
    min_displacement_atr: float = 0.80
    equal_liquidity_atr: float = 0.12
    max_zone_width_atr: float = 0.40
    first_touch_only: bool = True
    confirmation_tf: str = "5min"
    min_score: float = 70.0
    spread_price: float = 0.30
    slippage_price: float = 0.10
    max_holding_bars_5m: int = 72

CFG = Config()
