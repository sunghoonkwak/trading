# -*- coding: utf-8 -*-
"""Application-owned facade for open-order administration."""

from core import trading_config
from core.display import add_alert, clear_order_states, update_order_state


def _get_order_manager():
    from kis.order_manager import OrderManager

    return OrderManager


def _manager_fetch_open_orders():
    return _get_order_manager().fetch_open_orders()


def _manager_execute_action(market, action_type, order_data, new_price=None):
    return _get_order_manager().execute_action(market, action_type, order_data, new_price)


def fetch_open_orders():
    """Fetch open orders through OrderManager."""
    return _manager_fetch_open_orders()


def execute_manage_action(market, action_type, order_data, new_price=None):
    """Execute an order management action through OrderManager."""
    return _manager_execute_action(market, action_type, order_data, new_price)


def _sync_display_open_orders():
    add_alert("[ORD] Syncing open orders...", "INFO")
    clear_order_states()
    try:
        df, num_us, num_kr = fetch_open_orders()
        add_alert(f"[ORD] updated! Orders US/KR : {num_us} / {num_kr}", "SUCCESS")
        if not df.empty:
            for _, row in df.iterrows():
                row_l = {k.lower(): v for k, v in row.items()}
                odno = row_l.get('odno', row_l.get('ord_no', 'Unknown'))
                pdno = row_l.get('pdno', row_l.get('stck_shrn_iscd', 'Unknown'))
                api_name = row_l.get(
                    'prdt_name',
                    row_l.get('stck_nm', row_l.get('stck_nm40', 'Unknown')),
                )

                trading_config.update_stock_name(pdno, api_name)
                stock_info = trading_config.get_stock_info(pdno)
                market = row.get('_market', 'US')

                if market == "KR":
                    side = "Buy" if row_l.get('sll_buy_dvsn_cd') == '02' else "Sell"
                    price = str(int(float(row_l.get('ord_unpr', '0'))))
                    qty = str(row_l.get('psbl_qty', 0))
                else:
                    side_text = row_l.get(
                        'sll_buy_dvsn_cd_name',
                        row_l.get('sll_buy_dvsn_name', ''),
                    ).strip()
                    if not side_text or side_text in ['?', 'nan', 'None', '']:
                        side = "Buy" if row_l.get('sll_buy_dvsn_cd') == '02' else "Sell"
                    elif "매수" in side_text:
                        side = side_text.replace("매수", " Buy")
                    elif "매도" in side_text:
                        side = side_text.replace("매도", " Sell")
                    else:
                        side = side_text

                    p_val = row_l.get(
                        'ft_ord_unpr3',
                        row_l.get(
                            'ft_ord_unpr4',
                            row_l.get('ovrs_ord_unpr', row_l.get('ord_unpr', '0')),
                        ),
                    )
                    try:
                        p_float = float(p_val)
                        price = f"{p_float:.2f}" if p_float > 0 else "Market"
                    except Exception:
                        price = "0"

                    q_val = row_l.get(
                        'nccs_qty',
                        row_l.get('ft_ord_qty4', row_l.get('ord_qty', 0)),
                    )
                    qty = str(int(float(q_val)))

                raw_time = row_l.get('ord_tmd', '')
                time_str = None
                if raw_time and len(raw_time) == 6:
                    time_str = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:]}"

                update_order_state(
                    odno,
                    pdno,
                    stock_info.get('name', api_name),
                    side,
                    price,
                    qty,
                    "PLACED",
                    notify=False,
                    time_str=time_str,
                )
        return True
    except Exception as e:
        add_alert(f"Sync failed: {e}", "ERROR")
        return None


def sync_open_orders():
    """Sync open orders into display state."""
    return _sync_display_open_orders()
