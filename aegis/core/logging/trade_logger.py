"""
Trade Logger for AEGIS Core Logging.
Logs all trade executions and related events.

This module defines the TradeLogger class, responsible for logging every trade decision
(approved or rejected) and producing ML-ready structured records.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict

@dataclass
class TradeLogRecord:
	"""
	Schema for a single trade decision log entry.
	All fields are designed for ML training, audit, and cross-agent consistency.
	"""
	timestamp: str  # ISO8601 timestamp of the decision
	agent_name: str  # Which agent made the decision (e.g., 'forex', 'equity')
	account_id: str  # Unique account identifier
	market: str  # Market type (e.g., 'forex', 'equity', 'commodity')
	symbol: str  # Instrument symbol (e.g., 'EURUSD', 'RELIANCE')
	strategy_id: str  # Strategy identifier for traceability
	features_snapshot: Dict[str, Any]  # Features used for ML/model decision
	ml_raw_score: float  # Raw ML model score (pre-calibration)
	ml_calibrated_score: float  # Calibrated ML score (post-account calibration)
	risk_decision: str  # 'approved' or 'rejected' by risk engine
	trade_parameters: Dict[str, Any]  # Order size, stop, take-profit, etc.
	decision_reason: str  # Human-readable reason for decision (for audit/ML)
	data_collection_flag: bool = False  # True if this trade is part of a data collection phase
	trade_id: str = ""  # Populated after trade is placed (if approved)
	outcome: str = ""  # Populated after trade closes (e.g., 'win', 'loss', 'breakeven')
	pnl: float = 0.0  # Profit/loss after trade closes


class TradeLogger:
	"""
	Logs every trade decision (approved or rejected) in a structured, ML-ready format.
	Designed for use in both backtesting and live trading environments.
	"""

	def __init__(self):
		"""
		Initialize the TradeLogger and in-memory log storage.
		TODO: Add persistence to file or database backend.
		"""
		self.logs = []

	def log_trade_decision(
		self,
		timestamp,
		agent_name,
		account_id,
		market,
		symbol,
		strategy_id,
		features_snapshot,
		ml_raw_score,
		ml_calibrated_score,
		risk_decision,
		trade_parameters,
		decision_reason,
		data_collection_flag=False
	):
		"""
		Log a trade decision with all relevant context for ML and audit.
		Args:
			timestamp (str): ISO8601 timestamp of the decision.
			agent_name (str): Which agent made the decision.
			account_id (str): Unique account identifier.
			market (str): Market type (e.g., 'forex', 'equity').
			symbol (str): Instrument symbol.
			strategy_id (str): Strategy identifier.
			features_snapshot (dict): Features used for ML/model decision.
			ml_raw_score (float): Raw ML model score.
			ml_calibrated_score (float): Calibrated ML score.
			risk_decision (str): 'approved' or 'rejected' by risk engine.
			trade_parameters (dict): Order size, stop, take-profit, etc.
			decision_reason (str): Human-readable reason for decision.
		TODO: Add persistence to file or database backend.
		"""
		record = TradeLogRecord(
			timestamp=timestamp,
			agent_name=agent_name,
			account_id=account_id,
			market=market,
			symbol=symbol,
			strategy_id=strategy_id,
			features_snapshot=features_snapshot,
			ml_raw_score=ml_raw_score,
			ml_calibrated_score=ml_calibrated_score,
			risk_decision=risk_decision,
			trade_parameters=trade_parameters,
			decision_reason=decision_reason,
			data_collection_flag=data_collection_flag
		)
		self.logs.append(record)

	def update_trade_outcome(self, trade_id, outcome, pnl):
		"""
		Update the outcome and PnL for a trade after it closes.
		Args:
			trade_id (str): Unique trade identifier.
			outcome (str): Trade result ('win', 'loss', 'breakeven', etc.).
			pnl (float): Profit or loss for the trade.
		TODO: Add persistence to file or database backend.
		"""
		for record in self.logs:
			if record.trade_id == trade_id:
				record.outcome = outcome
				record.pnl = pnl
				break