# Trading Credentials

`src/core/credentials.py`는 KIS와 Toss 연동에서 공통으로 사용하는 암호화된
자격 증명 로딩을 담당합니다.

런타임 파일은 `~/KIS_config/` 아래에 둡니다.

| 파일 | 용도 |
| --- | --- |
| `password.txt` | Fernet 키를 만들 때 사용하는 비밀번호 |
| `credentials.enc` | 암호화된 KIS/Toss 자격 증명 |
| `KISYYYYMMDD` | KIS access token 캐시 |
| `TOSSYYYYMMDD_HHMMSS.json` | Toss access token 캐시 |

Toss 토큰 초기화는 저장된 토큰을 재사용하기 전에 만료 시각을 확인합니다.
오늘 날짜의 최신 `TOSSYYYYMMDD_*.json` 파일이 이미 만료되었거나 safety
margin 안에 있으면 시작 과정에서 새 Toss 토큰을 발급합니다.

런타임 Toss API helper도 저장된 최신 토큰을 사용하기 전에 만료 여부를
확인합니다. 봇이 실행 중인 동안 토큰이 만료되면 `toss.auth.load_access_token()`
이 새 토큰을 발급한 뒤 갱신된 access token을 반환합니다.

Telegram 알림은 토큰 갱신 자체가 아니라 Toss API query가 최종 실패했을 때
`toss.client.request_json()` 경계에서 전송합니다. 따라서 holdings,
buying-power, orders 같은 Toss 조회 실패는 로그뿐 아니라 Telegram으로도
운영자에게 전달됩니다.

`credentials.enc`는 쉼표로 구분된 다음 두 가지 암호화 payload 형식을
지원합니다.

```text
KIS_APP_KEY,KIS_APP_SECRET,KIS_HTS_ID
KIS_APP_KEY,KIS_APP_SECRET,KIS_HTS_ID,TOSS_CLIENT_ID,TOSS_CLIENT_SECRET
```

기존 KIS 자격 증명이 계속 동작하도록 3필드 형식도 읽을 수 있습니다.
Toss를 사용하려면 5필드 형식이 필요합니다.

암호화 파일을 생성하거나 교체하려면 다음 명령을 사용합니다.

```bash
venv/bin/python scripts/generate_credentials.py
```
