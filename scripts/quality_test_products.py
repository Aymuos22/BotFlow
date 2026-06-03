"""
quality_test_products.py
Targeted quality test for the 11 Skinrange men's-health products.

For every question we know the expected answer elements (price, product name, URL)
so we can score CORRECTNESS, not just "did it reply".

Usage (inside the API container):
    python scripts/quality_test_products.py
    python scripts/quality_test_products.py --out /tmp/quality_report.md
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.config import get_settings           # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.embeddings.client import get_embedding_client  # noqa: E402
from app.integrations.llm.client import get_llm_client  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.services.fallback_service import FallbackService  # noqa: E402
from app.services.rag_service import RAGService  # noqa: E402

SKRANGE = UUID("55b3e336-62cf-45ab-95f6-0bb9432af326")


# ═══════════════════════════════════════════════════════════════════════════
# Product truth table
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Product:
    name: str
    mrp: int
    cod: int
    prepaid: int
    url: str
    # short alias tokens that should appear in correct answers
    name_tokens: list[str] = field(default_factory=list)

PRODUCTS = [
    Product("Liv Muztang",           5999, 4999, 4499, "https://skinrange.com/products/liv-muztang",       ["liv muztang"]),
    Product("Liv Muztang REX",       9374, 9374, 8436, "https://skinrange.com/products/liv-muztang-rex",   ["muztang rex"]),
    Product("Liv Muztang Plus",      9375, 7499, 6749, "https://skinrange.com/products/liv-muztang-plus",  ["muztang plus"]),
    Product("Herbo 65",              4687, 4687, 4218, "https://skinrange.com/products/herbo-365",          ["herbo 65", "herbo65"]),
    Product("Ultimate Hammer",       1874, 1799, 1619, "https://skinrange.com/products/ultimate-hammer",    ["ultimate hammer"]),
    Product("Kaama Gold",            2999, 2499, 2249, "https://skinrange.com/products/kaama-gold",         ["kaama gold", "kama gold"]),
    Product("Ayush for Men",         2900, 2900, 2610, "https://skinrange.com/products/ayush-for-men",      ["ayush"]),
    Product("Extra Time Kit",        3749, 3599, 3239, "https://skinrange.com/products/extra-time",         ["extra time"]),
    Product("Sandy RX",             14063,14063,12656, "https://skinrange.com/products/sandy-rx",           ["sandy rx", "sandy"]),
    Product("Jaam e Ishq",           7000, 5100, 4590, "https://skinrange.com/products/jaam-e-ishq",        ["jaam", "ishq"]),
    Product("Macamo The Latin Lava", 9999, 9999, 8999, "https://skinrange.com/products/macamo",             ["macamo"]),
]


# ═══════════════════════════════════════════════════════════════════════════
# Question templates per product
# ═══════════════════════════════════════════════════════════════════════════

def questions_for(p: Product) -> list[dict]:
    n = p.name
    return [
        # ── Direct price ───────────────────────────────────────────────────
        {
            "tag": "EN-price-direct",
            "msg": f"what is the price of {n}",
            "expect_nums": [str(p.cod)],
            "expect_words": [],
            "category": "price",
        },
        {
            "tag": "EN-price-mrp",
            "msg": f"what is the MRP of {n}",
            "expect_nums": [str(p.mrp)],
            "expect_words": [],
            "category": "price",
        },
        {
            "tag": "EN-price-prepaid",
            "msg": f"what is the prepaid price of {n}",
            "expect_nums": [str(p.prepaid)],
            "expect_words": [],
            "category": "price",
        },
        {
            "tag": "EN-price-cod",
            "msg": f"what is the cash on delivery price of {n}",
            "expect_nums": [str(p.cod)],
            "expect_words": [],
            "category": "price",
        },
        # ── Hinglish price ────────────────────────────────────────────────
        {
            "tag": "HL-price-kya",
            "msg": f"{n} ki price kya hai",
            "expect_nums": [str(p.cod)],
            "expect_words": [],
            "category": "price",
        },
        {
            "tag": "HL-price-kitna",
            "msg": f"{n} kitne ka hai",
            "expect_nums": [str(p.cod)],
            "expect_words": [],
            "category": "price",
        },
        {
            "tag": "HL-price-cod",
            "msg": f"{n} COD pe kitne mein milega",
            "expect_nums": [str(p.cod)],
            "expect_words": [],
            "category": "price",
        },
        {
            "tag": "HL-price-prepaid",
            "msg": f"{n} prepaid offer mein kitna padega",
            "expect_nums": [str(p.prepaid)],
            "expect_words": [],
            "category": "price",
        },
        # ── Typo / misspelled ─────────────────────────────────────────────
        {
            "tag": "EN-typo-price",
            "msg": f"waht is the prise of {n.lower().replace('a', 'aa', 1)}",
            "expect_nums": [str(p.cod)],
            "expect_words": [],
            "category": "typo",
        },
        {
            "tag": "HL-typo-price",
            "msg": f"{n.split()[0].lower()} ki keemat kya hai",
            "expect_nums": [str(p.cod)],
            "expect_words": [],
            "category": "typo",
        },
        # ── What is / description ─────────────────────────────────────────
        {
            "tag": "EN-desc",
            "msg": f"what is {n} used for",
            "expect_nums": [],
            "expect_words": p.name_tokens,
            "category": "description",
        },
        {
            "tag": "HL-desc",
            "msg": f"{n} kya karta hai",
            "expect_nums": [],
            "expect_words": p.name_tokens,
            "category": "description",
        },
        # ── Buy / order ───────────────────────────────────────────────────
        {
            "tag": "EN-buy",
            "msg": f"I want to buy {n}",
            "expect_nums": [],
            "expect_words": p.name_tokens,
            "category": "buy",
        },
        {
            "tag": "HL-buy",
            "msg": f"{n} kharidna hai kaise order karu",
            "expect_nums": [],
            "expect_words": p.name_tokens,
            "category": "buy",
        },
    ]


ALL_QUESTIONS: list[dict] = []
for prod in PRODUCTS:
    for q in questions_for(prod):
        q["product"] = prod
        ALL_QUESTIONS.append(q)

TOTAL = len(ALL_QUESTIONS)


# ═══════════════════════════════════════════════════════════════════════════
# Scoring helpers
# ═══════════════════════════════════════════════════════════════════════════

def _score(answer: str, expect_nums: list[str], expect_words: list[str]) -> tuple[bool, list[str]]:
    """Return (passed, list_of_missing_items).

    Numbers: ALL must appear.
    Words: name_tokens are alternatives — at least ONE must appear (OR semantics).
    """
    ans_lower = answer.lower()
    missing = []
    for num in expect_nums:
        # accept num with/without commas, e.g. 4999 or 4,999
        raw = re.sub(r"\D", "", num)
        found = raw in re.sub(r"\D", "", answer)
        if not found:
            missing.append(num)
    # expect_words are alternative aliases — pass if ANY one matches
    if expect_words and not any(w.lower() in ans_lower for w in expect_words):
        missing.append(f"[any of: {', '.join(expect_words)}]")
    return (len(missing) == 0, missing)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

async def run(company_id: UUID, out_path: Path) -> None:
    s = get_settings()
    weaviate = WeaviateClient(
        url=s.weaviate_url,
        api_key=s.weaviate_api_key,
        timeout=s.weaviate_timeout_seconds,
    )

    results: list[dict] = []
    passed = failed = errors = 0

    try:
        async with AsyncSessionLocal() as db:
            rag = RAGService(
                config_repo=CompanyConfigRepository(db),
                weaviate_client=weaviate,
                llm_client=get_llm_client(),
                fallback_service=FallbackService(),
                default_top_k=s.rag_top_k,
                default_score_threshold=s.rag_score_threshold,
                default_hybrid_alpha=s.rag_hybrid_alpha,
                default_conversation_turns=s.rag_conversation_turns,
                augment_search_with_history=s.rag_augment_search_with_history,
                embedding_client=get_embedding_client(),
            )

            for i, q in enumerate(ALL_QUESTIONS, 1):
                prod: Product = q["product"]
                t0 = time.perf_counter()
                try:
                    raw = await rag.process_query(
                        company_id=company_id,
                        query=q["msg"],
                        conversation_id=None,
                        message_id=None,
                        background_tasks=None,
                    )
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)
                    answer = raw.get("answer") or ""
                    rtype   = raw.get("response_type", "?")
                    lang    = raw.get("language", "?")
                    score   = raw.get("top_score")
                    fb      = raw.get("fallback_triggered", False)

                    ok, missing = _score(answer, q["expect_nums"], q["expect_words"])
                    status = "PASS" if ok else "FAIL"
                    if ok:
                        passed += 1
                    else:
                        failed += 1
                except Exception as exc:
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)
                    answer = f"[ERROR] {exc}"
                    rtype = "error"; lang = "?"; score = None; fb = False
                    ok = False; missing = ["exception"]; status = "ERR"; errors += 1; failed += 1

                results.append({
                    "n": i, "product": prod.name, "tag": q["tag"],
                    "cat": q["category"], "msg": q["msg"],
                    "status": status, "ok": ok, "missing": missing,
                    "type": rtype, "lang": lang, "score": score,
                    "fallback": fb, "ms": elapsed_ms, "answer": answer,
                })

                icon = "✅" if ok else "❌"
                miss_str = f" ← missing {missing}" if missing else ""
                score_s = f"{score:.3f}" if score is not None else "  — "
                print(
                    f"{icon} [{i:03d}/{TOTAL}] {prod.name:<24} [{q['tag']:<18}] "
                    f"{elapsed_ms:>5}ms [{rtype}/{lang}] score={score_s}{miss_str}"
                )

    finally:
        await weaviate.aclose()
        await engine.dispose()

    # ── Per-product summary ──────────────────────────────────────────────────
    from collections import defaultdict
    by_product: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0, "cats": defaultdict(lambda: {"pass": 0, "fail": 0})})
    by_cat: dict[str, dict]     = defaultdict(lambda: {"pass": 0, "fail": 0})
    by_tag: dict[str, dict]     = defaultdict(lambda: {"pass": 0, "fail": 0})
    for r in results:
        key = "pass" if r["ok"] else "fail"
        by_product[r["product"]][key] += 1
        by_product[r["product"]]["cats"][r["cat"]][key] += 1
        by_cat[r["cat"]][key] += 1
        by_tag[r["tag"]][key] += 1

    # ── Print console summary ────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  TOTAL: {TOTAL}  |  PASS: {passed}  |  FAIL: {failed}  |  ERRORS: {errors}")
    print(f"  Pass rate: {100*passed//TOTAL}%")
    print(f"{'='*70}")
    print("\nBy Category:")
    for cat, v in sorted(by_cat.items()):
        t = v["pass"] + v["fail"]
        pct = 100 * v["pass"] // t if t else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        print(f"  {cat:<14} {bar} {pct:>3}%  ({v['pass']}/{t})")

    print("\nBy Product:")
    for pname, v in by_product.items():
        t = v["pass"] + v["fail"]
        pct = 100 * v["pass"] // t if t else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        cats_summary = "  ".join(
            f"{c}:{cv['pass']}/{cv['pass']+cv['fail']}"
            for c, cv in v["cats"].items()
        )
        print(f"  {pname:<26} {bar} {pct:>3}%  ({v['pass']}/{t})  {cats_summary}")

    print("\nFailing question templates:")
    for tag, v in sorted(by_tag.items(), key=lambda x: x[1]["fail"], reverse=True):
        if v["fail"] > 0:
            t = v["pass"] + v["fail"]
            print(f"  {tag:<22}  fail={v['fail']}/{t}")

    # ── Write Markdown report ────────────────────────────────────────────────
    lines = [
        "# Product Quality Test Report",
        f"\n**Total questions:** {TOTAL}  |  **Pass:** {passed}  |  **Fail:** {failed}  |  **Pass rate:** {100*passed//TOTAL}%\n",
        "---",
        "\n## Results by Category\n",
        "| Category | Pass | Fail | Rate |",
        "|----------|------|------|------|",
    ]
    for cat, v in sorted(by_cat.items()):
        t = v["pass"] + v["fail"]
        pct = 100 * v["pass"] // t if t else 0
        lines.append(f"| {cat} | {v['pass']} | {v['fail']} | {pct}% |")

    lines += [
        "\n## Results by Product\n",
        "| Product | Pass | Fail | Rate | price | description | buy | typo |",
        "|---------|------|------|------|-------|-------------|-----|------|",
    ]
    for pname, v in by_product.items():
        t = v["pass"] + v["fail"]
        pct = 100 * v["pass"] // t if t else 0
        cats = v["cats"]
        def _c(cat: str) -> str:
            cv = cats.get(cat, {"pass": 0, "fail": 0})
            return f"{cv['pass']}/{cv['pass']+cv['fail']}"
        lines.append(f"| {pname} | {v['pass']} | {v['fail']} | {pct}% | {_c('price')} | {_c('description')} | {_c('buy')} | {_c('typo')} |")

    lines += [
        "\n## Failing Templates\n",
        "| Template | Fail | Total |",
        "|----------|------|-------|",
    ]
    for tag, v in sorted(by_tag.items(), key=lambda x: x[1]["fail"], reverse=True):
        if v["fail"] > 0:
            lines.append(f"| {tag} | {v['fail']} | {v['pass']+v['fail']} |")

    lines += [
        "\n## Detailed Results\n",
        "| # | Product | Tag | Cat | Status | Type | Lang | Score | FB | ms | Missing | Answer (first 220 chars) |",
        "|---|---------|-----|-----|--------|------|------|-------|----|----|---------|--------------------------|",
    ]
    for r in results:
        icon = "✅" if r["ok"] else "❌"
        score = f"{r['score']:.3f}" if r["score"] is not None else "—"
        fb = "Y" if r["fallback"] else "N"
        miss = ", ".join(r["missing"]) if r["missing"] else "—"
        ans = (r["answer"] or "")[:220].replace("\n", " ").replace("|", "｜")
        lines.append(
            f"| {r['n']} | {r['product']} | {r['tag']} | {r['cat']} | {icon} {r['status']} "
            f"| {r['type']} | {r['lang']} | {score} | {fb} | {r['ms']} | {miss} | {ans} |"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  Report saved: {out_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--company-id", default=str(SKRANGE))
    p.add_argument("--out", default="/tmp/quality_report.md")
    args = p.parse_args()
    asyncio.run(run(UUID(args.company_id), Path(args.out)))


if __name__ == "__main__":
    main()
