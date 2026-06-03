"""
LLM client abstraction layer.

``LLMClientProtocol`` is a runtime Protocol that any LLM backend must satisfy.
``GroqLLMClient``        — production default (``groq`` package, GROQ_API_KEY).
``OpenAILLMClient``      — optional (``openai`` package, OPENAI_API_KEY).
``get_llm_client``       — FastAPI dependency; picks provider via ``LLM_PROVIDER``.

Design goals
------------
- No hard vendor lock-in: swap providers by changing env vars / overrides.
- Fully mockable in tests: ``AsyncMock`` satisfies the protocol.
- Groq calls use the synchronous SDK off the event loop via ``asyncio.to_thread``.

Default Groq settings use a modest ``max_completion_tokens`` and context cap so
requests fit typical free-tier TPM limits; override via env if your tier allows more.
Streaming can be enabled with ``LLM_STREAM=true``; the full reply is still
aggregated into one string for RAG.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Protocol, Union, runtime_checkable

logger = logging.getLogger(__name__)

_CONTEXT_SEP = "\n\n---\n\n"
_TRUNC_SUFFIX = "\n\n[… context truncated …]"
_SYSTEM_TRUNC = "\n\n[… system prompt truncated …]"


def _clip_text(text: str, max_chars: int, suffix: str = _TRUNC_SUFFIX) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    budget = max_chars - len(suffix)
    if budget <= 0:
        return suffix.strip()
    return text[:budget].rstrip() + suffix


def _join_and_truncate_chunks(chunks: List[str], max_chars: int) -> str:
    """Join RAG chunks and truncate to stay within LLM provider token budgets."""
    if max_chars <= 0:
        return ""
    text = _CONTEXT_SEP.join(chunks)
    return _clip_text(text, max_chars, _TRUNC_SUFFIX)


# --------------------------------------------------------------------------- #
# Language → system instruction snippets
# --------------------------------------------------------------------------- #

_LANG_INSTRUCTIONS = {
    "english": (
        "LANGUAGE RULE — STRICT AND NON-NEGOTIABLE: "
        "You MUST respond ONLY in English. "
        "Do NOT use Hindi, Hinglish, Devanagari script, or any other language anywhere in your reply. "
        "This rule applies regardless of the language of the user's question or the provided context."
    ),
    "hindi": (
        "भाषा नियम — कठोर और अनिवार्य: "
        "आपको केवल हिंदी (देवनागरी लिपि) में उत्तर देना है। "
        "रोमन लिपि, अंग्रेजी या हिंग्लिश में एक भी शब्द न लिखें। "
        "संदर्भ या प्रश्न किसी भी भाषा में हो, आपका पूरा उत्तर शुद्ध हिंदी देवनागरी में होना चाहिए। "
        "LANGUAGE RULE — STRICT: Reply ONLY in Hindi using Devanagari script. "
        "Do NOT use English or Roman script anywhere in your response."
    ),
    "hinglish": (
        "LANGUAGE RULE — STRICT AND NON-NEGOTIABLE: "
        "You MUST reply ONLY in Hinglish — Roman-script Hindi naturally mixed with English words, "
        "exactly how Indians type on WhatsApp. "
        "Example style: 'Aapka order 2 din mein aa jayega. Koi aur help chahiye?' "
        "Do NOT reply in formal English sentences only. "
        "Do NOT use Devanagari script. "
        "Your ENTIRE response must follow the casual Hinglish Roman-script style."
    ),
}

_LANG_REMINDER = {
    "english": "[IMPORTANT: Your reply must be in English only]",
    "hindi": "[महत्वपूर्ण: आपका उत्तर केवल हिंदी देवनागरी में होना चाहिए]",
    "hinglish": "[IMPORTANT: Reply in Hinglish Roman script only — not formal English, not Devanagari]",
}

_DEFAULT_SYSTEM_PROMPT = (
    "You are Alka Sharma from SkinRange, a helpful customer support assistant. "
    "You sound warm, patient, practical, and trustworthy, like a knowledgeable local advisor. "
    "Many customers are rural or semi-urban; use simple words, avoid technical jargon, "
    "and understand common Hinglish/Hindi health phrases even when the catalog is in English. "
    "Do not introduce yourself as Alka Sharma from SkinRange in normal replies. "
    "Say your name only when the user asks who you are, what your name is, or whether you are a bot. "
    "Answer the user's question using only the provided context. "
    "If the context does not contain enough information, say so politely. "
    "Context blocks may be labeled with [filename#chunk]; cite them briefly when helpful."
)

_WHATSAPP_RESPONSE_STYLE = (
    "WhatsApp response style: write like a message sent in WhatsApp, not a long email or product brochure. "
    "Keep replies concise, warm, and conversational — respond to what was actually asked, then stop. "
    "Only share additional product details (dosage, pack, link, etc.) if the customer specifically asks. "
    "Use short paragraphs or simple numbered/bulleted lines when listing options. "
    "Use at most one relevant emoji based on the user's situation and emotion: greeting, thanks, "
    "sleepy/tired, delivery/order, payment, refund/return, stamina, reassurance, happiness, worry, "
    "urgency, stock, skin/hair care, digestion/acidity, fever/cold/cough, heart/BP, diabetes, "
    "women's health, or pain. If the user says they are hurt, in pain, or uses phrases like "
    "dard/chot/takleef, use a sympathetic emoji such as 😟 or 🩹 and respond gently. "
    "Do not decorate every line. Avoid tables, heavy Markdown, long disclaimers, "
    "and source-citation blocks unless the user asks. "
    "Match the language of the user's latest message when it is clear; for very short or ambiguous "
    "messages, continue in the last decisive language used in the conversation."
)

# Appended after the tenant system_prompt (or default). Stops the model from
# treating every turn as a lead for doctor consultations when RAG FAQs mention them.
_RAG_RESPONSE_PRIORITIES = (
    "Response priorities: "
    "(1) Answer ONLY what the customer specifically asked. Do not list every product field. "
    "If they ask about price, share the price. If they ask what a product is used for, explain that briefly. "
    "If they ask for a recommendation, introduce the most relevant product(s) in 1-2 sentences and why "
    "they match the need — then offer to share more details if the customer wants. "
    "Think of yourself as a knowledgeable friend answering a question, not a product brochure. "
    "(2) When a user asks about the type of medicine (e.g. 'Is this Ayurvedic?', 'Is it herbal?', "
    "'Is this allopathic?'), answer directly using the Category or description field in Context. "
    "Do not give a vague or unrelated response. "
    "(3) For product recommendations, suggest only products whose Used For, description, "
    "or benefits directly match the user's stated need. Do not recommend a product just "
    "because it appears in Context, shares a broad wellness word, or belongs to a different "
    "health concern. If the user's need is broad or ambiguous, ask a brief follow-up question "
    "(e.g. age, gender, main concern) before suggesting products. Never invent product links, "
    "prices, dosage, stock, or pack details; if a field is missing from the matching product "
    "section, omit it. "
    "(4) Mention doctor consultation or scheduling a callback only when the user asks to "
    "speak to a doctor, wants medical advice beyond what is in the catalog, or the "
    "Context clearly requires escalation. "
    "(5) Do not default routine product or pricing questions into booking a consultation."
)


def _compose_full_system(
    *,
    lang_note: str,
    base_prompt: str,
    max_system_chars: int,
) -> str:
    return _clip_text(
        (
            f"{lang_note}\n\n{base_prompt}\n\n{_WHATSAPP_RESPONSE_STYLE}\n\n"
            f"{_RAG_RESPONSE_PRIORITIES}\n\n{lang_note}"
        ),
        max_system_chars,
        _SYSTEM_TRUNC,
    )


# --------------------------------------------------------------------------- #
# Protocol (interface)
# --------------------------------------------------------------------------- #


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Minimal interface for a language-model text-generation backend."""

    async def generate_answer(
        self,
        context_chunks: List[str],
        user_query: str,
        system_prompt: Optional[str],
        output_language: str,
        conversation_history: Optional[str] = None,
    ) -> str:
        ...


# --------------------------------------------------------------------------- #
# Groq implementation (default)
# --------------------------------------------------------------------------- #


class GroqLLMClient:
    """
    Groq-backed chat completions.

    Uses env ``GROQ_API_KEY`` if ``api_key`` is empty.  Sync HTTP calls run
    in a worker thread so the event loop is not blocked.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-120b",
        *,
        temperature: float = 1.0,
        max_completion_tokens: int = 1024,
        top_p: float = 1.0,
        reasoning_effort: Optional[str] = None,
        use_stream: bool = False,
        max_context_chars: int = 12000,
        max_system_chars: int = 6000,
    ) -> None:
        from groq import Groq  # deferred import so tests can mock without groq

        key = api_key or None  # Groq() reads GROQ_API_KEY when api_key is None
        self._client = Groq(api_key=key) if key else Groq()
        self._model = model
        self._temperature = temperature
        self._max_completion_tokens = max_completion_tokens
        self._top_p = top_p
        self._reasoning_effort = (reasoning_effort or "").strip() or None
        self._use_stream = use_stream
        self._max_context_chars = max_context_chars
        self._max_system_chars = max_system_chars

    def _build_messages(
        self,
        context_chunks: List[str],
        user_query: str,
        system_prompt: Optional[str],
        output_language: str,
        conversation_history: Optional[str] = None,
    ) -> list[dict]:
        context_text = _join_and_truncate_chunks(
            context_chunks, self._max_context_chars
        )
        lang_note = _LANG_INSTRUCTIONS.get(
            output_language, _LANG_INSTRUCTIONS["english"]
        )
        lang_reminder = _LANG_REMINDER.get(
            output_language, _LANG_REMINDER["english"]
        )
        base_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        # Language rule goes FIRST so the LLM sees it before anything else,
        # then response priorities, then language again to reinforce.
        full_system = _compose_full_system(
            lang_note=lang_note,
            base_prompt=base_prompt,
            max_system_chars=self._max_system_chars,
        )
        hist = (conversation_history or "").strip()
        if hist:
            hist_block = _clip_text(
                f"Prior conversation (for context):\n{hist}",
                min(4000, self._max_context_chars // 2),
                _TRUNC_SUFFIX,
            )
            user_content = (
                f"{hist_block}\n\nContext:\n{context_text}\n\nQuestion: {user_query}\n\n{lang_reminder}"
            )
        else:
            user_content = f"Context:\n{context_text}\n\nQuestion: {user_query}\n\n{lang_reminder}"
        return [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_content},
        ]

    def _sync_generate(
        self,
        context_chunks: List[str],
        user_query: str,
        system_prompt: Optional[str],
        output_language: str,
        conversation_history: Optional[str] = None,
    ) -> str:
        messages = self._build_messages(
            context_chunks,
            user_query,
            system_prompt,
            output_language,
            conversation_history,
        )

        logger.debug(
            "Groq LLM request model=%s language=%s chunks=%d stream=%s",
            self._model,
            output_language,
            len(context_chunks),
            self._use_stream,
        )

        # Groq on-demand TPM per request is tight; cap completion even if .env sets higher.
        max_comp = max(256, min(self._max_completion_tokens, 1024))
        create_kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_completion_tokens": max_comp,
            "top_p": self._top_p,
            "stop": None,
        }
        if self._reasoning_effort:
            create_kwargs["reasoning_effort"] = self._reasoning_effort

        if self._use_stream:
            create_kwargs["stream"] = True
            try:
                completion = self._client.chat.completions.create(**create_kwargs)
            except TypeError:
                create_kwargs.pop("reasoning_effort", None)
                completion = self._client.chat.completions.create(**create_kwargs)
            except Exception as exc:
                if "reasoning_effort" in create_kwargs:
                    logger.warning(
                        "Groq stream retry without reasoning_effort: %s", exc
                    )
                    create_kwargs.pop("reasoning_effort", None)
                    completion = self._client.chat.completions.create(
                        **create_kwargs
                    )
                else:
                    raise
            parts: List[str] = []
            for chunk in completion:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                piece = getattr(delta, "content", None) or ""
                if piece:
                    parts.append(piece)
            return "".join(parts)

        create_kwargs["stream"] = False
        try:
            completion = self._client.chat.completions.create(**create_kwargs)
        except TypeError:
            create_kwargs.pop("reasoning_effort", None)
            completion = self._client.chat.completions.create(**create_kwargs)
        except Exception as exc:
            if "reasoning_effort" in create_kwargs:
                logger.warning(
                    "Groq retry without reasoning_effort: %s", exc
                )
                create_kwargs.pop("reasoning_effort", None)
                completion = self._client.chat.completions.create(**create_kwargs)
            else:
                raise

        if not completion.choices:
            return ""
        msg = completion.choices[0].message
        return (getattr(msg, "content", None) or "") if msg is not None else ""

    async def generate_answer(
        self,
        context_chunks: List[str],
        user_query: str,
        system_prompt: Optional[str] = None,
        output_language: str = "english",
        conversation_history: Optional[str] = None,
    ) -> str:
        return await asyncio.to_thread(
            self._sync_generate,
            context_chunks,
            user_query,
            system_prompt,
            output_language,
            conversation_history,
        )


# --------------------------------------------------------------------------- #
# OpenAI implementation
# --------------------------------------------------------------------------- #


class OpenAILLMClient:
    """Async OpenAI-backed LLM client (``LLM_PROVIDER=openai``)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
        temperature: float = 0.4,
        max_completion_tokens: int = 384,
        max_context_chars: int = 12000,
        max_system_chars: int = 6000,
    ) -> None:
        from openai import AsyncOpenAI  # deferred import

        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._temperature = temperature
        self._max_completion_tokens = max(128, min(int(max_completion_tokens), 1024))
        self._max_context_chars = max_context_chars
        self._max_system_chars = max_system_chars

    async def generate_answer(
        self,
        context_chunks: List[str],
        user_query: str,
        system_prompt: Optional[str] = None,
        output_language: str = "english",
        conversation_history: Optional[str] = None,
    ) -> str:
        context_text = _join_and_truncate_chunks(
            context_chunks, self._max_context_chars
        )
        lang_note = _LANG_INSTRUCTIONS.get(
            output_language, _LANG_INSTRUCTIONS["english"]
        )
        lang_reminder = _LANG_REMINDER.get(
            output_language, _LANG_REMINDER["english"]
        )
        base_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        full_system = _compose_full_system(
            lang_note=lang_note,
            base_prompt=base_prompt,
            max_system_chars=self._max_system_chars,
        )
        hist = (conversation_history or "").strip()
        if hist:
            hist_block = _clip_text(
                f"Prior conversation (for context):\n{hist}",
                min(4000, self._max_context_chars // 2),
                _TRUNC_SUFFIX,
            )
            user_content = (
                f"{hist_block}\n\nContext:\n{context_text}\n\nQuestion: {user_query}\n\n{lang_reminder}"
            )
        else:
            user_content = f"Context:\n{context_text}\n\nQuestion: {user_query}\n\n{lang_reminder}"

        logger.debug(
            "OpenAI LLM request model=%s language=%s chunks=%d",
            self._model,
            output_language,
            len(context_chunks),
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": user_content},
            ],
            temperature=self._temperature,
            max_tokens=self._max_completion_tokens,
        )
        return response.choices[0].message.content or ""


# --------------------------------------------------------------------------- #
# FastAPI dependency factory
# --------------------------------------------------------------------------- #

_llm_instance: Optional[Union[GroqLLMClient, OpenAILLMClient]] = None


def get_llm_client() -> LLMClientProtocol:
    """
    FastAPI dependency that returns a singleton LLM client.

    Set ``LLM_PROVIDER=groq`` (default) or ``openai``.  Override in tests::

        app.dependency_overrides[get_llm_client] = lambda: mock_llm
    """
    global _llm_instance
    if _llm_instance is None:
        from app.core.config import get_settings

        s = get_settings()
        provider = (s.llm_provider or "groq").strip().lower()

        if provider == "openai":
            _llm_instance = OpenAILLMClient(
                api_key=s.openai_api_key or "no-key-set",
                model=s.llm_model,
                timeout=s.llm_timeout_seconds,
                temperature=s.llm_temperature,
                max_completion_tokens=s.llm_max_completion_tokens,
                max_context_chars=s.llm_max_context_chars,
                max_system_chars=s.llm_max_system_chars,
            )
        else:
            _llm_instance = GroqLLMClient(
                api_key=s.groq_api_key or "",
                model=s.llm_model,
                temperature=s.llm_temperature,
                max_completion_tokens=s.llm_max_completion_tokens,
                top_p=s.llm_top_p,
                reasoning_effort=s.llm_reasoning_effort,
                use_stream=s.llm_stream,
                max_context_chars=s.llm_max_context_chars,
                max_system_chars=s.llm_max_system_chars,
            )

    return _llm_instance
