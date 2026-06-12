"""
Global Risk Manager for AEGIS Core.
Manages global risk across all agents and markets.

This module defines the GlobalRiskManager class, responsible for enforcing portfolio-level risk,
acting as the final gatekeeper before trades, and managing agent kill switches.
"""


from aegis.core.trading_mode import TradingMode

import yaml
from aegis.core.risk.prop_firm_rules import PropFirmRiskRules
from aegis.core.risk.indian_market_rules import IndianMarketRiskRules

class GlobalRiskManager:
	"""
	Enforces portfolio-level risk, acts as the final gatekeeper before trades,
	and decides when to pause or stop agents in the AEGIS system.

	Risk hierarchy:
	  1. Account-level rules (prop firm or Indian market)
	  2. Portfolio-level drawdown and kill switch
	  3. Position sizing and risk per trade

	Designed for extensibility to support new markets and risk rules.
	"""

	def __init__(self, risk_profile_config_path="aegis/configs/risk_profiles.yaml"):
		"""
		Initialize the GlobalRiskManager and risk tracking structures.
		Loads risk profile config and sets up rule engines.
		"""
		with open(risk_profile_config_path, "r") as f:
			self.risk_profiles = yaml.safe_load(f)
		self.prop_firm_rules = PropFirmRiskRules(self.risk_profiles)
		self.indian_market_rules = IndianMarketRiskRules(self.risk_profiles)
		self.portfolio_equity = 1000000  # Placeholder for total equity
		self.portfolio_high = self.portfolio_equity
		self.portfolio_drawdown = 0
		self.kill_switch_triggered = False

	def evaluate_trade_risk(self, agent_name, account_id, trade_context, trading_mode=None):
		"""
		Evaluate the risk of a proposed trade before execution.
		Args:
			agent_name (str): Name of the agent proposing the trade.
			account_id (str): Account identifier.
			trade_context (dict): Must include 'account_equity', 'risk_profile', 'stop_loss_distance', 'market', etc.
			trading_mode (str, optional): Trading mode for the account (LIVE_FUND or DATA_COLLECTION).
		Returns:
			dict: {'allowed': bool, 'position_size': float, 'risk_amount': float, 'rejection_reason': str or None}
		"""
		# 1. Retrieve account equity and risk profile
		equity = trade_context.get('account_equity', 0)
		risk_profile = trade_context.get('risk_profile', 'conservative').lower()
		stop_loss_distance = trade_context.get('stop_loss_distance', None)
		market = trade_context.get('market', 'forex')

		# 2. Call account-level rules
		if market == 'forex':
			pf_result = self.prop_firm_rules.is_trade_allowed(account_id, trade_context)
			if not pf_result['allowed']:
				return {
					'allowed': False,
					'position_size': 0,
					'risk_amount': 0,
					'rejection_reason': pf_result['rejection_reason']
				}
		elif market in ('equity', 'commodity'):
			im_result = self.indian_market_rules.is_trade_allowed(market, trade_context)
			if not im_result['allowed']:
				return {
					'allowed': False,
					'position_size': 0,
					'risk_amount': 0,
					'rejection_reason': im_result['rejection_reason']
				}

		# 3. Calculate allowed risk amount and position size
		profile_cfg = self.risk_profiles.get(risk_profile, {})
		risk_per_trade_pct = profile_cfg.get('risk_per_trade_percent', 1.0)
		risk_amount = equity * (risk_per_trade_pct / 100.0)
		if stop_loss_distance and stop_loss_distance > 0:
			position_size = risk_amount / stop_loss_distance
		else:
			position_size = 0
			return {
				'allowed': False,
				'position_size': 0,
				'risk_amount': risk_amount,
				'rejection_reason': 'Invalid or missing stop_loss_distance'
			}

		# 4. Portfolio-level drawdown check
		if self.check_portfolio_drawdown():
			return {
				'allowed': False,
				'position_size': 0,
				'risk_amount': risk_amount,
				'rejection_reason': 'Portfolio drawdown limit breached'
			}

		return {
			'allowed': True,
			'position_size': position_size,
			'risk_amount': risk_amount,
			'rejection_reason': None
		}

	def check_portfolio_drawdown(self):
		"""
		Check if the portfolio has breached drawdown limits.
		Returns:
			bool: True if drawdown limits are breached, False otherwise.
		"""
		# Simple placeholder: 20% max drawdown
		self.portfolio_drawdown = (self.portfolio_high - self.portfolio_equity) / self.portfolio_high
		if self.portfolio_drawdown > 0.20 or self.kill_switch_triggered:
			return True
		return False

	def trigger_kill_switch(self, reason):
		"""
		Trigger a system-wide kill switch to pause or stop all agents.
		Args:
			reason (str): Reason for triggering the kill switch.
		"""
		self.kill_switch_triggered = True
		# TODO: Notify all agents and log the event
		print(f"KILL SWITCH TRIGGERED: {reason}")

	def reset_daily_limits(self):
		"""
		Reset daily risk and drawdown limits at the start of a new trading day.
		TODO: Implement logic to reset all daily risk counters and limits.
		"""
		pass