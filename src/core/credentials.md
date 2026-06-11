# Trading Credentials

`src/core/credentials.py` owns shared encrypted credential loading for KIS and
Toss integrations.

Runtime files live under `~/KIS_config/`:

| File | Purpose |
| --- | --- |
| `password.txt` | Password used to derive the Fernet key |
| `credentials.enc` | Encrypted KIS and Toss credential payload |
| `KISYYYYMMDD` | KIS access token cache |
| `TOSSYYYYMMDD_HHMMSS.json` | Toss access token cache |

Toss token initialization is date-based: if a `TOSSYYYYMMDD_*.json` file exists
for today, startup reuses it. Once the date changes after midnight, startup
issues a new Toss token instead of calculating from the token expiration time.

`credentials.enc` supports two comma-separated encrypted payload shapes:

```text
KIS_APP_KEY,KIS_APP_SECRET,KIS_HTS_ID
KIS_APP_KEY,KIS_APP_SECRET,KIS_HTS_ID,TOSS_CLIENT_ID,TOSS_CLIENT_SECRET
```

The 3-field form remains readable so existing KIS credentials continue to
work. Toss requires the 5-field form.

Generate or replace the encrypted file with:

```bash
venv/bin/python scripts/generate_credentials.py
```
