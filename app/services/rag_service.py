"""
RAGService – orchestrates retrieval-augmented generation.

Flow
----
1. Resolve company config (Weaviate collection, RAG JSON, prompts).
2. Detect language for retrieval; resolve reply language using conversation
   stickiness when *conversation_reply_language* is provided; optionally merge
   recent conversation into the search query.
3. Normalize query for Weaviate.
4. Optionally embed the query; run hybrid (BM25 + vector) or BM25-only search.
5. Evaluate retrieval confidence (configurable strategy over score list).
6. Re-rank with lexical MMR + deduplicate; label chunks with source filenames.
7. Call LLM with context (and optional conversation transcript).
8. Log retrieval metadata; return answer + sources.

Result dict keys
----------------
- ``response_type``: ``"rag"`` or ``"fallback"``
- ``answer``:        Text to send to the customer
- ``fallback_triggered``: bool
- ``language``:      Output language
- ``sources``:       List of dicts ``file_name``, ``document_id``, ``chunk_index``, ``score``
"""
import asyncio
import json
import logging
import math
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.integrations.llm.client import LLMClientProtocol
from app.integrations.weaviate.client import WeaviateClient
from app.models.product import Product
from app.repositories.company_config_repository import CompanyConfigRepository
from app.repositories.product_repository import ProductRepository
from app.services.fallback_service import FallbackService
from app.services.language_service import (
    detect_language,
    normalize_query,
    resolve_reply_language,
)
from app.utils.rag_postprocess import (
    dedupe_chunk_texts,
    format_conversation_transcript,
    format_hit_for_llm,
    merge_query_with_history,
    mmr_lexical_select,
)
from app.utils.whatsapp_formatting import whatsapp_friendly_text

if TYPE_CHECKING:
    from app.integrations.embeddings.client import EmbeddingClientProtocol

logger = logging.getLogger(__name__)

_RAW_JSON_MAX_BYTES = 120_000

# Short greetings / chit-chat score poorly in BM25 against product or policy docs;
# we still want a natural LLM reply instead of the low-confidence fallback.
_SMALL_TALK_MAX_CHARS = 96
_SMALL_TALK_MAX_WORDS = 8
_SMALL_TALK_CONTEXT_CHUNK = (
    "[Meta-instruction: The user sent a short greeting or conversational opener, "
    "not a factual question. Reply briefly and warmly as customer support. "
    "Do not say you could not find information in documents. Offer to help with "
    "products, orders, or other questions.]"
)
_IDENTITY_QUERY_RE = re.compile(
    r"\b("
    r"who\s+are\s+you|what\s+are\s+you|your\s+name|who\s+is\s+this|"
    r"are\s+you\s+a\s+bot|bot\s+(?:ho|hai|kaun)|"
    r"aap\s+kaun|tum\s+kaun|kaun\s+ho|kaun\s+hai|naam\s+kya"
    r")\b|"
    r"(आप\s+कौन|तुम\s+कौन|आपका\s+नाम|तुम्हारा\s+नाम|कौन\s+हो|कौन\s+हैं|बॉट)",
    re.IGNORECASE,
)

_IDENTITY_ANSWERS = {
    "english": (
        "I'm Alka Sharma from SkinRange, your support assistant. I can help with products, "
        "orders, returns, and basic usage questions."
    ),
    "hinglish": (
        "Main Alka Sharma from SkinRange hoon, aapki support assistant. Main products, orders, "
        "returns aur basic usage questions mein help kar sakti hoon."
    ),
    "hindi": (
        "मैं अलका शर्मा हूँ, SkinRange से आपकी सपोर्ट असिस्टेंट। मैं प्रोडक्ट, ऑर्डर, "
        "रिटर्न और basic usage सवालों में मदद कर सकती हूँ।"
    ),
}

_FIRST_GREETING_ANSWERS = {
    "english": (
        "👋 Hi, I'm Alka Sharma from SkinRange. How can I help you today?"
    ),
    "hinglish": (
        "🙏 Namaste, main Alka Sharma from SkinRange hoon. Aaj main aapki kya help kar sakti hoon?"
    ),
    "hindi": (
        "🙏 नमस्ते, मैं अलका शर्मा हूँ, SkinRange से। आज मैं आपकी क्या मदद कर सकती हूँ?"
    ),
}

_PRODUCT_INTENT_RE = re.compile(
    r"\b("
    r"suggest|recommend|recommendation|medicine|medicines|product|products|"
    r"best|which|konsa|kaunsa|dawai|dawa|ilaj|treatment|"
    # product type / category queries (EN + Hinglish)
    r"ayurvedic|ayurved|herbal|allopathic|homeopathic|natural|organic|"
    r"category|type|ingredients|composition|"
    r"aayurvedik|jadibutti|jadi|booti|"
    # price / buy intent (EN + Hinglish)
    r"price|cost|rate|mrp|buy|order|purchase|kitna|kitne|kimat|dam|"
    r"khareed|prepaid|cod|delivery|offer|discount|"
    r"how\s+much|what\s+is\s+the|tell\s+me|batao|bata|"
    r"used\s+for|kya\s+hai|kya\s+karta|kya\s+hota|ke\s+liye"
    r")\b",
    re.IGNORECASE,
)

# Price-specific intent — triggers named-product DB lookup even without Weaviate hit
_PRICE_INTENT_RE = re.compile(
    r"\b(price|cost|rate|mrp|kitna|kitne|kimat|dam|keemat|"
    r"prepaid|cod|offer|discount|buy|order|khareed|lena\s+hai|"
    r"how\s+much|padega|milega|ka\s+dam|ki\s+kimat|ki\s+price|"
    r"what.{0,10}price|what.{0,10}cost|what.{0,10}rate)\b",
    re.IGNORECASE,
)
_HEALTH_NEED_TERMS = {
    "acidity",
    "addiction",
    "anxiety",
    "asthma",
    "bp",
    "cold",
    "cough",
    "diabetes",
    "ed",
    "energy",
    "fatigue",
    "fever",
    "hair",
    "immunity",
    "insomnia",
    "joint",
    "kidney",
    "libido",
    "liver",
    "pain",
    "pcod",
    "pcos",
    "pe",
    "piles",
    "respiratory",
    "sex",
    "sexual",
    "skin",
    "sleep",
    "sprain",
    "stamina",
    "stress",
    "swelling",
    "sugar",
    "testosterone",
    "weight",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PRODUCT_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "based",
    "can",
    "for",
    "give",
    "have",
    "help",
    "i",
    "in",
    "is",
    "bata",
    "batao",
    "best",
    "dawa",
    "dawai",
    "ilaj",
    "ilaaj",
    "kya",
    "liye",
    "me",
    "medicine",
    "medicines",
    "mme",
    "my",
    "need",
    "of",
    "on",
    "please",
    "product",
    "products",
    "recommend",
    "recommendation",
    "some",
    "suggest",
    "the",
    "to",
    "with",
    "you",
}
_SEXUAL_STAMINA_TERMS = {
    "ed",
    "erectile",
    "erection",
    "fertility",
    "intimacy",
    "intimate",
    "libido",
    "male",
    "men",
    "pe",
    "performance",
    "premature",
    "reproductive",
    "sex",
    "sexual",
    "sperm",
    "testosterone",
    "timing",
}
_PRODUCT_FILE_HINTS = (
    "product",
    "catalog",
    "pricing",
)
_SLEEP_PURPOSE_RE = re.compile(
    r"\b("
    r"sleep support|sleep quality|sleep-wake|sleep cycle|insomnia|restful|"
    r"peaceful sleep|quality of sleep|sleep & stress"
    r")\b",
    re.IGNORECASE,
)
_MSK_TERMS = {
    "arthritis",
    "back",
    "bone",
    "bones",
    "joint",
    "joints",
    "knee",
    "knees",
    "muscle",
    "muscles",
    "sciatica",
    "spondylitis",
    "stiffness",
    "swelling",
}
_JOINT_PAIN_PURPOSE_RE = re.compile(
    r"\b(joint|joints|knee|back|shoulder|muscle|arthritis|spondylitis|sciatica)\b",
    re.IGNORECASE,
)
_SKIN_PURPOSE_RE = re.compile(
    r"\b("
    r"vitiligo|safed daag|white skin patches|skin patches|skin disorder|"
    r"skin disorders|pigmentation|melanin|acne|eczema|psoriasis|uneven skin"
    r")\b",
    re.IGNORECASE,
)
_MULTILINGUAL_QUERY_SYNONYMS = {
    "neend": {"sleep"},
    "nind": {"sleep"},
    "sona": {"sleep"},
    "sone": {"sleep"},
    "dawa": {"medicine"},
    "dawai": {"medicine"},
    "daawai": {"medicine"},
    "ilaaj": {"treatment"},
    "ilaj": {"treatment"},
    "taqat": {"stamina", "energy", "strength"},
    "takat": {"stamina", "energy", "strength"},
    "kamzori": {"weakness", "fatigue", "energy"},
    "dard": {"pain"},
    "jod": {"joint"},
    "jodo": {"joint", "joints"},
    "jodon": {"joint", "joints"},
    "ghutna": {"knee", "joint"},
    "ghutne": {"knee", "joint"},
    "ghutno": {"knee", "joint"},
    "kamar": {"back", "pain"},
    "peeth": {"back", "pain"},
    "haddi": {"bone", "joint"},
    "haddiyan": {"bones", "joint"},
    "sujan": {"swelling", "pain"},
    "moch": {"sprain", "pain"},
    # Hair care
    "baal": {"hair"},
    "baalo": {"hair"},
    "balon": {"hair"},
    "balo": {"hair"},
    "hair fall": {"hair"},
    "jharte": {"hair"},
    "jhadte": {"hair"},
    # Weight / obesity
    "motapa": {"weight", "obesity"},
    "mota": {"weight", "fat"},
    "patla": {"weight", "slim"},
    "vajan": {"weight"},
    "wazan": {"weight"},
    # Respiratory / breathing
    "saans": {"respiratory", "breathing", "lung"},
    "khansi": {"respiratory", "cough"},
    "khaansi": {"respiratory", "cough"},
    "sardi": {"respiratory", "cold"},
    # Addiction / smoking cessation
    "cigarette": {"addiction", "smoking"},
    "cigar": {"addiction", "smoking"},
    "bidi": {"addiction", "smoking"},
    "tambaaku": {"addiction", "tobacco"},
    "nasha": {"addiction"},
    "nashe": {"addiction"},
    "chhodna": {"addiction", "quit"},
    "chhod": {"addiction", "quit"},
    "alcohol": {"addiction"},
    "sharab": {"addiction", "alcohol"},
    # Piles / digestive
    "bawasir": {"piles"},
    "pet": {"digestion", "stomach"},
    "kabj": {"constipation", "digestion"},
    # Women's health
    "mahila": {"women"},
    "pcos": {"women", "hormonal"},
    "pcod": {"women", "hormonal"},
    "period": {"women", "menstrual"},
    "mahwari": {"women", "menstrual"},
    # Skin / vitiligo
    "safed daag": {"vitiligo", "skin"},
    "daag": {"skin"},
    # Liver / kidney
    "kaleja": {"liver"},
    "gurdha": {"kidney"},
    # Diabetes
    "sugar": {"diabetes"},
    "madhumeh": {"diabetes"},
    # Devanagari script
    "रिटर्न": {"return"},
    "वापसी": {"return"},
    "लौटाना": {"return"},
    "पॉलिसी": {"policy"},
    "नीति": {"policy"},
    "रिफंड": {"refund"},
    "पैसा": {"refund", "payment"},
    "नींद": {"sleep"},
    "निंद": {"sleep"},
    "सोना": {"sleep"},
    "सोने": {"sleep"},
    "दवा": {"medicine"},
    "दवाई": {"medicine"},
    "इलाज": {"treatment"},
    "ताकत": {"stamina", "energy", "strength"},
    "कमजोरी": {"weakness", "fatigue", "energy"},
    "दर्द": {"pain"},
    "जोड़": {"joint"},
    "जोड़ों": {"joint", "joints"},
    "घुटना": {"knee", "joint"},
    "घुटने": {"knee", "joint"},
    "घुटनों": {"knee", "joint"},
    "कमर": {"back", "pain"},
    "पीठ": {"back", "pain"},
    "हड्डी": {"bone", "joint"},
    "सूजन": {"swelling", "pain"},
    "मोच": {"sprain", "pain"},
    "बाल": {"hair"},
    "बालों": {"hair"},
    "मोटापा": {"weight", "obesity"},
    "वजन": {"weight"},
    "साँस": {"respiratory", "breathing"},
    "सांस": {"respiratory", "breathing"},
    "खांसी": {"respiratory", "cough"},
    "सर्दी": {"respiratory", "cold"},
    "नशा": {"addiction"},
    "तम्बाकू": {"addiction", "tobacco"},
    "बवासीर": {"piles"},
    "पेट": {"digestion", "stomach"},
    "कब्ज": {"constipation", "digestion"},
    "शराब": {"addiction", "alcohol"},
}
_FIELD_LABELS = {
    "english": {
        "intro": "Here are the best matching options:",
        "category": "Category",
        "form": "Form",
        "used_for": "Used for",
        "benefits": "Benefits",
        "dosage": "Dosage",
        "duration": "Recommended duration",
        "pack": "Pack",
        "price": "Price",
        "stock": "Stock",
        "link": "Link",
        "outro": "Tell me your age and main concern if you want a more specific suggestion.",
    },
    "hinglish": {
        "intro": "Is concern ke liye ye options match karte hain:",
        "category": "Category",
        "form": "Form",
        "used_for": "Kaam aata hai",
        "benefits": "Fayde",
        "dosage": "Dosage",
        "duration": "Duration",
        "pack": "Pack",
        "price": "Price",
        "stock": "Stock",
        "link": "Link",
        "outro": "Age aur main concern bata doge toh aur specific suggestion de sakta hoon.",
    },
    "hindi": {
        "intro": "इस समस्या के लिए ये विकल्प बेहतर मैच करते हैं:",
        "category": "श्रेणी",
        "form": "रूप",
        "used_for": "किसके लिए",
        "benefits": "फायदे",
        "dosage": "डोज़",
        "duration": "अनुशंसित अवधि",
        "pack": "पैक",
        "price": "कीमत",
        "stock": "स्टॉक",
        "link": "लिंक",
        "outro": "उम्र और मुख्य परेशानी बता दें तो मैं और specific सुझाव दे सकता हूँ।",
    },
}
_SITUATION_EMOJI = {
    "hi": "👋",
    "hello": "👋",
    "namaste": "🙏",
    "namaskar": "🙏",
    "ram ram": "🙏",
    "thanks": "😊",
    "thank you": "😊",
    "dhanyawad": "🙏",
    "shukriya": "🙏",
    "धन्यवाद": "🙏",
    "शुक्रिया": "🙏",
    "sleep": "😴",
    "insomnia": "😴",
    "neend": "😴",
    "nind": "😴",
    "नींद": "😴",
    "stamina": "💪",
    "libido": "💪",
    "taqat": "💪",
    "takat": "💪",
    "कमजोरी": "💪",
    "ताकत": "💪",
    "energy": "⚡",
    "fatigue": "⚡",
    "weakness": "⚡",
    "kamzori": "⚡",
    "pain": "😟",
    "hurt": "😟",
    "injury": "🩹",
    "injured": "🩹",
    "dard": "😟",
    "takleef": "😟",
    "chot": "🩹",
    "दर्द": "😟",
    "तकलीफ": "😟",
    "चोट": "🩹",
    "joint": "🦵",
    "knee": "🦵",
    "back pain": "😟",
    "jodo": "🦵",
    "ghutna": "🦵",
    "ghutne": "🦵",
    "जोड़": "🦵",
    "जोड़ों": "🦵",
    "घुटना": "🦵",
    "घुटने": "🦵",
    "skin": "✨",
    "pimple": "✨",
    "acne": "✨",
    "glow": "✨",
    "face": "✨",
    "twacha": "✨",
    "त्वचा": "✨",
    "चेहरा": "✨",
    "hair": "🌿",
    "बाल": "🌿",
    "baal": "🌿",
    "weight": "⚖️",
    "fat": "⚖️",
    "motapa": "⚖️",
    "मोटापा": "⚖️",
    "diabetes": "🩺",
    "sugar": "🩺",
    "bp": "❤️",
    "blood pressure": "❤️",
    "heart": "❤️",
    "हृदय": "❤️",
    "ब्लड प्रेशर": "❤️",
    "liver": "🛡️",
    "kidney": "💧",
    "stone": "💧",
    "pathri": "💧",
    "पथरी": "💧",
    "immunity": "🛡️",
    "immune": "🛡️",
    "cough": "🌬️",
    "cold": "🌬️",
    "fever": "🤒",
    "bukhar": "🤒",
    "बुखार": "🤒",
    "khansi": "🌬️",
    "sardi": "🌬️",
    "खांसी": "🌬️",
    "सर्दी": "🌬️",
    "acidity": "🔥",
    "gas": "🔥",
    "digestion": "🍽️",
    "pet": "🍽️",
    "पेट": "🍽️",
    "constipation": "🍽️",
    "kabj": "🍽️",
    "कब्ज": "🍽️",
    "piles": "🩺",
    "bawasir": "🩺",
    "बवासीर": "🩺",
    "period": "🌸",
    "pcos": "🌸",
    "women": "🌸",
    "mahila": "🌸",
    "माहवारी": "🌸",
    "पीरियड": "🌸",
    "addiction": "🤝",
    "nasha": "🤝",
    "नशा": "🤝",
    "stress": "🌿",
    "anxiety": "🌿",
    "tension": "🌿",
    "chinta": "🌿",
    "चिंता": "🌿",
    "order": "📦",
    "delivery": "📦",
    "shipping": "📦",
    "track": "📦",
    "tracking": "📦",
    "payment": "💳",
    "upi": "💳",
    "paid": "💳",
    "price": "💰",
    "cost": "💰",
    "kitna": "💰",
    "कितना": "💰",
    "stock": "✅",
    "available": "✅",
    "in stock": "✅",
    "urgent": "⚠️",
    "emergency": "⚠️",
    "jaldi": "⚠️",
    "जल्दी": "⚠️",
    "return": "🔁",
    "refund": "🔁",
    "replace": "🔁",
    "exchange": "🔁",
    "warranty": "🛠️",
}


def _looks_like_greeting_or_small_talk(text: str) -> bool:
    """
    True when the message is only a greeting or brief conversational phrase.

    These queries rarely match indexed chunks with a high retrieval score, but
    the user still expects a normal assistant reply, not the knowledge-base
    fallback message.
    """
    t = (text or "").strip()
    if not t or len(t) > _SMALL_TALK_MAX_CHARS:
        return False
    words = t.split()
    if len(words) > _SMALL_TALK_MAX_WORDS:
        return False
    low = " ".join(t.lower().split())
    if re.fullmatch(r"(thanks?|thank\s+you|thx|ty)\b[!.]*", low):
        return True
    if re.fullmatch(r"(ok+|okay|k)\b[!.]*", low):
        return True
    if re.fullmatch(r"(bye|goodbye|see\s+ya|later)\b[!.]*", low):
        return True
    if re.fullmatch(
        r"(h+e+l+l*o+|h+i+|hey+|hiya|hallo|namaste|namaskar)\s+ji\b[!.]*",
        low,
    ):
        return True
    if re.fullmatch(
        r"(h+e+l+l*o+|h+i+|hey+|hiya|hallo|namaste|namaskar)([!.,\s]*)?$",
        low,
    ):
        return True
    if re.fullmatch(r"good\s+(morning|afternoon|evening|day)\b[!.,\s]*", low):
        return True
    if re.fullmatch(r"नमस्ते|नमस्कार", t.strip()):
        return True
    return False


def _looks_like_greeting(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > _SMALL_TALK_MAX_CHARS:
        return False
    low = " ".join(t.lower().split())
    if re.fullmatch(
        r"(h+e+l+l*o+|h+i+|hey+|hiya|hallo|namaste|namaskar)\s+ji\b[!.]*",
        low,
    ):
        return True
    if re.fullmatch(
        r"(h+e+l+l*o+|h+i+|hey+|hiya|hallo|namaste|namaskar)([!.,\s]*)?$",
        low,
    ):
        return True
    if re.fullmatch(r"good\s+(morning|afternoon|evening|day)\b[!.,\s]*", low):
        return True
    if re.fullmatch(r"नमस्ते|नमस्कार", t.strip()):
        return True
    return False


def _first_greeting_answer(output_language: str) -> str:
    return _FIRST_GREETING_ANSWERS.get(output_language, _FIRST_GREETING_ANSWERS["english"])


def _query_terms_for_product_match(query: str) -> set[str]:
    raw = (query or "").lower()
    tokens = set(_TOKEN_RE.findall(raw))
    for src, expansions in _MULTILINGUAL_QUERY_SYNONYMS.items():
        if src in raw:
            tokens.update(expansions)
    return {
        t
        for t in tokens
        if len(t) >= 3 and t not in _PRODUCT_STOPWORDS and not t.isdigit()
    }


def _expand_multilingual_search_query(query: str) -> str:
    raw = query or ""
    expansions: set[str] = set()
    raw_l = raw.lower()
    for src, values in _MULTILINGUAL_QUERY_SYNONYMS.items():
        if src in raw_l:
            expansions.update(values)
    if not expansions:
        return raw
    return f"{raw} {' '.join(sorted(expansions))}"


def _looks_like_product_recommendation(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    if _PRODUCT_INTENT_RE.search(q):
        return True
    if _query_terms_for_product_match(q) & _HEALTH_NEED_TERMS:
        return True
    return bool(re.search(r"\bfor\s+[a-z][a-z0-9 -]{2,}\??$", q, re.IGNORECASE))


def _is_price_query(query: str) -> bool:
    """True when the user is asking for price / cost / buy info about a specific product."""
    return bool(_PRICE_INTENT_RE.search((query or "").strip()))


def _looks_like_identity_query(query: str) -> bool:
    return bool(_IDENTITY_QUERY_RE.search((query or "").strip()))


def _identity_answer(output_language: str) -> str:
    return _IDENTITY_ANSWERS.get(output_language, _IDENTITY_ANSWERS["english"])


def _is_productish_hit(hit: Dict[str, Any]) -> bool:
    fn = (hit.get("file_name") or "").lower()
    text = (hit.get("chunk_text") or "").lower()
    return (
        any(h in fn for h in _PRODUCT_FILE_HINTS)
        or "used for:" in text
        or "category:" in text
        or "benefits:" in text
    )


def _used_for_text(chunk_text: str) -> str:
    """Extract the most semantically relevant lines from a product chunk for scoring.

    Includes product identity, use-case, benefits, and category lines so that
    queries about medicine type (e.g. "Is this Ayurvedic?") can match correctly.
    """
    lines = []
    for line in (chunk_text or "").splitlines():
        low = line.lower().strip()
        if (
            low.startswith("product:")
            or low.startswith("used for:")
            or low.startswith("category:")
            or low.startswith("benefits:")
            or low.startswith("key ingredients:")
            or low.startswith("description:")
            or low.startswith('"name"')
            or low.startswith('"description"')
        ):
            lines.append(line)
    return "\n".join(lines)


def _product_match_score(hit: Dict[str, Any], query_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    text = (hit.get("chunk_text") or "").lower()
    if not text:
        return 0.0
    used_for = _used_for_text(text).lower()
    file_name = (hit.get("file_name") or "").lower()
    score = 0.0
    direct_matches = 0
    for term in query_terms:
        if term == "sleep" and term in used_for:
            if not _SLEEP_PURPOSE_RE.search(used_for):
                continue
            score += 4.0
            direct_matches += 1
        elif term == "skin" and term in used_for:
            if not _SKIN_PURPOSE_RE.search(used_for):
                continue
            score += 4.0
            direct_matches += 1
        elif (
            term == "pain"
            and (query_terms & _MSK_TERMS)
            and term in used_for
        ):
            if not _JOINT_PAIN_PURPOSE_RE.search(used_for):
                continue
            score += 4.0
            direct_matches += 1
        elif term in used_for:
            score += 4.0
            direct_matches += 1
    if direct_matches == 0:
        return 0.0
    if any(h in file_name for h in _PRODUCT_FILE_HINTS):
        score += 0.5
    if "stamina" in query_terms and "products-mens-health" in file_name:
        score += 2.0
    return score


def _section_matches_product_query(section: str, query_terms: set[str]) -> bool:
    hit = {"chunk_text": section, "file_name": "product-section"}
    if _product_match_score(hit, query_terms) <= 0:
        return False
    if "stamina" not in query_terms:
        return True
    section_terms = set(_TOKEN_RE.findall(section.lower()))
    return bool(_SEXUAL_STAMINA_TERMS & section_terms)


def _trim_hit_to_matching_product_sections(
    hit: Dict[str, Any],
    query_terms: set[str],
) -> Dict[str, Any]:
    text = hit.get("chunk_text") or ""
    sections = _split_product_sections(text)
    if len(sections) <= 1:
        return hit
    matching = [
        section
        for section in sections
        if _section_matches_product_query(section, query_terms)
    ]
    if not matching:
        return hit
    trimmed = dict(hit)
    trimmed["chunk_text"] = "\n\n---\n\n".join(matching)
    return trimmed


def _split_product_sections(text: str) -> List[str]:
    raw_sections = [
        s.strip()
        for s in re.split(r"\n\s*---\s*\n|\n(?=##\s+)|\n\s*},\s*\n\s*{", text or "")
        if s and s.strip()
    ]
    return raw_sections or ([text] if text else [])


def _line_field(section: str, label: str) -> Optional[str]:
    m = re.search(
        rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)(?:\n|$)",
        section,
    )
    if not m:
        return None
    return " ".join(m.group(1).strip().split())


def _jsonish_field(section: str, label: str) -> Optional[str]:
    m = re.search(
        rf'"{re.escape(label)}"\s*:\s*"([^"]+)"',
        section,
        re.IGNORECASE,
    )
    if not m:
        return None
    return " ".join(m.group(1).strip().split())


def _extract_product_card(section: str) -> Optional[Dict[str, str]]:
    text = (section or "").strip()
    if not text:
        return None
    name = (
        _line_field(text, "Product")
        or _jsonish_field(text, "name")
        or _jsonish_field(text, "title")
    )
    if not name:
        heading = re.search(r"(?m)^##\s+(.+)$", text)
        if heading:
            name = " ".join(heading.group(1).strip().split())
    if not name:
        return None
    return {
        "name": name,
        "category": _line_field(text, "Category") or _jsonish_field(text, "category") or "",
        "form": _line_field(text, "Form / Variant") or _line_field(text, "Form") or _line_field(text, "Variant") or "",
        "used_for": _line_field(text, "Used For")
        or _jsonish_field(text, "description")
        or "",
        "benefits": _line_field(text, "Benefits") or _jsonish_field(text, "benefits") or "",
        "dosage": _line_field(text, "Dosage & Schedule")
        or _line_field(text, "Dosage")
        or "",
        "duration": _line_field(text, "Recommended Duration")
        or _line_field(text, "Duration")
        or "",
        "pack": _line_field(text, "Available Packs") or _line_field(text, "Pack") or "",
        "price": _line_field(text, "Pricing") or _jsonish_field(text, "price") or "",
        "stock": _line_field(text, "Stock Status") or "",
        "link": _line_field(text, "Product Link")
        or _jsonish_field(text, "url")
        or _jsonish_field(text, "link")
        or "",
    }


def _product_cards_from_hits(
    hits: List[Dict[str, Any]],
    *,
    query_terms: set[str],
) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    seen: set[str] = set()
    for hit in hits:
        text = hit.get("chunk_text") or ""
        sections = [
            s.strip() for s in _split_product_sections(text) if s and s.strip()
        ] or [text]
        for section in sections:
            if not _section_matches_product_query(section, query_terms):
                continue
            card = _extract_product_card(section)
            if not card:
                continue
            if not (
                card.get("used_for")
                or card.get("benefits")
                or card.get("category")
                or card.get("dosage")
                or card.get("price")
            ):
                continue
            key = card["name"].casefold()
            if key in seen:
                continue
            seen.add(key)
            cards.append(card)
    return cards


def _fast_product_answer(
    cards_or_hits: List[Dict[str, Any]],
    *,
    query: str,
    output_language: str,
    max_items: int = 3,
) -> Optional[str]:
    if not _looks_like_product_recommendation(query):
        return None
    if output_language == "hindi":
        return None
    query_terms = _query_terms_for_product_match(query)
    cards = (
        cards_or_hits
        if cards_or_hits and "name" in cards_or_hits[0]
        else _product_cards_from_hits(cards_or_hits, query_terms=query_terms)
    )
    if not cards:
        return None
    # If this is a price query and none of the cards carry price data,
    # skip the fast path so the LLM can answer from Weaviate chunk context
    # (which includes full pricing from the catalog markdown).
    if _is_price_query(query) and not any(
        (card.get("price") or "").strip() for card in cards
    ):
        return None
    labels = _FIELD_LABELS.get(output_language, _FIELD_LABELS["english"])
    emoji = _emoji_for_query(query)
    intro = f"{emoji} {labels['intro']}" if emoji else labels["intro"]
    lines = [intro, ""]
    for idx, card in enumerate(cards[:max_items], 1):
        lines.append(f"{idx}. *{card['name']}*")
        for key in ("category", "form", "used_for", "benefits", "dosage", "duration", "pack", "price", "stock", "link"):
            value = (card.get(key) or "").strip()
            if value:
                lines.append(f"- {labels[key]}: {value}")
        lines.append("")
    lines.append(labels["outro"])
    return "\n".join(lines).strip()


def _stringish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    if isinstance(value, dict):
        return ", ".join(
            f"{k}: {v}" for k, v in value.items() if v is not None and str(v).strip()
        )
    return str(value).strip()


def _attr_value(attrs: Optional[Dict[str, Any]], *keys: str) -> str:
    data = attrs or {}
    lowered = {str(k).casefold(): v for k, v in data.items()}
    for key in keys:
        if key in data:
            return _stringish(data[key])
        low = key.casefold()
        if low in lowered:
            return _stringish(lowered[low])
    return ""


def _price_text(price_json: Optional[Dict[str, Any]]) -> str:
    if not price_json:
        return ""
    currency = _stringish(price_json.get("currency") or "INR")
    mrp = price_json.get("mrp")
    cod = price_json.get("cod_price")
    prepaid = price_json.get("prepaid_price")
    prepaid_offer = _stringish(price_json.get("prepaid_offer") or "")
    # Multi-tier pricing (new format)
    if cod is not None or prepaid is not None:
        parts: List[str] = []
        if mrp is not None:
            parts.append(f"MRP {currency} {mrp}")
        if cod is not None:
            parts.append(f"Cash on Delivery {currency} {cod}")
        if prepaid is not None:
            label = f"Prepaid {currency} {prepaid}"
            if prepaid_offer:
                label += f" ({prepaid_offer})"
            parts.append(label)
        return " | ".join(parts)
    # Legacy / fallback format
    if "text" in price_json:
        return _stringish(price_json.get("text"))
    amount = (
        price_json.get("selling_price")
        or price_json.get("sale_price")
        or price_json.get("amount")
        or price_json.get("price")
    )
    pack = _stringish(price_json.get("pack") or price_json.get("unit"))
    parts = []
    if mrp is not None:
        parts.append(f"MRP {currency} {mrp}".strip())
    if amount is not None:
        label = "Selling" if mrp is not None else "Price"
        parts.append(f"{label} {currency} {amount}".strip())
    if pack:
        parts.append(pack)
    if parts:
        return " | ".join(parts)
    return _stringish(price_json)


def _product_card_from_db(product: Product) -> Dict[str, str]:
    attrs = product.attributes_json or {}
    image_url = _attr_value(
        attrs,
        "image_url",
        "imageUrl",
        "image",
        "image_link",
        "photo_url",
        "picture_url",
    )
    return {
        "name": product.name,
        "category": product.category or _attr_value(attrs, "category", "product_category", "type") or "",
        "form": _attr_value(attrs, "form", "form_variant", "variant", "formulation") or "",
        "used_for": _attr_value(
            attrs,
            "used_for",
            "uses",
            "indications",
            "keywords",
        )
        or (product.description or ""),
        "benefits": _attr_value(attrs, "benefits", "key_benefits", "advantage"),
        "dosage": _attr_value(
            attrs,
            "dosage",
            "dosage_schedule",
            "dosage & schedule",
            "how_to_use",
            "usage",
        ),
        "duration": _attr_value(attrs, "duration", "recommended_duration", "course_duration", "treatment_duration"),
        "pack": _attr_value(attrs, "available_packs", "pack", "packs", "pack_size", "unit"),
        "price": _price_text(product.price_json),
        "_price_json": product.price_json or {},
        "stock": _attr_value(attrs, "stock_status", "stock", "availability"),
        "link": _attr_value(attrs, "product_url", "url", "link"),
        "image_url": image_url,
        "image_alt": _attr_value(attrs, "image_alt", "imageAlt", "alt_text", "alt")
        or product.name,
    }


def _product_card_context_chunks(cards: List[Dict[str, str]]) -> List[str]:
    chunks: List[str] = []
    for card in cards:
        lines = [f"Product: {card.get('name', '')}".strip()]
        if card.get("category"):
            lines.append(f"Category: {card['category']}")
        if card.get("form"):
            lines.append(f"Form: {card['form']}")
        if card.get("used_for"):
            lines.append(f"Used For: {card['used_for']}")
        if card.get("benefits"):
            lines.append(f"Benefits: {card['benefits']}")
        if card.get("dosage"):
            lines.append(f"Dosage: {card['dosage']}")
        if card.get("duration"):
            lines.append(f"Recommended Duration: {card['duration']}")
        if card.get("pack"):
            lines.append(f"Available Packs: {card['pack']}")
        # Always emit full price block so the LLM sees all three tiers
        price_str = card.get("price") or ""
        if price_str:
            lines.append(f"Price: {price_str}")
        # Emit individual price tiers as separate lines for easy LLM extraction
        raw_pj = card.get("_price_json")
        if raw_pj and isinstance(raw_pj, dict):
            mrp = raw_pj.get("mrp")
            cod = raw_pj.get("cod_price")
            pre = raw_pj.get("prepaid_price")
            cur = raw_pj.get("currency", "INR")
            offer = raw_pj.get("prepaid_offer", "")
            if mrp:
                lines.append(f"MRP: {cur} {mrp}")
            if cod:
                lines.append(f"Cash on Delivery (COD) Price: {cur} {cod}")
            if pre:
                offer_note = f" ({offer})" if offer else ""
                lines.append(f"Prepaid Price: {cur} {pre}{offer_note}")
        if card.get("stock"):
            lines.append(f"Stock Status: {card['stock']}")
        if card.get("link"):
            lines.append(f"Product Link: {card['link']}")
        if card.get("image_url"):
            lines.append(f"Image URL: {card['image_url']}")
            if card.get("image_alt"):
                lines.append(f"Image Alt: {card['image_alt']}")
        chunks.append("\n".join(line for line in lines if line.strip()))
    return chunks


def _recommended_product_media(cards: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen_urls: set[str] = set()
    for card in cards:
        image_url = (card.get("image_url") or "").strip()
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        out.append(
            {
                "name": (card.get("name") or "").strip(),
                "image_url": image_url,
                "image_alt": (card.get("image_alt") or card.get("name") or "").strip(),
                "link": (card.get("link") or "").strip(),
            }
        )
    return out


async def _product_cards_from_db(
    db: Any,
    *,
    company_id: uuid.UUID,
    product_ids: List[str],
) -> List[Dict[str, str]]:
    parsed: List[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for raw in product_ids:
        try:
            pid = uuid.UUID(str(raw))
        except (TypeError, ValueError):
            continue
        if pid in seen:
            continue
        seen.add(pid)
        parsed.append(pid)
    products = await ProductRepository(db).list_by_ids_for_company(company_id, parsed)
    return [_product_card_from_db(p) for p in products]


async def _product_cards_from_db_search(
    db: Any,
    *,
    company_id: uuid.UUID,
    query: str,
    limit: int = 3,
) -> List[Dict[str, str]]:
    """Best-effort product lookup from Postgres when Weaviate is unavailable."""
    raw_query = (query or "").casefold()
    query_terms = set(_TOKEN_RE.findall(raw_query))
    if not raw_query.strip() or not query_terms:
        return []

    products = await ProductRepository(db).list_by_company(
        company_id,
        is_active=True,
        limit=200,
    )
    scored: List[tuple[float, str, Product]] = []
    weak_terms = {
        "what",
        "which",
        "price",
        "cost",
        "rate",
        "tell",
        "about",
        "product",
        "medicine",
        "hai",
        "kya",
        "for",
        "the",
        "and",
        "of",
        "is",
        "do",
        "you",
        "have",
    }
    useful_terms = {t for t in query_terms if len(t) >= 3 and t not in weak_terms}
    for product in products:
        attrs = product.attributes_json or {}
        synonyms = product.synonyms_json or []
        haystack_parts = [
            product.name or "",
            product.sku or "",
            product.category or "",
            product.description or "",
            " ".join(synonyms),
            _stringish(attrs.get("used_for")),
            _stringish(attrs.get("benefits")),
            _stringish(attrs.get("keywords")),
        ]
        haystack = " ".join(haystack_parts).casefold()
        name = (product.name or "").casefold()
        name_terms = set(_TOKEN_RE.findall(name))
        score = 0.0

        # Full product name found verbatim in query
        if name and name in raw_query:
            score += 30.0
        # All tokens of product name found in query terms
        elif name_terms and name_terms.issubset(query_terms | useful_terms):
            score += 20.0
        # Majority of name tokens found (partial name match)
        elif name_terms:
            matched = name_terms & (query_terms | useful_terms)
            if matched and len(matched) / len(name_terms) >= 0.5:
                score += 10.0 * (len(matched) / len(name_terms))

        # Synonym exact match in query
        for syn in synonyms:
            syn_lower = syn.casefold()
            if len(syn_lower) >= 4 and syn_lower in raw_query:
                score += 15.0
                break

        overlap = useful_terms & set(_TOKEN_RE.findall(haystack))
        score += len(overlap) * 2.0
        # Require a meaningful match: either a name/synonym hit (score >= 10)
        # or at least 2 useful keyword overlaps (score >= 4), to avoid
        # returning loosely related products when the query is broad.
        if score >= 4.0:
            scored.append((score, product.name.casefold(), product))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [_product_card_from_db(product) for _, _, product in scored[:limit]]


def _emoji_for_query(query: str) -> str:
    terms = _query_terms_for_product_match(query)
    raw = (query or "").casefold()
    for term, emoji in _SITUATION_EMOJI.items():
        term_l = term.casefold()
        if term_l in terms:
            return emoji
        if " " in term_l and term_l in raw:
            return emoji
        if term_l.isascii():
            if len(term_l) > 2 and re.search(rf"\b{re.escape(term_l)}\b", raw):
                return emoji
            continue
        if term_l in raw:
            return emoji
    return ""


def _answer_has_known_emoji(answer: str) -> bool:
    text = answer or ""
    return any(emoji in text for emoji in set(_SITUATION_EMOJI.values()))


_URL_RE = re.compile(r"https?://\S+")
_LATIN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")


def _strip_urls(text: str) -> str:
    return _URL_RE.sub("", text or "")


def _has_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in (text or ""))


def _needs_language_repair(answer: str, output_language: str) -> bool:
    """
    Detect obvious language drift in generated replies.

    URLs and exact product names can legitimately contain Latin text, especially
    for Hindi replies, so this guard only catches clear drift. Repair is a
    second-pass rewrite, not a fact-generation step.
    """
    text = _strip_urls(answer)
    if not text.strip():
        return False
    if output_language == "english":
        return _has_devanagari(text)
    if output_language == "hinglish":
        return _has_devanagari(text)
    if output_language == "hindi":
        devanagari_count = sum(1 for ch in text if "\u0900" <= ch <= "\u097F")
        latin_words = _LATIN_WORD_RE.findall(text)
        if latin_words and devanagari_count == 0:
            return True
        # Allow a few product/brand words, but rewrite if English fragments
        # dominate the Hindi response.
        return len(latin_words) >= 8 and devanagari_count < 80
    return False


async def _repair_answer_language(
    llm: LLMClientProtocol,
    *,
    answer: str,
    output_language: str,
) -> str:
    try:
        repaired = await llm.generate_answer(
            context_chunks=[answer],
            user_query=(
                "Rewrite the draft reply into the required output language. "
                "Preserve product names, brand names, prices, dosage numbers, and URLs exactly. "
                "Do not add new facts. Do not remove useful product details. "
                "Return only the rewritten WhatsApp reply."
            ),
            system_prompt=(
                "You are a language cleanup step for a WhatsApp chatbot. "
                "Use only the draft reply provided in Context. "
                "Keep the same meaning and formatting as much as possible."
            ),
            output_language=output_language,
            conversation_history=None,
        )
        repaired = whatsapp_friendly_text(repaired)
        return repaired.strip() or answer
    except Exception as exc:
        logger.info(
            "Language repair failed; keeping original answer",
            extra={"output_language": output_language, "error": str(exc)},
        )
        return answer


def _prefer_direct_product_hits(
    hits: List[Dict[str, Any]],
    *,
    query: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    For product recommendation questions, keep the LLM focused on directly
    matching product chunks instead of loosely related wellness/policy chunks.
    """
    if not _looks_like_product_recommendation(query):
        return hits
    query_terms = _query_terms_for_product_match(query)
    if not query_terms:
        return hits

    scored: List[tuple[float, int, Dict[str, Any]]] = []
    for idx, hit in enumerate(hits):
        if not _is_productish_hit(hit):
            continue
        score = _product_match_score(hit, query_terms)
        if score <= 0:
            continue
        scored.append((score, idx, hit))
    if not scored:
        return hits

    # If the user asks broadly for stamina, product catalog pages can include
    # unrelated immunity/general wellness items. Prefer sexual-stamina products
    # when the matching chunks explicitly say they are for intimacy/men's health.
    if "stamina" in query_terms:
        sexual_scored = [
            item
            for item in scored
            if _SEXUAL_STAMINA_TERMS
            & set(_TOKEN_RE.findall((item[2].get("chunk_text") or "").lower()))
        ]
        if sexual_scored:
            scored = sexual_scored

    scored.sort(key=lambda item: (-item[0], item[1]))
    max_chunks = max(1, min(top_k, 5))
    return [
        _trim_hit_to_matching_product_sections(hit, query_terms)
        for _, _, hit in scored[:max_chunks]
    ]


def _sanitize_for_json(obj: Any) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def _clip_raw_result_for_db(raw: Any) -> Any:
    cleaned = _sanitize_for_json(raw)
    try:
        encoded = json.dumps(cleaned, default=str).encode("utf-8")
    except (TypeError, ValueError):
        return {"_error": "raw_result not JSON-serializable"}
    if len(encoded) <= _RAW_JSON_MAX_BYTES:
        return cleaned
    return {
        "_truncated": True,
        "original_bytes": len(encoded),
        "preview": encoded[:8000].decode("utf-8", errors="replace"),
    }


RetrievalLogPersister = Callable[[Dict[str, Any]], Awaitable[None]]


async def _persist_retrieval_log_best_effort(payload: Dict[str, Any]) -> None:
    from app.core.database import AsyncSessionLocal
    from app.repositories.retrieval_log_repository import RetrievalLogRepository

    try:
        async with AsyncSessionLocal() as session:
            repo = RetrievalLogRepository(session)
            try:
                await repo.create(payload)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.warning(
                    "retrieval_logs insert failed (isolated session)",
                    exc_info=True,
                )
    except Exception:
        logger.warning(
            "retrieval_logs could not open/write session",
            exc_info=True,
        )


async def _persist_product_events_best_effort(
    company_id: uuid.UUID,
    product_ids: List[str],
    event_type: str,
    channel: str,
    conversation_id: Optional[uuid.UUID],
    query_text: str,
) -> None:
    """
    Fire product analytics events in an isolated session.
    Non-fatal: any error is logged and swallowed.
    """
    from app.core.database import AsyncSessionLocal
    from app.repositories.product_event_repository import ProductEventRepository

    try:
        async with AsyncSessionLocal() as session:
            repo = ProductEventRepository(session)
            try:
                for pid_str in product_ids:
                    try:
                        pid = uuid.UUID(pid_str)
                    except (ValueError, AttributeError):
                        continue
                    await repo.create_event(
                        company_id=company_id,
                        product_id=pid,
                        event_type=event_type,
                        channel=channel,
                        conversation_id=conversation_id,
                        query_text=query_text[:500] if query_text else None,
                    )
                await session.commit()
            except Exception:
                await session.rollback()
                logger.warning(
                    "product_events insert failed",
                    exc_info=True,
                )
    except Exception:
        logger.warning(
            "product_events could not open session",
            exc_info=True,
        )


def _hits_from_search_result(search_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    hits = search_result.get("hits")
    if hits:
        return list(hits)
    chunks = search_result.get("chunks") or []
    return [
        {
            "chunk_text": c,
            "file_name": "",
            "document_id": None,
            "chunk_index": None,
            "score": None,
        }
        for c in chunks
    ]


def _scores_for_fallback(hits: List[Dict[str, Any]], top_score: Optional[float]) -> List[float]:
    out: List[float] = []
    for h in hits:
        s = h.get("score")
        if s is None:
            continue
        try:
            f = float(s)
        except (TypeError, ValueError):
            continue
        if math.isnan(f) or math.isinf(f):
            continue
        out.append(f)
    if not out and top_score is not None:
        try:
            ts = float(top_score)
            if not math.isnan(ts) and not math.isinf(ts):
                return [ts]
        except (TypeError, ValueError):
            pass
    return out


class RAGService:
    def __init__(
        self,
        config_repo: CompanyConfigRepository,
        weaviate_client: WeaviateClient,
        llm_client: LLMClientProtocol,
        fallback_service: FallbackService,
        default_top_k: int = 5,
        default_score_threshold: float = 0.4,
        default_hybrid_alpha: float = 0.5,
        default_confidence_strategy: str = "top",
        default_avg_top_n: int = 3,
        default_conversation_turns: int = 8,
        augment_search_with_history: bool = True,
        log_persister: Optional[RetrievalLogPersister] = None,
        embedding_client: Optional["EmbeddingClientProtocol"] = None,
    ) -> None:
        self._config_repo = config_repo
        self._weaviate = weaviate_client
        self._llm = llm_client
        self._fallback_svc = fallback_service
        self._default_top_k = default_top_k
        self._default_threshold = default_score_threshold
        self._default_hybrid_alpha = default_hybrid_alpha
        self._default_confidence_strategy = default_confidence_strategy
        self._default_avg_top_n = default_avg_top_n
        self._default_conversation_turns = default_conversation_turns
        self._augment_search = augment_search_with_history
        self._embedding = embedding_client
        self._log_persister: RetrievalLogPersister = (
            log_persister or _persist_retrieval_log_best_effort
        )

    async def process_query(
        self,
        company_id: uuid.UUID,
        query: str,
        conversation_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
        background_tasks: Any = None,
        *,
        conversation_messages: Optional[List[Any]] = None,
        conversation_transcript: Optional[str] = None,
        conversation_reply_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        ``conversation_reply_language`` is the last decisive user language in
        the thread (e.g. WhatsApp ``Conversation.detected_language`` before the
        current message). Short/ambiguous queries keep replying in that language.
        """
        config = await self._config_repo.get_by_company(company_id)
        if config is None:
            logger.warning(
                "No config found for company; using fallback",
                extra={"company_id": str(company_id)},
            )
            return self._fallback_result("No company config found.", "english")

        collection = config.weaviate_collection
        rag_config = config.rag_config_json or {}
        threshold = float(rag_config.get("score_threshold", self._default_threshold))
        top_k = int(rag_config.get("top_k", self._default_top_k))
        hybrid_alpha = float(rag_config.get("hybrid_alpha", self._default_hybrid_alpha))
        confidence_strategy = str(
            rag_config.get("confidence_strategy", self._default_confidence_strategy)
        )
        avg_top_n = int(rag_config.get("confidence_avg_top_n", self._default_avg_top_n))
        use_mmr = bool(rag_config.get("use_mmr", True))
        mmr_lambda = float(rag_config.get("mmr_lambda", 0.55))
        system_prompt = config.system_prompt if hasattr(config, "system_prompt") else None
        fallback_config = config.fallback_config_json
        supported_langs = list(config.supported_languages or ["english"])
        default_lang = config.default_language or "english"

        detected_lang = detect_language(query)
        output_lang = resolve_reply_language(
            current_text=query,
            conversation_last_language=conversation_reply_language,
            company_supported_languages=supported_langs,
            default_language=default_lang,
        )
        if _looks_like_identity_query(query):
            return {
                "response_type": "rag",
                "answer": whatsapp_friendly_text(_identity_answer(output_lang)),
                "fallback_triggered": False,
                "language": output_lang,
                "detected_language": detected_lang,
                "top_score": None,
                "sources": [],
                "product_ids": [],
                "recommended_products": [],
            }

        history_text = conversation_transcript
        if history_text is None and conversation_messages:
            max_turns = int(
                rag_config.get("conversation_turns", self._default_conversation_turns)
            )
            history_text = format_conversation_transcript(
                conversation_messages,
                max_turns=max_turns,
            )
        if _looks_like_greeting(query):
            return {
                "response_type": "rag",
                "answer": whatsapp_friendly_text(_first_greeting_answer(output_lang)),
                "fallback_triggered": False,
                "language": output_lang,
                "detected_language": detected_lang,
                "top_score": None,
                "sources": [],
                "product_ids": [],
                "recommended_products": [],
            }

        augment = self._augment_search and bool(
            rag_config.get("augment_search_with_history", True)
        )
        if _looks_like_product_recommendation(query):
            augment = False
        search_query = query
        if augment and history_text and history_text.strip():
            search_query = merge_query_with_history(query, history_text)
        else:
            search_query = _expand_multilingual_search_query(query)

        normalized = normalize_query(search_query, detected_lang)
        is_product_query = _looks_like_product_recommendation(query)
        is_price_q = _is_price_query(query)
        search_top_k = max(top_k, 24) if is_product_query else top_k

        query_vector: Optional[List[float]] = None
        embed_enabled = bool(rag_config.get("use_embeddings", True))
        if self._embedding is not None and embed_enabled:
            try:
                query_vector = await self._embedding.embed_query(normalized[:8000])
                if not query_vector:
                    query_vector = None
            except Exception as exc:
                logger.warning(
                    "Query embedding failed; using BM25 only",
                    extra={"company_id": str(company_id), "error": str(exc)},
                )
                query_vector = None

        search_result = await self._weaviate.hybrid_search(
            collection_name=collection,
            query=normalized,
            top_k=search_top_k,
            query_vector=query_vector,
            hybrid_alpha=hybrid_alpha,
        )

        hits = _hits_from_search_result(search_result)
        top_score: Optional[float] = search_result.get("top_score")
        if top_score is not None and isinstance(top_score, float) and (
            math.isnan(top_score) or math.isinf(top_score)
        ):
            top_score = None
        raw_result = search_result.get("raw", {})
        scores_fb = _scores_for_fallback(hits, top_score)

        use_fallback = self._fallback_svc.should_fallback(
            scores_fb,
            threshold,
            confidence_strategy,
            avg_top_n=avg_top_n,
        )

        selected_hits = hits
        if is_product_query:
            selected_hits = _prefer_direct_product_hits(
                hits,
                query=query,
                top_k=top_k,
            )
        elif not use_fallback and use_mmr and len(hits) > 1:
            selected_hits = mmr_lexical_select(
                hits,
                query=query,
                max_chunks=top_k,
                lambda_mult=mmr_lambda,
            )
        elif not use_mmr:
            selected_hits = hits[:top_k]

        chunk_strings = [format_hit_for_llm(h) for h in selected_hits]
        chunk_strings = dedupe_chunk_texts(chunk_strings)

        sources: List[Dict[str, Any]] = []
        seen_k: set[tuple[Any, ...]] = set()
        # Collect unique product_ids from retrieved chunks for analytics
        retrieved_product_ids: List[str] = []
        seen_pids: set[str] = set()
        for h in selected_hits:
            key = (
                h.get("file_name"),
                h.get("document_id"),
                h.get("chunk_index"),
            )
            if key in seen_k:
                continue
            seen_k.add(key)
            sources.append(
                {
                    "file_name": h.get("file_name") or "",
                    "document_id": str(h["document_id"])
                    if h.get("document_id") is not None
                    else None,
                    "chunk_index": h.get("chunk_index"),
                    "score": h.get("score"),
                    "product_id": h.get("product_id"),
                }
            )
            pid = h.get("product_id")
            if pid and str(pid) not in seen_pids:
                seen_pids.add(str(pid))
                retrieved_product_ids.append(str(pid))

        if use_fallback and _looks_like_greeting_or_small_talk(query):
            use_fallback = False
            chunk_strings = [_SMALL_TALK_CONTEXT_CHUNK]
            sources = []
            retrieved_product_ids = []

        llm_failed = False
        product_cards: List[Dict[str, str]] = []
        recommended_product_cards: List[Dict[str, str]] = []
        # On any non-greeting fallback, always try a direct DB name-match.
        # This handles typo queries (e.g. "prise of kaaama gold") where keyword
        # regex fails but the product name tokens still score above zero in the
        # DB scorer, avoiding false fallbacks on price/buy queries.
        if use_fallback and not _looks_like_greeting_or_small_talk(query):
            db = getattr(self._config_repo, "db", None)
            if db is not None:
                try:
                    product_cards = await _product_cards_from_db_search(
                        db,
                        company_id=company_id,
                        query=query,
                        limit=3,
                    )
                except Exception as _db_exc:
                    logger.debug(
                        "DB product search failed during fallback recovery",
                        extra={"error": str(_db_exc)},
                    )
                    product_cards = []
                if product_cards:
                    use_fallback = False
                    chunk_strings = _product_card_context_chunks(product_cards)
                    sources = []
                    retrieved_product_ids = []
        if use_fallback:
            answer = self._fallback_svc.get_fallback_message(
                fallback_config, output_lang
            )
            response_type = "fallback"
        else:
            product_db_lookup_attempted = False
            if is_product_query and retrieved_product_ids:
                db = getattr(self._config_repo, "db", None)
                if db is not None:
                    product_db_lookup_attempted = True
                    try:
                        product_cards = await _product_cards_from_db(
                            db,
                            company_id=company_id,
                            product_ids=retrieved_product_ids,
                        )
                    except Exception as _db_exc:
                        logger.debug(
                            "DB product cards lookup failed",
                            extra={"error": str(_db_exc)},
                        )
                        product_cards = []
            if product_db_lookup_attempted and not product_cards:
                answer = self._fallback_svc.get_fallback_message(
                    fallback_config, output_lang
                )
                response_type = "fallback"
                use_fallback = True
            else:
                # For price queries where DB cards carry no price information,
                # prefer the Weaviate chunk strings (which include full catalog
                # pricing) over the stripped DB card context so the LLM can
                # read and report MRP / COD / prepaid figures directly.
                _price_missing = _is_price_query(query) and product_cards and not any(
                    (c.get("price") or "").strip() for c in product_cards
                )
                llm_chunks = (
                    chunk_strings
                    if _price_missing or not product_cards
                    else _product_card_context_chunks(product_cards)
                )
                try:
                    answer = await self._llm.generate_answer(
                        context_chunks=llm_chunks,
                        user_query=query,
                        system_prompt=system_prompt,
                        output_language=output_lang,
                        conversation_history=history_text,
                    )
                    response_type = "rag"
                    recommended_product_cards = product_cards
                    if not recommended_product_cards:
                        _db = getattr(self._config_repo, "db", None)
                        if _db is not None:
                            try:
                                recommended_product_cards = (
                                    await _product_cards_from_db_search(
                                        _db,
                                        company_id=company_id,
                                        query=query,
                                        limit=3,
                                    )
                                )
                            except Exception:
                                recommended_product_cards = []
                except Exception as exc:
                    logger.warning(
                        "LLM generate_answer failed",
                        extra={"company_id": str(company_id), "error": str(exc)},
                        exc_info=True,
                    )
                    llm_failed = True
                    answer = (
                        "I'm having trouble generating a reply right now. "
                        "Please try a shorter question or again in a moment."
                    )
                    response_type = "fallback"

        fallback_out = use_fallback or llm_failed
        answer = whatsapp_friendly_text(answer)
        if not llm_failed and _needs_language_repair(answer, output_lang):
            answer = await _repair_answer_language(
                self._llm,
                answer=answer,
                output_language=output_lang,
            )
        emoji = _emoji_for_query(query)
        if emoji and not _answer_has_known_emoji(answer):
            answer = f"{emoji} {answer}"
        if fallback_out:
            sources = []
            recommended_product_cards = []

        # ── Product analytics events ─────────────────────────────────── #
        if retrieved_product_ids:
            channel = "portal" if conversation_id is None else "whatsapp"
            if background_tasks is not None:
                background_tasks.add_task(
                    _persist_product_events_best_effort,
                    company_id,
                    retrieved_product_ids,
                    "retrieved",
                    channel,
                    conversation_id,
                    query,
                )
                if not fallback_out:
                    background_tasks.add_task(
                        _persist_product_events_best_effort,
                        company_id,
                        retrieved_product_ids,
                        "suggested",
                        channel,
                        conversation_id,
                        query,
                    )
            else:
                asyncio.create_task(
                    _persist_product_events_best_effort(
                        company_id, retrieved_product_ids, "retrieved",
                        channel, conversation_id, query,
                    )
                )
                if not fallback_out:
                    asyncio.create_task(
                        _persist_product_events_best_effort(
                            company_id, retrieved_product_ids, "suggested",
                            channel, conversation_id, query,
                        )
                    )

        log_payload = {
            "company_id": company_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "query_text": query,
            "normalized_query": normalized,
            "detected_language": detected_lang,
            "weaviate_collection": collection,
            "top_k": top_k,
            "top_score": top_score,
            "result_count": len(hits),
            "fallback_triggered": fallback_out,
            "handoff_triggered": False,
            "raw_result_json": _clip_raw_result_for_db(
                {
                    "weaviate": raw_result,
                    "search_mode": search_result.get("search_mode"),
                    "scores": scores_fb,
                    "confidence_strategy": confidence_strategy,
                }
            ),
        }
        if background_tasks is not None:
            background_tasks.add_task(self._log_persister, log_payload)
        else:
            asyncio.create_task(self._log_persister(log_payload))

        return {
            "response_type": response_type,
            "answer": answer,
            "fallback_triggered": fallback_out,
            "language": output_lang,
            "detected_language": detected_lang,
            "top_score": top_score,
            "sources": sources,
            "product_ids": retrieved_product_ids,
            "recommended_products": _recommended_product_media(recommended_product_cards),
        }

    def _fallback_result(self, msg: str, language: str) -> Dict[str, Any]:
        return {
            "response_type": "fallback",
            "answer": whatsapp_friendly_text(msg),
            "fallback_triggered": True,
            "language": language,
            "detected_language": language,
            "sources": [],
            "product_ids": [],
            "recommended_products": [],
        }
