---
trigger: always_on
---

# 🚫 Prohibited Modifications (수정 금지)
1.  **Official API Preservation**: `src/kis/kis_api/` 디렉토리는 한국투자증권 공식 샘플 코드이므로 수정을 절대 금지합니다.
2.  **Explicit Consent**: 모든 코드 수정, 삭제, 파일 생성 작업 전에는 반드시 사용자에게 계획을 설명하고 명시적인 승인을 받아야 합니다.

# 🔄 Mandatory Workflow (필수 워크플로우)
1.  **Understand**: 코드 구조와 로그를 분석하여 근본 원인을 파악합니다.
2.  **Plan**: 단계별 수정 계획을 제안하고 승인을 받습니다.
3.  **Implement**: `GEMINI.md`의 아키텍처 가이드를 준수하며 코드를 구현합니다.
4.  **Verify**: 
    - `docker compose up -d --build` 실행 후 `docker logs my-trading-bot`으로 정상 동작을 확인합니다.
    - 사용자에게 구체적인 **Test Checklist**를 제공하여 검증을 완료합니다.
5.  **Document**: 
    - 모든 신규/수정된 `.py` 파일은 대응하는 `.md` 파일을 생성/업데이트해야 합니다.
    - 파일 삭제 시 대응하는 `.md` 파일도 반드시 함께 삭제합니다.
6.  **Commit**: 아래의 엄격한 커밋 규칙을 준수합니다.

# 📝 Commit Message Rules (STRICT)
- **Structure**: `<type>(<scope>): <subject>` (Body/Footer는 선택적이나 필요 시 72자 줄바꿈 준수)
- **Constraints**: 
    - **Subject**: 50자 이내. 파일명을 절대 포함하지 말고 "의도"와 "결과"에 집중합니다.
    - **Approval**: 커밋 메시지를 먼저 보여주고 사용자의 **확인(Confirm)**을 받은 후 `git commit`을 실행합니다.

# 📚 Documentation Rules
1.  **Template**: 모든 모듈 문서는 `templete/module_doc_template.md` 형식을 엄격히 따릅니다.
2.  **Language**: 
    - **Code**: 변수명, 주석, 로그 메시지는 모두 **English**만 사용합니다.
    - **Documentation**: `.md` 파일 내의 설명은 **Korean**을 사용합니다.
3.  **Sync**: `__init__.py`를 제외한 모든 `.py` 파일은 1:1로 대응하는 `.md` 파일이 존재해야 합니다.

# 🛠️ Coding Standards
- API 키, 패스워드 등 민감 정보는 절대 하드코딩하지 않습니다 (`~/KIS_config/` 외부 설정 파일 활용).
- 멀티 스레드 환경이므로 공유 자원 접근 시 Thread-safety를 항상 고려합니다.
