"""
SessionRangeBreakoutStrategy for AEGIS Forex Agent.

Proposes trade ideas based on a breakout of the Asian session range after the London open.
This strategy is intentionally simple and is designed for ML training and robust backtesting.
It does NOT size trades, set SL/TP, or check risk—only generates directional signals.

Why use this strategy?
- The Asian session often forms a tight range, which is frequently broken after London opens.
- Breakout direction can be a strong feature for ML models and is easy to backtest.
- Simplicity ensures clean, interpretable signals for data collection and model training.
"""

from datetime import datetime, time
from .base_strategy import BaseStrategy

class SessionRangeBreakoutStrategy(BaseStrategy):
    strategy_id = "SESSION_RANGE_BREAKOUT"
    description = "Asian session range breakout after London open"

    def __init__(self, asian_start=time(0, 0), asian_end=time(6, 0), london_open=time(7, 0)):
        """
        Initialize the strategy with session times.
        Args:
            asian_start (datetime.time): Start of Asian session (UTC)
            asian_end (datetime.time): End of Asian session (UTC)
            london_open (datetime.time): Start of London session (UTC)
        """
        self.asian_start = asian_start
        self.asian_end = asian_end
        self.london_open = london_open

    def generate_signal(self, market_data):
        """
        Generate a breakout signal if price breaks the Asian session range after London open.
        Args:
            market_data: List of dicts, each representing a M15 candle with keys:
                - 'timestamp' (ISO8601 string, UTC)
                - 'symbol' (str)
                - 'close' (float)
        Returns:
            dict: Signal dict if breakout detected, else None.
        """
        if not market_data or len(market_data) < 1:
            return None

        # Parse candles and filter for Asian session
        asian_candles = []
        for candle in market_data:
            ts = datetime.fromisoformat(candle['timestamp'])
            if self.asian_start <= ts.time() < self.asian_end:
                asian_candles.append(candle)

        if not asian_candles:
            # Asian session not complete or no data
            return None

        session_high = max(c['close'] for c in asian_candles)
        session_low = min(c['close'] for c in asian_candles)

        # Find the first candle after London open
        for candle in market_data:
            ts = datetime.fromisoformat(candle['timestamp'])
            if ts.time() >= self.london_open:
                last_close = candle['close']
                symbol = candle['symbol']
                timestamp = candle['timestamp']
                breakout_distance = 0.0
                direction = None
                if last_close > session_high:
                    direction = "BUY"
                    breakout_distance = abs(last_close - session_high)
                elif last_close < session_low:
                    direction = "SELL"
                    breakout_distance = abs(last_close - session_low)
                if direction:
                    return {
                        "symbol": symbol,
                        "direction": direction,
                        "timestamp": timestamp,
                        "strategy_id": self.strategy_id,
                        "session_high": session_high,
                        "session_low": session_low,
                        "breakout_distance": breakout_distance
                    }
                break  # Only check the first London open candle
        return None
