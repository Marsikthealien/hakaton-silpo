"""Прогін усіх сценаріїв агента по ЖИВОМУ API «Сільпо».

Потребує дійсного токена (`python -m silpo_agent_mcp.login`). Нічого не купує
й не оформлює: пише лише в кошик і паки, як і сам агент.

    .venv/bin/python qa/smoke.py

Очікується «усе зелене». Що саме перевіряється — розділ «Перевірка» в README.
"""

import asyncio, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from silpo_agent_mcp import facade, insights, game, proposed, weights, packs

async def main():
    fails = []
    async def run(name, coro, ok=lambda r: True, note=lambda r: ''):
        t0 = time.perf_counter()
        try:
            r = await coro
            if isinstance(r, dict) and r.get('error'):
                raise RuntimeError(r['error'])
            good = ok(r)
        except Exception as e:
            fails.append(name); print(f' FAIL  {name:22} {type(e).__name__}: {str(e)[:110]}'); return None
        ms = int((time.perf_counter()-t0)*1000)
        if not good: fails.append(name)
        print(f'{"  OK  " if good else " FAIL "} {name:22} {ms:>6}ms  {note(r)}')
        return r

    has = lambda r: bool(r.get('items'))
    total = lambda r: f'{r["item_count"]} поз. · {r["total_uah"]} ₴' + (f' · {r.get("novelty","")}' if r.get('novelty') else '')

    await run('who_am_i', facade.who_am_i(), lambda r: r.get('name'),
              lambda r: f'{r["name"]}, {r["receipts"]["count"]} чеків')
    await run('weekly_pack', facade.weekly_pack(budget_uah=900, novelty='new'), has, total)
    await run('budget_pack', facade.budget_pack(700, 7, novelty='familiar'), has, total)
    await run('family_pack', facade.family_pack('вечеря', 900), has,
              lambda r: total(r) + ' · блок: ' + ','.join(r['blocked_for_everyone']))
    await run('kids_pack', insights.kids_pack(400), has, total)
    await run('meal_pack new', facade.meal_pack(meal='вечеря', max_uah=500, novelty='new'), has, total)
    await run('coupon_audit', insights.coupon_audit(), lambda r: r['coupons_total'] > 0, lambda r: r['headline'])
    await run('savings_report', insights.savings_report(), lambda r: r['paid_uah'] > 0, lambda r: r['headline'])
    await run('spend_report', insights.spend_report(),
              lambda r: r['categories'] and all('items' in c for c in r['categories']), lambda r: r['headline'])
    await run('plus_check', insights.plus_check(), lambda r: r['verdict'], lambda r: r['verdict'])
    await run('impulse_check', insights.impulse_check('кола'), lambda r: r['verdict'], lambda r: r['verdict'])
    await run('game_profile', game.game_profile(), lambda r: r['level'] > 1,
              lambda r: f'рівень {r["level"]}, {r["xp"]} XP, {r["achievements_done"]}/{r["achievements_total"]}')
    await run('achievements', game.achievements(), lambda r: r['total'] == 14, lambda r: f'{r["done"]}/{r["total"]}')
    await run('themed_branches', game.themed_branches(), lambda r: r['total'] >= 9 and r['visited'] >= 1, lambda r: f'{r["visited"]}/{r["total"]}')
    await run('swipe_deck', proposed.swipe_deck(6), lambda r: r['cards'], lambda r: f'{len(r["cards"])} карток')
    p = await run('pack_from_receipt', facade.pack_from_receipt(0), has, total)
    if p:
        await run('pack_add', facade.pack_add('молоко'), lambda r: r.get('added'),
                  lambda r: r['said'])
        await run('pack_set_qty', facade.pack_set_qty('молоко', 3), lambda r: r['qty'] == 3,
                  lambda r: r['said'])
        # Міняємо ПЕРШУ позицію самого пака, а не зашите «чипси»: чек —
        # живий, і одного дня в ньому лишились самі пакети для сміття.
        first = ((p.get('items') or [{}])[0].get('name') or 'молоко').split()[0]
        await run('pack_swap_named', facade.pack_swap_named(first),
                  lambda r: r.get('said'), lambda r: r['said'][:60])
        await run('pack_remove', facade.pack_remove('молоко'), lambda r: r.get('removed'),
                  lambda r: r['said'])
    if p:
        await run('picking_risk', insights.picking_risk(p['id']), lambda r: 'risky' in r, lambda r: r['headline'][:60])
        await run('optimize_pack', facade.optimize_pack(p['id']), lambda r: r is not None, lambda r: '')
        await run('precheck_pack', facade.precheck_pack(p['id']),
                  lambda r: [c['id'] for c in r['checks']] == ['delivery', 'weight', 'coupon', 'promo'],
                  lambda r: r['verdict'] + ' · ' + ' '.join(
                      ('✓' if c['ok'] else '✗' if c['ok'] is False else '–') for c in r['checks']))
        packs.delete(p['id'])
    print('\n' + ('усе зелене' if not fails else f'ВПАЛО: {", ".join(fails)}'))
    return 1 if fails else 0

sys.exit(asyncio.run(main()))
