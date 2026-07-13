import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

def test_toss_infrastructure_import_does_not_load_telegram_interface():
    client_path = Path(__file__).resolve().parents[3] / "src/infrastructure/toss/client.py"
    tree = ast.parse(client_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "interfaces.telegram.utils" not in imported_modules
