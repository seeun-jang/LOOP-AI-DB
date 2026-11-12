from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock
from time import monotonic
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from psycopg import Connection, IntegrityError, OperationalError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from .ai import Tutor
from .config import ROOT, Settings
from .models import (AnswerCreate, DeleteAccount, ExperimentCreate, Login, MessageCreate,
                     PasswordChange, ProfileUpdate, Register, SessionCreate, SessionUpdate)
from .security import DUMMY_HASH, password_version, passwords, token_for, verify_password


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    pool = ConnectionPool(settings.database_url, min_size=1, max_size=8, open=False,
                          kwargs={'row_factory': dict_row}, timeout=10)
    tutor = Tutor(settings)

    @asynccontextmanager
    async def lifespan(app):
        pool.open()
        pool.wait(timeout=20)
        try:
            with pool.connection() as conn:
                conn.execute('SELECT user_id FROM users LIMIT 1')
            yield
        finally:
            pool.close()

    app = FastAPI(title='LOOP AI 학습 관리 API', version='1.0.0', lifespan=lifespan,
                  description='8개 PostgreSQL 테이블 기반. 로그인 토큰은 Authorize에 입력하세요.')
    app.state.pool = pool
    app.state.tutor = tutor
    bearer = HTTPBearer(auto_error=False)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default includes rejected input; passwords must not be echoed.
        errors = [{'loc': list(error['loc']), 'msg': error['msg'], 'type': error['type']} for error in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': errors})

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(status_code=409, content={'detail': '중복되거나 참조할 수 없는 데이터입니다. 입력값을 확인하세요.'})

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeout)
    async def database_unavailable(request, exc):
        return JSONResponse(status_code=503, content={'detail': '데이터베이스 연결을 확인하고 다시 시도하세요.'})

    @app.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        # Swagger uses its own CDN assets; only that developer page needs these.
        if request.url.path in ('/docs', '/redoc'):
            del response.headers['Content-Security-Policy']
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def database():
        # Success commits, exceptions roll back every write made by the request.
        with pool.connection() as conn:
            yield conn

    DB = Annotated[Connection, Depends(database)]

    def current_user(db: DB, auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        unauthorized = HTTPException(401, '로그인이 필요하거나 만료되었습니다.', headers={'WWW-Authenticate': 'Bearer'})
        if not auth:
            raise unauthorized
        try:
            claims = jwt.decode(auth.credentials, settings.jwt_secret, algorithms=['HS256'],
                                issuer='loop-ai', audience='loop-ai-web', options={'require': ['exp', 'sub', 'iat', 'ver']})
        except jwt.InvalidTokenError:
            raise unauthorized from None
        user = db.execute('SELECT * FROM users WHERE user_id = %s', (claims['sub'],)).fetchone()
        if not user or claims['ver'] != password_version(user['password_hash']):
            raise unauthorized
        return user

    User = Annotated[dict, Depends(current_user)]
    Offset = Annotated[int, Query(ge=0)]
    Limit = Annotated[int, Query(ge=1, le=100)]

    # Small, single-process login/registration throttle; no external state/table.
    auth_calls = defaultdict(deque)
    throttle_lock = Lock()

    def throttle(request: Request):
        now = monotonic()
        with throttle_lock:
            for key in list(auth_calls):
                if not auth_calls[key] or auth_calls[key][-1] < now - 60:
                    del auth_calls[key]
            calls = auth_calls[request.client.host if request.client else 'local']
            while calls and calls[0] < now - 60:
                calls.popleft()
            if len(calls) >= 20:
                raise HTTPException(429, '로그인 시도가 많습니다. 1분 후 다시 시도하세요.', headers={'Retry-After': '60'})
            calls.append(now)

    def public(user):
        return {key: user[key] for key in ('user_id', 'name', 'email')}

    def owned_session(db, user, session_id, lock=False, active=False):
        row = db.execute('SELECT s.*, t.name AS topic_name FROM sessions s JOIN topics t USING(topic_id) '
                         'WHERE s.session_id=%s AND s.user_id=%s' + (' FOR UPDATE OF s' if lock else ''),
                         (session_id, user['user_id'])).fetchone()
        if not row:
            raise HTTPException(404, '학습 세션을 찾을 수 없습니다.')
        if active and row['status'] != 'in_progress':
            raise HTTPException(409, '학습상태를 진행중으로 바꾼 뒤 계속하세요.')
        return row

    def owned_question(db, user, question_id, active=False):
        question = db.execute('SELECT q.* FROM questions q JOIN sessions s USING(session_id) '
                              'WHERE q.question_id=%s AND s.user_id=%s', (question_id, user['user_id'])).fetchone()
        if not question:
            raise HTTPException(404, '문제를 찾을 수 없습니다.')
        owned_session(db, user, question['session_id'], lock=active, active=active)
        return question

    def owned_experiment(db, user, experiment_id):
        row = db.execute('SELECT * FROM prompt_experiments WHERE experiment_id=%s AND user_id=%s',
                         (experiment_id, user['user_id'])).fetchone()
        if not row:
            raise HTTPException(404, '실험을 찾을 수 없습니다.')
        return row

    @app.get('/api/health')
    def health(db: DB):
        db.execute('SELECT 1')
        return {'status': 'ok', 'database': 'postgresql', 'ai_provider': settings.ai_provider}

    @app.post('/api/auth/register', status_code=201, dependencies=[Depends(throttle)])
    def register(data: Register, db: DB):
        user = db.execute('INSERT INTO users(user_id,password_hash,name,email) VALUES (%s,%s,%s,%s) RETURNING *',
                          (data.user_id, passwords.hash(data.password), data.name, data.email)).fetchone()
        return {'access_token': token_for(user, settings), 'token_type': 'bearer', 'user': public(user)}

    @app.post('/api/auth/login', dependencies=[Depends(throttle)])
    def login(data: Login, db: DB):
        user = db.execute('SELECT * FROM users WHERE user_id=%s', (data.user_id,)).fetchone()
        valid = verify_password(data.password, user['password_hash'] if user else DUMMY_HASH)
        if not user or not valid:
            raise HTTPException(401, '아이디 또는 비밀번호를 확인하세요.')
        return {'access_token': token_for(user, settings), 'token_type': 'bearer', 'user': public(user)}

    @app.get('/api/users/me')
    def me(user: User):
        return public(user)

    @app.patch('/api/users/me')
    def update_me(data: ProfileUpdate, user: User, db: DB):
        return db.execute('UPDATE users SET name=%s,email=%s WHERE user_id=%s RETURNING user_id,name,email',
                          (data.name, data.email, user['user_id'])).fetchone()

    @app.put('/api/users/me/password')
    def change_password(data: PasswordChange, user: User, db: DB):
        if not verify_password(data.current_password, user['password_hash']):
            raise HTTPException(400, '현재 비밀번호를 확인하세요.')
        db.execute('UPDATE users SET password_hash=%s WHERE user_id=%s', (passwords.hash(data.new_password), user['user_id']))
        return {'detail': '비밀번호를 변경했습니다. 다시 로그인하세요.'}

    @app.delete('/api/users/me', status_code=204)
    def delete_me(data: DeleteAccount, user: User, db: DB):
        if not verify_password(data.password, user['password_hash']):
            raise HTTPException(400, '비밀번호를 확인하세요.')
        db.execute('DELETE FROM users WHERE user_id=%s', (user['user_id'],))

    @app.get('/api/topics')
    def topics(user: User, db: DB):
        return db.execute('SELECT * FROM topics ORDER BY topic_id').fetchall()

    @app.post('/api/sessions', status_code=201)
    def new_session(data: SessionCreate, user: User, db: DB):
        return db.execute('INSERT INTO sessions(user_id,topic_id,title) VALUES (%s,%s,%s) RETURNING *',
                          (user['user_id'], data.topic_id, data.title)).fetchone()

    @app.get('/api/sessions')
    def list_sessions(user: User, db: DB, offset: Offset = 0, limit: Limit = 100):
        return db.execute('SELECT s.*,t.name AS topic_name FROM sessions s JOIN topics t USING(topic_id) '
                          'WHERE user_id=%s ORDER BY started_at DESC,session_id DESC LIMIT %s OFFSET %s',
                          (user['user_id'], limit, offset)).fetchall()

    @app.get('/api/sessions/{session_id}')
    def get_session(session_id: int, user: User, db: DB):
        return owned_session(db, user, session_id)

    @app.patch('/api/sessions/{session_id}')
    def update_session(session_id: int, data: SessionUpdate, user: User, db: DB):
        owned_session(db, user, session_id, lock=True)
        return db.execute('UPDATE sessions SET title=%s,status=%s WHERE session_id=%s RETURNING *',
                          (data.title, data.status, session_id)).fetchone()

    @app.delete('/api/sessions/{session_id}', status_code=204)
    def delete_session(session_id: int, user: User, db: DB):
        owned_session(db, user, session_id, lock=True)
        db.execute('DELETE FROM sessions WHERE session_id=%s', (session_id,))

    @app.get('/api/sessions/{session_id}/messages')
    def messages(session_id: int, user: User, db: DB, offset: Offset = 0, limit: Limit = 100):
        owned_session(db, user, session_id)
        return db.execute('SELECT * FROM messages WHERE session_id=%s ORDER BY message_id LIMIT %s OFFSET %s',
                          (session_id, limit, offset)).fetchall()

    @app.post('/api/sessions/{session_id}/messages', status_code=201)
    def chat(session_id: int, data: MessageCreate, user: User, db: DB):
        session = owned_session(db, user, session_id, lock=True, active=True)
        # Bound the context sent to an external provider; original messages remain intact.
        history = db.execute('SELECT role,content FROM (SELECT message_id,role,content FROM messages '
                             'WHERE session_id=%s ORDER BY message_id DESC LIMIT 12) h ORDER BY message_id', (session_id,)).fetchall()
        response = tutor.chat(session['topic_name'], history + [{'role': 'user', 'content': data.content}])
        user_message = db.execute('INSERT INTO messages(session_id,role,content) VALUES (%s,%s,%s) RETURNING *',
                                  (session_id, 'user', data.content)).fetchone()
        assistant_message = db.execute('INSERT INTO messages(session_id,role,content) VALUES (%s,%s,%s) RETURNING *',
                                       (session_id, 'assistant', response)).fetchone()
        return {'user_message': user_message, 'assistant_message': assistant_message, 'ai_provider': settings.ai_provider}

    @app.post('/api/sessions/{session_id}/questions', status_code=201)
    def new_question(session_id: int, user: User, db: DB):
        session = owned_session(db, user, session_id, lock=True, active=True)
        question = tutor.question(session['topic_name'])
        return db.execute('INSERT INTO questions(session_id,content,answer,explanation) VALUES (%s,%s,%s,%s) '
                          'RETURNING question_id,session_id,content',
                          (session_id, question.content, question.answer, question.explanation)).fetchone()

    @app.get('/api/sessions/{session_id}/questions')
    def questions(session_id: int, user: User, db: DB, offset: Offset = 0, limit: Limit = 100):
        owned_session(db, user, session_id)
        return db.execute('SELECT question_id,session_id,content FROM questions WHERE session_id=%s '
                          'ORDER BY question_id LIMIT %s OFFSET %s', (session_id, limit, offset)).fetchall()

    @app.post('/api/questions/{question_id}/attempts', status_code=201)
    def submit_answer(question_id: int, data: AnswerCreate, user: User, db: DB):
        question = owned_question(db, user, question_id, active=True)
        result = tutor.grade(question, data.submitted_answer)
        attempt = db.execute('INSERT INTO attempts(question_id,submitted_answer,is_correct,ai_feedback) '
                             'VALUES (%s,%s,%s,%s) RETURNING *',
                             (question_id, data.submitted_answer, result.is_correct, result.feedback)).fetchone()
        return {**attempt, 'answer': question['answer'], 'explanation': question['explanation']}

    @app.get('/api/questions/{question_id}/attempts')
    def attempts(question_id: int, user: User, db: DB, offset: Offset = 0, limit: Limit = 100):
        owned_question(db, user, question_id)
        return db.execute('SELECT * FROM attempts WHERE question_id=%s ORDER BY attempt_id LIMIT %s OFFSET %s',
                          (question_id, limit, offset)).fetchall()

    @app.get('/api/stats')
    def stats(user: User, db: DB):
        # COUNT DISTINCT avoids multiplying session counts by messages/questions/attempts.
        return db.execute('''SELECT t.topic_id,t.name AS topic_name,
            COUNT(DISTINCT s.session_id)::int AS session_count,
            COUNT(a.attempt_id)::int AS attempt_count,
            COUNT(a.attempt_id) FILTER (WHERE a.is_correct IS TRUE)::int AS correct_count,
            COUNT(a.attempt_id) FILTER (WHERE a.is_correct IS NULL)::int AS pending_count,
            ROUND(100.0 * COUNT(a.attempt_id) FILTER (WHERE a.is_correct IS TRUE)
                  / NULLIF(COUNT(a.attempt_id),0),1) AS accuracy
            FROM topics t LEFT JOIN sessions s ON s.topic_id=t.topic_id AND s.user_id=%s
            LEFT JOIN questions q ON q.session_id=s.session_id
            LEFT JOIN attempts a ON a.question_id=q.question_id
            GROUP BY t.topic_id,t.name ORDER BY t.topic_id''', (user['user_id'],)).fetchall()

    @app.post('/api/experiments', status_code=201)
    def experiment(data: ExperimentCreate, user: User, db: DB):
        history = [{'role': 'user', 'content': data.question}]
        response_a = tutor.chat('전공 학습', history, data.prompt_a)
        response_b = tutor.chat('전공 학습', history, data.prompt_b)
        row = db.execute('INSERT INTO prompt_experiments(user_id,question) VALUES (%s,%s) RETURNING *',
                         (user['user_id'], data.question)).fetchone()
        results = []
        for variant, prompt, response in [('A', data.prompt_a, response_a), ('B', data.prompt_b, response_b)]:
            results.append(db.execute('INSERT INTO experiment_results(experiment_id,variant,prompt,response) '
                                      'VALUES (%s,%s,%s,%s) RETURNING *', (row['experiment_id'], variant, prompt, response)).fetchone())
        return {**row, 'results': results, 'ai_provider': settings.ai_provider}

    @app.get('/api/experiments')
    def experiments(user: User, db: DB, offset: Offset = 0, limit: Limit = 100):
        return db.execute('SELECT * FROM prompt_experiments WHERE user_id=%s ORDER BY experiment_id DESC LIMIT %s OFFSET %s',
                          (user['user_id'], limit, offset)).fetchall()

    @app.get('/api/experiments/{experiment_id}')
    def get_experiment(experiment_id: int, user: User, db: DB):
        row = owned_experiment(db, user, experiment_id)
        results = db.execute('SELECT * FROM experiment_results WHERE experiment_id=%s ORDER BY variant', (experiment_id,)).fetchall()
        return {**row, 'results': results}

    @app.delete('/api/experiments/{experiment_id}', status_code=204)
    def delete_experiment(experiment_id: int, user: User, db: DB):
        owned_experiment(db, user, experiment_id)
        db.execute('DELETE FROM prompt_experiments WHERE experiment_id=%s', (experiment_id,))

    app.mount('/', StaticFiles(directory=ROOT / 'frontend', html=True), name='frontend')
    return app


# Use: python -m uvicorn backend.main:create_app --factory
