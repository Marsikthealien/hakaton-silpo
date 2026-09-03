/* Спільне для всіх сторінок: звернення до API, шапка, картка пака. */
const $ = s => document.querySelector(s);
const uah = n => (Math.round((n || 0) * 100) / 100).toLocaleString('uk-UA');
const TICKET = ['#F43F8E', '#3B82F6', '#F5A524', '#F97316', '#22C55E', '#8B5CF6'];
let PACK = null, ALLERGIES = [], SEEN = new Set();

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
function mountTop(current) {
  document.body.insertAdjacentHTML('afterbegin', `
    <div class="top"><div class="in">
      <a class="brand" href="/"><span class="dot"></span>
        <span><b>Pack Agent</b><span>розширення для «Сільпо»</span></span></a>
      <nav class="nav">
        <a href="/" ${current === 'home' ? 'aria-current="page"' : ''}>Асистент</a>
        <a href="/profile" ${current === 'profile' ? 'aria-current="page"' : ''}>Профіль</a>
        <a class="desktop-only" href="/tech" ${current === 'tech' ? 'aria-current="page"' : ''}>Під капотом</a>
      </nav>
      <div class="viewswitch" title="Як показувати клієнтську частину">
        <button onclick="setView('desktop')" aria-pressed="true">Десктоп</button>
        <button onclick="setView('mobile')" aria-pressed="false">Мобільний</button>
      </div>
      <div class="status" id="status"></div>
    </div></div>`);
  document.body.insertAdjacentHTML('beforeend', '<div class="toast" id="toast"></div>');
  setView(localStorage.getItem('view') || 'desktop', true);
}

/* Мобільний вигляд — той самий застосунок у рамці телефона.
   «Під капотом» у ньому не показуємо: це екран для команди, не для гостя. */
function setView(mode, silent) {
  document.body.classList.toggle('mobile', mode === 'mobile');
  // Кошик має бути один: на мобільному він усередині застосунку, на десктопі —
  // бічною панеллю, як на silpo.ua. Інакше на екрані два однакові списки.
  const tab = document.querySelector('.apptabs');
  if (tab) {
    tab.hidden = mode !== 'mobile';
    if (mode !== 'mobile' && typeof appTab === 'function') appTab('chat');
  }
  const left = document.querySelector('#scenarios');
  if (left) renderScenarios(left, document.querySelector('#scenarios-2'));
  document.querySelectorAll('.viewswitch button').forEach((b, i) =>
    b.setAttribute('aria-pressed', (i === 0) === (mode !== 'mobile')));
  try { localStorage.setItem('view', mode); } catch (e) {}
  if (mode === 'mobile' && location.pathname === '/tech' && !silent) location.href = '/';
}
async function loadStatus() {
  const s = await api('/api/status');
  $('#status').innerHTML = `
    <span class="pill">MCP-tools <b>${s.mcp_tools}</b></span>
    <span class="pill hot">викликів «Сільпо» <b id="calls">${s.silpo_calls}</b></span>
    <span class="pill">модель <b>${s.model_available ? s.model : 'офлайн'}</b></span>`;
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
function renderPack(p) {
  const box = $('#pack'); if (!box) return;
  if (!p || p.error) {
    box.innerHTML = `<h2>Пак ще не зібрано</h2>
      <p class="muted" style="margin:0">Натисни сценарій ліворуч або попроси словами —
        агент збере набір із реальних товарів «Сільпо».</p>`;
    return;
  }
  PACK = p;
  const src = { receipt: 'відтворено з чека', habits: 'зі звичок', silpo_set: 'із набору «Сільпо»',
                agent: 'зібрано агентом' }[p.source] || p.source;
  box.innerHTML = `
    <div class="head"><div class="t">
      <h2>${p.name}</h2>
      <div class="soft">${src} · ${p.item_count} позицій${
        p.receipt ? ` · в оригіналі ${uah(p.receipt.paid_uah)} ₴` : ''}</div></div>
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
          ${i.qty !== 1 ? `<div class="why">× ${i.qty}</div>` : ''}
          ${i.swapped_from ? `<div class="why swap">замість «${i.swapped_from}» — не було в магазині</div>` : ''}
          ${i.note ? `<div class="why">${i.note}</div>` : ''}
          <span style="display:flex;gap:12px;flex-wrap:wrap">
            <button class="link" onclick="showProduct('${i.slug}','${(i.name||'').replace(/'/g,'')}')">Відомості</button>
            <button class="link" onclick="pick('${i.product_id}')">Обрати інший →</button>
          </span>
        </div></div>`).join('')}
    <div class="total"><span>Разом</span><span>${uah(p.total_uah)} ₴</span></div>
    ${p.saved_uah > 0 ? `<div class="saved">знижка ${uah(p.saved_uah)} ₴</div>` : ''}
    ${(p.skipped || []).length ? `<div class="soft" style="margin-top:8px">Не додав:
      ${p.skipped.map(s => `${s.query} — ${s.reason}`).join(' · ')}</div>` : ''}
    <div id="offers"></div>`;
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

/* ---------- трейс ---------- */
async function loadTrace(limit = 30) {
  const t = await api('/api/trace?limit=' + limit);
  const sum = $('#trace-sum'); if (sum) sum.textContent = `${t.total} за сеанс`;
  const calls = $('#calls'); if (calls) calls.textContent = t.total;
  const box = $('#trace'); if (!box) return;
  box.innerHTML = (t.calls || []).slice().reverse().map(c => {
    const key = c.at + c.tool + c.ms, fresh = SEEN.has(key) ? '' : ' fresh'; SEEN.add(key);
    const prop = c.kind === 'proposed';
    return `<div class="call${c.ok ? '' : ' bad'}${fresh}"><span class="t">${c.at}</span>
      <span class="n" ${prop ? 'style="color:#6B34C9"' : ''}>${c.tool.replace('silpo_', '')}${
        prop ? ' ⁺' : ''}</span><span class="ms">${c.ms} ms</span></div>`;
  }).join('') || '<span class="muted">Ще жодного виклику.</span>';
}

/* ===================== сценарії ===================== */
/* Кожен сценарій оголошує очікуваний ланцюг tools — гість бачить його ДО запуску,
   а під час виконання виклики підсвічуються в тому порядку, в якому справді пішли. */
const SCENARIOS = [
  { id: 'repeat', title: 'Повтори останній чек',
    phrase: 'Повтори мою минулу покупку',
    path: '/api/pack/from_receipt', body: { index: 0 },
    tools: ['silpo_get_my_offline_orders', 'silpo_get_similar_products',
            'silpo_add_or_update_cart_products'] },

  { id: 'reorder', title: 'Що в мене закінчилось',
    phrase: 'Збери те, що я зазвичай беру і що вже мало б закінчитись',
    path: '/api/pack/reorder', body: {},
    tools: ['silpo_get_my_offline_orders', 'silpo_find_products_batch'] },

  { id: 'meal', title: 'Страва на суму', ask: 'meal',
    phrase: 'Хочу вечерю на 500 грн',
    path: '/api/pack/meal',
    tools: ['silpo_find_recipes*', 'silpo_find_products_batch'] },

  { id: 'mood', title: 'Вгадай мій настрій', quiz: 'mood',
    phrase: 'Підбери щось під мій настрій',
    path: '/api/pack/mood',
    tools: ['silpo_find_products_batch'] },

  { id: 'evening', title: 'Залипнути в телевізор', quiz: 'evening',
    phrase: 'Хочу залипнути ввечері',
    path: '/api/pack/evening',
    tools: ['silpo_get_product_sets', 'silpo_get_products', 'silpo_find_products_batch'] },

  { id: 'geo', title: 'Топати чи замовити', geo: true,
    phrase: 'Дійти до Сільпо чи замовити доставку?',
    path: '/api/delivery',
    tools: ['silpo_estimate_delivery*', 'silpo_list_branches', 'silpo_get_time_slots'] },

  { id: 'pantry', title: 'Що зникло з холодильника',
    phrase: 'Подивись, чого немає вдома, і збери список',
    path: '/api/pantry/missing', body: {}, method: 'GET',
    tools: ['silpo_pantry_missing*', 'silpo_get_my_offline_orders'] },

  { id: 'family', title: 'Вечеря на всю сімʼю',
    phrase: 'Збери вечерю, щоб усім підійшло',
    path: '/api/family', method: 'GET',
    tools: ['silpo_get_family_preferences*', 'silpo_get_my_family'] },

  { id: 'weight', title: 'Чи влізе кошик', method: 'GET',
    phrase: 'Кошик не заважкий для доставки?',
    path: '/api/weight',
    tools: ['silpo_get_shopping_cart_by_id', 'silpo_get_available_delivery_types',
            'silpo_get_time_slots'] },

  { id: 'risk', title: 'Кур’єр не подзвонить',
    phrase: 'Що в моєму замовленні можуть не зібрати?',
    path: '/api/order/risk',
    tools: ['silpo_get_my_online_orders', 'silpo_get_replacements',
            'silpo_get_my_food_restrictions'] },

  { id: 'savings', title: 'Скільки я заощадив', method: 'GET',
    phrase: 'Скільки Машрум мені заощадив і що згоріло?',
    path: '/api/savings',
    tools: ['silpo_get_my_offline_orders', 'silpo_get_my_coupons',
            'silpo_get_my_promos', 'silpo_get_loyalty_info'] },

  { id: 'route', title: 'Маршрут по залу', needsPack: true,
    phrase: 'Скажи, в якому порядку обходити магазин',
    path: '/api/route',
    tools: ['silpo_get_store_layout*'] },

  { id: 'heirloom', title: 'Спадкова кухня', method: 'GET',
    phrase: 'Приготуй те, що готувала бабуся',
    path: '/api/family/recipes',
    tools: ['silpo_get_family_recipes*', 'silpo_find_products_batch'] },

  { id: 'wellbeing', title: 'Після тренування', wellbeing: true,
    phrase: 'Я щойно з залу і спав 5 годин',
    path: '/api/wellbeing',
    tools: ['silpo_wellbeing_sync*', 'silpo_find_products_batch'] },
];

let MODE = 'direct';           // 'llm' — через локальну модель, 'direct' — напряму
let CHAIN_TIMER = null;

function setMode(m) {
  MODE = m;
  document.querySelectorAll('[data-mode]').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.mode === m));
  const note = document.querySelector('#mode-note');
  if (note) note.textContent = m === 'llm'
    ? 'Той самий MCP-виклик, що й «Напряму» — модель лише озвучує готовий результат у чаті. Пак однаковий.'
    : 'Сценарій іде напряму через MCP, без моделі.';
}

function renderScenarios(into, second) {
  // У мобільному вигляді сценарії стоять обабіч телефона: половина ліворуч,
  // половина праворуч. У десктопному — усі в одній колонці.
  const split = document.body.classList.contains('mobile') && second;
  const half = split ? Math.ceil(SCENARIOS.length / 2) : SCENARIOS.length;
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
  const note = `<p class="soft" style="margin:10px 0 0">⁺ — tool, якого в MCP «Сільпо»
    ще немає. Ми його реалізували в себе, щоб сценарій працював, і пропонуємо додати.</p>`;
  into.innerHTML = SCENARIOS.slice(0, half).map(card).join('') + (split ? '' : note);
  if (second) second.innerHTML = split ? SCENARIOS.slice(half).map(card).join('') + note : '';
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
  if (s.needsPack && !PACK) return toast('Спершу збери пак — маршрут будується під нього');
  if (s.id === 'route' && !extraBody)
    extraBody = { items: PACK.items.map(i => ({ name: i.name })), branch_id: PACK.branch || null };
  if (s.id === 'risk' && !extraBody)
    extraBody = { ...(PACK ? { pack_id: PACK.id } : {}), avoid: ALLERGIES };

  $('#scn-' + id).querySelectorAll('.tchip').forEach(c => c.classList.remove('on'));
  const before = (await api('/api/trace?limit=1')).total;
  const stop = await watchChain(id, before);

  // «Напряму» і «Через модель» дають РІВНО той самий пак: обидва режими
  // виконують той самий MCP-виклик (callScenario), картка малюється одразу.
  // У режимі моделі бульбашка «…» означає РЕАЛЬНИЙ виклик ШІ: якщо модель
  // відповіла — показуємо її текст, якщо ні (офлайн/таймаут) — кидаємо
  // помилку в чат і тост, а не тихий детермінований підсумок.
  const result = await callScenario(s, extraBody);
  stop();
  handleResult(s, result);
  if (MODE === 'llm' && window.bubble) {
    bubble('me', s.phrase);
    if (!result || result.error) {
      bubble('it', '⚠ Сценарій не виконався — дивись повідомлення про помилку.');
      return;
    }
    // Модель озвучує лише пак: там є склад, сума, знижка. Вердикт-екрани
    // (вага, ризик збирання, доставка) вона тільки вигадувала б («у кошику
    // 0 грн») — показуємо готовий вердикт як є, без виклику ШІ й без «…».
    const isPack = result.item_count != null || Array.isArray(result.items);
    if (!isPack) {
      bubble('it', result.verdict || 'Готово — дивись картку праворуч.');
      return;
    }
    bubble('it', '…');
    const line = $('#log').lastChild;
    let n;
    try {
      n = await api('/api/chat/narrate', 'POST',
        { phrase: s.phrase, tool: (s.tools[0] || '').replace('*', ''), result });
    } catch (e) {
      n = { error: String(e && e.message || e) };
    }
    if (n && n.reply && n.model) {
      line.textContent = n.reply;                 // ШІ справді озвучив
    } else {
      const msg = (n && n.error) || 'ШІ не відповів';
      line.className = 'msg err';
      line.textContent = '⚠ ' + msg;
      toast(msg);
    }
  }
}

async function callScenario(s, extraBody) {
  const body = { ...(s.body || {}), ...(extraBody || {}) };
  return s.method === 'GET' ? api(s.path) : api(s.path, 'POST', body);
}

function handleResult(s, r) {
  if (bad(r)) return;
  if (r.items) { renderPack(r); return; }
  if (s.id === 'geo') return renderDelivery(r);
  if (s.id === 'pantry') return renderPantry(r);
  if (s.id === 'family') return renderFamily(r);
  if (s.id === 'wellbeing') return renderWellbeing(r);
  if (s.id === 'weight') return renderWeight(r);
  if (s.id === 'route') return renderRoute(r);
  if (s.id === 'heirloom') return renderHeirloom(r);
  if (s.id === 'risk') return renderOrderRisk(r);
  if (s.id === 'savings') return renderSavings(r);
  toast('Готово');
}

/* Скільки заощаджено постфактум і що згорає: sumDiscount із чеків проти
   активних купонів із минулою датою. Тут — метрика користі в гривнях. */
function renderSavings(r) {
  const list = (arr, cls) => (arr || []).map(c => `
    <div class="habit ${cls || ''}">
      <b>${c.reward || '—'}</b> ${c.text || ''}
      <span class="soft">${c.days_left != null ? (c.days_left === 0 ? 'сьогодні' : `${c.days_left} дн.`) : ('до ' + (c.until || '').slice(0, 10))}${
        c.cap_uah ? ` · до ${uah(c.cap_uah)} ₴` : ''}${c.min_cheque ? ` · ${c.min_cheque}` : ''}</span>
    </div>`).join('');
  const ap = r.applied_rewards || {};
  const tile = (v, cap) => `<div style="flex:1;min-width:120px;background:var(--tint,#F4F6FB);
    border:1px solid var(--line);border-radius:12px;padding:11px 14px">
    <b style="display:block;font-size:20px;font-weight:800">${v}</b>
    <span class="soft" style="font-size:12px">${cap}</span></div>`;
  $('#pack').innerHTML = `
    <h2>Скільки Машрум заощадив</h2>
    <p class="soft" style="margin:0 0 12px">За ${r.receipts} останніх чеків · витрачено ${uah(r.spent_uah)} ₴</p>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">
      ${tile(uah(r.saved_uah) + ' ₴', 'знижок у чеках')}
      ${tile(uah(ap.uah || 0) + ' ₴', (ap.count || 0) + ' нагород застосовано')}
      ${tile(uah(r.bonuses_uah || 0) + ' ₴', 'балобонусів зараз')}
    </div>
    ${(r.coupons_wasted || []).length ? `<div class="warn">
      <b>Згоріло невикористаними: ${r.coupons_wasted.length} купон(ів) на ~${uah(r.coupons_wasted_est_uah)} ₴</b>
      ${list(r.coupons_wasted)}
      <div class="soft" style="margin-top:6px">${r.note}</div>
    </div>` : `<div class="warnbar">Протермінованих купонів немає — нічого не втрачено.</div>`}
    ${(r.coupons_burning || []).length ? `<h3 style="margin-top:14px">Згорають за 2 дні</h3>${list(r.coupons_burning, 'swap')}` : ''}
    ${(r.promos_burning || []).length ? `<h3 style="margin-top:14px">Промо, що згорають</h3>${list(r.promos_burning, 'swap')}` : ''}
    ${(r.coupons_ready || []).length ? `<h3 style="margin-top:14px">Готові спрацювати (${r.coupons_ready.length})</h3>${list(r.coupons_ready)}` : ''}
    <div class="note" style="margin-top:12px">Активацію купонів і промо підтверджуєш у застосунку — MCP їх лише читає.</div>`;
}

/* Ризик збирання: що можуть не зібрати й чим замінити наперед.
   Джерело — silpo_get_replacements (не просто stock:0), заміни з алергією відкинуто. */
function renderOrderRisk(r) {
  const src = { pack: 'поточний пак', online_order: 'замовлення в збиранні',
                cart: 'кошик «Сільпо»' }[r.source] || r.source;
  const rows = (r.at_risk || []).map(x => {
    const rep = x.replacement;
    const delta = rep && rep.delta_uah != null
      ? `<span class="${rep.delta_uah < 0 ? 'down' : 'up'}">${rep.delta_uah > 0 ? '+' : ''}${uah(rep.delta_uah)} ₴</span>` : '';
    return `<tr>
      <td>${x.name}${x.price_uah != null ? `<br><span class="soft">${uah(x.price_uah)} ₴</span>` : ''}
        <br><span class="soft">${x.reason}</span></td>
      <td>${rep
        ? `${rep.name}<br><span class="soft">${rep.price_uah != null ? uah(rep.price_uah) + ' ₴' : ''} ${delta}${
            rep.via === 'similar_products' ? ' · зі схожих' : ''}</span>`
        : `<span style="color:var(--red)">заміну треба обрати вручну${
            x.all_candidates_blocked ? ` — усі кандидати під обмеженням (${x.all_candidates_blocked.join(', ')})` : ''}</span>`}</td>
    </tr>`;
  }).join('');
  $('#pack').innerHTML = `
    <h2>Кур'єр не подзвонить</h2>
    <p class="soft" style="margin:0 0 12px">Джерело: ${src} · перевірено ${r.checked} позиц.${
      (r.checked_for || []).length ? ` · з поправкою на: ${r.checked_for.slice(0, 4).join(', ')}${r.checked_for.length > 4 ? '…' : ''}` : ''}</p>
    <div class="warnbar${r.clean ? '' : ' bad'}">${r.verdict}</div>
    ${rows ? `<div class="wrap-x" style="margin-top:12px"><table style="width:100%;font-size:13.5px">
      <thead><tr><th>Позиція під ризиком</th><th>Заміна наперед</th></tr></thead>
      <tbody>${rows}</tbody></table></div>` : ''}
    ${(r.blocked_by_allergy || []).length ? `<p class="soft" style="color:var(--red);margin-top:10px">
      Під алергією, безпечної заміни немає: ${r.blocked_by_allergy.join(', ')}</p>` : ''}
    <div class="note" style="margin-top:12px">${r.note || ''}</div>`;
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
    <div class="note" style="margin-top:12px">${r.spec}</div>`;
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
         <button class="no" onclick="swipe(false)" title="не показувати">✕</button>
         <button class="yes" onclick="swipe(true)" title="в обране">♥</button>
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
  'ананас':    { emoji: '🍍', line: 'колючий зовні, солодкий усередині', mood: 'ігривий' },
  'кавун':     { emoji: '🍉', line: 'великий, соковитий, на всю компанію', mood: 'святковий' },
  'лимон':     { emoji: '🍋', line: 'кислий і має на те причини', mood: 'втомлений' },
  'авокадо':   { emoji: '🥑', line: 'або ще ні, або вже все', mood: 'спокійний' },
  'банан':     { emoji: '🍌', line: 'простий, надійний, завжди під рукою', mood: 'бадьорий' },
  'полуниця':  { emoji: '🍓', line: 'ніжна і трохи закохана', mood: 'романтичний' },
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
    toast(`${f.emoji} Сьогодні ти ${fruit} — ${f.line}`);
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
