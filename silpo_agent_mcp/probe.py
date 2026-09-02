"""Розвідка реального MCP «Сільпо»: python -m silpo_agent_mcp.probe [outdir]

Вивантажує повні схеми всіх tools і зразки відповідей READ-ONLY інструментів,
щоб фасадні tools писалися під справжні формати, а не під здогадки з доки.
НІЧОГО не змінює: жоден write-tool не викликається.
"""

from __future__ import annotations

import json
import os
import sys

import anyio

from .silpo import SilpoError, silpo

# Тільки читання. Порядок = від дешевого до важкого.
READ_ONLY = [
    ("silpo_get_my_profile", {}),
    ("silpo_get_my_food_restrictions", {}),
    ("silpo_get_my_family", {}),
    ("silpo_get_loyalty_info", {}),
    ("silpo_get_my_coupons", {}),
    ("silpo_get_my_promos", {}),
    ("silpo_get_promo_codes", {}),
    ("silpo_get_my_certificates", {}),
    ("silpo_get_my_premium_subscription", {}),
    ("silpo_get_my_favorites", {}),
    ("silpo_get_my_delivery_addresses", {}),
    ("silpo_get_my_offline_orders", {}),
    ("silpo_get_my_online_orders", {}),
    ("silpo_get_my_shopping_cart", {}),
    ("silpo_get_product_sets", {}),
    ("silpo_get_categories", {}),
    ("silpo_list_branches", {}),
]


def _trim(obj, depth=0):
    """Стискає великі списки до 2 елементів — нам потрібна ФОРМА, не обсяг."""
    if isinstance(obj, list):
        return [_trim(x, depth + 1) for x in obj[:2]] + (["…"] if len(obj) > 2 else [])
    if isinstance(obj, dict):
        return {k: _trim(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, str) and len(obj) > 300:
        return obj[:300] + "…"
    return obj


async def _run(outdir: str) -> int:
    os.makedirs(outdir, exist_ok=True)
    try:
        await silpo.start()
    except SilpoError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    tools_path = os.path.join(outdir, "silpo_tools.json")
    with open(tools_path, "w", encoding="utf-8") as f:
        json.dump(silpo.tools, f, ensure_ascii=False, indent=2)
    print(f"✅ схеми {len(silpo.tools)} tools → {tools_path}")

    samples: dict = {}
    for name, args in READ_ONLY:
        if not any(t["name"] == name for t in silpo.tools):
            samples[name] = {"__skipped__": "немає такого tool на сервері"}
            continue
        try:
            samples[name] = _trim(await silpo.call(name, args))
            print(f"  · {name}")
        except Exception as exc:
            samples[name] = {"__error__": f"{type(exc).__name__}: {exc}"}
            print(f"  ✗ {name}: {exc}", file=sys.stderr)

    samples_path = os.path.join(outdir, "silpo_samples.json")
    with open(samples_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"✅ зразки відповідей → {samples_path}")

    await silpo.stop()
    return 0


def main() -> int:
    outdir = sys.argv[1] if len(sys.argv) > 1 else "probe_out"
    return anyio.run(_run, outdir)


if __name__ == "__main__":
    raise SystemExit(main())
