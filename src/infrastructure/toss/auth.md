# Toss Authentication Adapter

`infrastructure.toss.auth`는 OAuth token 발급, 저장, 만료 확인, 재발급을
담당한다. private config root와 credential loader는
`configure_auth_configuration()`으로 composition root가 주입한다.

구성이 없는 adapter는 token 또는 credential 파일을 추측해서 읽지 않고
fail-closed 한다. `src/main.py`는 Toss startup 전에 이 collaborator를
조립한다.

`toss.auth`는 기존 scripts와 tests의 compatibility shim이다. 그것만 기존
private configuration collaborator를 등록하며 새 production consumer는
infrastructure adapter를 직접 사용한다.
