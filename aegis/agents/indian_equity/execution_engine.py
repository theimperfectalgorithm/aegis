"""
Execution Engine for AEGIS Indian Equity Agent.

Provides two engines:
    1. KitePaperExecutionEngine  — Full paper trading simulation, no broker needed.
       Mirrors the Forex PaperExecutionEngine pattern for cross-agent consistency.
       Use this for backtesting, data collection, and development.

    2. KiteLiveExecutionEngine   — Real Zerodha Kite Connect integration.
       Requires a valid Kite API key and access token.
       Use this for live/semi-live trading once the strategy is validated.

Zerodha Kite Connect docs: https://kite.trade/docs/connect/v3/
Install: pip install kiteconnect
"""

import uuid
import logging
from collections import defaultdict
from copy import deepcopy
from abc import ABC, abstractmethod

logger = logging.getLogger("AEGIS.EquityExecutionEngine")


# ============================================================= #
# Abstract base
# ============================================================= #

class BaseEquityExecutionEngine(ABC):
    """
    Abstract interface all equity execution engines must implement.
    Keeps the EquityAgent and TradeDecisionPipeline broker-agnostic.
    """

    @abstractmethod
    def place_trade(self, account_id: str, order: dict) -> dict:
        """
        Place an equity order.

        Args:
            account_id (str): Account identifier.
            order (dict): Must contain:
                - 'symbol' (str): NSE symbol, e.g. 'RELIANCE'
                - 'side' (str): 'buy' or 'sell'
                - 'price' (float): Limit/market price
                - 'quantity' (int): Number of shares
                - 'stop_loss' (float)
                - 'take_profit' (float)
                - 'product' (str): 'MIS' (intraday) or 'CNC' (delivery)
                - 'exchange' (str): 'NSE' or 'BSE'
                - 'timestamp' (str): ISO8601 timestamp

        Returns:
            dict: Fill result with 'trade_id', 'entry_price', 'status', etc.
        """
        pass

    @abstractmethod
    def close_trade(self, account_id: str, trade_id: str, close_price: float = None, close_time: str = None) -> dict:
        pass

    @abstractmethod
    def get_open_positions(self, account_id: str) -> list:
        pass


# ============================================================= #
# Paper execution engine (no broker required)
# ============================================================= #

class KitePaperExecutionEngine(BaseEquityExecutionEngine):
    """
    Paper execution engine for Indian equities.

    Simulates immediate order fills with optional slippage.
    Tracks open and closed positions in memory.
    Structurally identical to the Forex PaperExecutionEngine for cross-agent ML consistency.

    Usage:
        engine = KitePaperExecutionEngine(slippage_pct=0.0005)
        fill = engine.place_trade("NSE001", order)
    """

    def __init__(self, slippage_pct: float = 0.0005):
        """
        Args:
            slippage_pct (float): Slippage applied to fill price as fraction of price.
                                  Default 0.05% — typical for Nifty 50 large-caps.
        """
        self.slippage_pct = slippage_pct
        self._open_positions: dict[str, list] = defaultdict(list)   # account_id -> [trade dicts]
        self._closed_positions: dict[str, list] = defaultdict(list)

    def place_trade(self, account_id: str, order: dict) -> dict:
        """Simulate an immediate fill with slippage."""
        price = order.get("price", 0.0)
        side = order.get("side", "buy").lower()
        quantity = order.get("quantity", 0)

        # Apply slippage: buyer pays slightly more, seller receives slightly less
        slippage = price * self.slippage_pct
        fill_price = price + slippage if side == "buy" else price - slippage

        trade_id = str(uuid.uuid4())
        trade = deepcopy(order)
        trade.update({
            "trade_id": trade_id,
            "entry_price": round(fill_price, 2),
            "fill_quantity": quantity,
            "direction": side.upper(),
            "status": "open",
            "open_time": order.get("timestamp"),
            "slippage": round(slippage, 4),
            "exchange": order.get("exchange", "NSE"),
            "product": order.get("product", "MIS"),
        })
        self._open_positions[account_id].append(trade)

        logger.info(
            f"[PAPER] {account_id} | {order.get('symbol')} {side.upper()} "
            f"qty={quantity} @ ₹{fill_price:.2f} (slippage ₹{slippage:.2f}) | trade_id={trade_id}"
        )
        return {
            "trade_id": trade_id,
            "entry_price": round(fill_price, 2),
            "quantity": quantity,
            "direction": side.upper(),
            "status": "filled",
            "slippage": round(slippage, 4),
            "timestamp": order.get("timestamp"),
        }

    def close_trade(self, account_id: str, trade_id: str, close_price: float = None, close_time: str = None) -> dict:
        """Simulate closing a position and compute P&L."""
        trades = self._open_positions[account_id]
        for i, trade in enumerate(trades):
            if trade["trade_id"] == trade_id:
                entry_price = trade["entry_price"]
                quantity = trade.get("fill_quantity", trade.get("quantity", 0))
                direction = trade.get("direction", "BUY")
                exit_price = close_price if close_price is not None else entry_price

                # Apply exit slippage
                slippage = exit_price * self.slippage_pct
                exit_price = exit_price - slippage if direction == "BUY" else exit_price + slippage

                pnl = (exit_price - entry_price) * quantity if direction == "BUY" else (entry_price - exit_price) * quantity

                trade["status"] = "closed"
                trade["close_price"] = round(exit_price, 2)
                trade["close_time"] = close_time
                trade["pnl"] = round(pnl, 2)

                self._closed_positions[account_id].append(deepcopy(trade))
                del trades[i]

                logger.info(
                    f"[PAPER] {account_id} | Closed {trade.get('symbol')} {direction} "
                    f"@ ₹{exit_price:.2f} | PnL=₹{pnl:,.2f} | trade_id={trade_id}"
                )
                return {
                    "trade_id": trade_id,
                    "close_price": round(exit_price, 2),
                    "pnl": round(pnl, 2),
                    "status": "closed",
                    "timestamp": close_time,
                }

        logger.warning(f"[PAPER] {account_id} | Attempted to close unknown trade {trade_id}")
        return {"trade_id": trade_id, "status": "not_found"}

    def get_open_positions(self, account_id: str) -> list:
        return deepcopy(self._open_positions[account_id])

    def get_daily_pnl(self, account_id: str) -> float:
        """Return total realized P&L for all closed positions today."""
        return sum(t.get("pnl", 0.0) for t in self._closed_positions[account_id])


# ============================================================= #
# Live Zerodha Kite Connect execution engine
# ============================================================= #

class KiteLiveExecutionEngine(BaseEquityExecutionEngine):
    """
    Live execution engine using Zerodha Kite Connect API.

    Requires:
        pip install kiteconnect
        A valid Kite API key and daily-refreshed access token.

    Access token must be refreshed daily via the Kite login flow.
    See: https://kite.trade/docs/connect/v3/user/#authentication-and-token-generation

    Usage:
        engine = KiteLiveExecutionEngine(api_key="your_key", access_token="your_token")
        fill = engine.place_trade("NSE001", order)
    """

    def __init__(self, api_key: str, access_token: str):
        """
        Args:
            api_key (str): Zerodha Kite API key.
            access_token (str): Daily access token from Kite login flow.
        """
        try:
            from kiteconnect import KiteConnect
        except ImportError:
            raise ImportError("kiteconnect not installed. Run: pip install kiteconnect")

        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)
        self._order_map: dict[str, str] = {}   # internal trade_id -> Kite order_id
        logger.info("KiteLiveExecutionEngine initialized and connected.")

    def place_trade(self, account_id: str, order: dict) -> dict:
        """
        Place a real order via Zerodha Kite Connect.

        Maps AEGIS order structure to Kite order parameters.
        Returns fill result with Kite order_id as trade_id.
        """
        side = order.get("side", "buy").lower()
        transaction_type = self.kite.TRANSACTION_TYPE_BUY if side == "buy" else self.kite.TRANSACTION_TYPE_SELL

        try:
            kite_order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=order.get("exchange", "NSE"),
                tradingsymbol=order.get("symbol"),
                transaction_type=transaction_type,
                quantity=order.get("quantity"),
                product=self.kite.PRODUCT_MIS,           # Intraday MIS only
                order_type=self.kite.ORDER_TYPE_MARKET,  # Market order for ORB breakout entry
                tag="AEGIS_EQUITY",
            )
            trade_id = str(kite_order_id)
            self._order_map[trade_id] = kite_order_id

            logger.info(
                f"[KITE LIVE] {account_id} | {order.get('symbol')} {side.upper()} "
                f"qty={order.get('quantity')} | Kite order_id={kite_order_id}"
            )
            return {
                "trade_id": trade_id,
                "entry_price": order.get("price"),   # Actual fill price fetched separately via order history
                "quantity": order.get("quantity"),
                "direction": side.upper(),
                "status": "placed",
                "kite_order_id": kite_order_id,
                "timestamp": order.get("timestamp"),
            }

        except Exception as e:
            logger.error(f"[KITE LIVE] Order placement failed: {e}")
            return {"trade_id": None, "status": "failed", "error": str(e)}

    def close_trade(self, account_id: str, trade_id: str, close_price: float = None, close_time: str = None) -> dict:
        """
        Place a market squareoff order for an open position.
        Kite MIS positions can also be squared off via the positions API.
        """
        try:
            positions = self.kite.positions()
            day_positions = positions.get("day", [])

            for pos in day_positions:
                # Match by order_id stored in _order_map or by checking open quantity
                if str(pos.get("tradingsymbol")) == str(trade_id) or trade_id in self._order_map:
                    symbol = pos["tradingsymbol"]
                    qty = abs(pos.get("quantity", 0))
                    if qty == 0:
                        continue

                    # Determine squareoff direction (opposite of original position)
                    tx_type = self.kite.TRANSACTION_TYPE_SELL if pos["quantity"] > 0 else self.kite.TRANSACTION_TYPE_BUY

                    sq_order_id = self.kite.place_order(
                        variety=self.kite.VARIETY_REGULAR,
                        exchange="NSE",
                        tradingsymbol=symbol,
                        transaction_type=tx_type,
                        quantity=qty,
                        product=self.kite.PRODUCT_MIS,
                        order_type=self.kite.ORDER_TYPE_MARKET,
                        tag="AEGIS_SQUAREOFF",
                    )
                    logger.info(f"[KITE LIVE] Squareoff: {symbol} qty={qty} | order_id={sq_order_id}")
                    return {"trade_id": trade_id, "squareoff_order_id": sq_order_id, "status": "squaredoff"}

            return {"trade_id": trade_id, "status": "not_found"}

        except Exception as e:
            logger.error(f"[KITE LIVE] Squareoff failed: {e}")
            return {"trade_id": trade_id, "status": "failed", "error": str(e)}

    def get_open_positions(self, account_id: str) -> list:
        """Fetch current open positions from Kite."""
        try:
            positions = self.kite.positions()
            return [p for p in positions.get("day", []) if p.get("quantity", 0) != 0]
        except Exception as e:
            logger.error(f"[KITE LIVE] Failed to fetch positions: {e}")
            return []
