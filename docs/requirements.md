# 요구사항 16개와 구현 대응

기준: 저장소의 2026-11-05 설계 보고서 3~4쪽. 원문 의미를 유지해 아래와 같이 구현했다. 모든 회원별 API는 로그인 토큰에서 소유자를 구하며 클라이언트가 회원 ID를 지정하지 않는다.

| 번호 | 요구사항 | 구현 및 확인 방법 | 테이블 |
|---|---|---|---|
| 01 | 아이디·비밀번호·이름·이메일로 회원가입 | 회원가입 화면, `POST /api/auth/register`, 필수값·형식 검증, Argon2id 해시 | users |
| 02 | 회원아이디로 식별, 중복 불가 | VARCHAR(50) PK, 중복 가입 409 | users |
| 03 | 주제번호·주제명·설명 유지 | 3개 주제 seed, `GET /api/topics`, 주제 카드 | topics |
| 04 | 주제번호로 식별, 여러 회원이 세션 생성 | topics PK, sessions.topic_id FK, 회원별 세션 생성 | topics, sessions |
| 05 | 한 회원이 여러 세션, 세션은 한 회원 소속 | `POST /api/sessions`, 회원 FK와 소유권 검증 | users, sessions |
| 06 | 세션번호·주제·제목·시작일시·상태 유지 | 자동 ID·TIMESTAMPTZ·상태 CHECK, 시작·수정 UI | sessions |
| 07 | 세션별 여러 메시지와 주체·내용·시각 유지 | 대화 입력, 사용자/AI 한 쌍 트랜잭션 저장, 메시지 ID순 재조회 | messages |
| 08 | 주제별 개념 설명·문제 제공 | 주제 문맥의 튜터·문제 생성, Gemini와 명시적 오프라인 데모 | messages, questions |
| 09 | 문제번호·소속세션·문제·정답·해설 유지 | 문제 생성 API, 정답/해설은 서버 보관, 최초 목록에는 정답 제외 | questions |
| 10 | 여러 번 답안 제출, 시도마다 결과 유지 | `POST /api/questions/{id}/attempts`, 매번 새 행 INSERT | attempts |
| 11 | 풀이별 AI 피드백 저장·재조회 | 제출과 함께 피드백 저장, 이전 시도별 표시 | attempts |
| 12 | 자신의 세션·대화·풀이 조회, 주제별 횟수·정답률 | 학습 기록·통계 화면, COUNT DISTINCT와 전체 시도 기준 집계 | sessions, messages, questions, attempts |
| 13 | 회원별 여러 프롬프트 실험, 질문·시각 유지 | `POST/GET /api/experiments`, 소유자·질문·생성 시각 | prompt_experiments |
| 14 | A/B별 프롬프트·응답 저장·비교 | A/B 비교 UI, UNIQUE(experiment_id,variant), A/B CHECK, 원자적 저장 | experiment_results |
| 15 | 자신의 세션 제목 수정·기록 삭제, 타인 접근 불가 | PATCH/DELETE sessions, 하위 데이터까지 소유권 검사, 타인 요청 404 | sessions 및 모든 하위 기록 |
| 16 | 모든 기록의 고유 ID·관계 일관성 | 8 PK·7 FK·CHECK·CASCADE/RESTRICT·트랜잭션, 실제 DB 검증 | 전체 |

Gemini는 키가 있어야 실제 생성형 AI로 동작한다. 이번 실제 시연·캡처는 `demo`이며, 고정 예시와 단답 일치 채점임을 화면에 명시했다. 데모의 기능 범위를 실제 AI 성능 검증으로 해석하지 않는다.
