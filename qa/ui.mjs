// Прогін справжнього UI у Chromium через DevTools Protocol: натискає кнопки,
// чекає на відповідь бекенду, читає DOM. Порт сервера — 8011.
//
//   chromium --headless=new --no-sandbox --remote-debugging-port=9222 about:blank &
//   .venv/bin/python -m uvicorn web.server:app --port 8000 &
//   node --experimental-websocket qa/ui.mjs
//
// Деталі перевірок — docs/CHECKLIST.md, розділ 2.

import { withPage, sleep } from './cdp.mjs';

const B = process.env.PACKAGENT_URL || "http://localhost:8000";
let fails = 0;
const check = (name, cond, extra = '') => {
  console.log(`${cond ? '  OK  ' : ' FAIL '} ${name}${extra ? ' — ' + extra : ''}`);
  if (!cond) fails++;
};
const until = async (ev, expr, tries = 90) => {
  for (let i = 0; i < tries; i++) { if (await ev(expr)) return true; await sleep(500); }
  return false;
};

// ------------------------------------------- статика не має кешуватись --
// Найпідступніший збій за весь проєкт: FileResponse віддає лише ETag і
// Last-Modified, браузер кешує app.css/app.js евристично й НЕ перепитує сервер.
// Виходить свіжий HTML зі старим скриптом — сторінка розсипається, а в консолі
// порожньо. Тому це окрема перевірка, а не «та ми ж бачили, що працює».
for (const path of ['/', '/app.css', '/app.js', '/profile', '/game', '/road']) {
  const r = await fetch(B + path);
  const cc = r.headers.get('cache-control') || '';
  check(`${path} не кешується`, cc.includes('no-store'), cc || 'заголовка немає');
}

// ---------------------------------------------------------------- головна --
await withPage(B + '/', async (ev, _shot, emulate) => {
  await emulate(1920, 1000);
  await until(ev, `document.querySelectorAll('#scenarios .scn').length > 0`);
  check('сценарії з реєстру бекенду',
    await ev(`document.querySelectorAll('#scenarios .scn').length === 17`),
    await ev(`String(document.querySelectorAll('#scenarios .scn').length)`));
  check('назви приходять із flows.py',
    await ev(`document.querySelector('#scn-repeat b').textContent === 'Повтори останній чек'`));
  check('групи згортаються', await ev(`document.querySelectorAll('#scenarios details.grp').length === 3`));
  check('аналітика', await ev(`document.querySelectorAll('#insights .scn').length === 11`),
    await ev(`String(document.querySelectorAll('#insights .scn').length)`));

  check('панелі закриті — робоча область на ВСЮ ширину, без смужок',
    await ev(`!document.querySelector('#shell').classList.contains('l') &&
      Math.round(document.querySelector('.main').getBoundingClientRect().width) === 1920 &&
      Math.round(document.querySelector('#side-left').getBoundingClientRect().width) === 0`),
    await ev(`String(Math.round(document.querySelector('.main').getBoundingClientRect().width)) + 'px'`));
  check('жоден екран не падає з порожнім JS',
    await ev(`document.querySelector('#nav').innerHTML.length > 100 &&
      document.querySelector('#btn-left').innerHTML.includes('svg')`));
  await ev(`togglePanel('l')`); await sleep(350);
  check('ліва панель розсовує сітку, а не накладається',
    await ev(`document.querySelector('#shell').classList.contains('l') &&
      document.querySelector('#side-left').getBoundingClientRect().width > 200 &&
      !document.querySelector('#scrim').classList.contains('on')`));
  await ev(`togglePanel('r')`); await sleep(350);
  check('права панель замінює ліву',
    await ev(`document.querySelector('#shell').classList.contains('r') &&
      !document.querySelector('#shell').classList.contains('l')`));
  await ev(`closePanels()`);
  check('іконки — не емоджі',
    await ev(`document.querySelectorAll('.appbar svg.ic').length >= 4 &&
      !/[\u{1F300}-\u{1FAFF}]/u.test(document.querySelector('.appbar').textContent)`));

  // Розумний бюджет: діалог → новизна → пак
  await ev(`runScenario('budget')`); await sleep(400);
  check('діалог бюджету', await ev(`quiz.open && !!document.querySelector('#b-sum')`));
  await ev(`$('#b-sum').value=600; quiz.close(); runScenario('budget',{budget_uah:600,days:7})`);
  await sleep(500);
  check('питання «знайоме чи нове»',
    await ev(`quiz.open && document.querySelector('#quiz-body').textContent.includes('знайоме')`));
  await ev(`noveltyPick('familiar')`);
  await until(ev, `!!document.querySelector('.packmsg .prod')`);
  check('пак зібрався В СТРІЧЦІ ЧАТУ', await ev(`!!document.querySelector('.packmsg .prod')`),
    await ev(`(PACK||{}).name || ''`));
  check('novelty доїхала до бекенду', await ev(`(PACK||{}).novelty === 'familiar'`));
  check('історія розмови збереглась',
    await ev(`document.querySelectorAll('#log .msg').length >= 2`),
    await ev(`String(document.querySelectorAll('#log .msg').length) + ' повідомлень'`));
  check('підказки стали правочними',
    await ev(`[...document.querySelectorAll('#quicks button')].some(b =>
      b.textContent.includes('Прибери'))`));

  // Редагування пака словами — головне, заради чого пак живе в чаті
  await ev(`$('#ask').value='прибери пакет'; send()`);
  await until(ev, `[...document.querySelectorAll('#log .msg')].some(m =>
    m.textContent.includes('Прибрав'))`);
  check('правка пака словами', await ev(`[...document.querySelectorAll('#log .msg')].some(m =>
    m.textContent.includes('Прибрав'))`),
    await ev(`[...document.querySelectorAll('#log .msg.bot')].pop().textContent.trim().slice(0,50)`));
  check('на екрані один розгорнутий пак, попередній згорнуто',
    await ev(`document.querySelectorAll('.packmsg').length === 1 &&
      [...document.querySelectorAll('#log .msg.sys')].some(m =>
        m.textContent.includes('замінено новим'))`));

  // Попередження про алергени — усередині картки пака, а не на всю сторінку
  await ev(`fetch('/api/profile',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({allergies:['сметана'],mode:'replace'})})`);
  await ev(`loadAllergies()`); await sleep(500);
  await ev(`$('#ask').value='повтори минулу покупку'; send()`);
  await until(ev, `!!document.querySelector('.packmsg .warn')`);
  check('попередження всередині екрана чату', await ev(`
    const w=document.querySelector('.packmsg .warn').getBoundingClientRect();
    const f=document.querySelector('.appframe').getBoundingClientRect();
    w.x > f.x && (w.x + w.width) < (f.x + f.width)`));
  check('алерген ловиться за основою слова («сметана» → «сметани»)',
    await ev(`document.querySelector('.packmsg .warn').textContent.includes('сметан')`));
  await ev(`fetch('/api/profile',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({allergies:[],mode:'replace'})})`);

  await ev(`runInsight('coupons')`);
  await until(ev, `$('#ires-coupons').textContent.includes('Спрацювало')`);
  check('чек-детектив', await ev(`$('#ires-coupons').textContent.includes('Спрацювало')`),
    (await ev(`$('#ires-coupons').textContent`) || '').slice(0, 70).replace(/\s+/g, ' '));

  // «Через модель» = «Напряму»: сценарій виконується тим самим MCP-викликом,
  // модель лише переказує. Ollama в тестах немає, тож перевіряємо головне —
  // що пак усе одно зібрався, а про мовчання ШІ сказано прямо.
  await ev(`setMode('llm')`);
  await ev(`runScenario('repeat')`);
  await until(ev, `[...document.querySelectorAll('#log .msg')].some(m =>
    m.classList.contains('err') || m.textContent.includes('ШІ'))`, 60);
  check('«через модель» дає той самий пак',
    await ev(`!!document.querySelector('.packmsg .prod') &&
      ((PACK||{}).source === 'receipt')`),
    await ev(`(PACK||{}).name || ''`));
  check('без Ollama каже прямо, а не підміняє шаблоном',
    await ev(`[...document.querySelectorAll('#log .msg')].some(m =>
      m.classList.contains('err'))`),
    await ev(`(document.querySelector('#log .msg.err')||{}).textContent || ''`));
  await ev(`setMode('direct')`);

  // Озвучення. У headless-браузері голосів немає, тому перевіряємо не звук,
  // а що саме пішло б у синтез: текст, момент і те, що службові рядки мовчать.
  check('кнопка озвучення є', await ev(`!!document.querySelector('#btn-tts') &&
    document.querySelector('#btn-tts').innerHTML.includes('svg')`));
  // Шляхів озвучення два — Respeecher і браузер, — тож ловимо обидва:
  // перехоплюємо і speechSynthesis, і запит на /api/tts.
  await ev(`window.__spoken=[];
    const _s = speechSynthesis.speak.bind(speechSynthesis);
    speechSynthesis.speak = u => { window.__spoken.push(u.text); return _s(u); };
    const _f = window.fetch;
    window.fetch = (url, opt) => {
      if (String(url).includes('/api/tts') && opt && opt.body)
        try { window.__spoken.push(JSON.parse(opt.body).text); } catch (e) {}
      return _f(url, opt);
    }; 1`);
  // Стан озвучення живе в localStorage і переживає прогони, тож спершу
  // приводимо його до відомого — інакше toggle вимикає замість вмикати.
  await ev(`if (TTS) toggleTts(); 1`); await sleep(300);
  await ev(`toggleTts()`); await sleep(600);
  check('озвучення вмикається й памʼятається',
    await ev(`TTS === true && localStorage.getItem('tts') === '1' &&
      document.querySelector('#btn-tts').getAttribute('aria-pressed') === 'true'`));
  await ev(`$('#ask').value='скільки я зекономив'; send()`);
  await until(ev, `(window.__spoken||[]).length > 1`);
  check('озвучується відповідь агента',
    await ev(`(window.__spoken||[]).some(t => t.includes('зекономив') || t.includes('Модель'))`),
    (await ev(`JSON.stringify((window.__spoken||[]).slice(-1))`) || '').slice(0, 60));
  check('службові рядки не озвучуються',
    await ev(`!(window.__spoken||[]).some(t => t.includes('→') || t.startsWith('скільки я'))`));
  await ev(`toggleTts()`); await sleep(300);
  check('вимикається', await ev(`TTS === false && localStorage.getItem('tts') === '0'`));

  // Індикатор роботи й синхронність тексту з голосом. Підміняємо синтез
  // повільним, щоб побачити порядок: текст НЕ має випереджати звук.
  await ev(`
    window.__textAt = null; window.__playedAt = null;
    const log = document.querySelector('#log');
    new MutationObserver(() => {
      const last = [...log.querySelectorAll('.msg.bot')].pop();
      if (last && !last.classList.contains('thinking') &&
          last.textContent.includes('зекономив') && !window.__textAt)
        window.__textAt = performance.now();
    }).observe(log, {childList:true, subtree:true, characterData:true});
    TTS = true; TTS_REMOTE = true;
    window.speechReady = async () => {
      await new Promise(r => setTimeout(r, 1800));
      return () => { window.__playedAt = performance.now(); };
    }; 1`);
  await ev(`$('#ask').value='скільки я зекономив'; send(); 1`);
  const phases = new Set();
  for (let i = 0; i < 90; i++) {
    const t = await ev(`(document.querySelector('#log .msg.thinking')||{}).textContent || ''`);
    if (t) phases.add(t);
    if (await ev(`(window.__playedAt||0) > 0`)) break;
    await sleep(200);
  }
  check('індикатор показує фази, а не німе «…»',
    phases.size >= 2 && [...phases].some(p => p.includes('Думаю')) &&
    [...phases].some(p => p.includes('Озвучую')),
    JSON.stringify([...phases]));
  check('текст зʼявляється РАЗОМ із голосом, а не раніше', await ev(`
    Math.abs((window.__playedAt||0) - (window.__textAt||0)) < 250 &&
    (window.__textAt||0) > 0`),
    await ev(`String(Math.round((window.__playedAt||0) - (window.__textAt||0))) + ' мс різниці'`));
  check('індикатор зникає після відповіді',
    await ev(`!document.querySelector('#log .msg.thinking')`));

  // Без озвучення затримки бути не повинно
  await ev(`TTS = false; window.__textAt = null; window.__t0 = performance.now(); 1`);
  await ev(`$('#ask').value='скільки я зекономив'; send(); 1`);
  await until(ev, `(window.__textAt||0) > 0`, 60);
  check('без озвучення текст не чекає',
    await ev(`((window.__textAt||0) - window.__t0) < 1500`),
    await ev(`String(Math.round((window.__textAt||0) - window.__t0)) + ' мс'`));

  await ev(`setView('mobile')`); await sleep(400);
  check('мобільний вигляд', await ev(`document.body.classList.contains('mobile')`));
  await ev(`setView('desktop')`);
});

// ---------------------------------------------------------------- профіль --
await withPage(B + '/profile', async (ev, _shot, emulate) => {
  await emulate(1400, 950);
  await until(ev, `document.querySelectorAll('#prefs-tiles .tile').length > 0`);
  check('смаки й обмеження — одним блоком із іконок',
    await ev(`document.querySelectorAll('#prefs-tiles .tile').length === 7`),
    await ev(`String(document.querySelectorAll('#prefs-tiles .tile').length)`));
  check('плитки без емоджі',
    await ev(`document.querySelectorAll('#prefs-tiles svg.ic').length === 7 &&
      !/[\u{1F300}-\u{1FAFF}]/u.test(document.querySelector('#prefs-tiles').textContent)`));
  await until(ev, `!!document.querySelector('.lvlbadge')`);
  check('вхід у грибницю — іконкою в портреті',
    await ev(`!!document.querySelector('.lvlbadge') &&
      document.querySelector('.lvlbadge').getAttribute('href') === '/game'`));

  for (const [fn, mark] of [['openAllergies', 'не можна'], ['openEquip', 'кухні'],
                            ['openHabits', 'регулярно'], ['openFacts', 'Памʼять'],
                            ['openConnectors', 'Джерела']]) {
    await ev(`${fn}()`); await sleep(400);
    check(`модалка ${fn}`, await ev(`document.querySelector('#sheet').open &&
      document.querySelector('#sheet-body').textContent.includes('${mark}')`));
    await ev(`closeSheet()`);
  }
  await ev(`openLikes()`); await sleep(900);
  check('ваги смаку живуть у «Вподобаннях»',
    await ev(`document.querySelector('#sheet-body').textContent.includes('Ваги смаку') &&
      document.querySelector('#sheet-body').textContent.includes('Відстежується')`));
  await ev(`closeSheet()`);

  // модалка з модалки → має бути «назад»
  await ev(`openFamily()`); await sleep(1200);
  check('модалка сімʼї', await ev(`document.querySelector('#sheet-body').textContent.includes('Мурчик')`));
  await ev(`editMember('x','Назар')`); await sleep(350);
  check('модалка з модалки дає «назад»',
    await ev(`SHEETS.length === 2 && !!document.querySelector('#sheet .shead .iconbtn')`));
  await ev(`sheetBack()`); await sleep(350);
  check('«назад» повертає до попередньої',
    await ev(`SHEETS.length === 1 &&
      document.querySelector('#sheet-body').textContent.includes('Мурчик')`));
  await ev(`closeSheet()`);

  check('чеки — картки зі справжніми кнопками',
    await ev(`document.querySelectorAll('#receipts .receipt .acts .go').length >= 10`));

  await ev(`setView('mobile')`); await sleep(600);
  check('профіль має мобільний вигляд',
    await ev(`document.body.classList.contains('mobile') &&
      document.querySelector('.appframe').getBoundingClientRect().width < 460 &&
      !!document.querySelector('.appnav')`),
    await ev(`String(Math.round(document.querySelector('.appframe').getBoundingClientRect().width)) + 'px'`));
  await ev(`setView('desktop')`);
});

// --------------------------------------------------------------- грибниця --
await withPage(B + '/game', async ev => {
  await until(ev, `document.querySelectorAll('#game-tiles .tile').length > 0`);
  check('картка грибниці компактна',
    await ev(`document.querySelector('.gamecard').getBoundingClientRect().height < 420`),
    await ev(`String(Math.round(document.querySelector('.gamecard').getBoundingClientRect().height)) + 'px'`));
  check('без дублю «витрачено всього»',
    await ev(`!document.querySelector('#level').textContent.includes('витрачено всього')`));
  check('чотири плитки без емоджі',
    await ev(`document.querySelectorAll('#game-tiles .tile').length === 4 &&
      document.querySelectorAll('#game-tiles svg.ic').length === 4`));
  check('є вихід на шлях', await ev(`!!document.querySelector('#roadlink')`));
  check('ваги смаку не підписані на грибниці',
    await ev(`!document.querySelector('#myc').textContent.match(/\\+\\d/)`));

  await ev(`openAch()`); await sleep(900);
  check('досягнення в модалці', await ev(`document.querySelectorAll('#sheet .ach .a').length === 14`));
  await ev(`closeSheet()`); await ev(`openSkins()`); await sleep(900);
  check('скіни в модалці', await ev(`document.querySelectorAll('#sheet .skin').length === 8`));
  await ev(`closeSheet()`); await ev(`openThemed()`); await sleep(900);
  check('дизайнерські «Сільпо» з джерелами',
    await ev(`document.querySelectorAll('#sheet .themed .th').length === 9 &&
              document.querySelectorAll('#sheet .themed a').length >= 8`));
  await ev(`closeSheet()`);
  await ev(`setView('mobile')`); await sleep(600);
  check('грибниця має мобільний вигляд',
    await ev(`document.querySelector('.appframe').getBoundingClientRect().width < 460`));
  await ev(`setView('desktop')`);
});

// ------------------------------------------------------------------ шлях --
await withPage(B + '/road', async ev => {
  await until(ev, `document.querySelectorAll('#road .lvlrow').length > 5`);
  check('шлях окремою сторінкою',
    await ev(`document.querySelectorAll('#road .lvlrow').length === 40`),
    await ev(`String(document.querySelectorAll('#road .lvlrow').length) + ' рівнів'`));
  check('рівні зверху вниз від меншого до більшого',
    await ev(`document.querySelector('#road .lvlrow .node').textContent === '1' &&
      [...document.querySelectorAll('#road .lvlrow .node')].pop().textContent === '40'`));
  check('крива видно як відступ вузла', await ev(`
    const rows=[...document.querySelectorAll('#road .lvlrow')];
    parseFloat(getComputedStyle(rows[rows.length-1]).getPropertyValue('--x')) >
    parseFloat(getComputedStyle(rows[0]).getPropertyValue('--x')) + 60`));
  await sleep(900);
  check('автоскрол на поточний рівень', await ev(`
    const b=$('#scroll').getBoundingClientRect(), n=document.querySelector('.lvlrow.now').getBoundingClientRect();
    $('#scroll').scrollTop > 100 && n.top > b.top && n.bottom < b.bottom`),
    'scrollTop=' + await ev(`String(Math.round($('#scroll').scrollTop))`));
  await ev(`tapLevel(GAME.level - 4)`); await sleep(1200);
  check('рівень відкриває картку', await ev(`document.querySelector('#sheet').open`));
  await ev(`closeSheet()`);
});

// ------------------------------------------------------------ під капотом --
await withPage(B + '/tech', async ev => {
  await until(ev, `document.querySelectorAll('#flows details').length > 0`);
  check('усі сценарії з ланцюгами',
    await ev(`document.querySelectorAll('#flows details').length === 30`),
    await ev(`String(document.querySelectorAll('#flows details').length)`));
  check('кроки всередині', await ev(`document.querySelectorAll('#flows .step').length > 80`));
  check('виклики MCP', await ev(`document.querySelectorAll('#calls .tracerow').length > 3`));
  await ev(`showCall(0)`); await sleep(300);
  check('виклик показує input і output',
    await ev(`document.querySelector('#sheet2').open &&
      document.querySelector('#sheet2 .io').textContent.includes('Input') &&
      document.querySelectorAll('#sheet2 pre')[1].textContent.length > 40`));
  await ev(`document.querySelector('#sheet2').close()`);
  check('демо-дані редаговані', await ev(`document.querySelectorAll('#demo .demoset textarea').length === 4`));
  // Картка голосу тягне перелік із Respeecher — це мережа, треба дочекатись.
  await until(ev, `document.querySelector('#voice').textContent.includes('Модель')`, 40);
  check('картка голосу є', await ev(`!!document.querySelector('#voice') &&
    document.querySelector('#voice').textContent.includes('Модель')`));
  check('стан ключа показано чесно', await ev(`
    fetch('/api/voice').then(r=>r.json()).then(v => {
      const t = document.querySelector('#voice').textContent;
      return v.has_key ? t.includes('є ·') : t.includes('озвучує браузер');
    })`));
  check('накопичений стан видно', await ev(`document.querySelectorAll('#state .call').length === 4`));

  await ev(`$('#d-plus').value = JSON.stringify({price_uah:299,cashback:0.08,free_delivery_from_uah:500})`);
  await ev(`saveDemo('plus')`); await sleep(1200);
  check('правка демо-даних діє одразу',
    (await ev(`fetch('/api/plus').then(r=>r.json()).then(d=>String(d.price_uah))`)) === '299');
  await ev(`resetDemo('plus')`); await sleep(900);
  check('скидання повертає значення з коду',
    (await ev(`fetch('/api/plus').then(r=>r.json()).then(d=>String(d.price_uah))`)) === '199');
});

console.log(fails ? `\n${fails} перевірок впало` : '\nусе зелене');
process.exit(fails ? 1 : 0);
