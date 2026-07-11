import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_toss_infrastructure_uses_the_same_legacy_compatibility_functions():
    from infrastructure.toss.get_holdings import get_holdings as infrastructure_get_holdings
    from toss.get_holdings import get_holdings as legacy_get_holdings

    assert legacy_get_holdings is infrastructure_get_holdings


def test_toss_infrastructure_import_does_not_load_telegram_interface():
    client_path = Path(__file__).resolve().parents[2] / "src/infrastructure/toss/client.py"
    tree = ast.parse(client_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "telegram_bot.telegram_utils" not in imported_modules
