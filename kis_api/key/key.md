# key.md

이 모듈은 암호화 키 파생 및 저장된 인증 정보 검색을 위한 핵심 암호화 로직을 제공합니다.

## Purpose (목적)
사용자 비밀번호로부터 암호화 키를 파생시키고 저장된 인증 파일을 복호화함으로써 API 키를 안전하게 관리하는 것입니다.

## Function (기능)

### generate_key_from_password
PBKDF2HMAC 알고리즘과 SHA256을 사용하여 평문 비밀번호로부터 URL-safe base64 인코딩된 키를 파생시킵니다.
#### input
- `password` (str): 사용자가 입력한 암호화 비밀번호.
#### output
- `bytes`: 파생된 암호화 키.

### get_secrets_from_password
`credentials.enc`로부터 암호화된 인증 정보를 로드하고, 비밀번호로 파생된 키를 사용하여 복호화한 후 개별 비밀 값들을 반환합니다.
- 앱 키(App Key), 앱 시크릿(App Secret), HTS ID의 전체 복호화 및 파싱을 처리합니다.
#### input
- `None`
#### output
- `tuple[str, str, str]`: (저장된 키, 저장된 시크릿, 저장된 HTS ID)를 포함하는 튜플.
