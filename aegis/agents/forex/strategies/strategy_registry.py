"""
StrategyRegistry for AEGIS Forex Agent strategy plug-in framework.

Manages registration and activation of available strategies.
Allows enabling/disabling strategies via config for flexible deployment.
"""

from .session_range_breakout import SessionRangeBreakoutStrategy

class StrategyRegistry:
    """
    Registry for all available Forex trading strategies.
    Enables dynamic registration and activation of strategies for backtesting and live trading.
    By default, registers SessionRangeBreakoutStrategy, which can be enabled/disabled via config.
    """
    def __init__(self):
        """
        Initialize the registry and active strategy list.
        TODO: Add config-driven activation and persistence if needed.
        """
        self._strategies = []
        self._active_strategies = []
        # Register default strategies
        self.register_strategy(SessionRangeBreakoutStrategy())

    def register_strategy(self, strategy_instance):
        """
        Register a new strategy instance.
        Args:
            strategy_instance: Instance of a class derived from BaseStrategy.
        """
        self._strategies.append(strategy_instance)

    def get_active_strategies(self):
        """
        Return a list of currently active strategy instances.
        Returns:
            List of active strategy instances.
        """
        return self._active_strategies

    def load_from_config(self, config):
        """
        Enable/disable strategies based on configuration.
        Args:
            config: Configuration dict specifying enabled strategies.
        Example config:
            {"enabled_strategies": ["SESSION_RANGE_BREAKOUT"]}
        """
        enabled = set(config.get("enabled_strategies", []))
        self._active_strategies = [s for s in self._strategies if getattr(s, "strategy_id", None) in enabled]
