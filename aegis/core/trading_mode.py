"""
Trading mode framework for the AEGIS system.

Defines trading modes (LIVE_FUND, DATA_COLLECTION) and configuration for mode-specific controls.
Allows the system to distinguish between live trading and data collection for ML.
"""

from enum import Enum, auto
from dataclasses import dataclass

class TradingMode(Enum):
    """
    Enum representing the trading mode for an account or agent.
    LIVE_FUND: Real-money trading with full risk controls.
    DATA_COLLECTION: Simulated or shadow trading for ML data gathering and strategy evaluation.
    """
    LIVE_FUND = auto()
    DATA_COLLECTION = auto()

@dataclass
class TradingModeConfig:
    """
    Configuration for trading mode controls and overrides.
    max_trades_per_day (int): Maximum trades allowed per day in this mode.
    max_daily_loss_override (float): Override for daily loss limit (if any) in this mode.
    ml_confidence_threshold (float): ML model confidence threshold for trade approval.
    allow_experimental_strategies (bool): Whether experimental strategies are allowed in this mode.
    label_for_logging (str): Label to tag all logs/trades for this mode (e.g., 'live', 'data-collection').
    """
    max_trades_per_day: int
    max_daily_loss_override: float
    ml_confidence_threshold: float
    allow_experimental_strategies: bool
    label_for_logging: str
