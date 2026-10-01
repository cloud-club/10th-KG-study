const messages = document.querySelector('#messages');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#chat-input');
const sendButton = document.querySelector('#send-button');
const promptButtons = [...document.querySelectorAll('.suggestion')];

let busy = false;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function scrollToLatest() {
  messages.scrollTop = messages.scrollHeight;
}

function setBusy(value) {
  busy = value;
  input.disabled = value;
  sendButton.disabled = value;
  for (const button of promptButtons) button.disabled = value;
  sendButton.setAttribute('aria-label', value ? '응답 기다리는 중' : '질문 보내기');
}

function addMessage(role, text, extraClass = '') {
  const item = element('div', `message ${role}${extraClass ? ` ${extraClass}` : ''}`);
  if (role !== 'user') item.append(element('span', 'avatar', '✳'));
  const body = element('div', 'message-content');
  body.append(element('p', '', text));
  item.append(body);
  messages.append(item);
  scrollToLatest();
  return { item, body };
}

function appendQuote(box, quote) {
  const blockquote = element('blockquote', '', `“${quote}”`);
  box.append(blockquote);
}

function evidenceBox(label, quotes, reference = false) {
  const box = element('div', `evidence-box${reference ? ' reference' : ''}`);
  box.append(element('span', 'evidence-label', label));
  const values = Array.isArray(quotes) ? quotes.filter(value => typeof value === 'string' && value.trim()) : [];
  if (values.length) values.forEach(value => appendQuote(box, value));
  else box.append(element('blockquote', '', '근거 문구 없음'));
  return box;
}

function localDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Asia/Seoul' }).format(date);
}

function safeHttpUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' || url.protocol === 'http:') return url.href;
  } catch (_) { /* Invalid URLs stay as plain text. */ }
  return null;
}

function addCandidate(candidate, number) {
  const card = element('article', 'candidate-card');
  const topline = element('div', 'candidate-topline');
  topline.append(element('span', 'topic-tag', candidate.topic || '공통 주제'));
  topline.append(element('span', 'candidate-status', '그래프 연결 · 탐색 후보'));
  card.append(topline);
  card.append(element('h3', '', `참고 게시물 ${number}`));

  const evidence = element('div', 'evidence-grid');
  evidence.append(evidenceBox('내 게시물 근거', candidate.own_evidence));
  evidence.append(evidenceBox('참고 게시물 근거', candidate.reference_evidence, true));
  card.append(evidence);

  const meta = element('div', 'candidate-meta');
  const published = localDate(candidate.published_at);
  if (published) meta.append(element('span', '', `게시일 ${published}`));
  if (candidate.like_count !== null && candidate.like_count !== undefined) {
    const likes = Number(candidate.like_count);
    if (Number.isFinite(likes)) meta.append(element('span', '', `관찰 좋아요 ${new Intl.NumberFormat('ko-KR').format(likes)}개`));
  }
  const url = safeHttpUrl(candidate.reference_url);
  if (url) {
    const link = element('a', '', '원문 보기 ↗');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    meta.append(link);
  }
  card.append(meta);

  const actions = element('div', 'candidate-actions');
  const button = element('button', '', '이 후보로 대본 써줘 →');
  button.type = 'button';
  button.disabled = !candidate.candidate_id;
  button.addEventListener('click', () => {
    if (busy || !candidate.candidate_id) return;
    sendMessage('이걸로 대본 써줘', { action: 'script', candidate_id: candidate.candidate_id });
  });
  actions.append(button);
  actions.append(element('span', 'candidate-caveat', '주제 공유만 확인됨 · 최종 추천 아님'));
  card.append(actions);
  return card;
}

function addTopics(topics) {
  const list = element('div', 'topic-list');
  for (const item of topics) {
    if (!item || !item.topic) continue;
    const pill = element('span', 'topic-pill', item.topic);
    const count = Array.isArray(item.own_post_ids) ? item.own_post_ids.length : 0;
    if (count) pill.append(element('small', '', `내 글 ${count}건`));
    list.append(pill);
  }
  return list;
}

function addScript(script) {
  const card = element('article', 'script-card');
  card.append(element('h3', '', script.title || '대본 초안'));
  card.append(element('div', 'script-body', script.body || ''));
  const evidence = Array.isArray(script.evidence) ? script.evidence : [];
  if (evidence.length) {
    const area = element('div', 'script-evidence');
    area.append(element('strong', '', '참고한 원문'));
    for (const item of evidence) {
      if (item && item.quote) area.append(element('p', '', `“${item.quote}”`));
    }
    card.append(area);
  }
  return card;
}

function showResponse(data) {
  const item = element('div', `message assistant${data.intent === 'error' ? ' error' : ''}`);
  item.append(element('span', 'avatar', '✳'));
  const stack = element('div', 'response-stack');
  const reply = element('div', 'message-content');
  reply.append(element('p', '', data.reply || '응답을 받았습니다.'));
  stack.append(reply);

  if (Array.isArray(data.candidates) && data.candidates.length) {
    const list = element('div', 'candidate-list');
    data.candidates.forEach((candidate, index) => list.append(addCandidate(candidate, index + 1)));
    stack.append(list);
  }
  if (Array.isArray(data.topics) && data.topics.length) stack.append(addTopics(data.topics));
  if (data.script && typeof data.script === 'object') stack.append(addScript(data.script));

  item.append(stack);
  messages.append(item);
  scrollToLatest();
}

async function sendMessage(message, options = {}) {
  const trimmed = message.trim();
  if (!trimmed || busy) return;
  addMessage('user', trimmed);
  input.value = '';
  setBusy(true);
  const loading = addMessage('assistant', '그래프에서 근거를 찾는 중', 'loading');
  loading.body.querySelector('p').classList.add('loading-dots');

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: trimmed, ...options }),
      signal: controller.signal,
    });
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error('서버 응답을 읽을 수 없습니다.'); }
    if (!response.ok || data.intent === 'error') {
      throw new Error(data.reply || `요청에 실패했습니다. (${response.status})`);
    }
    loading.item.remove();
    showResponse(data);
  } catch (error) {
    loading.item.remove();
    const message = error.name === 'AbortError' ? '응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.' : error.message || '서버에 연결할 수 없습니다.';
    addMessage('assistant', message, 'error');
  } finally {
    clearTimeout(timeout);
    setBusy(false);
    input.focus();
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

for (const button of promptButtons) {
  button.addEventListener('click', () => sendMessage(button.dataset.prompt || ''));
}
