"""
Stock portfolio storage and price fetching utilities.

Portfolio format (data/portfolios.json):
  { "guild_id:user_id": { "AAPL": {"shares": 2.5, "avg_cost": 182.50}, ... } }

Each pancake is treated as $1 USD when buying/selling shares.
"""
import json
import asyncio
from pathlib import Path
import yfinance as yf

DATA_DIR = Path(__file__).parent.parent / "data"
_PORTFOLIO_FILE = DATA_DIR / "portfolios.json"


def _load() -> dict:
    if not _PORTFOLIO_FILE.exists():
        return {}
    with open(_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(_PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------

def get_portfolio(guild_id: int, user_id: int) -> dict:
    """Return {ticker: {"shares": float, "avg_cost": float}} for a user."""
    data = _load()
    key = f"{guild_id}:{user_id}"
    return data.get(key, {})


def set_portfolio(guild_id: int, user_id: int, portfolio: dict) -> None:
    """Save a user's portfolio, removing the key entirely if the portfolio is empty."""
    data = _load()
    key = f"{guild_id}:{user_id}"
    if portfolio:
        data[key] = portfolio
    else:
        data.pop(key, None)
    _save(data)


def get_all_guild_portfolios(guild_id: int) -> dict:
    """Return {user_id_str: {ticker: holding}} for every user in this guild."""
    data = _load()
    prefix = f"{guild_id}:"
    return {
        key[len(prefix):]: val
        for key, val in data.items()
        if key.startswith(prefix)
    }


def clear_guild_portfolios(guild_id: int) -> None:
    """Delete all portfolio entries for a guild (called at month-end liquidation)."""
    data = _load()
    prefix = f"{guild_id}:"
    for key in [k for k in data if k.startswith(prefix)]:
        del data[key]
    _save(data)


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------

def _fetch_price_sync(ticker: str) -> float | None:
    """Blocking call – run inside an executor to keep the event loop free."""
    try:
        t = yf.Ticker(ticker.upper())
        price = t.fast_info.last_price
        if price and price > 0:
            return float(price)
        # Fallback: last close from recent history
        hist = t.history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception:
        return None


async def get_stock_price(ticker: str) -> float | None:
    """Async wrapper for fetching a single stock's current price."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_price_sync, ticker.upper())


async def get_prices_bulk(tickers: set) -> dict:
    """Fetch prices for multiple tickers concurrently.
    Returns {ticker: price_or_None}.
    """
    results = await asyncio.gather(
        *[get_stock_price(t) for t in tickers],
        return_exceptions=False,
    )
    return dict(zip(tickers, results))


# ---------------------------------------------------------------------------
# Month-end liquidation
# ---------------------------------------------------------------------------

async def liquidate_guild_portfolios(guild_id: int) -> dict:
    """
    Liquidate every portfolio in the guild at current market prices.

    Returns {user_id_str: pancakes_received} so the caller can credit balances.
    Holdings that can't be priced fall back to their cost basis.
    """
    portfolios = get_all_guild_portfolios(guild_id)
    if not portfolios:
        return {}

    # Collect all unique tickers across all users
    all_tickers: set = set()
    for user_portfolio in portfolios.values():
        all_tickers.update(user_portfolio.keys())

    prices = await get_prices_bulk(all_tickers)

    payouts: dict = {}
    for user_id_str, user_portfolio in portfolios.items():
        total = 0
        for ticker, holding in user_portfolio.items():
            price = prices.get(ticker)
            if price and price > 0:
                total += int(holding["shares"] * price)
            else:
                # Fall back to cost basis so users don't lose pancakes to API issues
                total += int(holding["shares"] * holding["avg_cost"])
        payouts[user_id_str] = total

    return payouts
