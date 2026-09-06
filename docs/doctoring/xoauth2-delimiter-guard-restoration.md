# XOAUTH2 입력 검사 삭제 복원

## 상태와 원인

2026-09-06 제안. Naruon #1287의 원격 HEAD
`5aa3f4854ecf23994d401379979b8a60c924135f`에서 사용자명·토큰의 Control-A
거부 검사와 두 회귀 테스트가 함께 삭제돼 있었다. merge-base
`81c105645ca6e680f5f8c15ba9c33b67eb63c48b`에는 이미 검사가 있었고,
`0279faef`가 이를 명시적으로 삭제했다. 최신 develop 병합만으로 복구된다고
가정하지 않는다. 보호 브랜치의 기존 #1340 구현을 이 PR 안에서 복원한다.

Google의 XOAUTH2 형식에서 Control-A는 필드 경계다. 임의 입력을 base64로
바꾸는 것만으로 경계 삽입이 방지되지는 않는다.
([Google, n.d.](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol))
직접 호출 검색에는 정의와 테스트만 있으므로, 현재 메일 전송 경로에서
실제 인증 우회가 발생했다고 주장하지 않는다.

## 검증 경계

`aa3c50b946b907c41829242dbf1d161a3bbf208f`는 두 악성 입력 모두
`DID NOT RAISE ValueError`로 실패했다. 검사 복원 커밋
`8e397fec2e7b935d05e0fed48e857b2c8a7b46f2`에서는 두 반례와 파일 전체 11개
테스트가 통과했다. 후속 검증은 정상 메시지의 정확한 바이트도 확인한다.
변경한 두 Python 파일의 기존 포맷 오류는 Ruff로 기계적으로 정리했다.

독립 단위 검증은 운영자 환경을 상속하지 않고, 설정 객체의 최초 생성에만
빈 환경 파일 목록을 주입한다. 실제 운영 설정 조회를 고치거나 시험한 것은 아니다.
정규 절대 경로의 프로젝트 가상환경을 사용하며 `../`가 포함된 실행 경로의
Python 시작 경고를 통과 증거에 포함하지 않는다. 정확한 최종 HEAD·명령·출력은
PR 영수증에 기록한다. `--noconftest` 검증은 전체 API·DB 통합 검증이 아니다.

#1287은 Draft 전환 당시 원격 `5aa3f485` 기준 102개 파일의 혼합 변경과
충돌이 남아 있었다. 이 근거 문서를 추가한 복원 후보의 비교 파일 수는 103개다.
이 복원은 기존 다른 변경을 삭제하거나 승계 완료로 처리하지 않는다. 전체 변경의
소유권·유효 delta·충돌·전체 테스트·독립 승인·보호 병합은 별도 검증해야 한다.
#1417의 SMTP 연결 정리 변경을 복사하지 않는다.

## 참고 문헌

Google. (n.d.). *OAuth 2.0 mechanism.* Google for Developers. Retrieved September 6, 2026, from https://developers.google.com/workspace/gmail/imap/xoauth2-protocol
