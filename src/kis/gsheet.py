# -*- coding: utf-8 -*-
"""
Compatibility wrapper for the Google Sheets portfolio data source.

New code should import from data.gsheet.
"""
from data.gsheet import (
    OWNERS,
    SCOPES,
    SERVICE_ACCOUNT_FILE,
    SPREADSHEET_NAME,
    connect_google_sheet,
    parse_worksheet_data,
)

__all__ = [
    "OWNERS",
    "SCOPES",
    "SERVICE_ACCOUNT_FILE",
    "SPREADSHEET_NAME",
    "connect_google_sheet",
    "parse_worksheet_data",
]
