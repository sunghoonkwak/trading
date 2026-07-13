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
assert "kis.kis_api.kis_auth" not in sys.modules
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
assert "kis.kis_api.kis_auth" not in sys.modules
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


def test_strategy_modules_do_not_import_kis_constants():
    offenders = []
    for path in (SRC_DIR / "strategy").glob("*.py"):
        if "kis.constants" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)

    assert offenders == []


def test_broker_package_import_does_not_touch_kis_config(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import pathlib
import broker.kis_broker
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
assert "kis.kis_api.kis_auth" not in sys.modules
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


def test_portfolio_integration_does_not_import_legacy_display():
    imports = _imports_in(SRC_DIR / "infrastructure/portfolio/integration.py")

    assert "core.display" not in imports


def test_market_utils_status_api_uses_market_open_contract(tmp_path):
    result = _run_import_check(
        tmp_path,
        """
import utils.market_utils as market_utils
assert not hasattr(market_utils, "is_market_holiday")
status = market_utils.get_us_market_status("2026-07-04")
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
import kis.kis_api.kis_auth
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
