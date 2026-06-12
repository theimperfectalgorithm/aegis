"""
StrategyRegistry for AEGIS Indian Equity Agent.

Manages registration and activation of equity trading strategies.
Mirrors the Forex StrategyRegistry pattern for cross-agent consistency.
"""

from .opening_range_breakout import OpeningRangeBreakoutStrategy


class EquityStrategyRegistry:
    """
    Registry for all available Indian Equity trading strategies.
    Supports dynamic registration and config-driven activation.
    """

    def __init__(self):
        """
        Initialize the registry and register all available strategies.
        Active strategies are empty by default — call load_from_config() to enable.
        """
        self._strategies = {}       # strategy_id -> instance
        self._active_strategies = []

        # Register all available strategies
        self._register(OpeningRangeBreakoutStrategy())

    def _register(self, strategy_instance):
        """Register a strategy instance by its strategy_id."""
        sid = getattr(strategy_instance, "strategy_id", None)
        if sid is None:
            raise ValueError(f"Strategy {strategy_instance} has no strategy_id")
        self._strategies[sid] = strategy_instance

    def get_active_strategies(self):
        """Return list of currently active strategy instances."""
        return self._active_strategies

    def get_all_strategy_ids(self):
        """Return all registered strategy IDs."""
        return list(self._strategies.keys())

    def load_from_config(self, config: dict):
        """
        Activate strategies listed in config.

        Args:
            config (dict): e.g. {"enabled_strategies": ["OPENING_RANGE_BREAKOUT"]}
        """
        enabled = set(config.get("enabled_strategies", []))
        self._active_strategies = [
            s for sid, s in self._strategies.items() if sid in enabled
        ]

    def enable_strategy(self, strategy_id: str):
        """Programmatically enable a strategy by ID."""
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy '{strategy_id}' not registered.")
        s = self._strategies[strategy_id]
        if s not in self._active_strategies:
            self._active_strategies.append(s)

    def disable_strategy(self, strategy_id: str):
        """Programmatically disable a strategy by ID."""
        self._active_strategies = [
            s for s in self._active_strategies
            if getattr(s, "strategy_id", None) != strategy_id
        ]
