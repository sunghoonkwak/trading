# -*- coding: utf-8 -*-
"""
Scheduler Order Interface Adapter

Executes daily strategy routines automatically and sends reports to Telegram.
Reuses the same execution and reporting logic as the Telegram bot.
"""
import logging
from collections.abc import Callable

from application.strategy_run_service import StrategyRunService


class SchedulerOrderRunner:
    """Factory-owned scheduled strategy jobs with explicit collaborators."""

    def __init__(
        self,
        *,
        strategy_run_service: StrategyRunService,
        notify: Callable[[str], None],
        format_strategy_report: Callable[[dict, dict], str],
        format_rebalancing_report: Callable[[dict], str],
    ) -> None:
        self._strategy_run_service = strategy_run_service
        self._notify = notify
        self._format_strategy_report = format_strategy_report
        self._format_rebalancing_report = format_rebalancing_report
        self._last_first_notify_date = ""

    def run_daily_order_report(self) -> None:
        logging.info("[Scheduler] Starting daily order report & execution job.")
        try:
            raoeo_res, va_res = self._strategy_run_service.run_suite(execute=True)
            raoeo_err = raoeo_res.get("error")
            va_err = va_res.get("error")
            if raoeo_err == "API Timeout" or va_err == "API Timeout":
                self._notify(
                    "⚠️ [네트워크 타임아웃] KIS API 무응답 (Daily Report)\n"
                    f"RAOEO: {raoeo_err}, VA: {va_err}"
                )
            report_text = self._format_strategy_report(raoeo_res, va_res)
            self._notify(f"⏰ <b>Daily Scheduler Execution</b>\n\n{report_text}")
        except Exception as exc:
            logging.error("[Scheduler] Daily Order Job failed: %s", exc, exc_info=True)
            self._notify(f"⚠️ Scheduler Order Error: {exc}")

    def run_periodic_rebalancing(self) -> None:
        from datetime import datetime

        import pytz

        now_et = datetime.now(pytz.timezone("US/Eastern"))
        us_date = now_et.strftime("%Y-%m-%d")
        cur_time = now_et.strftime("%H:%M")
        if not ("09:40" <= cur_time <= "15:40"):
            return

        from domain.strategy.base import StrategyStatus
        is_first_call = us_date != self._last_first_notify_date
        try:
            report = self._strategy_run_service.run_rebalancing(
                execute=True,
                orderable_cache_key=us_date,
            )
            status = report.get("status")
            if status == StrategyStatus.DISABLED:
                self._last_first_notify_date = us_date
                return
            should_notify = is_first_call or status not in {StrategyStatus.ALREADY_DONE}
            if should_notify:
                header = "🚀 <b>First Rebalancing Check</b>" if is_first_call else "🔄 <b>Periodic Rebalancing</b>"
                self._notify(f"{header}\n\n{self._format_rebalancing_report(report)}")
            self._last_first_notify_date = us_date
        except Exception as exc:
            logging.error("[Scheduler] Periodic Rebalancing failed: %s", exc, exc_info=True)
            self._notify(f"⚠️ Periodic Rebalancing Error: {exc}")
            self._last_first_notify_date = us_date
