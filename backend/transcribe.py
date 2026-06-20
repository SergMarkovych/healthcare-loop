"""Speech-to-text for the encounter note, via OpenRouter's transcription API.

Audio recorded in the browser is forwarded to OpenRouter's
/api/v1/audio/transcriptions endpoint and transcribed there, then the text is
returned to the UI. It reuses the same OPENROUTER_API_KEY the extractor uses
(read from os.environ, identical to backend/llm_client.py) so if OpenRouter
extraction works, dictation works.

PRIVACY NOTE: unlike a local model, this sends audio off-device to OpenRouter.
That is consistent with running extraction through OpenRouter (the note already
leaves the device). The UI states this; do not claim on-device privacy here.

If no API key is present both endpoints degrade gracefully and the UI hides the
mic button.

Tunables (env):
    STT_MODEL   default 'openai/whisper-1'  (e.g. 'openai/gpt-4o-mini-transcribe')
"""

from __future__ import annotations

import base64
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

_OR_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
_STT_MODEL = os.environ.get("STT_MODEL", "openai/whisper-1")


def _api_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "")


def _format_from_content_type(ct: str) -> str:
    ct = (ct or "").lower()
    if "wav" in ct or "x-wav" in ct:
        return "wav"
    if "ogg" in ct or "opus" in ct:
        return "ogg"
    if "mpeg" in ct or "mp3" in ct:
        return "mp3"
    if "mp4" in ct or "m4a" in ct or "aac" in ct:
        return "m4a"
    if "flac" in ct:
        return "flac"
    return "webm"  # MediaRecorder default in Chromium


@router.get("/api/transcribe/health")
def transcribe_health() -> dict:
    return {"available": bool(_api_key()), "model": _STT_MODEL, "provider": "openrouter"}


@router.post("/api/transcribe")
async def transcribe(request: Request) -> JSONResponse:
    # Audio is sent as the raw request body — deliberately avoids multipart so
    # the app boots without the python-multipart dependency.
    key = _api_key()
    if not key:
        return JSONResponse(
            {"text": "", "available": False,
             "error": "OPENROUTER_API_KEY not set — dictation needs the OpenRouter key the extractor uses"},
            status_code=503,
        )
    data = await request.body()
    if not data:
        return JSONResponse({"text": "", "error": "empty audio"}, status_code=400)

    payload = {
        "model": _STT_MODEL,
        "input_audio": {
            "data": base64.b64encode(data).decode("ascii"),
            "format": _format_from_content_type(request.headers.get("content-type", "")),
        },
        "language": "en",
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/SergMarkovych/healthcare-loop",
        "X-Title": "COMPASS HealthCare",
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(_OR_URL, headers=headers, json=payload)
        if r.status_code != 200:
            return JSONResponse(
                {"text": "", "error": f"OpenRouter {r.status_code}: {r.text[:300]}"},
                status_code=502,
            )
        body = r.json()
        return JSONResponse(
            {"text": (body.get("text") or "").strip(), "mode": "openrouter-stt", "model": _STT_MODEL}
        )
    except Exception as e:
        return JSONResponse({"text": "", "error": str(e)}, status_code=500)
