"""
Indian Equity Agent for AEGIS.

Manages NSE intraday equity trading using the Opening Range Breakout strategy.
Integrates with the shared TradeDecisionPipeline, GlobalRiskManager, and TradeLogger
for full auditability and ML-readiness.

Instrument scope: NSE Nifty 50 universe, Intraday MIS (margin intraday square-off)
Broker: Zerodha Kite Connect
Strategy: Opening Range Breakout (9:15–9:30 AM IST range, breakout after 9:30 AM)

Design notes:
    - Mirrors ForexAgent structure for cross-agent consistency
    - Broker-agnostic at this layer: accepts any BaseExecutionEngine
    - All trade decisions pass through the shared TradeDecisionPipeline
    - MIS squareoff is enforced at 3:15 PM IST
"""

import logging
import uuid
from datetime import datetime
import pytz

from aegis.core.trade_pipeline import TradeDecisionPipeline
from aegis.agents.indian_equity.strategies.strategy_registry import EquityStrategyRegistry
from aegis.agents.indian_equity.account_manager import EquityAccountManager, EquityPosition
from aegis.core.risk.global_risk_manager import GlobalRiskManager
from aegis.core.logging.trade_logger import TradeLogger

IST = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger("AEGIS.EquityAgent")


class EquityStrategyRouter:
    """
    Thin router that wraps EquityStrategyRegistry for use with TradeDecisionPipeline.
    Collects signals from all active strategies given market data.
    """

    def __init__(self, config: dict = None):
        self.registry = EquityStrategyRegistry()
        if config:
            self.registry.load_from_config(config)
        else:
            # Default: enable ORB
            self.registry.enable_strategy("OPENING_RANGE_BREAKOUT")

    def collect_signals(self, market_data: list) -> list:
        """
        Collect signals from all active strategies.

        Returns:
            list[dict]: Raw signal dicts from strategies.
        """
        signals = []
        for strategy in self.registry.get_active_strategies():
            signal = strategy.generate_signal(market_data)
            if signal is not None:
                signals.append(signal)
        return signals


class EquityAgent:
    """
    AEGIS Indian Equity Agent.

    Coordinates NSE intraday trading:
        1. Fetches or receives intraday OHLC market data
        2. Runs strategies to collect signals (via EquityStrategyRouter)
        3. Passes each signal through ML scoring → risk check → execution
        4. Logs every decision for ML training and audit
        5. Enforces MIS squareoff at 3:15 PM IST

    Usage:
        agent = EquityAgent(
            account_id="NSE001",
            capital=500000,
            execution_engine=KitePaperExecutionEngine(),
        )
        agent.process_market_data(candles)
        agent.run_squareoff_check()   # call periodically near market close
    """

    def __init__(
        self,
        account_id: str = "NSE001",
        capital: float = 500_000,
        execution_engine=None,
        risk_manager: GlobalRiskManager = None,
        strategy_config: dict = None,
        trade_logger: TradeLogger = None,
        max_daily_trades: int = 5,
        max_daily_loss_pct: float = 0.02,
        risk_profile: str = "balanced",
    ):
        """
        Args:
            account_id (str): NSE account identifier.
            capital (float): Trading capital in INR.
            execution_engine: Any BaseExecutionEngine (paper or live Kite).
            risk_manager (GlobalRiskManager): Shared risk manager. Creates default if None.
            strategy_config (dict): Strategy activation config. Defaults to ORB enabled.
            trade_logger (TradeLogger): Shared trade logger. Creates new if None.
            max_daily_trades (int): Daily trade cap. Default 5.
            max_daily_loss_pct (float): Daily loss limit as fraction of capital. Default 2%.
            risk_profile (str): Risk profile for this account ('conservative'|'balanced'|'aggressive').
        """
        self.account_id = account_id
        self.capital = capital
        self.risk_profile = risk_profile

        # Core components
        self.account_manager = EquityAccountManager(
            account_id=account_id,
            capital=capital,
            max_daily_trades=max_daily_trades,
            max_daily_loss_pct=max_daily_loss_pct,
        )
        self.strategy_router = EquityStrategyRouter(config=strategy_config)
        self.risk_manager = risk_manager or GlobalRiskManager()
        self.execution_engine = execution_engine
        self.trade_logger = trade_logger or TradeLogger()

        logger.info(
            f"EquityAgent initialized | account={account_id} | capital=₹{capital:,.0f} | "
            f"profile={risk_profile} | max_trades={max_daily_trades}"
        )

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def process_market_data(self, market_data: list):
        """
        Process a batch of intraday OHLC candles through the full trade pipeline.

        For each signal generated by active strategies:
            1. Build trade context for risk evaluation
            2. Check daily limits via account manager
            3. Evaluate risk via GlobalRiskManager
            4. Execute via execution engine (if approved)
            5. Register position in account manager
            6. Log every decision

        Args:
            market_data (list[dict]): Sorted ascending OHLC candles for one symbol.
        """
        if not market_data:
            return

        # Squareoff check first — never take new trades if deadline passed
        if self.account_manager.is_squareoff_required():
            logger.info(f"[{self.account_id}] Squareoff deadline reached — no new trades.")
            self.run_squareoff_check(market_data)
            return

        signals = self.strategy_router.collect_signals(market_data)
        if not signals:
            return

        for signal in signals:
            self._process_signal(signal, market_data)

    def _process_signal(self, signal: dict, market_data: list):
        """Process a single strategy signal through the full pipeline."""
        symbol = signal.get("symbol", "UNKNOWN")
        timestamp = signal.get("timestamp", datetime.now(IST).isoformat())
        strategy_id = signal.get("strategy_id", "UNKNOWN")

        # --- Daily limit check ---
        can_trade, reason = self.account_manager.can_trade()
        if not can_trade:
            logger.info(f"[{self.account_id}] Trade blocked (daily limits): {reason}")
            self._log_decision(
                signal=signal,
                features={},
                ml_raw_score=0.0,
                ml_calibrated_score=0.0,
                decision="rejected",
                reason=reason,
                trade_params={},
            )
            return

        # --- Build trade context for risk engine ---
        entry_price = signal.get("entry_price", 0.0)
        stop_loss = signal.get("stop_loss", 0.0)
        stop_loss_distance = abs(entry_price - stop_loss) if entry_price and stop_loss else 0.0

        trade_context = {
            "account_equity": self.capital,
            "risk_profile": self.risk_profile,
            "stop_loss_distance": stop_loss_distance,
            "market": "equity",
            "exposure": 0.0,   # Will be calculated from position size
        }

        # --- Risk evaluation ---
        risk_result = self.risk_manager.evaluate_trade_risk(
            agent_name="equity",
            account_id=self.account_id,
            trade_context=trade_context,
            trading_mode="DATA_COLLECTION",  # Default safe mode; switch to LIVE_FUND when ready
        )

        position_size = risk_result.get("position_size", 0.0)

        # Convert position size (INR) to share quantity
        quantity = int(position_size / entry_price) if entry_price > 0 else 0

        # Build ML features snapshot (mirrors Forex ORB features for cross-agent ML)
        features = {
            "breakout_distance": signal.get("breakout_distance", 0.0),
            "range_size": signal.get("range_size", 0.0),
            "hour_of_day": datetime.fromisoformat(timestamp).hour if timestamp else 9,
            "symbol": symbol,
            "direction": signal.get("direction", ""),
        }

        # ML scoring — v1: pass-through score (no model trained yet for equity)
        # This slot is ready for InferenceEngine once equity trade logs accumulate
        ml_raw_score = 0.5
        ml_calibrated_score = 0.5

        # Build order
        order = {
            "symbol": symbol,
            "side": signal.get("direction", "BUY").lower(),
            "price": entry_price,
            "quantity": quantity,
            "stop_loss": signal.get("stop_loss"),
            "take_profit": signal.get("take_profit"),
            "timestamp": timestamp,
            "product": "MIS",   # Zerodha intraday product type
            "exchange": "NSE",
        }
        trade_params = {**order, "risk_amount": risk_result.get("risk_amount", 0.0)}

        if not risk_result.get("allowed") or quantity <= 0:
            rejection_reason = risk_result.get("rejection_reason") or "Zero quantity calculated"
            logger.info(f"[{self.account_id}] Trade rejected: {rejection_reason}")
            self._log_decision(signal, features, ml_raw_score, ml_calibrated_score, "rejected", rejection_reason, trade_params)
            return

        # --- Execute trade ---
        if self.execution_engine is None:
            logger.warning(f"[{self.account_id}] No execution engine configured — skipping execution.")
            self._log_decision(signal, features, ml_raw_score, ml_calibrated_score, "rejected", "No execution engine", trade_params)
            return

        fill = self.execution_engine.place_trade(self.account_id, order)
        trade_id = fill.get("trade_id", str(uuid.uuid4()))

        # Register position in account manager
        position = EquityPosition(
            trade_id=trade_id,
            symbol=symbol,
            direction=signal.get("direction", "BUY"),
            entry_price=fill.get("entry_price", entry_price),
            quantity=quantity,
            stop_loss=signal.get("stop_loss", 0.0),
            take_profit=signal.get("take_profit", 0.0),
            open_time=timestamp,
            strategy_id=strategy_id,
        )
        self.account_manager.add_position(position)

        self._log_decision(signal, features, ml_raw_score, ml_calibrated_score, "approved", "All checks passed", trade_params)
        logger.info(f"[{self.account_id}] Trade placed: {symbol} {signal.get('direction')} qty={quantity} @ ₹{entry_price}")

    # ------------------------------------------------------------------ #
    # Squareoff
    # ------------------------------------------------------------------ #

    def run_squareoff_check(self, market_data: list = None):
        """
        Check if MIS squareoff deadline has passed and close all open positions.

        Args:
            market_data (list[dict]): Used to get last known price for PnL calculation.
                                      If None, positions are closed at entry price (paper).
        """
        if not self.account_manager.is_squareoff_required():
            return

        open_positions = self.account_manager.get_open_positions()
        if not open_positions:
            return

        logger.info(f"[{self.account_id}] Squareoff triggered for {len(open_positions)} position(s).")

        # Build last price lookup from market data
        last_prices = {}
        if market_data:
            for candle in market_data:
                last_prices[candle.get("symbol")] = candle.get("close", 0.0)

        close_time = datetime.now(IST).isoformat()

        for pos_dict in open_positions:
            trade_id = pos_dict["trade_id"]
            symbol = pos_dict["symbol"]
            close_price = last_prices.get(symbol, pos_dict["entry_price"])

            if self.execution_engine:
                self.execution_engine.close_trade(self.account_id, trade_id, close_price, close_time)

            closed = self.account_manager.close_position(trade_id, close_price, close_time)
            if closed:
                logger.info(f"[{self.account_id}] Squareoff: {symbol} PnL=₹{closed['pnl']:,.2f}")

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def report_status(self) -> dict:
        """
        Return account summary for reporting to the Main Orchestrator.
        """
        summary = self.account_manager.get_account_summary()
        summary["agent"] = "indian_equity"
        summary["risk_profile"] = self.risk_profile
        return summary

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _log_decision(self, signal, features, ml_raw_score, ml_calibrated_score, decision, reason, trade_params):
        """Log a trade decision to the shared TradeLogger."""
        self.trade_logger.log_trade_decision(
            timestamp=signal.get("timestamp", datetime.now(IST).isoformat()),
            agent_name="equity",
            account_id=self.account_id,
            market="equity",
            symbol=signal.get("symbol", ""),
            strategy_id=signal.get("strategy_id", ""),
            features_snapshot=features,
            ml_raw_score=ml_raw_score,
            ml_calibrated_score=ml_calibrated_score,
            risk_decision=decision,
            trade_parameters=trade_params,
            decision_reason=reason,
        )
