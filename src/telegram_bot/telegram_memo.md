# Telegram Memo (`src/telegram_bot/telegram_memo.py`)

## Overview (개요)
Telegram 일반 텍스트 메시지를 `memo.json`에 저장하고, 최근 1주일 메모를
조회하는 명령어를 제공합니다. 컴퓨터를 떠나 있을 때 버그, 아이디어, 작업
메모를 남기는 용도입니다.

## Core Logic (핵심 로직)
- **Auto Save**: 명령어가 아닌 텍스트 메시지를 KST 타임스탬프와 함께 저장합니다.
- **Date Grouping**: 날짜별로 메시지를 그룹화합니다.
- **Weekly View**: `/memo` 명령으로 최근 1주일 메모를 조회합니다.

## Commands (명령어)
| Command | Description |
|---------|-------------|
| `/memo` | View recent memos (1 week) |
| `{any text}` | Save as memo (returns today/weekly count) |

## Configuration (`memo.json`)
```json
{
  "2026-01-03": [
    "15:54:04 : 메모 기능 테스트",
    "16:03:09 : 버그 발견 - 주문버튼"
  ]
}
```

## Response Format (응답 형식)
- **Save**: `📝 Saved (today: 3, total: 5)` (total = last 7 days)
- **View**: Date-grouped list with bullet points
