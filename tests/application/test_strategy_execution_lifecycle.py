from application.strategy_execution_lifecycle import active_targets, history_for_date


def test_active_targets_keeps_only_enabled_configuration():
    assert active_targets(
        {
            "raoeo": {
                "targets": {
                    "TQQQ": {"enabled": True},
                    "SOXL": {"enabled": False},
                    "UPRO": {},
                }
            }
        },
        "raoeo",
    ) == {"TQQQ": {"enabled": True}, "UPRO": {}}


def test_history_for_date_returns_the_matching_entry_only():
    history = [{"date": "2026-07-14"}, {"date": "2026-07-15", "raoeo": {}}]

    assert history_for_date(history, "2026-07-15") == {"date": "2026-07-15", "raoeo": {}}
    assert history_for_date(history, "2026-07-16") is None
