"""AgentVid Multi-Language AI Audio Transcription & Voice-Synced Caption Engine.

Solves two core problems:
1. Local English-only ASR (Parakeet) cannot transcribe Hindi, Hinglish, Bengali, Urdu, Tamil, Arabic, etc.
   When an AI API key is configured (Gemini, Groq, OpenAI, OpenRouter), AgentVid sends lightweight audio
   chunks directly to the AI model to transcribe the exact spoken language with voice-synced timestamps.
2. Strict pause-aware cue grouping (`words_to_cues`) splits on silence gaps (>0.65s) and caps cue durations
   so captions ALWAYS change dynamically with the speaker's voice and NEVER freeze across the video.
"""
from __future__ import annotations

import base64
import json
import math
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx

from . import ai, auth, brain, ctx, media, roman, transcribe, usage

CAPTION_LANGUAGES: list[dict[str, str]] = [
    {"id": "auto", "label": "Auto-Detect Spoken Language", "iso": ""},
    {"id": "en", "label": "English", "iso": "en"},
    {"id": "hi-Latn", "label": "Hinglish (Hindi in English letters)", "iso": "hi"},
    {"id": "hi", "label": "Hindi (हिन्दी)", "iso": "hi"},
    {"id": "bn-Latn", "label": "Banglish (Bengali in English letters)", "iso": "bn"},
    {"id": "bn", "label": "Bengali (বাংলা)", "iso": "bn"},
    {"id": "ur", "label": "Urdu / Roman Urdu", "iso": "ur"},
    {"id": "ta", "label": "Tamil (தமிழ்)", "iso": "ta"},
    {"id": "te", "label": "Telugu (తెలుగు)", "iso": "te"},
    {"id": "mr", "label": "Marathi (मराठी)", "iso": "mr"},
    {"id": "gu", "label": "Gujarati (ગુજરાતી)", "iso": "gu"},
    {"id": "pa", "label": "Punjabi (ਪੰਜਾਬੀ)", "iso": "pa"},
    {"id": "es", "label": "Spanish (Español)", "iso": "es"},
    {"id": "fr", "label": "French (Français)", "iso": "fr"},
    {"id": "de", "label": "German (Deutsch)", "iso": "de"},
    {"id": "ar", "label": "Arabic (العربية)", "iso": "ar"},
    {"id": "pt", "label": "Portuguese (Português)", "iso": "pt"},
    {"id": "ja", "label": "Japanese (日本語)", "iso": "ja"},
    {"id": "ko", "label": "Korean (한국어)", "iso": "ko"},
    {"id": "en-translate", "label": "Auto-Translate Any Speech → English", "iso": ""},
]

LANG_BY_ID: dict[str, dict[str, str]] = {x["id"]: x for x in CAPTION_LANGUAGES}


def language_label(lang_id: str) -> str:
    return (LANG_BY_ID.get(lang_id or "auto") or LANG_BY_ID["auto"])["label"]


def _sanitize_word(w: dict[str, Any]) -> dict[str, Any] | None:
    txt = re.sub(r"[\x00-\x1f\x7f]+", " ", str(w.get("w") or "")).strip()
    if not txt:
        return None
    try:
        s = max(0.0, float(w.get("s", 0.0)))
        e = float(w.get("e", s + 0.25))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(s) and math.isfinite(e)):
        return None
    # Cap single-word duration so a stray word can never stretch across 20 seconds of silence
    e = max(s + 0.08, min(e, s + 1.15))
    return {"w": txt, "s": round(s, 3), "e": round(e, 3)}


def words_to_cues(
    words: list[dict[str, Any]],
    max_words: int = 4,
    max_gap: float = 0.65,
    max_dur: float = 2.6,
) -> list[dict[str, Any]]:
    """Group word timestamps into tight, dynamic, pause-aware caption cues (NEVER freezes across silence!)."""
    cleaned = [cw for w in (words or []) if (cw := _sanitize_word(w)) is not None]
    cleaned.sort(key=lambda x: x["s"])
    if not cleaned:
        return []

    cues: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []

    def _flush():
        if not cur:
            return
        cs = cur[0]["s"]
        ce = cur[-1]["e"]
        # Guarantee sane cue bounds (never > 3.6s even if timestamps are sparse)
        ce = round(max(cs + 0.25, min(ce, cs + 3.6)), 3)
        text = " ".join(x["w"] for x in cur).strip()
        if text:
            cues.append({
                "id": f"cap_{uuid.uuid4().hex[:6]}",
                "start": round(cs, 3),
                "end": ce,
                "text": text,
                "words": list(cur),
            })
        cur.clear()

    for w in cleaned:
        if cur:
            prev = cur[-1]
            gap = w["s"] - prev["e"]
            span = w["e"] - cur[0]["s"]
            if gap > max_gap or span > max_dur or len(cur) >= max_words:
                _flush()
        cur.append(w)
        if w["w"] and w["w"][-1] in ".?!।":
            _flush()
    _flush()

    # Prevent overlapping cues so rapid speech swaps cleanly without two lines colliding
    for i in range(len(cues) - 1):
        if cues[i]["end"] > cues[i + 1]["start"] - 0.02:
            cues[i]["end"] = round(max(cues[i]["start"] + 0.18, cues[i + 1]["start"] - 0.02), 3)

    return cues


def _cues_to_words(raw_cues: list[dict[str, Any]], offset_sec: float, seg_dur: float) -> list[dict[str, Any]]:
    """Convert AI-returned phrase cues [{start, end, text}] into smoothly timed word dicts."""
    words: list[dict[str, Any]] = []
    for c in raw_cues:
        if not isinstance(c, dict):
            continue
        txt = re.sub(r"[\x00-\x1f\x7f]+", " ", str(c.get("text") or "")).strip()
        if not txt:
            continue
        try:
            s = float(c.get("start", 0.0))
            e = float(c.get("end", s + 1.2))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(s) and math.isfinite(e)):
            continue
        s = max(0.0, min(seg_dur - 0.05, s))
        e = max(s + 0.2, min(seg_dur, e))
        # Clamp runaway AI cue end so a single phrase never freezes across silence
        if e - s > 4.2:
            e = min(seg_dur, s + 3.2)
        parts = txt.split()
        if not parts:
            continue
        step = (e - s) / len(parts)
        for i, tok in enumerate(parts):
            ws = offset_sec + s + i * step
            we = offset_sec + s + (i + 1) * step
            words.append({"w": tok, "s": round(ws, 3), "e": round(we, 3)})
    return words


def _extract_mp3_clip(video_path: Path, start: float, duration: float, out_mp3: Path) -> bool:
    """Extract a compact mono 16kHz MP3 clip for fast AI audio upload."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{max(0.0, start):.3f}",
        "-t", f"{max(0.5, duration):.3f}",
        "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
        str(out_mp3),
    ]
    try:
        media.run(cmd, timeout=120)
        return out_mp3.is_file() and out_mp3.stat().st_size > 256
    except Exception:
        return False


def _lang_instruction(language: str) -> str:
    lang = (language or "auto").strip()
    if lang == "en-translate":
        return "Translate everything spoken into natural, concise English captions."
    if lang == "hi-Latn":
        return (
            "The video may be in Hindi/Hinglish. Write ALL spoken Hindi/Urdu words in natural Roman/English letters "
            "(Hinglish, e.g. 'yaar ye dekho', 'kya baat hai') — NEVER use Devanagari or Urdu script."
        )
    if lang == "hi":
        return "Transcribe spoken Hindi accurately in Hindi Devanagari script (हिन्दी). Keep English words as spoken."
    if lang == "bn-Latn":
        return (
            "The video may be in Bengali/Banglish. Write spoken Bengali words in natural Roman/English letters "
            "(Banglish, e.g. 'ki obostha', 'darun lagche') — NEVER use Bengali script."
        )
    if lang == "bn":
        return "Transcribe spoken Bengali accurately in Bengali script (বাংলা)."
    if lang == "ur":
        return "Transcribe spoken Urdu accurately in Roman Urdu / English letters so captions render cleanly on screen."
    if lang == "auto" or lang not in LANG_BY_ID:
        return (
            "Auto-detect the spoken language accurately. If the speaker speaks Hindi, Urdu, or Bengali, write clear "
            "natural spoken words matching the audio (prefer Romanized Hinglish/Banglish if mixed with English, or "
            "the native spoken language accurately). Never guess random English words for non-English speech."
        )
    return f"Transcribe accurately in {LANG_BY_ID[lang]['label']}."


def _transcribe_chunk_gemini(mp3_path: Path, seg_dur: float, language: str) -> tuple[list[dict[str, Any]], str]:
    """Send a compact MP3 audio clip directly to Gemini for multi-language timestamped captions."""
    b64 = base64.b64encode(mp3_path.read_bytes()).decode("ascii")
    schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "start": {"type": "NUMBER"},
                "end": {"type": "NUMBER"},
                "text": {"type": "STRING"},
            },
            "required": ["start", "end", "text"],
        },
    }
    prompt = (
        f"Listen carefully to this {seg_dur:.1f}-second audio clip and generate exact, voice-synchronized video captions.\n"
        f"{_lang_instruction(language)}\n"
        "Strict rules:\n"
        "- Return a JSON array of objects: [{\"start\": seconds, \"end\": seconds, \"text\": \"2 to 5 spoken words\"}].\n"
        "- Every cue MUST closely match when those exact words are actually spoken (0.0 to "
        f"{seg_dur:.1f} seconds). Captions MUST change rapidly as the speaker talks (each cue 0.5s to 2.6s long, 2 to 5 words).\n"
        "- Do NOT output one static caption for the whole clip.\n"
        "- If a section is pure silence, background noise, or instrumental music with no vocals, omit it (do NOT hallucinate words).\n"
        "- If lyrics/singing or dialogue are clearly audible, transcribe them accurately at the exact seconds they occur.\n"
        "- Return [] if there are no audible voices or vocals."
    )
    body = {
        "contents": [{
            "parts": [
                {"inlineData": {"mimeType": "audio/mp3", "data": b64}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }

    last_err = None
    for model in ai.models():
        try:
            url = f"{ai.base_url()}/{model}:generateContent"
            r = httpx.post(url, headers={"x-goog-api-key": ai.key()}, json=body, timeout=180)
            if r.status_code != 200:
                ai._fail(r, model)
            data = r.json()
            cand = (data.get("candidates") or [{}])[0]
            raw_txt = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
            parsed = json.loads(raw_txt)
            if isinstance(parsed, list):
                meta = data.get("usageMetadata") or {}
                usage.record(meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0), "AI Audio Captions")
                ai.clear_problem()
                return parsed, model
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return [], ""


def _transcribe_chunk_whisper(mp3_path: Path, seg_dur: float, language: str) -> tuple[list[dict[str, Any]], str]:
    """Use OpenAI or Groq Whisper audio transcription API with word-level timestamps."""
    prov = ai.provider()
    base = ai.base_url().rstrip("/")
    api_key = ai.key()
    model = "whisper-large-v3-turbo" if prov == "groq" else "whisper-1"
    lang_info = LANG_BY_ID.get(language or "auto", LANG_BY_ID["auto"])
    iso_lang = lang_info.get("iso") or ""

    endpoint = f"{base}/audio/translations" if language == "en-translate" else f"{base}/audio/transcriptions"
    form_data: list[tuple[str, str]] = [
        ("model", model),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("timestamp_granularities[]", "segment"),
    ]
    if iso_lang and language != "en-translate":
        form_data.append(("language", iso_lang))

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    with mp3_path.open("rb") as fh:
        files = {"file": (mp3_path.name, fh, "audio/mpeg")}
        r = httpx.post(endpoint, headers=headers, data=form_data, files=files, timeout=180)
    if r.status_code != 200:
        ai._fail(r, model)

    data = r.json()
    words_raw = data.get("words") or []
    out_words: list[dict[str, Any]] = []
    if words_raw:
        for w in words_raw:
            tok = str(w.get("word") or w.get("w") or "").strip()
            if not tok:
                continue
            ws = max(0.0, float(w.get("start", 0.0)))
            we = max(ws + 0.08, float(w.get("end", ws + 0.25)))
            out_words.append({"w": tok, "s": round(ws, 3), "e": round(we, 3)})
    else:
        for seg in data.get("segments") or []:
            txt = str(seg.get("text") or "").strip()
            if not txt:
                continue
            ss = max(0.0, float(seg.get("start", 0.0)))
            se = max(ss + 0.25, float(seg.get("end", ss + 1.5)))
            parts = txt.split()
            step = (se - ss) / max(1, len(parts))
            for i, tok in enumerate(parts):
                out_words.append({"w": tok, "s": round(ss + i * step, 3), "e": round(ss + (i + 1) * step, 3)})

    # Romanize if user explicitly asked for Hinglish / Banglish / Roman Urdu
    if language in ("hi-Latn", "ur") and out_words:
        try:
            out_words = brain.fix_caption_words(out_words, lang="hi")
        except Exception:
            out_words = roman.words(out_words)
    elif language == "bn-Latn" and out_words:
        out_words = roman.words(out_words)

    return out_words, model


def _can_ai_transcribe_audio() -> bool:
    if not ai.ready():
        return False
    return ai.provider() in ("gemini", "openai", "groq")


def transcribe_video_ranges(
    video_path: Path,
    ranges: list[tuple[float, float]],
    language: str = "auto",
    allow_ai: bool = True,
    progress_cb: Callable[[float, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Transcribe specified (start, end) ranges using AI Audio (Gemini/Groq/OpenAI) or local Parakeet fallback."""
    if not ranges:
        return {"words": [], "cues": [], "source": "no_ranges", "language": language, "note": ""}

    # Normalize & merge overlapping ranges, then split long ranges into manageable chunks
    norm = sorted((max(0.0, float(a)), max(0.0, float(b))) for a, b in ranges if float(b) - float(a) >= 0.4)
    merged: list[list[float]] = []
    for a, b in norm:
        if merged and a <= merged[-1][1] + 1.0:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    use_ai = bool(allow_ai and _can_ai_transcribe_audio())
    prov = ai.provider() if use_ai else ""
    chunk_limit = 75.0 if prov == "gemini" else 300.0

    chunks: list[tuple[float, float]] = []
    for a, b in merged:
        cur = a
        while cur < b - 0.3:
            nxt = min(b, cur + chunk_limit)
            chunks.append((round(cur, 2), round(nxt, 2)))
            cur = nxt

    all_words: list[dict[str, Any]] = []
    model_used = ""
    ai_err = ""

    if use_ai:
        def _run_ai_chunks():
            nonlocal model_used, ai_err
            with tempfile.TemporaryDirectory(prefix="av_aicap_") as td:
                tdir = Path(td)
                for idx, (s0, s1) in enumerate(chunks):
                    if cancel_cb and cancel_cb():
                        raise InterruptedError("Cancelled by user.")
                    dur = max(0.5, s1 - s0)
                    if progress_cb:
                        progress_cb(
                            round(idx / max(1, len(chunks)), 3),
                            f"AI ({ai.label()}) transcribing {language_label(language)} ({idx + 1}/{len(chunks)})...",
                        )
                    mp3 = tdir / f"chunk_{idx:03d}.mp3"
                    if not _extract_mp3_clip(video_path, s0, dur, mp3):
                        continue
                    try:
                        if prov == "gemini":
                            raw_cues, mdl = _transcribe_chunk_gemini(mp3, dur, language)
                            model_used = mdl or model_used
                            all_words.extend(_cues_to_words(raw_cues, s0, dur))
                        else:
                            w_rel, mdl = _transcribe_chunk_whisper(mp3, dur, language)
                            model_used = mdl or model_used
                            for w in w_rel:
                                all_words.append({
                                    "w": w["w"],
                                    "s": round(s0 + w["s"], 3),
                                    "e": round(s0 + w["e"], 3),
                                })
                    except Exception as e:
                        ai_err = str(e)
                        break

        if ctx.uid_or_none() is None:
            with ctx.as_user(auth.local_user().id):
                _run_ai_chunks()
        else:
            _run_ai_chunks()

        if all_words:
            cues = words_to_cues(all_words)
            return {
                "words": all_words,
                "cues": cues,
                "source": f"ai_audio ({ai.label()} · {model_used})",
                "language": language,
                "note": f"Generated {len(cues)} voice-synced captions via {ai.label()} ({model_used}).",
            }
        if not ai_err:
            return {
                "words": [],
                "cues": [],
                "source": f"ai_audio_silent ({ai.label()})",
                "language": language,
                "note": f"AI ({ai.label()}) listened to the audio and detected no clear speech in these segments.",
            }

    # Fallback: Local offline speech model (English-focused Parakeet 0.6B)
    non_en = language not in ("auto", "en", "")
    if transcribe.model_ready():
        with tempfile.TemporaryDirectory(prefix="av_loccap_") as td:
            tdir = Path(td)
            for idx, (s0, s1) in enumerate(chunks):
                if cancel_cb and cancel_cb():
                    raise InterruptedError("Cancelled by user.")
                dur = max(0.5, s1 - s0)
                if progress_cb:
                    progress_cb(
                        round(idx / max(1, len(chunks)), 3),
                        f"Running local offline speech model ({idx + 1}/{len(chunks)})...",
                    )
                wav = tdir / f"seg_{idx:03d}.wav"
                try:
                    media.run([
                        "ffmpeg", "-y", "-v", "error",
                        "-ss", f"{s0:.3f}", "-t", f"{dur:.3f}",
                        "-i", str(video_path),
                        "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(wav),
                    ], timeout=120)
                    if wav.is_file():
                        audio_i16 = media.load_audio(wav)
                        w_rel = transcribe.transcribe(audio_i16)
                        for w in w_rel:
                            all_words.append({
                                "w": w["w"],
                                "s": round(s0 + w["s"], 3),
                                "e": round(s0 + w["e"], 3),
                            })
                except Exception:
                    continue

        cues = words_to_cues(all_words)
        note = f"Generated {len(cues)} captions using local offline speech model."
        if non_en:
            note += (
                f" Note: Local offline model is English-only; configure a Gemini, Groq, or OpenAI API key in Settings "
                f"for accurate {language_label(language)} speech recognition."
            )
        elif ai_err:
            note += f" (AI audio fallback: {ai_err[:120]})"
        return {
            "words": all_words,
            "cues": cues,
            "source": "offline_speech_model",
            "language": language,
            "note": note,
        }

    note = (
        f"Could not transcribe audio ({ai_err}). Configure a Gemini, Groq, or OpenAI API key in Settings for "
        f"multi-language AI captions ({language_label(language)}), or download the local offline speech package for English."
        if ai_err
        else f"Add a Gemini, Groq, or OpenAI API key in Settings for accurate {language_label(language)} AI captions, "
             f"or download the Offline Speech Package for English local videos."
    )
    return {
        "words": [],
        "cues": [],
        "source": "unavailable",
        "language": language,
        "note": note,
    }


def translate_or_adapt_words(words: list[dict[str, Any]], language: str, title: str = "") -> list[dict[str, Any]]:
    """Adapt existing captions (e.g. from YouTube) into Hinglish/Banglish/English when requested and AI is ready."""
    if not words or language in ("auto", ""):
        return words
    if language == "en-translate" and ai.ready():
        try:
            if ctx.uid_or_none() is None:
                with ctx.as_user(auth.local_user().id):
                    return brain.translate_caption_words(words, lang="auto", title=title)
            return brain.translate_caption_words(words, lang="auto", title=title)
        except Exception:
            return words
    if language in ("hi-Latn", "ur"):
        if ai.ready():
            try:
                if ctx.uid_or_none() is None:
                    with ctx.as_user(auth.local_user().id):
                        return brain.fix_caption_words(words, title=title, lang="hi")
                return brain.fix_caption_words(words, title=title, lang="hi")
            except Exception:
                return roman.words(words)
        return roman.words(words)
    if language == "bn-Latn":
        return roman.words(words)
    return words
