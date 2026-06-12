import pandas as pd

def generate_diagnostic_report(backtest_results):
	"""
	Generate a diagnostic report (tables only) for a backtest, paper, or live run.
	Includes:
	  - Strategy-wise performance table
	  - ML acceptance vs rejection table
	  - Risk blocks summary
	  - Equity curve (as a table)
	  - Drawdown over time (as a table)
	Args:
		backtest_results (dict): Results dict from backtest, paper, or live engine
	Returns:
		dict of pandas DataFrames for reporting
	How to use: Review these tables daily to monitor system health, ML selectivity, risk blocks, and strategy/account performance. Use equity/drawdown tables for risk and capital review.
	"""
	trades = backtest_results.get('trades', [])
	df_trades = pd.DataFrame(trades)
	# Strategy-wise performance
	if not df_trades.empty and 'strategy_id' in df_trades:
		strat_perf = df_trades.groupby('strategy_id').agg(
			trades=('pnl', 'count'),
			wins=('outcome', lambda x: (x == 'win').sum()),
			losses=('outcome', lambda x: (x == 'loss').sum()),
			win_rate=('outcome', lambda x: (x == 'win').mean()),
			total_pnl=('pnl', 'sum'),
			avg_pnl=('pnl', 'mean')
		).reset_index()
	else:
		strat_perf = pd.DataFrame()
	# ML acceptance/rejection
	if not df_trades.empty and 'ml_rejected' in df_trades:
		total = len(df_trades)
		rejected = df_trades['ml_rejected'].sum()
		accepted = total - rejected
		acceptance_rate = accepted / total if total > 0 else 0.0
		ml_stats = pd.DataFrame([{
			'total_signals': total,
			'accepted_by_ml': accepted,
			'rejected_by_ml': rejected,
			'acceptance_rate': acceptance_rate
		}])
	else:
		ml_stats = pd.DataFrame()
	# Risk blocks summary
	if not df_trades.empty and 'risk_rejected' in df_trades:
		total = len(df_trades)
		blocked = df_trades['risk_rejected'].sum()
		reasons = df_trades[df_trades['risk_rejected']]['risk_reason'].value_counts().to_dict() if 'risk_reason' in df_trades else {}
		risk_stats = pd.DataFrame([{
			'total_signals': total,
			'blocked_by_risk': blocked,
			'block_reasons_breakdown': reasons
		}])
	else:
		risk_stats = pd.DataFrame()
	# Equity curve (cumulative PnL)
	if not df_trades.empty and 'pnl' in df_trades:
		df_trades['equity'] = df_trades['pnl'].cumsum()
		equity_curve = df_trades[['timestamp', 'equity']]
	else:
		equity_curve = pd.DataFrame()
	# Drawdown over time
	if not df_trades.empty and 'pnl' in df_trades:
		equity = df_trades['pnl'].cumsum()
		dd = (equity.cummax() - equity)
		drawdown_timeline = pd.DataFrame({'timestamp': df_trades['timestamp'], 'drawdown': dd})
	else:
		drawdown_timeline = pd.DataFrame()
	return {
		'strategy_performance': strat_perf,
		'ml_stats': ml_stats,
		'risk_stats': risk_stats,
		'equity_curve': equity_curve,
		'drawdown_timeline': drawdown_timeline
	}
import matplotlib.pyplot as plt
import numpy as np

def compare_equity_curves(run_a, run_b, label_a="Baseline", label_b="ML-Filtered"):
	"""
	Plot and compare equity curves from two backtest runs.
	"""
	eq_a = run_a.get('equity_curve', [])
	eq_b = run_b.get('equity_curve', [])
	plt.figure(figsize=(10, 5))
	plt.plot(eq_a, label=label_a)
	plt.plot(eq_b, label=label_b)
	plt.title("Equity Curve Comparison")
	plt.xlabel("Time")
	plt.ylabel("Equity")
	plt.legend()
	plt.show()

def compare_drawdowns(run_a, run_b, label_a="Baseline", label_b="ML-Filtered"):
	"""
	Plot and compare drawdowns from two backtest runs.
	"""
	dd_a = run_a.get('drawdowns', [])
	dd_b = run_b.get('drawdowns', [])
	plt.figure(figsize=(10, 5))
	plt.plot(dd_a, label=label_a)
	plt.plot(dd_b, label=label_b)
	plt.title("Drawdown Comparison")
	plt.xlabel("Time")
	plt.ylabel("Drawdown")
	plt.legend()
	plt.show()

def compare_trade_stats(run_a, run_b, label_a="Baseline", label_b="ML-Filtered"):
	"""
	Print and compare trade statistics from two backtest runs.
	"""
	stats_a = run_a.get('stats', {})
	stats_b = run_b.get('stats', {})
	print(f"\nTrade Stats Comparison:")
	print(f"{'Metric':<25}{label_a:<15}{label_b:<15}")
	all_keys = set(stats_a.keys()) | set(stats_b.keys())
	for k in sorted(all_keys):
		v_a = stats_a.get(k, '-')
		v_b = stats_b.get(k, '-')
		print(f"{k:<25}{v_a:<15}{v_b:<15}")
"""
Backtesting Reports for AEGIS.
Generates performance and analytics reports from backtesting results.

This module defines the BacktestReport class, responsible for aggregating results from logs
and producing performance summaries for strategies and agents.
Ensures reporting parity between live and backtest environments.
"""


class BacktestReport:
	"""
	Aggregates results from logs and produces performance summaries for backtests.
	Designed for extensibility to support new metrics and reporting formats.
	"""

	def __init__(self):
		"""
		Initialize the BacktestReport and result storage.
		TODO: Set up references to logs and metrics.
		"""
		pass

	def generate_equity_curve(self):
		"""
		Generate the equity curve from backtest results.
		Returns:
			List or structure representing equity over time.
		TODO: Implement equity curve calculation.
		"""
		pass

	def generate_drawdown_report(self):
		"""
		Generate a drawdown report from backtest results.
		Returns:
			List or structure representing drawdown periods and values.
		TODO: Implement drawdown calculation and reporting.
		"""
		pass

	def generate_strategy_breakdown(self):
		"""
		Generate a breakdown of performance by strategy.
		Returns:
			Dict or structure summarizing performance by strategy.
		TODO: Implement strategy-level performance aggregation.
		"""
		pass