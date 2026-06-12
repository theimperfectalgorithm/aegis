"""
Account Profiles for Forex Agent.
Defines risk and strategy profiles for each prop firm account.

This module defines data structures for risk profiles and strategy permissions per account.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class RiskProfile:
	"""
	Represents a risk profile for a prop firm account.
	"""
	name: str  # e.g., 'conservative', 'balanced', 'aggressive', 'experimental'
	max_drawdown: float  # Maximum allowed drawdown
	max_daily_loss: float  # Maximum daily loss
	risk_per_trade: float  # Risk per trade as a percentage
	notes: str = ""


@dataclass
class StrategyPermission:
	"""
	Represents strategy permissions for a specific account.
	"""
	account_id: str
	allowed_strategies: List[str] = field(default_factory=list)


@dataclass
class AccountProfile:
	"""
	Combines risk profile and strategy permissions for a prop firm account.
	"""
	account_id: str
	risk_profile: RiskProfile
	strategy_permission: StrategyPermission