import os
from typing import Any
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("alpaca-trading")


API_KEY    = os.getenv("ALPACA_API_KEY") or os.getenv("API_KEY_ID")
API_SECRET = os.getenv("ALPACA_SECRET_KEY") or os.getenv("API_SECRET_KEY")

if not API_KEY or not API_SECRET:
    raise ValueError(
        "Alpaca API credentials not found. "
        "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in Render's Environment tab."
    )

# FIX 2: paper mode derived from env var, not hardcoded
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
IS_PAPER = "paper-api" in ALPACA_BASE_URL

trading_client = TradingClient(API_KEY, API_SECRET, paper=IS_PAPER)
stock_client   = StockHistoricalDataClient(API_KEY, API_SECRET)


@mcp.tool()
async def get_account_info() -> str:
    """Get current account information including balances and status."""
    account = trading_client.get_account()
    return f"""Account Information:
-------------------
Account ID: {account.id}
Status: {account.status}
Currency: {account.currency}
Buying Power: ${float(account.buying_power):.2f}
Cash: ${float(account.cash):.2f}
Portfolio Value: ${float(account.portfolio_value):.2f}
Equity: ${float(account.equity):.2f}
Long Market Value: ${float(account.long_market_value):.2f}
Short Market Value: ${float(account.short_market_value):.2f}
Pattern Day Trader: {'Yes' if account.pattern_day_trader else 'No'}
Mode: {'Paper' if IS_PAPER else 'LIVE'}
"""

@mcp.tool()
async def get_positions() -> str:
    """Get all current positions in the portfolio."""
    positions = trading_client.get_all_positions()
    if not positions:
        return "No open positions found."
    result = "Current Positions:\n-------------------\n"
    for p in positions:
        result += f"""Symbol: {p.symbol}
Quantity: {p.qty} shares
Market Value: ${float(p.market_value):.2f}
Avg Entry: ${float(p.avg_entry_price):.2f}
Current Price: ${float(p.current_price):.2f}
Unrealized P/L: ${float(p.unrealized_pl):.2f} ({float(p.unrealized_plpc)*100:.2f}%)
-------------------
"""
    return result

@mcp.tool()
async def get_stock_quote(symbol: str) -> str:
    """Get the latest quote for a stock. Args: symbol e.g. AAPL"""
    try:
        quotes = stock_client.get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=symbol.upper()))
        if symbol.upper() in quotes:
            q = quotes[symbol.upper()]
            return f"Latest Quote {symbol.upper()}: Ask=${q.ask_price:.2f} Bid=${q.bid_price:.2f} @ {q.timestamp}"
        return f"No quote data for {symbol}."
    except Exception as e:
        return f"Error fetching quote for {symbol}: {e}"

@mcp.tool()
async def get_stock_bars(symbol: str, days: int = 5) -> str:
    """Get historical price bars. Args: symbol, days (default 5)"""
    try:
        bars = stock_client.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=symbol.upper(),
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=days)
        ))
        sym = symbol.upper()
        if sym in bars and bars[sym]:
            lines = [f"Historical Data {sym} (last {days} days):"]
            for b in bars[sym]:
                lines.append(f"{b.timestamp.date()}  O={b.open:.2f} H={b.high:.2f} L={b.low:.2f} C={b.close:.2f} V={b.volume}")
            return "\n".join(lines)
        return f"No historical data for {symbol}."
    except Exception as e:
        return f"Error fetching bars for {symbol}: {e}"

@mcp.tool()
async def get_orders(status: str = "all", limit: int = 10) -> str:
    """Get orders. Args: status (open/closed/all), limit (default 10)"""
    try:
        status_map = {"open": QueryOrderStatus.OPEN, "closed": QueryOrderStatus.CLOSED}
        orders = trading_client.get_orders(GetOrdersRequest(
            status=status_map.get(status.lower(), QueryOrderStatus.ALL),
            limit=limit
        ))
        if not orders:
            return f"No {status} orders found."
        lines = [f"{status.capitalize()} Orders ({len(orders)}):"]
        for o in orders:
            lines.append(f"{o.symbol} | {o.side} {o.qty} | {o.type} | {o.status} | {o.submitted_at}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching orders: {e}"

@mcp.tool()
async def place_market_order(symbol: str, side: str, quantity: float) -> str:
    """Place a market order. Args: symbol, side (buy/sell), quantity"""
    try:
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order = trading_client.submit_order(MarketOrderRequest(
            symbol=symbol.upper(), qty=quantity,
            side=order_side, time_in_force=TimeInForce.DAY))
        return f"Market order placed: {order.side} {order.qty} {order.symbol} | ID={order.id} | Status={order.status}"
    except Exception as e:
        return f"Error placing market order: {e}"

@mcp.tool()
async def place_limit_order(symbol: str, side: str, quantity: float, limit_price: float) -> str:
    """Place a limit order. Args: symbol, side (buy/sell), quantity, limit_price"""
    try:
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order = trading_client.submit_order(LimitOrderRequest(
            symbol=symbol.upper(), qty=quantity, side=order_side,
            time_in_force=TimeInForce.DAY, limit_price=limit_price))
        return f"Limit order placed: {order.side} {order.qty} {order.symbol} @ ${float(order.limit_price):.2f} | ID={order.id} | Status={order.status}"
    except Exception as e:
        return f"Error placing limit order: {e}"

@mcp.tool()
async def cancel_all_orders() -> str:
    """Cancel all open orders."""
    try:
        trading_client.cancel_orders()
        return "All open orders cancelled."
    except Exception as e:
        return f"Error cancelling orders: {e}"

@mcp.tool()
async def close_all_positions(cancel_orders: bool = True) -> str:
    """Close all open positions. Args: cancel_orders (default True)"""
    try:
        trading_client.close_all_positions(cancel_orders=cancel_orders)
        return "All positions closed."
    except Exception as e:
        return f"Error closing positions: {e}"



if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"Starting alpaca-mcp-server (SSE transport) on port {port}  paper={IS_PAPER}")
    mcp.run(transport="sse")
