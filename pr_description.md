🎯 What:
- `backend/core/runtime_secrets.py` 내의 `build_encryption_keyring` 함수에 대한 누락된 단위 테스트를 추가했습니다.

📊 Coverage:
- 새로운 `EncryptionKeyRing` 생성에 대한 유효한 케이스(이전 키가 없는 경우 및 있는 경우)를 테스트했습니다.
- 입력값 오류 시 발생하는 에러 케이스(Active 키가 누락되었거나 유효하지 않은 경우, 이전 키들 포맷이 잘못된 경우, 식별자가 중복된 경우 등)를 전부 처리했습니다.

✨ Result:
- `build_encryption_keyring` 함수의 테스트 커버리지가 강화되었고 엣지 케이스들을 커버함으로써 이후 발생할 수 있는 리팩토링 시의 안전망이 구축되었습니다.
