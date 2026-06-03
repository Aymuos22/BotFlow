"""
smoke_test_100.py — Fire 100 messages through RAGService directly (no HTTP).

Usage (from repo root, inside container):
    python scripts/smoke_test_100.py
    python scripts/smoke_test_100.py --company-id 55b3e336-62cf-45ab-95f6-0bb9432af326
    python scripts/smoke_test_100.py --out /tmp/results.md
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
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

from app.core.config import get_settings  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.integrations.embeddings.client import get_embedding_client  # noqa: E402
from app.integrations.llm.client import get_llm_client  # noqa: E402
from app.integrations.weaviate.client import WeaviateClient  # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.services.fallback_service import FallbackService  # noqa: E402
from app.services.rag_service import RAGService  # noqa: E402

SKRANGE = UUID("55b3e336-62cf-45ab-95f6-0bb9432af326")

# ---------------------------------------------------------------------------
# 100 test messages
# ---------------------------------------------------------------------------
MESSAGES = [
    # ── English – product price ───────────────────────────────────────────────
    ("EN-price-01", "what is the price of Liv Muztang"),
    ("EN-price-02", "how much does Kaama Gold cost?"),
    ("EN-price-03", "price of ultimate hammer"),
    ("EN-price-04", "tell me the cost of sandy rx"),
    ("EN-price-05", "whats the mrp of jaam e ishq"),
    ("EN-price-06", "how much for macamo"),
    ("EN-price-07", "price of herbo 65 pleese"),        # typo: pleese
    ("EN-price-08", "cost of ayush for menn"),           # typo: menn
    ("EN-price-09", "extra time kit prise?"),            # typo: prise
    ("EN-price-10", "liv mustang price"),                # misspelled: mustang
    # ── English – product/problem queries ─────────────────────────────────────
    ("EN-prod-01", "which product is best for stamina"),
    ("EN-prod-02", "what do you have for men's health"),
    ("EN-prod-03", "best medicine for weak erection"),
    ("EN-prod-04", "do you sell anything for timing"),
    ("EN-prod-05", "is there something for sexual weakness"),
    ("EN-prod-06", "i have early discharge problem what to take"),
    ("EN-prod-07", "what helps with low sperm count"),
    ("EN-prod-08", "anything for penis size"),
    ("EN-prod-09", "i want to improve my sex life"),
    ("EN-prod-10", "what is liv muztang used for"),
    # ── English – incomplete / vague ──────────────────────────────────────────
    ("EN-vague-01", "price"),
    ("EN-vague-02", "tell me about"),
    ("EN-vague-03", "I want"),
    ("EN-vague-04", "how to"),
    ("EN-vague-05", "best product for"),
    ("EN-vague-06", "is it good"),
    ("EN-vague-07", "can you help"),
    ("EN-vague-08", "what about the"),
    ("EN-vague-09", "I need something for"),
    ("EN-vague-10", "hello"),
    # ── English – heavy typos ─────────────────────────────────────────────────
    ("EN-typo-01", "waht is the prise of kaama gold?"),
    ("EN-typo-02", "i want to bye liv mustang"),
    ("EN-typo-03", "plz tel me abot ur products"),
    ("EN-typo-04", "dis product is for wat?"),
    ("EN-typo-05", "i hvae erectile dysfuntion"),
    ("EN-typo-06", "how do i ordr this"),
    ("EN-typo-07", "wht is cod prce"),
    ("EN-typo-08", "is ther any discunt"),
    ("EN-typo-09", "i want prepiad offer details"),
    ("EN-typo-10", "ur products are availble on delivry?"),
    # ── Hindi – product price ─────────────────────────────────────────────────
    ("HI-price-01", "Liv Muztang ki price kya hai"),
    ("HI-price-02", "Kaama Gold kitne ka hai"),
    ("HI-price-03", "Ultimate Hammer ka dam kya hai"),
    ("HI-price-04", "Sandy RX ki kimat batao"),
    ("HI-price-05", "Jaam e Ishq ka rate kya hai"),
    ("HI-price-06", "Macamo kitne mein milega"),
    ("HI-price-07", "Herbo 65 ki price kitni hai"),
    ("HI-price-08", "Ayush for Men kya price hai"),
    ("HI-price-09", "Extra Time kit khareedna hai price batao"),
    ("HI-price-10", "prepaid offer kya hai"),
    # ── Hindi – problem / need ────────────────────────────────────────────────
    ("HI-prod-01", "mardana kamzori ke liye kya lena chahiye"),
    ("HI-prod-02", "timing badhane ki dawa batao"),
    ("HI-prod-03", "sex power ke liye kaunsi dawa best hai"),
    ("HI-prod-04", "shighrapatan ka ilaj chahiye"),
    ("HI-prod-05", "mujhe neend nahi aati koi dawa hai"),
    ("HI-prod-06", "baal jhadte hain koi oil batao"),
    ("HI-prod-07", "sugar control karne ki dawa chahiye"),
    ("HI-prod-08", "pet ki problem ke liye kya lena chahiye"),
    ("HI-prod-09", "liver ke liye koi medicine hai"),
    ("HI-prod-10", "safed daag ka ilaj chahiye"),
    # ── Hindi – typos / incomplete ────────────────────────────────────────────
    ("HI-typo-01", "liv muztng ki keemat"),
    ("HI-typo-02", "kma gold price"),
    ("HI-typo-03", "mardna takat wali"),
    ("HI-typo-04", "timing ki dawa do"),
    ("HI-typo-05", "sex ke liye"),
    ("HI-typo-06", "balo ka oil"),
    ("HI-typo-07", "sugar ki"),
    ("HI-typo-08", "ye product kaise use kre"),
    ("HI-typo-09", "COD pe milega kya"),
    ("HI-typo-10", "prepaid mein kya milta hai"),
    # ── Hinglish – product queries ────────────────────────────────────────────
    ("HL-prod-01", "bhai Liv Muztang ka price kya hai yaar"),
    ("HL-prod-02", "Ultimate Hammer lena chahta hoon kitna padega"),
    ("HL-prod-03", "Kaama Gold COD pe milega kya"),
    ("HL-prod-04", "Sandy RX prepaid offer ke saath kitna hoga"),
    ("HL-prod-05", "Herbo 65 order karna hai price bata"),
    ("HL-prod-06", "Macamo wala product kya karta hai"),
    ("HL-prod-07", "Ayush for Men good hai kya"),
    ("HL-prod-08", "Extra time kit se kya hota hai exactly"),
    ("HL-prod-09", "jaam e ishq kya hota hai"),
    ("HL-prod-10", "liv muztang plus vs liv muztang difference"),
    # ── Hinglish – problem queries ────────────────────────────────────────────
    ("HL-need-01", "yaar mujhe stamina badhana hai kya lu"),
    ("HL-need-02", "sex mein timing bahut kam hai help karo"),
    ("HL-need-03", "bhai weakness bahut hai body mein kya khayen"),
    ("HL-need-04", "erection nahi hoti properly koi solution hai"),
    ("HL-need-05", "discharge bahut jaldi ho jata hai medicine chahiye"),
    ("HL-need-06", "baal bahut girte hain koi tel batao"),
    ("HL-need-07", "sugar high hai koi dawa batao bhai"),
    ("HL-need-08", "pet mein gas bahut hoti hai remedy"),
    ("HL-need-09", "liver weak hai koi medicine suggest karo"),
    ("HL-need-10", "bhai weight loss ke liye kuch hai kya"),
    # ── Edge cases ────────────────────────────────────────────────────────────
    ("EDGE-01", "stop"),
    ("EDGE-02", "hi"),
    ("EDGE-03", "ok thanks"),
    ("EDGE-04", "What is your return policy?"),
    ("EDGE-05", "I want to speak to a human"),
    ("EDGE-06", "Can I pay with UPI?"),
    ("EDGE-07", "Do you deliver to Mumbai?"),
    ("EDGE-08", "What are your timings?"),
    ("EDGE-09", "Is there any side effect?"),
    ("EDGE-10", "How long does it take to show results?"),
]

assert len(MESSAGES) == 100, f"Got {len(MESSAGES)} messages, expected 100"

_PASS_TYPES = {"rag", "fallback"}


async def run(company_id: UUID, out_path: Path) -> None:
    s = get_settings()
    weaviate = WeaviateClient(
        url=s.weaviate_url,
        api_key=s.weaviate_api_key,
        timeout=s.weaviate_timeout_seconds,
    )
    passed = failed = 0
    results: list[dict] = []

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

            for i, (tag, msg) in enumerate(MESSAGES, 1):
                t0 = time.perf_counter()
                try:
                    raw = await rag.process_query(
                        company_id=company_id,
                        query=msg,
                        conversation_id=None,
                        message_id=None,
                        background_tasks=None,
                    )
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)
                    answer = raw.get("answer") or ""
                    rtype = raw.get("response_type", "?")
                    lang = raw.get("language", "?")
                    score = raw.get("top_score")
                    fallback = raw.get("fallback_triggered", False)
                    ok = bool(answer) and rtype in _PASS_TYPES
                    status = "PASS" if ok else "FAIL"
                    if ok:
                        passed += 1
                    else:
                        failed += 1
                except Exception as exc:
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)
                    answer = f"[ERROR] {exc}"
                    rtype = "error"; lang = "?"; score = None; fallback = False
                    status = "ERR"; failed += 1

                results.append({
                    "n": i, "tag": tag, "status": status,
                    "msg": msg, "type": rtype, "lang": lang,
                    "score": score, "fallback": fallback,
                    "ms": elapsed_ms, "answer": answer,
                })
                icon = "✅" if status == "PASS" else "❌"
                score_str = f"{score:.3f}" if score is not None else "  — "
                fb = " [FB]" if fallback else ""
                print(
                    f"{icon} [{i:03d}] {tag:<12} {elapsed_ms:>5}ms "
                    f"[{rtype}/{lang}] score={score_str}{fb}  {msg[:55]!r}"
                )
    finally:
        await weaviate.aclose()
        await engine.dispose()

    # ── Write Markdown report ────────────────────────────────────────────────
    lines = [
        "# Smoke Test — 100 Messages",
        f"\n**Pass:** {passed} / 100  |  **Fail/Error:** {failed} / 100\n",
        "---\n",
        "| # | Tag | Status | Type | Lang | Score | ms | Fallback | Message | Answer (first 200 chars) |",
        "|---|-----|--------|------|------|-------|----|----------|---------|--------------------------|",
    ]
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        score = f"{r['score']:.3f}" if r["score"] is not None else "—"
        fb = "yes" if r["fallback"] else "no"
        ans = (r["answer"] or "")[:200].replace("\n", " ").replace("|", "｜")
        msg_cell = r["msg"][:60].replace("|", "｜")
        lines.append(
            f"| {r['n']} | {r['tag']} | {icon} {r['status']} | {r['type']} | {r['lang']} "
            f"| {score} | {r['ms']} | {fb} | {msg_cell} | {ans} |"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"  PASS: {passed}/100   FAIL/ERR: {failed}/100")
    print(f"  Report: {out_path}")
    print(f"{'='*60}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--company-id", default=str(SKRANGE))
    p.add_argument("--out", default="/tmp/smoke_test_100_results.md")
    args = p.parse_args()
    asyncio.run(run(UUID(args.company_id), Path(args.out)))


if __name__ == "__main__":
    main()
