"""Regression checks for durable layered-architecture contracts."""

import ast
import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _is_package_or_child(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def _find_import_violations(source_root: Path) -> list[str]:
    """Return imports that violate the repository's permanent layer rules."""
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
                if any(_is_package_or_child(module, package) for package in forbidden):
                    violations.append(f"{relative_path}: {module}")
    return sorted(violations)


def _run_import_check(tmp_path: Path, code: str) -> subprocess.CompletedProcess[str]:
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


def test_layer_import_rules_are_enforced():
    assert _find_import_violations(SRC_DIR) == []


def test_import_violation_reports_the_importing_path(tmp_path):
    source_root = tmp_path / "src"
    package = source_root / "domain" / "strategy"
    package.mkdir(parents=True)
    (package / "rules.py").write_text("from broker import kis_broker\n", encoding="utf-8")

    assert _find_import_violations(source_root) == ["domain/strategy/rules.py: broker"]


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
