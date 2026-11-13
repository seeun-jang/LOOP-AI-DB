'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const state = {token: sessionStorage.getItem('loop-token'), user: null, topics: [], sessions: [], session: null, register: false, epoch: 0};
const names = {learn: '전공 채팅', history: '학습 기록', experiments: '프롬프트 실험실', stats: '학습 통계', account: '내 계정'};
const statuses = {in_progress: '진행중', completed: '완료', stopped: '중단'};
let toastTimer;
function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
function notify(text, error = false) { const node = $('#toast'); node.textContent = text; node.className = error ? 'error-toast' : ''; node.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => node.hidden = true, error ? 7000 : 3500); }
function date(value) { return new Date(value).toLocaleString('ko-KR', {timeZone:'Asia/Seoul', month:'long', day:'numeric', hour:'2-digit', minute:'2-digit'}); }
function empty(text) { return el('div', 'empty', text); }
function data(form) { return Object.fromEntries(new FormData(form)); }
function saveToken(token) { state.token = token; token ? sessionStorage.setItem('loop-token', token) : sessionStorage.removeItem('loop-token'); }
function logout() {
  saveToken(null); state.user = null; state.session = null; state.sessions = []; state.topics = []; state.epoch++;
  ['#chat-messages','#question-list','#experiment-result','#experiment-list','#history-list','#recent-sessions','#stat-summary','#stats-body'].forEach(selector => $(selector).replaceChildren());
  $('#experiment-result').hidden = true; $('#experiment-result').removeAttribute('data-id');
  ['#auth-form','#message-form','#experiment-form','#profile-form','#password-form','#session-edit-form','#delete-account-form'].forEach(selector => $(selector).reset());
  $$('dialog').forEach(dialog => dialog.close()); $('#auth-screen').hidden = false; $('#app-screen').hidden = true; $('#auth-error').textContent = '';
}
async function api(path, options = {}) {
  const headers = {...(state.token ? {Authorization: `Bearer ${state.token}`} : {}), ...(options.body ? {'Content-Type': 'application/json'} : {})};
  let response;
  try { response = await fetch(`/api${path}`, {...options, headers, body: options.body ? JSON.stringify(options.body) : undefined}); }
  catch { throw new Error('서버에 연결할 수 없습니다. 실행 상태를 확인하세요.'); }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && state.token && !path.startsWith('/auth/')) logout();
    const detail = body.detail;
    throw new Error(Array.isArray(detail) ? detail.map(item => `${item.loc?.at(-1) || '입력값'}: ${item.msg}`).join(' / ') : detail || '요청을 처리하지 못했습니다. 다시 시도하세요.');
  }
  return body;
}
async function all(path) {
  const rows = [];
  for (let offset = 0;; offset += 100) { const page = await api(`${path}?offset=${offset}&limit=100`); rows.push(...page); if (page.length < 100) return rows; }
}
function action(button, task) {
  return async event => { event?.preventDefault(); if (button.disabled) return; button.disabled = true; const children = [...button.childNodes]; button.textContent = '처리 중…';
    try { await task(event); } catch (error) { notify(error.message, true); }
    finally { button.disabled = false; button.replaceChildren(...children); if (button.closest('#message-form') || button.id === 'generate-question') button.disabled = state.session?.status !== 'in_progress'; }
  };
}
function bindForm(id, task) { const form = $(id); form.addEventListener('submit', action($('button[type="submit"]', form), () => task(form))); }
function setAuthMode(register) {
  state.register = register; $('#register-fields').hidden = !register;
  $('#login-tab').classList.toggle('active', !register); $('#register-tab').classList.toggle('active', register);
  $('#auth-title').textContent = register ? '나만의 학습 루프 만들기' : '다시 만나 반가워요';
  $('#auth-description').textContent = register ? '작은 질문부터, 함께 성장을 시작해요.' : '로그인하고 나의 학습을 이어가세요.';
  $('#auth-submit').textContent = register ? '가입하고 시작하기 →' : '로그인 →';
  const password = $('#auth-form [name="password"]'); password.minLength = register ? 10 : 1; password.autocomplete = register ? 'new-password' : 'current-password';
  $$('#register-fields input').forEach(input => { input.disabled = !register; input.required = register; }); $('#auth-error').textContent = '';
}
$('#login-tab').onclick = () => setAuthMode(false); $('#register-tab').onclick = () => setAuthMode(true);
$('#demo-login').onclick = () => { setAuthMode(false); const form = $('#auth-form'); form.elements.user_id.value = 'demo_student'; form.elements.password.value = 'LoopDemo2026!'; form.requestSubmit(); };
$('#logout').onclick = logout;
bindForm('#auth-form', async form => {
  try { $('#auth-error').textContent = ''; const result = await api(state.register ? '/auth/register' : '/auth/login', {method:'POST', body: data(form)}); saveToken(result.access_token); state.user = result.user; await enterApp(); }
  catch (error) { $('#auth-error').textContent = error.message; }
});
function renderProfile() { $('#profile-name').textContent = state.user.name; $('#avatar').textContent = state.user.name.slice(0, 1); $('#account-id').value = state.user.user_id; $('#profile-form').elements.name.value = state.user.name; $('#profile-form').elements.email.value = state.user.email; }
async function enterApp() {
  const [topics, health] = await Promise.all([api('/topics'), api('/health')]); state.topics = topics;
  renderProfile(); $('#mode-badge').textContent = health.ai_provider === 'demo' ? '데모 모드 · 고정 학습 예시' : 'Gemini · AI 연결';
  $('#topic-select').replaceChildren(); $('#topic-cards').replaceChildren();
  const icons = ['▱', '⌘', '✧'];
  topics.forEach((topic, index) => {
    const option = el('option', '', topic.name); option.value = topic.topic_id; $('#topic-select').append(option);
    const card = el('button', 'topic-card'); card.type = 'button'; card.dataset.topic = topic.topic_id;
    card.append(el('span', 'topic-icon', icons[index % 3]), el('span', 'arrow', '↗'), el('h3', '', topic.name), el('p', '', topic.description || '새로운 주제를 학습해 보세요.'));
    card.onclick = () => { $('#topic-select').value = topic.topic_id; highlightTopic(); $('#session-form').elements.title.focus(); };
    $('#topic-cards').append(card);
  });
  const lab=el('button','topic-card');lab.type='button';lab.append(el('span','arrow','↗'),el('h3','','프롬프트 실험'),el('p','','같은 질문, 다른 지시. A/B 응답을 나란히 비교해 보세요.'));lab.onclick=()=>showPage('experiments').catch(error=>notify(error.message,true));$('#topic-cards').append(lab);
  $('#topic-select').value = state.topics.find(topic=>topic.name==='인공지능')?.topic_id || state.topics[0]?.topic_id;
  highlightTopic(); $('#auth-screen').hidden = true; $('#app-screen').hidden = false; resetLearning(); await showPage('learn');
}
function highlightTopic() { $$('.topic-card').forEach(card => card.classList.toggle('selected', card.dataset.topic === $('#topic-select').value)); window.LoopGuide.select($('#topic-select').value); }
$('#topic-select').onchange = highlightTopic;
async function showPage(page) {
  if (page !== 'learn') state.epoch++;
  $$('.page').forEach(section => section.hidden = section.id !== `page-${page}`);
  $$('.nav-item[data-page]').forEach(button => button.classList.toggle('active', button.dataset.page === page));
  $('#breadcrumb').textContent = `LOOP AI / ${names[page]}`;
  if (page === 'learn' && !state.session) await refreshSessions();
  if (page === 'history') await refreshSessions();
  if (page === 'experiments') await refreshExperiments();
  if (page === 'stats') await refreshStats();
  if (page === 'account') renderProfile();
}
$$('[data-page]').forEach(button => button.onclick = () => (button.dataset.page === 'learn' && state.session ? selectSession(state.session.session_id) : showPage(button.dataset.page)).catch(error => notify(error.message, true)));
function sessionRow(session, removable = false) {
  const row = el('div', 'session-row'); const button = el('button', 'session-open'); button.type = 'button';
  button.append(el('span', 'tag', session.topic_name), el('strong', '', session.title), el('small', '', `${date(session.started_at)} · 세션 #${session.session_id}`));
  button.onclick = () => selectSession(session.session_id).catch(error => notify(error.message, true));
  row.append(button, el('span', `status-label ${session.status}`, statuses[session.status]));
  if (removable) { const remove = el('button', 'icon-button', '삭제'); remove.type = 'button'; remove.setAttribute('aria-label', `${session.title} 삭제`); remove.onclick = action(remove, async () => {
    if (!confirm('이 세션의 대화·문제·풀이 기록을 모두 삭제할까요? 삭제 후 복구할 수 없습니다.')) return;
    await api(`/sessions/${session.session_id}`, {method:'DELETE'}); if (state.session?.session_id === session.session_id) resetLearning(); await refreshSessions(); notify('학습 기록을 삭제했습니다.');
  }); row.append(remove); }
  row.append(el('span', 'row-arrow', '↗')); return row;
}
async function refreshSessions() {
  state.sessions = await all('/sessions'); $('#recent-sessions').replaceChildren(...state.sessions.slice(0, 3).map(session => sessionRow(session)));
  $('#history-list').replaceChildren(...state.sessions.map(session => sessionRow(session, true))); $('#history-count').textContent = `전체 ${state.sessions.length}개의 학습 기록`;
  if (!state.sessions.length) { $('#recent-sessions').append(empty('아직 학습 기록이 없어요. 첫 번째 학습 루프를 시작해 보세요.')); $('#history-list').append(empty('학습을 시작하면 대화와 풀이 기록이 이곳에 차곡차곡 쌓입니다.')); }
}
function resetLearning() { state.session = null; state.epoch++; $('#learning-setup').hidden = false; $('#learning-active').hidden = true; window.LoopGuide.sync(false); }
$('#back-to-topics').onclick = () => { resetLearning(); refreshSessions().catch(error => notify(error.message, true)); };
bindForm('#session-form', async form => { const values = data(form); const session = await api('/sessions', {method:'POST', body:{...values, topic_id:Number(values.topic_id)}}); form.elements.title.value = ''; await selectSession(session.session_id); notify('새로운 학습을 시작했습니다.'); });
async function selectSession(id) {
  const epoch = ++state.epoch;
  const [session, messages, questions] = await Promise.all([api(`/sessions/${id}`), all(`/sessions/${id}/messages`), all(`/sessions/${id}/questions`)]);
  const attempts = await Promise.all(questions.map(question => all(`/questions/${question.question_id}/attempts`)));
  if (epoch !== state.epoch || !state.token) return;
  state.session = session; await showPage('learn'); $('#learning-setup').hidden = true; $('#learning-active').hidden = false;
  window.LoopGuide.select(session.topic_id); window.LoopGuide.sync(true, questions.length > 0);
  $('#session-topic').textContent = session.topic_name; $('#session-title').textContent = session.title; $('#session-date').textContent = `${date(session.started_at)} 시작 · ${statuses[session.status]} · 세션 #${session.session_id}`;
  $('#chat-messages').replaceChildren(...messages.map(renderMessage)); if (!messages.length) $('#chat-messages').append(el('div', 'chat-welcome', '안녕하세요, 나의 학습 튜터입니다.\n궁금한 개념을 질문하며 첫 대화를 시작해 보세요.'));
  $('#question-list').replaceChildren(...questions.map((question, i) => renderQuestion(question, attempts[i])));
  if (!questions.length) $('#question-list').append(el('div', 'chat-welcome', '아직 연습문제가 없어요.\n위 버튼으로 배운 내용을 확인해 보세요.'));
  const active = session.status === 'in_progress'; $$('#message-form textarea, #message-form button, #generate-question').forEach(control => control.disabled = !active);
  $('#chat-messages').scrollTop = $('#chat-messages').scrollHeight;
}
function renderMessage(message) { const node = el('article', `message ${message.role}`); node.append(el('span', 'message-name', message.role === 'user' ? '나' : '✧ LOOP AI'), el('div', 'message-content', message.content), el('span', 'message-time', date(message.created_at))); return node; }
bindForm('#message-form', async form => { const id = state.session.session_id; await api(`/sessions/${id}/messages`, {method:'POST', body:data(form)}); form.reset(); if (state.session?.session_id === id) await selectSession(id); });
$('#generate-question').onclick = action($('#generate-question'), async () => { const id = state.session.session_id; await api(`/sessions/${id}/questions`, {method:'POST'}); if (state.session?.session_id === id) await selectSession(id); notify('연습문제를 만들었습니다.'); });
function renderQuestion(question, attempts) {
  const node = el('article', 'question-card'); node.append(el('h3', '', `QUESTION ${question.question_id}`), el('p', 'question-text', question.content));
  const form = el('form', 'answer-form'); const label = el('label', 'sr-only', `문제 ${question.question_id} 답안`); const input = el('input'); input.name = 'submitted_answer'; input.required = true; input.maxLength = 8000; input.placeholder = '답안을 입력해 주세요'; input.id = `answer-${question.question_id}`; label.htmlFor = input.id;
  const button = el('button', 'primary', '답안 제출 →'); button.type = 'submit'; form.append(label, input, button); input.disabled = button.disabled = state.session.status !== 'in_progress';
  const id = state.session.session_id;
  form.onsubmit = action(button, async () => { const result = await api(`/questions/${question.question_id}/attempts`, {method:'POST', body:data(form)}); if (state.session?.session_id === id) await selectSession(id); notify(result.is_correct ? '정답입니다. 풀이와 피드백을 저장했어요.' : '풀이와 피드백을 저장했어요. 다시 도전해 보세요.'); }); node.append(form);
  attempts.forEach((attempt, index) => { const item = el('div', `attempt ${attempt.is_correct ? '' : 'wrong'}`); item.append(el('strong', '', `${attempt.is_correct === null ? '◷ 채점 대기' : attempt.is_correct ? '✓ 정답' : '↻ 다시 도전'} · ${index + 1}번째 제출`), el('p', '', `제출: ${attempt.submitted_answer}`), el('p', '', attempt.ai_feedback || '피드백을 기다리고 있어요.'), el('small', '', date(attempt.submitted_at))); node.append(item); }); return node;
}
$('#edit-session').onclick = () => { const form = $('#session-edit-form'); form.elements.title.value = state.session.title; form.elements.status.value = state.session.status; $('#session-dialog').showModal(); };
$('#cancel-edit').onclick = () => $('#session-dialog').close();
bindForm('#session-edit-form', async form => { const id = state.session.session_id; const updated = await api(`/sessions/${id}`, {method:'PATCH', body:data(form)}); if (state.session?.session_id === id) state.session = {...state.session, ...updated}; $('#session-dialog').close(); await selectSession(id); notify('제목과 학습상태를 저장했습니다.'); });
bindForm('#experiment-form', async form => { const result = await api('/experiments', {method:'POST', body:data(form)}); renderExperiment(result); await refreshExperiments(); notify('A/B 결과를 함께 저장했습니다.'); });
async function refreshExperiments() {
  const rows = await all('/experiments'); $('#experiment-list').replaceChildren(...rows.map(experiment => { const row = el('div', 'session-row'); const button = el('button', 'session-open'); button.type = 'button'; button.append(el('span', 'tag', 'A/B 비교'), el('strong', '', experiment.question), el('small', '', `${date(experiment.created_at)} · 실험 #${experiment.experiment_id}`)); button.onclick = action(button, async () => { renderExperiment(await api(`/experiments/${experiment.experiment_id}`)); });
    const remove = el('button', 'icon-button', '삭제'); remove.type = 'button'; remove.setAttribute('aria-label', `실험 ${experiment.experiment_id} 삭제`); remove.onclick = action(remove, async () => { if (!confirm('이 실험과 A/B 결과를 삭제할까요?')) return; await api(`/experiments/${experiment.experiment_id}`, {method:'DELETE'}); if ($('#experiment-result').dataset.id === String(experiment.experiment_id)) $('#experiment-result').hidden = true; await refreshExperiments(); notify('실험을 삭제했습니다.'); }); row.append(button, remove); return row; }));
  if (!rows.length) $('#experiment-list').append(empty('아직 실험이 없어요. 같은 질문에 서로 다른 지시를 적용해 보세요.'));
}
function renderExperiment(experiment) {
  const root = $('#experiment-result'); root.hidden = false; root.dataset.id = experiment.experiment_id;
  const heading = el('div', 'result-heading'); heading.append(el('h2', '', 'A/B 비교 결과'), el('span', 'tag pale', `저장 완료 · 실험 #${experiment.experiment_id}`));
  const grid = el('div', 'result-grid'); experiment.results.forEach(result => { const card = el('article', 'card result-card'); const title = el('h3'); title.append(el('span', `variant ${result.variant === 'B' ? 'green' : ''}`, result.variant), document.createTextNode(`설정 ${result.variant}`)); card.append(title, el('p', 'result-prompt', result.prompt), el('div', 'result-text', result.response)); grid.append(card); }); root.replaceChildren(heading, el('p', 'experiment-question', experiment.question), grid);
}
async function refreshStats() {
  const rows = await api('/stats'); const total = key => rows.reduce((sum, row) => sum + row[key], 0); const count = total('attempt_count');
  const cards = [['전체 학습', `${total('session_count')}회`, '지금까지 시작한 학습 세션'], ['문제 풀이', `${count}회`, '다시 도전한 제출까지 모두 기록'], ['나의 정답률', count ? `${(100 * total('correct_count') / count).toFixed(1)}%` : '—', '전체 제출을 기준으로 계산']];
  $('#stat-summary').replaceChildren(...cards.map(([label, value, footnote]) => { const card = el('div', 'card summary-card'); card.append(el('span', '', label), el('strong', 'summary-value', value), el('small', '', footnote)); return card; }));
  $('#stats-body').replaceChildren(...rows.map(row => { const tr = el('tr'); [row.topic_name, `${row.session_count}회`, `${row.attempt_count}회`, `${row.correct_count}개`].forEach(value => tr.append(el('td', '', value))); const cell = el('td'); const inner = el('div', 'accuracy-cell'); inner.append(el('span', '', row.accuracy === null ? '풀이 없음' : `${row.accuracy}%`)); const progress = el('progress'); progress.max = 100; progress.value = Number(row.accuracy || 0); progress.setAttribute('aria-label', `${row.topic_name} 정답률`); inner.append(progress); cell.append(inner); tr.append(cell); return tr; }));
}
bindForm('#profile-form', async form => { state.user = await api('/users/me', {method:'PATCH', body:data(form)}); renderProfile(); notify('회원 정보를 저장했습니다.'); });
bindForm('#password-form', async form => { await api('/users/me/password', {method:'PUT', body:data(form)}); form.reset(); logout(); notify('비밀번호를 변경했습니다. 다시 로그인하세요.'); });
$('#delete-account').onclick = () => $('#delete-account-dialog').showModal();
$('#cancel-delete-account').onclick = () => { $('#delete-account-dialog').close(); $('#delete-account-form').reset(); };
bindForm('#delete-account-form', async form => { await api('/users/me', {method:'DELETE', body:data(form)}); $('#delete-account-dialog').close(); form.reset(); logout(); notify('계정과 모든 학습 기록을 삭제했습니다.'); });
$('#practice-slot').append($('.practice-panel'));
window.LoopGuide.init();window.LoopGuide.sync(false);
document.addEventListener('loop-guide-topic',event=>{if(!state.session){$('#topic-select').value=event.detail.topicId;highlightTopic();}});
setAuthMode(false);
if (state.token) { api('/users/me').then(async user => { state.user = user; await enterApp(); }).catch(error => { logout(); notify(error.message, true); }); }
