"""
BaseStrategy for AEGIS Indian Equity Agent strategy plug-in framework.

Defines the interface all equity strategies must follow.
Strategies generate trade signals only — no risk, sizing, or execution logic here.
This keeps strategies portable, testable, and plug-and-play with the TradeDecisionPipeline.
"""

from abc import ABC, abstractmethod


class BaseEquityStrategy(ABC):
    """
    Abstract base class for all Indian Equity trading strategies in AEGIS.
    Each strategy must define a unique strategy_id and description.
    Strategies generate trade ideas (signals) only — they never size, risk-check, or execute.
    """
    strategy_id: str
    description: str

    @abstractmethod
    def generate_signal(self, market_data):
        """
        Generate a trade signal based on market data.

        Args:
            market_data (list[dict]): List of OHLC candle dicts, each with:
                - 'timestamp' (str): ISO8601 UTC timestamp
                - 'symbol' (str): NSE symbol, e.g. 'RELIANCE', 'NIFTY 50'
                - 'open' (float)
                - 'high' (float)
                - 'low' (float)
                - 'close' (float)
                - 'volume' (int)

        Returns:
            dict or None: Signal dict if triggered, else None.
            Signal schema:
                - 'symbol' (str)
                - 'direction' (str): 'BUY' or 'SELL'
                - 'timestamp' (str)
                - 'strategy_id' (str)
                - 'entry_price' (float): Suggested entry (breakout level)
                - 'stop_loss' (float): Suggested SL price
                - 'take_profit' (float): Suggested TP price
                - additional strategy-specific keys
        """
        pass
