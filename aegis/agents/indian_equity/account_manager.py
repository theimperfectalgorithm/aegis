"""
EquityAccountManager for AEGIS Indian Equity Agent.

Manages the NSE trading account state:
  - Tracks open intraday positions and portfolio holdings
  - Enforces MIS squareoff deadline (3:15 PM IST)
  - Tracks daily P&L and trade count against config limits
  - Provides account summary for risk and orchestrator reporting

Designed for Zerodha Kite but broker-agnostic at this layer.
"""

import logging
from datetime import datetime, time
from copy import deepcopy

import pytz

IST = pytz.timezone("Asia/Kolkata")
SQUAREOFF_DEADLINE = time(15, 15)

logger = logging.getLogger("AEGIS.EquityAccountManager")


class EquityPosition:
    """Represents a single open intraday equity position."""

    def __init__(
        self,
        trade_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: int,
        stop_loss: float,
        take_profit: float,
        open_time: str,
        strategy_id: str,
    ):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction          # 'BUY' or 'SELL'
        self.entry_price = entry_price
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.open_time = open_time
        self.strategy_id = strategy_id
        self.status = "open"
        self.close_price = None
        self.close_time = None
        self.pnl = 0.0

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at a given market price."""
        if self.direction == "BUY":
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity

    def close(self, close_price: float, close_time: str):
        """Mark position as closed and compute final P&L."""
        self.close_price = close_price
        self.close_time = close_time
        self.status = "closed"
        if self.direction == "BUY":
            self.pnl = (close_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - close_price) * self.quantity

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "open_time": self.open_time,
            "strategy_id": self.strategy_id,
            "status": self.status,
            "close_price": self.close_price,
            "close_time": self.close_time,
            "pnl": self.pnl,
        }


class EquityAccountManager:
    """
    Manages NSE intraday equity account state for AEGIS.

    Responsibilities:
        - Track open MIS positions
        - Enforce per-day trade count limits
        - Track daily realized and unrealized P&L
        - Flag when squareoff deadline is approaching
        - Provide account summaries for risk engine and orchestrator
    """

    def __init__(self, account_id: str, capital: float, max_daily_trades: int = 5, max_daily_loss_pct: float = 0.02):
        """
        Args:
            account_id (str): Unique identifier for this NSE account.
            capital (float): Starting capital in INR for the day.
            max_daily_trades (int): Max number of trades allowed per day. Default 5.
            max_daily_loss_pct (float): Max daily loss as fraction of capital (e.g. 0.02 = 2%). Default 2%.
        """
        self.account_id = account_id
        self.capital = capital
        self.max_daily_trades = max_daily_trades
        self.max_daily_loss_pct = max_daily_loss_pct

        self._open_positions: dict[str, EquityPosition] = {}   # trade_id -> EquityPosition
        self._closed_positions: list[EquityPosition] = []
        self._daily_trade_count = 0
        self._daily_realized_pnl = 0.0

        logger.info(f"EquityAccountManager initialized: {account_id}, capital=₹{capital:,.0f}")

    # ------------------------------------------------------------------ #
    # Position management
    # ------------------------------------------------------------------ #

    def add_position(self, position: EquityPosition):
        """Register a new open position."""
        self._open_positions[position.trade_id] = position
        self._daily_trade_count += 1
        logger.info(f"[{self.account_id}] Position opened: {position.symbol} {position.direction} qty={position.quantity} @ ₹{position.entry_price}")

    def close_position(self, trade_id: str, close_price: float, close_time: str) -> dict | None:
        """
        Close an open position and move it to closed history.

        Returns:
            dict: Closed position summary, or None if trade_id not found.
        """
        position = self._open_positions.pop(trade_id, None)
        if position is None:
            logger.warning(f"[{self.account_id}] Attempted to close unknown trade {trade_id}")
            return None

        position.close(close_price, close_time)
        self._closed_positions.append(position)
        self._daily_realized_pnl += position.pnl
        logger.info(f"[{self.account_id}] Position closed: {position.symbol} PnL=₹{position.pnl:,.2f}")
        return position.to_dict()

    def get_open_positions(self) -> list[dict]:
        """Return list of all open position dicts."""
        return [deepcopy(p.to_dict()) for p in self._open_positions.values()]

    def get_position(self, trade_id: str) -> EquityPosition | None:
        return self._open_positions.get(trade_id)

    # ------------------------------------------------------------------ #
    # Risk and limit checks
    # ------------------------------------------------------------------ #

    def can_trade(self) -> tuple[bool, str]:
        """
        Check if a new trade is allowed under daily limits.

        Returns:
            (bool, str): (allowed, reason)
        """
        if self._daily_trade_count >= self.max_daily_trades:
            return False, f"Daily trade limit reached ({self.max_daily_trades})"

        max_loss = self.capital * self.max_daily_loss_pct
        if self._daily_realized_pnl <= -max_loss:
            return False, f"Daily loss limit breached (₹{self._daily_realized_pnl:,.2f} / limit ₹{-max_loss:,.2f})"

        return True, "OK"

    def is_squareoff_required(self) -> bool:
        """
        Return True if current IST time is at or past the MIS squareoff deadline (3:15 PM).
        """
        now_ist = datetime.now(IST).time()
        return now_ist >= SQUAREOFF_DEADLINE

    def get_symbols_to_squareoff(self) -> list[str]:
        """Return symbols with open positions that must be squared off."""
        return [p.symbol for p in self._open_positions.values()]

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def get_account_summary(self) -> dict:
        """
        Return a full account state summary for reporting to the orchestrator.
        """
        total_unrealized = 0.0  # Would require current prices — left as 0 here
        return {
            "account_id": self.account_id,
            "capital": self.capital,
            "daily_trade_count": self._daily_trade_count,
            "max_daily_trades": self.max_daily_trades,
            "daily_realized_pnl": round(self._daily_realized_pnl, 2),
            "open_positions": len(self._open_positions),
            "closed_positions": len(self._closed_positions),
            "squareoff_required": self.is_squareoff_required(),
        }

    def reset_daily_state(self):
        """
        Reset daily counters. Call at start of each trading day.
        Open positions should have been squared off before calling this.
        """
        if self._open_positions:
            logger.warning(f"[{self.account_id}] reset_daily_state called with {len(self._open_positions)} open positions — squareoff first!")
        self._daily_trade_count = 0
        self._daily_realized_pnl = 0.0
        self._closed_positions = []
        logger.info(f"[{self.account_id}] Daily state reset.")
