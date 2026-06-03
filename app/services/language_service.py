"""
Language detection and normalization service.

Approach
--------
Rule-based detection without any ML dependency – suitable for Phase 2.
Accuracy is good for clearly Hindi or clearly English text.  Hinglish
detection is intentionally broad (few false negatives over false positives)
since the cost of misidentification is minor (slightly different LLM instruction).

Devanagari Unicode block: U+0900 – U+097F
Hinglish markers: common Hindi words written in Roman script.
"""
import re
from typing import Any, List, Optional

# Common Hindi function words and filler words written in Roman script
_HINGLISH_MARKERS = frozenset([
    # Basic verbs / forms
    "hai", "hain", "hoon", "hu", "hun", "tha", "thi", "the",
    "hota", "hoti", "hote", "hoga", "hogi", "hoge",
    "kar", "karo", "karna", "karta", "karti", "karte",
    "kiya", "kiye", "karti", "karunga", "karungi",
    "ki", "kijiye", "kariye", "kara", "karaya", "karwa", "karwao",
    "hona", "ho", "hoye", "hua", "hui", "hue", "huye",
    "raha", "rahi", "rahe", "rha", "rhi", "rhe",
    "gaya", "gayi", "gaye", "ja", "jao", "jana", "jata", "jati", "jate",
    "aana", "aao", "aya", "ayi", "aaye", "aata", "aati", "aate",
    "dena", "do", "dijiye", "diya", "di", "de", "dedo", "dede",
    "lena", "lo", "lijiye", "liya", "le", "lelo", "lelu", "leni", "lena",
    "mil", "mila", "mili", "mile", "milna", "milta", "milti", "milte",
    "rakho", "rakhna", "rakha", "rakhi", "rakhte",
    "lag", "laga", "lagi", "lage", "lagta", "lagti", "lagte", "lagao",
    "pata", "malum", "maalum", "janna", "jaanna", "janana", "batana",
    "bhejo", "bhejna", "bheja", "bheji", "bhejdo", "bhej", "mangwa",
    "mangwana", "mangao", "mangaya", "mangani",
    "dikha", "dikhao", "dikhana", "dikhado", "dikhaao",
    "samjhao", "samjhana", "samjhado", "samjhaao",
    "banao", "banana", "banado", "banwao", "banwana",
    "lagado", "laga do", "lagana", "hatado", "hatao", "hatana",
    "check", "check karo", "confirm", "confirm karo",
    "suggest", "suggest karo", "recommend", "recommend karo",
    "prescribe", "prescribe karo", "booking", "book", "book karo",
    "call", "call karo", "phone", "phone karo",

    # Connectors
    "aur", "ya", "lekin", "par", "kyunki", "toh", "to", "phir",
    "jab", "tab", "agar", "magar", "fir", "warna", "varnah",
    "isliye", "isiliye", "kyoki", "kyonki", "jabki", "balki",
    "jaise", "waise", "vaise", "jaisa", "waisa", "vaisa",
    "jiski", "jiska", "jiske", "jisme", "jahan", "jahaan",

    # Negation
    "nahi", "nhi", "nahin", "na", "mat", "kabhi nahi", "bilkul nahi",

    # Question words
    "kya", "kaun", "kyun", "kyu", "kab", "kahan", "kidhar", "kaise",
    "kitna", "kitni", "kitne", "kis", "kisi", "kisme", "kiske", "kiska",
    "kiski", "kaunsa", "kaunsi", "kaunse", "kon", "konsa", "konsi", "konse",

    # Pronouns
    "main", "mai", "mein", "me", "hum", "ham", "mera", "meri", "mere",
    "tera", "teri", "tere", "tum", "aap", "tu",
    "unka", "unki", "unke", "unhe", "unko",
    "isko", "isse", "iska", "iski", "iske",
    "usko", "usse", "uska", "uski", "uske",
    "mujhe", "muje", "mujko", "mujhko", "mujhse", "mujhme",
    "hume", "humko", "hamko", "hamse", "apko", "aapko", "apse", "aapse",
    "tumhe", "tumko", "tujhe", "tujko", "khud", "apna", "apni", "apne",
    "ye", "yeh", "yah", "wo", "woh", "vo", "vah", "yehi", "wahi", "vahi",
    "inhe", "inka", "inki", "inke", "inhone", "unhone",

    # Postpositions
    "ka", "ki", "ke", "ko", "se", "me", "mein", "par", "pe", "tak", "ke liye", "liye",
    "wale", "wali", "wala", "walon", "dwara", "dvara", "saath", "sath",
    "andar", "bahar", "upar", "neeche", "niche", "aage", "piche", "peeche",
    "pass", "paas", "bina", "liye", "liyeh", "liyee",

    # Common adverbs / modifiers
    "bhi", "sirf", "bas", "bahut", "bohot", "bahot",
    "thoda", "zyada", "jada", "kam", "abhi", "ab",
    "yaha", "yahan", "waha", "wahan",
    "itna", "itni", "itne", "utna", "utni", "utne",
    "jaldi", "dheere", "dhire", "phir", "fir", "dubara", "dobara",
    "pehle", "pahle", "baad", "bad", "baadme", "rozana", "regular",
    "kabhi", "hamesha", "aksar", "aksar", "shayad", "shayad",
    "lagbhag", "karib", "kareeb", "sir", "madam",

    # Common adjectives
    "accha", "acha", "achha", "theek", "sahi", "galat",
    "bura", "badhiya", "mast", "solid", "bekar",
    "zaruri", "jaruri", "important", "asli", "nakli", "sasta", "sasti",
    "saste", "mehenga", "mahinga", "mahanga", "mehengi", "mahangi",
    "naya", "nayi", "naye", "purana", "purani", "purane",
    "chota", "choti", "chote", "bada", "badi", "bade",
    "tez", "tezzi", "halka", "halki", "bhari", "garam", "thanda", "thandi",

    # Commands / casual speech
    "chal", "chalo", "ruk", "ruko", "sun", "suno", "dekh", "dekho",
    "bolo", "bata", "batao", "samajh", "samjha", "samjho",
    "chahiye", "chaiye", "chaahiye", "chahie", "chahiyeh", "chahiya",
    "chahata", "chahati", "chahte", "chahunga", "chahungi",

    # Requests / politeness
    "please", "pls", "plz", "kripya", "zara", "thoda",
    "bhai", "bhaiya", "bhayya", "yaar", "dost", "bhaii",
    "madad", "sahayata",
    "help", "request", "gujarish", "guzarish", "maaf", "maaf kijiye",
    "shukriya", "dhanyawad", "dhanyavaad", "thanks", "thanku",
    "krdo", "kardo", "kro", "krlu", "karu", "karun", "krna",
    "dedo", "de do", "de dena", "dede", "dediye", "dijiyega",
    "batado", "bata do", "bata dena", "btao", "btado", "btana",
    "bhejdo", "bhej do", "bhej dena", "send kardo", "send kar do",
    "dikha do", "dikhado", "samjha do", "samjhado",
    "dawa", "dawai", "daawai", "ilaaj", "ilaj", "neend", "nind",
    "stamina", "taqat", "takat", "kamzori",
    "dard", "jod", "jodo", "jodon", "ghutna", "ghutne", "ghutno",
    "kamar", "peeth", "haddi", "haddiyan", "sujan",
    "bukhar", "khansi", "zukam", "jukam", "sardi", "khujli", "jalan",
    "ulti", "matli", "dast", "kabj", "kabz", "pet", "gas", "acidity",
    "pachan", "hajma", "bhook", "bhukh", "wajan", "vajan", "motapa",
    "sugar", "diabetes", "bp", "pressure", "dil", "saans", "sans",
    "skin", "twacha", "baal", "bal", "hair", "daag", "dhabbe", "pimple",
    "acne", "jhai", "jhaiya", "rang", "safed", "kala", "kali",
    "mahila", "period", "mahavari", "garbh", "pregnancy", "bachcha",
    "purush", "mardana", "sex", "shakti", "energy", "thakan", "thakaan",
    "tension", "stress", "chinta", "ghabrahat", "kamjori", "weakness",

    # Fillers / conversational
    "haan", "han", "ha", "hmm", "hmmm", "arey", "arre",
    "achha", "acha", "oh", "oye", "acha", "ji", "hanji", "haanji",
    "are", "re", "na", "na ji", "acchha", "achchha",

    # Time / frequency
    "roz", "kal", "aaj", "parso", "kabhi", "hamesha",
    "subah", "dopahar", "shaam", "sham", "raat", "din", "hafte", "hafta",
    "mahina", "mahine", "saal", "sal", "time", "samay", "der", "turant",
    "aj", "ajj", "kl",

    # Commerce / support words common in WhatsApp chats
    "daam", "dam", "kimat", "keemat", "rate", "paisa", "paise", "rupaye",
    "kitne ka", "discount", "chhoot", "offer", "cod", "online", "payment",
    "order", "mangwana", "delivery", "deliver", "parcel", "courier",
    "address", "pincode", "pin", "gaon", "shehar", "shahar", "district",
    "return", "refund", "badalna", "exchange", "cancel", "track", "tracking",
    "available", "milega", "mil jayega", "stock", "khareedna", "kharidna",
    "leneka", "lenge", "lunga", "lungi", "bhej sakte", "bhejoge",

    # Common Hinglish slang
    "scene", "setting", "jugaad", "timepass", "bakchodi",
    "faltu", "jhakkas", "pataka", "item",

    # Agreement / disagreement
    "haan", "hanji", "bilkul", "sahi", "theek",
    "nahi", "nah", "nope",

    # Respect / suffix
    "ji"
])

# Markers that are too ambiguous in English text; they create false positives.
# Example: "to" and "me" are valid Hinglish tokens but appear frequently in
# normal English questions ("how to...", "send me...").
_AMBIGUOUS_MARKERS = frozenset([
    "to",
    "me",
    "no",
    "oh",
    "the",
    # English words often used in Hinglish, but unsafe alone.
    "help",
    "request",
    "thanks",
    "regular",
    "important",
    "stamina",
    "skin",
    "hair",
    "sex",
    "energy",
    "stress",
    "gas",
    "acidity",
    "sugar",
    "diabetes",
    "bp",
    "pressure",
    "period",
    "pregnancy",
    "order",
    "delivery",
    "deliver",
    "payment",
    "return",
    "refund",
    "discount",
    "offer",
    "cod",
    "online",
    "parcel",
    "courier",
    "address",
    "pincode",
    "pin",
    "exchange",
    "cancel",
    "track",
    "tracking",
    "available",
    "stock",
    "time",
    "rate",
    "product",
])

_HINGLISH_SINGLE_STRONG_MARKERS = frozenset([
    "chahiye", "chaiye", "chaahiye", "chahie", "chahiyeh", "chahiya",
    "mujhe", "muje", "mujko", "mujhko", "aapko", "apko", "tumko", "tujhe",
    "kya", "kyu", "kyun", "kaise", "kaunsa", "kaunsi", "konsa", "konsi",
    "batao", "batana", "batado", "btado", "btao", "dijiye", "kijiye",
    "kardo", "krdo", "kro", "dedo", "dede", "bhejdo", "dikhado",
    "samjhado", "lagado", "hatado", "chalo", "suno", "dekho", "dikhao",
    "madad", "sahayata", "dard", "dawai", "dawa", "ilaaj", "ilaj",
    "jodo", "jodon", "ghutna", "ghutne", "kamzori", "kamjori", "taqat",
    "takat", "neend", "nind", "bukhar", "khansi", "zukam", "jukam",
    "sardi", "khujli", "jalan", "kabj", "kabz", "pet", "pachan",
    "bhook", "bhukh", "baal", "bal", "twacha", "daag", "dhabbe",
    "mahila", "mardana", "shakti", "thakan", "thakaan", "chinta",
])

_HINGLISH_PHRASE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in [
        r"\b(?:de\s*(?:do|dena|dijiye|dijiyega)|dedo|dede)\b",
        r"\b(?:kar|kr)\s*(?:do|dena|dijiye|dijiyega)\b",
        r"\b(?:bata|bta)\s*(?:do|dena|dijiye|dijiyega)\b",
        r"\b(?:bhej|send)\s*(?:do|dena|dijiye|dijiyega|kar\s*do|kardo)\b",
        r"\b(?:dikha|dikhaao|dikhao|show)\s*(?:do|dena|dijiye|dijiyega)\b",
        r"\b(?:samjha|explain)\s*(?:do|dena|dijiye|dijiyega)\b",
        r"\b(?:suggest|recommend|prescribe)\s*(?:kar\s*do|kardo|karo|kijiye)\b",
        r"\b(?:check|confirm|book|call|phone)\s*(?:kar\s*do|kardo|karo|kijiye)\b",
        r"\b(?:order|booking|payment|delivery|refund|return)\s*(?:karna|karo|kar\s*do|kardo|de\s*do|bata\s*do)\b",
        r"\b(?:mujhe|muje|aapko|apko|humko|hamko)\b.*\b(?:chahiye|chaiye|chaahiye|chahie)\b",
        r"\b(?:kitne|kitna|kitni)\s*(?:ka|ki|ke|rupaye|paise|price|rate)\b",
        r"\b(?:kab|kaise|kahan|kidhar)\s*(?:milega|milegi|mile|aayega|ayega|aayegi|deliver|delivery)\b",
    ]
)

# Minimum fraction of text characters that must be Devanagari to call it Hindi
_DEVANAGARI_THRESHOLD = 0.25

# Minimum number of Hinglish marker words to classify as Hinglish
_HINGLISH_MIN_MARKERS = 2

# Minimum fraction of words that must be Hinglish markers
_HINGLISH_MARKER_FRACTION = 0.15
_ENGLISH_GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "hii",
    "hiii",
    "good morning",
    "good afternoon",
    "good evening",
}
_HINGLISH_GREETING_WORDS = {
    "namaste",
    "namaskar",
    "ram ram",
    "pranam",
    "namaste ji",
    "namaskar ji",
    "ram ram ji",
}
_NEUTRAL_SHORT_PHRASES = {
    "ok",
    "okay",
    "k",
    "yes",
    "no",
    "thanks",
    "thank you",
    "thx",
    "ty",
}
_ENGLISH_INTENT_WORDS = {
    "return",
    "refund",
    "policy",
    "order",
    "delivery",
    "shipping",
    "price",
    "product",
    "medicine",
    "suggest",
    "recommend",
    "sleep",
    "stamina",
    "pain",
    "joint",
    "skin",
    "hair",
    "weight",
    "diabetes",
}


def _normalized_short_phrase(text: str) -> str:
    return " ".join(
        text.strip().lower().strip("?!.,;:'\"").split()
    )


def detect_language(text: str) -> str:
    """
    Classify *text* as ``english``, ``hindi``, or ``hinglish``.

    Priority:
      1. If ≥ 25 % of characters are Devanagari → ``hindi``
      2. If ≥ 2 marker words or ≥ 15 % of words are Hinglish markers → ``hinglish``
      3. Otherwise → ``english``

    Args:
        text: Raw user message text.

    Returns:
        One of ``"english"``, ``"hindi"``, ``"hinglish"``.
    """
    if not text or not text.strip():
        return "english"

    phrase = _normalized_short_phrase(text)
    if phrase in _HINGLISH_GREETING_WORDS:
        return "hinglish"
    if phrase in _ENGLISH_GREETING_WORDS:
        return "english"
    if any(pattern.search(phrase) for pattern in _HINGLISH_PHRASE_PATTERNS):
        return "hinglish"

    # Check Devanagari
    devanagari_count = sum(1 for ch in text if "\u0900" <= ch <= "\u097F")
    if devanagari_count / max(len(text), 1) >= _DEVANAGARI_THRESHOLD:
        return "hindi"

    # Check Hinglish markers
    words = text.lower().split()
    if not words:
        return "english"

    marker_count = sum(
        1
        for w in words
        if (token := w.strip("?,!.;:'\"")) in _HINGLISH_MARKERS
        and token not in _AMBIGUOUS_MARKERS
    )
    token_set = {w.strip("?,!.;:'\"").lower() for w in words}
    if marker_count >= _HINGLISH_MIN_MARKERS:
        return "hinglish"
    if token_set & _HINGLISH_SINGLE_STRONG_MARKERS:
        return "hinglish"
    if marker_count / len(words) >= _HINGLISH_MARKER_FRACTION and marker_count >= 2:
        return "hinglish"

    return "english"


def normalize_query(text: str, language: str) -> str:
    """
    Normalize a search query for Weaviate retrieval.

    - English  : strip leading/trailing whitespace, collapse internal spaces.
    - Hinglish : lowercase + collapse spaces (makes BM25 more consistent).
    - Hindi    : strip whitespace, preserve Devanagari casing (unchanged).

    No transliteration or stemming is performed in Phase 2.

    Args:
        text:     Original user query.
        language: Detected language (``english``, ``hindi``, ``hinglish``).

    Returns:
        Normalized query string.
    """
    text = text.strip()
    if language in ("english",):
        return " ".join(text.split())
    elif language == "hinglish":
        return " ".join(text.lower().split())
    else:  # hindi
        return " ".join(text.split())


def is_strong_language_signal(text: str, detected: str) -> bool:
    """
    True when *text* clearly signals which language the user is using.

    Short Latin-only replies (e.g. "ok", "thanks") are treated as weak so we
    can keep replying in the last language they used in this conversation.
    """
    if not text or not text.strip():
        return False
    phrase = _normalized_short_phrase(text)
    if phrase in _ENGLISH_GREETING_WORDS or phrase in _HINGLISH_GREETING_WORDS:
        return True
    if phrase in _NEUTRAL_SHORT_PHRASES:
        return False
    if detected in ("hindi", "hinglish"):
        return True
    # english (or anything else): require enough substance to switch/stick
    stripped = text.strip()
    words = stripped.split()
    word_set = {w.strip("?,!.;:'\"").lower() for w in words}
    if detected == "english" and (word_set & _ENGLISH_INTENT_WORDS):
        return True
    if detected == "english" and len(words) >= 2 and phrase not in _NEUTRAL_SHORT_PHRASES:
        return True
    if len(stripped) >= 36:
        return True
    if len(words) >= 5:
        return True
    return False


def resolve_reply_language(
    current_text: str,
    conversation_last_language: Optional[str],
    company_supported_languages: List[str],
    default_language: str,
) -> str:
    """
    Pick the language for the bot reply.

    Uses the current message when it is a strong language signal; otherwise
    falls back to *conversation_last_language* (last decisive user language).
    """
    detected = detect_language(current_text)
    if is_strong_language_signal(current_text, detected):
        return choose_output_language(
            detected_language=detected,
            company_supported_languages=company_supported_languages,
            default_language=default_language,
        )
    if conversation_last_language:
        return choose_output_language(
            detected_language=conversation_last_language,
            company_supported_languages=company_supported_languages,
            default_language=default_language,
        )
    return choose_output_language(
        detected_language=detected,
        company_supported_languages=company_supported_languages,
        default_language=default_language,
    )


def last_decisive_user_language_from_history(
    history: Optional[List[Any]],
) -> Optional[str]:
    """
    Scan portal *history* (prior turns) for the last user message with a
    strong language signal. Used for stateless portal chat stickiness.
    """
    if not history:
        return None
    last_strong: Optional[str] = None
    for turn in history:
        role = getattr(turn, "role", None)
        if role != "user":
            continue
        content = getattr(turn, "content", "") or ""
        d = detect_language(content)
        if is_strong_language_signal(content, d):
            last_strong = d
    return last_strong


def choose_output_language(
    detected_language: Optional[str],
    company_supported_languages: List[str],
    default_language: str,
) -> str:
    """
    Decide the language the bot reply should be written in.

    Rules (in order):
      1. Use the detected language if it is explicitly supported.
      2. If the user wrote Hinglish (Roman Hindi) but only ``hindi`` is enabled,
         still answer in Hinglish (Roman mix) so the reply matches how they type.
      3. Fall back to the company's default language.

    Args:
        detected_language:           Language detected in the user message.
        company_supported_languages: Languages the company has enabled.
        default_language:            Company's configured default.

    Returns:
        A language string (``"english"``, ``"hindi"``, ``"hinglish"``).
    """
    supported = company_supported_languages or []
    if detected_language and detected_language in supported:
        return detected_language
    if (
        detected_language == "hinglish"
        and "hinglish" not in supported
        and "hindi" in supported
    ):
        return "hinglish"
    return default_language
