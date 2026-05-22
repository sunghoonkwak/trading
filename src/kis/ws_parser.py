"""Helpers for normalizing KIS WebSocket records."""

from html import escape


SENSITIVE_COLUMNS = {
    "CUST_ID",
    "ACNT_NO",
    "ACNT_NO2",
    "ODER_NO",
    "OODER_NO",
    "ACNT_NAME",
}


def mask_record_for_log(record: list[str], columns: list[str]) -> list[str]:
    """Mask sensitive fields while preserving record positions for debugging."""
    masked = []
    for idx, value in enumerate(record):
        column = columns[idx] if idx < len(columns) else f"EXTRA_{idx}"
        masked.append("********" if column in SENSITIVE_COLUMNS else value)
    return masked


def mask_dict_for_log(data: dict) -> dict:
    """Mask sensitive fields in a named WebSocket record dump."""
    return {
        key: "********" if key in SENSITIVE_COLUMNS else value
        for key, value in data.items()
    }


def should_log_normalization(note: str | None, expected_truncation: bool) -> bool:
    """Return whether a normalization event should be logged as diagnostic drift."""
    if note is None:
        return False

    if expected_truncation and note.startswith("truncated "):
        return False

    return True


def should_send_schema_drift_alert(
    sent_at: dict[str, float],
    tr_id: str,
    now: float,
    interval_seconds: float = 3600.0,
) -> bool:
    """Return whether this TR_ID should send a schema drift alert now."""
    last_sent = sent_at.get(tr_id)
    if last_sent is not None and now - last_sent < interval_seconds:
        return False

    sent_at[tr_id] = now
    return True


def build_schema_drift_alert(
    tr_id: str,
    note: str,
    field_count: int,
    column_count: int,
) -> str:
    """Build a Telegram-safe schema drift alert without raw record values."""
    return (
        "⚠️ <b>KIS WebSocket schema drift</b>\n"
        f"TR: {escape(tr_id)}\n"
        f"Action: {escape(note)}\n"
        f"fields={field_count} columns={column_count}"
    )


def normalize_record(record: list[str], columns: list[str]) -> tuple[list[str], str | None]:
    """Return a record whose width matches the configured column list."""
    expected = len(columns)
    actual = len(record)

    if actual == expected:
        return record, None

    if actual < expected:
        missing_columns = columns[actual:]
        return record + [""] * (expected - actual), (
            f"padded {expected - actual} missing field(s): {missing_columns}"
        )

    extra_count = actual - expected
    return record[:expected], f"truncated {extra_count} extra field(s)"
