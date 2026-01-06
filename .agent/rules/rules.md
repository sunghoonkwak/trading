---
trigger: always_on
---

# Rules

---

## 0. *****가장 중요*****
.antigravityignore에 기입된 폴더나 파일은 절대 읽지마

## 1. Conversation Rules
1. Use Korean if possible.
2. Use **bold style** for important points.

## 2. MCP
1. MCP사용을 매우매우 권장함

## 2. Command Execution Rules
1. Only ask for git commands when committing.
2. Do not ask when reading project files.

## 3. coding rules
1. Only English is available. Never use Korean.
2. 앞으로 작성할 모든 코드에서 API 키나 비밀번호는 직접 입력하지 말고, 반드시 내가 미리 만들어둔 load_credentials() 함수를 호출하는 방식으로 작성해줘. 그리고 민감한 정보가 담긴 .enc 파일은 절대 읽지 마

## 4. Commit Message
1. Every commit message should follow this structure:

```text
<type>(<scope>): <subject>

[body]

[footer]
```
2. Follow 72/50 rule.

3. commit message 요청시 그냥 보여줘 commit command run할 준비하지마, 그리고 md파일 수정 안했으면 수정해