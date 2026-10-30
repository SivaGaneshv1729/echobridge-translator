"""EchoBridge Web Server — FastAPI backend for web-based Language Coach & Translation.

Exposes REST API endpoints for:
  - Language coaching with Groq/Gemini LLM pools
  - Text translation (Argos Translate)
  - Session management & conversation history
  - Health checks and key pool status

Usage:
  pip install fastapi uvicorn
  python web_server.py
"""
import os
import sys
import json
import time
import uuid
import logging
from typing import Optional, Dict, Any, List
from dataclasses import asdict

# Ensure project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from engines.language_coach import LanguageCoachEngine, COACH_SCENARIOS, CoachingResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger("EchoBridge.Web")

# ─── App Configuration ────────────────────────────────────────────
app = FastAPI(
    title="EchoBridge API",
    description="Real-Time AI Language Coach & Translation API",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the web frontend
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ─── Session Store ────────────────────────────────────────────────
# Lightweight in-memory session store (per-session coach instances)
sessions: Dict[str, Dict[str, Any]] = {}
MAX_SESSIONS = 100
SESSION_TIMEOUT_S = 3600  # 1 hour


def _get_or_create_session(session_id: Optional[str] = None) -> tuple:
    """Get existing session or create a new one. Returns (session_id, session_dict)."""
    _cleanup_stale_sessions()

    if session_id and session_id in sessions:
        sessions[session_id]["last_active"] = time.time()
        return session_id, sessions[session_id]

    # Create new session
    new_id = session_id or str(uuid.uuid4())[:12]
    coach = LanguageCoachEngine(
        api_keys_file="config/api_keys.json",
        fallback_to_offline=True
    )
    sessions[new_id] = {
        "coach": coach,
        "created": time.time(),
        "last_active": time.time(),
        "history": [],
        "settings": {
            "practice_lang": "ja",
            "scenario": "free_talk",
            "provider": coach.provider
        }
    }
    logger.info(f"Created new session: {new_id} (provider: {coach.provider})")
    return new_id, sessions[new_id]


def _cleanup_stale_sessions():
    """Remove sessions older than timeout."""
    now = time.time()
    stale = [sid for sid, s in sessions.items() if now - s["last_active"] > SESSION_TIMEOUT_S]
    for sid in stale:
        del sessions[sid]
        logger.info(f"Cleaned up stale session: {sid}")


# ─── Request/Response Models ─────────────────────────────────────
class CoachRequest(BaseModel):
    text: str
    practice_lang: str = "ja"
    session_id: Optional[str] = None
    scenario: Optional[str] = None

class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "ja"

class ScenarioRequest(BaseModel):
    scenario: str
    session_id: Optional[str] = None

class SessionSettingsRequest(BaseModel):
    session_id: Optional[str] = None
    provider: Optional[str] = None
    practice_lang: Optional[str] = None


# ─── API Endpoints ────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve the web frontend."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "EchoBridge API is running. Web frontend not found."}


@app.get("/api/health")
async def health_check():
    """Health check and system status."""
    _, session = _get_or_create_session("__health__")
    coach = session["coach"]
    pool_status = coach.get_key_pool_status()
    return {
        "status": "healthy",
        "version": "2.0.0",
        "active_sessions": len(sessions) - 1,  # Exclude health check session
        "llm_pool": pool_status,
        "timestamp": time.time()
    }


@app.get("/api/scenarios")
async def get_scenarios():
    """List all available coaching scenarios."""
    scenarios = []
    for sid, info in COACH_SCENARIOS.items():
        scenarios.append({
            "id": sid,
            "title": info["title"],
            "description": info["description"],
            "icon": info["icon"]
        })
    return {"scenarios": scenarios}


@app.post("/api/coach")
async def coach_evaluate(req: CoachRequest):
    """Evaluate user speech and get coaching feedback + conversational reply."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    session_id, session = _get_or_create_session(req.session_id)
    coach: LanguageCoachEngine = session["coach"]

    # Apply scenario if requested
    if req.scenario:
        coach.set_scenario(req.scenario)
        session["settings"]["scenario"] = req.scenario

    import unicodedata
    clean_text = unicodedata.normalize("NFKC", req.text.strip())

    # Run the coach evaluation
    result: CoachingResult = coach.evaluate_and_reply(clean_text, req.practice_lang)

    # Build response
    turn = {
        "user_text": result.user_text,
        "practice_lang": result.practice_lang,
        "reply_text": result.reply_text,
        "reply_lang": result.reply_lang,
        "suggested_correction": result.suggested_correction,
        "is_natural": result.is_natural,
        "politeness_level": result.politeness_level,
        "grammar_notes": result.grammar_notes,
        "vocabulary_tips": result.vocabulary_tips,
        "scenario_id": result.scenario_id,
        "timestamp": time.time()
    }
    session["history"].append(turn)

    return {
        "session_id": session_id,
        "result": turn,
        "provider": coach.provider,
        "turn_count": len(session["history"])
    }


@app.post("/api/translate")
async def translate_text(req: TranslateRequest):
    """Translate text between languages using the LLM pool."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Use a dedicated session for translation
    _, session = _get_or_create_session("__translate__")
    coach: LanguageCoachEngine = session["coach"]

    import unicodedata
    clean_text = unicodedata.normalize("NFKC", req.text.strip())

    # Build translation prompt
    lang_names = {"en": "English", "ja": "Japanese", "zh": "Chinese", "ko": "Korean",
                  "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
                  "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada"}
    src_name = lang_names.get(req.source_lang, req.source_lang)
    tgt_name = lang_names.get(req.target_lang, req.target_lang)

    # Use the coach's LLM pool to do translation
    import urllib.request
    import urllib.error

    translation_prompt = (
        f"Translate the following text from {src_name} to {tgt_name}. "
        f"Return ONLY the translated text, nothing else.\n\n"
        f"Text: {clean_text}"
    )

    translated = None

    # Try Groq (using high-speed, general-purpose translation model)
    GROQ_TRANSLATE_MODEL = "llama-3.1-8b-instant"
    if coach.groq_keys:
        try:
            payload = {
                "model": GROQ_TRANSLATE_MODEL,
                "messages": [
                    {"role": "system", "content": f"You are a professional translator. Translate from {src_name} to {tgt_name}. Return ONLY the translation."},
                    {"role": "user", "content": clean_text}
                ],
                "temperature": 0.1
            }
            for i in range(len(coach.groq_keys)):
                key = coach.groq_keys[(coach.groq_key_index + i) % len(coach.groq_keys)]
                try:
                    api_req = urllib.request.Request(
                        "https://api.groq.com/openai/v1/chat/completions",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "User-Agent": "EchoBridge/2.0"
                        }
                    )
                    with urllib.request.urlopen(api_req, timeout=10.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        translated = data["choices"][0]["message"]["content"].strip()
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Groq translation failed: {e}")

    # Fallback to Gemini
    if not translated and coach.gemini_keys:
        try:
            payload = {
                "contents": [{"role": "user", "parts": [{"text": translation_prompt}]}]
            }
            for i in range(len(coach.gemini_keys)):
                key = coach.gemini_keys[(coach.gemini_key_index + i) % len(coach.gemini_keys)]
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{coach.gemini_model}:generateContent?key={key}"
                try:
                    api_req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(api_req, timeout=12.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        translated = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Gemini translation failed: {e}")

    # Final Fallback to local offline translation engine for EN <-> JA
    if not translated and {req.source_lang, req.target_lang} <= {"en", "ja"}:
        try:
            from engines.translation import TranslatorEngine
            models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models_cache", "translation")
            if os.path.exists(models_dir):
                local_translator = TranslatorEngine(models_dir)
                translated, _ = local_translator.translate(clean_text, from_code=req.source_lang, to_code=req.target_lang)
        except Exception as e:
            logger.warning(f"Offline local translate error: {e}")

    if not translated:
        raise HTTPException(status_code=503, detail="Translation service temporarily unavailable")

    return {
        "original": clean_text,
        "translated": translated,
        "source_lang": req.source_lang,
        "target_lang": req.target_lang
    }


@app.post("/api/scenario")
async def set_scenario(req: ScenarioRequest):
    """Switch the active coaching scenario."""
    session_id, session = _get_or_create_session(req.session_id)
    coach: LanguageCoachEngine = session["coach"]

    if not coach.set_scenario(req.scenario):
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

    session["settings"]["scenario"] = req.scenario
    return {
        "session_id": session_id,
        "scenario": req.scenario,
        "title": COACH_SCENARIOS[req.scenario]["title"]
    }


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "history": sessions[session_id]["history"],
        "settings": sessions[session_id]["settings"]
    }


@app.post("/api/session/clear")
async def clear_session(req: ScenarioRequest):
    """Clear conversation history for a session."""
    session_id = req.session_id or req.scenario  # Reusing model
    if session_id and session_id in sessions:
        sessions[session_id]["coach"].clear_history()
        sessions[session_id]["history"] = []
        return {"session_id": session_id, "status": "cleared"}
    raise HTTPException(status_code=404, detail="Session not found")


@app.post("/api/session/settings")
async def update_session_settings(req: SessionSettingsRequest):
    """Update session settings (provider, practice language)."""
    session_id, session = _get_or_create_session(req.session_id)
    coach: LanguageCoachEngine = session["coach"]

    if req.provider and req.provider in ("groq", "gemini", "builtin"):
        coach.provider = req.provider
        session["settings"]["provider"] = req.provider

    if req.practice_lang and req.practice_lang in ("ja", "en"):
        session["settings"]["practice_lang"] = req.practice_lang

    return {
        "session_id": session_id,
        "settings": session["settings"],
        "pool_status": coach.get_key_pool_status()
    }


# ─── Startup & Main ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting EchoBridge Web Server on port {port}...")
    uvicorn.run(
        "web_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
