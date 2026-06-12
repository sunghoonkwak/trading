# -*- coding: utf-8 -*-
"""Broker-owned portfolio source entrypoints."""

from broker.toss_portfolio import TOSS_ACCOUNT_KEY


def fetch_kis_source():
    """Fetch the KIS portfolio source through the KIS broker facade."""
    from broker.kis_portfolio import fetch_kis_portfolio

    return fetch_kis_portfolio()


def fetch_toss_source():
    """Fetch the Toss portfolio source through the Toss broker facade."""
    from broker.toss_portfolio import fetch_toss_portfolio

    return fetch_toss_portfolio()
