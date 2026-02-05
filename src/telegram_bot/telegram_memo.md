# Telegram Memo Module

## Overview
Saves arbitrary text messages from Telegram to `memo.json` for later review.
Useful for noting bugs, feature ideas, or tasks while away from the computer.

## Features
- **Auto Save**: Any non-command text message is saved with timestamp
- **Date Grouping**: Messages grouped by date (KST)
- **Weekly View**: `/memo` shows recent 1 week of messages

## Commands
| Command | Description |
|---------|-------------|
| `/memo` | View recent memos (1 week) |
| `{any text}` | Save as memo (returns today/weekly count) |

## File Format (`memo.json`)
```json
{
  "2026-01-03": [
    "15:54:04 : 메모 기능 테스트",
    "16:03:09 : 버그 발견 - 주문버튼"
  ]
}
```

## Response Format
- **Save**: `📝 Saved (today: 3, total: 5)` (total = last 7 days)
- **View**: Date-grouped list with bullet points
