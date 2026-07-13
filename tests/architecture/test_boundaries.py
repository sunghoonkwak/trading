import ast
import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"

# The U1 allowance has been retired by U3. Keep this named, versioned register
# so later migration units cannot reintroduce a broad legacy exception.
LEGACY_IMPORT_ALLOWLIST_VERSION = 2
LEGACY_IMPORT_ALLOWLIST = {}


def _module_name(node):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module]
    return []


def _imports_in(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        module
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for module in _module_name(node)
    }


def _is_package_or_child(module, package):
    return module == package or module.startswith(f"{package}.")


def _find_import_violations(source_root):
    """Return ``path: import`` entries for target-layer and vendor violations."""
    rules = {
        "domain": {
            "application", "infrastructure", "interfaces", "kis", "toss",
            "broker", "core", "data", "state", "scheduler", "web",
        },
        "application/ports": {
            "application", "infrastructure", "interfaces", "kis", "toss",
            "broker", "core", "data", "state", "scheduler", "web",
        },
        "application": {
            "infrastructure", "interfaces", "kis", "toss", "broker", "core",
            "data", "state", "scheduler", "web",
        },
        "infrastructure": {"interfaces"},
        "interfaces": {"infrastructure", "kis", "toss", "broker", "data", "state"},
        "infrastructure/kis/kis_api": {
            "application", "domain", "infrastructure", "interfaces", "broker", "core",
            "data", "state", "scheduler", "toss", "web",
        },
    }
    violations = []
    for relative_root, forbidden in rules.items():
        package_root = source_root / relative_root
        if not package_root.exists():
            continue
        for path in package_root.rglob("*.py"):
            relative_path = path.relative_to(source_root).as_posix()
            if relative_root == "application" and relative_path.startswith("application/ports/"):
                continue
            allowed = LEGACY_IMPORT_ALLOWLIST.get(relative_path, set())
            for module in _imports_in(path):
                if (
                    relative_root == "infrastructure/kis/kis_api"
                    and _is_package_or_child(module, "infrastructure.kis.kis_api")
                ):
                    continue
                if (
                    relative_root == "application/ports"
                    and _is_package_or_child(module, "application.ports")
                ):
                    continue
                if module in allowed:
                    continue
                if any(_is_package_or_child(module, package) for package in forbidden):
                    violations.append(f"{relative_path}: {module}")
    return sorted(violations)


def _run_import_check(tmp_path, code):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["PYTHONPATH"] = str(SRC_DIR)
    return subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_data_package_import_does_not_import_kis_data_service(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import data
assert "data.data_service" not in sys.modules
assert "infrastructure.kis.kis_api.kis_auth" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_data_package_does_not_export_portfolio_cache(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import data
assert not hasattr(data, "PortfolioCache")
assert "data.data_service" not in sys.modules
assert "infrastructure.kis.kis_api.kis_auth" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_telegram_interface_import_does_not_initialize_bot_module(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import interfaces.telegram
assert "interfaces.telegram.bot" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_strategy_execution_import_does_not_touch_kis_config(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import pathlib
import application.strategy_execution
assert not (pathlib.Path.home() / "KIS_config").exists()
""",
    )

    assert result.returncode == 0, result.stderr


def test_strategy_modules_do_not_import_kis_infrastructure_constants():
    offenders = []
    for path in (SRC_DIR / "strategy").glob("*.py"):
        if "infrastructure.kis.constants" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)

    assert offenders == []


def test_kis_broker_adapter_import_does_not_touch_kis_config(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import pathlib
import infrastructure.kis.broker
assert not (pathlib.Path.home() / "KIS_config").exists()
""",
    )

    assert result.returncode == 0, result.stderr


def test_app_imports_do_not_load_runtime_kis_modules(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import interfaces.web.server
import interfaces.scheduler.order_runner
import interfaces.telegram.strategy
assert "infrastructure.kis.kis_api.kis_auth" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_scheduler_portfolio_interface_import_does_not_load_kis_wrapper(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import interfaces.scheduler.portfolio_runner
assert "kis.get_portfolio" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_weight_diff_adapter_import_does_not_load_kis_worker(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import infrastructure.portfolio.weight_diffs
assert "kis.kis_thread" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_weight_diff_adapter_uses_composed_dependencies():
    imports = _imports_in(SRC_DIR / "infrastructure/portfolio/weight_diffs.py")

    assert "broker.market_data" not in imports
    assert "data.calculate_weights" not in imports
    assert "data.config_manager" not in imports
    assert "infrastructure.portfolio.composition" not in imports


def test_portfolio_composition_uses_composed_dependencies():
    imports = _imports_in(SRC_DIR / "infrastructure/portfolio/composition.py")

    assert "core.display" not in imports
    assert "data.config_manager" not in imports
    assert "data.calculate_weights" not in imports
    assert "state.system_state" not in imports
    assert "utils.market_utils" not in imports


def test_portfolio_integration_does_not_import_legacy_display():
    imports = _imports_in(SRC_DIR / "infrastructure/portfolio/integration.py")

    assert "core.display" not in imports


def test_portfolio_integration_does_not_import_legacy_gsheet():
    imports = _imports_in(SRC_DIR / "infrastructure/portfolio/integration.py")

    assert "data.gsheet" not in imports


def test_portfolio_integration_uses_kis_source_adapter():
    imports = _imports_in(SRC_DIR / "infrastructure/portfolio/integration.py")

    assert "broker.kis_portfolio" not in imports


def test_kis_portfolio_source_does_not_import_legacy_broker():
    imports = _imports_in(SRC_DIR / "infrastructure/portfolio/kis_source.py")

    assert "broker.kis_portfolio" not in imports
    assert "core.display" not in imports
    assert "core.trading_config" not in imports


def test_gsheet_source_does_not_import_legacy_config():
    imports = _imports_in(SRC_DIR / "infrastructure/gsheet/portfolio_source.py")

    assert "core.constants" not in imports


def test_toss_auth_does_not_import_legacy_config():
    imports = _imports_in(SRC_DIR / "infrastructure/toss/auth.py")

    assert "core.constants" not in imports
    assert "core.credentials" not in imports


def test_production_broker_modules_do_not_import_toss_compatibility_package():
    offenders = []
    for path in (SRC_DIR / "broker").glob("*.py"):
        if any(_is_package_or_child(module, "toss") for module in _imports_in(path)):
            offenders.append(path.name)

    assert offenders == []


def test_kis_worker_does_not_import_legacy_display():
    imports = _imports_in(SRC_DIR / "infrastructure/kis/worker.py")

    assert "core.display" not in imports


def test_kis_worker_does_not_import_legacy_trading_config():
    imports = _imports_in(SRC_DIR / "infrastructure/kis/worker.py")

    assert "core.trading_config" not in imports


def test_kis_worker_does_not_import_legacy_system_state():
    imports = _imports_in(SRC_DIR / "infrastructure/kis/worker.py")

    assert "state.system_state" not in imports


def test_kis_worker_does_not_import_legacy_thread_comm():
    imports = _imports_in(SRC_DIR / "infrastructure/kis/worker.py")

    assert "core.thread_comm" not in imports


def test_retired_kis_ws_manager_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/kis_ws_manager.py").exists()


def test_retired_kis_rest_client_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/kis_rest_client.py").exists()


def test_retired_kis_portfolio_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/kis_portfolio.py").exists()


def test_retired_kis_worker_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/kis_worker.py").exists()


def test_retired_kis_logger_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/kis_logger.py").exists()


def test_retired_kis_ws_notifications_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/kis_ws_notifications.py").exists()


def test_retired_kis_event_handler_module_is_removed():
    assert not (SRC_DIR / "broker/kis_event_handler.py").exists()


def test_retired_kis_logger_module_is_removed():
    assert not (SRC_DIR / "infrastructure/kis/kis_logger.py").exists()


def test_retired_kis_rest_client_module_is_removed():
    assert not (SRC_DIR / "infrastructure/kis/kis_rest_client.py").exists()


def test_retired_kis_ws_manager_module_is_removed():
    assert not (SRC_DIR / "infrastructure/kis/kis_ws_manager.py").exists()


def test_retired_kis_ws_notifications_module_is_removed():
    assert not (SRC_DIR / "infrastructure/kis/kis_ws_notifications.py").exists()


def test_retired_kis_compatibility_modules_are_removed():
    for relative_path in (
        "kis/__init__.py",
        "kis/constants.py",
        "kis/ws_parser.py",
        "kis/kis_api/__init__.py",
    ):
        assert not (SRC_DIR / relative_path).exists()


def test_retired_toss_compatibility_package_is_removed():
    assert list((SRC_DIR / "toss").glob("*.py")) == []


def test_retired_toss_broker_compatibility_modules_are_removed():
    for relative_path in (
        "broker/toss_broker.py",
        "broker/toss_portfolio.py",
    ):
        assert not (SRC_DIR / relative_path).exists()


def test_retired_toss_prefixed_adapter_modules_are_removed():
    for relative_path in (
        "infrastructure/toss/toss_broker.py",
        "infrastructure/toss/toss_portfolio.py",
    ):
        assert not (SRC_DIR / relative_path).exists()


def test_retired_kis_broker_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/kis_broker.py").exists()


def test_retired_order_admin_compatibility_module_is_removed():
    assert not (SRC_DIR / "broker/order_admin.py").exists()


def test_retired_market_data_broker_module_is_removed():
    assert not (SRC_DIR / "broker/market_data.py").exists()


def test_retired_strategy_broker_module_is_removed():
    assert not (SRC_DIR / "broker/strategy_broker.py").exists()


def test_retired_legacy_sidecars_are_removed():
    for relative_path in (
        "data/portfolio_integration.md",
        "strategy/report_formatter.md",
    ):
        assert not (SRC_DIR / relative_path).exists()


def test_retired_data_compatibility_modules_are_removed():
    for relative_path in (
        "data/__init__.py",
        "data/calculate_weights.py",
        "data/config_manager.py",
    ):
        assert not (SRC_DIR / relative_path).exists()


def test_no_active_python_consumer_uses_retired_toss_broker_modules():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            source = path.read_text(encoding="utf-8")
            if (
                "broker.toss_broker" in source
                or "broker.toss_portfolio" in source
                or "from broker import toss_broker" in source
                or "from broker import toss_portfolio" in source
            ):
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_no_active_python_consumer_uses_retired_kis_broker_module():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            source = path.read_text(encoding="utf-8")
            if "broker.kis_broker" in source or "from broker import kis_broker" in source:
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_no_active_python_consumer_uses_retired_order_admin_module():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            source = path.read_text(encoding="utf-8")
            if "broker.order_admin" in source or "from broker import order_admin" in source:
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_no_active_python_consumer_uses_retired_broker_modules():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            source = path.read_text(encoding="utf-8")
            if (
                "broker.market_data" in source
                or "broker.strategy_broker" in source
                or "from broker import market_data" in source
                or "from broker import strategy_broker" in source
            ):
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_no_active_python_consumer_uses_retired_toss_prefixed_adapters():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            if "infrastructure.toss.toss_" in path.read_text(encoding="utf-8"):
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_kis_rest_client_does_not_import_legacy_state():
    imports = _imports_in(SRC_DIR / "infrastructure/kis/rest_client.py")

    assert "state.system_state" not in imports


def test_kis_ws_manager_does_not_import_legacy_runtime_modules():
    imports = _imports_in(SRC_DIR / "infrastructure/kis/ws_manager.py")

    assert "core.trading_config" not in imports
    assert "core.display" not in imports
    assert "state.system_state" not in imports
    assert "broker.kis_event_handler" not in imports


def test_kis_vendor_callbacks_use_runtime_collaborators():
    imports = _imports_in(SRC_DIR / "infrastructure/kis/vendor_callbacks.py")

    assert "core.display" not in imports
    assert "core.credentials" not in imports
    assert "state.system_state" not in imports


def test_strategy_execution_composition_uses_injected_dependencies():
    imports = _imports_in(SRC_DIR / "infrastructure/strategy_execution.py")

    assert "broker.market_data" not in imports
    assert "broker.strategy_broker" not in imports
    assert "data.config_manager" not in imports


def test_retired_data_gsheet_has_no_active_python_consumers():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            if "data.gsheet" in path.read_text(encoding="utf-8"):
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_no_active_python_consumer_uses_retired_data_modules():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            source = path.read_text(encoding="utf-8")
            if (
                "data.config_manager" in source
                or "data.calculate_weights" in source
                or "from data import config_manager" in source
                or "from data import calculate_weights" in source
            ):
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_no_active_python_consumer_uses_retired_price_utils():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            if "utils.price_utils" in path.read_text(encoding="utf-8"):
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_no_active_python_consumer_uses_retired_market_utils():
    roots = [SRC_DIR, SRC_DIR.parent / "tests", SRC_DIR.parent / "scripts"]
    consumers = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            if "utils.market_utils" in path.read_text(encoding="utf-8"):
                consumers.append(path.relative_to(SRC_DIR.parent).as_posix())

    assert consumers == []


def test_market_signals_status_api_uses_market_open_contract(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import infrastructure.market_signals as market_signals
assert not hasattr(market_signals, "is_market_holiday")
status = market_signals.get_us_market_status("2026-07-04")
assert set(status) == {"is_market_open", "message"}
assert status["is_market_open"] is False
assert "closed" in status["message"].lower()
""",
    )

    assert result.returncode == 0, result.stderr


def test_target_layer_and_vendor_import_rules_are_enforced():
    assert LEGACY_IMPORT_ALLOWLIST_VERSION == 2
    assert _find_import_violations(SRC_DIR) == []


def test_import_violation_reports_the_importing_path(tmp_path):
    source_root = tmp_path / "src"
    package = source_root / "domain" / "strategy"
    package.mkdir(parents=True)
    (package / "rules.py").write_text("from broker import kis_broker\n", encoding="utf-8")

    assert _find_import_violations(source_root) == [
        "domain/strategy/rules.py: broker"
    ]


def test_vendor_allowlist_is_empty_after_kis_vendor_migration():
    assert LEGACY_IMPORT_ALLOWLIST == {}


def test_vendor_kis_import_does_not_load_application_owned_packages(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import infrastructure.kis.kis_api.kis_auth
for prefix in ("application", "broker", "core", "data", "domain", "interfaces", "state", "toss"):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules)
""",
    )

    assert result.returncode == 0, result.stderr


def test_domain_and_port_imports_do_not_load_runtime_dependencies(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import sys
import application.ports
import domain.portfolio
import domain.strategy
for prefix in ("kis", "toss", "telegram", "fastapi", "core"):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules)
""",
    )

    assert result.returncode == 0, result.stderr
