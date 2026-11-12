"""Real PostgreSQL integration tests in a unique disposable schema, never public."""
import uuid
import json
import httpx
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from psycopg import sql

from backend.config import ROOT, Settings
from backend.main import create_app
from backend.ai import Tutor
from backend.models import GeneratedQuestion, Grading


@pytest.fixture(scope='module')
def environment():
    base = Settings()
    schema = 'loop_test_' + uuid.uuid4().hex
    admin = psycopg.connect(base.database_url, autocommit=True)
    admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    parts = urlsplit(base.database_url)
    query = dict(parse_qsl(parts.query)); query['options'] = f'-csearch_path={schema}'
    url = urlunsplit(parts._replace(query=urlencode(query)))
    settings = Settings(database_url=url, ai_provider='demo')
    try:
        with psycopg.connect(url, autocommit=True) as db:
            db.execute((ROOT / 'database/schema.sql').read_text(encoding='utf-8'))
            db.execute((ROOT / 'database/seed.sql').read_text(encoding='utf-8'))
        app = create_app(settings)
        with TestClient(app) as client:
            yield client, app, url
    finally:
        assert schema.startswith('loop_test_') and len(schema) == 42
        admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        admin.close()


@pytest.fixture(scope='module')
def accounts(environment):
    client, _, _ = environment
    result = []
    for user_id in ('student_one', 'student_two'):
        response = client.post('/api/auth/register', json={'user_id':user_id, 'password':'TestPassword2026!', 'name':user_id, 'email':f'{user_id}@example.com'})
        assert response.status_code == 201, response.text
        assert 'password_hash' not in response.text
        result.append({'Authorization':'Bearer ' + response.json()['access_token']})
    return result


def test_authentication_and_profile(environment, accounts):
    client, _, _ = environment; one, _ = accounts
    assert client.get('/api/users/me').status_code == 401
    assert client.get('/api/users/me', headers={'Authorization':'Bearer forged'}).status_code == 401
    assert client.post('/api/auth/login', json={'user_id':'student_one', 'password':'wrong'}).status_code == 401
    assert client.post('/api/auth/login', json={'user_id':'student_one', 'password':'TestPassword2026!'}).status_code == 200
    duplicate = client.post('/api/auth/register', json={'user_id':'student_one','password':'AnotherPassword!','name':'중복','email':'other@example.com'})
    assert duplicate.status_code == 409
    result = client.patch('/api/users/me', headers=one, json={'name':'변경된 이름','email':'changed@example.com'})
    assert result.status_code == 200 and result.json()['name'] == '변경된 이름'
    assert client.get('/api/users/me', headers=one).json()['email'] == 'changed@example.com'
    invalid = client.post('/api/auth/register', json={'user_id':'x','password':'sensitive','name':'','email':'bad'})
    assert invalid.status_code == 422 and 'sensitive' not in invalid.text
    assert client.get('/api/sessions?offset=-1', headers=one).status_code == 422


def test_learning_workflow_ownership_and_cascades(environment, accounts):
    client, _, url = environment; one, two = accounts
    assert len(client.get('/api/topics', headers=one).json()) == 3
    assert client.post('/api/sessions', headers=one, json={'topic_id':99999,'title':'missing topic'}).status_code == 409
    session = client.post('/api/sessions', headers=one, json={'topic_id':1,'title':'키와 관계'}).json(); sid = session['session_id']
    root = f'/api/sessions/{sid}'
    assert client.get(root, headers=two).status_code == 404
    assert client.patch(root, headers=two, json={'title':'남의 기록','status':'completed'}).status_code == 404
    assert client.delete(root, headers=two).status_code == 404
    for suffix in ('messages','questions'):
        assert client.get(f'{root}/{suffix}', headers=two).status_code == 404
    assert client.post(f'{root}/messages', headers=two, json={'content':'침입'}).status_code == 404
    assert client.post(f'{root}/questions', headers=two).status_code == 404
    result = client.post(f'{root}/messages', headers=one, json={'content':"기본키 알려줘 <script>alert(1)</script> ' OR 1=1 --"})
    assert result.status_code == 201, result.text
    messages = client.get(f'{root}/messages', headers=one).json()
    assert [row['role'] for row in messages] == ['user','assistant']
    assert '<script>' in messages[0]['content']  # preserved data; browser uses textContent.
    question = client.post(f'{root}/questions', headers=one).json(); qid = question['question_id']
    assert 'answer' not in question
    assert 'answer' not in client.get(f'{root}/questions', headers=one).json()[0]
    attempt_path = f'/api/questions/{qid}/attempts'
    assert client.post(attempt_path, headers=two, json={'submitted_answer':'기본키'}).status_code == 404
    assert client.get(attempt_path, headers=two).status_code == 404
    wrong = client.post(attempt_path, headers=one, json={'submitted_answer':'외래키'})
    right = client.post(attempt_path, headers=one, json={'submitted_answer':'기본키'})
    assert wrong.status_code == right.status_code == 201
    assert not wrong.json()['is_correct'] and right.json()['is_correct']
    assert right.json()['answer'] == '기본키' and right.json()['ai_feedback']
    assert len(client.get(attempt_path, headers=one).json()) == 2
    # A second session with no attempt must still count exactly once.
    second = client.post('/api/sessions', headers=one, json={'topic_id':1,'title':'다음 학습'}).json()['session_id']
    stats = client.get('/api/stats', headers=one).json()
    assert stats[0]['session_count'] == 2 and stats[0]['attempt_count'] == 2 and stats[0]['accuracy'] == 50
    assert stats[1]['accuracy'] is None
    assert all(row['session_count'] == 0 for row in client.get('/api/stats', headers=two).json())
    assert client.patch(root, headers=one, json={'title':'수정된 제목','status':'completed'}).status_code == 200
    assert client.get(root, headers=one).json()['title'] == '수정된 제목'
    assert client.post(f'{root}/messages', headers=one, json={'content':'계속'}).status_code == 409
    assert client.post(attempt_path, headers=one, json={'submitted_answer':'기본키'}).status_code == 409
    assert client.delete(root, headers=one).status_code == 204
    assert client.get(root, headers=one).status_code == 404
    with psycopg.connect(url) as db:
        assert db.execute('SELECT count(*) FROM messages WHERE session_id=%s',(sid,)).fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM questions WHERE session_id=%s',(sid,)).fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM attempts WHERE question_id=%s',(qid,)).fetchone()[0] == 0
    client.delete(f'/api/sessions/{second}', headers=one)


def test_experiment_atomicity_and_access(environment, accounts, monkeypatch):
    client, app, url = environment; one, two = accounts
    body = {'question':'정규화란?','prompt_a':'짧게 설명','prompt_b':'예시와 함께'}
    result = client.post('/api/experiments', headers=one, json=body)
    assert result.status_code == 201, result.text
    eid = result.json()['experiment_id']
    assert [row['variant'] for row in result.json()['results']] == ['A','B']
    assert client.get(f'/api/experiments/{eid}', headers=two).status_code == 404
    assert client.delete(f'/api/experiments/{eid}', headers=two).status_code == 404
    assert client.get(f'/api/experiments/{eid}', headers=one).json()['results'][1]['prompt'] == body['prompt_b']
    before = len(client.get('/api/experiments', headers=one).json())
    original = app.state.tutor.chat
    def fail_b(topic, history, instruction=''):
        if instruction == body['prompt_b']:
            raise HTTPException(502,'Simulated provider failure')
        return original(topic, history, instruction)
    with monkeypatch.context() as patch:
        patch.setattr(app.state.tutor, 'chat', fail_b)
        assert client.post('/api/experiments', headers=one, json=body).status_code == 502
    assert len(client.get('/api/experiments', headers=one).json()) == before
    assert client.delete(f'/api/experiments/{eid}', headers=one).status_code == 204
    with psycopg.connect(url) as db:
        assert db.execute('SELECT count(*) FROM experiment_results WHERE experiment_id=%s',(eid,)).fetchone()[0] == 0


def test_ai_failure_does_not_save_partial_messages(environment, accounts, monkeypatch):
    client, app, _ = environment; one, _ = accounts
    sid = client.post('/api/sessions', headers=one, json={'topic_id':2,'title':'실패 복구'}).json()['session_id']
    def fail(*args, **kwargs): raise HTTPException(502,'Simulated timeout')
    with monkeypatch.context() as patch:
        patch.setattr(app.state.tutor, 'chat', fail)
        assert client.post(f'/api/sessions/{sid}/messages', headers=one, json={'content':'질문'}).status_code == 502
    assert client.get(f'/api/sessions/{sid}/messages', headers=one).json() == []
    with pytest.raises(HTTPException): app.state.tutor.parse(GeneratedQuestion, '{bad json')
    with pytest.raises(HTTPException): app.state.tutor.parse(Grading, '{"is_correct":"false","feedback":"bad"}')
    client.delete(f'/api/sessions/{sid}', headers=one)


def test_concurrent_messages_preserve_paired_order(environment, accounts):
    client, _, _ = environment; one, _ = accounts
    sid = client.post('/api/sessions', headers=one, json={'topic_id':2,'title':'동시 요청'}).json()['session_id']
    def send(content): return client.post(f'/api/sessions/{sid}/messages', headers=one, json={'content':content})
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(send, ['첫 질문','다음 질문']))
    assert all(response.status_code == 201 for response in responses)
    assert [message['role'] for message in client.get(f'/api/sessions/{sid}/messages', headers=one).json()] == ['user','assistant','user','assistant']
    client.delete(f'/api/sessions/{sid}', headers=one)


def test_database_constraints_and_seed_repeat(environment):
    _, _, url = environment
    with psycopg.connect(url, autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'").fetchone()[0] == 8
        for kind, expected in [('PRIMARY KEY',8),('FOREIGN KEY',7)]:
            assert db.execute('SELECT count(*) FROM information_schema.table_constraints WHERE constraint_schema=current_schema() AND constraint_type=%s',(kind,)).fetchone()[0] == expected
        for query in ["INSERT INTO sessions(user_id,topic_id,title) VALUES ('missing',1,'bad')",
                      "INSERT INTO sessions(user_id,topic_id,title,status) VALUES ('demo_student',1,'bad','invalid')",
                      "INSERT INTO messages(session_id,role,content) VALUES (1,'system','bad')",
                      "INSERT INTO experiment_results(experiment_id,variant,prompt,response) VALUES (1,'A','duplicate','bad')",
                      "INSERT INTO experiment_results(experiment_id,variant,prompt,response) VALUES (1,'C','bad','bad')",
                      'DELETE FROM topics WHERE topic_id=1']:
            with pytest.raises(psycopg.IntegrityError): db.execute(query)
        before = db.execute('SELECT last_value FROM sessions_session_id_seq').fetchone()[0]
        db.execute((ROOT/'database/seed.sql').read_text(encoding='utf-8'))
        assert db.execute('SELECT last_value FROM sessions_session_id_seq').fetchone()[0] >= before


def test_password_revocation_and_account_delete(environment, accounts):
    client, _, url = environment; one, _ = accounts
    assert client.put('/api/users/me/password', headers=one, json={'current_password':'wrong','new_password':'NewPassword2026!'}).status_code == 400
    assert client.put('/api/users/me/password', headers=one, json={'current_password':'TestPassword2026!','new_password':'NewPassword2026!'}).status_code == 200
    assert client.get('/api/users/me', headers=one).status_code == 401
    response = client.post('/api/auth/login', json={'user_id':'student_one','password':'NewPassword2026!'})
    headers = {'Authorization':'Bearer '+response.json()['access_token']}
    client.post('/api/sessions', headers=headers, json={'topic_id':1,'title':'탈퇴 시 삭제'})
    client.post('/api/experiments', headers=headers, json={'question':'질문','prompt_a':'A','prompt_b':'B'})
    assert client.request('DELETE','/api/users/me', headers=headers,json={'password':'wrong'}).status_code == 400
    assert client.request('DELETE','/api/users/me', headers=headers,json={'password':'NewPassword2026!'}).status_code == 204
    assert client.get('/api/users/me', headers=headers).status_code == 401
    with psycopg.connect(url) as db:
        assert db.execute("SELECT count(*) FROM sessions WHERE user_id='student_one'").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM prompt_experiments WHERE user_id='student_one'").fetchone()[0] == 0


def test_static_web_and_headers(environment):
    client, _, _ = environment
    for path in ('/','/app.js','/style.css','/favicon.svg','/docs','/openapi.json'):
        assert client.get(path).status_code == 200
    assert client.get('/.env').status_code == 404
    assert client.get('/database/schema.sql').status_code == 404
    assert "script-src 'self'" in client.get('/').headers['Content-Security-Policy']
    assert client.get('/api/health').headers['Cache-Control'] == 'no-store'


def test_sql_crud_script_rolls_back(environment):
    _, _, url = environment
    with psycopg.connect(url, autocommit=True) as db:
        tables = ['users','topics','sessions','messages','questions','attempts','prompt_experiments','experiment_results']
        counts = lambda: [db.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0] for table in tables]
        before = counts()
        db.execute((ROOT/'database/queries.sql').read_text(encoding='utf-8'))
        assert counts() == before


def test_gemini_http_contract_and_sanitized_failures(environment, monkeypatch):
    _, _, url = environment
    tutor = Tutor(Settings(database_url=url, ai_provider='gemini', gemini_api_key='test-key-not-a-real-secret', gemini_model='test-model'))
    original_client = httpx.Client
    requests = []
    def response(request):
        requests.append(request)
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"content":"1+1?","answer":"2","explanation":"덧셈"}'}]}}]})
    monkeypatch.setattr('backend.ai.httpx.Client', lambda **kwargs: original_client(transport=httpx.MockTransport(response),**kwargs))
    assert tutor.question('Python').answer == '2'
    request = requests[0]; body = json.loads(request.content)
    assert str(request.url).endswith('/models/test-model:generateContent')
    assert request.headers['x-goog-api-key'] == 'test-key-not-a-real-secret'
    assert body['contents'][0]['role'] == 'user'
    assert body['generationConfig']['responseMimeType'] == 'application/json'
    assert 'responseJsonSchema' in body['generationConfig']
    def quota(request): return httpx.Response(429,json={'error':{'message':'test-key-not-a-real-secret'}})
    monkeypatch.setattr('backend.ai.httpx.Client', lambda **kwargs: original_client(transport=httpx.MockTransport(quota),**kwargs))
    with pytest.raises(HTTPException) as error: tutor.chat('Python',[{'role':'user','content':'질문'}])
    assert error.value.status_code == 502 and 'test-key' not in str(error.value.detail)
