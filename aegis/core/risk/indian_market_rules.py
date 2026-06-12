"""
Indian Market Risk Rules for AEGIS Core Risk.

Enforces SEBI and NSE/BSE regulations for Indian equity and commodity trading.

Rules enforced:
    Equity (Intraday MIS):
        - SEBI peak margin: 20% upfront margin (VAR + ELM) for MIS intraday positions
        - Per-trade exposure cap: max 5% of daily capital per symbol
        - Daily loss limit: configurable per risk profile (default 2%)
        - MIS squareoff deadline: 3:15 PM IST (hard rule)
        - NSE circuit breaker awareness: reject trades near ±5%/±10%/±20% limits
        - No trading in NSE F&O ban list stocks

    Commodity:
        - Max daily volatility cap: configurable (default 2% daily move)
        - SEBI commodity margin: 10% upfront margin for commodity futures

All rules are explainable and logged for compliance and audit.
"""

import logging
from datetime import datetime, time
import pytz

IST = pytz.timezone("Asia/Kolkata")
SQUAREOFF_DEADLINE = time(15, 15)   # MIS squareoff hard cut-off

logger = logging.getLogger("AEGIS.IndianMarketRules")

# SEBI-derived constants
SEBI_MIS_MARGIN_PCT = 0.20
MAX_SINGLE_SYMBOL_EXPOSURE_PCT = 0.05
CIRCUIT_BREAKER_BUFFER_PCT = 0.02


class IndianMarketRiskRules:
	"""
	Enforces SEBI and NSE/BSE risk rules for Indian equity and commodity trading.

	Hierarchy of checks (applied in order):
		1. MIS squareoff deadline — hard block after 3:15 PM IST
		2. Circuit breaker proximity — reject if stock is near ±5% circuit
		3. F&O ban list — reject banned securities
		4. Per-symbol exposure cap (SEBI: 5% of capital per trade)
		5. Daily loss limit from risk profile config
		6. SEBI margin availability check
		7. Commodity volatility cap
	"""

	def __init__(self, risk_profiles: dict, banned_symbols: list = None):
		"""
		Args:
			risk_profiles (dict): Loaded from aegis/configs/risk_profiles.yaml
			banned_symbols (list): NSE symbols currently in F&O ban list. Default empty.
		"""
		self.risk_profiles = risk_profiles
		self.banned_symbols = set(banned_symbols or [])

	def is_trade_allowed(self, market_type: str, trade_context: dict) -> dict:
		"""
		Determine if a trade is allowed under Indian market rules.

		Args:
			market_type (str): 'equity' or 'commodity'
			trade_context (dict): Must contain:
				- 'capital' (float): Total daily trading capital in INR
				- 'exposure' (float): Value of proposed position (price × quantity)
				- 'symbol' (str): NSE trading symbol
				- 'risk_profile' (str): Account risk profile
				- 'daily_realized_pnl' (float, optional): Today's realized P&L
				- 'last_close' (float, optional): Previous close for circuit check
				- 'current_price' (float, optional): Current market price
				- 'volatility' (float, optional): Commodity: daily % move
				- 'available_margin' (float, optional): Margin available in account

		Returns:
			dict: {'allowed': bool, 'rejection_reason': str or None}
		"""
		if market_type == 'equity':
			return self._check_equity(trade_context)
		elif market_type == 'commodity':
			return self._check_commodity(trade_context)
		else:
			return {'allowed': False, 'rejection_reason': f'Unknown market type: {market_type}'}

	def _check_equity(self, ctx: dict) -> dict:
		symbol = ctx.get('symbol', '')
		capital = ctx.get('capital', 0.0)
		exposure = ctx.get('exposure', 0.0)
		risk_profile = ctx.get('risk_profile', 'balanced').lower()
		daily_pnl = ctx.get('daily_realized_pnl', 0.0)
		last_close = ctx.get('last_close')
		current_price = ctx.get('current_price')

		# 1. Squareoff deadline — hard block
		now_ist = datetime.now(IST).time()
		if now_ist >= SQUAREOFF_DEADLINE:
			return {
				'allowed': False,
				'rejection_reason': 'MIS squareoff deadline passed (3:15 PM IST). No new trades.'
			}

		# 2. F&O ban list check
		if symbol in self.banned_symbols:
			return {
				'allowed': False,
				'rejection_reason': f'{symbol} is in the NSE F&O ban list.'
			}

		# 3. Circuit breaker proximity
		if last_close and current_price and last_close > 0:
			pct_move = abs(current_price - last_close) / last_close
			for threshold in [0.05, 0.10, 0.20]:
				if pct_move >= (threshold - CIRCUIT_BREAKER_BUFFER_PCT):
					return {
						'allowed': False,
						'rejection_reason': (
							f'{symbol} is within {CIRCUIT_BREAKER_BUFFER_PCT*100:.0f}% of a '
							f'{threshold*100:.0f}% circuit breaker (move: {pct_move*100:.1f}%).'
						)
					}

		# 4. Per-symbol exposure cap
		if capital > 0 and exposure / capital > MAX_SINGLE_SYMBOL_EXPOSURE_PCT:
			return {
				'allowed': False,
				'rejection_reason': (
					f'Trade exposure ₹{exposure:,.0f} ({exposure/capital*100:.1f}% of capital) '
					f'exceeds SEBI 5% per-symbol limit.'
				)
			}

		# 5. Daily loss limit
		profile_cfg = self.risk_profiles.get(risk_profile, {})
		max_daily_loss_pct = profile_cfg.get('max_daily_loss_pct', 0.02)
		max_daily_loss_inr = capital * max_daily_loss_pct
		if daily_pnl <= -max_daily_loss_inr:
			return {
				'allowed': False,
				'rejection_reason': (
					f'Daily loss limit breached: ₹{daily_pnl:,.2f} '
					f'(limit: ₹{-max_daily_loss_inr:,.2f}).'
				)
			}

		# 6. SEBI MIS margin check
		required_margin = exposure * SEBI_MIS_MARGIN_PCT
		available_margin = ctx.get('available_margin', capital)
		if required_margin > available_margin:
			return {
				'allowed': False,
				'rejection_reason': (
					f'Insufficient margin. Required: ₹{required_margin:,.0f} '
					f'(20% of ₹{exposure:,.0f}). Available: ₹{available_margin:,.0f}.'
				)
			}

		return {'allowed': True, 'rejection_reason': None}

	def _check_commodity(self, ctx: dict) -> dict:
		volatility = ctx.get('volatility', 0.0)
		capital = ctx.get('capital', 0.0)
		exposure = ctx.get('exposure', 0.0)
		risk_profile = ctx.get('risk_profile', 'balanced').lower()

		profile_cfg = self.risk_profiles.get(risk_profile, {})
		max_volatility = profile_cfg.get('commodity_max_volatility', 0.02)
		if volatility > max_volatility:
			return {
				'allowed': False,
				'rejection_reason': (
					f'Commodity volatility {volatility*100:.1f}% exceeds '
					f'{max_volatility*100:.1f}% cap for {risk_profile} profile.'
				)
			}

		# SEBI commodity margin: 10%
		required_margin = exposure * 0.10
		available_margin = ctx.get('available_margin', capital)
		if required_margin > available_margin:
			return {
				'allowed': False,
				'rejection_reason': (
					f'Insufficient commodity margin. Required: ₹{required_margin:,.0f}. '
					f'Available: ₹{available_margin:,.0f}.'
				)
			}

		return {'allowed': True, 'rejection_reason': None}

	def check_equity_risk(self, capital_state: dict) -> bool:
		"""Legacy method. Returns True if risk is breached."""
		return not self._check_equity(capital_state)['allowed']

	def check_commodity_risk(self, capital_state: dict) -> bool:
		"""Legacy method. Returns True if risk is breached."""
		return not self._check_commodity(capital_state)['allowed']

	def update_banned_symbols(self, symbols: list):
		"""Update NSE F&O ban list. Call daily before market open."""
		self.banned_symbols = set(symbols)
		logger.info(f"F&O ban list updated: {len(self.banned_symbols)} symbols.")

	def is_market_open(self) -> bool:
		"""Return True if current IST time is within NSE trading hours."""
		now = datetime.now(IST).time()
		return time(9, 15) <= now <= time(15, 30)