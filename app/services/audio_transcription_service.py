"""Audio download and transcription helpers for WhatsApp inbound media."""
from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
import asyncio
from functools import lru_cache
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadedAudio:
    content: bytes
    filename: str
    content_type: str


_CONTENT_TYPE_EXT = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/ogg": "ogg",
    "audio/oga": "ogg",
    "audio/amr": "amr",
    "audio/aac": "aac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
}


def is_audio_content_type(content_type: str | None) -> bool:
    return (content_type or "").strip().lower().startswith("audio/")


def _filename(content_type: str | None, fallback: str = "whatsapp-audio") -> str:
    clean = (content_type or "").split(";", 1)[0].strip().lower()
    ext = _CONTENT_TYPE_EXT.get(clean, "ogg")
    return f"{fallback}.{ext}"


async def download_twilio_audio(
    *,
    media_url: str,
    content_type: str | None,
    account_sid: str,
    auth_token: str,
    timeout_seconds: int,
) -> DownloadedAudio:
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(media_url, auth=(account_sid, auth_token))
    response.raise_for_status()
    audio_bytes = response.content
    _validate_size(audio_bytes)
    resolved_type = response.headers.get("content-type") or content_type or "audio/ogg"
    return DownloadedAudio(
        content=audio_bytes,
        filename=_filename(resolved_type, "twilio-whatsapp-audio"),
        content_type=resolved_type,
    )


async def download_meta_audio(
    *,
    media_id: str,
    access_token: str,
    graph_base_url: str,
    graph_version: str,
    timeout_seconds: int,
    content_type: str | None = None,
) -> DownloadedAudio:
    base = graph_base_url.rstrip("/")
    version = graph_version.strip().lstrip("/")
    media_info_url = f"{base}/{version}/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        info_response = await client.get(media_info_url, headers=headers)
        info_response.raise_for_status()
        info = info_response.json()
        download_url = str(info.get("url") or "").strip()
        if not download_url:
            raise RuntimeError("Meta media metadata did not include a download URL.")
        media_response = await client.get(download_url, headers=headers)
        media_response.raise_for_status()
    audio_bytes = media_response.content
    _validate_size(audio_bytes)
    resolved_type = media_response.headers.get("content-type") or content_type or info.get("mime_type") or "audio/ogg"
    return DownloadedAudio(
        content=audio_bytes,
        filename=_filename(str(resolved_type), "meta-whatsapp-audio"),
        content_type=str(resolved_type),
    )


async def transcribe_audio(audio: DownloadedAudio, *, language: Optional[str] = None) -> str:
    errors: list[str] = []
    prepared = _prepare_openai_audio(audio)

    if settings.openai_api_key:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)
        for model in _transcription_models():
            file_obj = io.BytesIO(prepared.content)
            file_obj.name = prepared.filename
            kwargs = {
                "model": model,
                "file": file_obj,
            }
            if language:
                kwargs["language"] = language
            try:
                result = await client.audio.transcriptions.create(**kwargs)
                text = getattr(result, "text", None)
                if text is None and isinstance(result, dict):
                    text = result.get("text")
                transcript = str(text or "").strip()
                if not transcript:
                    raise RuntimeError("Audio transcription returned empty text.")
                logger.info(
                    "WhatsApp audio transcribed",
                    extra={
                        "provider": "openai",
                        "content_type": audio.content_type,
                        "prepared_content_type": prepared.content_type,
                        "bytes": len(audio.content),
                        "prepared_bytes": len(prepared.content),
                        "model": model,
                    },
                )
                return transcript
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                logger.warning(
                    "Audio transcription model failed",
                    extra={"provider": "openai", "model": model, "error": str(exc)},
                )
    else:
        errors.append("openai: OPENAI_API_KEY not configured")

    if settings.whatsapp_audio_local_fallback_enabled:
        try:
            return await asyncio.to_thread(_transcribe_audio_local, prepared, language)
        except Exception as exc:
            errors.append(f"local-faster-whisper: {exc}")
            logger.warning(
                "Local audio transcription failed",
                extra={"model": settings.whatsapp_audio_local_model, "error": str(exc)},
            )

    raise RuntimeError("All audio transcription models failed: " + " | ".join(errors))


@lru_cache(maxsize=4)
def _local_whisper_model(model_name: str, compute_type: str):
    from faster_whisper import WhisperModel

    return WhisperModel(
        model_name,
        device="cpu",
        compute_type=compute_type,
        download_root="/tmp/faster-whisper-models",
    )


def _transcribe_audio_local(audio: DownloadedAudio, language: Optional[str] = None) -> str:
    suffix = os.path.splitext(audio.filename or "")[1] or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as src:
        src.write(audio.content)
        src_path = src.name
    try:
        model_name = (settings.whatsapp_audio_local_model or "base").strip()
        compute_type = (settings.whatsapp_audio_local_compute_type or "int8").strip()
        model = _local_whisper_model(model_name, compute_type)
        segments, info = model.transcribe(
            src_path,
            language=language,
            beam_size=1,
            vad_filter=False,
        )
        transcript = " ".join(seg.text.strip() for seg in segments if seg.text and seg.text.strip()).strip()
        if not transcript:
            raise RuntimeError("Local audio transcription returned empty text.")
        logger.info(
            "WhatsApp audio transcribed",
            extra={
                "provider": "faster-whisper",
                "model": model_name,
                "compute_type": compute_type,
                "language": getattr(info, "language", None),
                "language_probability": getattr(info, "language_probability", None),
                "bytes": len(audio.content),
            },
        )
        return transcript
    finally:
        try:
            os.unlink(src_path)
        except FileNotFoundError:
            pass


def _validate_size(content: bytes) -> None:
    max_bytes = int(settings.whatsapp_audio_max_bytes or 0)
    if max_bytes > 0 and len(content) > max_bytes:
        raise RuntimeError(f"Audio file too large ({len(content)} bytes; max {max_bytes}).")


def _transcription_models() -> list[str]:
    configured = (settings.whatsapp_audio_transcription_model or "").strip()
    candidates = [
        configured,
        "gpt-4o-mini-transcribe",
        "gpt-4o-transcribe",
        "whisper-1",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for model in candidates:
        if not model:
            continue
        key = model.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(model)
    return out


def _prepare_openai_audio(audio: DownloadedAudio) -> DownloadedAudio:
    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    filename = (audio.filename or "").lower()
    supported_ext = (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")
    if filename.endswith(supported_ext) and content_type not in {"audio/ogg", "audio/amr"}:
        return audio
    try:
        converted = _convert_to_mp3(audio.content, audio.filename)
        _validate_size(converted)
        return DownloadedAudio(
            content=converted,
            filename="whatsapp-audio.mp3",
            content_type="audio/mpeg",
        )
    except Exception as exc:
        logger.warning(
            "Audio conversion failed; sending original audio to transcription",
            extra={"filename": audio.filename, "content_type": audio.content_type, "error": str(exc)},
        )
        return audio


def _convert_to_mp3(content: bytes, source_name: str) -> bytes:
    suffix = os.path.splitext(source_name or "")[1] or ".ogg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as src:
        src.write(content)
        src_path = src.name
    out_path = src_path + ".mp3"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                src_path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-ar",
                "16000",
                "-ac",
                "1",
                out_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        with open(out_path, "rb") as fh:
            return fh.read()
    finally:
        for path in (src_path, out_path):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
