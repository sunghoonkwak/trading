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

from infrastructure.http_defaults import install_requests_default_timeout

install_requests_default_timeout()

# Force-disable any global requests-cache to prevent SQLite multi-thread errors
try:
    import requests_cache
    if requests_cache.is_installed():
        requests_cache.uninstall_cache()
except ImportError:
    pass

from application.runtime_service import RuntimeCommandResult, RuntimeController
from infrastructure import display, event_pipe, lock_manager
from infrastructure import trading_configuration as trading_config
from infrastructure.logger import LogManager
from infrastructure.runtime_settings import CONFIG_ROOT


class TradingSystem:
    """Main application class for the KIS Trading System."""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.shutdown_event = threading.Event()
        self._runtime_lock = threading.Lock()
        self._runtime_running = False
        self._web_server_started = False
        self._scheduler_runner = None
        self._strategy_runtime = None

    def setup_logging(self):
        """Configures system-wide logging via LogManager."""
        log_file = LogManager.setup(self.base_dir)
        display.log_file_path = log_file

    def load_telegram_credentials(self) -> tuple[str | None, str | None]:
        """Load private Telegram credentials from the composition root."""
        try:
            path = os.path.join(CONFIG_ROOT, "telegram.txt")
            with open(path, "r") as file:
                token, chat_id = file.read().split(",")[:2]
            return token.strip(), chat_id.strip()
        except Exception as error:
            logging.error("Error loading Telegram credentials: %s", error)
            return None, None

    def _build_portfolio_service(self):
        """Compose the portfolio use case from runtime adapters."""
        from application.portfolio_retrieval_service import PortfolioRetrievalService
        from domain.portfolio.weights import calculate_target_weights
        from infrastructure.config import ConfigFile, load_json, save_json
        from infrastructure.market_signals import get_fear_and_greed
        from infrastructure.portfolio.composition import (
            PortfolioServiceDependencies,
            build_portfolio_service,
        )
        from infrastructure.portfolio.integration import (
            fetch_toss_exchange_rate,
            fetch_toss_portfolio_source,
            fetch_toss_prices,
            get_cached_gsheet_portfolio,
            send_telegram_warning,
        )
        from infrastructure.portfolio.kis_source import fetch_kis_portfolio_source
        from infrastructure.system_state import is_kis_ready
        from infrastructure.toss.portfolio import TOSS_ACCOUNT_KEY

        self._configure_gsheet_source()
        self._configure_kis_portfolio_source()
        portfolio_source = PortfolioRetrievalService(
            fetch_kis=fetch_kis_portfolio_source,
            fetch_toss=fetch_toss_portfolio_source,
            get_cached_gsheet=get_cached_gsheet_portfolio,
            fetch_toss_exchange_rate=fetch_toss_exchange_rate,
            fetch_toss_prices=fetch_toss_prices,
            publish_alert=display.add_alert,
            publish_warning=send_telegram_warning,
            toss_account_key=TOSS_ACCOUNT_KEY,
        )
        return build_portfolio_service(
            PortfolioServiceDependencies(
                is_kis_ready=is_kis_ready,
                portfolio_source=portfolio_source,
                save_portfolio=lambda value: save_json(ConfigFile.PORTFOLIO, value),
                load_weights=lambda: load_json(ConfigFile.PORTFOLIO_WEIGHTS),
                calculate_targets=calculate_target_weights,
                fear_and_greed=get_fear_and_greed,
                publish_alert=display.add_alert,
            )
        )

    def _configure_kis_portfolio_source(self):
        """Compose KIS portfolio source runtime collaborators."""
        from infrastructure.kis.worker import WorkerSerializedKisOperations
        from infrastructure.portfolio.kis_source import (
            configure_alert_publisher,
            configure_feature_flags,
            configure_serialized_operations,
        )

        configure_feature_flags(
            rest_api_enabled=trading_config.is_kis_rest_api_enabled,
            domestic_enabled=trading_config.is_kis_domestic_enabled,
        )
        configure_alert_publisher(display.add_alert)
        configure_serialized_operations(WorkerSerializedKisOperations())

    def _configure_gsheet_source(self):
        """Compose the private Google Sheets credential path."""
        from infrastructure.gsheet import configure_service_account_file

        configure_service_account_file(
            os.path.join(CONFIG_ROOT, "service-account.json")
        )

    def _configure_strategy_execution_service(self):
        """Compose strategy execution collaborators from runtime adapters."""
        if self._strategy_runtime is not None:
            return

        from application.strategy_broker import StrategyBrokerService
        from application.strategy_execution import (
            StrategyExecutionDependencies,
            StrategyExecutionRuntime,
        )
        from infrastructure import market_data, market_signals
        from infrastructure.config import ConfigFile, load_json, save_json
        from infrastructure.kis import broker as kis_broker
        from infrastructure.toss import broker as toss_broker

        strategy_broker = StrategyBrokerService(
            load_strategy_config=lambda: load_json(
                ConfigFile.STRATEGY_CONFIG, default={}
            ),
            kis_orderable_usd=kis_broker.get_orderable_usd,
            toss_orderable_usd=toss_broker.get_orderable_usd,
            kis_place_order=kis_broker.place_overseas_order,
            toss_place_order=toss_broker.place_order,
        )

        dependencies = StrategyExecutionDependencies(
                load_strategy_config=lambda: load_json(
                    ConfigFile.STRATEGY_CONFIG, default={}
                ),
                load_history=lambda: load_json(
                    ConfigFile.STRATEGY_HISTORY, default=[], strict=True
                ),
                save_history=lambda history: save_json(ConfigFile.STRATEGY_HISTORY, history),
                fetch_prices=market_data.fetch_prices,
                strategy_broker_name=strategy_broker.get_strategy_broker_name,
                get_orderable_usd=strategy_broker.get_orderable_usd,
                execute_order=strategy_broker.place_order,
                portfolio_reader_factory=self._build_portfolio_service,
                get_market_status=market_signals.get_us_market_status,
        )
        self._strategy_runtime = StrategyExecutionRuntime(dependencies)

    def initialize_telegram(self):
        """Initializes the Telegram bot thread."""
        print("[Startup] Step 1: Initializing Telegram Bot...")
        from application.strategy_execution import (
            normalize_strategy_history_date,
        )
        from domain.portfolio.weights import get_cash_weight
        from infrastructure import (
            market_data,
            market_signals,
            order_admin,
        )
        from infrastructure import (
            trading_configuration as stock_configuration,
        )
        from infrastructure.config import ConfigFile, load_json, save_json
        from infrastructure.portfolio import refresh_gsheet_cache
        from infrastructure.portfolio.weight_diffs import (
            WeightDiffDependencies,
            get_weight_diffs,
        )
        from infrastructure.system_state import ThreadStatus, update_telegram_state
        from interfaces.telegram.bot import initialize_telegram
        from interfaces.telegram.memo import MemoStore
        from interfaces.telegram.portfolio import PortfolioCommandDependencies
        from interfaces.telegram.strategy import StrategyCommandDependencies

        self._configure_strategy_execution_service()
        assert self._strategy_runtime is not None
        self._configure_kis_portfolio_source()
        update_telegram_state(thread_status=ThreadStatus.STARTING)
        if initialize_telegram(
            portfolio_dependencies=PortfolioCommandDependencies(
                reader=self._build_portfolio_service(),
                market_reader=market_data,
                order_reader=order_admin,
                get_weight_diffs=lambda scope="all": get_weight_diffs(
                    scope,
                    WeightDiffDependencies(
                        get_portfolio_data=lambda requested_scope: (
                            self._build_portfolio_service().get_portfolio_data(
                                scope=requested_scope
                            )
                        ),
                        load_weights=lambda: load_json(ConfigFile.PORTFOLIO_WEIGHTS),
                        get_cash_weight=get_cash_weight,
                        get_fear_and_greed=market_signals.get_fear_and_greed,
                        fetch_price=market_data.fetch_price,
                    ),
                ),
                refresh_gsheet_cache=refresh_gsheet_cache,
                load_stock_configuration=stock_configuration.load_stock_configuration,
                get_fear_and_greed=market_signals.get_fear_and_greed,
            ),
            strategy_dependencies=StrategyCommandDependencies(
                strategy_run_service=self._strategy_runtime.strategy_run_service(),
                clear_history=self._strategy_runtime.clear_history,
                normalize_history_date=normalize_strategy_history_date,
                prepare_cash_funding=self._strategy_runtime.prepare_cash_funding,
                execute_cash_funding=self._strategy_runtime.execute_cash_funding,
                save_cash_funding_result=self._strategy_runtime.save_cash_funding_result,
            ),
            strategy_run_service=self._strategy_runtime.strategy_run_service(),
            memo_store=MemoStore(
                load=lambda: load_json(ConfigFile.MEMO, default={}),
                save=lambda memos: save_json(ConfigFile.MEMO, memos),
                add_alert=display.add_alert,
            ),
            runtime_controller=RuntimeController(
                start=self.start_trading_runtime,
                stop=self.stop_trading_runtime,
                is_running=self.is_trading_runtime_running,
            ),
            credentials_loader=self.load_telegram_credentials,
            add_alert=display.add_alert,
        ):
            from infrastructure.kis.event_handler import (
                configure_notification_sender as configure_kis_event_notification_sender,
            )
            from infrastructure.kis.vendor_callbacks import (
                configure_notification_sender as configure_kis_vendor_notification_sender,
            )
            from infrastructure.portfolio.integration import (
                configure_alert_publisher,
                configure_warning_notifier,
            )
            from interfaces.telegram.utils import send_notification

            configure_kis_event_notification_sender(send_notification)
            configure_kis_vendor_notification_sender(send_notification)
            configure_alert_publisher(display.add_alert)
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

            self._configure_gsheet_source()
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
            from infrastructure.credentials import get_secrets_from_password
            from infrastructure.kis import configure_kis_vendor_hooks
            from infrastructure.kis.rest_client import configure_state_publisher
            from infrastructure.kis.vendor_callbacks import configure_runtime_collaborators
            from infrastructure.kis.ws_manager import (
                configure_alert_publisher as configure_ws_alert_publisher,
            )
            from infrastructure.kis.ws_manager import (
                configure_event_handler,
                configure_subscription_provider,
            )
            from infrastructure.kis.ws_manager import (
                configure_state_publisher as configure_ws_state_publisher,
            )
            from infrastructure.system_state import (
                AuthStatus,
                ThreadStatus,
                WebSocketStatus,
                update_kis_state,
            )

            status_by_phase = {
                "authenticating": AuthStatus.AUTHENTICATING,
                "authenticated": AuthStatus.AUTHENTICATED,
                "failed": AuthStatus.FAILED,
            }

            def publish_kis_auth_state(phase: str, error: str | None = None) -> None:
                is_websocket = phase.startswith("ws_")
                status = status_by_phase[phase.removeprefix("ws_")]
                update_kis_state(
                    **({"ws_auth_status": status} if is_websocket else {"auth_status": status}),
                    **({"last_error": error} if error else {}),
                )

            websocket_status_by_name = {
                "connected": WebSocketStatus.CONNECTED,
                "connecting": WebSocketStatus.CONNECTING,
                "reconnecting": WebSocketStatus.RECONNECTING,
                "disconnected": WebSocketStatus.DISCONNECTED,
                "error": WebSocketStatus.ERROR,
            }

            def publish_websocket_state(
                status_name: str,
                error: str | None = None,
            ) -> None:
                status = websocket_status_by_name.get(status_name)
                if status is not None:
                    update_kis_state(
                        ws_status=status,
                        **({"last_error": error} if error else {}),
                    )

            worker_thread_status_by_name = {
                "running": ThreadStatus.RUNNING,
                "stopped": ThreadStatus.STOPPED,
            }

            def publish_worker_thread_state(status_name: str) -> None:
                status = worker_thread_status_by_name.get(status_name)
                if status is not None:
                    update_kis_state(thread_status=status)

            from infrastructure.kis.event_handler import on_result

            configure_subscription_provider(
                domestic_enabled=trading_config.is_kis_domestic_enabled,
                domestic_tickers=lambda: [
                    stock["ticker"]
                    for stock in trading_config.CONFIG.get("KR", [])
                    if not stock.get("disabled")
                ],
                overseas_tickers=lambda: [
                    stock["ticker"]
                    for stock in trading_config.CONFIG.get("US", [])
                    if not stock.get("disabled")
                ],
                market_prefix=trading_config.get_kis_market_prefix,
            )
            configure_ws_alert_publisher(display.add_alert)
            configure_ws_state_publisher(publish_websocket_state)
            configure_event_handler(on_result)

            configure_state_publisher(publish_kis_auth_state)
            configure_runtime_collaborators(
                credential_provider=get_secrets_from_password,
                alert_publisher=display.add_alert,
                websocket_state_publisher=publish_websocket_state,
            )

            configure_kis_vendor_hooks()
            from infrastructure.kis.worker import (
                configure_alert_publisher as configure_kis_worker_alert_publisher,
            )
            from infrastructure.kis.worker import (
                configure_rest_api_enabled as configure_kis_worker_rest_api_enabled,
            )
            from infrastructure.kis.worker import (
                configure_state_publisher as configure_kis_worker_state_publisher,
            )
            from infrastructure.kis.worker import (
                initialize_websocket_and_pipe,
                is_kis_thread_running,
                request_kis_auth,
                request_kis_ws_auth,
                start_kis_thread,
                wait_for_response,
            )

            configure_kis_worker_alert_publisher(display.add_alert)
            configure_kis_worker_rest_api_enabled(
                trading_config.is_kis_rest_api_enabled
            )
            configure_kis_worker_state_publisher(publish_worker_thread_state)

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
            return True
        except Exception as e:
            logging.error(f"[Startup] KIS error: {e}")
            return False

    def initialize_toss(self):
        """Initializes Toss access token for today's trading session."""
        print("[Startup] Step 3: Initializing Toss API...")
        try:
            from infrastructure.credentials import load_credentials
            from infrastructure.toss.auth import (
                configure_auth_configuration,
                ensure_daily_token,
            )
            from infrastructure.toss.client import configure_failure_notifier
            from interfaces.telegram.utils import send_notification

            configure_auth_configuration(
                config_root=CONFIG_ROOT,
                credentials_loader=load_credentials,
            )
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
            from infrastructure import market_signals
            from infrastructure.runtime_settings import DEFAULT_USD_KRW_EXCHANGE_RATE
            from interfaces.scheduler.order_runner import SchedulerOrderRunner
            from interfaces.scheduler.portfolio_runner import (
                SchedulerPortfolioRunner,
                SchedulerReportDependencies,
            )
            from interfaces.scheduler.runner import SchedulerRunner
            from interfaces.telegram.portfolio_formatter import format_portfolio_summary
            from interfaces.telegram.report_formatter import (
                format_rebalancing_report,
                format_strategy_report,
            )
            from interfaces.telegram.utils import send_notification

            self._configure_strategy_execution_service()
            assert self._strategy_runtime is not None
            self._scheduler_runner = SchedulerRunner(
                portfolio_reader=self._build_portfolio_service(),
                order_runner=SchedulerOrderRunner(
                    strategy_run_service=self._strategy_runtime.strategy_run_service(),
                    notify=send_notification,
                    format_strategy_report=format_strategy_report,
                    format_rebalancing_report=format_rebalancing_report,
                ),
                portfolio_runner=SchedulerPortfolioRunner(
                    send_notification,
                    SchedulerReportDependencies(
                        history_dir=os.path.join(CONFIG_ROOT, "portfolio_history"),
                        default_exchange_rate=DEFAULT_USD_KRW_EXCHANGE_RATE,
                        get_fear_and_greed=market_signals.get_fear_and_greed,
                    ),
                    format_portfolio_summary,
                ),
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
        from infrastructure.runtime_settings import (
            DEFAULT_HOST,
            DEFAULT_USD_KRW_EXCHANGE_RATE,
            DEFAULT_WEB_PORT,
        )
        try:
            from application.order_report_service import OrderManagementService
            from infrastructure import market_signals, order_admin
            from infrastructure.config import ConfigFile, load_json, save_json
            from infrastructure.runtime_settings import ENV_TRUE_VALUES
            from interfaces.scheduler.portfolio_runner import (
                SchedulerPortfolioRunner,
                SchedulerReportDependencies,
            )
            from interfaces.telegram.portfolio_formatter import format_portfolio_summary
            from interfaces.telegram.utils import send_notification
            from interfaces.web import WebDependencies, create_web_app, start_web_server

            portfolio_reader = self._build_portfolio_service()
            portfolio_runner = SchedulerPortfolioRunner(
                send_notification,
                SchedulerReportDependencies(
                    history_dir=os.path.join(CONFIG_ROOT, "portfolio_history"),
                    default_exchange_rate=DEFAULT_USD_KRW_EXCHANGE_RATE,
                    get_fear_and_greed=market_signals.get_fear_and_greed,
                ),
                format_portfolio_summary,
            )
            web_app = create_web_app(
                WebDependencies(
                    runtime_is_running=self.is_trading_runtime_running,
                    set_broadcast_callback=event_pipe.set_web_broadcast_callback,
                    load_memos=lambda: load_json(ConfigFile.MEMO, default={}),
                    save_memos=lambda memos: save_json(ConfigFile.MEMO, memos),
                    portfolio_reader=portfolio_reader,
                    order_service=OrderManagementService(
                        sync_open_orders=order_admin.sync_open_orders,
                        fetch_open_orders=order_admin.fetch_open_orders,
                        execute_manage_action=order_admin.execute_manage_action,
                    ),
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

            from infrastructure.order_admin import sync_open_orders

            sync_open_orders()
            print("[Startup] ✓ Orders synced")
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
            from infrastructure.kis.worker import stop_kis_thread
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
        from infrastructure.kis.logger import install_kis_logging

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
