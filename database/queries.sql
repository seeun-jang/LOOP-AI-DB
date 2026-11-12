-- Run after schema.sql and seed.sql, with psql -v ON_ERROR_STOP=1 -f database/queries.sql.
-- Queries use the public disposable demo account. Application APIs bind the logged-in user.
-- Entire demonstration is rolled back, including the temporary CRUD records.
BEGIN;
-- 01. 회원 조회 (비밀번호 해시 제외)
SELECT user_id, name, email FROM users WHERE user_id='demo_student';
-- 02. 학습주제 조회
SELECT topic_id, name, description FROM topics ORDER BY topic_id;
-- 03. 회원별 세션 조회
SELECT s.session_id,s.title,s.started_at,s.status,t.name AS topic_name
FROM sessions s JOIN topics t USING(topic_id)
WHERE s.user_id='demo_student' ORDER BY s.started_at DESC,s.session_id DESC;
-- 04. 대화 조회: 소유 세션을 통해 접근
SELECT m.* FROM messages m JOIN sessions s USING(session_id)
WHERE s.user_id='demo_student' ORDER BY m.message_id;
-- 05. 문제 조회 (정답은 서버 채점에 사용; 최초 학습 화면에는 제외)
SELECT q.* FROM questions q JOIN sessions s USING(session_id)
WHERE s.user_id='demo_student' ORDER BY q.question_id;
-- 06. 반복 제출 및 피드백 조회
SELECT a.* FROM attempts a JOIN questions q USING(question_id) JOIN sessions s USING(session_id)
WHERE s.user_id='demo_student' ORDER BY a.attempt_id;
-- 07. 주제별 학습 횟수와 정답률: 시도별 집계, 세션 중복 제거
SELECT t.name,COUNT(DISTINCT s.session_id) AS session_count,COUNT(a.attempt_id) AS attempt_count,
       COUNT(a.attempt_id) FILTER(WHERE a.is_correct IS TRUE) AS correct_count,
       ROUND(100.0*COUNT(a.attempt_id) FILTER(WHERE a.is_correct IS TRUE)/NULLIF(COUNT(a.attempt_id),0),1) AS accuracy
FROM topics t LEFT JOIN sessions s ON s.topic_id=t.topic_id AND s.user_id='demo_student'
LEFT JOIN questions q ON q.session_id=s.session_id LEFT JOIN attempts a ON a.question_id=q.question_id
GROUP BY t.topic_id,t.name ORDER BY t.topic_id;
-- 08. A/B 실험 및 실험결과 조회
SELECT e.experiment_id,e.question,e.created_at,r.variant,r.prompt,r.response
FROM prompt_experiments e JOIN experiment_results r USING(experiment_id)
WHERE e.user_id='demo_student' ORDER BY e.experiment_id,r.variant;

DO $$
DECLARE
    uid VARCHAR(50) := 'sql_demo_' || txid_current();
    tid INTEGER; sid INTEGER; mid INTEGER; qid INTEGER; aid INTEGER; eid INTEGER; rid INTEGER;
BEGIN
    -- 09. 회원·학습주제 생성
    INSERT INTO users VALUES(uid,'$argon2id$v=19$m=65536,t=3,p=4$u9az/WodOpmG6GZv6w/GTg$F9qng+P0DwMVKGH7ia+oCyH+/lH0Zf/06wzDeXwurlY','SQL 실습','sql@example.invalid');
    INSERT INTO topics(name,description) VALUES('SQL 실습 '||uid,'롤백되는 임시 주제') RETURNING topic_id INTO tid;
    -- 10. 세션·메시지 생성
    INSERT INTO sessions(user_id,topic_id,title) VALUES(uid,tid,'CRUD 실습') RETURNING session_id INTO sid;
    INSERT INTO messages(session_id,role,content) VALUES(sid,'user','기본키란?') RETURNING message_id INTO mid;
    -- 11. 문제·풀이 생성
    INSERT INTO questions(session_id,content,answer,explanation) VALUES(sid,'행 식별 키는?','기본키','중복과 NULL 금지') RETURNING question_id INTO qid;
    INSERT INTO attempts(question_id,submitted_answer,is_correct,ai_feedback) VALUES(qid,'기본키',TRUE,'정답입니다.') RETURNING attempt_id INTO aid;
    -- 12. 프롬프트실험·A/B 실험결과 생성
    INSERT INTO prompt_experiments(user_id,question) VALUES(uid,'기본키란?') RETURNING experiment_id INTO eid;
    INSERT INTO experiment_results(experiment_id,variant,prompt,response) VALUES(eid,'A','짧게','행의 식별자') RETURNING result_id INTO rid;
    INSERT INTO experiment_results(experiment_id,variant,prompt,response) VALUES(eid,'B','예시로','학생번호는 학생 행의 식별자입니다.');
    -- 13. 회원·주제·세션·메시지 수정
    UPDATE users SET name='SQL 수정' WHERE user_id=uid;
    UPDATE topics SET description='주제 수정 예시' WHERE topic_id=tid;
    UPDATE sessions SET title='CRUD 완료',status='completed' WHERE session_id=sid;
    UPDATE messages SET content='기본키를 설명해주세요.' WHERE message_id=mid;
    -- 14. 문제·풀이·실험·결과 수정 (직접 SQL 관리 예시; UI는 제출 이력 불변)
    UPDATE questions SET explanation='기본키는 행의 고유한 식별자입니다.' WHERE question_id=qid;
    UPDATE attempts SET ai_feedback='근거를 포함한 피드백' WHERE attempt_id=aid;
    UPDATE prompt_experiments SET question='기본키의 역할은?' WHERE experiment_id=eid;
    UPDATE experiment_results SET response='행을 유일하게 식별합니다.' WHERE result_id=rid;
    -- 15. 8개 테이블 개별 삭제: 자식부터 부모 순서
    DELETE FROM attempts WHERE attempt_id=aid;
    DELETE FROM questions WHERE question_id=qid;
    DELETE FROM messages WHERE message_id=mid;
    DELETE FROM sessions WHERE session_id=sid;
    DELETE FROM experiment_results WHERE experiment_id=eid;
    DELETE FROM prompt_experiments WHERE experiment_id=eid;
    DELETE FROM topics WHERE topic_id=tid;
    DELETE FROM users WHERE user_id=uid;
END $$;
-- 16. 8 PK · 7 FK 및 참조 규칙 확인
SELECT table_name,constraint_type,constraint_name
FROM information_schema.table_constraints
WHERE constraint_schema=current_schema() AND constraint_type IN ('PRIMARY KEY','FOREIGN KEY')
ORDER BY table_name,constraint_type;
ROLLBACK;
-- Identity sequences may advance even after ROLLBACK; gaps are valid identifiers.
