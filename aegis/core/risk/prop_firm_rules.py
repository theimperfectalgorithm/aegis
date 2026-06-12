"""
Prop Firm Rules for AEGIS Core Risk.
Defines risk rules for prop firm trading accounts.

This module defines the PropFirmRiskRules class, responsible for enforcing prop firm constraints
and tracking rule violations for each account.
"""



class PropFirmRiskRules:
	"""
	Enforces prop firm-specific constraints, tracks daily loss, max drawdown, and rule violations.
	Designed for extensibility to support multiple prop firms and evolving rules.
	"""

	def __init__(self, risk_profiles):
		"""
		Initialize the PropFirmRiskRules and account risk tracking.
		Args:
			risk_profiles (dict): Loaded risk profile config.
		"""
		self.risk_profiles = risk_profiles
		self.daily_pnl = {}  # account_id -> daily PnL
		self.cumulative_drawdown = {}  # account_id -> drawdown
		self.account_equity_high = {}  # account_id -> highest equity
		self.daily_trade_count = {}  # account_id -> trades today

	def check_daily_loss(self, account_id, account_equity, risk_profile):
		"""
		Check if the account has breached daily loss limits.
		Args:
			account_id (str): Account identifier.
			account_equity (float): Current account equity.
			risk_profile (str): Account risk profile.
		Returns:
			bool: True if daily loss limit is breached, False otherwise.
		"""
		profile_cfg = self.risk_profiles.get(risk_profile, {})
		max_daily_loss_pct = profile_cfg.get('max_daily_loss_percent', 2.0)
		equity_high = self.account_equity_high.get(account_id, account_equity)
		daily_loss = equity_high - account_equity
		self.daily_pnl[account_id] = daily_loss
		if daily_loss > (equity_high * max_daily_loss_pct / 100.0):
			return True
		return False

	def check_max_drawdown(self, account_id, account_equity, risk_profile):
		"""
		Check if the account has breached max drawdown limits.
		Args:
			account_id (str): Account identifier.
			account_equity (float): Current account equity.
			risk_profile (str): Account risk profile.
		Returns:
			bool: True if max drawdown is breached, False otherwise.
		"""
		profile_cfg = self.risk_profiles.get(risk_profile, {})
		max_drawdown_pct = profile_cfg.get('max_drawdown_percent', 10.0)
		equity_high = self.account_equity_high.get(account_id, account_equity)
		drawdown = (equity_high - account_equity) / equity_high
		self.cumulative_drawdown[account_id] = drawdown
		if drawdown > (max_drawdown_pct / 100.0):
			return True
		return False

	def is_trade_allowed(self, account_id, trade_context):
		"""
		Determine if a trade is allowed for the given account under current risk rules.
		Args:
			account_id (str): Account identifier.
			trade_context (dict): Contextual information about the trade.
		Returns:
			dict: {'allowed': bool, 'rejection_reason': str or None}
		"""
		account_equity = trade_context.get('account_equity', 0)
		risk_profile = trade_context.get('risk_profile', 'conservative').lower()
		max_trades = self.risk_profiles.get(risk_profile, {}).get('max_trades_per_day', 2)

		# Track highest equity for drawdown
		equity_high = self.account_equity_high.get(account_id, account_equity)
		if account_equity > equity_high:
			self.account_equity_high[account_id] = account_equity
		else:
			self.account_equity_high[account_id] = equity_high

		# 1. Daily loss cap
		if self.check_daily_loss(account_id, account_equity, risk_profile):
			return {'allowed': False, 'rejection_reason': 'Daily loss limit breached'}

		# 2. Max drawdown cap
		if self.check_max_drawdown(account_id, account_equity, risk_profile):
			return {'allowed': False, 'rejection_reason': 'Max drawdown limit breached'}

		# 3. Max trades per day
		count = self.daily_trade_count.get(account_id, 0)
		if count >= max_trades:
			return {'allowed': False, 'rejection_reason': f'Max trades per day ({max_trades}) reached'}
		self.daily_trade_count[account_id] = count + 1

		return {'allowed': True, 'rejection_reason': None}