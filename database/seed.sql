-- Public, disposable demo account only: demo_student / LoopDemo2026!
-- Re-running this seed never overwrites a changed password or user data.
BEGIN;
INSERT INTO users (user_id, password_hash, name, email) VALUES
('demo_student', '$argon2id$v=19$m=65536,t=3,p=4$u9az/WodOpmG6GZv6w/GTg$F9qng+P0DwMVKGH7ia+oCyH+/lH0Zf/06wzDeXwurlY', '데모 학습자', 'demo@example.invalid')
ON CONFLICT DO NOTHING;
INSERT INTO topics (topic_id, name, description) VALUES
(1, '데이터베이스', '관계형 모델, 기본키·외래키, SQL과 정규화'),
(2, 'Python', '자료형, 함수, 반복문과 프로그램 기초'),
(3, '인공지능', '지도학습, 모델 평가와 데이터 분리')
ON CONFLICT DO NOTHING;
INSERT INTO sessions (session_id, user_id, topic_id, title, status) VALUES
(1, 'demo_student', 1, '기본키와 외래키 이해하기', 'completed') ON CONFLICT DO NOTHING;
INSERT INTO messages (message_id, session_id, role, content) VALUES
(1, 1, 'user', '기본키와 외래키의 차이를 알려줘.'),
(2, 1, 'assistant', '[데모 예시] 기본키는 행을 유일하게 식별하고, 외래키는 다른 테이블의 키를 참조하여 관계를 유지합니다.')
ON CONFLICT DO NOTHING;
INSERT INTO questions (question_id, session_id, content, answer, explanation) VALUES
(1, 1, '테이블의 각 행을 유일하게 식별하는 키는? (기본키/외래키)', '기본키', '기본키는 중복과 NULL을 허용하지 않습니다.')
ON CONFLICT DO NOTHING;
INSERT INTO attempts (attempt_id, question_id, submitted_answer, is_correct, ai_feedback) VALUES
(1, 1, '외래키', FALSE, '[데모 채점] 외래키는 다른 테이블의 키를 참조합니다.'),
(2, 1, '기본키', TRUE, '[데모 채점] 정답입니다. 기본키는 각 행을 유일하게 식별합니다.')
ON CONFLICT DO NOTHING;
INSERT INTO prompt_experiments (experiment_id, user_id, question) VALUES
(1, 'demo_student', '정규화를 설명해줘.') ON CONFLICT DO NOTHING;
INSERT INTO experiment_results (result_id, experiment_id, variant, prompt, response) VALUES
(1, 1, 'A', '한 문장으로 설명해줘.', '[데모 A] 정규화는 중복과 갱신 이상을 줄이도록 테이블을 분리하는 과정입니다.'),
(2, 1, 'B', '초보자를 위해 예시와 함께 설명해줘.', '[데모 B] 학생 이름을 수강 행마다 저장하면 수정할 곳이 많아집니다. 학생과 수강 테이블을 분리하고 학생번호로 연결하면 이 중복을 줄일 수 있습니다.')
ON CONFLICT DO NOTHING;
-- Never move an identity sequence backwards when seed is repeated.
SELECT setval(pg_get_serial_sequence('topics','topic_id'), GREATEST((SELECT max(topic_id) FROM topics), (SELECT last_value FROM topics_topic_id_seq)));
SELECT setval(pg_get_serial_sequence('sessions','session_id'), GREATEST((SELECT max(session_id) FROM sessions), (SELECT last_value FROM sessions_session_id_seq)));
SELECT setval(pg_get_serial_sequence('messages','message_id'), GREATEST((SELECT max(message_id) FROM messages), (SELECT last_value FROM messages_message_id_seq)));
SELECT setval(pg_get_serial_sequence('questions','question_id'), GREATEST((SELECT max(question_id) FROM questions), (SELECT last_value FROM questions_question_id_seq)));
SELECT setval(pg_get_serial_sequence('attempts','attempt_id'), GREATEST((SELECT max(attempt_id) FROM attempts), (SELECT last_value FROM attempts_attempt_id_seq)));
SELECT setval(pg_get_serial_sequence('prompt_experiments','experiment_id'), GREATEST((SELECT max(experiment_id) FROM prompt_experiments), (SELECT last_value FROM prompt_experiments_experiment_id_seq)));
SELECT setval(pg_get_serial_sequence('experiment_results','result_id'), GREATEST((SELECT max(result_id) FROM experiment_results), (SELECT last_value FROM experiment_results_result_id_seq)));
COMMIT;
