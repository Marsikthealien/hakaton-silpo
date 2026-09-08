/* Спільне для всіх сторінок: звернення до API, шапка, картка пака. */
const $ = s => document.querySelector(s);
const uah = n => (Math.round((n || 0) * 100) / 100).toLocaleString('uk-UA');
const TICKET = ['#F43F8E', '#3B82F6', '#F5A524', '#F97316', '#22C55E', '#8B5CF6'];
let PACK = null, ALLERGIES = [];

async function api(url, method = 'GET', body) {
  const r = await fetch(url, {
    method, headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return r.json();
}
function toast(text) {
  const el = $('#toast'); el.textContent = text; el.classList.add('on');
  setTimeout(() => el.classList.remove('on'), 2600);
}
function bad(data) { if (data && data.error) { toast(data.error); return true; } return false; }

/* ---------- шапка ---------- */

/* ===================== Іконки =====================
   Лінійний набір 24×24, один stroke, без емоджі: емоджі в кожній системі свої,
   а половина з них кольорові й ламають ритм інтерфейсу. */
const ICONS = {
  panel:    '<path d="M3 5h18v14H3z"/><path d="M9 5v14"/>',
  cart:     '<path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.4a2 2 0 0 0 2-1.6L20.5 8H6"/><circle cx="10" cy="20" r="1.4"/><circle cx="17.5" cy="20" r="1.4"/>',
  chat:     '<path d="M21 12a8 8 0 0 1-8 8H4l2-3a8 8 0 1 1 15-5z"/>',
  receipt:  '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
  user:     '<circle cx="12" cy="8" r="3.5"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
  gear:     '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v2.6M12 18.9v2.6M21.5 12h-2.6M5.1 12H2.5M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8M18.7 18.7l-1.8-1.8M7.1 7.1 5.3 5.3"/>',
  pulse:    '<path d="M3 12h4l2.5-7 4 14L16 12h5"/>',
  close:    '<path d="M6 6l12 12M18 6 6 18"/>',
  back:     '<path d="M15 5l-7 7 7 7"/>',
  right:    '<path d="M9 5l7 7-7 7"/>',
  refresh:  '<path d="M20 11a8 8 0 1 0-.7 4.3"/><path d="M20 5v6h-6"/>',
  ban:      '<circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/>',
  heart:    '<path d="M12 20s-7.5-4.7-7.5-9.4A4.1 4.1 0 0 1 12 8a4.1 4.1 0 0 1 7.5 2.6C19.5 15.3 12 20 12 20z"/>',
  family:   '<circle cx="8" cy="8" r="2.6"/><circle cx="16.5" cy="9.5" r="2"/><path d="M3 19a5 5 0 0 1 10 0M14 19a4 4 0 0 1 7 0"/>',
  pan:      '<path d="M3.5 10.5h11a3.5 3.5 0 0 1 0 7h-11a3.5 3.5 0 0 1 0-7z"/><path d="M18 14h3.5"/><path d="M6 7.5V5M10 7.5V5"/>',
  cycle:    '<path d="M4 11a8 8 0 0 1 13.7-5.6L20 8"/><path d="M20 4v4h-4"/><path d="M20 13a8 8 0 0 1-13.7 5.6L4 16"/><path d="M4 20v-4h4"/>',
  brain:    '<path d="M9.5 4.5A3 3 0 0 0 6 7.4 2.8 2.8 0 0 0 4.5 10a2.8 2.8 0 0 0 1 2.2A3 3 0 0 0 7 17a3 3 0 0 0 2.5 2.5z"/><path d="M14.5 4.5A3 3 0 0 1 18 7.4a2.8 2.8 0 0 1 1.5 2.6 2.8 2.8 0 0 1-1 2.2A3 3 0 0 1 17 17a3 3 0 0 1-2.5 2.5z"/><path d="M12 4.3v15.4"/>',
  plug:     '<path d="M8 3v6M16 3v6"/><path d="M5.5 9h13v2.5a6.5 6.5 0 0 1-13 0z"/><path d="M12 18v3"/>',
  scales:   '<path d="M12 4v16M7 20h10"/><path d="M4 9h16"/><path d="M4 9l-2 5a2.6 2.6 0 0 0 4 0z"/><path d="M20 9l2 5a2.6 2.6 0 0 1-4 0z"/>',
  trophy:   '<path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4.5a3 3 0 0 0 3 3M17 6h2.5a3 3 0 0 1-3 3"/><path d="M12 14v3M8.5 20h7l-.7-3h-5.6z"/>',
  mushroom: '<path d="M3.5 11a8.5 8.5 0 0 1 17 0c0 1.2-3.8 2-8.5 2s-8.5-.8-8.5-2z"/><path d="M9.5 13.2c0 3-.5 5-1 6.8h7c-.5-1.8-1-3.8-1-6.8"/>',
  compass:  '<circle cx="12" cy="12" r="8.5"/><path d="M15.5 8.5 13.6 13.6 8.5 15.5l1.9-5.1z"/>',
  gift:     '<path d="M3.5 11h17v9h-17z"/><path d="M2.5 7.5h19V11h-19z"/><path d="M12 7.5V20"/><path d="M12 7.5C10.5 4 6.5 4 7 6.4c.4 1.9 3.4 1.5 5 1.1zM12 7.5c1.5-3.5 5.5-3.5 5 -1.1-.4 1.9-3.4 1.5-5 1.1z"/>',
  map:      '<path d="M9 4 3 6.5v14L9 18l6 2.5 6-2.5v-14L15 6.5z"/><path d="M9 4v14M15 6.5v14"/>',
  flask:    '<path d="M10 3v6.5L4.8 18a2 2 0 0 0 1.7 3h11a2 2 0 0 0 1.7-3L14 9.5V3"/><path d="M8.5 3h7M8 14h8"/>',
  spark:    '<path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z"/><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
  wallet:   '<path d="M3.5 7.5h17v12h-17z"/><path d="M3.5 7.5 15 4v3.5"/><circle cx="16.5" cy="13.5" r="1.3"/>',
  moon:     '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
  sun:      '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M21.5 12h-2M4.5 12h-2M18.4 5.6l-1.4 1.4M7 17l-1.4 1.4M18.4 18.4 17 17M7 7 5.6 5.6"/>',
  leaf:     '<path d="M4 20c0-9 6-15 16-15 0 10-6 15-16 15z"/><path d="M4 20c3-6 7-9 11-10.5"/>',
  ticket:   '<path d="M3.5 8.5a2 2 0 0 0 0 7v3h17v-3a2 2 0 0 1 0-7v-3h-17z"/><path d="M9.5 6v12"/>',
  tag:      '<path d="M11 3.5H20v9l-8.5 8.5-9-9z"/><circle cx="16.2" cy="7.8" r="1.4"/>',
  calendar: '<path d="M3.5 5.5h17v15h-17z"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  swipe:    '<path d="M9 11V5.5a1.7 1.7 0 0 1 3.4 0V12"/><path d="M12.4 11.2a1.6 1.6 0 0 1 3.2 0v1"/><path d="M15.6 12a1.6 1.6 0 0 1 3.2 0v3.5a5.5 5.5 0 0 1-5.5 5.5h-1a4.5 4.5 0 0 1-3.6-1.8L5 15.5a1.7 1.7 0 0 1 2.6-2.1L9 15"/>',
  sprout:   '<path d="M12 21v-8"/><path d="M12 13C12 8 8.5 5.5 4.5 5.5 4.5 10 8 13 12 13z"/><path d="M12 13c0-3.5 2.6-6 6-6 0 3.5-2.6 6-6 6z"/>',
  fridge:   '<path d="M5.5 3h13v18h-13z"/><path d="M5.5 10h13M8.5 6.5v2M8.5 13v2.5"/>',
  heartbeat:'<path d="M3.5 12h4L9 9l2.5 6L14 11l1.5 1h5"/>',
  sound:    '<path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4z"/><path d="M15.5 9a4 4 0 0 1 0 6"/><path d="M18 6.5a7.5 7.5 0 0 1 0 11"/>',
  mute:     '<path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4z"/><path d="M16 10l4 4M20 10l-4 4"/>',
  flower:   '<circle cx="12" cy="12" r="2.4"/><path d="M12 3.5a3 3 0 0 1 0 6 3 3 0 0 1 0-6zM12 14.5a3 3 0 0 1 0 6 3 3 0 0 1 0-6zM20.5 12a3 3 0 0 1-6 0 3 3 0 0 1 6 0zM9.5 12a3 3 0 0 1-6 0 3 3 0 0 1 6 0z"/>',
};

/* size — у пікселях; клас лишається для кольору через currentColor */
function icon(name, size = 20, cls = '') {
  return `<svg class="ic ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
    stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}

function mountTop(current) {
  // У хедері лише те, що потрібно ГОСТЮ: назва, перемикач вигляду й вихід на
  // головну. Навігація між екранами живе всередині застосунку, як у «Сільпо».
  const home = current === 'home';
  document.body.insertAdjacentHTML('afterbegin', `
    <div class="top"><div class="in">
      <a class="brand" href="/">
        <span class="dot"></span>
        <span><b>${home ? '' : '← '}Хакатон «Сільпо»</b>
          <span>${{home:'асистент', profile:'профіль', game:'грибниця',
                   road:'шлях', tech:'під капотом'}[current] || ''}</span></span></a>
      <div class="viewswitch" title="Як показувати клієнтську частину">
        <button onclick="setView('desktop')" aria-pressed="true">Десктоп</button>
        <button onclick="setView('mobile')" aria-pressed="false">Мобільний</button>
      </div>
      <div class="topact">
        <button class="iconbtn sm" id="statebtn" onclick="showState()"
          title="Стан підключення">${icon('pulse', 18)}</button>
        <a class="iconbtn sm" href="/tech" title="Під капотом">${icon('gear', 18)}</a>
      </div>
    </div></div>`);
  document.body.insertAdjacentHTML('beforeend',
    '<div class="toast" id="toast"></div>' +
    '<dialog class="sheet" id="sheet"><div id="sheet-body"></div></dialog>' +
    '<div class="scrim" id="scrim" onclick="closePanels()"></div>');
  setView(localStorage.getItem('view') || 'desktop', true);
}

/* ---------- нижня навігація застосунку ----------
   Одна на всі екрани: із профілю й грибниці теж має бути видно, де ти. */
function appNav(current) {
  const tabs = [
    ['chat', 'Чат', 'chat', "location.href='/'"],
    ['cart', 'Кошик', 'cart', "location.href='/'"],
    ['profile', 'Профіль', 'user', "location.href='/profile'"],
  ];
  return `<nav class="appnav">${tabs.map(([id, label, ic, act]) =>
    `<button aria-selected="${id === current}" onclick="${act}">
      <span class="em">${icon(ic, 21)}</span>${label}</button>`).join('')}</nav>`;
}

/* ===================== Озвучення відповідей =====================
   Через `speechSynthesis` браузера: нуль залежностей, нуль трафіку й жодного
   аудіо на сервері. Для демо це важливо — асистент, який ГОВОРИТЬ, одразу
   читається як асистент, а не як форма з кнопками.

   Голоси браузер віддає асинхронно, тому чекаємо `voiceschanged`; якщо
   українського голосу в системі немає, кажемо про це прямо, а не мовчимо. */
let TTS = false, TTS_VOICE = null, TTS_REMOTE = false, TTS_AUDIO = null;

function ttsVoices() {
  return new Promise(resolve => {
    const got = speechSynthesis.getVoices();
    if (got.length) return resolve(got);
    speechSynthesis.addEventListener('voiceschanged',
      () => resolve(speechSynthesis.getVoices()), { once: true });
    setTimeout(() => resolve(speechSynthesis.getVoices()), 1200);
  });
}

async function ttsInit() {
  // Два шляхи. Respeecher (українська модель ua-rt) дає справжній український
  // голос і вміє наголоси; браузерний синтез безкоштовний, але бере системний
  // голос, а українського в системі часто просто немає. Тому Respeecher —
  // основний, браузер — запасний, і перемикання відбувається саме.
  const v = await api('/api/voice');
  TTS_REMOTE = !!(v && v.has_key);
  if ('speechSynthesis' in window) {
    const voices = await ttsVoices();
    TTS_VOICE = voices.find(x => x.lang === 'uk-UA')
      || voices.find(x => (x.lang || '').startsWith('uk')) || null;
  }
  try { TTS = localStorage.getItem('tts') === '1'; } catch (e) {}
  syncTtsBtn();
  return TTS_REMOTE || TTS_VOICE;
}

function ttsSource() {
  return TTS_REMOTE ? 'Respeecher, українська модель'
    : TTS_VOICE ? `браузер · ${TTS_VOICE.name}`
    : 'браузер · українського голосу в системі немає';
}

function syncTtsBtn() {
  const btn = document.querySelector('#btn-tts');
  if (!btn) return;
  btn.setAttribute('aria-pressed', String(TTS));
  btn.innerHTML = icon(TTS ? 'sound' : 'mute', 18);
  btn.title = TTS ? `Озвучення: ${ttsSource()}` : 'Озвучувати відповіді';
}

async function toggleTts() {
  if (!('speechSynthesis' in window))
    return toast('Браузер не вміє синтез мовлення');
  TTS = !TTS;
  try { localStorage.setItem('tts', TTS ? '1' : '0'); } catch (e) {}
  if (!TTS) speechSynthesis.cancel();
  syncTtsBtn();
  if (!TTS) { if (TTS_AUDIO) TTS_AUDIO.pause(); return toast('Озвучення вимкнено'); }
  if (!TTS_REMOTE && !TTS_VOICE) await ttsInit();
  toast('Озвучую: ' + ttsSource());
  speak('Готовий. Питайте.');
}

/* Текст для вимови ≠ текст для екрана: стрілки, крапки-роздільники й «₴»
   вголос звучать як сміття. */
function ttsText(raw) {
  return String(raw || '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/₴/g, ' гривень')
    .replace(/→|·|↑|↗/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 400);
}

function ttsStop() {
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  if (TTS_AUDIO) { TTS_AUDIO.pause(); TTS_AUDIO = null; }
}

function speakLocal(text) {
  if (!('speechSynthesis' in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'uk-UA';
  if (TTS_VOICE) u.voice = TTS_VOICE;
  u.rate = 1.05;
  speechSynthesis.speak(u);
}

async function speak(raw) {
  if (!TTS) return;
  const text = ttsText(raw);
  if (!text) return;
  ttsStop();                     // нова відповідь перебиває попередню
  if (!TTS_REMOTE) return speakLocal(text);
  try {
    // Сирий текст, не почищений: підготовку до вимови робить бекенд —
    // там і числа словами, і наголоси, які вміє лише українська модель.
    const r = await fetch('/api/tts', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text: raw }),
    });
    if (!r.ok) throw new Error('tts ' + r.status);
    const url = URL.createObjectURL(await r.blob());
    TTS_AUDIO = new Audio(url);
    TTS_AUDIO.onended = () => URL.revokeObjectURL(url);
    await TTS_AUDIO.play();
  } catch (e) {
    // Ключ протух, ліміт, мережа — демо не має замовкати через це.
    TTS_REMOTE = false;
    syncTtsBtn();
    speakLocal(text);
  }
}

/* ---------- модалка зі стеком ----------
   Модалка може відкрити модалку (сімʼя → учасник). Стек дає кнопку «назад»,
   інакше гість вилітає на сторінку й губить контекст. */
let SHEETS = [];
function sheet(title, sub, html, opts = {}) {
  if (!opts._back) SHEETS.push({ title, sub, html });
  const back = SHEETS.length > 1;
  document.querySelector('#sheet-body').innerHTML = `
    <div class="shead">
      ${back ? `<button class="iconbtn sm plain" onclick="sheetBack()"
        title="Назад">${icon('back', 18)}</button>` : ''}
      <div class="t" style="flex:1;min-width:0">
        <h2>${title}</h2>${sub ? `<div class="soft">${sub}</div>` : ''}</div>
      <button class="iconbtn sm plain" onclick="closeSheet()"
        title="Закрити">${icon('close', 18)}</button></div>
    <div class="sbody">${html}</div>`;
  const dlg = document.querySelector('#sheet');
  if (!dlg.open) dlg.showModal();
}
function sheetBack() {
  SHEETS.pop();
  const prev = SHEETS[SHEETS.length - 1];
  if (!prev) return closeSheet();
  sheet(prev.title, prev.sub, prev.html, { _back: true });
}
function closeSheet() {
  SHEETS = [];
  document.querySelector('#sheet')?.close();
}
/* Перемалювати верхню модалку — коли її вміст змінився (напр. після збереження) */
function sheetReplace(title, sub, html) {
  SHEETS.pop();
  sheet(title, sub, html);
}

/* ---------- бічні панелі ---------- */
function togglePanel(side) {
  const shell = document.querySelector('#shell');
  if (!shell) return;
  const on = !shell.classList.contains(side);
  shell.classList.remove('l', 'r');
  shell.classList.toggle(side, on);
  syncPanels();
}
function closePanels() {
  document.querySelector('#shell')?.classList.remove('l', 'r');
  syncPanels();
}
function syncPanels() {
  const shell = document.querySelector('#shell');
  if (!shell) return;
  const open = shell.classList.contains('l') || shell.classList.contains('r');
  const overlay = window.matchMedia('(max-width:900px)').matches ||
    document.body.classList.contains('mobile');
  document.querySelector('#scrim')?.classList.toggle('on', open && overlay);
  document.querySelector('#btn-left')?.setAttribute('aria-pressed', shell.classList.contains('l'));
  document.querySelector('#btn-right')?.setAttribute('aria-pressed', shell.classList.contains('r'));
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePanels(); });

async function showState() {
  const s = await api('/api/status');
  sheet('Стан підключення', 'Технічні лічильники — щоб не займали хедер', `
    <div class="grid2">
      <div class="kpi"><b>${s.mcp_tools}</b><span>MCP-tools доступно агенту</span></div>
      <div class="kpi"><b>${s.silpo_calls}</b><span>викликів «Сільпо» за сеанс</span></div>
      <div class="kpi ${s.model_available ? 'good' : ''}"><b>${s.model_available ? 'онлайн' : 'офлайн'}</b>
        <span>${s.model || 'модель'}</span></div>
      <div class="kpi"><b>${(s.servers || []).length}</b><span>MCP-серверів: ${(s.servers||[]).join(', ')}</span></div>
    </div>
    <p class="soft" style="margin:12px 0 0">${s.model_available
      ? 'Вільний текст обробляє локальна модель.'
      : 'Модель офлайн — намір розбирається за ключовими словами. Сценарії працюють однаково.'}</p>
    <a class="go ghost" href="/tech" style="margin-top:12px;display:inline-block;
      text-decoration:none">Відкрити «Під капотом» →</a>`);
}

/* Мобільний вигляд — той самий застосунок у рамці телефона.
   «Під капотом» у ньому не показуємо: це екран для команди, не для гостя. */
function setView(mode, silent) {
  // Кошик один: і на десктопі, і на мобільному він усередині застосунку.
  // Різниця лише в тому, що на десктопі його можна тримати в правій панелі.
  document.body.classList.toggle('mobile', mode === 'mobile');
  document.querySelectorAll('.viewswitch button').forEach((b, i) =>
    b.setAttribute('aria-pressed', (i === 0) === (mode !== 'mobile')));
  try { localStorage.setItem('view', mode); } catch (e) {}
  syncPanels();
  if (mode === 'mobile' && location.pathname === '/tech' && !silent) location.href = '/';
}
async function loadStatus() {
  // Стан лишається доступним, але в хедері від нього — лише крапка.
  // Числа відкриваються в модалці: на демо вони не мають конкурувати з фічами.
  const s = await api('/api/status');
  const btn = $('#statebtn');
  if (btn) {
    btn.title = `MCP-tools ${s.mcp_tools} · викликів «Сільпо» ${s.silpo_calls}` +
      ` · модель ${s.model_available ? s.model : 'офлайн'}`;
  }
  return s;
}

/* ---------- профіль ---------- */
async function loadAllergies() {
  const d = await api('/api/profile');
  const p = d.profile || {};
  ALLERGIES = [...(p.allergies || []), ...(p.dislikes || [])];
  return p;
}

/* ---------- картка пака ---------- */
/* Пак живе в СТРІЧЦІ ЧАТУ, а не в окремій вкладці: інакше кожен новий набір
   стирав розмову, і не було видно, що з чого вийшло. Тому renderPack повертає
   розмітку, а куди її покласти — вирішує сторінка. */
function packHtml(p) {
  PACK = p;
  const src = { receipt: 'відтворено з чека', habits: 'зі звичок', silpo_set: 'із набору «Сільпо»',
                agent: 'зібрано агентом' }[p.source] || p.source;
  return `
    <div class="head"><div class="t">
      <h2>${p.name}</h2>
      <div class="soft">${src} · ${p.item_count} позицій${
        p.receipt ? ` · в оригіналі ${uah(p.receipt.paid_uah)} ₴` : ''}${
        p.people ? ` · на ${p.people} осіб` : ''}${
        p.novelty && p.novelty !== 'any' ? ` · ${p.novelty === 'new' ? 'щось нове' : 'щось знайоме'}` : ''}</div></div>
      <button class="go ghost" onclick="optimize()">Знижки</button>
      <button class="go" onclick="toCart()">У кошик «Сільпо»</button></div>
    ${p.recipe ? `<div class="recipe"><b>${p.recipe.title}</b>
      <ol>${p.recipe.steps.map(s => `<li>${s}</li>`).join('')}</ol></div>` : ''}
    ${(p.items || []).map(i => `
      <div class="prod">
        <img src="${i.image || ''}" alt="" loading="lazy">
        <div class="body">
          <div class="line"><span class="nm">${i.name}</span>
            <span class="pr">${i.old_price ? `<span class="old">${uah(i.old_price)}</span>` : ''}${uah(i.price)} ₴</span></div>
          ${i.scaled ? `<div class="why">${i.scaled}</div>`
            : (i.qty !== 1 ? `<div class="why">× ${i.qty}</div>` : '')}
          ${i.because ? `<div class="why because">${i.because}</div>` : ''}
          ${i.novelty_relaxed ? `<div class="why">знайомого в бюджеті не було — взяв незнайоме</div>` : ''}
          ${i.swapped_from ? `<div class="why swap">замість «${i.swapped_from}» — не було в магазині</div>` : ''}
          ${i.note ? `<div class="why">${i.note}</div>` : ''}
          <span style="display:flex;gap:12px;flex-wrap:wrap">
            <button class="link" onclick="showProduct('${i.slug}','${(i.name||'').replace(/'/g,'')}')">Відомості</button>
            <button class="link" onclick="pick('${i.product_id}')">Обрати інший →</button>
          </span>
        </div></div>`).join('')}
    <div class="total"><span>Разом</span><span>${uah(p.total_uah)} ₴</span></div>
    ${p.saved_uah > 0 ? `<div class="saved">знижка ${uah(p.saved_uah)} ₴</div>` : ''}
    ${(p.blocked_for_everyone || []).length ? `<div class="soft" style="margin-top:8px">
      Виключено для всієї родини: <b>${p.blocked_for_everyone.join(', ')}</b> —
      алергія будь-кого блокує товар для всього кошика.</div>` : ''}
    ${(p.skipped || []).length ? `<div class="soft" style="margin-top:8px">Не додав:
      ${p.skipped.map(s => `${s.query} — ${s.reason}`).join(' · ')}</div>` : ''}
    ${p.why ? `<div class="soft" style="margin-top:8px">${p.why}</div>` : ''}
    <div id="offers"></div>`;
}

/* Пак у стрічку чату. Попередній пак згортаємо до рядка — історія лишається
   читаною, а на екрані завжди один розгорнутий набір. */
function renderPack(p) {
  if (!p || p.error) return;
  const log = $('#log');
  if (log) {
    log.querySelectorAll('.packmsg').forEach(el => {
      const name = el.dataset.name || 'Пак';
      const sum = el.dataset.total || '';
      el.outerHTML = `<div class="msg sys">↑ ${name}${sum ? ' · ' + sum + ' ₴' : ''}
        — замінено новим набором</div>`;
    });
    log.insertAdjacentHTML('beforeend',
      `<div class="packmsg" data-name="${p.name}" data-total="${uah(p.total_uah)}">
         ${packHtml(p)}<div class="alerts" id="alerts"></div></div>`);
    log.scrollTop = log.scrollHeight;
    // `const` на верхньому рівні скрипта не стає властивістю window, тому
    // перевіряємо typeof, а не window.QUICKS_PACK.
    const quicks = $('#quicks');
    if (quicks && typeof QUICKS_PACK !== 'undefined')
      quicks.innerHTML = QUICKS_PACK.map(q =>
        `<button onclick="quick('${q}')">${q}</button>`).join('');
  } else {
    const box = $('#pack');
    if (box) box.innerHTML = packHtml(p);
  }
  screenAllergens(); payment();
}

async function openPack(id) { renderPack(await api('/api/pack?pack_id=' + id)); }

/* ---------- заміна позиції ---------- */
async function pick(id) {
  const d = await api('/api/pack/alternatives', 'POST',
    { pack_id: PACK.id, product_id: id, limit: 6 });
  if (bad(d)) return;
  $('#picker-body').innerHTML = `
    <div class="head"><div class="t">
      <h2 style="margin:0 0 2px">Замість «${d.current.name}»</h2>
      <div class="soft">зараз ${uah(d.current.price_uah)} ₴ · нічого не змінюється, поки не обереш</div></div>
      <button class="go ghost" onclick="picker.close()">Закрити</button></div>
    ${d.options.length ? `<div class="opts">${d.options.map(o => `
      <button class="opt" onclick="swapTo('${id}','${o.product_id}')">
        <img src="${o.image || ''}" alt="" loading="lazy">
        <span style="flex:1;min-width:0">
          <span class="nm" style="display:block;font-size:13px;font-weight:600">${o.name}</span>
          <span class="soft">${o.unit || ''}${o.old_price_uah ? ` · було ${uah(o.old_price_uah)} ₴` : ''}</span></span>
        <span class="d"><span class="pr" style="display:block;font-weight:800">${uah(o.price_uah)} ₴</span>
          <span class="${o.delta_uah < 0 ? 'down' : 'up'}">${o.delta_uah > 0 ? '+' : ''}${uah(o.delta_uah)} ₴</span></span>
      </button>`).join('')}</div>` : `<p class="muted">${d.note}</p>`}`;
  picker.showModal();
}
async function swapTo(oldId, newId) {
  picker.close(); toast('Міняю…');
  const r = await api('/api/pack/swap_to', 'POST',
    { pack_id: PACK.id, product_id: oldId, new_product_id: newId });
  if (bad(r)) return;
  toast(`${r.swapped.to} · ${r.swapped.delta_uah > 0 ? '+' : ''}${uah(r.swapped.delta_uah)} ₴`);
  openPack(PACK.id);
}

/* ---------- алергени, Дольки, знижки, кошик ---------- */
async function screenAllergens() {
  // Блок алергенів належить конкретному паку, тож і живе в його картці —
  // а не смугою на всю сторінку понад застосунком.
  const box = $('#alerts'); if (!box) return;
  if (!ALLERGIES.length || !PACK) { box.innerHTML = ''; return; }
  const s = await api('/api/pack/screen', 'POST', { pack_id: PACK.id, avoid: ALLERGIES });
  box.innerHTML = (s.flagged || []).length ? `
    <div class="warn"><b>Обережно: ${s.flagged.length} позиц. під твоїм обмеженням</b>
      ${s.flagged.map(f => `<div style="font-size:13px;margin-top:6px">${f.name}
        <span class="soft">— збіг «${f.matched}»</span>
        <button class="link" onclick="pick('${f.product_id}')">замінити</button></div>`).join('')}
      <div class="soft" style="margin-top:8px">Перевірка за назвою: складу MCP «Сільпо» не віддає.</div>
    </div>` : '';
}
async function payment() {
  const box = $('#payment'); if (!box || !PACK) return;
  const p = await api('/api/payment', 'POST', { pack_total_uah: PACK.total_uah });
  if (!p.hint) { box.innerHTML = ''; return; }
  const pct = Math.min(100, Math.round(p.hint.have_uah / p.hint.min_uah * 100));
  box.innerHTML = `
    <section class="card"><h3>Оплата Дольками</h3>
      <p class="muted" style="margin:0">Чек ділиться на 3 платежі без комісії — від ${uah(p.hint.min_uah)} ₴.</p>
      <div class="bar"><i style="width:${pct}%"></i></div>
      <div style="display:flex;justify-content:space-between;font-size:13px">
        <span>${uah(p.hint.have_uah)} ₴</span><b>бракує ${uah(p.hint.missing_uah)} ₴</b></div>
      <button class="link" onclick="topUp()">Добрати зі звичного →</button></section>`;
}
async function topUp() {
  toast('Добираю зі звичного…');
  const p = await api('/api/pack/reorder', 'POST', {});
  if (!bad(p)) renderPack(p);
}
function ticket(p, i) {
  const hits = (p.applies_to || []).map(h => h.name || h).join(', ');
  return `<div class="ticket">
    <div class="val" style="background:${TICKET[i % TICKET.length]}">${
      (p.reward || '').replace(/[^0-9]/g, '') || '%'}</div>
    <div class="txt">${p.text}<small>${hits || p.reward || ''}</small></div>
    <div class="end">+</div></div>`;
}
async function optimize() {
  const o = await api('/api/pack/optimize', 'POST', { pack_id: PACK.id });
  if (bad(o)) return;
  const multi = (o.multibuy || []).map(m =>
    `<div class="note" style="margin:7px 0"><b>−${uah(m.saving_uah)} ₴</b> ${m.name}<br>
      <span class="soft">${m.text} · доплата ${uah(m.extra_cost_uah)} ₴</span></div>`).join('');
  $('#offers').innerHTML = `
    <h3>Знижки саме на цей пак</h3>${multi}
    ${(o.coupons || []).map((c, i) => ticket({ reward: c.reward, text: c.text }, i + 3)).join('')}
    <p class="soft" style="margin:10px 0 7px">Активувати в застосунку:
      ${o.activate_promos.length} із ${o.promo_limit.total} (ліміт ${o.promo_limit.maxSelect})</p>
    ${(o.activate_promos || []).map((p, i) => ticket(p, i)).join('')}`;
  toast('Порахував знижки');
}
async function toCart() {
  toast('Кладу в кошик…');
  const r = await api('/api/pack/to_cart', 'POST', { pack_id: PACK.id });
  if (bad(r)) return;
  const issues = [...(r.not_added || []).map(n => `${n} — не потрапив`),
    ...(r.warnings || []).map(w => w.message === 'product.offer.stock.max'
      ? 'товар щойно закінчився — «Сільпо» зменшила кількість' : w.message)];
  $('#offers').insertAdjacentHTML('afterbegin', `
    <div class="note" style="margin-top:12px">
      <b>У кошику ${r.in_cart} із ${r.requested} позицій на ${uah(r.total_uah)} ₴</b><br>
      <span class="soft">знижка ${uah(r.discount_uah)} ₴ · оформлення підтверджуєш ти</span><br>
      <a href="${r.checkout_url}" target="_blank" rel="noopener">Відкрити кошик «Сільпо» →</a>
      ${issues.length ? `<div style="color:var(--red);font-size:12.5px;margin-top:6px">
        ${issues.map(t => '· ' + t).join('<br>')}</div>` : ''}</div>`);
  toast('Покладено в справжній кошик');
  suggestAlso();
}

/* Перед оформленням — «що беруть із цим». Ненавʼязливо, але завжди. */
async function suggestAlso() {
  const first = (PACK.items || [])[0];
  if (!first) return;
  const r = await api('/api/also_bought?product_name=' + encodeURIComponent(first.name));
  if (!r.also_bought?.length) return;
  $('#offers').insertAdjacentHTML('beforeend', `
    <h3>З цим зазвичай беруть</h3>
    <div class="chips">${r.also_bought.map(a =>
      `<button class="fbtn" onclick="addByName('${a.name.replace(/'/g,'')}')">${a.name}
        <span class="soft">×${a.times}</span></button>`).join('')}</div>
    <p class="soft">Порахувано з ${r.receipts_with_it} твоїх чеків · <code>silpo_also_bought</code> ⁺</p>`);
}
async function addByName(name) {
  toast('Шукаю…');
  const p = await api('/api/pack/build', 'POST', { name: PACK.name, items: [name] });
  if (bad(p)) return;
  toast('Додано окремим паком — обʼєднай або поклади в кошик');
  renderPack(p);
}

/* ===================== сценарії =====================
   Кожен сценарій оголошує очікуваний ланцюг tools — гість бачить його ДО запуску,
   а під час виконання виклики підсвічуються в тому порядку, в якому справді пішли. */
/* Назви, фрази й ланцюги tools живуть на бекенді (silpo_agent_mcp/flows.py) —
   одне джерело для карток, «Під капотом» і документації. Тут лишається тільки
   те, чого бекенд знати не має: який маршрут смикнути й що спитати в гостя. */
const HANDLERS = {
  repeat:   { path: '/api/pack/from_receipt', body: { index: 0 } },
  reorder:  { path: '/api/pack/reorder', body: {} },
  pantry:   { path: '/api/pantry/missing', method: 'GET' },
  wellbeing:{ path: '/api/wellbeing', wellbeing: true },
  weekly:   { path: '/api/pack/weekly', ask: 'weekly', novelty: true },
  budget:   { path: '/api/pack/budget', ask: 'budget', novelty: true },

  meal:     { path: '/api/pack/meal', ask: 'meal', novelty: true },
  mood:     { path: '/api/pack/mood', quiz: 'mood', novelty: true },
  evening:  { path: '/api/pack/evening', quiz: 'evening', novelty: true },
  party:    { path: '/api/pack/party', ask: 'party', novelty: true },
  kids:     { path: '/api/pack/kids', ask: 'kids' },
  family:   { path: '/api/family', method: 'GET' },
  heirloom: { path: '/api/family/recipes', method: 'GET' },

  geo:      { path: '/api/delivery', geo: true },
  weight:   { path: '/api/weight', method: 'GET' },
  route:    { path: '/api/route', needsPack: true },
  send:     { path: '/api/pack/send', ask: 'send' },
};

/* Аналітика: відповідь — одне число, а не пак. */
const INSIGHT_HANDLERS = {
  coupons:  { path: '/api/coupons/audit' },
  savings:  { path: '/api/savings' },
  spend:    { path: '/api/spend' },
  plus:     { path: '/api/plus' },
  reminders:{ path: '/api/reminders' },
  popular:  { path: '/api/popular' },
  risk:     { path: '/api/risk', method: 'POST' },
  eco:      { path: '/api/eco' },
  impulse:  { path: '/api/impulse', ask: 'impulse' },
  compare:  { path: '/api/compare', ask: 'compare' },
  certs:    { path: '/api/certificates' },
};

let FLOWS = null, SCENARIOS = [], INSIGHTS = [];

/* Зшиваємо опис із бекенду з обробником. Сценарій без обробника (напр. grybnytsia)
   у списку не показуємо — він живе на своєму екрані. */
async function mountScenarios() {
  FLOWS = await api('/api/flows');
  SCENARIOS = (FLOWS.flows || [])
    .filter(f => HANDLERS[f.id])
    .map(f => ({ ...f, ...HANDLERS[f.id],
                 tools: f.steps.filter(x => x.kind !== 'ours')
                   .map(x => x.tool + (x.kind === 'proposed' ? '*' : '')) }));
  INSIGHTS = (FLOWS.flows || [])
    .filter(f => INSIGHT_HANDLERS[f.id])
    .map(f => ({ ...f, ...INSIGHT_HANDLERS[f.id], hint: f.result }));
  renderScenarios(document.querySelector('#scenarios'));
  renderInsights(document.querySelector('#insights'));
  const b = document.querySelector('#btn-left');
  if (b) b.title = `Сценарії — ${SCENARIOS.length + INSIGHTS.length} штук`;
}

let MODE = 'direct';           // 'llm' — через локальну модель, 'direct' — напряму
let CHAIN_TIMER = null;

function setMode(m) {
  MODE = m;
  document.querySelectorAll('[data-mode]').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.mode === m));
}

/* Сімнадцять сценаріїв підряд — це чотири тисячі пікселів скролу, у якому
   зникає і головне, і нове. Тому групуємо: перша група розгорнута, решта —
   на один клік. Групи не тематичні для краси, а за джерелом даних. */
const GROUPS = [
  { id: 'chek',   title: 'Із твоїх чеків',       open: true,
    about: 'усе будується на історії покупок' },
  { id: 'podiia', title: 'Під подію і компанію',  open: false,
    about: 'страва, настрій, вечір, зустріч, родина' },
  { id: 'shop',   title: 'Магазин і логістика',   open: false,
    about: 'відстань, вага, маршрут, «Нова пошта»' },
];

function renderScenarios(into) {
  if (!into) return;
  const card = s => `
    <div class="scn" id="scn-${s.id}">
      <div class="top"><b>${s.title}</b>
        <button class="run" onclick="runScenario('${s.id}')">Запустити</button></div>
      <div class="phrase">«${s.phrase}»</div>
      <div class="tools">${s.tools.map(t => `
        <span class="tchip ${t.endsWith('*') ? 'prop' : ''}" data-tool="${t.replace('*','')}"
          >${t.replace('silpo_','').replace('*','')}${t.endsWith('*') ? ' ⁺' : ''}</span>`).join('')}</div>
      <div class="live" id="live-${s.id}" hidden></div>
    </div>`;
  into.innerHTML = (FLOWS.groups || [])
    .filter(g => SCENARIOS.some(s => s.group === g.id))
    .map((g, i) => {
      const rows = SCENARIOS.filter(s => s.group === g.id);
      return `<details class="grp" ${i === 0 ? 'open' : ''}>
        <summary><b>${g.title}</b><span>${rows.length} · ${g.about}</span></summary>
        ${rows.map(card).join('')}</details>`;
    }).join('')
    + `<p class="soft" style="margin:10px 0 0">⁺ — tool, якого в MCP «Сільпо» ще немає.
       Ми його реалізували в себе, щоб сценарій працював, і пропонуємо додати.</p>`;
}

/* Живий ланцюг: опитуємо трейс і показуємо виклики в міру того, як вони йдуть. */
async function watchChain(id, sinceTotal) {
  const box = $('#live-' + id);
  box.hidden = false;
  const card = $('#scn-' + id);
  const tick = async () => {
    const t = await api('/api/trace?limit=40');
    const fresh = t.total > sinceTotal ? t.calls.slice(-(t.total - sinceTotal)) : [];
    box.innerHTML = fresh.map(c => `
      <div class="row ${c.kind === 'proposed' ? 'prop' : ''}">
        <span class="nm">${c.tool.replace('silpo_', '')}${c.kind === 'proposed' ? ' ⁺' : ''}</span>
        <span class="ms">${c.ms} ms</span></div>`).join('')
      || '<div class="row"><span class="spin">запит пішов…</span></div>';
    fresh.forEach(c => {
      const chip = card.querySelector(`[data-tool="${c.tool}"]`);
      if (chip) chip.classList.add('on');
    });
  };
  await tick();
  CHAIN_TIMER = setInterval(tick, 450);
  return () => { clearInterval(CHAIN_TIMER); tick(); };
}

async function runScenario(id, extraBody) {
  const s = SCENARIOS.find(x => x.id === id);
  if (s.quiz && !extraBody) return openQuiz(s);
  if (s.ask === 'meal' && !extraBody) return askMeal(s);
  if (s.geo && !extraBody) return askGeo(s);
  if (s.wellbeing && !extraBody) return askWellbeing(s);
  if (s.ask && ASKS[s.ask] && !extraBody) return ASKS[s.ask](s);
  // Новизна — окреме питання, і воно йде ПІСЛЯ теми: спершу «що», потім «яке».
  if (s.novelty && !(extraBody || {}).novelty) return askNovelty(s, extraBody || {});
  if (s.needsPack && !PACK) return toast('Спершу збери пак — маршрут будується під нього');
  if (s.id === 'route' && !extraBody)
    extraBody = { items: PACK.items.map(i => ({ name: i.name })), branch_id: PACK.branch || null };

  $('#scn-' + id).querySelectorAll('.tchip').forEach(c => c.classList.remove('on'));
  const before = (await api('/api/trace?limit=1')).total;
  const stop = await watchChain(id, before);

  // Сценарій ЗАВЖДИ виконується тим самим MCP-викликом — і від кнопки, і
  // «через модель». Тому обидва режими дають рівно той самий пак; модель у
  // другому режимі лише переказує готовий результат людською мовою.
  const result = await callScenario(s, extraBody);
  stop();
  if (MODE === 'llm') return narrateResult(s, result);
  handleResult(s, result);
}

/* «Через модель»: показуємо пак і просимо модель озвучити його. */
async function narrateResult(s, result) {
  bubble('me', s.phrase);
  if (!result || result.error) {
    bubble('it', 'Сценарій не виконався — дивись повідомлення про помилку.');
    return handleResult(s, result);
  }
  handleResult(s, result);

  // Модель озвучує лише ПАК. У вердикт-екранів (вага, ризик збирання,
  // доставка) немає ні сум, ні позицій — модель їх просто вигадує.
  const isPack = result.item_count != null || Array.isArray(result.items);
  if (!isPack) {
    const line = result.verdict || result.headline || 'Готово — дивись картку нижче.';
    return bubble('it', line);
  }

  bubble('it', '…');
  const line = $('#log').lastElementChild;
  let n;
  try {
    n = await api('/api/chat/narrate', 'POST',
      { phrase: s.phrase, tool: (s.tools?.[0] || '').replace('*', ''), result });
  } catch (e) {
    n = { error: String((e && e.message) || e) };
  }
  if (n && n.reply && n.model) {
    line.textContent = n.reply;      // ШІ справді озвучив
    speak(n.reply);
  } else {
    // «…» обіцяє, що ШІ викликано. Не справдилось — кажемо це прямо,
    // а не підсовуємо детермінований рядок замість моделі.
    const msg = (n && n.error) || 'ШІ не відповів';
    line.className = 'msg err';
    line.textContent = msg;
    toast(msg);
  }
}

async function callScenario(s, extraBody) {
  const body = { ...(s.body || {}), ...(extraBody || {}) };
  return s.method === 'GET' ? api(s.path) : api(s.path, 'POST', body);
}

function handleResult(s, r) {
  if (bad(r)) return;
  // Кнопка сценарію — це та сама фраза: лишаємо її в розмові, щоб історія
  // читалась однаково, звідки б не прийшов запит.
  if (typeof bubble === 'function' && s.phrase) {
    if (MODE !== 'llm') bubble('me', s.phrase);
    bubble('tools', '→ ' + (s.tools || []).slice(0, 3).map(t =>
      t.replace('silpo_', '').replace('*', '')).join(' · '));
  }
  if (r.items) { renderPack(r); return; }
  if (s.id === 'geo') return renderDelivery(r);
  if (s.id === 'pantry') return renderPantry(r);
  if (s.id === 'family') return renderFamily(r);
  if (s.id === 'wellbeing') return renderWellbeing(r);
  if (s.id === 'weight') return renderWeight(r);
  if (s.id === 'route') return renderRoute(r);
  if (s.id === 'heirloom') return renderHeirloom(r);
  toast('Готово');
}

/* ===================== діалоги сценаріїв ===================== */
const QUIZ = {
  mood: { title: 'Вгадай мій настрій', steps: [
    { q: 'Що зараз найбільше хочеться?', a: [['Сміятися','ігривий'],['Тиші','спокійний'],
      ['Обійняти когось','романтичний'],['Впасти на диван','втомлений']] },
    { q: 'Який був день?', a: [['Летів шкереберть','втомлений'],['Рівний','спокійний'],
      ['Вибуховий','бадьорий'],['Було що святкувати','святковий']] },
    { q: 'Вечір із ким?', a: [['Сам / сама','спокійний'],['Удвох','романтичний'],
      ['З друзями','святковий'],['З екраном','ігривий']] }],
    finish: answers => {
      const score = {};
      answers.forEach(m => score[m] = (score[m] || 0) + 1);
      return { mood: Object.keys(score).sort((a, b) => score[b] - score[a])[0], max_uah: 600 };
    } },
  evening: { title: 'Вечір удома', steps: [
    { q: 'Що вмикаєш?', a: [['Футбол','футбол'],['Фільм','фільм'],['Серіал','серіал'],
      ['Нічого — просто вечеря','вечеря']] },
    { q: 'Скільки вас?', a: [['Сам / сама','сам'],['Удвох','романтична вечеря'],
      ['Компанія','компанія']] }],
    finish: ([what, who]) => ({
      genre: what !== 'вечеря' ? what : (who === 'сам' ? 'фільм' : who), max_uah: 700 }) },
};

function openQuiz(s) {
  const def = QUIZ[s.quiz];
  let i = 0; const picked = [];
  const draw = () => {
    const step = def.steps[i];
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">${def.title}</h2><div class="soft">${step.q}</div>
      <div class="quiz">${step.a.map((a, k) =>
        `<button onclick="quizPick(${k})">${a[0]}</button>`).join('')}</div>
      <div class="dots">${def.steps.map((_, k) =>
        `<i class="${k <= i ? 'on' : ''}"></i>`).join('')}</div>`;
  };
  window.quizPick = k => {
    picked.push(def.steps[i].a[k][1]);
    if (++i < def.steps.length) return draw();
    quiz.close();
    runScenario(s.id, def.finish(picked));
  };
  draw(); quiz.showModal();
}

function askMeal(s) {
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Страва на суму</h2>
    <div class="soft">Врахую алергії, техніку на твоїй кухні та звички з чеків.</div>
    <h3>Що готуємо</h3>
    <div class="quiz" style="grid-template-columns:repeat(4,1fr)">
      ${['сніданок','обід','вечеря','десерт'].map(m =>
        `<button onclick="mealPick('${m}')" data-meal="${m}">${m}</button>`).join('')}
    </div>
    <h3>Бюджет</h3>
    <div class="filters">
      <input id="meal-sum" type="number" placeholder="без обмеження" min="50" step="10">
      ${[200,400,700].map(v => `<button class="fbtn" onclick="$('#meal-sum').value=${v}">${v} ₴</button>`).join('')}
    </div>
    <h3>Або конкретна страва</h3>
    <div class="filters"><input id="meal-q" placeholder="карбонара, шакшука…"></div>
    <button class="go" style="width:100%;margin-top:12px" onclick="mealGo()">Підібрати</button>`;
  window.MEAL = 'вечеря';
  quiz.showModal();
  setTimeout(() => document.querySelector('[data-meal="вечеря"]')?.classList.add('sel'), 0);
}
function mealPick(m) {
  window.MEAL = m;
  document.querySelectorAll('[data-meal]').forEach(b =>
    b.style.borderColor = b.dataset.meal === m ? 'var(--blue)' : '');
}
function mealGo() {
  const sum = +$('#meal-sum').value || null;
  const q = $('#meal-q').value.trim() || null;
  quiz.close();
  runScenario('meal', { meal: window.MEAL, max_uah: sum, query: q });
}

function askGeo(s) {
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Топати чи замовити</h2>
    <div class="soft">Порівняю магазини поруч і доставку. Координати нікуди не йдуть,
      крім розрахунку відстані — вони не залишають цей компʼютер.</div>
    <div class="filters" style="margin-top:14px">
      <input id="geo-total" type="number" value="700" min="0" step="50" placeholder="сума кошика">
      <button class="fbtn" onclick="geoGo(true)">Взяти мою геолокацію</button>
    </div>
    <h3>Або адреса словами</h3>
    <div class="filters"><input id="geo-addr" placeholder="Київ, Оболонський проспект 1Б"></div>
    <button class="go" style="width:100%;margin-top:12px" onclick="geoGo(false)">Порівняти</button>`;
  quiz.showModal();
}
async function geoGo(useDevice) {
  const total = +$('#geo-total').value || 0;
  const addr = $('#geo-addr')?.value.trim();
  quiz.close();
  if (useDevice && navigator.geolocation) {
    toast('Питаю геолокацію…');
    return navigator.geolocation.getCurrentPosition(
      pos => runScenario('geo', { latitude: pos.coords.latitude,
        longitude: pos.coords.longitude, cart_total_uah: total }),
      () => toast('Геолокацію не дали — введи адресу словами'));
  }
  if (!addr) return toast('Потрібна адреса або геолокація');
  toast('Шукаю адресу…');
  const found = await api('/api/address?address=' + encodeURIComponent(addr));
  const first = (found.addresses || [])[0];
  if (!first) return toast('Такої адреси не знайшлось');
  runScenario('geo', { latitude: first.latitude, longitude: first.longitude,
    cart_total_uah: total });
}

function askWellbeing(s) {
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Як ти сьогодні</h2>
    <div class="soft">Ці дані прийшли б із фітнес-трекера чи трекера настрою через їхній MCP.
      Тут вводимо руками, щоб показати сценарій.</div>
    <h3>Тренування</h3>
    <div class="quiz" style="grid-template-columns:repeat(3,1fr)">
      ${['силове','кардіо','не було'].map(w =>
        `<button onclick="WB.workout='${w}';mark(this)">${w}</button>`).join('')}</div>
    <h3>Скільки спав</h3>
    <div class="quiz" style="grid-template-columns:repeat(3,1fr)">
      ${[5,7,9].map(h => `<button onclick="WB.sleep_hours=${h};mark(this)">${h} год</button>`).join('')}</div>
    <button class="go" style="width:100%;margin-top:14px" onclick="wbGo()">Підібрати</button>`;
  window.WB = { source: 'ручне введення' };
  quiz.showModal();
}
function mark(btn) {
  [...btn.parentNode.children].forEach(b => b.style.borderColor = '');
  btn.style.borderColor = 'var(--blue)';
}
function wbGo() { quiz.close(); runScenario('wellbeing', WB); }

/* ===================== вивід нестандартних результатів ===================== */
function renderDelivery(r) {
  if (!r.options?.length) return toast('Магазинів поруч не знайшлось');
  $('#pack').innerHTML = `
    <h2>Як забрати</h2>
    <p class="soft" style="margin:0 0 12px">У радіусі ${r.radius_km} км — ${r.within_radius} магазинів.
      Ціни доставки й пороги — з <code>get_time_slots</code>.</p>
    <div class="wrap-x"><table style="width:100%;font-size:13.5px">
      <thead><tr><th>Спосіб</th><th>Магазин</th><th>Пішки</th><th>Ціна</th><th>Мінімум</th><th>Слот</th></tr></thead>
      <tbody>${r.options.map(o => `<tr>
        <td>${o.delivery_type}</td>
        <td>${o.branch}<br><span class="soft">${o.distance_km != null ? o.distance_km + " км" : "доставка"}</span></td>
        <td>${o.walk_minutes != null ? o.walk_minutes + " хв" : "—"}</td>
        <td><b>${o.cost_uah ? uah(o.cost_uah) + ' ₴' : 'безкоштовно'}</b>
          ${o.next_tier ? `<br><span class="soft">${uah(o.next_tier.cost_uah)} ₴
            від ${uah(o.next_tier.from_uah)} ₴ — бракує ${uah(o.next_tier.need_more_uah)} ₴</span>` : ''}</td>
        <td>${o.min_order_uah ? uah(o.min_order_uah) + ' ₴' : '—'}
          ${o.meets_minimum ? '' : '<br><span class="soft" style="color:var(--red)">не дотягує</span>'}</td>
        <td>${o.slot || '—'}</td></tr>`).join('')}</tbody>
    </table></div>
    <div class="note" style="margin-top:12px">${r.spec}</div>`;
}
function renderPantry(r) {
  $('#pack').innerHTML = `
    <h2>Чого немає вдома</h2>
    <p class="soft" style="margin:0 0 12px">Джерело інвентарю: ${r.pantry_source || 'ще не синхронізовано'}
      ${r.pantry_at ? '· ' + r.pantry_at : ''}</p>
    ${r.missing?.length ? r.missing.map(m => `<div class="habit"><b>${m.name}</b>
      береш кожні ~${m.cycle_days} дн., минуло ${m.days_since}</div>`).join('')
      : '<p class="muted">Усе на місці.</p>'}
    <button class="go" style="margin-top:12px" onclick="runScenario('reorder')">Зібрати пак із цього</button>
    <div class="note" style="margin-top:12px">${r.spec}</div>`;
}
function renderFamily(r) {
  $('#pack').innerHTML = `
    <h2>Сімʼя</h2>
    ${r.members.map(m => `<div class="habit"><b>${m.name} <span class="soft">· ${m.role}${
      m.age ? ', ' + m.age + ' р.' : ''}</span></b>
      ${m.known ? `любить: ${(m.likes || []).join(', ') || '—'} · не можна:
        ${(m.allergies || []).join(', ') || '—'}`
        : '<span style="color:var(--red)">вподобань немає — MCP їх не віддає</span>'}</div>`).join('')}
    ${r.pets.map(p => `<div class="habit"><b>${p.name} <span class="soft">· ${p.kind}</span></b>
      корм додається автоматично</div>`).join('')}
    <button class="go" style="margin-top:12px" onclick="familyDinner()">
      Зібрати вечерю на всіх</button>
    <div class="note" style="margin-top:12px">${r.spec}</div>`;
}
async function familyDinner(){
  toast('Збираю з поправкою на чиїсь алергії…');
  const p = await api('/api/pack/family', 'POST', { theme: 'вечеря', max_uah: 900 });
  if (bad(p)) return;
  renderPack(p);
  if ((p.blocked_for_everyone || []).length)
    toast('Виключив для всіх: ' + p.blocked_for_everyone.join(', '));
}
function renderWellbeing(r) {
  $('#pack').innerHTML = `
    <h2>За твоїм станом</h2>
    <p class="soft">${JSON.stringify(r.stored)}</p>
    <div class="chips" style="margin:10px 0">${(r.suggested_queries || []).map(q =>
      `<span class="tag">${q}</span>`).join('') || '<span class="soft">без підказок</span>'}</div>
    <button class="go" onclick="buildFrom(${JSON.stringify(r.suggested_queries || []).replace(/"/g,'&quot;')})">
      Зібрати пак із цього</button>
    <div class="note" style="margin-top:12px">${r.spec}</div>`;
}
async function buildFrom(items) {
  if (!items.length) return toast('Нема з чого збирати');
  const p = await api('/api/pack/build', 'POST',
    { name: 'Під самопочуття', items, max_uah: 500 });
  if (!bad(p)) renderPack(p);
}

/* ===================== картка товару ===================== */
async function showProduct(slug, name) {
  toast('Читаю картку…');
  const p = await api('/api/product?slug=' + encodeURIComponent(slug));
  if (bad(p)) return;
  const c = p.composition || {};
  const also = await api('/api/also_bought?product_name=' + encodeURIComponent(p.name || name || ''));
  $('#picker-body').innerHTML = `
    <div class="head"><div class="t"><h2 style="margin:0 0 2px">${p.name}</h2>
      <div class="soft">${p.unit || ''} · у наявності ${p.stock ?? '—'}</div></div>
      <button class="go ghost" onclick="picker.close()">Закрити</button></div>
    <div class="pcard">
      <img src="${(p.images || [])[0] || ''}" alt="" loading="lazy">
      <div class="info">
        <div style="font-size:26px;font-weight:800;margin-bottom:8px">
          ${p.old_price_uah ? `<span class="old">${uah(p.old_price_uah)} ₴</span> ` : ''}${uah(p.price_uah)} ₴</div>
        ${Object.entries(p.attributes || {}).map(([k, v]) =>
          `<div class="attr"><span>${k}</span><span>${v}</span></div>`).join('')
          || '<div class="soft">Атрибутів немає.</div>'}
        ${p.url ? `<p style="margin:10px 0 0"><a href="${p.url}" target="_blank" rel="noopener">
          Картка на silpo.ua →</a></p>` : ''}
      </div>
    </div>
    <div class="alerg">
      <b>Ймовірні алергени:</b> ${(c.likely_allergens || []).join(', ') || 'не виявлено'}
      <span class="simchip">${c.simulated ? 'simulated' : 'з API'}</span>
      <div class="soft" style="margin-top:6px">${p.verify_note}</div>
    </div>
    ${also.also_bought?.length ? `<h3>З цим беруть</h3>
      <div class="chips">${also.also_bought.map(a =>
        `<span class="tag">${a.name} <b>×${a.times}</b></span>`).join('')}</div>
      <p class="soft">Порахувано з ${also.receipts_with_it} твоїх чеків.</p>` : ''}`;
  picker.showModal();
}

/* ===================== заміна з фільтрами ===================== */
let PICK_STATE = { productId: null, prefer: 'any', query: null, max: null };
async function pick(id, patch) {
  PICK_STATE = { ...PICK_STATE, productId: id, ...(patch || {}) };
  const d = await api('/api/pack/alternatives', 'POST', {
    pack_id: PACK.id, product_id: PICK_STATE.productId, prefer: PICK_STATE.prefer,
    query: PICK_STATE.query, max_price: PICK_STATE.max, limit: 8 });
  if (bad(d)) return;
  $('#picker-body').innerHTML = `
    <div class="head"><div class="t">
      <h2 style="margin:0 0 2px">Замість «${d.current.name}»</h2>
      <div class="soft">зараз ${uah(d.current.price_uah)} ₴ · нічого не змінюється, поки не обереш ·
        <button class="link" onclick="showProduct('${d.current.slug}')">відомості про товар</button></div></div>
      <button class="go ghost" onclick="picker.close()">Закрити</button></div>
    <div class="filters">
      <input id="alt-q" placeholder="пошук серед товарів «Сільпо»" value="${PICK_STATE.query || ''}"
        onkeydown="if(event.key==='Enter')applyFilters()">
      <button class="fbtn" data-prefer="any" onclick="setPrefer('any')">усе схоже</button>
      <button class="fbtn" data-prefer="cheaper" onclick="setPrefer('cheaper')">дешевше</button>
      <button class="fbtn" data-prefer="promo" onclick="setPrefer('promo')">зі знижкою</button>
      <input id="alt-max" type="number" style="max-width:120px" placeholder="до, ₴"
        value="${PICK_STATE.max || ''}" onkeydown="if(event.key==='Enter')applyFilters()">
      <button class="fbtn" onclick="applyFilters()">Застосувати</button>
    </div>
    ${d.hidden_by_allergies?.length ? `<p class="soft" style="color:var(--red)">
      Приховано через твої обмеження: ${d.hidden_by_allergies.length}</p>` : ''}
    ${d.options.length ? `<div class="opts">${d.options.map(o => `
      <div class="opt">
        <img src="${o.image || ''}" alt="" loading="lazy">
        <span style="flex:1;min-width:0">
          <span class="nm" style="display:block;font-size:13px;font-weight:600">${o.name}</span>
          <span class="soft">${o.unit || ''}${o.old_price_uah ? ` · було ${uah(o.old_price_uah)} ₴` : ''}${
            o.multibuy ? ' · мультипак' : ''}</span>
          <button class="link" onclick="event.stopPropagation();showProduct('${o.slug}')">відомості</button>
        </span>
        <span class="d">
          <span class="pr" style="display:block;font-weight:800">${uah(o.price_uah)} ₴</span>
          <span class="${o.delta_uah < 0 ? 'down' : 'up'}">${o.delta_uah > 0 ? '+' : ''}${uah(o.delta_uah)} ₴</span>
          <button class="fbtn" style="margin-top:5px"
            onclick="swapTo('${PICK_STATE.productId}','${o.product_id}')">обрати</button>
        </span>
      </div>`).join('')}</div>` : `<p class="muted">${d.note}</p>`}`;
  document.querySelectorAll('[data-prefer]').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.prefer === PICK_STATE.prefer));
  if (!picker.open) picker.showModal();
}
function setPrefer(p) { pick(PICK_STATE.productId, { prefer: p }); }
function applyFilters() {
  pick(PICK_STATE.productId, { query: $('#alt-q').value.trim() || null,
    max: +$('#alt-max').value || null });
}

/* ===================== колода свайпів ===================== */
let DECK = [], DECK_I = 0;
async function loadDeck(into) {
  const d = await api('/api/deck');
  DECK = d.cards || []; DECK_I = 0;
  drawDeck(into, d.already_swiped);
}
function drawDeck(into, swiped) {
  const card = DECK[DECK_I];
  into.innerHTML = !card
    ? `<p class="muted">Картки скінчились. Оцінено: ${swiped ?? DECK_I}.</p>`
    : `<div class="deck"><div class="swipecard">
         <img src="${card.image || ''}" alt="" loading="lazy">
         <div class="nm">${card.name}</div>
         <div class="pr">${uah(card.price_uah)} ₴
           ${card.old_price_uah ? `<span class="old">${uah(card.old_price_uah)} ₴</span>` : ''}</div>
         <div class="soft">${card.unit || ''}</div>
       </div></div>
       <div class="deck-btns">
         <button class="no" onclick="swipe(false)" title="не показувати">${icon('close', 22)}</button>
         <button class="yes" onclick="swipe(true)" title="в обране">${icon('heart', 22)}</button>
       </div>
       <p class="soft" style="text-align:center">${DECK_I + 1} із ${DECK.length}</p>`;
}
async function swipe(liked) {
  const card = DECK[DECK_I];
  if (!card) return;
  await api('/api/swipe', 'POST', { product_id: card.product_id,
    external_id: card.external_id, liked, name: card.name });
  toast(liked ? 'В «Обране» «Сільпо»' : 'Більше не покажу');
  DECK_I++;
  drawDeck($('#deck'), null);
}

/* ===================== кошик у вигляді застосунку ===================== */
async function renderCart(into) {
  const c = await api('/api/cart');
  if (bad(c)) return;
  const box = into || $('#cart');
  if (!box) return;
  if (!c.items.length) {
    box.innerHTML = `<p class="muted">Кошик порожній. Збери пак — і поклади його сюди.</p>`;
    return;
  }
  const weight = c.weight_kg ? `${c.weight_kg} кг` : '—';
  box.innerHTML = `
    ${(c.warnings || []).length ? `<div class="warnbar bad">
      ${c.warnings.map(w => w.message === 'product.offer.stock.max'
        ? 'Товар щойно закінчився — «Сільпо» зменшила кількість.' : w.message).join('<br>')}
    </div>` : ''}
    <h3 style="margin:0 0 4px">Ваше замовлення: ${c.items.length} товарів</h3>
    <p class="soft" style="margin:0 0 8px">${c.delivery_type}${c.slot ? ' · з ' + c.slot : ''}</p>
    ${c.items.map(i => `
      <div class="crow">
        <img src="${i.image || ''}" alt="" loading="lazy">
        <div class="mid">
          <div class="nm">${i.name}</div>
          <div class="un">${i.unit || ''}</div>
          <div class="prices">
            ${i.old_price_uah ? `<span class="was">${uah(i.old_price_uah)} ₴</span>
              <span class="off">−${i.discount_percent}%</span>` : ''}
            <span class="now">${uah(i.line_total_uah)} ₴</span>
          </div>
        </div>
        <div class="side">
          <button class="icobtn" title="Відомості про товар"
            onclick="showProduct('${i.slug}')">ⓘ</button>
          <div class="stepper">
            <button onclick="setQty('${i.product_id}', ${i.qty - (i.step || 1)})">−</button>
            <span>${i.qty} шт</span>
            <button onclick="setQty('${i.product_id}', ${i.qty + (i.step || 1)})">+</button>
          </div>
        </div>
      </div>`).join('')}
    <div class="sums">
      <div class="r"><span>Товари</span><span>${uah(c.goods_uah)} ₴</span></div>
      ${c.service_uah ? `<div class="r"><span>Сервісний збір</span><span>${uah(c.service_uah)} ₴</span></div>` : ''}
      <div class="r"><span>Доставка</span><span>${c.delivery_uah ? uah(c.delivery_uah) + ' ₴' : '0.00 ₴'}</span></div>
      <div class="r"><span>Загальна вага</span><span>${weight}</span></div>
      <div class="r disc"><span>Сума знижки</span><span>${uah(c.discount_uah)} ₴</span></div>
      <div class="r total"><span>До оплати</span><span>${uah(c.total_uah)} ₴</span></div>
    </div>
    <button class="checkoutbar" style="margin-top:12px"
      onclick="window.open('${c.checkout_url}','_blank')">
      <span>Оформити</span><span>${uah(c.total_uah)} ₴</span></button>
    <p class="soft" style="text-align:center;margin:8px 0 0">
      Оформлення підтверджуєш ти — агент доводить до цієї кнопки й зупиняється.</p>`;
}

async function setQty(productId, qty) {
  if (qty <= 0) return removeFromCart(productId);
  toast('Оновлюю…');
  await api('/api/cart/qty', 'POST', { product_id: productId, quantity: qty });
  renderCart();
}
async function removeFromCart(productId) {
  await api('/api/cart/remove', 'POST', { product_id: productId });
  toast('Прибрав'); renderCart();
}

/* ===================== «Який ти фрукт сьогодні» ===================== */
/* Настрій під продуктовий магазин: замість абстрактних станів — фрукт,
   і кожен фрукт тягне свою полицю. Мемно, але веде до реальних товарів. */
const FRUITS = {
  'ананас':    { line: 'колючий зовні, солодкий усередині', mood: 'ігривий' },
  'кавун':     { line: 'великий, соковитий, на всю компанію', mood: 'святковий' },
  'лимон':     { line: 'кислий і має на те причини', mood: 'втомлений' },
  'авокадо':   { line: 'або ще ні, або вже все', mood: 'спокійний' },
  'банан':     { line: 'простий, надійний, завжди під рукою', mood: 'бадьорий' },
  'полуниця':  { line: 'ніжна і трохи закохана', mood: 'романтичний' },
};
const FRUIT_QUIZ = [
  { q: 'Ранок почався з…', a: [['Кави на бігу','банан'],['Тиші й вікна','авокадо'],
      ['Будильника втретє','лимон'],['Гарного сну','полуниця']] },
  { q: 'Вечір мрії — це…', a: [['Гучна компанія','кавун'],['Серіал під ковдрою','авокадо'],
      ['Щось несподіване','ананас'],['Удвох і без телефона','полуниця']] },
  { q: 'Твоя полиця в магазині…', a: [['Де все зі знижкою','лимон'],['Де солодке','ананас'],
      ['Де свіже й зелене','авокадо'],['Де на компанію','кавун']] },
];
QUIZ.mood = {
  title: 'Який ти фрукт сьогодні',
  steps: FRUIT_QUIZ,
  finish: answers => {
    const score = {};
    answers.forEach(f => score[f] = (score[f] || 0) + 1);
    const fruit = Object.keys(score).sort((a, b) => score[b] - score[a])[0];
    const f = FRUITS[fruit];
    toast(`Сьогодні ти ${fruit} — ${f.line}`);
    return { mood: f.mood, max_uah: 600, fruit };
  },
};


/* ===================== нові сценарії ===================== */
function renderWeight(r) {
  $('#pack').innerHTML = `
    <h2>Чи влізе кошик</h2>
    <p class="soft" style="margin:0 0 12px">Вага кошика — ${r.cart_weight_kg} кг.
      Ліміти беруться з доступних слотів: у доставки він є, у самовивозу немає.</p>
    ${r.blocked.length ? `<div class="warnbar bad">${r.verdict}</div>`
      : `<div class="warnbar">${r.verdict}</div>`}
    ${r.options.map(o => `<div class="attr"><span>${o.label}</span>
      <span>${o.max_kg ? 'макс ' + o.max_kg + ' кг' : 'без ліміту'}
        ${o.fits ? '✓' : '· перевищення ' + o.over_kg + ' кг'}</span></div>`).join('')}`;
}

function renderRoute(r) {
  $('#pack').innerHTML = `
    <h2>Маршрут по залу</h2>
    <p class="soft" style="margin:0 0 12px">${r.steps} відділів.
      Планування в кожному магазині своє — порядок можна переставити, і ми його запамʼятаємо
      для цього магазину.</p>
    ${r.route.map((step, n) => `<div class="habit">
      <b>${n + 1}. ${step.aisle}</b>${step.items.join(' · ')}</div>`).join('')}
    <div class="note" style="margin-top:12px">${r.spec}</div>`;
}

async function renderHeirloom(r) {
  $('#pack').innerHTML = `
    <h2>Спадкова кухня</h2>
    <p class="soft" style="margin:0 0 12px">Рецепти родини — будь-хто з рідних додає,
      будь-хто перетворює на кошик із поправкою на чиїсь алергії.</p>
    ${r.recipes.map(rec => `<div class="card" style="background:var(--tint);margin-bottom:10px">
      <div class="head"><div class="t"><h3 style="margin:0;text-transform:none;font-size:16px;
        letter-spacing:0;color:var(--ink)">${rec.title}</h3>
        <div class="soft">${rec.author || 'без автора'} · ${rec.meal} · ${rec.minutes} хв ·
          на ${rec.serves}</div></div>
        <button class="go" onclick="cookHeirloom('${rec.id}')">Зібрати кошик</button></div>
      <div class="chips">${rec.items.map(i => `<span class="tag">${i}</span>`).join('')}</div>
      ${rec.note ? `<p class="soft" style="margin:8px 0 0">${rec.note}</p>` : ''}
    </div>`).join('')}
    <button class="go ghost" onclick="addHeirloom()">Додати сімейний рецепт</button>`;
}
async function cookHeirloom(id) {
  const r = await api('/api/family/recipes');
  const rec = (r.recipes || []).find(x => x.id === id);
  if (!rec) return toast('Рецепт зник');
  toast('Шукаю складники…');
  const p = await api('/api/pack/build', 'POST',
    { name: rec.title, items: rec.items, max_uah: null });
  if (bad(p)) return;
  p.recipe = { title: rec.title, meal: rec.meal, minutes: rec.minutes,
               equipment: rec.equipment, serves: rec.serves, steps: rec.steps };
  renderPack(p);
}
function addHeirloom() {
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Сімейний рецепт</h2>
    <div class="soft">Стане доступним усім у «Сімейному доступі».</div>
    <label>Назва</label><input id="h-title" placeholder="Бабусині вареники">
    <label>Автор</label><input id="h-author" placeholder="Бабуся Ніна">
    <label>Складники через кому</label><input id="h-items" placeholder="борошно, картопля, цибуля">
    <label>Кроки через крапку з комою</label>
    <input id="h-steps" placeholder="Замісити тісто; зліпити; варити 5 хвилин">
    <button class="go" style="width:100%;margin-top:12px" onclick="saveHeirloom()">Зберегти</button>`;
  quiz.showModal();
}
async function saveHeirloom() {
  const r = await api('/api/family/recipe', 'POST', {
    title: $('#h-title').value.trim(),
    author: $('#h-author').value.trim(),
    items: $('#h-items').value.split(',').map(s => s.trim()).filter(Boolean),
    steps: $('#h-steps').value.split(';').map(s => s.trim()).filter(Boolean) });
  quiz.close();
  if (bad(r)) return;
  toast('Записано в книгу родини');
  runScenario('heirloom');
}

/* ===================== Новизна: знайоме чи нове ===================== */
/* Питання, яке агент має ставити САМ, а не вирішувати за гостя. «Знайоме» й
   «нове» — різні осі: свайп уліво теж робить товар знайомим. */
function askNovelty(s, body) {
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Щось знайоме чи щось нове?</h2>
    <div class="soft">Ваги смаку в тебе вже накопичені — з чеків і зі свайпів
      у «Департаменті дивинок». Питання лише, з якого боку їх читати.</div>
    <div class="quiz" style="grid-template-columns:1fr">
      <button onclick="noveltyPick('familiar')"><b>Щось знайоме</b><br>
        <span class="soft">перевірене: те, що вже було в чеках і сподобалось</span></button>
      <button onclick="noveltyPick('new')"><b>Щось нове</b><br>
        <span class="soft">чого ти ще не брав — але з полиць, які ти любиш</span></button>
      <button onclick="noveltyPick('any')"><b>Байдуже</b><br>
        <span class="soft">просто найкраще під запит</span></button>
    </div>`;
  window.noveltyPick = mode => { quiz.close(); runScenario(s.id, { ...body, novelty: mode }); };
  quiz.showModal();
}

/* ===================== діалоги нових сценаріїв ===================== */
const ASKS = {
  weekly: s => {
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">Тижневий закуп</h2>
      <div class="soft">Складеться з трьох джерел: чого немає вдома, що мало б
        закінчитись за циклом покупок, і що з улюбленого зараз в акції.
        Кожна позиція скаже, чому вона тут.</div>
      <h3>Стеля бюджету</h3>
      <div class="filters"><input id="w-sum" type="number" placeholder="без обмеження" step="50">
        ${[700,1200,2000].map(v => `<button class="fbtn" onclick="$('#w-sum').value=${v}">${v} ₴</button>`).join('')}</div>
      <button class="go" style="width:100%;margin-top:12px"
        onclick="quiz.close();runScenario('weekly',{budget_uah:+$('#w-sum').value||null})">Зібрати</button>`;
    quiz.showModal();
  },
  budget: s => {
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">Розумний бюджет</h2>
      <div class="soft">Кошик рівно під залишок. Спершу те, що вже мало б
        закінчитись, потім те, що береш найчастіше. Що не влізло — назву поіменно.</div>
      <h3>Скільки лишилось</h3>
      <div class="filters"><input id="b-sum" type="number" value="840" step="10">
        <input id="b-days" type="number" value="7" step="1" style="max-width:90px" title="на скільки днів"></div>
      <button class="go" style="width:100%;margin-top:12px"
        onclick="quiz.close();runScenario('budget',{budget_uah:+$('#b-sum').value||500,days:+$('#b-days').value||7})">Зібрати</button>`;
    quiz.showModal();
  },
  party: s => {
    const themes = ['шашлик','настолки','пікнік','день народження','футбол','фільм'];
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">Зустріч</h2>
      <div class="soft">Кількості рахуються на людей: вагове в кілограмах, штучне
        в штуках. Мішок вугілля лишається одним і на трьох, і на шістьох.</div>
      <h3>Тема</h3>
      <div class="quiz" style="grid-template-columns:repeat(3,1fr)">
        ${themes.map(t => `<button data-th="${t}" onclick="partyPick('${t}')">${t}</button>`).join('')}</div>
      <h3>Скільки людей і бюджет</h3>
      <div class="filters">
        <input id="p-people" type="number" value="6" min="2" max="30" style="max-width:90px">
        <input id="p-sum" type="number" placeholder="бюджет" step="100"></div>
      <button class="go" style="width:100%;margin-top:12px" onclick="partyGo()">Зібрати</button>`;
    window.PARTY = 'шашлик';
    quiz.showModal();
    setTimeout(() => partyPick('шашлик'), 0);
  },
  kids: s => {
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">Дитяча зона за віком</h2>
      <div class="soft">Вік візьму з акаунта «Сільпо»
        (<span class="mono">get_my_family.children[].dateOfBirth</span>) — поле є в API
        і не використовується ніде. Підлітку 16 «дитячі товари» означають інше,
        ніж однорічному.</div>
      <div class="filters" style="margin-top:12px">
        <input id="k-sum" type="number" placeholder="бюджет" step="50"></div>
      <button class="go" style="width:100%;margin-top:12px"
        onclick="quiz.close();runScenario('kids',{max_uah:+$('#k-sum').value||null})">Підібрати</button>`;
    quiz.showModal();
  },
  send: s => {
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">Відправ рідним в інше місто</h2>
      <div class="soft">Логістика в «Сільпо» вже є: NovaPoshta в типах доставки
        і довідник відділень у двох tools. Бракує лише історії — ось вона.</div>
      <h3>Куди</h3>
      <div class="filters"><input id="s-city" value="Полтава" placeholder="місто">
        <input id="s-office" placeholder="№ відділення (необовʼязково)" style="max-width:190px"></div>
      <h3>Що покласти</h3>
      <div class="filters"><input id="s-items" value="кава, шоколад, печиво, чай"></div>
      <button class="go" style="width:100%;margin-top:12px" onclick="sendGo()">Зібрати й знайти відділення</button>`;
    quiz.showModal();
  },
  impulse: s => {
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">Чи варто це брати</h2>
      <div class="soft">Порівняю поточну ціну з твоєю власною середньою за чеками
        і подивлюсь, скільки разів ти брав це за 30 днів. Агент, який лише
        продає, — не помічник.</div>
      <div class="filters" style="margin-top:12px">
        <input id="i-name" value="чипси" placeholder="що саме"></div>
      <button class="go" style="width:100%;margin-top:12px"
        onclick="quiz.close();runInsight('impulse',{name:$('#i-name').value.trim()})">Спитати</button>`;
    quiz.showModal();
  },
  compare: s => {
    $('#quiz-body').innerHTML = `
      <h2 style="margin:0 0 2px">Де вигідніше</h2>
      <div class="soft">Ціна прив'язана до магазину, а <span class="mono">find_products_batch</span>
        приймає branchId прямо в аргументах — тож порівняння можливе без жодного нового tool.</div>
      <h3>Список</h3>
      <div class="filters"><input id="c-items" value="молоко, хліб, яйця, кава"></div>
      <h3>Місто і скільки магазинів</h3>
      <div class="filters"><input id="c-city" value="Київ">
        <input id="c-limit" type="number" value="4" min="2" max="8" style="max-width:80px"></div>
      <button class="go" style="width:100%;margin-top:12px" onclick="compareGo()">Порівняти</button>`;
    quiz.showModal();
  },
};

function partyPick(t) {
  window.PARTY = t;
  document.querySelectorAll('[data-th]').forEach(b =>
    b.style.borderColor = b.dataset.th === t ? 'var(--blue)' : '');
}
function partyGo() {
  quiz.close();
  runScenario('party', { theme: window.PARTY, people: +$('#p-people').value || 4,
                         max_uah: +$('#p-sum').value || null });
}
function sendGo() {
  const items = $('#s-items').value.split(',').map(x => x.trim()).filter(Boolean);
  quiz.close();
  runScenario('send', { city: $('#s-city').value.trim() || 'Полтава', items,
                        office_query: $('#s-office').value.trim() || null });
}
function compareGo() {
  const items = $('#c-items').value.split(',').map(x => x.trim()).filter(Boolean);
  quiz.close();
  runInsight('compare', { items, city: $('#c-city').value.trim() || 'Київ',
                          limit: +$('#c-limit').value || 4 });
}

/* ===================== Аналітика ===================== */
function renderInsights(into) {
  if (!into) return;
  into.innerHTML = INSIGHTS.map(i => `
    <div class="scn" id="ins-${i.id}">
      <div class="top"><b>${i.title}</b>
        <button class="run" onclick="runInsight('${i.id}')">Спитати</button></div>
      <div class="phrase">«${i.phrase}»</div>
      <div class="soft" style="font-size:12px">${i.hint}</div>
      <div class="live" id="ires-${i.id}" hidden></div>
    </div>`).join('')
    + `<p class="soft" style="margin:10px 0 0">Жодного нового tool: усе рахується з
       тих 40, що вже працюють. Не використовує їх ніхто, бо відповідь живе
       на стику двох викликів.</p>`;
}

async function runInsight(id, body) {
  const i = INSIGHTS.find(x => x.id === id);
  if (i.ask && !body) return ASKS[i.ask](i);
  const box = $('#ires-' + id);
  box.hidden = false;
  box.innerHTML = '<div class="row"><span class="spin">рахую з чеків…</span></div>';
  const r = (i.method === 'POST' || body)
    ? await api(i.path, 'POST', body || {})
    : await api(i.path);
  if (bad(r)) { box.innerHTML = ''; return; }
  box.innerHTML = insightView(id, r);
  window.LAST_INSIGHT = r;
}

const money = v => uah(v) + ' ₴';

function insightView(id, r) {
  const line = (a, b, cls) => `<div class="row ${cls||''}"><span class="nm">${a}</span>
    <span class="ms">${b}</span></div>`;
  if (id === 'coupons') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b></div>
    ${r.expired_count ? line('згоріли невикористаними', r.expired_count + ' шт', 'prop') : ''}
    ${(r.burning||[]).slice(0,5).map(c =>
      line(`${c.about||'купон'} · ${c.reward||''}`,
           c.days_left === 0 ? 'сьогодні' : c.days_left + ' дн', c.days_left <= 1 ? 'prop' : '')).join('')}
    ${(r.not_activated||[]).length ? `<p class="soft" style="margin:7px 0 0">
      Не активовано ${r.not_activated.length} — активувати треба руками в застосунку:
      tool на запис у MCP немає.</p>` : ''}`;
  if (id === 'savings') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b></div>
    ${line('частка знижок у сумі', r.saved_share + '%')}
    ${line('балобонусів нараховано', money(r.bonuses_uah))}
    ${(r.by_promo||[]).slice(0,4).map(p =>
      line((p.text||'промо').slice(0,44), `${money(p.uah)} · ${p.times}×`)).join('')}
    <p class="soft" style="margin:7px 0 0">Звірка через <span class="mono">promoId</span>:
      купон ↔ <span class="mono">rewards[]</span> у чеку. Точний збіг, не здогадка.</p>`;
  if (id === 'spend') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b>
      ${r.delta_percent != null ? `<span class="${r.delta_percent>0?'due':''}">
        ${r.delta_percent>0?'+':''}${r.delta_percent}%</span>` : ''}</div>
    ${(r.categories||[]).slice(0,6).map(c => line(c.category,
      `${money(c.now_uah)}${c.delta_percent!=null?` · ${c.delta_percent>0?'+':''}${c.delta_percent}%`:''}`,
      (c.delta_percent||0) >= 25 ? 'prop' : '')).join('')}`;
  if (id === 'plus') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b></div>
    ${line('береш на місяць', money(r.per_month_uah))}
    ${line('кешбек за місяць', money(r.cashback_per_month_uah))}
    ${line('підписка коштує', money(r.price_uah))}
    ${line('чистими', money(r.net_per_month_uah), r.net_per_month_uah > 0 ? '' : 'prop')}
    <p class="soft" style="margin:7px 0 0">${r.gap}</p>`;
  if (id === 'reminders') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b></div>
    ${(r.overdue||[]).slice(0,5).map(h =>
      line(h.name.slice(0,40), `прострочено ${-h.days_left} дн`, 'prop')).join('')}
    ${(r.soon||[]).slice(0,3).map(h =>
      line(h.name.slice(0,40), `через ${h.days_left} дн`)).join('')}
    ${r.pet_note ? `<p class="soft" style="margin:7px 0 0">${r.pet_note}</p>` : ''}`;
  if (id === 'popular') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b></div>
    ${(r.categories||[]).slice(0,6).map(c => line(c.title, '')).join('')}
    <p class="soft" style="margin:7px 0 0">${r.gap}</p>`;
  if (id === 'risk') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline || r.note}</b></div>
    ${(r.risky||[]).slice(0,5).map(x =>
      line(x.name || x.product_id, (x.options||[]).length + ' замін')).join('')}`;
  if (id === 'eco') return `
    <div class="head" style="margin:0 0 6px"><b>Екооцінка ${r.score}/100</b></div>
    ${r.weight_kg ? line('вага кошика', r.weight_kg + ' кг') : ''}
    ${(r.single_use||[]).map(n => line(n.slice(0,40), 'одноразове', 'prop')).join('')}
    ${(r.advice||[]).map(a => `<p class="soft" style="margin:5px 0 0">${a}</p>`).join('')}
    <p class="soft" style="margin:7px 0 0">${r.gap}</p>`;
  if (id === 'impulse') return `
    <div class="head" style="margin:0 0 6px"><b>${r.verdict === 'бери' ? '✅ бери' : '⏸ почекай'}
      · ${r.query}</b></div>
    ${(r.reasons||[]).map(x => line(x, '')).join('')}
    ${line('брав усього', r.times_bought + ' раз(и), за 30 дн — ' + r.times_last_30d)}
    ${r.avg_paid_uah ? line('твоя середня ціна', money(r.avg_paid_uah)) : ''}
    ${r.price_now_uah ? line('зараз', money(r.price_now_uah)) : ''}`;
  if (id === 'certs') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline || r.error}</b></div>
    ${(r.certificates || []).map(c => line(`${c.value_uah} ₴ · до ${c.expires || '—'}`,
      c.days_left != null ? `${c.days_left} дн` : '')).join('')}
    ${r.cart_total_uah ? line('кошик зараз', money(r.cart_total_uah)) : ''}
    ${r.left_to_pay_uah != null && r.count ? line('лишиться доплатити', money(r.left_to_pay_uah),
      r.covers_cart ? '' : 'prop') : ''}
    <p class="soft" style="margin:7px 0 0">${r.gap || r.note || ''}</p>`;
  if (id === 'compare') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b></div>
    ${(r.branches||[]).map(b => line(`${b.city||''} ${b.address||b.branch_id}`.slice(0,40),
      b.error ? 'помилка' : `${money(b.total_uah)}${b.missing?.length ? ` · нема ${b.missing.length}` : ''}`,
      r.best && b.branch_id === r.best.branch_id ? '' : '')).join('')}
    <p class="soft" style="margin:7px 0 0">${r.how}</p>`;
  return `<div class="row"><span class="nm">Готово</span></div>`;
}
