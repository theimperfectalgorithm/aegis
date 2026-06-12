"""
BaseStrategy for AEGIS Forex Agent strategy plug-in framework.

Defines the interface and contract all trading strategies must follow.
Strategies generate trade ideas (signals), not trades. No risk, ML, or execution logic is allowed here.
This ensures strategies are portable, testable, and can be plugged in without modifying core logic.
"""

from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    """
    Abstract base class for all Forex trading strategies in AEGIS.
    Each strategy must define a unique strategy_id and description.
    Strategies generate trade ideas (signals) only.
    """
    strategy_id: str
    description: str

    @abstractmethod
    def generate_signal(self, market_data):
        """
        Generate a trade signal based on market data.
        Args:
            market_data: Market data input for the strategy.
        Returns:
            Standardized signal object or None if no signal.
        TODO: Define the signal object schema elsewhere in the system.
        """
        pass
