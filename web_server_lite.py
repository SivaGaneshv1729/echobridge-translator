"""EchoBridge Lightweight Web Server — Zero-dependency HTTP server using Python stdlib only.

Serves the web frontend and exposes the Language Coach & Translation REST API
without requiring FastAPI or uvicorn.

Usage:
  python web_server_lite.py [port]
  python web_server_lite.py 8000
"""
import os
import sys
import json
import time
import uuid
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any, List

# Ensure project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engines.language_coach import LanguageCoachEngine, COACH_SCENARIOS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("EchoBridge.WebLite")

# ─── Session Store ────────────────────────────────────────────────
sessions: Dict[str, Dict[str, Any]] = {}
_session_lock = threading.Lock()
SESSION_TIMEOUT_S = 3600

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
API_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "api_keys.json")


def _cleanup_stale_sessions():
    now = time.time()
    with _session_lock:
        stale = [sid for sid, s in sessions.items() if now - s["last_active"] > SESSION_TIMEOUT_S]
        for sid in stale:
            del sessions[sid]
            logger.info(f"Cleaned up stale session: {sid}")


def get_or_create_session(session_id: Optional[str] = None):
    _cleanup_stale_sessions()
    with _session_lock:
        if session_id and session_id in sessions:
            sessions[session_id]["last_active"] = time.time()
            return session_id, sessions[session_id]
        new_id = session_id or str(uuid.uuid4())[:12]
        coach = LanguageCoachEngine(
            api_keys_file=API_KEYS_FILE,
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
        logger.info(f"New session: {new_id} (provider: {coach.provider})")
        return new_id, sessions[new_id]


# ─── HTTP Handler ─────────────────────────────────────────────────
class EchoBridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info(f"{self.address_string()} - {fmt % args}")

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400):
        self._send_json({"detail": message, "error": True}, status)

    def _send_file(self, path: str, mime: str):
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def _read_body(self) -> Optional[dict]:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("", "/", "/index.html"):
            index_path = os.path.join(STATIC_DIR, "index.html")
            self._send_file(index_path, "text/html; charset=utf-8")
            return

        if path == "/api/health":
            _, session = get_or_create_session("__health__")
            pool = session["coach"].get_key_pool_status()
            self._send_json({
                "status": "healthy",
                "version": "2.0.0",
                "active_sessions": max(0, len(sessions) - 1),
                "llm_pool": pool,
                "timestamp": time.time()
            })
            return

        if path == "/api/scenarios":
            scenarios = []
            for sid, info in COACH_SCENARIOS.items():
                scenarios.append({
                    "id": sid,
                    "title": info["title"],
                    "description": info["description"],
                    "icon": info["icon"]
                })
            self._send_json({"scenarios": scenarios})
            return

        if path.startswith("/api/history/"):
            sid = path.split("/api/history/")[-1]
            with _session_lock:
                if sid not in sessions:
                    self._send_error_json("Session not found", 404)
                    return
                self._send_json({
                    "session_id": sid,
                    "history": sessions[sid]["history"],
                    "settings": sessions[sid]["settings"]
                })
            return

        # Static files
        if path.startswith("/static/"):
            file_path = os.path.join(STATIC_DIR, path[len("/static/"):])
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".svg": "image/svg+xml",
            }
            self._send_file(file_path, mime_map.get(ext, "application/octet-stream"))
            return

        self._send_error_json("Not found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            body = self._read_body()
        except json.JSONDecodeError:
            self._send_error_json("Invalid JSON body")
            return

        if path == "/api/coach":
            self._handle_coach(body)
        elif path == "/api/translate":
            self._handle_translate(body)
        elif path == "/api/scenario":
            self._handle_set_scenario(body)
        elif path == "/api/session/clear":
            self._handle_clear_session(body)
        elif path == "/api/session/settings":
            self._handle_session_settings(body)
        else:
            self._send_error_json("Not found", 404)

    def _handle_coach(self, body: dict):
        import unicodedata
        text = (body.get("text") or "").strip()
        if not text:
            self._send_error_json("Text cannot be empty")
            return
        text = unicodedata.normalize("NFKC", text)

        session_id = body.get("session_id")
        practice_lang = body.get("practice_lang", "ja")
        scenario = body.get("scenario")

        session_id, session = get_or_create_session(session_id)
        coach: LanguageCoachEngine = session["coach"]

        if scenario:
            coach.set_scenario(scenario)
            session["settings"]["scenario"] = scenario

        result = coach.evaluate_and_reply(text, practice_lang)

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

        self._send_json({
            "session_id": session_id,
            "result": turn,
            "provider": coach.provider,
            "turn_count": len(session["history"])
        })

    def _handle_translate(self, body: dict):
        import urllib.request
        import urllib.error
        import unicodedata

        text = (body.get("text") or "").strip()
        if not text:
            self._send_error_json("Text cannot be empty")
            return
        text = unicodedata.normalize("NFKC", text)

        source_lang = body.get("source_lang", "en")
        target_lang = body.get("target_lang", "ja")

        lang_names = {
            "en": "English", "ja": "Japanese", "zh": "Chinese", "ko": "Korean",
            "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
            "hi": "Hindi", "te": "Telugu", "ta": "Tamil"
        }
        src_name = lang_names.get(source_lang, source_lang)
        tgt_name = lang_names.get(target_lang, target_lang)

        _, session = get_or_create_session("__translate__")
        coach: LanguageCoachEngine = session["coach"]

        translated = None

        # Try Groq — use a fast, generally available model for translation
        GROQ_TRANSLATE_MODEL = "llama-3.1-8b-instant"
        if coach.groq_keys:
            payload = json.dumps({
                "model": GROQ_TRANSLATE_MODEL,
                "messages": [
                    {"role": "system", "content": f"You are a professional translator. Translate from {src_name} to {tgt_name}. Return ONLY the translated text, nothing else."},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.1
            }).encode("utf-8")
            for i in range(len(coach.groq_keys)):
                key = coach.groq_keys[(coach.groq_key_index + i) % len(coach.groq_keys)]
                try:
                    req = urllib.request.Request(
                        "https://api.groq.com/openai/v1/chat/completions",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "User-Agent": "EchoBridge/2.0"
                        }
                    )
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        translated = data["choices"][0]["message"]["content"].strip()
                        break
                except Exception as e:
                    logger.warning(f"Groq translate error: {e}")

        # Fallback to Gemini
        if not translated and coach.gemini_keys:
            prompt = f"Translate from {src_name} to {tgt_name}. Return ONLY the translation.\n\nText: {text}"
            payload = json.dumps({
                "contents": [{"role": "user", "parts": [{"text": prompt}]}]
            }).encode("utf-8")
            for i in range(len(coach.gemini_keys)):
                key = coach.gemini_keys[(coach.gemini_key_index + i) % len(coach.gemini_keys)]
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{coach.gemini_model}:generateContent?key={key}"
                try:
                    req = urllib.request.Request(
                        url, data=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=12.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        translated = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        break
                except Exception as e:
                    logger.warning(f"Gemini translate error: {e}")

        # Final Fallback to local offline translation engine if available for EN <-> JA
        if not translated and {source_lang, target_lang} <= {"en", "ja"}:
            try:
                from engines.translation import TranslatorEngine
                models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models_cache", "translation")
                if os.path.exists(models_dir):
                    local_translator = TranslatorEngine(models_dir)
                    translated, _ = local_translator.translate(text, from_code=source_lang, to_code=target_lang)
            except Exception as e:
                logger.warning(f"Offline local translate error: {e}")

        if not translated:
            self._send_error_json("Translation service temporarily unavailable", 503)
            return

        self._send_json({
            "original": text,
            "translated": translated,
            "source_lang": source_lang,
            "target_lang": target_lang
        })

    def _handle_set_scenario(self, body: dict):
        session_id = body.get("session_id")
        scenario = body.get("scenario", "")
        session_id, session = get_or_create_session(session_id)
        coach: LanguageCoachEngine = session["coach"]

        if not coach.set_scenario(scenario):
            self._send_error_json(f"Unknown scenario: {scenario}")
            return

        session["settings"]["scenario"] = scenario
        self._send_json({
            "session_id": session_id,
            "scenario": scenario,
            "title": COACH_SCENARIOS[scenario]["title"]
        })

    def _handle_clear_session(self, body: dict):
        sid = body.get("session_id") or body.get("scenario")
        with _session_lock:
            if sid in sessions:
                sessions[sid]["coach"].clear_history()
                sessions[sid]["history"] = []
                self._send_json({"session_id": sid, "status": "cleared"})
            else:
                self._send_error_json("Session not found", 404)

    def _handle_session_settings(self, body: dict):
        session_id = body.get("session_id")
        session_id, session = get_or_create_session(session_id)
        coach: LanguageCoachEngine = session["coach"]

        provider = body.get("provider")
        if provider and provider in ("groq", "gemini", "builtin"):
            coach.provider = provider
            session["settings"]["provider"] = provider

        practice_lang = body.get("practice_lang")
        if practice_lang and practice_lang in ("ja", "en"):
            session["settings"]["practice_lang"] = practice_lang

        self._send_json({
            "session_id": session_id,
            "settings": session["settings"],
            "pool_status": coach.get_key_pool_status()
        })


# ─── Main Entrypoint ──────────────────────────────────────────────
def run(port: int = 8000):
    server = HTTPServer(("0.0.0.0", port), EchoBridgeHandler)
    logger.info(f"╔══════════════════════════════════════════════╗")
    logger.info(f"║  EchoBridge Web Server started               ║")
    logger.info(f"║  Local:   http://localhost:{port}                ║")
    logger.info(f"║  Network: http://0.0.0.0:{port}                  ║")
    logger.info(f"╚══════════════════════════════════════════════╝")
    logger.info("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped.")
        server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))
    run(port)
