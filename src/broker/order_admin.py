# -*- coding: utf-8 -*-
"""Application-owned facade for open-order administration."""


def _wrapper_fetch_open_orders():
    from kis.wrapper import fetch_open_orders as kis_fetch_open_orders

    return kis_fetch_open_orders()


def _wrapper_execute_manage_action(market, action_type, order_data, new_price=None):
    from kis.wrapper import execute_manage_action as kis_execute_manage_action

    return kis_execute_manage_action(market, action_type, order_data, new_price)


def _wrapper_sync_open_orders():
    from kis.wrapper import sync_open_orders as kis_sync_open_orders

    return kis_sync_open_orders()


def fetch_open_orders():
    """Fetch open orders through the existing KIS wrapper."""
    return _wrapper_fetch_open_orders()


def execute_manage_action(market, action_type, order_data, new_price=None):
    """Execute an order management action through the existing KIS wrapper."""
    return _wrapper_execute_manage_action(market, action_type, order_data, new_price)


def sync_open_orders():
    """Sync open orders into display state through the existing KIS wrapper."""
    return _wrapper_sync_open_orders()
