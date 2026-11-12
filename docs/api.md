# API 사용 요약

기준 주소 `http://127.0.0.1:8000`. JSON 요청·응답, 가입/로그인 후 `Authorization: Bearer <access_token>`을 사용한다. `/docs`에서 전체 입력·출력 스키마와 Try it out을 제공한다. 응답에 비밀번호 해시는 포함하지 않는다.

| 메서드·경로 | 동작 |
|---|---|
| GET /api/health | DB 연결·AI 실행 모드 확인 |
| POST /api/auth/register | `{user_id,password,name,email}` 가입, 토큰 반환 |
| POST /api/auth/login | `{user_id,password}` 로그인, 토큰 반환 |
| GET /api/users/me | 내 회원 정보 |
| PATCH /api/users/me | `{name,email}` 수정 |
| PUT /api/users/me/password | `{current_password,new_password}` 변경, 기존 토큰 무효화 |
| DELETE /api/users/me | `{password}` 확인 후 회원·학습·실험 삭제 |
| GET /api/topics | 공용 학습주제 |
| POST /api/sessions | `{topic_id,title}` 생성 |
| GET /api/sessions | 내 세션 목록 |
| GET /api/sessions/{id} | 내 세션 상세 |
| PATCH /api/sessions/{id} | `{title,status}` 수정 |
| DELETE /api/sessions/{id} | 내 세션·대화·문제·풀이 삭제 |
| GET /api/sessions/{id}/messages | 소유 세션 대화 |
| POST /api/sessions/{id}/messages | `{content}` 질문, 사용자·AI 쌍 반환 |
| GET /api/sessions/{id}/questions | 문제 목록(정답 제외) |
| POST /api/sessions/{id}/questions | 주제별 문제 1개 생성 |
| GET /api/questions/{id}/attempts | 모든 제출 이력·피드백 |
| POST /api/questions/{id}/attempts | `{submitted_answer}`, 새 풀이와 결과·정답·해설 반환 |
| GET /api/stats | 내 주제별 session_count/attempt_count/correct_count/pending_count/accuracy |
| GET /api/experiments | 내 실험 목록 |
| POST /api/experiments | `{question,prompt_a,prompt_b}`, A/B 두 결과 생성·저장 |
| GET /api/experiments/{id} | 소유 실험과 두 결과 |
| DELETE /api/experiments/{id} | 내 실험·결과 삭제 |

목록 API는 세션·메시지·문제·풀이·실험에 `offset=0&limit=100`을 지원한다. limit 1~100, offset 0 이상이다. UI는 여러 페이지를 순서대로 조회하여 이전 기록을 누락하지 않는다.

진행중인 세션에서만 대화·문제·풀이를 생성한다. 완료/중단 상태는 읽을 수 있고, 세션 수정에서 진행중으로 바꾸면 학습을 재개할 수 있다. 다른 회원의 세션·메시지·문제·풀이·실험 경로는 모두 404다.

| 상태 | 의미 |
|---|---|
| 201 / 204 | 생성 성공 / 삭제 성공(본문 없음) |
| 400 | 현재 비밀번호 불일치 |
| 401 | 인증 실패·만료·폐기된 토큰 |
| 404 | 리소스 없음 또는 타인 소유 |
| 409 | 중복·FK 충돌 또는 진행중이 아닌 학습에 쓰기 |
| 422 | 입력 필수값·길이·형식 검증 실패 |
| 429 | 로그인/가입 요청 한도 초과 |
| 502 / 503 | AI 호출 실패 / DB 연결 실패 |

AI 실패 요청은 재시도할 수 있지만 **성공한 요청을 다시 보내면 새 기록이 생성**된다. 이 프로젝트는 네트워크 재전송에 대한 멱등 키를 구현하지 않았으며, UI는 처리 중 버튼을 잠가 중복 클릭을 막는다.
