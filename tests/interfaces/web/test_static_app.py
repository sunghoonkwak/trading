from pathlib import Path

APP_JS = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "interfaces"
    / "web"
    / "static"
    / "app.js"
)


def test_dashboard_does_not_build_inline_event_handlers_from_data():
    source = APP_JS.read_text(encoding="utf-8")

    assert "onclick=" not in source
    assert "showCancelConfirm(id, order.ticker)" in source
    assert "copyMemoToClipboard(memo)" in source


def test_dashboard_uses_text_nodes_for_external_order_and_memo_values():
    source = APP_JS.read_text(encoding="utf-8")

    assert "createTextSpan(order.name" in source
    assert "header.textContent = date" in source
    assert "textSpan.textContent = isExpanded ? text : displayHeader" in source
    assert "escapeHtml(acc.account_name || acc.account_id || 'Unknown')" in source
