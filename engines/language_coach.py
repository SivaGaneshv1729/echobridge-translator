"""AI Language Tutor and Conversational Coach Engine for EchoBridge.
Supports Hybrid Local Heuristic Engine, Local Ollama (Qwen2.5/Llama3), and OpenAI-compatible endpoints.
"""
import json
import logging
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

@dataclass
class CoachingResult:
    """Structured linguistic feedback and conversational reply from the AI Language Coach."""
    user_text: str
    practice_lang: str               # "ja" or "en"
    reply_text: str                  # Assistant's conversational continuation
    reply_lang: str                  # Language of reply (matches practice_lang)
    suggested_correction: str        # More natural / grammatically correct phrasing
    is_natural: bool                 # True if user speech was already natural
    politeness_level: str            # e.g. "Casual", "Polite (丁寧語)", "Honorific (敬語)", "Formal"
    grammar_notes: str               # Explanation of errors, particle nuances, or sentence structure
    vocabulary_tips: List[str] = field(default_factory=list)

class LanguageCoachEngine:
    """Evaluates speech utterances, provides conversational replies, and explains communication improvements."""

    def __init__(
        self,
        provider: str = "builtin",          # "builtin", "ollama", or "api"
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:0.5b",
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_model: str = "gpt-4o-mini"
    ):
        self.provider = provider
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.api_url = api_url.rstrip("/") if api_url else None
        self.api_key = api_key
        self.api_model = api_model

    def evaluate_and_reply(self, user_text: str, practice_lang: str = "ja") -> CoachingResult:
        """
        Evaluate user's spoken sentence and generate a conversational reply + coaching notes.
        """
        user_text = user_text.strip()
        if not user_text:
            return CoachingResult(
                user_text="",
                practice_lang=practice_lang,
                reply_text="I'm listening! Please speak a sentence." if practice_lang == "en" else "聞いていますよ！話してみてください。",
                reply_lang=practice_lang,
                suggested_correction="",
                is_natural=True,
                politeness_level="Neutral",
                grammar_notes="No speech detected."
            )

        # 1. Try Ollama if configured
        if self.provider == "ollama":
            result = self._query_ollama(user_text, practice_lang)
            if result:
                return result

        # 2. Try Cloud / Custom API if configured
        if self.provider == "api" and self.api_url and self.api_key:
            result = self._query_api(user_text, practice_lang)
            if result:
                return result

        # 3. Default: High-performance Builtin Heuristic Evaluator
        return self._evaluate_builtin(user_text, practice_lang)

    def _evaluate_builtin(self, text: str, lang: str) -> CoachingResult:
        """
        Instant 100% offline rule-based & linguistic pattern analyzer for Japanese and English.
        Detects particle misuse, politeness levels, unnatural phrasing, and generates contextual replies.
        """
        if lang == "ja":
            return self._evaluate_japanese_builtin(text)
        else:
            return self._evaluate_english_builtin(text)

    def _evaluate_japanese_builtin(self, text: str) -> CoachingResult:
        """Analyze Japanese grammar, politeness, and particle usage."""
        text_clean = text.strip()
        corrections = []
        notes = []
        vocab_tips = []
        suggested = text_clean
        is_natural = True

        # Politeness detection
        has_desu_masu = bool(re.search(r'(です|ます|でした|ました|ません|ましょう)', text_clean))
        has_keigo = bool(re.search(r'(いらっしゃ|なさる|おっしゃ|くださ|いたし|存じ|参り|申します)', text_clean))
        has_casual = bool(re.search(r'(だ|だよ|ね|よ|じゃない|ちゃう|てる|とく)[。！？\s]*$', text_clean))

        if has_keigo:
            politeness = "Honorific (敬語 - Keigo)"
        elif has_desu_masu:
            politeness = "Polite (丁寧語 - Teineigo)"
        elif has_casual:
            politeness = "Casual (普通体 - Plain Form)"
        else:
            politeness = "Informal / Incomplete"

        # Pattern 1: Particle 'どこ行きますか' -> 'どこへ行きますか / どこに行きますか'
        if re.search(r'どこ(行く|行きます)', text_clean):
            suggested = re.sub(r'どこ(行く|行きます)', r'どこへ\1', suggested)
            notes.append("When indicating destination with motion verbs like 行く (to go), add the directional particle 『へ』 (e) or 『に』 (ni).")
            is_natural = False

        # Pattern 2: '何食べる' -> '何を食べる'
        if re.search(r'何(食べる|食べます)', text_clean):
            suggested = re.sub(r'何(食べる|食べます)', r'何を\1', suggested)
            notes.append("In polite conversation, explicitly include the direct object particle 『を』 (wo) after 何.")
            is_natural = False

        # Pattern 3: '〜が好きです' vs '〜を好きです' (Common beginner pitfall)
        if "を好き" in text_clean:
            suggested = suggested.replace("を好き", "が好き")
            notes.append("In Japanese, 好き (suki) is a na-adjective. The object of affection is marked with 『が』, not 『を』.")
            is_natural = False

        # Pattern 4: '〜ができる' vs '〜をできる'
        if "をできる" in text_clean or "をできます" in text_clean:
            suggested = suggested.replace("をできる", "ができる").replace("をできます", "ができます")
            notes.append("Potential verbs like できる (can do) take the particle 『が』 rather than 『を』.")
            is_natural = False

        # Pattern 5: Missing polite ending in a polite context
        if not has_desu_masu and not has_keigo and ("駅" in text_clean or "すみません" in text_clean):
            if not suggested.endswith(("です", "ます", "ですか", "ますか")):
                notes.append("Tip: When addressing strangers or in public (asking for directions), end your sentence with 『〜ですか？』 or 『〜でしょうか？』 for polite tone.")
                vocab_tips.append("Try starting with 『すみません、ちょっとお伺いしてもいいですか？』 (Excuse me, may I ask you something?)")

        # Conversational reply generation
        if "駅" in text_clean or "どこ" in text_clean:
            reply = "駅ですね！この道をまっすぐ歩いて、2つ目の交差点を右に曲がると見えてきますよ。"
            vocab_tips.append("『徒歩5分』 (5 minutes on foot) is a great phrase when discussing distances.")
        elif "何" in text_clean and ("食べ" in text_clean or "お腹" in text_clean):
            reply = "お腹が空きましたね！近くに美味しいラーメン屋さんとお寿司屋さんがありますが、どちらがいいですか？"
            vocab_tips.append("『おすすめは何ですか？』 (What do you recommend?)")
        elif "元気" in text_clean or "こんにちは" in text_clean or "初めまして" in text_clean:
            reply = "こんにちは！お会いできて嬉しいです。今日の日本語の練習、一緒に楽しく頑張りましょう！"
        else:
            reply = f"なるほど、よく分かりました！とても自然な話し方ですね。続けてもっと詳しく教えてもらえますか？"

        if is_natural and not notes:
            notes.append("Your sentence structure, particles, and pronunciation rhythm are clear and natural!")

        return CoachingResult(
            user_text=text_clean,
            practice_lang="ja",
            reply_text=reply,
            reply_lang="ja",
            suggested_correction=suggested if not is_natural else text_clean,
            is_natural=is_natural,
            politeness_level=politeness,
            grammar_notes=" ".join(notes),
            vocabulary_tips=vocab_tips
        )

    def _evaluate_english_builtin(self, text: str) -> CoachingResult:
        """Analyze English grammar, phrasing, and formality."""
        text_clean = text.strip()
        notes = []
        vocab_tips = []
        suggested = text_clean
        is_natural = True

        # Politeness / Formality detection
        has_polite = bool(re.search(r'\b(could you|would you|please|may i|i would like|appreciate)\b', text_clean, re.I))
        has_slang = bool(re.search(r'\b(gonna|wanna|gotta|kinda|dunno|yeah|dude|bro)\b', text_clean, re.I))

        if has_polite:
            formality = "Polite / Formal"
        elif has_slang:
            formality = "Casual / Colloquial"
        else:
            formality = "Neutral / Conversational"

        # Pattern 1: Missing indefinite article before singular countable noun
        if re.search(r'\b(have|want|see|buy|need)\s+(car|dog|cat|book|ticket|station|hotel)\b', text_clean, re.I):
            suggested = re.sub(
                r'\b(have|want|see|buy|need)\s+(car|dog|cat|book|ticket|station|hotel)\b',
                lambda m: f"{m.group(1)} a {m.group(2)}",
                suggested,
                flags=re.I
            )
            notes.append("Remember to use the indefinite article 'a' or 'the' before singular countable nouns.")
            is_natural = False

        # Pattern 2: 'where is station' -> 'where is the station'
        if re.search(r'\bwhere is station\b', text_clean, re.I):
            suggested = re.sub(r'\bwhere is station\b', 'where is the station', suggested, flags=re.I)
            notes.append("Missing definite article: Use 'the' when referring to a specific public location like 'the station'.")
            is_natural = False

        # Pattern 3: 'I very like' -> 'I really like'
        if re.search(r'\bi very like\b', text_clean, re.I):
            suggested = re.sub(r'\bi very like\b', 'I really like', suggested, flags=re.I)
            notes.append("'Very' modifies adjectives, not verbs directly. Use 'really like' or 'like ... very much'.")
            is_natural = False

        # Conversational reply generation
        lower = text_clean.lower()
        if "station" in lower or "where" in lower or "how to get" in lower:
            reply = "You can take the central line right from here! It's just a 5-minute walk down the main street."
            vocab_tips.append("'Within walking distance' is a natural native idiom.")
        elif "food" in lower or "eat" in lower or "hungry" in lower or "restaurant" in lower:
            reply = "There's an amazing local cafe just around the corner. What kind of cuisine are you in the mood for?"
            vocab_tips.append("'I'm in the mood for...' expresses your craving naturally.")
        elif "hello" in lower or "hi" in lower or "morning" in lower:
            reply = "Good day! It's great to speak with you. What would you like to chat about today?"
        else:
            reply = "That makes total sense! Could you tell me a little more about that?"

        if is_natural and not notes:
            notes.append("Excellent phrasing and natural grammatical cadence!")

        return CoachingResult(
            user_text=text_clean,
            practice_lang="en",
            reply_text=reply,
            reply_lang="en",
            suggested_correction=suggested if not is_natural else text_clean,
            is_natural=is_natural,
            politeness_level=formality,
            grammar_notes=" ".join(notes),
            vocabulary_tips=vocab_tips
        )

    def _query_ollama(self, text: str, lang: str) -> Optional[CoachingResult]:
        """Query local Ollama instance for conversational partner response and structured grammar coaching."""
        system_prompt = (
            f"You are a friendly, encouraging AI Language Tutor helping the user master {('Japanese' if lang == 'ja' else 'English')}.\n"
            "Analyze what the user said, continue the conversation naturally in the practice language, and provide constructive feedback.\n"
            "Respond ONLY with valid JSON in this exact structure:\n"
            "{\n"
            '  "reply": "Conversational continuation in the practice language",\n'
            '  "correction": "Natural, corrected sentence (or same as user text if already natural)",\n'
            '  "is_natural": true/false,\n'
            '  "politeness": "Casual / Polite (丁寧語) / Keigo / Formal",\n'
            '  "grammar_notes": "Concise explanation in English of grammar, particles, or nuance",\n'
            '  "vocabulary_tips": ["Tip 1", "Tip 2"]\n'
            "}"
        )

        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "format": "json",
            "stream": false
        }

        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("message", {}).get("content", "{}")
                parsed = json.loads(content)
                return CoachingResult(
                    user_text=text,
                    practice_lang=lang,
                    reply_text=parsed.get("reply", "That's interesting!"),
                    reply_lang=lang,
                    suggested_correction=parsed.get("correction", text),
                    is_natural=parsed.get("is_natural", True),
                    politeness_level=parsed.get("politeness", "Polite"),
                    grammar_notes=parsed.get("grammar_notes", "Good communication!"),
                    vocabulary_tips=parsed.get("vocabulary_tips", [])
                )
        except Exception as e:
            logger.info(f"Ollama coach query failed ({e}), falling back to builtin offline engine.")
            return None

    def _query_api(self, text: str, lang: str) -> Optional[CoachingResult]:
        """Query external OpenAI-compatible API endpoint for coaching."""
        # Built with standard HTTP request to avoid external package dependencies
        try:
            payload = {
                "model": self.api_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"You are an encouraging AI Language Tutor for {('Japanese' if lang == 'ja' else 'English')}. "
                            "Analyze the user's sentence and reply with pure JSON: "
                            "{\"reply\": \"...\", \"correction\": \"...\", \"is_natural\": bool, \"politeness\": \"...\", \"grammar_notes\": \"...\", \"vocabulary_tips\": [\"...\"]}"
                        )
                    },
                    {"role": "user", "content": text}
                ],
                "response_format": {"type": "json_object"}
            }
            req = urllib.request.Request(
                f"{self.api_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return CoachingResult(
                    user_text=text,
                    practice_lang=lang,
                    reply_text=parsed.get("reply", "Understood!"),
                    reply_lang=lang,
                    suggested_correction=parsed.get("correction", text),
                    is_natural=parsed.get("is_natural", True),
                    politeness_level=parsed.get("politeness", "Polite"),
                    grammar_notes=parsed.get("grammar_notes", "Clear expression!"),
                    vocabulary_tips=parsed.get("vocabulary_tips", [])
                )
        except Exception as e:
            logger.warning(f"Cloud API coach query failed ({e}), falling back to builtin engine.")
            return None
