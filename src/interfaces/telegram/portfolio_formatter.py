"""Telegram presentation helpers for portfolio application results."""

from collections.abc import Callable


def format_portfolio_summary(
    data: dict,
    get_fear_and_greed: Callable[[], float],
) -> str:
    """Format portfolio summary result data for a Telegram message."""
    if data.get("error"):
        return f"⚠️ <b>Error:</b> {data['error']}"
    fg_index = int(get_fear_and_greed())
    stats = data.get("stats", {})
    total_usd = data.get("total_value_usd", 0)
    rate = data.get("exchange_rate", 0)
    total_krw = total_usd * rate if rate > 0 else 0
    lines = [
        f"💰 <b>Portfolio Summary</b> (Rate: {rate:,.1f} | F&G: {fg_index})",
        "",
        f"<b>Total</b>: <b>${total_usd/1000:,.1f}K</b> (₩{total_krw/1000000:,.1f}M)",
        f"<b>Cash</b>: <b>{stats.get('total_cash_usd', 0) / total_usd * 100 if total_usd > 0 else 0:.1f}%</b>",
        "",
        f"🇺🇸 <b>US Assets</b>: ${stats.get('us_stock_usd', 0) + stats.get('us_cash_usd', 0) / 1000:,.1f}K ({stats.get('us_pct', 0):.1f}%)",
        f"  Stock: ${stats.get('us_stock_usd', 0)/1000:,.1f}K | Cash: {stats.get('us_cash_ratio', 0):.1f}%",
        f"🇰🇷 <b>KR Assets</b>: ₩{(stats.get('kr_stock_krw', 0) + stats.get('kr_cash_krw', 0))/1000000:,.1f}M ({stats.get('kr_pct', 0):.1f}%)",
        f"  Stock: ₩{stats.get('kr_stock_krw', 0)/1000000:,.1f}M | Cash: {stats.get('kr_cash_ratio', 0):.1f}%",
        "",
        "📊 <i>Select a ticker below or type directly:</i>",
    ]
    return "\n".join(lines)
