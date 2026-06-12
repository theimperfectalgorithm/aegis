"""
Market Data module for AEGIS Core.

Provides market data fetching for all agents.
Currently implements:
    - KiteMarketDataFetcher: Fetches NSE OHLC candles from Zerodha Kite Connect
    - CandleNormalizer: Normalises raw candles into AEGIS standard format

AEGIS standard candle format:
    {
        'timestamp': str    # ISO8601 UTC (or IST)
        'symbol': str       # NSE symbol e.g. 'RELIANCE'
        'open': float
        'high': float
        'low': float
        'close': float
        'volume': int
    }

Zerodha Kite Connect docs: https://kite.trade/docs/connect/v3/market-quotes/
Install: pip install kiteconnect
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger("AEGIS.MarketData")

# ---- AEGIS Nifty 50 default watchlist --------------------------------- #
# Full list of current Nifty 50 constituents (as of June 2026).
# Update quarterly when Nifty 50 rebalances.
NIFTY_50_SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC",
    "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LTIM",
    "LT", "M&M", "MARUTI", "NTPC", "NESTLEIND",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN",
    "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS",
    "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO",
]


# ============================================================= #
# Candle normalizer
# ============================================================= #

class CandleNormalizer:
    """
    Converts raw broker candle formats into the AEGIS standard candle dict.
    Add new broker formats here as static methods.
    """

    @staticmethod
    def from_kite(raw_candles: list, symbol: str) -> list:
        """
        Normalise Kite Connect historical_data() response.

        Kite raw format: list of [datetime, open, high, low, close, volume]

        Args:
            raw_candles: Raw list from kite.historical_data()
            symbol: NSE symbol string

        Returns:
            list[dict]: AEGIS standard candle dicts sorted ascending by timestamp.
        """
        normalized = []
        for c in raw_candles:
            if isinstance(c, dict):
                # Some Kite SDK versions return dicts
                ts = c.get("date") or c.get("timestamp")
                normalized.append({
                    "timestamp": _to_ist_str(ts),
                    "symbol": symbol,
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("high", 0)),
                    "low": float(c.get("low", 0)),
                    "close": float(c.get("close", 0)),
                    "volume": int(c.get("volume", 0)),
                })
            else:
                # List format: [datetime, open, high, low, close, volume]
                ts, o, h, lo, cl, vol = c
                normalized.append({
                    "timestamp": _to_ist_str(ts),
                    "symbol": symbol,
                    "open": float(o),
                    "high": float(h),
                    "low": float(lo),
                    "close": float(cl),
                    "volume": int(vol),
                })
        return sorted(normalized, key=lambda x: x["timestamp"])

    @staticmethod
    def from_dict_list(raw: list, symbol: str) -> list:
        """
        Normalise a generic list of OHLCV dicts.
        Expects keys: timestamp/date, open, high, low, close, volume.
        """
        normalized = []
        for c in raw:
            ts = c.get("timestamp") or c.get("date") or c.get("time")
            normalized.append({
                "timestamp": _to_ist_str(ts) if ts else "",
                "symbol": symbol,
                "open": float(c.get("open", 0)),
                "high": float(c.get("high", 0)),
                "low": float(c.get("low", 0)),
                "close": float(c.get("close", 0)),
                "volume": int(c.get("volume", 0)),
            })
        return sorted(normalized, key=lambda x: x["timestamp"])


def _to_ist_str(ts) -> str:
    """Convert various timestamp formats to ISO8601 IST string."""
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = IST.localize(ts)
        else:
            ts = ts.astimezone(IST)
        return ts.isoformat()
    return str(ts)


# ============================================================= #
# Kite market data fetcher
# ============================================================= #

class KiteMarketDataFetcher:
    """
    Fetches NSE OHLC candle data from Zerodha Kite Connect.

    Requires:
        pip install kiteconnect
        A valid Kite API key and daily access token.

    Usage:
        fetcher = KiteMarketDataFetcher(api_key="...", access_token="...")
        candles = fetcher.get_intraday_candles("RELIANCE", interval="15minute")

    Supported intervals (Kite): minute, 3minute, 5minute, 10minute, 15minute,
                                  30minute, 60minute, day
    """

    def __init__(self, api_key: str, access_token: str):
        try:
            from kiteconnect import KiteConnect
        except ImportError:
            raise ImportError("kiteconnect not installed. Run: pip install kiteconnect")

        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)
        self._instrument_cache: dict = {}   # symbol -> instrument_token
        logger.info("KiteMarketDataFetcher initialized.")

    def get_instrument_token(self, symbol: str, exchange: str = "NSE") -> Optional[int]:
        """
        Look up the Kite instrument token for a given NSE symbol.
        Tokens are required for historical data requests.

        Caches results in memory for the session.
        """
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self._instrument_cache:
            return self._instrument_cache[cache_key]

        try:
            instruments = self.kite.instruments(exchange)
            for inst in instruments:
                if inst["tradingsymbol"] == symbol:
                    token = inst["instrument_token"]
                    self._instrument_cache[cache_key] = token
                    return token
        except Exception as e:
            logger.error(f"Failed to fetch instruments for {exchange}: {e}")

        return None

    def get_intraday_candles(
        self,
        symbol: str,
        interval: str = "15minute",
        exchange: str = "NSE",
        date: Optional[datetime] = None,
    ) -> list:
        """
        Fetch intraday OHLC candles for a single symbol on a given date.

        Args:
            symbol (str): NSE symbol, e.g. 'RELIANCE'
            interval (str): Candle interval. Default '15minute'.
            exchange (str): Exchange. Default 'NSE'.
            date (datetime): Trading date in IST. Defaults to today.

        Returns:
            list[dict]: AEGIS standard candle dicts sorted ascending by timestamp.
        """
        if date is None:
            date = datetime.now(IST)

        from_dt = date.replace(hour=9, minute=15, second=0, microsecond=0)
        to_dt = date.replace(hour=15, minute=30, second=0, microsecond=0)

        token = self.get_instrument_token(symbol, exchange)
        if token is None:
            logger.error(f"Could not find instrument token for {symbol}. Skipping.")
            return []

        try:
            raw = self.kite.historical_data(
                instrument_token=token,
                from_date=from_dt,
                to_date=to_dt,
                interval=interval,
                continuous=False,
            )
            candles = CandleNormalizer.from_kite(raw, symbol)
            logger.info(f"Fetched {len(candles)} candles for {symbol} ({interval}) on {from_dt.date()}")
            return candles

        except Exception as e:
            logger.error(f"Failed to fetch candles for {symbol}: {e}")
            return []

    def get_bulk_intraday_candles(
        self,
        symbols: list,
        interval: str = "15minute",
        exchange: str = "NSE",
        date: Optional[datetime] = None,
    ) -> dict:
        """
        Fetch intraday candles for multiple symbols.

        Returns:
            dict: {symbol: [candle dicts]}
        """
        result = {}
        for symbol in symbols:
            result[symbol] = self.get_intraday_candles(symbol, interval, exchange, date)
        return result

    def get_last_price(self, symbols: list, exchange: str = "NSE") -> dict:
        """
        Fetch the last traded price for a list of symbols.

        Returns:
            dict: {symbol: last_price}
        """
        try:
            exchange_symbols = [f"{exchange}:{s}" for s in symbols]
            quotes = self.kite.ltp(exchange_symbols)
            return {
                s: quotes.get(f"{exchange}:{s}", {}).get("last_price", 0.0)
                for s in symbols
            }
        except Exception as e:
            logger.error(f"Failed to fetch LTP: {e}")
            return {s: 0.0 for s in symbols}


# ============================================================= #
# Mock data fetcher for testing (no API key needed)
# ============================================================= #

class MockMarketDataFetcher:
    """
    Returns synthetic intraday candles for testing without a broker connection.

    Usage:
        fetcher = MockMarketDataFetcher()
        candles = fetcher.get_intraday_candles("RELIANCE")
    """

    def get_intraday_candles(self, symbol: str, base_price: float = 2500.0, interval: str = "15minute") -> list:
        """
        Generate synthetic 15-min candles from 9:15 AM to 3:30 PM IST.

        The first candle (9:15–9:30) forms the opening range.
        The second candle (9:30–9:45) simulates a breakout above the range.
        """
        import random
        today = datetime.now(IST).replace(hour=9, minute=15, second=0, microsecond=0)
        candles = []
        price = base_price
        times_ist = [
            today.replace(hour=9, minute=15),
            today.replace(hour=9, minute=30),
            today.replace(hour=9, minute=45),
            today.replace(hour=10, minute=0),
            today.replace(hour=10, minute=15),
            today.replace(hour=10, minute=30),
        ]

        for i, ts in enumerate(times_ist):
            o = round(price, 2)
            h = round(price + random.uniform(2, 8), 2)
            lo = round(price - random.uniform(2, 5), 2)
            cl = round(random.uniform(lo, h), 2)

            # Force a breakout on the second candle (after range formation)
            if i == 1:
                h = round(o + 15, 2)   # Spike above range
                cl = round(o + 12, 2)   # Close above opening range high

            candles.append({
                "timestamp": ts.isoformat(),
                "symbol": symbol,
                "open": o,
                "high": h,
                "low": lo,
                "close": cl,
                "volume": random.randint(50000, 300000),
            })
            price = cl

        return candles

    def get_bulk_intraday_candles(self, symbols: list, **kwargs) -> dict:
        return {s: self.get_intraday_candles(s) for s in symbols}

    def get_last_price(self, symbols: list, **kwargs) -> dict:
        return {s: 2500.0 for s in symbols}
