// Точкова перевірка сценарію «Вечеря на всю сімʼю» у справжньому UI.
// Це головний флоу персональних даних: родина → підтвердження → страва →
// кошик → знижки. Кожен крок має бути видно на екрані гостя, а не лише в JSON.
//
//   chromium --headless=new --no-sandbox --remote-debugging-port=9222 about:blank &
//   .venv/bin/python -m uvicorn web.server:app --port 8000 &
//   node --experimental-websocket qa/family.mjs

import { withPage, sleep } from './cdp.mjs';

const B = process.env.PACKAGENT_URL || 'http://localhost:8000';
let fails = 0;
const check = (name, cond, extra = '') => {
  console.log(`${cond ? '  OK  ' : ' FAIL '} ${name}${extra ? ' — ' + extra : ''}`);
  if (!cond) fails++;
};
const until = async (ev, expr, tries = 120) => {
  for (let i = 0; i < tries; i++) { if (await ev(expr)) return true; await sleep(500); }
  return false;
};

await withPage(B, async (ev, shot, emulate) => {
  await emulate(1400, 950);
  await until(ev, `typeof runScenario === 'function' && !!document.querySelector('#scn-family')`);
  await sleep(800);
  check('порожній чат без кнопок-заготовок',
    await ev(`document.querySelectorAll('#quicks button').length === 0`));
  check('між tools на картці — стрілки',
    await ev(`document.querySelectorAll('#scn-family .tarr').length >= 4`));

  const before = await ev(`fetch('/api/trace?limit=1').then(r => r.json()).then(t => t.total)`);

  // Крок 1: родина — підтвердження, а не довідка.
  await ev(`runScenario('family')`);
  const asked = await until(ev, `!!document.querySelector('.panelmsg .go')`);
  check('картка «Хто вечеряє» з кнопкою підтвердження', asked,
    await ev(`(document.querySelector('.panelmsg .go') || {}).textContent || ''`));
  check('є кнопка «Змінити»',
    await ev(`[...document.querySelectorAll('.panelmsg .fbtn')].some(b => b.textContent.includes('Змінити'))`));
  check('тварина українською, не «cats»',
    await ev(`!/\\bcats\\b/.test(document.querySelector('.panelmsg').textContent)`));
  check('у телефоні немає назв методів',
    await ev(`![...document.querySelectorAll('#log .msg.sys')].some(m => m.textContent.includes('→'))`));

  // Крок 2: «Все правильно» → страва й кошик.
  await ev(`familyDinner()`);
  const built = await until(ev, `!!document.querySelector('.packmsg .prod')`);
  check('пак зібрався', built);
  if (!built) return;

  check('над кошиком — страва',
    await ev(`!!document.querySelector('.packmsg .dish .dt b')`),
    await ev(`(document.querySelector('.packmsg .dish .dt b') || {}).textContent || ''`));
  check('відхилена страва названа з іменем',
    await ev(`/Відхилено:.*\\(.+\\)/.test((document.querySelector('.packmsg .drej') || {}).textContent || '')`),
    await ev(`((document.querySelector('.packmsg .drej') || {}).textContent || '').slice(0, 120)`));
  // Між стравою і товарами джерел немає — вони під кошиком, у стовпчик,
  // одним коротким рядком кожне.
  check('джерела — під кошиком у стовпчик, коротко',
    await ev(`!document.querySelector('.packmsg .srcs') &&
      document.querySelectorAll('.packmsg .brief .bk').length >= 5 &&
      [...document.querySelectorAll('.packmsg .brief .bv')].every(v => v.textContent.length < 60)`),
    await ev(`[...document.querySelectorAll('.packmsg .brief .bk')].map(e => e.textContent).join(' · ')`));
  check('кожна позиція пояснює, звідки вона',
    await ev(`(() => { const rows = [...document.querySelectorAll('.packmsg .prod')];
      return rows.length > 0 && rows.every(r => r.querySelector('.why.because')); })()`),
    await ev(`document.querySelectorAll('.packmsg .prod').length + ' позицій'`));
  check('без службових рядків: «зібрано агентом», «замінено новим набором», «активацію записано»',
    await ev(`!/зібрано агентом|замінено новим набором|Активацію записано|Промо обрано під кошик/
      .test(document.querySelector('#log').textContent)`));
  check('кнопки «Знижки» немає, знижки показані самі',
    await ev(`![...document.querySelectorAll('.packmsg .go')].some(b => b.textContent.trim() === 'Знижки')
      && (document.querySelector('#offers') || {}).innerHTML.length > 0`));
  check('алергени не потрапили в сам пак',
    await ev(`![...document.querySelectorAll('.packmsg .prod .nm')]
      .some(e => /горіх|арахіс|мигдал|фундук/i.test(e.textContent))`));

  const calls = await ev(`fetch('/api/trace?limit=80').then(r => r.json())
    .then(t => t.calls.slice(-(t.total - ${before})).map(c => c.tool))`);
  const n = tool => calls.filter(c => c === tool).length;
  // Кеш родини живе 5 хв: другий прогін поспіль дає ×0 — теж правильно.
  check('родину прочитано щонайбільше раз, не двічі', n('silpo_get_my_family') <= 1,
    `get_my_family ×${n('silpo_get_my_family')}`);
  check('усі джерела в ланцюгу', ['silpo_wellbeing_state', 'silpo_get_taste_weights',
    'silpo_pantry_state', 'silpo_find_recipes', 'silpo_get_my_promos'].every(t => n(t) >= 1),
    calls.filter((c, i) => calls.indexOf(c) === i).map(c => c.replace('silpo_', '')).join(' → '));

  // Крок 3: підказка під паком → перевірка перед «Оформити» одним кроком.
  const chip = await ev(`[...document.querySelectorAll('#quicks button')]
    .find(b => /перед оформленням/i.test(b.textContent))?.textContent || ''`);
  check('під паком є підказка «Перевір перед оформленням»', !!chip);
  await ev(`quick('Перевір перед оформленням')`);
  const checked = await until(ev, `!!document.querySelector('.precheck .pf')`);
  check('картка перевірки зʼявилась у телефоні', checked);
  check('у ній чотири рядки: доставка · вага · купон · промо',
    await ev(`[...document.querySelectorAll('.precheck .prow .pt b')].map(b => b.textContent).join(' · ')
      === 'Топати чи замовити · Вага кошика · Купон · Промо'`),
    await ev(`[...document.querySelectorAll('.precheck .prow .pt b')].map(b => b.textContent).join(' · ')`));
  check('перевірено саме цей пак, а не останній створений',
    await ev(`(document.querySelector('.precheck .ph .soft') || {}).textContent.includes(PACK.name)`),
    await ev(`(document.querySelector('.precheck .ph .soft') || {}).textContent`));
  check('кожен рядок називає tools, з яких узятий',
    await ev(`[...document.querySelectorAll('.precheck .prow code')].every(c => c.textContent.trim().length > 0)`));

  await shot('qa-family.png');
  console.log('  ..  знімок: qa-family.png');
});

console.log(fails ? `\nВПАЛО: ${fails}` : '\nусе зелене');
process.exit(fails ? 1 : 0);
