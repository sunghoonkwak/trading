# -*- coding: utf-8 -*-
"""Application-owned facade for Toss portfolio retrieval."""

from typing import Any, Dict, Optional, Tuple


TOSS_OWNER_ID = "owner_01"
TOSS_ACCOUNT_NAME = "토스"
TOSS_ACCOUNT_KEY = f"{TOSS_ACCOUNT_NAME}_{TOSS_OWNER_ID}"
TOSS_DEFAULT_ACCOUNT_SEQ = 1


def _empty_source() -> Dict[str, Any]:
    return {
        "accounts": {},
        "holdings": [],
        "asset_info": {},
        "cash_holdings": [],
    }


def _to_float(value: Any, field_name: str) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Toss {field_name} is not numeric: {value!r}") from exc


def _toss_market(country: str, currency: str) -> str:
    if country in {"KR", "US"}:
        return country
    return "KR" if currency == "KRW" else "US"


def fetch_toss_portfolio(
    account_seq: int = TOSS_DEFAULT_ACCOUNT_SEQ,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Fetch Toss holdings and buying power in the standard source format."""
    from toss.get_buying_power import get_buying_power
    from toss.get_holdings import get_holdings
    from toss.get_prices import load_access_token

    access_token = load_access_token()
    holdings_result = get_holdings(
        account_seq=account_seq,
        access_token=access_token,
    )

    toss_data = _empty_source()
    toss_data["accounts"][TOSS_ACCOUNT_KEY] = {
        "name": TOSS_ACCOUNT_NAME,
        "owner_id": TOSS_OWNER_ID,
    }

    for item in holdings_result.get("items", []):
        ticker = str(item.get("symbol", "")).strip()
        if not ticker:
            continue

        qty = _to_float(item.get("quantity"), "quantity")
        if qty <= 0:
            continue

        name = str(item.get("name") or ticker)
        currency = str(item.get("currency") or "USD").upper()
        market_country = str(item.get("marketCountry") or "")
        market = _toss_market(market_country, currency)
        avg_price = _to_float(item.get("averagePurchasePrice"), "averagePurchasePrice")
        cur_price = _to_float(item.get("lastPrice"), "lastPrice")

        toss_data["asset_info"][ticker] = {
            "name": name,
            "market": market,
            "asset_type": "Stock",
            "currency": currency,
        }
        toss_data["holdings"].append(
            {
                "account_key": TOSS_ACCOUNT_KEY,
                "ticker": ticker,
                "name": name,
                "qty": qty,
                "avg_price": avg_price,
                "cur_price": cur_price,
            }
        )

    for currency in ["KRW", "USD"]:
        buying_power = get_buying_power(
            account_seq=account_seq,
            currency=currency,
            access_token=access_token,
        )
        amount = _to_float(buying_power.get("cashBuyingPower"), "cashBuyingPower")
        if amount <= 0:
            continue

        toss_data["cash_holdings"].append(
            {
                "account_name": TOSS_ACCOUNT_NAME,
                "account_key": TOSS_ACCOUNT_KEY,
                "amount": amount,
                "currency": currency,
            }
        )

    return toss_data, None
