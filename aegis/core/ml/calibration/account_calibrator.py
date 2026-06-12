"""
Account Calibrator for AEGIS ML Calibration.
Handles account-specific calibration for ML models.

This module defines the AccountCalibrator class, responsible for adjusting ML confidence
and applying account-specific thresholds and scaling.
"""


from aegis.core.trading_mode import TradingMode, TradingModeConfig


import yaml

class AccountCalibrator:
	"""
	Account-specific ML calibration and approval logic for AEGIS.

	This layer is separate from the ML model to ensure that risk and business rules can be changed
	without retraining the model. Calibration protects prop firm accounts by enforcing stricter
	thresholds for live trading and conservative profiles, and allows more flexibility for data collection
	and experimental profiles. All logic is explainable and auditable.
	"""

	def __init__(self, risk_profile_config_path="aegis/configs/risk_profiles.yaml"):
		"""
		Initialize the AccountCalibrator and load risk profile thresholds.
		Args:
			risk_profile_config_path (str): Path to the risk profile YAML config.
		"""
		with open(risk_profile_config_path, "r") as f:
			self.risk_profiles = yaml.safe_load(f)

	def calibrate_score(self, raw_score, account_profile, trading_mode=None, trading_mode_config=None):
		"""
		Calibrate the raw ML score for a specific account profile and trading mode.
		Args:
			raw_score (float): The uncalibrated score from the ML model (0-1).
			account_profile: The account's profile (must have 'risk_profile' and 'trading_mode').
			trading_mode (str or TradingMode, optional): Trading mode for the account.
			trading_mode_config (optional): Not used in v1.
		Returns:
			float: Calibrated score (identity in v1, but hook for future scaling).
		"""
		# In v1, calibration is identity (no scaling), but this is the hook for future logic.
		return raw_score

	def is_trade_allowed(self, calibrated_score, account_profile, trading_mode=None, trading_mode_config=None):
		"""
		Determine if a trade is allowed based on the calibrated score, account profile, and trading mode.
		Args:
			calibrated_score (float): The calibrated ML score (0-1).
			account_profile: The account's profile (must have 'risk_profile' and 'trading_mode').
			trading_mode (str or TradingMode, optional): Trading mode for the account.
			trading_mode_config (optional): Not used in v1.
		Returns:
			dict: {'allowed': bool, 'calibrated_score': float, 'rejection_reason': str or None}
		"""
		risk_profile = getattr(account_profile, 'risk_profile', None) or account_profile.get('risk_profile')
		mode = trading_mode or getattr(account_profile, 'trading_mode', None) or account_profile.get('trading_mode')
		if not risk_profile or not mode:
			return {'allowed': False, 'calibrated_score': calibrated_score, 'rejection_reason': 'Missing risk_profile or trading_mode'}

		profile_cfg = self.risk_profiles.get(risk_profile.lower())
		if not profile_cfg:
			return {'allowed': False, 'calibrated_score': calibrated_score, 'rejection_reason': f'Unknown risk_profile: {risk_profile}'}

		# Determine threshold based on mode
		if str(mode).upper() in ('LIVE_FUND', 'LIVE', 'LIVEFUND'):
			min_conf = profile_cfg.get('live_min_confidence', 0.6)
		else:
			min_conf = profile_cfg.get('data_min_confidence', 0.5)

		if calibrated_score >= min_conf:
			return {'allowed': True, 'calibrated_score': calibrated_score, 'rejection_reason': None}
		else:
			return {
				'allowed': False,
				'calibrated_score': calibrated_score,
				'rejection_reason': f'Confidence {calibrated_score:.2f} below minimum {min_conf:.2f} for {risk_profile} ({mode})'
			}