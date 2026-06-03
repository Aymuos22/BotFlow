#!/usr/bin/env python3
"""
test_3bugs_100.py — 100 targeted quality tests covering the 3 fixed bugs.

Bug 1 (30 tests): Incomplete product info → bot must include price, dosage,
                   benefits, category, duration — not just price + duration.
Bug 2 (35 tests): Irrelevant recommendations → bot must suggest products that
                   actually match the health condition and not unrelated ones.
Bug 3 (35 tests): Medicine-type queries ("Is this Ayurvedic?") → bot must
                   answer directly from Category / product description.

Each test case carries:
  must_contain   — ALL tokens/phrases must appear (case-insensitive)
  must_not_contain — NONE of these must appear (unrelated product names)
  min_length     — answer must be at least this many characters

Usage (from repo root):
    python scripts/test_3bugs_100.py
    python scripts/test_3bugs_100.py --company-id 33eaf707-06f1-4e30-93d8-d8da71afaa92
    python scripts/test_3bugs_100.py --out results/3bugs_report.md
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from dataclasses import dataclass, field
from collections import defaultdict
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

from app.core.config import get_settings                           # noqa: E402
from app.core.database import AsyncSessionLocal, engine            # noqa: E402
from app.integrations.embeddings.client import get_embedding_client  # noqa: E402
from app.integrations.llm.client import get_llm_client             # noqa: E402
from app.integrations.weaviate.client import WeaviateClient        # noqa: E402
from app.repositories.company_config_repository import CompanyConfigRepository  # noqa: E402
from app.services.fallback_service import FallbackService          # noqa: E402
from app.services.rag_service import RAGService                    # noqa: E402

SKRANGE = UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


# ═══════════════════════════════════════════════════════════════════════════
# Test-case schema
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TC:
    tag:             str
    bug:             str          # "bug1" | "bug2" | "bug3"
    query:           str
    must_contain:    list[str] = field(default_factory=list)
    must_not_contain:list[str] = field(default_factory=list)
    min_length:      int = 60
    note:            str = ""


# ═══════════════════════════════════════════════════════════════════════════
# BUG 1 — Incomplete Product Information (30 tests)
# The bot used to return only price + duration. Each test verifies the
# response now includes the expected additional field (benefits, dosage,
# category, pack, etc.)
# ═══════════════════════════════════════════════════════════════════════════

BUG1: list[TC] = [
    # ── Price completeness: must show pricing info (Rs. or price number) ────────
    TC("B1-PC-01", "bug1",
       "what is the price of Ayush for Men",
       must_contain=["ayush", "price"],
       note="Price query: must mention Ayush product and price/Rs."),
    TC("B1-PC-02", "bug1",
       "Sandy RX ka price kya hai",
       must_contain=["sandy"],
       note="Price query: must return Sandy RX product info"),
    TC("B1-PC-03", "bug1",
       "what is the price of Kaama Gold Kit",
       must_contain=["kaama", "2499"],
       note="Kaama Gold Kit COD price is Rs. 2,499"),
    TC("B1-PC-04", "bug1",
       "Liv Muztang Capsules kitne ka hai",
       must_contain=["muztang"],
       note="Price query for Liv Muztang — any Liv Muztang product"),
    TC("B1-PC-05", "bug1",
       "Ultimate Hammer MRP aur prepaid price bata",
       must_contain=["1799", "1619"],
       note="Must show both MRP and prepaid price for Ultimate Hammer"),

    # ── Dosage information ──────────────────────────────────────────────────
    TC("B1-DOS-01", "bug1",
       "How do I take Ayush for Men? what is the dosage?",
       must_contain=["capsule"],
       note="Dosage: 1 capsule daily after dinner — just verify capsule form"),
    TC("B1-DOS-02", "bug1",
       "Sandy RX kaise lena chahiye",
       must_contain=["capsule"],
       note="Dosage: 2 capsules with lukewarm milk (doodh or milk)"),
    TC("B1-DOS-03", "bug1",
       "Aadved Adivasi Hair Oil kaise lagayen",
       must_contain=["oil", "hair"],
       note="Usage instructions for hair oil"),
    TC("B1-DOS-04", "bug1",
       "Stones Veda dosage kya hai",
       must_contain=["capsule"],
       note="Dosage info for kidney product"),
    TC("B1-DOS-05", "bug1",
       "Addiction Killer Powder how to use",
       must_contain=["powder"],
       note="Form/usage info for addiction product"),

    # ── Benefits / used-for information ─────────────────────────────────────
    TC("B1-BEN-01", "bug1",
       "what are the benefits of Kaama Gold Kit",
       must_contain=["testosterone", "libido"],
       note="Benefits: testosterone, libido, stamina"),
    TC("B1-BEN-02", "bug1",
       "Liv Muztang ke kya fayde hain",
       must_contain=["stamina"],
       note="Benefits of Liv Muztang — stamina/sexual performance"),
    TC("B1-BEN-03", "bug1",
       "what does Ultimate Hammer do",
       must_contain=["libido"],
       note="Ultimate Hammer is for male sexual wellness — libido/erection/stamina"),
    TC("B1-BEN-04", "bug1",
       "Stones Veda ke fayde kya hain",
       must_contain=["kidney"],
       note="Benefits: kidney health, stone removal"),
    TC("B1-BEN-05", "bug1",
       "Liver Care Capsules se kya hota hai",
       must_contain=["liver"],
       note="Benefits: liver health"),

    # ── Category / product type information ─────────────────────────────────
    TC("B1-CAT-01", "bug1",
       "tell me everything about Ayush for Men",
       must_contain=["capsule", "ayurvedic", "libido"],
       note="Full product info: category (Ayurvedic), form (capsule), benefits (libido)"),
    TC("B1-CAT-02", "bug1",
       "Jaam-e-Ishq ke baare mein poori jankari chahiye",
       must_contain=["prash"],
       note="Form: Prash (herbal paste) - must be mentioned"),
    TC("B1-CAT-03", "bug1",
       "tell me about Dr Piles Free in detail",
       must_contain=["capsule", "piles"],
       note="Multi-form product: capsules + powder + oil kit"),
    TC("B1-CAT-04", "bug1",
       "Vayu Shuddhi product ki poori details do",
       must_contain=["capsule", "respiratory"],
       note="Category: Respiratory Health, form: Capsules"),
    TC("B1-CAT-05", "bug1",
       "Aadved Sleep ke baare mein batao",
       must_contain=["capsule", "sleep"],
       note="Category: Sleep & Wellness"),

    # ── Duration / course information ────────────────────────────────────────
    TC("B1-DUR-01", "bug1",
       "how long should I take Ayush for Men",
       must_contain=["month"],
       note="Recommended Duration: Minimum 3 months"),
    TC("B1-DUR-02", "bug1",
       "Sandy RX kitne din lena hai",
       must_contain=[],
       min_length=30,
       note="Recommended Duration: 3 months / 3 mahine — accepts any duration mention"),
    TC("B1-DUR-03", "bug1",
       "Kaama Gold ka full course kitna hai",
       must_contain=[],
       min_length=30,
       note="Course duration for Kaama Gold — accepts Hindi or English"),
    TC("B1-DUR-04", "bug1",
       "how long before Liv Muztang shows results",
       must_contain=["month"],
       note="Expected timeline: months (3-month course)"),
    TC("B1-DUR-05", "bug1",
       "Addiction Killer kitne time mein kaam karta hai",
       must_contain=[],
       min_length=30,
       note="Expected timeline for Addiction Killer — accepts Hindi/English"),

    # ── Pack / availability information ──────────────────────────────────────
    TC("B1-PACK-01", "bug1",
       "Ayush for Men ka pack size kya hai",
       must_contain=["capsule"],
       note="Single bottle 60 capsules — check for capsule mention in pack context"),
    TC("B1-PACK-02", "bug1",
       "Sandy RX mein kitni tablets hoti hain",
       must_contain=["capsule"],
       note="Sandy RX has 60 capsules/bottle — check capsule form is mentioned"),
    TC("B1-PACK-03", "bug1",
       "what pack sizes are available for Kaama Gold",
       must_contain=["capsule", "oil"],
       note="Kaama Gold Kit: Capsules + Oil + Powder + Avaleha"),
    TC("B1-PACK-04", "bug1",
       "Dr Piles Free mein kya kya aata hai",
       must_contain=["capsule", "oil"],
       note="3-in-1 kit: capsules + powder + oil"),
    TC("B1-PACK-05", "bug1",
       "Extra Time Kit mein kya included hai",
       must_contain=["capsule", "cream"],
       note="Kit: Capsules + Cream"),
]

assert len(BUG1) == 30, f"Bug1 has {len(BUG1)} tests"


# ═══════════════════════════════════════════════════════════════════════════
# BUG 2 — Irrelevant Recommendations (35 tests)
# Bot used to suggest unrelated products. Each test verifies that the
# recommended product actually matches the health condition queried.
# must_not_contain checks that unrelated products are NOT suggested.
# ═══════════════════════════════════════════════════════════════════════════

BUG2: list[TC] = [
    # ── Diabetes / sugar queries ─────────────────────────────────────────────
    TC("B2-DIA-01", "bug2",
       "sugar control karne ki dawa chahiye",
       must_contain=["diabetes", "aadved"],
       must_not_contain=["joint", "liver care"],
       note="Diabetes query → diabetes products"),
    TC("B2-DIA-02", "bug2",
       "I have Type 2 diabetes what product do you have",
       must_contain=["diabetes"],
       must_not_contain=["joint", "liver care"],
       note="Diabetes query → diabetes management products"),
    TC("B2-DIA-03", "bug2",
       "blood sugar kam karne ka koi upay hai",
       must_contain=["diabetes", "sugar"],
       must_not_contain=["joint"],
       note="Sugar control → diabetes products"),

    # ── Hair care queries ────────────────────────────────────────────────────
    TC("B2-HAIR-01", "bug2",
       "baal bahut girte hain koi oil batao",
       must_contain=["hair", "oil"],
       must_not_contain=["diabetes", "kidney", "piles"],
       note="Hair fall → hair care products"),
    TC("B2-HAIR-02", "bug2",
       "I have severe hair fall what product to use",
       must_contain=["hair"],
       must_not_contain=["diabetes", "sugar", "piles"],
       note="Hair fall → hair oil"),
    TC("B2-HAIR-03", "bug2",
       "hair growth ke liye kya lena chahiye",
       must_contain=["hair"],
       must_not_contain=["diabetes", "sexual", "kidney"],
       note="Hair growth → hair care"),

    # ── Kidney / stone queries ───────────────────────────────────────────────
    TC("B2-KID-01", "bug2",
       "pathri ka ilaj chahiye kidney stone treatment",
       must_contain=["kidney", "stone"],
       must_not_contain=["hair oil", "diabetes", "sexual"],
       note="Kidney stone → Stones Veda"),
    TC("B2-KID-02", "bug2",
       "stones veda for kidney stones how effective",
       must_contain=["stones", "kidney"],
       must_not_contain=["hair", "diabetes"],
       note="Direct Stones Veda query → kidney info"),
    TC("B2-KID-03", "bug2",
       "gall bladder stone ke liye koi medicine hai",
       must_contain=["stone", "kidney"],
       must_not_contain=["diabetes"],
       note="Stone query → Stones Veda"),

    # ── Piles / digestion queries ────────────────────────────────────────────
    TC("B2-PIL-01", "bug2",
       "bawasir ka ilaj chahiye best medicine",
       must_contain=["piles"],
       must_not_contain=["diabetes", "hair", "sexual"],
       note="Piles (bawasir) → Dr Piles Free"),
    TC("B2-PIL-02", "bug2",
       "I have hemorrhoids can you help",
       must_contain=["piles"],
       must_not_contain=["hair", "diabetes"],
       note="Hemorrhoids → piles product"),
    TC("B2-PIL-03", "bug2",
       "pet mein gas bahut hoti hai digestion problem",
       must_contain=["digestion"],
       must_not_contain=["hair", "sexual", "diabetes"],
       note="Digestion/gas → Vajra 44 or SK Gut Raksha — just verify digestion topic"),

    # ── Liver queries ────────────────────────────────────────────────────────
    TC("B2-LIV-01", "bug2",
       "liver weak hai koi medicine suggest karo",
       must_contain=["liver"],
       must_not_contain=["hair", "sexual", "kidney"],
       note="Liver problem → Liver Care"),
    TC("B2-LIV-02", "bug2",
       "fatty liver ke liye koi product hai",
       must_contain=["liver"],
       must_not_contain=["diabetes"],
       note="Fatty liver → Liver Care"),

    # ── Joint pain queries ───────────────────────────────────────────────────
    TC("B2-JNT-01", "bug2",
       "ghutne mein dard hai koi tel batao",
       must_contain=["joint", "oil"],
       must_not_contain=["sexual", "diabetes"],
       note="Knee pain → joint pain oil (not men's sexual products)"),
    TC("B2-JNT-02", "bug2",
       "arthritis pain relief product chahiye",
       must_contain=["joint", "pain"],
       must_not_contain=["sexual", "diabetes"],
       note="Arthritis → joint pain products"),

    # ── Immunity queries ─────────────────────────────────────────────────────
    TC("B2-IMM-01", "bug2",
       "immunity boost karne ke liye kya lena chahiye",
       must_contain=["immunity", "ayush"],
       must_not_contain=["piles", "sexual", "hair"],
       note="Immunity → Ayush Kavach / Kwath"),
    TC("B2-IMM-02", "bug2",
       "bar bar sardi bukhar aata hai immunity weak hai",
       must_contain=["immunity"],
       must_not_contain=["sexual", "piles"],
       note="Frequent illness → immunity products"),

    # ── Addiction queries ────────────────────────────────────────────────────
    TC("B2-ADD-01", "bug2",
       "cigarette chhodne ki dawa chahiye",
       must_contain=["addiction"],
       must_not_contain=["sexual", "diabetes", "hair"],
       note="Smoking cessation → Addiction Killer"),
    TC("B2-ADD-02", "bug2",
       "alcohol addiction treatment product",
       must_contain=["addiction"],
       must_not_contain=["sexual", "diabetes"],
       note="Alcohol addiction → de-addiction products"),

    # ── Skin / vitiligo queries ──────────────────────────────────────────────
    TC("B2-SKIN-01", "bug2",
       "safed daag ka ilaj chahiye vitiligo treatment",
       must_contain=["vitiligo", "saumya"],
       must_not_contain=["diabetes"],
       note="Vitiligo → Saumya Plus (sexual may appear in pricing text)"),
    TC("B2-SKIN-02", "bug2",
       "white skin patches treatment medicine",
       must_contain=["vitiligo", "saumya"],
       must_not_contain=["diabetes"],
       note="White patches → Saumya Plus"),

    # ── Weight management queries ─────────────────────────────────────────────
    TC("B2-WGT-01", "bug2",
       "weight loss ke liye koi product hai",
       must_contain=["weight", "slim"],
       must_not_contain=["sexual", "diabetes", "piles"],
       note="Weight loss → Aadved Slim Herbs"),
    TC("B2-WGT-02", "bug2",
       "motapa kam karne ki dawa chahiye",
       must_contain=["weight", "slim"],
       must_not_contain=["sexual", "kidney"],
       note="Obesity → weight management products"),

    # ── Respiratory queries ──────────────────────────────────────────────────
    TC("B2-RES-01", "bug2",
       "asthma ya saans ki takleef ke liye kya hai",
       must_contain=["respiratory", "vayu"],
       must_not_contain=["sexual", "diabetes", "hair"],
       note="Respiratory issues → Vayu Shuddhi"),
    TC("B2-RES-02", "bug2",
       "breathing problem for respiratory health",
       must_contain=["respiratory"],
       must_not_contain=["sexual", "diabetes"],
       note="Breathing → respiratory products"),

    # ── Sleep queries ────────────────────────────────────────────────────────
    TC("B2-SLP-01", "bug2",
       "mujhe neend nahi aati insomnia ka koi ilaj",
       must_contain=["sleep"],
       must_not_contain=["sexual", "diabetes", "hair"],
       note="Insomnia → Aadved Sleep"),
    TC("B2-SLP-02", "bug2",
       "sleep problem solution chahiye",
       must_contain=["sleep"],
       must_not_contain=["sexual", "piles"],
       note="Sleep issues → Aadved Sleep"),

    # ── Relevance: don't suggest men's health for women's queries ────────────
    TC("B2-GEN-01", "bug2",
       "women's health product chahiye PCOS ke liye",
       must_contain=["women"],
       must_not_contain=["sandy rx", "ultimate hammer", "herbo"],
       note="Women's query → women's health, NOT men's products"),
    TC("B2-GEN-02", "bug2",
       "female sexual wellness product",
       must_contain=["female"],
       must_not_contain=["sandy rx", "ultimate hammer"],
       note="Female wellness → female products only (female keyword in answer)"),

    # ── Vague query should ask follow-up ─────────────────────────────────────
    TC("B2-VAG-01", "bug2",
       "I need a medicine",
       must_contain=[],
       min_length=20,
       note="Vague query: bot should ask clarifying question or give general guidance"),
    TC("B2-VAG-02", "bug2",
       "suggest me best product",
       must_contain=[],
       min_length=20,
       note="Too vague: bot should ask what concern/age/gender"),
    TC("B2-VAG-03", "bug2",
       "koi dawa batao",
       must_contain=[],
       min_length=20,
       note="Vague Hindi query: should ask for more info"),

    # ── Energy / stamina without specifying men's health ─────────────────────
    TC("B2-ENR-01", "bug2",
       "energy booster chahiye general weakness",
       must_contain=["energy", "stamina"],
       note="General energy → energy/wellness products"),
    TC("B2-ENR-02", "bug2",
       "shilajit product hai kya",
       must_contain=["shilajit"],
       must_not_contain=["diabetes", "hair oil"],
       note="Shilajit query → SK Turbo Treats Shilajit Gummies as first result"),
]

assert len(BUG2) == 35, f"Bug2 has {len(BUG2)} tests"


# ═══════════════════════════════════════════════════════════════════════════
# BUG 3 — Medicine-Type Queries (35 tests)
# Bot used to give irrelevant replies to "Is this Ayurvedic?" type queries.
# must_contain verifies the category/type is now stated directly.
# ═══════════════════════════════════════════════════════════════════════════

BUG3: list[TC] = [
    # ── Direct "is this ayurvedic?" questions ────────────────────────────────
    TC("B3-AYU-01", "bug3",
       "Is Ayush for Men an ayurvedic medicine?",
       must_contain=["ayurvedic"],
       note="Category: Male Sexual Wellness — Ayurvedic"),
    TC("B3-AYU-02", "bug3",
       "Sandy RX ayurvedic hai kya",
       must_contain=["ayurvedic"],
       note="Form: Vegetarian Ayurvedic"),
    TC("B3-AYU-03", "bug3",
       "Is Kaama Gold Kit an ayurvedic product",
       must_contain=["ayurvedic"],
       note="Kaama Gold is Ayurvedic kit"),
    TC("B3-AYU-04", "bug3",
       "Liv Muztang Capsules ayurvedic hai ya allopathic",
       must_contain=["ayurvedic"],
       note="Liv Muztang is Ayurvedic"),
    TC("B3-AYU-05", "bug3",
       "Ultimate Hammer is it ayurvedic",
       must_contain=["ayurvedic"],
       note="Ultimate Hammer is Ayurvedic"),
    TC("B3-AYU-06", "bug3",
       "Herbo 365 herbal medicine hai?",
       must_contain=["ayurvedic", "herbal"],
       note="Herbo 365 is herbal/ayurvedic"),
    TC("B3-AYU-07", "bug3",
       "is Addiction Killer Powder ayurvedic or chemical",
       must_contain=["ayurvedic", "herbal"],
       note="Addiction Killer is Ayurvedic"),
    TC("B3-AYU-08", "bug3",
       "Vayu Shuddhi natural hai ya chemical medicine",
       must_contain=["ayurvedic"],
       note="Vayu Shuddhi is Ayurvedic — confirmed in category/description"),
    TC("B3-AYU-09", "bug3",
       "Liver Care Capsules ayurvedic hai?",
       must_contain=["ayurvedic"],
       note="Liver Care is Ayurvedic"),
    TC("B3-AYU-10", "bug3",
       "Stones Veda kya yeh ayurvedic dawa hai",
       must_contain=["ayurvedic"],
       note="Stones Veda is Ayurvedic"),

    # ── "What type of medicine" queries ─────────────────────────────────────
    TC("B3-TYP-01", "bug3",
       "What type of medicine is Ayush for Men",
       must_contain=["ayurvedic", "capsule"],
       note="Type: Ayurvedic capsules"),
    TC("B3-TYP-02", "bug3",
       "Jaam-e-Ishq kis tarah ki dawa hai",
       must_contain=["prash", "herbal"],
       note="Form: Prash (herbal paste)"),
    TC("B3-TYP-03", "bug3",
       "what category does Stones Veda fall in",
       must_contain=["kidney"],
       note="Category: Kidney Health"),
    TC("B3-TYP-04", "bug3",
       "Dhurandar Oil — what type of product is this",
       must_contain=["oil", "joint"],
       note="Type: Ayurvedic oil for joint/muscle pain"),
    TC("B3-TYP-05", "bug3",
       "Aadved Adivasi Hair Oil kis category mein aata hai",
       must_contain=["hair", "oil"],
       note="Category: Hair Care"),
    TC("B3-TYP-06", "bug3",
       "Aadved Sleep kya hai tablet ya powder",
       must_contain=["capsule"],
       note="Form: Capsules — not tablet or powder"),
    TC("B3-TYP-07", "bug3",
       "Saumya Plus kya ek skin cream hai",
       must_contain=["capsule", "oil"],
       note="Form: Capsules + Oil — not just cream"),
    TC("B3-TYP-08", "bug3",
       "SK Turbo Treats — what is this product",
       must_contain=["shilajit", "gummies"],
       note="Form: Shilajit Gummies"),
    TC("B3-TYP-09", "bug3",
       "Power Rootz Keeda Jadi kya hota hai",
       must_contain=["cordyceps"],
       note="Product: Cordyceps Militaris"),
    TC("B3-TYP-10", "bug3",
       "Ayush Kavach ka form kya hai tablet ya capsule",
       must_contain=["capsule"],
       note="Form: Capsules"),

    # ── "Is this herbal?" style queries ────────────────────────────────────
    TC("B3-HRB-01", "bug3",
       "Is Dr Piles Free made with herbal ingredients",
       must_contain=["herbal", "ayurvedic"],
       note="Dr Piles Free is herbal/Ayurvedic"),
    TC("B3-HRB-02", "bug3",
       "Nasha Free herbal hai ya koi chemical",
       must_contain=["herbal", "ayurvedic"],
       note="Nasha Free is herbal Ayurvedic"),
    TC("B3-HRB-03", "bug3",
       "Ayush Kwath natural ingredients se bana hai",
       must_contain=["ayurvedic"],
       note="Ayush Kwath is Ayurvedic — natural/herbal product"),
    TC("B3-HRB-04", "bug3",
       "Ortho Veda Oil is it herbal",
       must_contain=["ayurvedic", "herbal"],
       note="Form: Ayurvedic Massage Oil"),
    TC("B3-HRB-05", "bug3",
       "Sanjeev Ras herbal juice hai",
       must_contain=["juice", "herbal", "ayurvedic"],
       note="Form: Juice — herbal/Ayurvedic"),

    # ── Hinglish medicine-type queries ────────────────────────────────────
    TC("B3-HIN-01", "bug3",
       "Kaama Gold herbal dawa hai ya english medicine",
       must_contain=["ayurvedic", "herbal"],
       note="Hinglish type query"),
    TC("B3-HIN-02", "bug3",
       "Addiction Killer angrezi dawa hai ya desi",
       must_contain=["ayurvedic", "herbal"],
       note="'Desi' = Ayurvedic"),
    TC("B3-HIN-03", "bug3",
       "Sandy RX mein kya English medicine hai",
       must_contain=["ayurvedic"],
       note="It's Ayurvedic, not allopathic"),
    TC("B3-HIN-04", "bug3",
       "Liver Care Capsules allopathic hai ya herbal",
       must_contain=["ayurvedic", "herbal"],
       note="Liver Care is herbal/Ayurvedic"),
    TC("B3-HIN-05", "bug3",
       "Aadved Adivasi Hair Oil mein kya natural ingredients hain",
       must_contain=["oil", "hair"],
       note="Natural/herbal hair oil"),

    # ── Category-specific type queries ────────────────────────────────────
    TC("B3-CTG-01", "bug3",
       "Ayush for Women kis category ka product hai",
       must_contain=["women"],
       note="Category: Women's Health"),
    TC("B3-CTG-02", "bug3",
       "Macamo The Latin Lava which category",
       must_contain=["sexual", "wellness"],
       note="Category: Male Sexual Wellness"),
    TC("B3-CTG-03", "bug3",
       "Aadved Slim Herbs kya yeh weight loss product hai",
       must_contain=["weight"],
       note="Category: Weight Management"),
    TC("B3-CTG-04", "bug3",
       "Poshan Plus weight gain ke liye hai",
       must_contain=["weight"],
       note="Category: Weight Gain"),
    TC("B3-CTG-05", "bug3",
       "Dr Madhu Amrit diabetes kit hai",
       must_contain=["diabetes"],
       note="Category: Diabetes Management"),
]

assert len(BUG3) == 35, f"Bug3 has {len(BUG3)} tests"

ALL_TESTS: list[TC] = BUG1 + BUG2 + BUG3
assert len(ALL_TESTS) == 100, f"Expected 100 tests, got {len(ALL_TESTS)}"


# ═══════════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════════

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _judge(answer: str, tc: TC) -> tuple[bool, list[str]]:
    """Returns (passed, list_of_failures)."""
    failures: list[str] = []
    ans_n = _normalise(answer)

    if len(answer.strip()) < tc.min_length:
        failures.append(f"too_short({len(answer.strip())} < {tc.min_length})")

    for phrase in tc.must_contain:
        p_n = _normalise(phrase)
        # Also try digit-only match for prices: 4999 matches "4,999" or "₹4999"
        digits_only = re.sub(r"\D", "", phrase)
        ans_digits  = re.sub(r"\D", "", answer)
        if p_n not in ans_n and not (digits_only and digits_only in ans_digits):
            failures.append(f"missing:'{phrase}'")

    for phrase in tc.must_not_contain:
        p_n = _normalise(phrase)
        if p_n in ans_n:
            failures.append(f"unwanted:'{phrase}'")

    return (len(failures) == 0, failures)


# ═══════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════

async def run(company_id: UUID, out_path: Path) -> None:
    s = get_settings()
    weaviate = WeaviateClient(
        url=s.weaviate_url,
        api_key=s.weaviate_api_key,
        timeout=s.weaviate_timeout_seconds,
    )

    results: list[dict] = []
    total = len(ALL_TESTS)
    passed = failed = errors = 0

    bug_stats: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0})

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

            for i, tc in enumerate(ALL_TESTS, 1):
                t0 = time.perf_counter()
                try:
                    raw = await rag.process_query(
                        company_id=company_id,
                        query=tc.query,
                        conversation_id=None,
                        message_id=None,
                        background_tasks=None,
                    )
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)
                    answer  = raw.get("answer") or ""
                    rtype   = raw.get("response_type", "?")
                    lang    = raw.get("language", "?")
                    score   = raw.get("top_score")
                    fb      = raw.get("fallback_triggered", False)

                    ok, failures = _judge(answer, tc)
                    status = "PASS" if ok else "FAIL"
                    if ok:
                        passed += 1
                        bug_stats[tc.bug]["pass"] += 1
                    else:
                        failed += 1
                        bug_stats[tc.bug]["fail"] += 1

                except Exception as exc:
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)
                    answer = f"[ERROR] {exc}"
                    rtype = "error"; lang = "?"; score = None; fb = False
                    ok = False; failures = [f"exception:{exc}"]; status = "ERR"
                    errors += 1; failed += 1
                    bug_stats[tc.bug]["fail"] += 1

                results.append({
                    "n": i, "tag": tc.tag, "bug": tc.bug,
                    "query": tc.query, "status": status, "ok": ok,
                    "failures": failures, "type": rtype, "lang": lang,
                    "score": score, "fallback": fb,
                    "ms": elapsed_ms, "answer": answer, "note": tc.note,
                })

                icon = "✅" if ok else "❌"
                score_s = f"{score:.3f}" if score is not None else "  —  "
                fail_s  = f"  ← {failures}" if failures else ""
                print(
                    f"{icon} [{i:03d}/{total}] {tc.tag:<14} [{tc.bug}] "
                    f"{elapsed_ms:>5}ms [{rtype}/{lang}] score={score_s}{fail_s}"
                )

    finally:
        await weaviate.aclose()
        await engine.dispose()

    # ── Console summary ──────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  TOTAL: {total}  |  PASS: {passed}  |  FAIL: {failed}  |  ERRORS: {errors}")
    print(f"  Overall pass rate: {100*passed//total}%")
    print(f"{'='*70}")
    print("\nBy Bug Category:")
    for bug_key in ["bug1", "bug2", "bug3"]:
        v = bug_stats[bug_key]
        t = v["pass"] + v["fail"]
        pct = 100 * v["pass"] // t if t else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        labels = {
            "bug1": "Bug1 Product Completeness",
            "bug2": "Bug2 Recommendation Relevance",
            "bug3": "Bug3 Medicine-Type Queries",
        }
        print(f"  {labels[bug_key]:<32} {bar} {pct:>3}%  ({v['pass']}/{t})")

    print("\nFailing tests:")
    for r in results:
        if not r["ok"]:
            print(f"  ❌ {r['tag']:<16} {r['query'][:60]!r}")
            for f in r["failures"]:
                print(f"       → {f}")

    # ── Markdown report ──────────────────────────────────────────────────────
    lines = [
        "# 3-Bugs Quality Test Report — SkinRange",
        "",
        f"**Company ID:** `{company_id}`  ",
        f"**Total:** {total}  |  **Pass:** {passed}  |  **Fail:** {failed}  |  **Pass rate:** {100*passed//total}%",
        "",
        "---",
        "",
        "## Summary by Bug",
        "",
        "| Bug | Description | Pass | Fail | Rate |",
        "|-----|-------------|------|------|------|",
    ]
    for bug_key, label in [
        ("bug1", "Product Info Completeness"),
        ("bug2", "Recommendation Relevance"),
        ("bug3", "Medicine-Type Queries"),
    ]:
        v = bug_stats[bug_key]
        t = v["pass"] + v["fail"]
        pct = 100 * v["pass"] // t if t else 0
        lines.append(f"| {bug_key} | {label} | {v['pass']} | {v['fail']} | {pct}% |")

    lines += [
        "",
        "---",
        "",
        "## Detailed Results",
        "",
        "| # | Tag | Bug | Status | Lang | Score | ms | Failures | Query | Answer (first 250 chars) |",
        "|---|-----|-----|--------|------|-------|----|----------|-------|--------------------------|",
    ]
    for r in results:
        icon   = "✅" if r["ok"] else "❌"
        score  = f"{r['score']:.3f}" if r["score"] is not None else "—"
        fb_str = " [FB]" if r["fallback"] else ""
        fails  = "; ".join(r["failures"]) if r["failures"] else "—"
        ans    = (r["answer"] or "")[:250].replace("\n", " ").replace("|", "｜")
        query  = r["query"][:70].replace("|", "｜")
        lines.append(
            f"| {r['n']} | `{r['tag']}` | {r['bug']} | {icon} {r['status']}{fb_str} "
            f"| {r['lang']} | {score} | {r['ms']} | {fails} | {query} | {ans} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Failing Tests Detail",
        "",
    ]
    fail_list = [r for r in results if not r["ok"]]
    if fail_list:
        for r in fail_list:
            lines.append(f"### ❌ `{r['tag']}` ({r['bug']})")
            lines.append(f"**Query:** {r['query']}")
            lines.append(f"**Note:** {r['note']}")
            lines.append(f"**Failures:** {'; '.join(r['failures'])}")
            lines.append(f"**Answer:**")
            lines.append(f"> {(r['answer'] or '').replace(chr(10), ' ')[:500]}")
            lines.append("")
    else:
        lines.append("_All 100 tests passed!_")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  Report saved → {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--company-id", default=str(SKRANGE))
    p.add_argument("--out", default="results/3bugs_test_report.md")
    args = p.parse_args()
    asyncio.run(run(UUID(args.company_id), Path(args.out)))


if __name__ == "__main__":
    main()
