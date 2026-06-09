# -*- coding: utf-8 -*-
"""Application-owned facade for open-order administration."""


def _get_order_manager():
    from kis.order_manager import OrderManager

    return OrderManager


def _manager_fetch_open_orders():
    return _get_order_manager().fetch_open_orders()


def _manager_execute_action(market, action_type, order_data, new_price=None):
    return _get_order_manager().execute_action(market, action_type, order_data, new_price)


def _wrapper_sync_open_orders():
    from kis.wrapper import sync_open_orders as kis_sync_open_orders

    return kis_sync_open_orders()


def fetch_open_orders():
    """Fetch open orders through OrderManager."""
    return _manager_fetch_open_orders()


def execute_manage_action(market, action_type, order_data, new_price=None):
    """Execute an order management action through OrderManager."""
    return _manager_execute_action(market, action_type, order_data, new_price)


def sync_open_orders():
    """Sync open orders into display state through the existing KIS wrapper."""
    return _wrapper_sync_open_orders()
