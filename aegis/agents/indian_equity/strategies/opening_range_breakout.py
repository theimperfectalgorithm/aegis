"""
OpeningRangeBreakoutStrategy for AEGIS Indian Equity Agent.

Trades the breakout of the first 15-minute candle after NSE market open (9:15–9:30 AM IST).
This mirrors the SessionRangeBreakoutStrategy used in the Forex agent, keeping ML features
consistent across agents and allowing cross-agent model comparisons.

Strategy logic:
    - Formation window: 9:15–9:30 AM IST (first 15-min candle)
    - Breakout confirmation: Next candle close above the range high (BUY) or below range low (SELL)
    - Stop loss: Opposite end of the opening range
    - Take profit: Range size × TP multiplier (default 1.5×)
    - Squareoff deadline: 3:15 PM IST (mandatory for MIS/intraday)

Why this strategy?
    - NSE opening range is frequently broken in the first 30–60 minutes after open
    - Clean, rule-based signals that are easy to backtest and interpret for ML
    - Directly analogous to Forex SessionRangeBreakout for cross-agent ML consistency
"""

from datetime import datetime, time
import pytz
from .base_strategy import BaseEquityStrategy

IST = pytz.timezone("Asia/Kolkata")

OPEN_TIME = time(9, 15)       # NSE market open (IST)
RANGE_END = time(9, 30)       # End of 15-min opening range formation
SQUAREOFF_DEADLINE = time(15, 15)  # Intraday MIS squareoff cut-off


class OpeningRangeBreakoutStrategy(BaseEquityStrategy):
    """
    Opening Range Breakout strategy for NSE equities.
    Generates BUY/SELL signals on breakout of the first 15-min range after market open.
    """
    strategy_id = "OPENING_RANGE_BREAKOUT"
    description = "NSE first 15-min opening range breakout after 9:30 AM IST"

    def __init__(self, tp_multiplier: float = 1.5, sl_buffer_pct: float = 0.001):
        """
        Args:
            tp_multiplier (float): Take-profit = range size × tp_multiplier. Default 1.5.
            sl_buffer_pct (float): Extra buffer added to SL beyond the range boundary (0.1%). Default 0.001.
        """
        self.tp_multiplier = tp_multiplier
        self.sl_buffer_pct = sl_buffer_pct

    def _to_ist(self, timestamp_str: str) -> datetime:
        """Parse ISO8601 timestamp and convert to IST."""
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            # Assume IST if no tz info
            dt = IST.localize(dt)
        else:
            dt = dt.astimezone(IST)
        return dt

    def generate_signal(self, market_data: list) -> dict | None:
        """
        Generate an ORB signal from a list of OHLC candles.

        Args:
            market_data (list[dict]): Intraday OHLC candles sorted ascending by timestamp.
                Each candle: {'timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume'}

        Returns:
            dict or None: Signal dict if breakout detected, else None.
        """
        if not market_data or len(market_data) < 2:
            return None

        # --- Step 1: Build the opening range from candles within 9:15–9:30 IST ---
        range_candles = []
        post_range_candles = []

        for candle in market_data:
            dt = self._to_ist(candle["timestamp"])
            t = dt.time()
            if OPEN_TIME <= t < RANGE_END:
                range_candles.append(candle)
            elif RANGE_END <= t < SQUAREOFF_DEADLINE:
                post_range_candles.append(candle)

        if not range_candles:
            # Opening range not yet formed
            return None
        if not post_range_candles:
            # No post-range candles to check for breakout
            return None

        range_high = max(c["high"] for c in range_candles)
        range_low = min(c["low"] for c in range_candles)
        range_size = range_high - range_low

        if range_size <= 0:
            return None

        symbol = market_data[0]["symbol"]

        # --- Step 2: Check first post-range candle for breakout ---
        first_post = post_range_candles[0]
        close = first_post["close"]
        timestamp = first_post["timestamp"]

        direction = None
        entry_price = None
        stop_loss = None
        take_profit = None
        breakout_distance = 0.0

        if close > range_high:
            direction = "BUY"
            entry_price = range_high  # Enter at the breakout level
            stop_loss = range_low * (1 - self.sl_buffer_pct)
            take_profit = entry_price + (range_size * self.tp_multiplier)
            breakout_distance = close - range_high

        elif close < range_low:
            direction = "SELL"
            entry_price = range_low  # Enter at the breakout level
            stop_loss = range_high * (1 + self.sl_buffer_pct)
            take_profit = entry_price - (range_size * self.tp_multiplier)
            breakout_distance = range_low - close

        if direction is None:
            return None

        return {
            "symbol": symbol,
            "direction": direction,
            "timestamp": timestamp,
            "strategy_id": self.strategy_id,
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "range_high": round(range_high, 2),
            "range_low": round(range_low, 2),
            "range_size": round(range_size, 2),
            "breakout_distance": round(breakout_distance, 2),
            "tp_multiplier": self.tp_multiplier,
            "squareoff_deadline": SQUAREOFF_DEADLINE.isoformat(),
        }
