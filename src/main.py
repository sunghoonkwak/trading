# -*- coding: utf-8 -*-
"""
Main Trading System Entry Point

Initializes and orchestrates all sub-systems (KIS, Telegram, Scheduler, Web).
"""
import logging
import os
import sys
import threading
import time

from core.http_defaults import install_requests_default_timeout

install_requests_default_timeout()

# Force-disable any global requests-cache to prevent SQLite multi-thread errors
try:
    import requests_cache
    if requests_cache.is_installed():
        requests_cache.uninstall_cache()
except ImportError:
    pass

from application.runtime_service import RuntimeCommandResult, RuntimeController
from core import display, event_pipe, lock_manager, trading_config
from utils.logger import LogManager


class TradingSystem:
    """Main application class for the KIS Trading System."""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.shutdown_event = threading.Event()
        self._runtime_lock = threading.Lock()
        self._runtime_running = False
        self._web_server_started = False
        self._scheduler_runner = None

    def setup_logging(self):
        """Configures system-wide logging via LogManager."""
        log_file = LogManager.setup(self.base_dir)
        display.log_file_path = log_file

    def initialize_telegram(self):
        """Initializes the Telegram bot thread."""
        print("[Startup] Step 1: Initializing Telegram Bot...")
        from application.strategy_execution import get_strategy_run_service
        from broker import market_data, order_admin
        from data.config_manager import ConfigFile, load_json, save_json
        from infrastructure.portfolio import (
            build_portfolio_service,
            refresh_gsheet_cache,
        )
        from infrastructure.portfolio.weight_diffs import get_weight_diffs
        from infrastructure.strategy_execution import configure_strategy_execution_service
        from interfaces.telegram.bot import initialize_telegram
        from interfaces.telegram.memo import MemoStore
        from interfaces.telegram.portfolio import PortfolioCommandDependencies
        from state.system_state import ThreadStatus, update_telegram_state

        configure_strategy_execution_service()
        update_telegram_state(thread_status=ThreadStatus.STARTING)
        if initialize_telegram(
            portfolio_dependencies=PortfolioCommandDependencies(
                reader=build_portfolio_service(),
                market_reader=market_data,
                order_reader=order_admin,
                get_weight_diffs=get_weight_diffs,
                refresh_gsheet_cache=refresh_gsheet_cache,
            ),
            strategy_run_service=get_strategy_run_service(),
            memo_store=MemoStore(
                load=lambda: load_json(ConfigFile.MEMO, default={}),
                save=lambda memos: save_json(ConfigFile.MEMO, memos),
            ),
            runtime_controller=RuntimeController(
                start=self.start_trading_runtime,
                stop=self.stop_trading_runtime,
                is_running=self.is_trading_runtime_running,
            ),
        ):
            from broker.kis_event_handler import (
                configure_notification_sender as configure_kis_event_notification_sender,
            )
            from infrastructure.kis.vendor_callbacks import (
                configure_notification_sender as configure_kis_vendor_notification_sender,
            )
            from infrastructure.portfolio.integration import configure_warning_notifier
            from interfaces.telegram.utils import send_notification

            configure_kis_event_notification_sender(send_notification)
            configure_kis_vendor_notification_sender(send_notification)
            configure_warning_notifier(send_notification)
            update_telegram_state(thread_status=ThreadStatus.RUNNING, bot_connected=True)
            logging.info("[Startup] Telegram Bot initialized")
            print("[Startup] ✓ Telegram Bot initialized")
            return True
        else:
            update_telegram_state(thread_status=ThreadStatus.ERROR, last_error="Failed")
            logging.critical("[Startup] Telegram initialization failed")
            print("[Startup] ✗ Telegram init failed")
            return False

    def initialize_gsheet_cache(self):
        """Warms the Google Sheets source cache once during startup."""
        print("[Startup] Step 1b: Loading GSheet cache...")
        try:
            from infrastructure.portfolio import refresh_gsheet_cache

            result = refresh_gsheet_cache()
            if result["success"]:
                logging.info(
                    "[Startup] GSheet cache loaded: %s holdings, %s cash rows",
                    result["holdings_count"],
                    result["cash_count"],
                )
                print("[Startup] ✓ GSheet cache loaded")
            else:
                logging.warning(
                    "[Startup] GSheet cache loaded with warnings: %s",
                    result["error"],
                )
                print("[Startup] ⚠ GSheet cache loaded with warnings")
        except Exception as e:
            logging.error(f"[Startup] GSheet cache initialization failed: {e}")
            print("[Startup] ✗ GSheet cache init failed (continuing...)")

    def initialize_kis(self):
        """Initializes KIS API and WebSocket connection."""
        print("[Startup] Step 2: Initializing KIS API...")
        try:
            from infrastructure.kis import configure_kis_vendor_hooks

            configure_kis_vendor_hooks()
            from broker.kis_worker import (
                initialize_websocket_and_pipe,
                is_kis_thread_running,
                request_kis_auth,
                request_kis_ws_auth,
                start_kis_thread,
                wait_for_response,
            )

            if not is_kis_thread_running():
                if start_kis_thread():
                    print("[Startup] ✓ KIS Thread started")
                else:
                    print("[Startup] ✗ KIS Thread failed")
                    return False

            time.sleep(0.5)

            # REST & WS Auth
            if trading_config.is_kis_rest_api_enabled():
                auth_id = request_kis_auth()
                auth_response = wait_for_response(auth_id, timeout=30.0)
                if not auth_response or not auth_response.success:
                    error = auth_response.error if auth_response else "timeout"
                    logging.error(f"[Startup] REST API authentication failed: {error}")
                    print("[Startup] ✗ REST API authentication failed")
                    return False
                print("[Startup] ✓ REST API authenticated")
            else:
                print("[Startup] - REST API disabled; skipping REST authentication")

            ws_auth_id = request_kis_ws_auth()
            ws_auth_response = wait_for_response(ws_auth_id, timeout=30.0)
            if not ws_auth_response or not ws_auth_response.success:
                error = ws_auth_response.error if ws_auth_response else "timeout"
                logging.error(f"[Startup] WebSocket authentication failed: {error}")
                print("[Startup] ✗ WebSocket authentication failed")
                return False
            print("[Startup] ✓ WebSocket authenticated")

            # Pipe Server & WS Init
            if event_pipe.create_pipe_server():
                def wait_client():
                    if event_pipe.wait_for_client(): event_pipe.start_writer_thread()
                threading.Thread(target=wait_client, daemon=True).start()

            if not initialize_websocket_and_pipe():
                logging.error("[Startup] WebSocket and event pipe initialization failed")
                print("[Startup] ✗ KIS WebSocket initialization failed")
                return False
            print("[Startup] ✓ KIS fully initialized")

            from broker.order_admin import sync_open_orders
            sync_open_orders()
            print("[Startup] ✓ Orders synced")
            return True
        except Exception as e:
            logging.error(f"[Startup] KIS error: {e}")
            return False

    def initialize_toss(self):
        """Initializes Toss access token for today's trading session."""
        print("[Startup] Step 3: Initializing Toss API...")
        try:
            from infrastructure.toss.client import configure_failure_notifier
            from interfaces.telegram.utils import send_notification
            from toss.auth import ensure_daily_token

            configure_failure_notifier(send_notification)
            token_path = ensure_daily_token()
            logging.info(f"[Startup] Toss token ready: {token_path}")
            print("[Startup] ✓ Toss API token ready")
            return True
        except Exception as e:
            logging.error(f"[Startup] Toss error: {e}")
            print("[Startup] ✗ Toss API initialization failed")
            return False

    def start_scheduler(self):
        """Starts the background task scheduler."""
        print("[Startup] Step 4: Starting Scheduler Service...")
        try:
            from application.strategy_execution import get_strategy_run_service
            from infrastructure.portfolio import build_portfolio_service
            from infrastructure.strategy_execution import configure_strategy_execution_service
            from interfaces.scheduler.order_runner import SchedulerOrderRunner
            from interfaces.scheduler.portfolio_runner import SchedulerPortfolioRunner
            from interfaces.scheduler.runner import SchedulerRunner
            from interfaces.telegram.utils import send_notification

            configure_strategy_execution_service()
            self._scheduler_runner = SchedulerRunner(
                portfolio_reader=build_portfolio_service(),
                order_runner=SchedulerOrderRunner(
                    strategy_run_service=get_strategy_run_service(),
                    notify=send_notification,
                ),
                portfolio_runner=SchedulerPortfolioRunner(send_notification),
            )
            self._scheduler_runner.start()
            print("[Startup] ✓ Scheduler started")
        except Exception as e:
            logging.error(f"[Startup] Scheduler error: {e}")

    def start_web_server(self):
        """Starts the Web Event Viewer dashboard."""
        if self._web_server_started:
            print("[Startup] - Web Event Viewer already started")
            return
        print("[Startup] Step 5: Starting Web Event Viewer...")
        from core.constants import DEFAULT_HOST, DEFAULT_WEB_PORT
        try:
            from broker import order_admin
            from core import event_pipe
            from core.constants import ENV_TRUE_VALUES
            from data.config_manager import ConfigFile, load_json, save_json
            from infrastructure.portfolio import build_portfolio_service
            from interfaces.scheduler.portfolio_runner import SchedulerPortfolioRunner
            from interfaces.telegram.utils import send_notification
            from interfaces.web import WebDependencies, create_web_app, start_web_server

            portfolio_reader = build_portfolio_service()
            portfolio_runner = SchedulerPortfolioRunner(send_notification)
            web_app = create_web_app(
                WebDependencies(
                    runtime_is_running=self.is_trading_runtime_running,
                    set_broadcast_callback=event_pipe.set_web_broadcast_callback,
                    load_memos=lambda: load_json(ConfigFile.MEMO, default={}),
                    save_memos=lambda memos: save_json(ConfigFile.MEMO, memos),
                    portfolio_reader=portfolio_reader,
                    sync_open_orders=order_admin.sync_open_orders,
                    fetch_open_orders=order_admin.fetch_open_orders,
                    execute_manage_action=order_admin.execute_manage_action,
                    run_portfolio_report=portfolio_runner.run_daily_portfolio_report,
                    run_order_report=self._run_manual_order_report,
                    env_flag=lambda name, default=False: os.environ.get(name, "").strip().lower()
                    in ENV_TRUE_VALUES if name in os.environ else default,
                )
            )
            threading.Thread(
                target=start_web_server,
                kwargs={
                    "application": web_app,
                    "host": DEFAULT_HOST,
                    "port": DEFAULT_WEB_PORT,
                },
                daemon=True,
            ).start()
            self._web_server_started = True
            print("[Startup] ✓ Web Event Viewer started in background")
        except Exception:
            logging.exception("[Startup] Web server failed to start")

    def _run_manual_order_report(self):
        if self._scheduler_runner is None:
            raise RuntimeError("Scheduler runtime is not running.")
        self._scheduler_runner.run_daily_order_report()

    def _notify_startup_failure(self, component: str):
        """Send a best-effort Telegram alert for fail-closed startup errors."""
        try:
            from interfaces.telegram.utils import send_notification

            send_notification(
                "🚨 <b>Startup failure</b>\n"
                f"Component: {component}\n"
                "Trading bot stopped before scheduler/web startup."
            )
        except Exception as e:
            logging.error("[Startup] Failed to send startup failure alert: %s", e)

    def shutdown(self):
        """Gracefully shuts down all systems."""
        print("\n[System] Shutting down...")
        self.stop_trading_runtime()
        try:
            from interfaces.telegram.bot import shutdown_telegram
            shutdown_telegram()
        except: pass
        print("[System] Goodbye!")

    def is_trading_runtime_running(self) -> bool:
        return self._runtime_running

    def start_trading_runtime(self) -> RuntimeCommandResult:
        """Start trading services while keeping Telegram as the control plane."""
        with self._runtime_lock:
            if self._runtime_running:
                return RuntimeCommandResult(
                    success=True,
                    message="Trading runtime is already ON.",
                    already_in_state=True,
                )

            logging.info("[Runtime] Starting trading runtime by operator command")
            self.initialize_gsheet_cache()
            time.sleep(0.5)
            if not self.initialize_kis():
                logging.critical("[Runtime] KIS initialization failed; runtime remains OFF")
                self._notify_startup_failure("KIS")
                self._stop_runtime_dependencies()
                return RuntimeCommandResult(
                    success=False,
                    component="KIS",
                    message="KIS initialization failed. Trading runtime remains OFF.",
                )

            time.sleep(0.5)
            if not self.initialize_toss():
                logging.critical("[Runtime] Toss initialization failed; runtime remains OFF")
                self._notify_startup_failure("Toss")
                self._stop_runtime_dependencies()
                return RuntimeCommandResult(
                    success=False,
                    component="Toss",
                    message="Toss initialization failed. Trading runtime remains OFF.",
                )

            time.sleep(0.5)
            self.start_scheduler()
            self._runtime_running = True
            logging.info("[Runtime] Trading runtime is ON")
            return RuntimeCommandResult(
                success=True,
                message="Trading runtime is ON.",
            )

    def _stop_runtime_dependencies(self):
        try:
            if self._scheduler_runner is not None:
                self._scheduler_runner.stop()
                self._scheduler_runner = None
        except Exception as e:
            logging.warning("[Runtime] Scheduler stop skipped or failed: %s", e)
        try:
            from broker.kis_worker import stop_kis_thread
            stop_kis_thread()
        except Exception as e:
            logging.warning("[Runtime] KIS worker stop skipped or failed: %s", e)

    def stop_trading_runtime(self) -> RuntimeCommandResult:
        """Stop trading services without stopping Telegram."""
        with self._runtime_lock:
            if not self._runtime_running:
                return RuntimeCommandResult(
                    success=True,
                    message="Trading runtime is already OFF.",
                    already_in_state=True,
                )

            logging.info("[Runtime] Stopping trading runtime by operator command")
            self._stop_runtime_dependencies()
            self._runtime_running = False
            return RuntimeCommandResult(
                success=True,
                message="Trading runtime is OFF. Telegram control remains available.",
            )

    def run(self):
        """Main execution loop."""
        self.setup_logging()
        from broker.kis_logger import install_kis_logging

        install_kis_logging()
        print("=== KIS Real-time Trading System ===\n")

        # Ensure the script is only run within a Docker container
        if os.environ.get('ENV_MODE') != 'docker':
            print("\n[ERROR] This application must be run using Docker (docker-compose).")
            print("Direct execution of src/main.py on the host environment is strictly prohibited to prevent conflicts.")
            sys.exit(1)

        # Lock Check
        if not lock_manager.acquire_lock(self.base_dir):
            print("\n[ERROR] Another instance is already running!")
            print("Please stop the existing process (or Docker container) before starting a new one.\n")
            sys.exit(1)

        if not self.initialize_telegram():
            logging.critical("[Startup] Telegram initialization failed; refusing to start trading runtime")
            print("\n[ERROR] Telegram initialization failed. Trading runtime will not start.")
            self.shutdown()
            sys.exit(1)
        self.start_web_server()

        print("\n[Startup] Control plane is ready. Trading runtime is OFF.")
        try:
            while not self.shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Shutdown] Keyboard Interrupt")
        finally:
            self.shutdown()

if __name__ == "__main__":
    app = TradingSystem()
    app.run()
