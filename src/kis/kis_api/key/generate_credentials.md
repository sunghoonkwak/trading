# generate_credentials.md

이 유틸리티 스크립트는 암호화된 인증 정보 저장소를 안전하게 초기화하는 데 사용됩니다.

## Purpose (목적)
사용자가 민감한 API 인증 정보를 한 번 입력하면, 이를 비밀번호로 암호화하여 `credentials.enc`에 안전하게 저장함으로써 소스 코드에 비밀값이 하드코딩되는 것을 방지합니다.

## Function (기능)

### 스크립트 실행 (메인 로직)
`getpass`를 사용하여 사용자로부터 암호화 비밀번호와 KIS API 인증 정보(App Key, Secret, HTS ID)를 입력받습니다.
- `Fernet` 대칭 암호화 방식을 사용하여 결합된 데이터를 암호화합니다.
- 결과 암호문을 `credentials.enc` 파일로 저장합니다.
#### input
- `getpass`를 통한 대화형 사용자 입력.
#### output
- `credentials.enc`: 민감한 인증 정보가 포함된 암호화된 파일.
