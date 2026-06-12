"""
Performance Logger for AEGIS Core Logging.
Logs performance metrics and analytics.

This module defines the PerformanceLogger class, responsible for tracking aggregated
performance metrics and providing summaries to the Main Agent.
"""

from collections import defaultdict

class PerformanceLogger:

import pandas as pd
import numpy as np

	def get_strategy_performance(self):
		"""
		Returns a DataFrame with per-strategy performance: trades, wins, losses, win_rate, total_pnl, avg_pnl.
		Use this to compare strategy effectiveness and risk.
		"""
		df = pd.DataFrame(self.trade_results, columns=[
			'agent_name', 'account_id', 'pnl', 'timestamp', 'strategy_id', 'outcome', 'ml_rejected', 'risk_rejected', 'risk_reason'])
		if df.empty:
			return pd.DataFrame()
		grouped = df.groupby('strategy_id')
		perf = grouped.agg(
			trades=('pnl', 'count'),
			wins=('outcome', lambda x: (x == 'win').sum()),
			losses=('outcome', lambda x: (x == 'loss').sum()),
			win_rate=('outcome', lambda x: (x == 'win').mean()),
			total_pnl=('pnl', 'sum'),
			avg_pnl=('pnl', 'mean')
		).reset_index()
		return perf

	def get_account_performance(self):
		"""
		Returns a DataFrame with per-account performance: trades, total_pnl, max_drawdown, win_rate.
		Use this to monitor account health and risk.
		"""
		df = pd.DataFrame(self.trade_results, columns=[
			'agent_name', 'account_id', 'pnl', 'timestamp', 'strategy_id', 'outcome', 'ml_rejected', 'risk_rejected', 'risk_reason'])
		if df.empty:
			return pd.DataFrame()
		grouped = df.groupby('account_id')
		def max_drawdown(pnls):
			equity = np.cumsum(pnls)
			dd = np.maximum.accumulate(equity) - equity
			return dd.max() if len(dd) > 0 else 0.0
		perf = grouped.agg(
			trades=('pnl', 'count'),
			total_pnl=('pnl', 'sum'),
			max_drawdown=('pnl', max_drawdown),
			win_rate=('outcome', lambda x: (x == 'win').mean())
		).reset_index()
		return perf

	def get_ml_filter_stats(self):
		"""
		Returns ML filter stats: total_signals, accepted_by_ml, rejected_by_ml, acceptance_rate.
		Use this to monitor ML filter selectivity and drift.
		"""
		df = pd.DataFrame(self.trade_results, columns=[
			'agent_name', 'account_id', 'pnl', 'timestamp', 'strategy_id', 'outcome', 'ml_rejected', 'risk_rejected', 'risk_reason'])
		if df.empty or 'ml_rejected' not in df:
			return pd.DataFrame()
		total = len(df)
		rejected = df['ml_rejected'].sum()
		accepted = total - rejected
		acceptance_rate = accepted / total if total > 0 else 0.0
		return pd.DataFrame([{
			'total_signals': total,
			'accepted_by_ml': accepted,
			'rejected_by_ml': rejected,
			'acceptance_rate': acceptance_rate
		}])

	def get_risk_block_stats(self):
		"""
		Returns risk block stats: total_signals, blocked_by_risk, block_reasons_breakdown.
		Use this to audit risk engine behavior and tune risk controls.
		"""
		df = pd.DataFrame(self.trade_results, columns=[
			'agent_name', 'account_id', 'pnl', 'timestamp', 'strategy_id', 'outcome', 'ml_rejected', 'risk_rejected', 'risk_reason'])
		if df.empty or 'risk_rejected' not in df:
			return pd.DataFrame()
		total = len(df)
		blocked = df['risk_rejected'].sum()
		reasons = df[df['risk_rejected']]['risk_reason'].value_counts().to_dict()
		return pd.DataFrame([{
			'total_signals': total,
			'blocked_by_risk': blocked,
			'block_reasons_breakdown': reasons
		}])

	def get_daily_summary(self, date):
		"""
		Returns a DataFrame with all trades and stats for a given day (YYYY-MM-DD).
		Use this for daily review and anomaly detection.
		"""
		df = pd.DataFrame(self.trade_results, columns=[
			'agent_name', 'account_id', 'pnl', 'timestamp', 'strategy_id', 'outcome', 'ml_rejected', 'risk_rejected', 'risk_reason'])
		if df.empty:
			return pd.DataFrame()
		df['date'] = pd.to_datetime(df['timestamp']).dt.date.astype(str)
		return df[df['date'] == date]

	def get_weekly_summary(self, week_id):
		"""
		Returns a DataFrame with all trades and stats for a given ISO week (e.g., '2025-W50').
		Use this for weekly review and performance tracking.
		"""
		df = pd.DataFrame(self.trade_results, columns=[
			'agent_name', 'account_id', 'pnl', 'timestamp', 'strategy_id', 'outcome', 'ml_rejected', 'risk_rejected', 'risk_reason'])
		if df.empty:
			return pd.DataFrame()
		df['week'] = pd.to_datetime(df['timestamp']).dt.isocalendar().week.astype(str)
		df['year'] = pd.to_datetime(df['timestamp']).dt.isocalendar().year.astype(str)
		week_str = week_id.split('-W')
		if len(week_str) == 2:
			year, week = week_str
			return df[(df['year'] == year) & (df['week'] == week)]
		return pd.DataFrame()
	"""
	Tracks aggregated performance metrics and provides daily, weekly, and monthly summaries.
	Designed for use in both backtesting and live trading environments.
	All fields are designed for ML training, audit, and cross-agent consistency.
	"""

	def __init__(self):
		"""
		Initialize the PerformanceLogger and in-memory metrics storage.
		TODO: Add persistence to file or database backend.
		"""
		self.trade_results = []  # List of (agent_name, account_id, pnl, timestamp)
		self.daily_summary = defaultdict(float)
		self.weekly_summary = defaultdict(float)
		self.monthly_summary = defaultdict(float)

	def record_trade_result(self, agent_name, account_id, pnl):
		"""
		Record the result of a trade for performance tracking.
		Args:
			agent_name (str): Which agent executed the trade.
			account_id (str): Unique account identifier.
			pnl (float): Profit or loss for the trade.
		TODO: Add timestamp and persist to file or database backend.
		"""
		self.trade_results.append((agent_name, account_id, pnl))

	def get_daily_summary(self, date):
		"""
		Get aggregated performance metrics for a specific day.
		Args:
			date (str): Date in 'YYYY-MM-DD' format.
		Returns:
			dict: Aggregated metrics for the day.
		TODO: Implement daily aggregation and persistence.
		"""
		# Placeholder: return empty dict
		return {}

	def get_weekly_summary(self, week_id):
		"""
		Get aggregated performance metrics for a specific week.
		Args:
			week_id (str): Week identifier (e.g., '2025-W50').
		Returns:
			dict: Aggregated metrics for the week.
		TODO: Implement weekly aggregation and persistence.
		"""
		# Placeholder: return empty dict
		return {}

	def get_monthly_summary(self, month_id):
		"""
		Get aggregated performance metrics for a specific month.
		Args:
			month_id (str): Month identifier (e.g., '2025-12').
		Returns:
			dict: Aggregated metrics for the month.
		TODO: Implement monthly aggregation and persistence.
		"""
		# Placeholder: return empty dict
		return {}