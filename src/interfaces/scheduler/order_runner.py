# -*- coding: utf-8 -*-
"""
Scheduler Order Interface Adapter

Executes daily strategy routines automatically and sends reports to Telegram.
Reuses the same execution and reporting logic as the Telegram bot.
"""
import logging
from collections.abc import Callable

from application.strategy_run_service import StrategyRunService
from interfaces.telegram.report_formatter import format_strategy_report

_strategy_run_service: StrategyRunService | None = None
_notification_sender = None


class SchedulerOrderRunner:
    """Factory-owned scheduled strategy jobs with explicit collaborators."""

    def __init__(
        self,
        *,
        strategy_run_service: StrategyRunService,
        notify: Callable[[str], None],
    ) -> None:
        self._strategy_run_service = strategy_run_service
        self._notify = notify
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
            report_text = format_strategy_report(raoeo_res, va_res)
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
        from interfaces.telegram.report_formatter import format_rebalancing_report

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
                self._notify(f"{header}\n\n{format_rebalancing_report(report)}")
            self._last_first_notify_date = us_date
        except Exception as exc:
            logging.error("[Scheduler] Periodic Rebalancing failed: %s", exc, exc_info=True)
            self._notify(f"⚠️ Periodic Rebalancing Error: {exc}")
            self._last_first_notify_date = us_date


def configure_strategy_run_service(service: StrategyRunService) -> None:
    """Inject the application strategy use case from the composition root."""
    global _strategy_run_service
    _strategy_run_service = service


def configure_notification_sender(sender) -> None:
    """Inject the notification port from the runtime composition root."""
    global _notification_sender
    _notification_sender = sender


def _send_notification(message: str) -> None:
    if _notification_sender is None:
        raise RuntimeError("Scheduler notification sender is not configured.")
    _notification_sender(message)


def _get_strategy_run_service() -> StrategyRunService:
    if _strategy_run_service is None:
        raise RuntimeError("StrategyRunService is not configured.")
    return _strategy_run_service


def run_strategy_suite(execute: bool = False):
    """Compatibility seam for the shared application strategy use case."""
    return _get_strategy_run_service().run_suite(execute=execute)


def run_rebalancing_strategy(execute: bool = False, orderable_cache_key: str = ""):
    """Compatibility seam for the application rebalancing use case."""
    return _get_strategy_run_service().run_rebalancing(
        execute=execute,
        orderable_cache_key=orderable_cache_key,
    )


def run_daily_order_report():
    """
    Execute daily order update routine (typically scheduled for evening).
    Calculates and Executes RAOEO and VA strategies, then sends a unified report.
    """
    logging.info("[Scheduler] Starting daily order report & execution job.")

    try:
        # Run RAOEO and Value Averaging with shared market data.
        raoeo_res, va_res = run_strategy_suite(execute=True)

        raoeo_err = raoeo_res.get("error")
        va_err = va_res.get("error")
        if raoeo_err == "API Timeout" or va_err == "API Timeout":
            _send_notification(f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Daily Report)\nRAOEO: {raoeo_err}, VA: {va_err}")

        # Format Unified Report
        report_text = format_strategy_report(raoeo_res, va_res)

        # Send Notification
        full_message = f"⏰ <b>Daily Scheduler Execution</b>\n\n{report_text}"
        _send_notification(full_message)

        logging.info("[Scheduler] Daily execution completed and report sent.")

    except Exception as e:
        if "Timeout" in str(e):
            alert_msg = f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Daily Order): {e}"
        else:
            alert_msg = f"⚠️ Scheduler Order Error: {e}"
        logging.error(f"[Scheduler] Daily Order Job failed: {e}", exc_info=True)
        _send_notification(alert_msg)

# Module-level flag: US/Eastern date of last first-notification
_last_first_notify_date: str = ""


def run_periodic_rebalancing():
    """
    Execute rebalancing strategy periodically during US market hours.
    Notification rules:
      1. First scheduled call of the US trading day -> ALWAYS notify
      2. Subsequent calls -> only notify if actual rebalancing orders exist
    """
    global _last_first_notify_date
    from datetime import datetime

    import pytz

    tz = pytz.timezone('US/Eastern')
    now_et = datetime.now(tz)
    us_date = now_et.strftime("%Y-%m-%d")
    cur_time = now_et.strftime("%H:%M")

    # Time window: 09:40 ~ 15:40 US/Eastern
    if not ("09:40" <= cur_time <= "15:40"):
        return

    # First scheduled call of this US trading day?
    is_first_call = (us_date != _last_first_notify_date)

    try:
        reb_res = run_rebalancing_strategy(
            execute=True,
            orderable_cache_key=us_date,
        )

        from domain.strategy.base import StrategyStatus

        # Notify on the first market-window check, or later only when the
        # strategy actually acted or surfaced an error.

        status = reb_res.get('status')

        if status == StrategyStatus.DISABLED:
            _last_first_notify_date = us_date
            return

        logging.info(f"[Scheduler] Running periodic rebalancing at {cur_time} ET ({us_date})")

        if is_first_call:
            should_notify = True
        elif status == StrategyStatus.ALREADY_DONE:
            should_notify = False
        else:
            # For subsequent calls, only notify if action was taken
            should_notify = status in [StrategyStatus.EXECUTED, StrategyStatus.PARTIAL, StrategyStatus.ERROR]


        if should_notify:
            if status == StrategyStatus.ERROR and reb_res.get("error") == "API Timeout":
                _send_notification("⚠️ [네트워크 타임아웃] KIS API 무응답 (Periodic Rebalancing)")
            else:
                from interfaces.telegram.report_formatter import format_rebalancing_report
                header = "🚀 <b>First Rebalancing Check</b>" if is_first_call else "🔄 <b>Periodic Rebalancing</b>"
                report_text = format_rebalancing_report(reb_res)
                _send_notification(f"{header}\n\n{report_text}")
                logging.info(f"[Scheduler] Rebalancing notification sent (FirstCall: {is_first_call})")
        else:
            logging.info("[Scheduler] Rebalancing checked: No action needed.")

        # Mark this date as notified (whether we sent or not, the day is checked)
        _last_first_notify_date = us_date

    except Exception as e:
        if "Timeout" in str(e):
            alert_msg = f"⚠️ [네트워크 타임아웃] KIS API 무응답 (Rebalancing): {e}"
        else:
            alert_msg = f"⚠️ Periodic Rebalancing Error: {e}"
        logging.error(f"[Scheduler] Periodic Rebalancing failed: {e}", exc_info=True)
        _send_notification(alert_msg)
        # Still mark date so we don't retry first-call notification on error
        _last_first_notify_date = us_date
