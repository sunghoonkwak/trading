# -*- coding: utf-8 -*-
"""
Strategy execution application service.

This module handles the orchestration of strategy execution:
1. Unified 6-step flow for all strategies
2. Centralized market status & history management
3. Single integrated history file (strategy_history.json)
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from application.order_report_service import OrderReportService
from application.order_submission_service import DurableOrderSubmissionService
from application.strategy_run_service import (
    StrategyHistoryService,
    StrategyMarketDataService,
    StrategyRunService,
)
from domain.strategy import raoeo, rebalancing, value_averaging
from domain.strategy.base import OrderSide, StrategyOrder, StrategyStatus
from domain.strategy.constants import (
    ORDER_TYPE_LIMIT,
    STRATEGY_HISTORY_COMPACT_DATE_RE,
    STRATEGY_HISTORY_DATE_RE,
    TZ_ET,
)
from domain.strategy.pricing import resolve_current_price


@dataclass(frozen=True)
class StrategyExecutionDependencies:
    """Infrastructure collaborators supplied by the composition root."""

    load_strategy_config: Callable[[], Dict[str, Any]]
    load_history: Callable[[], List[Dict[str, Any]]]
    save_history: Callable[[List[Dict[str, Any]]], bool]
    fetch_prices: Callable[[List[str]], Dict[str, float]]
    strategy_broker_name: Callable[[], str]
    get_orderable_usd: Callable[[str, float], float]
    execute_order: Callable[[StrategyOrder], Tuple[bool, str]]
    portfolio_reader_factory: Callable[[], Any]
    get_market_status: Callable[[str], Dict[str, Any]]
    orderable_usd_cache: Dict[str, float] = field(default_factory=dict)


class StrategyExecutionRuntime:
    """Instance-owned collaborators for one configured strategy execution."""

    def __init__(self, dependencies: StrategyExecutionDependencies) -> None:
        self.dependencies = dependencies
        self._execution_lock = _strategy_execution_lock

    def market_data_service(self) -> StrategyMarketDataService:
        reader = self.dependencies.portfolio_reader_factory()
        return StrategyMarketDataService(
            load_portfolio=reader.get_portfolio_data,
            load_strategy_config=self.dependencies.load_strategy_config,
            fetch_prices=self.dependencies.fetch_prices,
            resolve_price=resolve_current_price,
            strategy_broker_name=self.dependencies.strategy_broker_name,
        )

    def order_report_service(self) -> OrderReportService:
        return OrderReportService(
            execute_order=self.dependencies.execute_order,
            sleep=time.sleep,
        )

    def order_submission_service(self) -> DurableOrderSubmissionService:
        return DurableOrderSubmissionService(self.order_report_service())

    def history_service(self) -> StrategyHistoryService:
        return StrategyHistoryService(
            load=self.dependencies.load_history,
            save=self.dependencies.save_history,
        )

    def strategy_run_service(self) -> StrategyRunService:
        """Expose this runtime's execution entry points without global lookup."""
        return StrategyRunService(
            run_raoeo=self.run_raoeo,
            run_value_averaging=self.run_value_averaging,
            run_rebalancing=self.run_rebalancing,
            run_suite=self.run_suite,
        )

    def run_raoeo(self, *, execute: bool = False, **kwargs: Any) -> Dict[str, Any]:
        with self._execution_lock:
            return _run_raoeo_strategy(
                dependencies=self.dependencies,
                execute=execute,
                context=kwargs.get("context"),
            )

    def run_value_averaging(
        self, *, execute: bool = False, **kwargs: Any
    ) -> Dict[str, Any]:
        with self._execution_lock:
            return _run_va_strategy(
                dependencies=self.dependencies,
                execute=execute,
                market_snapshot=kwargs.get("market_snapshot"),
                context=kwargs.get("context"),
            )

    def run_rebalancing(
        self, *, execute: bool = False, **kwargs: Any
    ) -> Dict[str, Any]:
        with self._execution_lock:
            return _run_rebalancing_strategy(
                dependencies=self.dependencies,
                execute=execute,
                orderable_cache_key=kwargs.get("orderable_cache_key", ""),
            )

    def run_suite(self, *, execute: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        with self._execution_lock:
            context = self._build_run_context()
            return (
                self.run_raoeo(execute=execute, context=context),
                self.run_value_averaging(execute=execute, context=context),
            )

    def clear_history(self, target_date: str = "") -> Dict[str, Any]:
        with self._execution_lock:
            target_date = normalize_strategy_history_date(target_date)
            return self.history_service().clear_date(target_date)

    def prepare_cash_funding(
        self,
        raoeo_report: Optional[Dict] = None,
        context: Optional["StrategyRunContext"] = None,
    ) -> Tuple[Any, Dict]:
        if raoeo_report is None:
            raoeo_report = self.run_raoeo(execute=False)

        pending_orders = raoeo_report.get("pending_orders", [])
        reference_buy = next(
            (order for order in pending_orders if order.side == OrderSide.BUY),
            None,
        )
        report_info = raoeo_report.get("info", {})
        holdings = report_info.get("holdings")
        prices = report_info.get("current_prices", {})
        if holdings is None:
            run_context = context or self._build_run_context()
            holdings, prices = run_context.get_market_data(
                force_refresh=True,
                include_cash_ticker=True,
            )

        orderable_usd = self._report_orderable_usd(report_info)
        if orderable_usd is None:
            orderable_usd = (
                self.dependencies.get_orderable_usd(
                    reference_buy.symbol, reference_buy.price
                )
                if reference_buy
                else 0.0
            )
        return raoeo.calculate_cash_funding_order(
            orders=pending_orders,
            portfolio=holdings,
            current_prices=prices,
            cash_ticker=self.dependencies.load_strategy_config().get("cash_ticker", ""),
            orderable_usd=orderable_usd,
        )

    def execute_cash_funding(
        self,
        raoeo_report: Optional[Dict] = None,
        context: Optional["StrategyRunContext"] = None,
    ) -> Tuple[Any, Dict]:
        order, info = self.prepare_cash_funding(raoeo_report, context=context)
        if not info.get("required") or order is None:
            return None, info

        with self._execution_lock:
            def persist_intent(submission_orders: List[StrategyOrder]) -> None:
                submitted_order = submission_orders[0]
                self._save_cash_funding_record(
                    datetime.now(TZ_ET).strftime("%Y-%m-%d"),
                    {
                        "order": submitted_order,
                        "success": False,
                        "message": "Submission started; reconcile before retrying.",
                        "ambiguous": True,
                    },
                )

            results = self.order_submission_service().submit(
                [order],
                persist_intent=persist_intent,
            )
            result = results[0]
            success, message = result["success"], result["message"]
            result = {
                "order": order,
                "success": success,
                "message": message,
                "ambiguous": message.startswith("[AMBIGUOUS]"),
            }
            if success:
                logging.info("Cash funding sale accepted. Waiting 5s before strategy execution...")
                time.sleep(5)
            return result, info

    def save_cash_funding_result(self, today_str: str, result: Dict) -> List[Dict]:
        order = result.get("order") if result else None
        if order is None:
            return []

        with self._execution_lock:
            return self._save_cash_funding_record(today_str, result)

    def _save_cash_funding_record(self, today_str: str, result: Dict) -> List[Dict]:
        order = result["order"]
        history = self.history_service().load_history()
        today_entry = _get_today_entry(history, today_str)
        if today_entry is None:
            today_entry = {"date": today_str}
            history.insert(0, today_entry)

        raoeo_data = today_entry.setdefault("raoeo", {"orders": []})
        results = raoeo_data.setdefault("cash_funding_results", [])
        record = {
            "ticker": order.symbol,
            "side": order.side.name,
            "qty": order.quantity,
            "price": order.price,
            "order_type": order.order_type,
            "reason": order.reason,
            "success": result["success"],
            "message": result["message"],
            "ambiguous": result.get("ambiguous", False),
            "correlation_id": order.correlation_id,
        }
        existing = next(
            (
                index
                for index, previous in enumerate(results)
                if order.correlation_id
                and previous.get("correlation_id") == order.correlation_id
            ),
            None,
        )
        if existing is None:
            results.append(record)
        else:
            results[existing] = record
        if not self.dependencies.save_history(history[:200]):
            raise RuntimeError("Failed to save cash funding history.")
        return results

    def _report_orderable_usd(self, report_info: Dict) -> Any:
        if self.dependencies.strategy_broker_name() != "toss":
            return None
        usd_cash = report_info.get("holdings", {}).get("USD cash", {})
        if usd_cash.get("type") != "CASH":
            return None
        try:
            return float(usd_cash.get("qty", 0.0))
        except (TypeError, ValueError):
            return None

    def _build_run_context(self) -> "StrategyRunContext":
        return StrategyRunContext(
            get_market_data=lambda **kwargs: self.market_data_service().get_market_data(
                **kwargs
            ),
            load_strategy_config=self.dependencies.load_strategy_config,
            fetch_prices=self.dependencies.fetch_prices,
        )


_dependencies: Optional[StrategyExecutionDependencies] = None
_strategy_execution_lock = threading.RLock()


def configure_strategy_execution(dependencies: StrategyExecutionDependencies) -> None:
    """Configure the application service from the runtime composition root."""
    global _dependencies
    _dependencies = dependencies


def _require_dependencies() -> StrategyExecutionDependencies:
    if _dependencies is None:
        raise RuntimeError("Strategy execution dependencies are not configured.")
    return _dependencies


class StrategyRunContext:
    """Share expensive market data across one strategy execution bundle."""

    def __init__(
        self,
        *,
        get_market_data: Callable[..., Tuple[Dict, Dict]],
        load_strategy_config: Callable[[], Dict[str, Any]],
        fetch_prices: Callable[[List[str]], Dict[str, float]],
    ):
        self._market_snapshot: Optional[Tuple[Dict, Dict]] = None
        self._get_market_data = get_market_data
        self._load_strategy_config = load_strategy_config
        self._fetch_prices = fetch_prices

    def get_market_data(
        self,
        force_refresh: bool = True,
        include_cash_ticker: bool = False,
    ) -> Tuple[Dict, Dict]:
        if self._market_snapshot is None:
            if include_cash_ticker:
                self._market_snapshot = self._get_market_data(
                    force_refresh=force_refresh,
                    include_cash_ticker=True,
                )
            else:
                self._market_snapshot = self._get_market_data(
                    force_refresh=force_refresh,
                )
        elif include_cash_ticker:
            self._ensure_cash_ticker_price()
        return self._market_snapshot

    def _ensure_cash_ticker_price(self) -> None:
        if self._market_snapshot is None:
            return

        strategy_config = self._load_strategy_config()
        cash_ticker = strategy_config.get("cash_ticker", "")
        if not cash_ticker:
            return

        holdings, prices = self._market_snapshot
        if prices.get(cash_ticker, 0.0) > 0:
            return

        holding_price = resolve_current_price(cash_ticker, holdings.get(cash_ticker, {}), {})
        if holding_price > 0:
            prices[cash_ticker] = holding_price
            return

        prices.update(self._fetch_prices([cash_ticker]))


def _build_strategy_run_context() -> StrategyRunContext:
    """Build one execution context from the configured application ports."""
    dependencies = _require_dependencies()
    return StrategyRunContext(
        get_market_data=get_market_data,
        load_strategy_config=dependencies.load_strategy_config,
        fetch_prices=dependencies.fetch_prices,
    )


# -------------------------------------------------------------------------
# Common Helpers
# -------------------------------------------------------------------------

def get_market_data(
    force_refresh: bool = False,
    include_cash_ticker: bool = False,
) -> Tuple[Dict, Dict]:
    """
    Fetch current portfolio and prices for all configured strategy targets.
    Returns: (portfolio_holdings, current_prices_map)
    """
    return get_strategy_market_data_service().get_market_data(
        force_refresh=force_refresh,
        include_cash_ticker=include_cash_ticker,
    )


def get_strategy_market_data_service() -> StrategyMarketDataService:
    """Build the application market-data service from legacy adapters."""
    return StrategyExecutionRuntime(_require_dependencies()).market_data_service()


def get_orderable_usd(symbol: str, order_price: float) -> float:
    """Return strategy-broker USD buying power for a representative buy."""
    return _require_dependencies().get_orderable_usd(symbol, order_price)


def _get_rebalancing_orderable_usd(
    symbol: str,
    order_price: float,
    cache_key: str = "",
) -> float:
    """Reuse buying power during one automatic trading-day check cycle."""
    if not cache_key:
        return get_orderable_usd(symbol, order_price)
    cache = _require_dependencies().orderable_usd_cache
    if cache_key not in cache:
        cache.clear()
        cache[cache_key] = get_orderable_usd(symbol, order_price)
    return cache[cache_key]


def _get_runtime_rebalancing_orderable_usd(
    dependencies: StrategyExecutionDependencies,
    symbol: str,
    order_price: float,
    cache_key: str = "",
) -> float:
    if not cache_key:
        return dependencies.get_orderable_usd(symbol, order_price)
    cache = dependencies.orderable_usd_cache
    if cache_key not in cache:
        cache.clear()
        cache[cache_key] = dependencies.get_orderable_usd(symbol, order_price)
    return cache[cache_key]


def execute_single_order(order: StrategyOrder) -> Tuple[bool, str]:
    """Execute a single strategy order via the configured strategy broker."""
    broker_name = _require_dependencies().strategy_broker_name()
    estimated_amount = (
        f"{order.quantity * order.price:.2f}"
        if order.price > 0
        else "unknown"
    )
    price_text = f"{order.price:.2f}" if order.price > 0 else "MARKET"
    logging.info(
        "[OrderAudit] Preparing strategy order: broker=%s symbol=%s side=%s "
        "quantity=%s price=%s estimated_amount=%s order_type=%s reason=%s",
        broker_name,
        order.symbol,
        order.side.name,
        order.quantity,
        price_text,
        estimated_amount,
        order.order_type,
        order.reason,
    )
    return _require_dependencies().execute_order(order)


def get_order_report_service() -> OrderReportService:
    """Build the application order-result facade over the configured broker."""
    return OrderReportService(execute_order=execute_single_order, sleep=time.sleep)


def _build_base_report(today_str: str, market_status: Dict) -> Dict:
    """Create base report structure used by all strategies."""
    return {
        "date": today_str,
        "status": None,
        "market_status": market_status,
        "orders": [],
        "succeeded_orders": [],
        "pending_orders": [],
        "execution_results": [],
        "info": {},
        "error": None,
    }


# -------------------------------------------------------------------------
# Unified History Management
# -------------------------------------------------------------------------

def _load_history(history_service: Optional[StrategyHistoryService] = None) -> list:
    """Load unified strategy history."""
    service = history_service or get_strategy_history_service()
    return service.load_history()


def get_strategy_history_service() -> StrategyHistoryService:
    """Build the application history service from the legacy JSON adapter."""
    return StrategyExecutionRuntime(_require_dependencies()).history_service()


def normalize_strategy_history_date(raw: str = "") -> str:
    """Return a strategy history date string, defaulting to today in ET."""
    if not raw:
        return datetime.now(TZ_ET).strftime("%Y-%m-%d")

    raw = raw.strip()
    if STRATEGY_HISTORY_COMPACT_DATE_RE.match(raw):
        normalized = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    elif STRATEGY_HISTORY_DATE_RE.match(raw):
        normalized = raw
    else:
        raise ValueError("Date must be YYYY-MM-DD or YYYYMMDD.")

    try:
        datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Date must be a valid calendar date.") from exc
    return normalized


def clear_strategy_history_for_date(target_date: str = "") -> Dict[str, Any]:
    """Remove the full strategy history entry for a date."""
    target_date = normalize_strategy_history_date(target_date)
    return get_strategy_history_service().clear_date(target_date)


def _get_today_entry(hist_data: list, today_str: str) -> Optional[Dict]:
    """Find or create today's entry in history."""
    for entry in hist_data:
        if entry.get("date") == today_str:
            return entry
    return None


def _restore_orders_from_strategy_history(
    strategy_data: Dict
) -> List[Tuple[StrategyOrder, bool]]:
    """
    Restore orders from a strategy's history section with success status.
    Returns: List of (StrategyOrder, success_status) tuples
    """
    orders_data = strategy_data.get("orders", [])
    restored = []

    for order_data in orders_data:
        try:
            order = StrategyOrder(
                symbol=order_data["ticker"],
                side=OrderSide[order_data["side"]],
                quantity=order_data["qty"],
                price=order_data["price"],
                order_type=order_data.get("order_type", ORDER_TYPE_LIMIT),
                reason=order_data.get("reason", ""),
                target_budget=order_data.get("target_budget"),
                correlation_id=order_data.get("correlation_id"),
            )
            success = order_data.get("success", False)
            restored.append((order, success))
        except Exception as e:
            logging.error(f"Failed to restore order: {order_data}, error: {e}")
            continue

    return restored


def _build_order_history_entry(
    order: StrategyOrder,
    success: bool,
    message: str,
    *,
    ambiguous: bool = False,
) -> Dict:
    """Serialize a strategy order for strategy_history.json."""
    entry = {
        "ticker": order.symbol,
        "side": order.side.name,
        "qty": order.quantity,
        "price": order.price,
        "order_type": order.order_type,
        "reason": order.reason,
        "success": success,
        "message": message,
        "ambiguous": ambiguous,
    }
    if order.target_budget is not None:
        entry["target_budget"] = order.target_budget
    if order.correlation_id:
        entry["correlation_id"] = order.correlation_id
    return entry


def _persist_submission_intent(
    *,
    today_str: str,
    strategy_key: str,
    report: Dict,
    history_service: StrategyHistoryService,
    extra_fields: Optional[Dict] = None,
    orders_to_submit: Optional[List[StrategyOrder]] = None,
    succeeded_orders: Optional[List[StrategyOrder]] = None,
) -> None:
    """Durably block retries before sending any order to a broker."""
    orders_to_submit = orders_to_submit or report.get("orders", [])

    intent_data = _build_strategy_history_data(
        report,
        strategy_key,
        extra_fields=extra_fields,
    )
    intent_data["status"] = StrategyStatus.PARTIAL.value
    intent_data["orders"] = [
        _build_order_history_entry(order, True, "Success")
        for order in succeeded_orders or []
    ] + [
        _build_order_history_entry(
            order,
            False,
            "Submission started; reconcile before retrying.",
            ambiguous=True,
        )
        for order in orders_to_submit
    ]
    _save_strategy_to_history(
        today_str,
        strategy_key,
        intent_data,
        history_service=history_service,
    )


def _submit_strategy_orders(
    *,
    report: Dict,
    strategy_key: str,
    today_str: str,
    orders: List[StrategyOrder],
    history_service: StrategyHistoryService,
    order_report_service: OrderReportService,
    extra_fields: Optional[Dict] = None,
    succeeded_orders: Optional[List[StrategyOrder]] = None,
    sell_first: bool = False,
    sell_wait_seconds: int = 0,
) -> List[Dict]:
    """Submit orders through the single durable strategy submission boundary."""
    preserved_orders = succeeded_orders or []

    def persist_intent(submission_orders: List[StrategyOrder]) -> None:
        _persist_submission_intent(
            today_str=today_str,
            strategy_key=strategy_key,
            report=report,
            history_service=history_service,
            extra_fields=extra_fields,
            orders_to_submit=submission_orders,
            succeeded_orders=preserved_orders,
        )

    def persist_outcome(results: List[Dict]) -> None:
        _apply_execution_results(report, orders, results)
        save_data = _build_strategy_history_data(
            report,
            strategy_key,
            extra_fields=extra_fields,
        )
        if preserved_orders:
            report["succeeded_orders"] = preserved_orders + report["succeeded_orders"]
            report["orders"] = preserved_orders + orders
            save_data["orders"] = _build_merged_history_entries(
                preserved_orders,
                results,
            )
        _save_strategy_to_history(
            today_str,
            strategy_key,
            save_data,
            history_service=history_service,
        )

    return DurableOrderSubmissionService(order_report_service).submit(
        orders,
        persist_intent=persist_intent,
        persist_outcome=persist_outcome,
        sell_first=sell_first,
        sell_wait_seconds=sell_wait_seconds,
    )


def _restore_history_orders(report: Dict, strategy_hist: Dict) -> Tuple[List[StrategyOrder], List[StrategyOrder]]:
    """Restore historical orders into a report and return succeeded/failed lists."""
    orders_with_status = _restore_orders_from_strategy_history(strategy_hist)
    all_orders = [order for order, _ in orders_with_status]
    succeeded = [order for order, success in orders_with_status if success]
    failed = [order for order, success in orders_with_status if not success]

    report["orders"] = all_orders
    report["succeeded_orders"] = succeeded
    report["pending_orders"] = failed
    return succeeded, failed


def _apply_execution_results(
    report: Dict,
    orders: List[StrategyOrder],
    results: List[Dict],
) -> None:
    """Store execution results and derive report status/order buckets."""
    report["execution_results"] = results
    report["status"] = _execution_status(orders, results)
    report["succeeded_orders"] = [
        result["order"] for result in results if result["success"]
    ]
    report["pending_orders"] = [
        result["order"] for result in results if not result["success"]
    ]


def _execution_status(
    orders: List[StrategyOrder],
    results: List[Dict],
) -> StrategyStatus:
    success_count = sum(1 for result in results if result["success"])
    if success_count == len(orders):
        return StrategyStatus.EXECUTED
    return StrategyStatus.PARTIAL


def _build_merged_history_entries(
    succeeded: List[StrategyOrder],
    results: List[Dict],
) -> List[Dict]:
    """Merge previous successes with the latest retry results for history."""
    merged_orders = [
        _build_order_history_entry(order, True, "Success")
        for order in succeeded
    ]
    for result in results:
        order = result["order"]
        merged_orders.append(_build_order_history_entry(
            order,
            result["success"],
            result["message"],
            ambiguous=result.get("ambiguous", False),
        ))
    return merged_orders


def _retry_failed_history_orders(
    report: Dict,
    strategy_key: str,
    today_str: str,
    succeeded: List[StrategyOrder],
    failed: List[StrategyOrder],
    extra_fields: Optional[Dict] = None,
    sell_first: bool = False,
    sell_wait_seconds: int = 0,
    order_report_service: Optional[OrderReportService] = None,
    history_service: Optional[StrategyHistoryService] = None,
) -> None:
    service = order_report_service or get_order_report_service()
    report["orders"] = succeeded + failed
    _submit_strategy_orders(
        report=report,
        strategy_key=strategy_key,
        today_str=today_str,
        orders=failed,
        history_service=history_service or get_strategy_history_service(),
        order_report_service=service,
        extra_fields=extra_fields,
        succeeded_orders=succeeded,
        sell_first=sell_first,
        sell_wait_seconds=sell_wait_seconds,
    )


def _has_ambiguous_history_order(strategy_hist: Dict) -> bool:
    """Prevent automatic retries until an operator reconciles a timeout."""
    return any(order.get("ambiguous", False) for order in strategy_hist.get("orders", []))


def _mark_ambiguous_order_error(report: Dict) -> None:
    report["status"] = StrategyStatus.ERROR
    report["error"] = "Ambiguous order outcome requires reconciliation."
    report["pending_orders"] = []


def _save_strategy_to_history(
    today_str: str,
    strategy_key: str,
    strategy_data: Dict,
    history_service: Optional[StrategyHistoryService] = None,
):
    """Save a strategy's result to the unified history file."""
    service = history_service or StrategyHistoryService(
        load=_load_history,
        save=_require_dependencies().save_history,
    )
    service.save_strategy(
        today_str,
        strategy_key,
        strategy_data,
    )


def _build_strategy_history_data(
    report: Dict,
    strategy_key: str,
    extra_fields: Optional[Dict] = None
) -> Dict:
    """Build the history data dict for a strategy from its report."""
    now_et = datetime.now(TZ_ET)
    data = {
        "time": now_et.strftime("%H:%M:%S"),
        "status": report["status"].value if isinstance(report["status"], StrategyStatus) else report["status"],
        "orders": [],
    }

    # Add extra fields (e.g., targets_context for VA, context for Rebalancing)
    if extra_fields:
        data.update(extra_fields)

    if strategy_key == "raoeo":
        skipped_buy_budgets = report.get("info", {}).get("skipped_buy_budgets")
        if skipped_buy_budgets:
            data["skipped_buy_budgets"] = skipped_buy_budgets

    # Build order list from execution results or calculated orders
    if report.get("execution_results"):
        for res in report["execution_results"]:
            order = res["order"]
            data["orders"].append(_build_order_history_entry(
                order,
                res["success"],
                res["message"],
                ambiguous=res.get("ambiguous", False),
            ))
    elif report.get("orders"):
        for order in report["orders"]:
            data["orders"].append(_build_order_history_entry(
                order,
                False,
                "Calculated Only",
            ))

    return data


def prepare_raoeo_cash_funding(
    raoeo_report: Optional[Dict] = None,
    context: Optional[StrategyRunContext] = None,
) -> Tuple[Any, Dict]:
    """Calculate a manual cash-ticker funding order for pending RAOEO buys."""
    if raoeo_report is None:
        raoeo_report = run_raoeo_strategy(execute=False)

    pending_orders = raoeo_report.get("pending_orders", [])
    reference_buy = next(
        (order for order in pending_orders if order.side == OrderSide.BUY),
        None,
    )
    strategy_config = _require_dependencies().load_strategy_config()
    report_info = raoeo_report.get("info", {})
    holdings = report_info.get("holdings")
    prices = report_info.get("current_prices", {})
    if holdings is None:
        run_context = context or _build_strategy_run_context()
        holdings, prices = run_context.get_market_data(
            force_refresh=True,
            include_cash_ticker=True,
        )

    orderable_usd = _report_orderable_usd(report_info)
    if orderable_usd is None:
        orderable_usd = (
            get_orderable_usd(reference_buy.symbol, reference_buy.price)
            if reference_buy
            else 0.0
        )
    return raoeo.calculate_cash_funding_order(
        orders=pending_orders,
        portfolio=holdings,
        current_prices=prices,
        cash_ticker=strategy_config.get("cash_ticker", ""),
        orderable_usd=orderable_usd,
    )


def _report_orderable_usd(report_info: Dict) -> Any:
    """Reuse Toss portfolio buying power captured as USD cash when available."""
    if _require_dependencies().strategy_broker_name() != "toss":
        return None

    usd_cash = report_info.get("holdings", {}).get("USD cash", {})
    if usd_cash.get("type") != "CASH":
        return None

    try:
        return float(usd_cash.get("qty", 0.0))
    except (TypeError, ValueError):
        return None


def execute_raoeo_cash_funding(
    raoeo_report: Optional[Dict] = None,
    context: Optional[StrategyRunContext] = None,
) -> Tuple[Any, Dict]:
    """Compatibility entry point routed through the durable runtime flow."""
    return StrategyExecutionRuntime(_require_dependencies()).execute_cash_funding(
        raoeo_report,
        context=context,
    )


def save_raoeo_cash_funding_result(today_str: str, result: Dict) -> List[Dict]:
    """Store a manual funding result without turning it into a retry order."""
    order = result.get("order") if result else None
    if order is None:
        return []

    hist_data = _load_history()
    today_entry = _get_today_entry(hist_data, today_str)
    if not today_entry:
        today_entry = {"date": today_str}
        hist_data.insert(0, today_entry)

    raoeo_data = today_entry.setdefault("raoeo", {"orders": []})
    results = raoeo_data.setdefault("cash_funding_results", [])
    results.append({
        "ticker": order.symbol,
        "side": order.side.name,
        "qty": order.quantity,
        "price": order.price,
        "order_type": order.order_type,
        "reason": order.reason,
        "success": result["success"],
        "message": result["message"],
    })
    _require_dependencies().save_history(hist_data[:200])
    return results


def _execute_orders(
    orders: List[StrategyOrder],
    sell_first: bool = False,
    sell_wait_seconds: int = 0,
    order_report_service: Optional[OrderReportService] = None,
) -> List[Dict]:
    """
    Execute a list of orders. Optionally execute sells first with a wait.
    Returns: list of execution result dicts
    """
    service = order_report_service or get_order_report_service()
    return service.execute_many(
        orders,
        sell_first=sell_first,
        sell_wait_seconds=sell_wait_seconds,
    )


def _handle_raoeo_history(
    report: Dict,
    raoeo_hist: Dict,
    execute: bool,
    market_status: Dict,
    today_str: str,
    order_report_service: Optional[OrderReportService] = None,
    history_service: Optional[StrategyHistoryService] = None,
) -> None:
    logging.info(f"RAOEO: Found today's history at {raoeo_hist.get('time', '?')}")
    succeeded, failed = _restore_history_orders(report, raoeo_hist)

    if _has_ambiguous_history_order(raoeo_hist):
        _mark_ambiguous_order_error(report)
        return

    if not failed:
        report["status"] = StrategyStatus.EXECUTED
        logging.info("RAOEO: All orders from history were successful.")
        return

    if not execute:
        report["status"] = StrategyStatus.PARTIAL
        return

    if not market_status["is_market_open"]:
        report["status"] = StrategyStatus.NON_MARKET_TIME
        return

    logging.info(f"RAOEO: Re-executing {len(failed)} failed orders.")
    _retry_failed_history_orders(
        report,
        "raoeo",
        today_str,
        succeeded,
        failed,
        sell_first=True,
        sell_wait_seconds=5,
        order_report_service=order_report_service,
        history_service=history_service,
    )


def _handle_va_history(
    report: Dict,
    va_hist: Dict,
    execute: bool,
    market_status: Dict,
    today_str: str,
    order_report_service: Optional[OrderReportService] = None,
    history_service: Optional[StrategyHistoryService] = None,
) -> None:
    logging.info(f"VA: Found today's history at {va_hist.get('time', '?')}")
    succeeded, failed = _restore_history_orders(report, va_hist)
    report["info"]["targets_context"] = va_hist.get("targets_context", {})

    if _has_ambiguous_history_order(va_hist):
        _mark_ambiguous_order_error(report)
        return

    if not failed:
        hist_status = va_hist.get("status")
        try:
            report["status"] = StrategyStatus(hist_status)
        except ValueError:
            report["status"] = StrategyStatus.EXECUTED
        return

    if not execute:
        report["status"] = StrategyStatus.PARTIAL
        return

    if not market_status["is_market_open"]:
        report["status"] = StrategyStatus.NON_MARKET_TIME
        return

    _retry_failed_history_orders(
        report,
        "va",
        today_str,
        succeeded,
        failed,
        extra_fields={
            "targets_context": va_hist.get("targets_context", {}),
        },
        order_report_service=order_report_service,
        history_service=history_service,
    )


def _handle_rebalancing_history(report: Dict, reb_hist: Dict) -> None:
    logging.info(f"[Rebalancing] Found today's history at {reb_hist.get('time', '?')}")
    _, failed = _restore_history_orders(report, reb_hist)
    report["info"]["context"] = reb_hist.get("context", {})

    if _has_ambiguous_history_order(reb_hist):
        _mark_ambiguous_order_error(report)
        return

    if not failed:
        report["status"] = StrategyStatus.ALREADY_DONE
    else:
        report["status"] = StrategyStatus.PARTIAL


def _calculate_raoeo_reserved_cash(strategy_config: Dict) -> float:
    raoeo_conf = strategy_config.get('raoeo', {}).get('targets', {})
    reserved_cash = 0.0

    for target_config in raoeo_conf.values():
        if not target_config.get('enabled', True):
            continue
        seed = float(target_config.get('seed', 0))
        duration = int(target_config.get('duration', 1))
        if duration > 0 and seed > 0:
            reserved_cash += seed / duration

    return reserved_cash


def _rebalancing_reference_asset(
    reb_conf: Dict,
    holdings: Dict,
    prices: Dict[str, float],
) -> Tuple[Any, float]:
    reference_asset = reb_conf.get("assets", [{}])[0].get("ticker")
    reference_holding = holdings.get(reference_asset, {}) if reference_asset else {}
    reference_price = (
        resolve_current_price(reference_asset, reference_holding, prices)
        if reference_asset
        else 0.0
    )
    return reference_asset, reference_price


def _rebalancing_history_context(calc_info: Dict) -> Dict:
    return {
        "seed": calc_info.get("seed"),
        "orderable_usd": calc_info.get("orderable_usd"),
        "total_available": calc_info.get("total_available"),
        "scale_factor": calc_info.get("scale_factor"),
        "asset_status": calc_info.get("asset_status", {}),
    }


# -------------------------------------------------------------------------
# RAOEO Execution
# -------------------------------------------------------------------------

def _run_raoeo_strategy(
    *,
    dependencies: StrategyExecutionDependencies,
    execute: bool = False,
    context: Optional[StrategyRunContext] = None,
) -> Dict[str, Any]:
    """
    Run RAOEO strategy with unified 6-step flow.
    """
    today_str = datetime.now(TZ_ET).strftime("%Y-%m-%d")
    market_status = dependencies.get_market_status(today_str)
    report = _build_base_report(today_str, market_status)
    history_service = StrategyHistoryService(
        load=dependencies.load_history,
        save=dependencies.save_history,
    )
    order_report_service = OrderReportService(
        execute_order=dependencies.execute_order,
        sleep=time.sleep,
    )

    try:
        # Step 1: Check enabled
        strategy_config = dependencies.load_strategy_config()
        raoeo_section = strategy_config.get('raoeo', {})

        if not raoeo_section.get('enabled', True):
            report["status"] = StrategyStatus.DISABLED
            return report

        raoeo_conf = raoeo_section.get('targets', {})

        # Filter enabled tickers only
        active_targets = {
            t: c for t, c in raoeo_conf.items() if c.get('enabled', True)
        }

        if not active_targets:
            report["status"] = StrategyStatus.DISABLED
            return report

        # Step 2: Market status (already determined above)

        # Step 3: Check today's history
        hist_data = history_service.load_history()
        today_entry = _get_today_entry(hist_data, today_str)
        raoeo_hist = today_entry.get("raoeo") if today_entry else None

        if raoeo_hist and raoeo_hist.get("orders"):
            _handle_raoeo_history(
                report,
                raoeo_hist,
                execute,
                market_status,
                today_str,
                order_report_service=order_report_service,
                history_service=history_service,
            )
            return report

        # Step 5: No history — calculate only when the market is open
        if not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
            return report

        run_context = context or StrategyRunContext(
            get_market_data=StrategyExecutionRuntime(dependencies)
            .market_data_service()
            .get_market_data,
            load_strategy_config=dependencies.load_strategy_config,
            fetch_prices=dependencies.fetch_prices,
        )
        holdings, prices = run_context.get_market_data(force_refresh=True)
        report["info"]["holdings"] = holdings
        report["info"]["current_prices"] = prices

        orders, calc_info = raoeo.calculate_orders(
            targets_config=active_targets,
            portfolio=holdings,
            current_prices=prices,
            history_data=hist_data,
            today_date=today_str,
        )
        report["orders"] = orders
        report["pending_orders"] = orders
        report["info"].update(calc_info)

        if not orders:
            report["status"] = StrategyStatus.SKIPPED
            if execute and report["info"].get("skipped_buy_budgets"):
                save_data = _build_strategy_history_data(report, "raoeo")
                _save_strategy_to_history(
                    today_str, "raoeo", save_data, history_service=history_service
                )
            return report

        # Step 6: Execute if requested
        if not execute:
            if not market_status["is_market_open"]:
                report["status"] = StrategyStatus.NON_MARKET_TIME
            else:
                report["status"] = StrategyStatus.SKIPPED
            return report

        if not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
            return report

        _submit_strategy_orders(
            report=report,
            strategy_key="raoeo",
            today_str=today_str,
            orders=orders,
            history_service=history_service,
            order_report_service=order_report_service,
            sell_first=True,
            sell_wait_seconds=5,
        )

    except requests.exceptions.Timeout as e:
        logging.error(f"[API Timeout] RAOEO Service Timeout Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = "API Timeout"
    except Exception as e:
        logging.error(f"RAOEO Service Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = str(e)

    return report


def run_raoeo_strategy(
    execute: bool = False,
    context: Optional[StrategyRunContext] = None,
) -> Dict[str, Any]:
    """Compatibility entry point for callers not yet composed with a runtime."""
    with _strategy_execution_lock:
        return _run_raoeo_strategy(
            dependencies=_require_dependencies(),
            execute=execute,
            context=context or _build_strategy_run_context(),
        )


# -------------------------------------------------------------------------
# Value Averaging Execution
# -------------------------------------------------------------------------

def _run_va_strategy(
    *,
    dependencies: StrategyExecutionDependencies,
    execute: bool = False,
    market_snapshot: Optional[Tuple[Dict, Dict]] = None,
    context: Optional[StrategyRunContext] = None,
    history_service: Optional[StrategyHistoryService] = None,
) -> Dict[str, Any]:
    """
    Run Value Averaging strategy with unified 6-step flow.
    """
    today_str = datetime.now(TZ_ET).strftime("%Y-%m-%d")
    market_status = dependencies.get_market_status(today_str)
    report = _build_base_report(today_str, market_status)
    history_service = history_service or StrategyHistoryService(
        load=dependencies.load_history,
        save=dependencies.save_history,
    )
    order_report_service = OrderReportService(
        execute_order=dependencies.execute_order,
        sleep=time.sleep,
    )

    try:
        # Step 1: Check enabled
        strategy_config = dependencies.load_strategy_config()
        va_section = strategy_config.get('value_averaging', {})

        if not va_section.get('enabled', True):
            report["status"] = StrategyStatus.DISABLED
            return report

        va_conf = va_section.get('targets', {})

        active_targets = {
            t: c for t, c in va_conf.items() if c.get('enabled', True)
        }

        if not active_targets:
            report["status"] = StrategyStatus.DISABLED
            return report

        # Step 2: Market status (already determined)

        # Step 3: Check today's history
        hist_data = history_service.load_history()
        today_entry = _get_today_entry(hist_data, today_str)
        va_hist = today_entry.get("va") if today_entry else None

        if va_hist:
            _handle_va_history(
                report,
                va_hist,
                execute,
                market_status,
                today_str,
                order_report_service=order_report_service,
                history_service=history_service,
            )
            return report

        # Step 5: No history — calculate only when the market is open
        if not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
            return report

        if market_snapshot is not None:
            holdings, prices = market_snapshot
        else:
            run_context = context or StrategyRunContext(
                get_market_data=StrategyExecutionRuntime(dependencies)
                .market_data_service()
                .get_market_data,
                load_strategy_config=dependencies.load_strategy_config,
                fetch_prices=dependencies.fetch_prices,
            )
            holdings, prices = run_context.get_market_data(force_refresh=True)

        # VA needs history for day_count calculation
        orders, context_map = value_averaging.calculate_orders(
            targets_config=active_targets,
            portfolio=holdings,
            current_prices=prices,
            history_data=hist_data,
            today_date=today_str
        )

        targets_context = {
            t: {"day_count": ctx.get("day_count", 0)} for t, ctx in context_map.items()
        }
        report["orders"] = orders
        report["pending_orders"] = orders
        report["info"]["targets_context"] = targets_context
        report["info"]["context_map"] = context_map

        if not orders:
            report["status"] = StrategyStatus.SKIPPED
        elif not execute:
            report["status"] = StrategyStatus.NON_MARKET_TIME if not market_status["is_market_open"] else StrategyStatus.SKIPPED
        elif not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
        else:
            _submit_strategy_orders(
                report=report,
                strategy_key="va",
                today_str=today_str,
                orders=orders,
                history_service=history_service,
                order_report_service=order_report_service,
                extra_fields={"targets_context": targets_context},
            )

        # Save history (always save for VA — day_count tracking)
        if not execute or not orders or not market_status["is_market_open"]:
            save_data = _build_strategy_history_data(
                report,
                "va",
                extra_fields={"targets_context": targets_context},
            )
            _save_strategy_to_history(
                today_str, "va", save_data, history_service=history_service
            )

    except requests.exceptions.Timeout as e:
        logging.error(f"[API Timeout] VA Service Timeout Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = "API Timeout"
    except Exception as e:
        logging.error(f"VA Service Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = str(e)

    return report


def run_va_strategy(
    execute: bool = False,
    market_snapshot: Optional[Tuple[Dict, Dict]] = None,
    context: Optional[StrategyRunContext] = None,
) -> Dict[str, Any]:
    """Compatibility entry point for callers not yet composed with a runtime."""
    with _strategy_execution_lock:
        return _run_va_strategy(
            dependencies=_require_dependencies(),
            execute=execute,
            market_snapshot=market_snapshot,
            context=context or _build_strategy_run_context(),
            history_service=StrategyHistoryService(
                load=_load_history,
                save=_require_dependencies().save_history,
            ),
        )


def run_strategy_suite(
    execute: bool = False,
    context: Optional[StrategyRunContext] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run RAOEO and Value Averaging with shared market data."""
    with _strategy_execution_lock:
        run_context = context or _build_strategy_run_context()
        raoeo_report = run_raoeo_strategy(execute=execute, context=run_context)
        va_report = run_va_strategy(execute=execute, context=run_context)
        return raoeo_report, va_report


# -------------------------------------------------------------------------
# Rebalancing Execution
# -------------------------------------------------------------------------

def _run_rebalancing_strategy(
    *,
    dependencies: StrategyExecutionDependencies,
    execute: bool = False,
    orderable_cache_key: str = "",
    history_service: Optional[StrategyHistoryService] = None,
    market_data_service: Optional[Any] = None,
    get_orderable_usd_port: Optional[Callable[[str, float], float]] = None,
) -> Dict[str, Any]:
    """
    Run Rebalancing strategy with unified 6-step flow.
    """
    today_str = datetime.now(TZ_ET).strftime("%Y-%m-%d")
    market_status = dependencies.get_market_status(today_str)
    report = _build_base_report(today_str, market_status)
    history_service = history_service or StrategyHistoryService(
        load=dependencies.load_history,
        save=dependencies.save_history,
    )
    order_report_service = OrderReportService(
        execute_order=dependencies.execute_order,
        sleep=time.sleep,
    )

    try:
        # Step 1: Check enabled
        strategy_config = dependencies.load_strategy_config()
        reb_conf = strategy_config.get('rebalancing', {})

        if not reb_conf.get('enabled', False):
            report["status"] = StrategyStatus.DISABLED
            return report

        # Step 2: Market status (already determined)

        # Step 3: Check today's history
        hist_data = history_service.load_history()
        today_entry = _get_today_entry(hist_data, today_str)
        reb_hist = today_entry.get("rebalancing") if today_entry else None

        if reb_hist and reb_hist.get("orders"):
            _handle_rebalancing_history(report, reb_hist)
            return report

        # Step 5: No history — calculate only when the market is open
        if not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
            return report

        # Load market data (portfolio + prices)
        market_data_service = market_data_service or StrategyExecutionRuntime(
            dependencies
        ).market_data_service()
        holdings, prices = market_data_service.get_market_data(force_refresh=True)

        # RAOEO budget reservation
        raoeo_daily_total = _calculate_raoeo_reserved_cash(strategy_config)
        reference_asset, reference_price = _rebalancing_reference_asset(
            reb_conf,
            holdings,
            prices,
        )
        orderable_usd = (
            (
                _get_runtime_rebalancing_orderable_usd(
                    dependencies,
                    reference_asset,
                    reference_price,
                    cache_key=orderable_cache_key,
                )
                if get_orderable_usd_port is None
                else get_orderable_usd_port(reference_asset, reference_price)
            )
            if reference_asset and reference_price > 0
            else 0.0
        )

        # Calculate
        orders, calc_info = rebalancing.calculate_orders(
            config=reb_conf,
            portfolio=holdings,
            current_prices=prices,
            orderable_usd=orderable_usd,
            reserved_cash=raoeo_daily_total
        )

        report["orders"] = orders
        report["pending_orders"] = orders
        report["info"].update(calc_info)

        if not orders:
            report["status"] = StrategyStatus.SKIPPED
            return report

        # Step 6: Execute if requested
        if not execute:
            report["status"] = StrategyStatus.NON_MARKET_TIME if not market_status["is_market_open"] else StrategyStatus.SKIPPED
            return report

        if not market_status["is_market_open"]:
            report["status"] = StrategyStatus.NON_MARKET_TIME
            return report

        history_context = _rebalancing_history_context(calc_info)
        _submit_strategy_orders(
            report=report,
            strategy_key="rebalancing",
            today_str=today_str,
            orders=orders,
            history_service=history_service,
            order_report_service=order_report_service,
            extra_fields={"context": history_context},
            sell_first=True,
            sell_wait_seconds=60,
        )

    except requests.exceptions.Timeout as e:
        logging.error(f"[API Timeout] Rebalancing Service Timeout Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = "API Timeout"
    except Exception as e:
        logging.error(f"Rebalancing Service Error: {e}", exc_info=True)
        report["status"] = StrategyStatus.ERROR
        report["error"] = str(e)

    return report


def run_rebalancing_strategy(
    execute: bool = False,
    orderable_cache_key: str = "",
) -> Dict[str, Any]:
    """Compatibility entry point for callers not yet composed with a runtime."""
    with _strategy_execution_lock:
        dependencies = _require_dependencies()
        return _run_rebalancing_strategy(
            dependencies=dependencies,
            execute=execute,
            orderable_cache_key=orderable_cache_key,
            history_service=StrategyHistoryService(
                load=_load_history,
                save=dependencies.save_history,
            ),
            market_data_service=_build_strategy_run_context(),
            get_orderable_usd_port=get_orderable_usd,
        )
