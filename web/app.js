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
/* Імена учасників компанії вводить людина — у розмітку вони йдуть екранованими.
   Префікс не з примхи: app.js вантажиться на кожну сторінку, а inline-скрипти
   сторінок живуть у ТОМУ САМОМУ глобальному просторі. `esc` уже оголошено в
   tech.html, `csv` — у profile.html; повторний `const` валить увесь скрипт
   сторінки SyntaxError'ом ще до першого рядка. */
const uiEsc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

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
  // компанія — три однакові фігури в ряд: рівні, на відміну від «сімʼї»
  phone:    '<rect x="7" y="2.5" width="10" height="19" rx="2.4"/><path d="M10.8 5.4h2.4"/><path d="M10.5 18.8h3"/>',
  crew:     '<circle cx="6" cy="9" r="2.2"/><circle cx="12" cy="8" r="2.4"/><circle cx="18" cy="9" r="2.2"/><path d="M2 18a4 4 0 0 1 8 0M14 18a4 4 0 0 1 8 0M8.5 19a3.6 3.6 0 0 1 7 0"/>',
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
  rec:      '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/>',
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
  const tech = current === 'tech';
  document.body.insertAdjacentHTML('afterbegin', `
    <div class="top"><div class="in">
      <a class="brand" href="/">
        <span class="dot"></span>
        <span><b>${home ? '' : '← '}Машрум Генадійович</b>
          <span>Персоналізація${{profile:' · профіль', game:' · грибниця',
                   tech:' · під капотом'}[current] || ''}</span></span></a>
      ${tech ? '' : `<button class="iconbtn sm plain" id="btn-left"
        onclick="togglePanel('l')" title="Сценарії" aria-pressed="true"
        >${icon('panel', 18)}</button>`}
      ${tech ? '' : `<button class="iconbtn sm plain" id="phonebtn"
        onclick="openPhoneSize()" title="Розмір телефона">${icon('phone', 18)}</button>`}
      ${tech ? '' : `<button class="iconbtn sm plain" id="recbtn"
        onclick="setRec(true)" title="Режим запису: лише телефон (Alt+R)">${icon('rec', 18)}</button>`}
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
  applyPhoneSize(phoneSize());
  setView(tech ? 'desktop' : 'mobile');
  // ?rec — одразу в режим запису; ?rec=trace — телефон разом зі стрічкою
  // викликів. Стан живе в адресі, тож перезавантаження його не збиває.
  const rec = new URLSearchParams(location.search).get('rec');
  if (rec !== null && !tech) setRec(true, rec === 'trace', true);
}

/* ---------- режим запису ----------
   Для відео потрібен лише екран гостя: без шапки, панелі сценаріїв і
   дев-підказок. Телефон стає по центру на чистому тлі в тому розмірі, що
   обрано в «Розмір телефона». `trace` лишає праворуч стрічку «Що
   відбувається» — для запису, де важливо показати виклики MCP поруч з
   екраном. Вихід — Alt+R: кнопки на екрані немає навмисно, щоб її не
   було й на записі. */
function setRec(on, trace = false, silent = false) {
  document.body.classList.toggle('rec', on);
  document.body.classList.toggle('rec-trace', on && trace);
  const shell = document.querySelector('#shell');
  if (shell && on) { shell.classList.remove('l'); shell.classList.toggle('r', trace); }
  if (shell && !on) { shell.classList.add('l'); shell.classList.remove('r'); }
  const url = new URL(location.href);
  if (on) url.searchParams.set('rec', trace ? 'trace' : ''); else url.searchParams.delete('rec');
  history.replaceState(null, '', url.pathname + url.search.replace(/rec=(&|$)/, 'rec$1'));
  syncPanels();
  const keys = typeof REC_KEYS !== 'undefined' ? ' · цифри — кроки демо, Alt+K — список' : '';
  if (!silent) toast(on ? (trace ? 'Запис із стрічкою · Alt+R — вийти' + keys
                              : 'Режим запису · Alt+R — вийти, Alt+T — зі стрічкою' + keys)
                       : 'Звичайний вигляд');
}
document.addEventListener('keydown', e => {
  if (!e.altKey || e.ctrlKey || e.metaKey) return;
  const k = (e.key || '').toLowerCase();
  if (k === 'r' || k === 'к') { e.preventDefault(); setRec(!document.body.classList.contains('rec')); }
  if (k === 't' || k === 'е') { e.preventDefault(); setRec(true, !document.body.classList.contains('rec-trace')); }
});

/* ---------- стрічка «що відбувається» ----------
   Праворуч від телефона, зверху вниз, без жодної схеми «ланцюг агента».
   Один рядок — один справжній виклик: назва, скільки мілісекунд, аргументи й
   відповідь. Розлого не показуємо: аргументи в один рядок, відповідь до 240
   символів, решта — за кліком. Сенс не в тому, щоб гість це читав, а в тому,
   щоб він БАЧИВ, що число на екрані виведене з API, а не вигадане. */
let LIVE_TIMER = null;       // опитування трейсу
let LIVE_SEEN = 0;           // скільки викликів уже забрано з трейсу
let LIVE_QUEUE = [];         // черга на показ
let LIVE_DRAIN = null;       // таймер, що показує чергу по одному
const LIVE_GAP = 500;        // пауза між рядками, мс

/* `args` приходить обʼєктом, `out` — рядком. String() на обʼєкті дає
   «[object Object]», тож серіалізуємо явно. */
const flatVal = v => (v == null ? ''
  : typeof v === 'string' ? v
  : (() => { try { return JSON.stringify(v, null, 1); } catch (e) { return ''; } })());

let LIVE_ITEMS = [];         // повні дані рядків — для картки за кліком

function liveRow(c) {
  const kind = c.kind === 'proposed' ? 'prop' : c.kind === 'llm' ? 'llm' : '';
  const idx = LIVE_ITEMS.push(c) - 1;
  const out = flatVal(c.out).replace(/\s+/g, ' ');
  // Людською мовою — зверху, технічна назва — дрібним під нею. Гість має
  // бачити, що агент пішов по чеки; розробник — який саме tool це зробив.
  // Людською мовою — зверху, назва tool — пілюлею під нею, підсумок — одним
  // рядком. Сирий JSON тут не потрібен: він за кліком, у картці виклику.
  const gist = c.note || (out ? out.replace(/^\{\s*"success":\s*true,?\s*/, '').slice(0, 96) : '');
  return `<div class="lrow tap ${kind} ${c.ok === false ? 'bad' : ''}"
      onclick="openCall(${idx})" title="Показати повністю">
    <div class="h"><span class="n">${uiEsc(c.title || c.tool)}</span>
      <span class="ms">${c.ms != null ? c.ms + ' ms' : ''}</span></div>
    <div class="tl"><code>${uiEsc(c.tool.replace(/^silpo_/, ''))}</code>${
      c.kind === 'proposed' ? '<em>⁺ пропонуємо</em>' : ''}</div>
    ${gist ? `<div class="io ${c.note ? 'note' : 'out'}">${uiEsc(gist)}${
      !c.note && out.length > 96 ? '…' : ''}</div>` : ''}
  </div>`;
}

/* Картка виклику: аргументи й відповідь ЦІЛКОМ. У стрічці вони обрізані
   навмисно — там треба бачити хід, а не читати JSON; читати його треба тут. */
function openCall(i) {
  const c = LIVE_ITEMS[i];
  if (!c) return;
  const args = flatVal(c.args).replace(/^\{\}$/, '');
  const out = flatVal(c.out);
  sheet(c.title || c.tool,
    `<code>${uiEsc(c.tool)}</code> · ${c.kind === 'proposed'
      ? 'tool, якого в MCP немає — ми його пропонуємо'
      : c.kind === 'llm' ? 'локальна модель' : 'офіційний tool mcp.silpo.ua'}${
      c.ms != null ? ' · ' + c.ms + ' ms' : ''}${c.at ? ' · ' + c.at : ''}`, `
    ${c.ok === false ? '<div class="warn" style="margin:0 0 12px"><b>Виклик не вдався</b></div>' : ''}
    ${c.note ? `<p class="soft" style="margin:0 0 12px">${uiEsc(c.note)}</p>` : ''}
    <h3 style="margin-top:0">Аргументи</h3>
    <pre class="calljson">${args ? uiEsc(args) : '<span class="soft">без аргументів</span>'}</pre>
    <h3>Відповідь</h3>
    <pre class="calljson">${out ? uiEsc(out) : '<span class="soft">порожньо</span>'}</pre>
    ${c.shed ? `<p class="soft" style="margin:10px 0 0">Відповідь звільнено з памʼяті:
      трейс тримає сумарний бюджет, і найстаріші віддають місце новим.</p>` : ''}`);
}

/* Черга з паузою. Виклики MCP повертаються пачкою — 15 рядків, що зʼявились
   одночасно, прочитати неможливо, і саме тоді стрічка перестає бути доказом
   і стає шумом. Показуємо по одному раз на пів секунди. */
/* Виклики групуються за тим, ЩО їх спричинило: сценарій, запит у чаті або
   фонове завантаження сторінки. Без цього стрічка — суцільний потік, у якому
   не видно, де закінчився один намір і почався інший. */
function liveGroup(title) { pushLive({ group: title }); }

function liveBody() {
  const box = $('#livefeed');
  if (!box) return null;
  if (box.dataset.empty !== 'no') { box.innerHTML = ''; box.dataset.empty = 'no'; }
  let last = box.lastElementChild;
  if (!last || !last.classList.contains('lgroup')) {
    box.insertAdjacentHTML('beforeend',
      `<div class="lgroup"><div class="gh">Фонові виклики</div><div class="gb"></div></div>`);
    last = box.lastElementChild;
  }
  return last.querySelector('.gb');
}

function pushLive(item) {
  LIVE_QUEUE.push(item);
  if (LIVE_DRAIN) return;
  const step = () => {
    const next = LIVE_QUEUE.shift();
    if (next === undefined) { clearInterval(LIVE_DRAIN); LIVE_DRAIN = null; return; }
    const box = $('#livefeed');
    if (!box) return;
    if (next && next.group) {
      if (box.dataset.empty !== 'no') { box.innerHTML = ''; box.dataset.empty = 'no'; }
      box.insertAdjacentHTML('beforeend', `<div class="lgroup enter">
        <div class="gh">${uiEsc(next.group)}</div><div class="gb"></div></div>`);
    } else {
      const body = liveBody();
      if (!body) return;
      body.insertAdjacentHTML('beforeend', next);
      body.lastElementChild?.classList.add('enter');
    }
    box.scrollTop = box.scrollHeight;
  };
  step();                                  // перший рядок — одразу
  LIVE_DRAIN = setInterval(step, LIVE_GAP);
}

/* Крок алгоритму або репліка локальної моделі — те, що не є викликом MCP,
   але без чого ланцюг не читається. Іде тією самою чергою, щоб порядок
   лишався справжнім. */
function liveStep(text, cls = 'step') {
  pushLive(`<div class="lrow ${cls}"><div class="h">
    <span class="n">${uiEsc(text)}</span></div></div>`);
}

/* Порожню групу лишати не можна: сценарій, який нічого не викликав, показував
   би заголовок над пусткою. Прибираємо її, коли черга спорожніла. */
function pruneLive() {
  document.querySelectorAll('#livefeed .lgroup').forEach(g => {
    if (!g.querySelector('.gb')?.children.length && g !== $('#livefeed').lastElementChild)
      g.remove();
  });
}

/* Опитування дешеве: спершу лише лічильник, і тільки коли він виріс —
   самі нові виклики. Доти щосекунди тягнулись 60 записів разом із
   відповідями, тобто сотні кілобайтів заради відповіді «нічого нового». */
let LIVE_IDLE = 0;
async function pumpLive() {
  const box = $('#livefeed');
  if (!box) return;
  const head = await api('/api/trace?limit=1');
  if (!head || head.total == null) return;
  if (head.total <= LIVE_SEEN) {
    // Тиша — опитуємо рідше; перший же новий виклик повертає темп.
    if (++LIVE_IDLE === 12) { clearInterval(LIVE_TIMER); LIVE_TIMER = setInterval(pumpLive, 2500); }
    return;
  }
  if (LIVE_IDLE >= 12) { clearInterval(LIVE_TIMER); LIVE_TIMER = setInterval(pumpLive, 900); }
  LIVE_IDLE = 0;
  const t = await api('/api/trace?limit=' + Math.min(60, head.total - LIVE_SEEN));
  if (!t || !t.calls) return;
  const fresh = t.calls.slice(-(t.total - LIVE_SEEN));
  LIVE_SEEN = t.total;
  fresh.forEach(c => pushLive(liveRow(c)));
  const note = $('#live-note');
  if (note) note.textContent = `${t.total} викликів за сеанс`;
}

/* Стрічка показує те, що відбувається ЗАРАЗ, а не переказує історію сеансу.
   Раніше на кожному перезавантаженні вона починала з нуля й по одному рядку
   на пів секунди програвала всі накопичені виклики — сорок рядків це двадцять
   секунд чужого минулого замість того, що робиться цієї миті. */
async function startLive() {
  const t = await api('/api/trace?limit=1');
  LIVE_SEEN = (t && t.total) || 0;
  const note = $('#live-note');
  if (note) note.textContent = 'виклики MCP наживо';
  clearInterval(LIVE_TIMER);
  LIVE_TIMER = setInterval(pumpLive, 900);
}

/* Очищення. Раніше воно скидало лічильник у нуль — і наступне ж опитування
   тягнуло весь трейс назад, тобто кнопка не робила нічого. Тепер зсуваємо
   позицію на поточний кінець: старе зникає назавжди, нове йде далі. */
async function clearLive() {
  const box = $('#livefeed');
  LIVE_QUEUE = [];
  LIVE_ITEMS = [];
  clearInterval(LIVE_DRAIN); LIVE_DRAIN = null;
  const t = await api('/api/trace?limit=1');
  LIVE_SEEN = (t && t.total) || LIVE_SEEN;
  if (box) {
    box.dataset.empty = 'yes';
    box.innerHTML = '<p class="soft">Очищено. Наступний виклик зʼявиться тут.</p>';
  }
}

/* ---------- нижня навігація застосунку ----------
   Одна на всі екрани: із профілю й грибниці теж має бути видно, де ти. */
/* Кошик — окремий екран застосунку, а не бічна панель. На головній нижня
   навігація перемикає вкладку на місці; з інших сторінок веде на головну. */
/* Перехід між екранами з тим самим станом запису: у режимі запису адреса
   несе `?rec`, і профіль чи грибниця відкриваються так само — без шапки. */
function withRec(url) {
  if (!document.body.classList.contains('rec')) return url;
  const u = new URL(url, location.origin);
  u.searchParams.set('rec', document.body.classList.contains('rec-trace') ? 'trace' : '');
  return u.pathname + u.search.replace(/rec=(&|$)/, 'rec$1');
}
function nav(url) { location.href = withRec(url); }
function goTab(name) {
  if (typeof appTab === 'function') return appTab(name);
  nav(name === 'chat' ? '/' : '/?tab=' + name);
}

function appNav(current) {
  // Компанія — обʼєкт у профілі (Профіль → Компанії), а не окрема вкладка.
  const tabs = [
    ['chat', 'Чат', 'chat', "goTab('chat')"],
    ['cart', 'Кошик', 'cart', "goTab('cart')"],
    ['profile', 'Профіль', 'user', "nav('/profile')"],
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

/* Синтез ОКРЕМО від відтворення.

   Раніше текст зʼявлявся одразу, а голос доганяв його через три секунди —
   виглядало так, ніби агент читає власну репліку вголос уже після того, як
   сказав її. Тому спершу готуємо аудіо, і лише тоді показуємо текст: голос і
   рядок мають зʼявитись разом.

   Повертає функцію відтворення або null, якщо озвучувати нема чим. */
async function speechReady(raw) {
  if (!TTS) return null;
  const text = ttsText(raw);
  if (!text) return null;
  ttsStop();                     // нова відповідь перебиває попередню
  if (!TTS_REMOTE) return () => speakLocal(text);
  try {
    // Сирий текст, не почищений: підготовку до вимови робить бекенд —
    // там і числа словами, і наголоси, які вміє лише українська модель.
    const r = await fetch('/api/tts', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text: raw }),
    });
    if (!r.ok) throw new Error('tts ' + r.status);
    const url = URL.createObjectURL(await r.blob());
    return () => {
      TTS_AUDIO = new Audio(url);
      TTS_AUDIO.onended = () => URL.revokeObjectURL(url);
      TTS_AUDIO.play().catch(() => {});
    };
  } catch (e) {
    // Ключ протух, ліміт, мережа — демо не має замовкати через це.
    TTS_REMOTE = false;
    syncTtsBtn();
    return () => speakLocal(text);
  }
}

/* Сумісність: озвучити без очікування (кнопка вмикання, довільний текст). */
async function speak(raw) {
  const play = await speechReady(raw);
  if (play) play();
}

/* ---------- індикатор роботи ----------
   Замість німого «…» — фази, які відповідають РЕАЛЬНИМ етапам: спершу запит,
   потім синтез голосу. Гість бачить, на чому саме агент зараз стоїть. */
const THINK_PHASES = ['Думаю…', 'Дивлюсь у «Сільпо»…', 'Рахую…', 'Майже готово…'];

function thinking(phases) {
  const list = phases || THINK_PHASES;
  bubble('it', list[0], { silent: true });
  let el = $('#log').lastElementChild;
  if (!el.classList.contains('msg')) el = el.querySelector('.msg') || el;   // хід з аватаром
  el.classList.add('thinking');
  let i = 0;
  const timer = setInterval(() => {
    i = (i + 1) % list.length;
    el.textContent = list[i];
  }, 1600);
  const stop = () => { clearInterval(timer); el.classList.remove('thinking'); };
  return {
    el,
    phase(text) { clearInterval(timer); el.textContent = text; },
    async finish(text, { voice = true } = {}) {
      // Текст показуємо ТІЛЬКИ разом із готовим голосом.
      let play = null;
      if (voice && TTS) {
        this.phase('Озвучую…');
        play = await speechReady(text);
      }
      stop();
      el.textContent = text;
      scrollChat();
      if (play) play();
    },
    fail(text) { stop(); el.className = 'msg err'; el.textContent = text; },
  };
}

/* ---------- модалки всередині телефона ----------
   <dialog> живе у верхньому шарі й позиціюється від вікна, а не від рамки
   телефона. Тому кожен showModal() спершу підганяє діалог під прямокутник
   .appframe: сам діалог стає затемненням розміром з екран телефона, а його
   внутрішній блок — карткою знизу, як у мобільному застосунку. */
function fitDialog(d) {
  const frame = document.querySelector('.appframe');
  if (!frame) { delete d.dataset.fit; return; }
  const r = frame.getBoundingClientRect();
  const bw = parseFloat(getComputedStyle(frame).borderLeftWidth) || 0;
  const rad = parseFloat(getComputedStyle(frame).borderTopLeftRadius) || 0;
  Object.assign(d.style, {
    left: (r.left + bw) + 'px', top: (r.top + bw) + 'px',
    width: (r.width - 2 * bw) + 'px', height: (r.height - 2 * bw) + 'px',
    borderRadius: Math.max(0, rad - bw) + 'px',
  });
  d.dataset.fit = '1';
}
if (window.HTMLDialogElement) {
  const showModal = HTMLDialogElement.prototype.showModal;
  HTMLDialogElement.prototype.showModal = function () { fitDialog(this); return showModal.call(this); };
  window.addEventListener('resize', () =>
    document.querySelectorAll('dialog[open]').forEach(fitDialog));
}

/* ---------- модалка зі стеком ----------
   Модалка може відкрити модалку (сімʼя → учасник). Стек дає кнопку «назад»,
   інакше гість вилітає на сторінку й губить контекст. */
let SHEETS = [];
/* `opts.redraw` — імʼя функції, яка вміє перемалювати цю модалку заново.
   Без неї «назад» повертає ЗНІМОК розмітки: список, у якому щойно створили
   запис, повертався порожнім, бо html запамʼятався до створення. */
function sheet(title, sub, html, opts = {}) {
  if (!opts._back) SHEETS.push({ title, sub, html, redraw: opts.redraw });
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
  lockScroll(true);
}

/* Сторінка не має рухатись, поки відкрита модалка. Стежимо за ВСІМА
   діалогами: їх на сторінці кілька (модалка, опитувальник, вибір товару),
   і закриття одного не означає, що можна відпускати скрол. */
function lockScroll(on) {
  const anyOpen = on || !!document.querySelector('dialog[open]');
  document.body.classList.toggle('modal', anyOpen);
}

/* `showModal()` викликається з десятка місць — опитувальники сценаріїв, вибір
   товару, картка виклику. Додавати блокування в кожне означало б забути в
   одному, тож стежимо за атрибутом `open` на будь-якому діалозі. */
new MutationObserver(() => lockScroll(false)).observe(document.documentElement, {
  subtree: true, attributes: true, attributeFilter: ['open'],
});
function sheetBack() {
  SHEETS.pop();
  const prev = SHEETS[SHEETS.length - 1];
  if (!prev) return closeSheet();
  // Модалка, яка вміє перемалюватись, робить це заново — дані могли змінитись.
  if (prev.redraw && typeof window[prev.redraw] === 'function') {
    SHEETS.pop();
    return window[prev.redraw]();
  }
  sheet(prev.title, prev.sub, prev.html, { _back: true });
}
function closeSheet() {
  SHEETS = [];
  document.querySelector('#sheet')?.close();
  lockScroll(false);
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
  // На головному екрані колонки — частина сітки, а не накладка: затемнення
  // там не зʼявляється ніколи, інакше панель сценаріїв блокувала б застосунок
  // рівно тоді, коли треба дивитись, як сценарій іде.
  const overlay = !shell.classList.contains('live') &&
    (window.matchMedia('(max-width:900px)').matches ||
     document.body.classList.contains('mobile'));
  document.querySelector('#scrim')?.classList.toggle('on', open && overlay);
  document.querySelector('#btn-left')?.setAttribute('aria-pressed', shell.classList.contains('l'));

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
/* Клієнтська частина ЗАВЖДИ в рамці телефона. Перемикача вигляду більше немає:
   гість «Сільпо» тримає застосунок у руці, і показувати його розтягнутим на всю
   ширину монітора означало б показувати те, чого не існує. Десктоп лишився
   рівно для «Під капотом» — це екран для команди, не для гостя. */
function setView(mode) {
  document.body.classList.toggle('mobile', mode === 'mobile');
  syncPanels();
}
/* ---------- розмір рамки телефона ----------
   Три змінні в `:root` (`--phone-w`, `--phone-h`, `--phone-h-min`) правляться
   звідси й лягають у localStorage. Пресети — реальні логічні розміри пристроїв
   (CSS-пікселі, не фізичні): саме в них показують демо, і саме на них ламається
   верстка. Ширина задається З РАМКОЮ: box-sizing усюди border-box, тож 10px
   бортика з кожного боку вже в числі. */
const PHONES = [
  { id: 'se',     name: 'iPhone SE',      w: 375, h: 667 },
  { id: 'i15',    name: 'iPhone 15',      w: 393, h: 852 },
  { id: 'pixel',  name: 'Pixel 8',        w: 412, h: 915 },
  { id: 'max',    name: 'iPhone 15 Pro Max', w: 430, h: 932 },
  { id: 'tablet', name: 'Планшет 7"',     w: 600, h: 960 },
];
const PHONE_DEFAULT = { w: 424, h: 0 };   // h:0 — «за висотою вікна», як було

function phoneSize() {
  try {
    const raw = JSON.parse(localStorage.getItem('phone') || 'null');
    if (raw && raw.w) return { w: +raw.w, h: +raw.h || 0 };
  } catch (e) {}
  return { ...PHONE_DEFAULT };
}

/* h === 0 означає «тягнутись за вікном» — початкова поведінка проєкту.
   Тримаємо її окремим випадком, а не магічним числом: інакше на невисокому
   екрані фіксовані 932px вилазять за межі вікна й ріжуться. */
function applyPhoneSize(size) {
  const r = document.documentElement.style;
  r.setProperty('--phone-w', (size.w || PHONE_DEFAULT.w) + 'px');
  r.setProperty('--phone-h', size.h ? `min(${size.h}px, 92vh)` : 'min(80vh,780px)');
  r.setProperty('--phone-h-min', size.h ? '0px' : '560px');
  try { localStorage.setItem('phone', JSON.stringify(size)); } catch (e) {}
}

function openPhoneSize() {
  const s = phoneSize();
  sheet('Розмір телефона',
    'Логічні пікселі пристрою. Ширина — разом із рамкою 10 px з кожного боку', `
    <div class="phones">${PHONES.map(p => `
      <button class="ph ${s.w === p.w && s.h === p.h ? 'on' : ''}"
        onclick="pickPhone(${p.w},${p.h})">
        <b>${p.name}</b><span>${p.w} × ${p.h}</span></button>`).join('')}
      <button class="ph ${s.h ? '' : 'on'}" onclick="pickPhone(424,0)">
        <b>За вікном</b><span>424 × min(80vh, 780)</span></button>
    </div>
    <h3>Або вручну</h3>
    <div class="filters">
      <label style="flex:1">Ширина, px
        <input id="ph-w" type="number" min="280" max="900" step="1" value="${s.w}"></label>
      <label style="flex:1">Висота, px
        <input id="ph-h" type="number" min="0" max="1400" step="1" value="${s.h}"
          placeholder="0 — за вікном"></label>
    </div>
    <p class="soft" style="margin:8px 0 0">Висота <b>0</b> — рамка тягнеться за
      вікном, як було до появи цього налаштування. Будь-яка інша обмежується
      92 % висоти вікна, щоб телефон не вилазив за екран на невисокому моніторі.</p>
    <div class="filters" style="margin-top:12px">
      <button class="go" style="flex:1" onclick="applyPhoneManual()">Застосувати</button>
      <button class="go ghost" onclick="pickPhone(424,0)">Скинути</button></div>`,
    { redraw: 'openPhoneSize' });
}

function pickPhone(w, h) {
  applyPhoneSize({ w, h });
  toast(h ? `${w} × ${h}` : 'Розмір за вікном');
  openPhoneSize();                 // перемальовуємо: активний пресет змінився
}

function applyPhoneManual() {
  const w = Math.max(280, Math.min(900, +($('#ph-w') || {}).value || PHONE_DEFAULT.w));
  const h = Math.max(0, Math.min(1400, +($('#ph-h') || {}).value || 0));
  pickPhone(w, h);
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
      <h2>${p.name}</h2>${
        p.people ? `<div class="soft">на ${p.people} осіб</div>` : ''}</div></div>
    ${dishHtml(p)}
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
    ${p.crew ? `<div class="filters" style="margin-top:10px">
      <button class="fbtn" onclick="crewSuggestAsk()">+ пропозиція</button>
      <button class="fbtn" onclick="crewSplit(${+p.total_uah || 0})">Розділити чек на компанію</button></div>` : ''}
    ${Array.isArray(p.sources) && p.sources.some(s => s.short) ? `<div class="brief">
      ${p.sources.filter(s => s.short).map(s =>
        `<span class="bk">${uiEsc(s.title)}</span><span class="bv">${uiEsc(s.short)}</span>`).join('')}</div>`
    : (p.considered_allergies || []).length ? `<div class="soft" style="margin-top:8px">
      Враховано алергії: ${p.considered_allergies.map(a =>
        `<b>${uiEsc(a.term)}</b> (${uiEsc((a.who || []).join(', '))})`).join(', ')}</div>` : ''}
    <div id="offers"></div>
    <button class="go tocart" onclick="toCart()">У кошик</button>`;
}

/* Страва над кошиком: що готуємо, чому саме це, і що відхилено — з іменем.
   «Збери вечерю» — це відповідь на «що готуємо», а не список продуктів. */
function dishHtml(p) {
  const d = p.dish; if (!d) return '';
  const rej = (p.dishes_rejected || []).filter(r => r.reason === 'алергія');
  const other = p.dishes_other || [];
  return `<div class="dish">
    <div class="dt"><b>${uiEsc(d.title)}</b>
      <span class="soft">${d.minutes ? d.minutes + ' хв · ' : ''}на ${d.for_people || d.serves}${
        d.scale > 1 ? ` (рецепт ×${d.scale})` : ''}</span></div>
    ${(d.why || []).length ? `<ul class="dwhy">${d.why.map(w => `<li>${uiEsc(w)}</li>`).join('')}</ul>` : ''}
    ${rej.length ? `<div class="drej">Відхилено: ${rej.map(r =>
      `<b>${uiEsc(r.title)}</b> — ${uiEsc(r.item)} (${uiEsc((r.who || []).join(', ') || 'алергія')})`).join('; ')}</div>` : ''}
    ${other.length ? `<div class="dalt">Або: ${other.map(o =>
      `<button class="link" onclick="familyDinner('${uiEsc(o.title).replace(/'/g, '')}')">${uiEsc(o.title)}</button>`).join(' · ')}</div>` : ''}
  </div>`;
}

/* Пак у стрічку чату. Попередній пак згортаємо до рядка — історія лишається
   читаною, а на екрані завжди один розгорнутий набір. */
function renderPack(p) {
  if (!p || p.error) return;
  const log = $('#log');
  if (log) {
    // Попередній набір зникає мовчки: два паки з живими кнопками в одній
    // розмові плутають, а службовий рядок про заміну нічого не додавав.
    log.querySelectorAll('.packmsg').forEach(el => el.remove());
    log.insertAdjacentHTML('beforeend',
      `<div class="packmsg" data-name="${p.name}" data-total="${uah(p.total_uah)}">
         ${packHtml(p)}<div class="alerts" id="alerts"></div></div>`);
    scrollChat();
    // `const` на верхньому рівні скрипта не стає властивістю window, тому
    // перевіряємо typeof, а не window.QUICKS_PACK.
    const quicks = $('#quicks');
    if (quicks && typeof QUICKS_PACK !== 'undefined')
      quicks.innerHTML = QUICKS_PACK(p).map(q =>
        `<button onclick="quick('${q}')">${q}</button>`).join('');
  } else {
    const box = $('#pack');
    if (box) box.innerHTML = packHtml(p);
  }
  // payment() тут не потрібен: підказку про оплату малює вкладка «Кошик»,
  // коли її відкривають, а зайве читання кошика лише шумить у стрічці.
  screenAllergens(); OFFERS_READY = showOffers(p);
}
/* showOffers перемальовує #offers цілком; примітка «У кошику…» від toCart,
   що встигла раніше, зникала разом із ним. Тому toCart чекає на знижки. */
let OFFERS_READY = Promise.resolve();

async function openPack(id) { renderPack(await api('/api/pack?pack_id=' + id)); }

/* Ціль для вердикт-екранів: доставка, вага, комора, родина, компанія.
   Раніше вони писали просто в `$('#pack')` — контейнер, який зник, коли пак
   переїхав у стрічку чату. Виклик падав із «Cannot set properties of null»,
   і сценарій тихо не показував НІЧОГО: ані результату, ані помилки.
   Слот повертає ціль, яка існує завжди: у чаті це нове повідомлення, поза
   чатом — старий контейнер, якщо сторінка його має. */
/* Прокрутка розмови до останнього. Скролиться не #log, а вкладка навколо
   нього (#tab-chat має overflow) — тому пряме `#log.scrollTop` мовчки не
   робило нічого, і нова картка зʼявлялась під згином екрана. */
/* Показуємо ПОЧАТОК нового: коротка бульбашка — унизу цілком, а висока
   картка (пак зі стравою й товарами) — від свого верху, а не від кінця:
   інакше після «Все правильно» екран відлітав до кнопки «У кошик», і сама
   страва лишалась за кадром. `target` — що саме показати; без нього —
   останній елемент стрічки. */
function scrollChat(target) {
  const log = $('#log');
  if (!log) return;
  const box = log.closest('.appbody') || log;
  const el = target || log.lastElementChild;
  requestAnimationFrame(() => {
    if (!el) return box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
    const boxRect = box.getBoundingClientRect(), r = el.getBoundingClientRect();
    const top = box.scrollTop + (r.top - boxRect.top);
    const fits = r.height <= box.clientHeight - 16;
    box.scrollTo({ top: fits ? top + r.height - box.clientHeight + 12 : top - 8, behavior: 'smooth' });
  });
}
function packSlot() {
  const box = $('#pack');
  if (box) return box;
  const log = $('#log');
  if (!log) return { set innerHTML(_) {} };
  return {
    set innerHTML(html) {
      log.insertAdjacentHTML('beforeend', `<div class="panelmsg">${html}</div>`);
      scrollChat();
    },
  };
}

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
  const sure = (p.applies_to || []).some(h => h.confidence === 'точний');
  return `<div class="ticket${p.selected ? ' on' : ''}">
    <div class="val" style="background:${TICKET[i % TICKET.length]}">${
      (p.reward || '').replace(/[^0-9]/g, '') || '%'}</div>
    <div class="txt">${p.text}<small>${hits || p.reward || ''}${
      p.selected && !sure ? ' · збіг за типом товару — перевір бренд' : ''}</small></div>
    <div class="end">${p.selected ? '✓' : '+'}</div></div>`;
}
/* Знижки застосовуються до кожного пака самі: купони спрацюють на касі, а
   промо, які лягають на кошик, агент обирає одразу. Кнопки «Знижки» немає —
   промокод, про який треба згадати й натиснути, і є та сама проблема з
   другого слайда. Пак родини приносить розрахунок із собою; решта — доганяє. */
async function showOffers(p) {
  const box = $('#offers'); if (!box) return;
  const o = p && p.offers ? p.offers
    : await api('/api/pack/optimize', 'POST', { pack_id: (p || PACK).id });
  if (!o || o.error) return;
  const multi = (o.multibuy || []).map(m =>
    `<div class="note" style="margin:7px 0"><b>−${uah(m.saving_uah)} ₴</b> ${m.name}<br>
      <span class="soft">${m.text} · доплата ${uah(m.extra_cost_uah)} ₴</span></div>`).join('');
  const promos = o.activate_promos || [];
  const chosen = promos.filter(x => x.selected);
  const rest = promos.filter(x => !x.selected);
  if (!multi && !(o.coupons || []).length && !promos.length) return;
  box.innerHTML = `
    <h3>Знижки на цей пак</h3>${multi}
    ${(o.coupons || []).map((c, i) => ticket({ reward: c.reward, text: c.text,
        applies_to: c.applies_to, selected: true }, i + 3)).join('')}
    ${chosen.map((x, i) => ticket(x, i)).join('')}
    ${rest.length ? `<details class="packwhy"><summary>ще ${rest.length} промо не про цей кошик</summary>
      ${rest.map((x, i) => ticket(x, i + chosen.length)).join('')}</details>` : ''}`;
}
async function toCart() {
  toast('Кладу в кошик…');
  const r = await api('/api/pack/to_cart', 'POST', { pack_id: PACK.id });
  if (bad(r)) return;
  await Promise.resolve(OFFERS_READY).catch(() => {});
  // Окремої картки «У кошику N із N» немає — вона дублювала вкладку «Кошик».
  // Замість неї одразу відкриваємо сам кошик: те, що не потрапило, видно там.
  const dropped = (r.not_added || []).length;
  toast(dropped ? `У кошику ${r.in_cart} із ${r.requested} — ${dropped} не потрапило` : 'Покладено в кошик');
  suggestAlso();
  goTab('cart');
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
        <span class="soft">×${a.times}</span></button>`).join('')}</div>`);
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
  reorder:  { path: '/api/pack/reorder', body: {} },
  // repeat — «Як завжди» Машрум уже вміє, і чеки він бачить. Ендпоінт живий:
  // ним працює «Повторити як пак» на картці чека в профілі.
  // repeat:   { path: '/api/pack/from_receipt', body: { index: 0 } },
  pantry:   { path: '/api/pantry/missing', method: 'GET' },
  wellbeing:{ path: '/api/wellbeing', wellbeing: true },
  weekly:   { path: '/api/pack/weekly', ask: 'weekly', novelty: true },
  // budget — кошик під суму Машрум збирає й сам, персональних даних це не
  // потребує. Ендпоінт живий, картку знято.
  // budget:   { path: '/api/pack/budget', ask: 'budget', novelty: true },

  mood:     { path: '/api/pack/mood', quiz: 'mood', novelty: true },
  kids:     { path: '/api/pack/kids', ask: 'kids' },
  family:   { path: '/api/family', method: 'GET' },
  crew:     { path: '/api/crew', method: 'GET' },
  heirloom: { path: '/api/family/recipes', method: 'GET' },

  precheck: { path: '/api/pack/precheck', needsPack: true },
  geo:      { path: '/api/delivery', geo: true },
  weight:   { path: '/api/weight', method: 'GET' },

  // meal — рецепти Машрум робить добре, і база в «Сільпо» вже є; tool живий,
  // картки немає. Сценарії, зняті зовсім, описані в silpo_agent_mcp/flows.py.
};

/* Аналітика: відповідь — одне число, а не пак. */
const INSIGHT_HANDLERS = {
  coupons:  { path: '/api/coupons/audit' },
  savings:  { path: '/api/savings' },
  spend:    { path: '/api/spend' },
  plus:     { path: '/api/plus' },
  risk:     { path: '/api/risk', method: 'POST' },
  impulse:  { path: '/api/impulse', ask: 'impulse' },
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
  // Ланцюг «що всередині» лежить у самій картці, але згорнутим: розгорнутий
  // він перетворює панель на простирадло, а згорнутий — доступний за один
  // клік, не змушуючи йти в «Під капотом». Джерело те саме — /api/flows.
  const kindDot = { real: 'var(--green)', proposed: '#7A46D6', ours: 'var(--amber)' };
  const card = s => `
    <div class="scn" id="scn-${s.id}">
      <div class="top"><b>${s.title}${s.new ? '<span class="isnew">нове</span>' : ''}</b>
        <button class="run" onclick="runScenario('${s.id}')">Запустити</button></div>
      <div class="phrase">«${s.phrase}»</div>
      <div class="tools">${s.tools.map(t => `
        <span class="tchip ${t.endsWith('*') ? 'prop' : ''}" data-tool="${t.replace('*','')}"
          >${t.replace('silpo_','').replace('*','')}${t.endsWith('*') ? ' ⁺' : ''}</span>`).join('<i class="tarr">→</i>')}</div>
      <details class="inside">
        <summary>що всередині · ${(s.steps || []).length} кроків</summary>
        <div class="isteps">
          ${(s.steps || []).map(st => `<div class="istep">
            <i style="background:${kindDot[st.kind] || 'var(--blue)'}"></i>
            <span><code>${uiEsc(st.tool)}</code>
              <span class="nt">${uiEsc(st.note)}</span></span></div>`).join('')}
          <div class="istep res"><i style="background:var(--blue)"></i>
            <span><b>Результат</b><span class="nt">${uiEsc(s.result || '')}</span></span></div>
        </div>
      </details>
      <div class="live" id="live-${s.id}" hidden></div>
    </div>`;
  into.innerHTML = (FLOWS.groups || [])
    .filter(g => SCENARIOS.some(s => s.group === g.id))
    .map((g, i) => {
      const rows = SCENARIOS.filter(s => s.group === g.id);
      // Розгорнута перша група — і будь-яка, де є новий сценарій: інакше
      // свіжу картку просто не знайти під згорнутою назвою групи.
      const open = i === 0 || rows.some(s => s.new);
      return `<details class="grp" ${open ? 'open' : ''}>
        <summary><b>${g.title}</b><span>${rows.length} · ${g.about}</span></summary>
        ${rows.map(card).join('')}</details>`;
    }).join('')
    + `<p class="soft" style="margin:10px 0 0">⁺ — tool, якого в MCP «Сільпо» ще немає.
       Ми його реалізували в себе, щоб сценарій працював, і пропонуємо додати.</p>`;
}

/* Живий ланцюг: опитуємо трейс і показуємо виклики в міру того, як вони йдуть.
   Чипи підсвічуються ПО ЧЕРЗІ з паузою: половина викликів відпрацьовує за
   мілісекунду, і без паузи весь ланцюг спалахував разом — а сенс саме в
   тому, щоб було видно, що за чим іде. */
const CHIP_GAP = 420;
async function watchChain(id, sinceTotal) {
  const box = $('#live-' + id);
  box.hidden = false;
  const card = $('#scn-' + id);
  const lit = new Set();
  let due = 0;
  const light = tool => {
    if (lit.has(tool)) return;
    lit.add(tool);
    const chip = card.querySelector(`[data-tool="${tool}"]`);
    if (!chip) return;
    due = Math.max(due, Date.now()) + CHIP_GAP;
    setTimeout(() => chip.classList.add('on'), due - Date.now() - CHIP_GAP);
  };
  const tick = async () => {
    const t = await api('/api/trace?limit=40');
    const fresh = t.total > sinceTotal ? t.calls.slice(-(t.total - sinceTotal)) : [];
    box.innerHTML = fresh.map(c => `
      <div class="row ${c.kind === 'proposed' ? 'prop' : ''}">
        <span class="nm">${c.tool.replace('silpo_', '')}${c.kind === 'proposed' ? ' ⁺' : ''}</span>
        <span class="ms">${c.ms} ms</span></div>`).join('')
      || '<div class="row"><span class="spin">запит пішов…</span></div>';
    fresh.forEach(c => light(c.tool));
  };
  await tick();
  CHAIN_TIMER = setInterval(tick, 450);
  return () => { clearInterval(CHAIN_TIMER); tick(); };
}

async function runScenario(id, extraBody) {
  const s = SCENARIOS.find(x => x.id === id);
  // Компанію обирають у профілі, а кошик збирається тут: id приїжджає в адресі.
  if (id === 'crew' && CREW_ID && !extraBody) extraBody = { crew_id: CREW_ID };
  if (s.quiz && !extraBody) return openQuiz(s);
  if (s.ask === 'meal' && !extraBody) return askMeal(s);
  if (s.geo && !extraBody) return askGeo(s);
  if (s.wellbeing && !extraBody) return askWellbeing(s);
  if (s.ask && ASKS[s.ask] && !extraBody) return ASKS[s.ask](s);
  // Новизна — окреме питання, і воно йде ПІСЛЯ теми: спершу «що», потім «яке».
  if (s.novelty && !(extraBody || {}).novelty) return askNovelty(s, extraBody || {});
  if (s.needsPack && !PACK) return toast('Спершу збери пак — сценарій будується під нього');
  if (s.needsPack) extraBody = { ...(extraBody || {}), pack_id: PACK.id };
  // if (s.id === 'route' && !extraBody)
  //   extraBody = { items: PACK.items.map(i => ({ name: i.name })), branch_id: PACK.branch || null };

  liveGroup(s.title);
  $('#scn-' + id).querySelectorAll('.tchip').forEach(c => c.classList.remove('on'));
  // Фраза гостя — одразу, як у розмові; відповідь доганяє. Доти вона
  // зʼявлялась разом із результатом, і кілька секунд екран мовчав.
  const said = MODE !== 'llm' && typeof bubble === 'function' && !!s.phrase;
  if (said) bubble('me', s.phrase);
  const before = (await api('/api/trace?limit=1')).total;
  const stop = await watchChain(id, before);

  // Сценарій ЗАВЖДИ виконується тим самим MCP-викликом — і від кнопки, і
  // «через модель». Тому обидва режими дають рівно той самий пак; модель у
  // другому режимі лише переказує готовий результат людською мовою.
  const result = await callScenario(s, extraBody);
  stop();
  if (MODE === 'llm') return narrateResult(s, result);
  handleResult(s, result, { quiet: said });
}

/* «Через модель»: агент СПЕРШУ відповідає, і лише тоді показує пак.
   Раніше було навпаки — пак випадав одразу, а «…» зʼявлялось під ним, і
   виглядало так, ніби модель коментує те, що вже й так на екрані. Порядок у
   розмові має бути як у розмові: питання → думаю → відповідь → набір. */
async function narrateResult(s, result) {
  bubble('me', s.phrase);
  if (!result || result.error) {
    bubble('it', 'Сценарій не виконався — дивись повідомлення про помилку.');
    return handleResult(s, result);
  }

  if (typeof liveStep === 'function') liveStep(`сценарій «${s.title}» виконано`);

  // Модель озвучує лише ПАК. У вердикт-екранів (вага, ризик збирання,
  // доставка) немає ні сум, ні позицій — модель їх просто вигадує.
  const isPack = result.item_count != null || Array.isArray(result.items);
  if (!isPack) {
    bubble('it', result.verdict || result.headline || 'Готово — дивись картку нижче.');
    return handleResult(s, result, { quiet: true });
  }

  const t = thinking(['Думаю…', 'Формулюю відповідь…', 'Майже готово…']);
  liveStep('локальна модель переказує результат…');
  let n;
  try {
    n = await api('/api/chat/narrate', 'POST',
      { phrase: s.phrase, tool: (s.tools?.[0] || '').replace('*', ''), result });
  } catch (e) {
    n = { error: String((e && e.message) || e) };
  }
  if (n && n.reply && n.model) {
    liveStep(`${n.model}: ${n.reply}`, 'llm');
    await t.finish(n.reply);         // ШІ справді озвучив
  } else {
    liveStep((n && n.error) || 'ШІ не відповів', 'bad');
    // «…» обіцяє, що ШІ викликано. Не справдилось — кажемо це прямо,
    // а не підсовуємо детермінований рядок замість моделі.
    const msg = (n && n.error) || 'ШІ не відповів';
    t.fail(msg);
    if (n && n.hint) bubble('tools', n.hint);
    toast(msg);
  }
  handleResult(s, result, { quiet: true });   // пак — після відповіді
}

async function callScenario(s, extraBody) {
  const body = { ...(s.body || {}), ...(extraBody || {}) };
  return s.method === 'GET' ? api(s.path) : api(s.path, 'POST', body);
}

function handleResult(s, r, opts = {}) {
  if (bad(r)) return;
  // Кнопка сценарію — це та сама фраза: лишаємо її в розмові, щоб історія
  // читалась однаково, звідки б не прийшов запит. `quiet` — коли ці рядки
  // вже виведені раніше (режим «через модель» ставить їх до відповіді).
  // Назв методів у телефоні немає: це екран гостя, а ланцюг викликів живе
  // в панелі «Що відбувається» праворуч.
  if (!opts.quiet && typeof bubble === 'function' && s.phrase && MODE !== 'llm')
    bubble('me', s.phrase);
  if (r.items) { renderPack(r); return; }
  if (s.id === 'geo') return renderDelivery(r);
  if (s.id === 'pantry') return renderPantry(r);
  if (s.id === 'family') return renderFamily(r);
  if (s.id === 'crew') return renderCrew(r);
  if (s.id === 'wellbeing') return renderWellbeing(r);
  if (s.id === 'weight') return renderWeight(r);
  if (s.id === 'precheck') return renderPrecheck(r);
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
  // Гостю важливі два способи: дійти або замовити додому. Бізнес-доставку
  // й розширений асортимент ховаємо під «ще» — це не про «топати чи замовити».
  const main = r.options.filter(o => o.delivery_type === 'SelfPickup' || o.delivery_type === 'DeliveryHome');
  const rest = r.options.filter(o => !main.includes(o));
  const way = o => `<div class="way ${o.meets_minimum ? '' : 'short'}">
      <div class="wtop">
        <b>${uiEsc(o.label || o.delivery_type)}</b>
        <span class="cost">${o.cost_uah ? uah(o.cost_uah) + ' ₴' : 'безкоштовно'}</span></div>
      <div class="wmeta">${uiEsc(o.branch || 'хаб доставки')}${
        o.distance_km != null ? ` · ${o.distance_km} км` : ''}${
        o.walk_minutes != null ? ` · пішки ${o.walk_minutes} хв` : ''}</div>
      <div class="wmeta">${o.slot ? 'слот ' + o.slot : 'слот не вказано'}${
        o.min_order_uah ? ` · мінімум ${uah(o.min_order_uah)} ₴` : ''}</div>
      ${o.meets_minimum === false
        ? '<div class="wnote bad">кошик не дотягує до мінімуму</div>' : ''}
      ${o.next_tier ? `<div class="wnote">добери ${uah(o.next_tier.need_more_uah)} ₴ —
        і доставка коштуватиме ${uah(o.next_tier.cost_uah)} ₴</div>` : ''}
    </div>`;
  packSlot().innerHTML = `
    <h2>Топати чи замовити</h2>
    <p class="soft" style="margin:0 0 12px">${r.within_radius} магазин${r.within_radius === 1 ? '' : 'и'} у радіусі ${String(r.radius_km).replace('.', ',')} км</p>
    <div class="ways">${(main.length ? main : r.options).map(way).join('')}</div>
    ${main.length && rest.length ? `<details class="packwhy" style="margin-top:8px">
      <summary>ще ${rest.length} способ${rest.length === 1 ? '' : 'и'}</summary>
      <div class="ways" style="margin-top:8px">${rest.map(way).join('')}</div></details>` : ''}`;
}
function renderPantry(r) {
  packSlot().innerHTML = `
    <h2>Чого немає вдома</h2>
    <p class="soft" style="margin:0 0 12px">Джерело інвентарю: ${r.pantry_source || 'ще не синхронізовано'}
      ${r.pantry_at ? '· ' + r.pantry_at : ''}</p>
    ${r.missing?.length ? r.missing.map(m => `<div class="habit"><b>${m.name}</b>
      береш кожні ~${m.cycle_days} дн., минуло ${m.days_since}</div>`).join('')
      : '<p class="muted">Усе на місці.</p>'}
    <button class="go" style="margin-top:12px" onclick="runScenario('reorder')">Зібрати пак із цього</button>
    <div class="note" style="margin-top:12px">${r.spec}</div>`;
}
let FAMILY_SNAPSHOT = null;
function renderFamily(r) {
  // Склад показуємо не «для інформації», а щоб підтвердити або виправити:
  // «Все правильно» збирає вечерю без повторного читання родини (бекенд
  // тримає щойно прочитане), «Змінити» пише в профіль тим самим tool, яким
  // користується форма в профілі.
  FAMILY_SNAPSHOT = r;
  const line = m => `${(m.likes || []).length ? 'любить: ' + uiEsc(m.likes.join(', ')) : 'смаків не вказано'} ·
    не можна: ${(m.allergies || []).length ? `<span style="color:var(--red)">${uiEsc(m.allergies.join(', '))}</span>` : '—'}`;
  packSlot().innerHTML = `
    <h2>Хто вечеряє</h2>
    ${r.members.map(m => `<div class="habit"><b>${uiEsc(m.name)} <span class="soft">· ${m.role}${
      m.age ? ', ' + m.age + ' р.' : ''}</span></b>${line(m)}</div>`).join('')}
    ${r.pets.map(p => `<div class="habit"><b>${uiEsc(p.name)} <span class="soft">· ${uiEsc(p.kind || '')}</span></b>
      корм додасться сам</div>`).join('')}
    <div class="filters" style="margin-top:12px">
      <button class="go" onclick="familyDinner()">Все правильно →</button>
      <button class="fbtn" onclick="familyEdit()">Змінити</button></div>`;
}
function familyEdit() {
  const r = FAMILY_SNAPSHOT; if (!r) return;
  packSlot().innerHTML = `
    <h2>Хто вечеряє</h2>
    <p class="soft" style="margin:0 0 10px">Що зміниш — запишеться в профіль</p>
    ${r.members.map((m, i) => `<div class="habit fedit" data-i="${i}">
      <input class="f-name" value="${uiEsc(m.name === 'без імені' ? '' : m.name)}" placeholder="імʼя">
      <input class="f-likes" value="${uiEsc((m.likes || []).join(', '))}" placeholder="любить: паста, суші">
      <input class="f-all" value="${uiEsc((m.allergies || []).join(', '))}" placeholder="не можна: арахіс"></div>`).join('')}
    <div class="filters" style="margin-top:12px">
      <button class="go" onclick="familySave()">Зберегти й зібрати →</button>
      <button class="fbtn" onclick="renderFamily(FAMILY_SNAPSHOT)">Назад</button></div>`;
}
async function familySave() {
  const r = FAMILY_SNAPSHOT; if (!r) return;
  const csv = v => v.split(',').map(x => x.trim()).filter(Boolean);
  const rows = [...document.querySelectorAll('.fedit')];
  let changed = 0;
  for (const el of rows) {
    const m = r.members[+el.dataset.i];
    const name = el.querySelector('.f-name').value.trim();
    const likes = csv(el.querySelector('.f-likes').value);
    const allergies = csv(el.querySelector('.f-all').value);
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    if ((name || 'без імені') === m.name && same(likes, m.likes || []) && same(allergies, m.allergies || []))
      continue;
    await api('/api/family/member', 'POST', { member_id: m.id, name: name || null, likes, allergies });
    changed++;
  }
  toast(changed ? `Записав у профіль: ${changed}` : 'Нічого не змінилось');
  familyDinner();
}
async function familyDinner(dish){
  toast(dish ? `Збираю під «${dish}»…` : 'Обираю страву на всіх…');
  // 1500 ₴ — не кругле число заради краси: джерела беруть з бюджету по
  // черзі, і на 900 ₴ хвіст черги (напої до столу, кава) просто не влазив.
  const p = await api('/api/pack/family', 'POST', { theme: 'вечеря', max_uah: 1500,
    ...(dish ? { dish } : {}) });
  if (bad(p)) return;
  renderPack(p);
  if ((p.blocked_for_everyone || []).length)
    toast('Виключив для всіх: ' + p.blocked_for_everyone.join(', '));
}
/* ===================== компанія ===================== */
/* Новий концепт: разова група під подію. Не плутати з «сімейною групою»
   «Сільпо» — там сталий звʼязок акаунтів зі спільними бонусами, тут вечір.
   Учасники, їхні обмеження й пропозиції живуть у нашому сховищі, бо в MCP
   для цього немає жодної точки входу. */
let CREW = null;
/* Компанію відкривають із профілю: /?crew=crew-2. Далі всі виклики цієї
   сесії йдуть саме під неї, а не під «останню створену». */
const CREW_ID = new URLSearchParams(location.search).get('crew');

/* Запрошення: посилання на /join?crew=… і QR із нього. Хост — той, з якого
   відкрито сторінку, тож із ноутбука в локальній мережі гість читає код
   телефоном і справді додає себе. У живому продукті це deep link у
   застосунок «Сільпо». */
const joinUrl = c => `${location.origin}/join?crew=${encodeURIComponent(c.id)}`;
function inviteHtml(c) {
  const url = joinUrl(c);
  return `<div class="invite">
    <img class="qr" src="/qr?text=${encodeURIComponent(url)}" alt="QR запрошення" width="118" height="118">
    <div class="it">
      <b>Покликати в компанію</b>
      <a class="lnk" href="${url}" target="_blank" rel="noopener">${url.replace(/^https?:\/\//, '')}</a>
      <button class="fbtn" onclick="copyText('${url}')">Скопіювати посилання</button>
    </div></div>`;
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); toast('Скопійовано'); }
  catch (e) { toast('Не вдалося скопіювати — виділи текст руками'); }
}

/* Пропозиція з чату: «зберемось компанією на пікнік» → створити «Пікнік»?
   Нічого не створюється без натискання — це вибір людини, не агента. */
function renderCrewProposal(pr) {
  packSlot().innerHTML = `
    <h2>Зберемо компанію «${uiEsc(pr.title)}»?</h2>
    <p class="soft">Разова група під ${uiEsc(pr.occasion)}: кожен додасть свої алергії й
      побажання зі свого телефона — за посиланням або QR — а кошик буде один.</p>
    <div class="filters" style="margin-top:10px">
      <button class="go" onclick="crewCreateFromChat('${uiEsc(pr.title)}','${uiEsc(pr.occasion)}')">Створити компанію</button>
      <button class="fbtn" onclick="bubble('it','Гаразд, без компанії.',{silent:true})">Не треба</button></div>`;
}
async function crewShow(id) { renderCrew(await api('/api/crew?crew_id=' + encodeURIComponent(id))); }
async function crewCreateFromChat(title, occasion) {
  const r = await api('/api/crew/create', 'POST', { title, occasion, demo: true });
  if (bad(r)) return;
  bubble('it', `Компанію «${title}» створено. Ось посилання й QR — кидай у чат компанії.`, { silent: true });
  renderCrew(await api('/api/crew?crew_id=' + encodeURIComponent(r.crew.id)));
  const quicks = $('#quicks');
  if (quicks) quicks.innerHTML = [
    `Запропонуй в компанію з імʼям ${title} закупку на ${occasion}`,
  ].map(q => `<button onclick="quick('${q.replace(/'/g, 'ʼ')}')">${q}</button>`).join('');
}

/* Одна розмітка на чат і на вкладку «Компанія»: люди, обмеження,
   пропозиції, запрошення, кнопки. */
function crewHtml(r) {
  const c = r.crew, mem = r.members || [];
  const blocked = r.blocked_for_everyone || [];
  const diets = r.diets || [];
  return `
    <h2>${uiEsc(c.title)} <span class="soft">· ${mem.length} осіб</span></h2>
    ${inviteHtml(c)}
    ${blocked.length ? `<div class="warn" style="margin:8px 0">
      Виключено для всієї компанії: <b>${uiEsc(blocked.join(', '))}</b></div>` : ''}
    ${diets.length ? `<div class="dietbar">Дієти: <b>${
      diets.map(d => `${uiEsc(d.term)} (${uiEsc(d.who)})`).join(' · ')}</b></div>` : ''}

    ${mem.map((m, i) => `<div class="habit">
      <b>${uiEsc(m.name)} <span class="soft">· ${uiEsc(m.role || 'гість')}</span></b>
      <div>${(m.allergies || []).length
        ? `<span style="color:var(--red)">алергія: ${uiEsc((m.allergies || []).join(', '))}</span>`
        : '<span class="soft">алергій не вказав</span>'}${
        (m.diets || []).length ? ' · ' + uiEsc((m.diets || []).join(', ')) : ''}</div>
      <div class="chips" style="margin-top:5px">${
        (m.suggests || []).map(x => `<span class="tag">${uiEsc(x)}</span>`).join('')
        || '<span class="soft">нічого не запропонував</span>'}</div>
      <div class="soft" style="margin-top:4px">заплатив: ${(+m.paid_uah || 0).toFixed(2)} ₴
        · <a href="#" onclick="crewPaidAsk(${i});return false">змінити</a>
        · <a href="#" onclick="crewLeave(${i});return false">прибрати</a></div>
    </div>`).join('')}

    <div class="filters" style="margin-top:12px">
      <button class="fbtn" onclick="crewJoinAsk()">+ учасник</button>
      <button class="fbtn" onclick="nav('/profile?crew=${encodeURIComponent(c.id)}')">Відкрити в профілі →</button>
    </div>
    <button class="go" style="margin-top:10px;width:100%" onclick="crewPack()">
      Зібрати кошик компанії</button>`;
}

function renderCrew(r) {
  CREW = r && r.crew ? r : null;
  if (!CREW) return renderCrewEmpty(r);
  packSlot().innerHTML = crewHtml(CREW);
}


function renderCrewEmpty(r) {
  packSlot().innerHTML = `
    <h2>Компанія</h2>
    <p class="soft">${(r && r.hint) || 'Компанії ще немає.'}</p>
    <p class="soft">Разова група під подію: кожен додає свої алергії й свої
      пропозиції, а кошик виходить один. Це <b>не</b> «сімейна група» —
      звʼязувати акаунти назавжди заради одного пікніка ніхто не буде.</p>
    <div class="filters" style="margin-top:12px">
      <input id="cr-title" value="Пікнік на Трухановому" placeholder="назва">
      <input id="cr-occ" value="пікнік" placeholder="привід" style="max-width:150px"></div>
    <button class="go" style="margin-top:10px" onclick="crewCreate()">Створити компанію</button>`;
}

async function crewCreate() {
  const title = ($('#cr-title') || {}).value || 'Компанія';
  const occasion = ($('#cr-occ') || {}).value || 'пікнік';
  const r = await api('/api/crew/create', 'POST', { title, occasion, demo: true });
  if (bad(r)) return;
  toast('Компанію створено');
  renderCrew(await api('/api/crew'));
}

/* Id відкритої компанії: з адреси, інакше з того, що вже показано. */
const crewId = () => CREW_ID || (CREW && CREW.crew && CREW.crew.id)
  || (PACK && PACK.crew && PACK.crew.id) || null;
const crewMembers = () => (CREW && CREW.members) || (PACK && PACK.crew && PACK.crew.members) || [];

async function crewReload() {
  const id = crewId();
  const r = await api('/api/crew' + (id ? '?crew_id=' + encodeURIComponent(id) : ''));
  CREW = r && r.crew ? r : null;
  if (!CREW) return renderCrewEmpty(r);
  if (PACK && PACK.crew) PACK.crew.members = CREW.members;
  // Оновлюємо картку, що вже в розмові, а не додаємо ще одну.
  const last = [...document.querySelectorAll('#log .panelmsg')].reverse()
    .find(el => el.querySelector('.invite'));
  if (last) last.innerHTML = crewHtml(CREW); else packSlot().innerHTML = crewHtml(CREW);
}

function crewJoinAsk() {
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Хто ще з нами</h2>
    <div class="soft">Кожен каже про себе сам. Зараз ці дані тримає в голові
      організатор — і саме так хтось отримує горіхи в салаті.</div>
    <h3>Імʼя</h3>
    <div class="filters"><input id="cj-name" placeholder="Наприклад, Оксана"></div>
    <h3>Алергії та дієти</h3>
    <div class="filters"><input id="cj-alg" placeholder="через кому: горіхи, мед">
      <input id="cj-diet" placeholder="без лактози" style="max-width:170px"></div>
    <h3>Що пропонує взяти</h3>
    <div class="filters"><input id="cj-sug" placeholder="через кому: сир, виноград"></div>
    <button class="go" style="width:100%;margin-top:12px" onclick="crewJoin()">Додати</button>`;
  quiz.showModal();
}

const crewCsv = id => (($('#' + id) || {}).value || '')
  .split(',').map(x => x.trim()).filter(Boolean);

async function crewJoin() {
  const name = (($('#cj-name') || {}).value || '').trim();
  if (!name) return toast('Без імені не додам');
  quiz.close();
  const r = await api('/api/crew/join', 'POST', { crew_id: crewId(), name,
    allergies: crewCsv('cj-alg'), diets: crewCsv('cj-diet'), suggests: crewCsv('cj-sug') });
  if (bad(r)) return;
  toast(name + ' у компанії');
  crewReload();
}

function crewSuggestAsk() {
  const names = crewMembers().map(m => m.name);
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Докинути в список</h2>
    <h3>Від кого</h3>
    <div class="filters"><select id="cs-who">${
      names.map(n => `<option>${uiEsc(n)}</option>`).join('')}</select></div>
    <h3>Що саме</h3>
    <div class="filters"><input id="cs-items" placeholder="через кому: гірчиця, кетчуп"></div>
    <button class="go" style="width:100%;margin-top:12px" onclick="crewSuggest()">Докинути</button>`;
  quiz.showModal();
}

async function crewSuggest() {
  const name = (($('#cs-who') || {}).value || '').trim();
  const items = crewCsv('cs-items');
  if (!items.length) return toast('Порожньо');
  quiz.close();
  const r = await api('/api/crew/suggest', 'POST', { crew_id: crewId(), name, items });
  if (bad(r)) return;
  toast(`${name}: +${(r.added || []).length}`);
  // Пропозиція після зібраного кошика — кошик перезбирається з нею.
  if (PACK && PACK.crew) return crewPack();
  crewReload();
}

async function crewLeave(i) {
  const m = (CREW.members || [])[i];
  if (!m) return;
  const r = await api('/api/crew/leave', 'POST', { crew_id: crewId(), name: m.name });
  if (bad(r)) return;
  toast(m.name + ' більше не в компанії');
  crewReload();
}

function crewPaidAsk(i) {
  const m = (CREW.members || [])[i];
  if (!m) return;
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 2px">Скільки заплатив ${uiEsc(m.name)}</h2>
    <div class="soft">Це вхід для розрахунку. Хто платив на касі, хто скидався
      наперед — до кошика це відношення має, а до чека вже ні.</div>
    <div class="filters" style="margin-top:12px">
      <input id="cp-sum" type="number" value="${+m.paid_uah || 0}" step="10"></div>
    <button class="go" style="width:100%;margin-top:12px"
      onclick="crewPaid(${i})">Зберегти</button>`;
  quiz.showModal();
}

async function crewPaid(i) {
  const m = (CREW.members || [])[i];
  if (!m) return;
  const amount_uah = +(($('#cp-sum') || {}).value || 0);
  quiz.close();
  const r = await api('/api/crew/paid', 'POST',
    { crew_id: crewId(), name: m.name, amount_uah });
  if (bad(r)) return;
  crewReload();
}

async function crewPack() {
  toast('Збираю з поправкою на алергії всіх…');
  const p = await api('/api/pack/crew', 'POST', { crew_id: crewId(), max_uah: 1500 });
  if (bad(p)) return;
  renderPack(p);
  if ((p.blocked_for_everyone || []).length)
    toast('Виключив для всіх: ' + p.blocked_for_everyone.join(', '));
  window.CREW_PACK_TOTAL = p.total_uah || p.sum_uah || 0;
}

/* Розрахунок. Грошей не рухаємо: суми готові до передачі в банківський
   «розділити чек» — у Monobank така механіка вже є. Платіжної інтеграції
   тут немає й не імітується. */
/* Розрахунок живе або в чаті (#quiz), або в профілі (sheet). Сума й компанія
   запамʼятовуються, щоб після зміни частки перемалювати те саме вікно. */
let SPLIT_TOTAL = 0, SPLIT_CREW = null, LAST_SPLIT = null;
async function crewSplit(total) {
  const total_uah = +total || +window.CREW_PACK_TOTAL || SPLIT_TOTAL || 0;
  if (!total_uah) return toast('Спершу збери кошик — нема чого ділити');
  SPLIT_TOTAL = total_uah; SPLIT_CREW = crewId();
  const r = await api('/api/crew/split', 'POST', { crew_id: SPLIT_CREW, total_uah });
  if (bad(r)) return;
  $('#quiz-body').innerHTML = `
    <h2 style="margin:0 0 10px">Розділити на компанію</h2>${splitHtml(r)}`;
  if (!quiz.open) quiz.showModal();
}
/* Після зміни частки — перерахувати й перемалювати відкрите вікно. */
async function splitRefresh() {
  const r = await api('/api/crew/split', 'POST', { crew_id: SPLIT_CREW, total_uah: SPLIT_TOTAL });
  if (bad(r)) return;
  if ($('#quiz') && $('#quiz').open) {
    $('#quiz-body').innerHTML = `<h2 style="margin:0 0 10px">Розділити на компанію</h2>${splitHtml(r)}`;
  } else if ($('#sheet') && $('#sheet').open && typeof sheetReplace === 'function') {
    sheetReplace('Розділити на компанію', '', splitHtml(r));
  }
}
/* Головне тут — скільки кому заплатити. Рівна частка мінус те, що людина
   вже виклала; хто виклав більше — тому повертають. Частку можна змінити:
   організатор закріплює суму тапом по ній, гість пропонує свою з телефона —
   і тут це видно, з кнопками прийняти або лишити порівну. Одна розмітка
   на чат і на профіль. */
function splitHtml(r) {
  LAST_SPLIT = r;
  return `
    ${r.rows.map((x, i) => {
      const due = Math.max(0, -x.balance_uah);
      const n = uiEsc(x.name).replace(/'/g, 'ʼ');
      return `<div class="payrow" id="pay-${i}">
        <div class="pn"><b>${uiEsc(x.name)}</b>${x.paid_uah > 0
          ? `<span class="soft">заплатив ${uah(x.paid_uah)} ₴</span>` : ''}${
          x.fixed ? `<span class="soft">закріплено · <a href="#" onclick="shareSet('${n}', null);return false">порівну</a></span>` : ''}${
          x.proposed_uah != null ? `<span class="prop">пропонує <b>${uah(x.proposed_uah)} ₴</b>${
            x.proposal_note ? ' — ' + uiEsc(x.proposal_note) : ''}</span>
            <span class="filters" style="margin:4px 0 0">
              <button class="fbtn" onclick="shareAnswer('${n}', true)">Прийняти</button>
              <button class="fbtn" onclick="shareAnswer('${n}', false)">Лишити порівну</button></span>` : ''}</div>
        <div class="pv ${due > 0 ? '' : 'ok'}">
          <button class="amt" title="Змінити частку" onclick="shareEdit(${i})">${due > 0 ? uah(due) + ' ₴'
            : x.balance_uah > 0.005 ? 'повернути ' + uah(x.balance_uah) + ' ₴' : 'у нулі'}</button></div>
      </div>`; }).join('')}
    <div class="payrow total"><div class="pn"><b>Разом</b></div><div class="pv">${uah(r.total_uah)} ₴</div></div>
    ${r.transfers.length ? `<h3 style="margin-top:14px">Перекази між своїми</h3>
      ${r.transfers.map(t => `<div class="payrow"><div class="pn"><b>${uiEsc(t.from)} → ${uiEsc(t.to)}</b></div>
        <div class="pv">${uah(t.amount_uah)} ₴</div></div>`).join('')}` : ''}
    <p class="soft" style="margin:10px 0 0">Тапни суму, щоб закріпити комусь іншу частку —
      решту поділю порівну між іншими.</p>`;
}
/* Тап по сумі — поле з сумою й «Закріпити». */
function shareEdit(i) {
  const x = LAST_SPLIT && LAST_SPLIT.rows[i]; if (!x) return;
  const n = uiEsc(x.name).replace(/'/g, 'ʼ');
  const row = document.getElementById('pay-' + i); if (!row) return;
  row.querySelector('.pv').innerHTML = `<span class="filters" style="margin:0;flex-wrap:nowrap">
    <input id="share-${i}" type="number" min="0" step="1" value="${Math.round(x.share_uah)}"
      style="min-width:0;width:86px;padding:7px 9px"
      onkeydown="if(event.key==='Enter')shareSet('${n}', +this.value)">
    <button class="fbtn" onclick="shareSet('${n}', +document.getElementById('share-${i}').value)">Закріпити</button></span>`;
  row.querySelector('input').focus();
}
async function shareSet(name, amount) {
  const body = { crew_id: SPLIT_CREW, name };
  if (amount != null && !isNaN(amount)) body.amount_uah = amount;
  const r = await api('/api/crew/share', 'POST', body);
  if (bad(r)) return;
  splitRefresh();
}
async function shareAnswer(name, accept) {
  const r = await api('/api/crew/share/answer', 'POST', { crew_id: SPLIT_CREW, name, accept });
  if (bad(r)) return;
  splitRefresh();
}

function renderWellbeing(r) {
  packSlot().innerHTML = `
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
         <div class="pr">${uah(card.price_uah ?? card.price)} ₴
           ${(card.old_price_uah ?? card.old_price) ? `<span class="old">${uah(card.old_price_uah ?? card.old_price)} ₴</span>` : ''}</div>
         <div class="soft">${card.unit || card.shelf || ''}</div>
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
    ${(c.warnings || []).some(w => w.message === 'product.offer.stock.max') ? `<div class="warnbar bad">
      Товар щойно закінчився — «Сільпо» зменшила кількість.</div>` : ''}
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
        <div class="cside">
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
      <span>Оформити</span><span>${uah(c.total_uah)} ₴</span></button>`;
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
/* Перевірка перед «Оформити» — одна картка на чотири рядки. Кожен рядок:
   назва, підсумок, tools, з яких він узятий, і знак. Три стани, не два:
   ✓ — гаразд, ✗ — треба глянути, «–» — нема що перевіряти (жоден купон не
   про цей кошик — не помилка, просто нічого не ляже). */
function renderPrecheck(r) {
  if (!r || !r.checks) return toast('Перевірка не вдалась');
  const sign = ok => ok === true ? '<i class="ok">✓</i>'
    : ok === false ? '<i class="bad">✗</i>' : '<i class="none">–</i>';
  packSlot().innerHTML = `
    <div class="precheck ${r.all_clear ? 'clear' : ''}">
      <div class="ph">Перевірка перед «Оформити»
        <span class="soft">${uiEsc(r.pack.name)} · ${uah(r.pack.total_uah)} ₴</span></div>
      ${r.checks.map(c => `<div class="prow">
        <div class="pt"><b>${uiEsc(c.title)}</b>${sign(c.ok)}</div>
        <div class="ps">${uiEsc(c.summary || '')}</div>
        ${c.detail ? `<div class="pd ${c.ok === false ? 'bad' : ''}">${uiEsc(c.detail)}</div>` : ''}
        <code>${(c.tools || []).map(t => uiEsc(t.replace('silpo_', ''))).join(' · ')}</code>
      </div>`).join('')}
      <div class="pf"><b>${uiEsc(r.verdict)}</b>
        <a href="${r.checkout_url}" target="_blank" rel="noopener">Відкрити кошик «Сільпо» →</a></div>
    </div>`;
}
async function precheck() {
  if (!PACK) return toast('Спершу збери пак');
  const s = SCENARIOS.find(x => x.id === 'precheck');
  if (s) return runScenario('precheck');
  const r = await api('/api/pack/precheck', 'POST', { pack_id: PACK.id });
  if (!bad(r)) renderPrecheck(r);
}
/* «Куди йдуть гроші» — портрет на телефоні: смужки по розділах, тап по
   розділу розкриває, що саме в ньому. Це відповідь на питання, якого в
   застосунку досі не було; бізнесу — той самий портрет для персональних
   пропозицій. Розділ визначено за назвою товару — у чеку категорії немає. */
function spendHtml(r, opts = {}) {
  const rows = r.categories.slice(0, 8);
  const max = Math.max(...rows.map(c => c.now_uah), 1);
  const uid = 'sp' + Date.now().toString(36);
  window[uid] = r;
  return `
    <div class="spend" id="${uid}">
      ${opts.title === false ? '' : '<h2>Куди йдуть гроші</h2>'}
      <p class="soft" style="margin:0 0 10px">${uiEsc(r.headline)}</p>
      <div class="bh">${r.window_days === 180 ? 'Пів року' : r.window_days + ' днів'} · за розділами · тапни розділ</div>
      ${rows.map((c, i) => `
        <button class="sbar" onclick="spendOpen('${uid}', ${i})" aria-expanded="false">
          <span class="sl">${uiEsc(c.category)}</span>
          <span class="st"><i style="width:${Math.round(c.now_uah / max * 100)}%"></i></span>
          <span class="sv">${uah(Math.round(c.now_uah))} ₴</span>
        </button>
        <div class="sitems" hidden></div>`).join('')}
      <p class="muted" style="margin-top:8px">розділ визначено за назвою товару — у чеку категорії немає</p>
    </div>`;
}
function renderSpend(r) {
  if (!r || !r.categories) return toast('Немає чеків для портрета');
  packSlot().innerHTML = spendHtml(r);
}
function spendOpen(uid, i) {
  const r = window[uid]; const box = document.getElementById(uid);
  if (!r || !box) return;
  const bars = box.querySelectorAll('.sbar'), lists = box.querySelectorAll('.sitems');
  const wasOpen = bars[i].getAttribute('aria-expanded') === 'true';
  bars.forEach(b => { b.setAttribute('aria-expanded', 'false'); b.classList.remove('on'); });
  lists.forEach(l => { l.hidden = true; });
  if (wasOpen) return;
  const c = r.categories[i];
  bars[i].setAttribute('aria-expanded', 'true'); bars[i].classList.add('on');
  lists[i].innerHTML = `<div class="sh">${uiEsc(c.category)} · що саме</div>
    ${(c.items || []).map(it => `<div class="si">
      <span>${uiEsc(it.name)}</span>
      <b>${it.times > 1 ? '×' + it.times + ' · ' : ''}${uah(Math.round(it.uah))} ₴</b></div>`).join('')}
    ${c.distinct > (c.items || []).length
      ? `<div class="soft" style="font-size:11.5px;margin-top:4px">і ще ${c.distinct - c.items.length} товарів</div>` : ''}`;
  lists[i].hidden = false;
  lists[i].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}
function renderWeight(r) {
  packSlot().innerHTML = `
    <h2>Чи влізе кошик</h2>
    <p class="soft" style="margin:0 0 12px">Вага кошика — ${r.cart_weight_kg} кг.
      Ліміти беруться з доступних слотів: у доставки він є, у самовивозу немає.</p>
    ${r.blocked.length ? `<div class="warnbar bad">${r.verdict}</div>`
      : `<div class="warnbar">${r.verdict}</div>`}
    ${r.options.map(o => `<div class="attr"><span>${o.label}</span>
      <span>${o.max_kg ? 'макс ' + o.max_kg + ' кг' : 'без ліміту'}
        ${o.fits ? '✓' : '· перевищення ' + o.over_kg + ' кг'}</span></div>`).join('')}`;
}


async function renderHeirloom(r) {
  packSlot().innerHTML = `
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
};


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
  // Портрет витрат — це екран гостя, а не лише рядок у панелі.
  if (id === 'spend') { if (typeof bubble === 'function') bubble('me', i.phrase); renderSpend(r); }
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
      (c.delta_percent||0) >= 25 ? 'prop' : '')).join('')}
    <p class="soft" style="margin:7px 0 0">Що саме в кожному розділі — на телефоні, тапом по смужці.</p>`;
  if (id === 'plus') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline}</b></div>
    ${line('береш на місяць', money(r.per_month_uah))}
    ${line('кешбек за місяць', money(r.cashback_per_month_uah))}
    ${line('підписка коштує', money(r.price_uah))}
    ${line('чистими', money(r.net_per_month_uah), r.net_per_month_uah > 0 ? '' : 'prop')}
    <p class="soft" style="margin:7px 0 0">${r.gap}</p>`;
  if (id === 'risk') return `
    <div class="head" style="margin:0 0 6px"><b>${r.headline || r.note}</b></div>
    ${(r.risky||[]).slice(0,5).map(x =>
      line(x.name || x.product_id, (x.options||[]).length + ' замін')).join('')}`;
  if (id === 'impulse') return `
    <div class="head" style="margin:0 0 6px"><b>${r.verdict === 'бери' ? '✅ бери' : '⏸ почекай'}
      · ${r.query}</b></div>
    ${(r.reasons||[]).map(x => line(x, '')).join('')}
    ${line('брав усього', r.times_bought + ' раз(и), за 30 дн — ' + r.times_last_30d)}
    ${r.avg_paid_uah ? line('твоя середня ціна', money(r.avg_paid_uah)) : ''}
    ${r.price_now_uah ? line('зараз', money(r.price_now_uah)) : ''}`;
  return `<div class="row"><span class="nm">Готово</span></div>`;
}
