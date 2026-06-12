"""
TradeDecisionPipeline for the AEGIS system.

Coordinates the full trade decision lifecycle in a deterministic, auditable, and reusable way.
Works for live trading, data collection, and backtesting modes.
"""

class TradeDecisionPipeline:
    """
    Orchestrates the end-to-end trade decision process for any agent or mode.
    Enforces the correct order of operations and ensures every decision is logged.
    """
    def __init__(self, strategy_router, feature_engineer, inference_engine, account_calibrator, risk_manager, execution_engine, trade_logger):
        """
        The execution_engine argument can be any object implementing the ExecutionEngine interface:
        (e.g., PaperExecutionEngine, MT5ExecutionEngine, or a mock for testing).
        No code in this pipeline assumes a specific broker or MT5.
        """
        """
        Initialize the pipeline with all required components.
        Args:
            strategy_router: StrategyRouter instance
            feature_engineer: FeatureEngineer instance
            inference_engine: InferenceEngine instance
            account_calibrator: AccountCalibrator instance
            risk_manager: GlobalRiskManager or similar
            execution_engine: ExecutionEngine instance
            trade_logger: TradeLogger instance
        """
        self.strategy_router = strategy_router
        self.feature_engineer = feature_engineer
        self.inference_engine = inference_engine
        self.account_calibrator = account_calibrator
        self.risk_manager = risk_manager
        self.execution_engine = execution_engine
        self.trade_logger = trade_logger

    def process_market_data(self, market_data, agent_name):
        """
        Process incoming market data and coordinate the full trade decision pipeline.
        Args:
            market_data: Market data input for the pipeline
            agent_name: Name of the agent invoking the pipeline
        """
        # 1. Collect signals from StrategyRouter
        signals = self.strategy_router.collect_signals(market_data)

        # 2. For each signal, process through the pipeline
        for signal in signals:
            # a. Build ML features
            features = self.feature_engineer.build_features(market_data, signal)

            # b. Get ML raw score
            ml_raw_score = self.inference_engine.score_trade(market_data, signal)

            # c. Calibrate score per account (mode-aware)
            account_profile = signal.account_profile  # Assumed attribute
            trading_mode = signal.trading_mode  # Assumed attribute
            trading_mode_config = signal.trading_mode_config  # Assumed attribute
            ml_calibrated_score = self.account_calibrator.calibrate_score(
                ml_raw_score, account_profile, trading_mode, trading_mode_config
            )

            # d. Ask Risk Engine if trade is allowed
            is_allowed = self.risk_manager.evaluate_trade_risk(
                agent_name, signal.account_id, signal.trade_context, trading_mode
            )

            # e. If allowed, send to ExecutionEngine (broker-agnostic)
            if is_allowed:
                # Order is sent to the provided execution engine (paper, MT5, etc.)
                self.execution_engine.place_trade(signal.account_id, signal.order)
                decision = 'approved'
                reason = 'Risk checks passed'
            else:
                decision = 'rejected'
                reason = 'Risk engine rejected trade'

            # f. Log every decision (approved or rejected)
            self.trade_logger.log_trade_decision(
                timestamp=signal.timestamp,
                agent_name=agent_name,
                account_id=signal.account_id,
                market=signal.market,
                symbol=signal.symbol,
                strategy_id=signal.strategy_id,
                features_snapshot=features,
                ml_raw_score=ml_raw_score,
                ml_calibrated_score=ml_calibrated_score,
                risk_decision=decision,
                trade_parameters=signal.trade_parameters,
                decision_reason=reason
            )
