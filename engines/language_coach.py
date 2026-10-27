"""AI Language Tutor and Conversational Coach Engine for EchoBridge.
Supports Hybrid Local Heuristic Engine, Local Ollama (Qwen2.5/Llama3), and OpenAI-compatible endpoints.
Includes Situational Role-Play Scenarios (Dining, Transit, Hotel, Business, Free Talk).
"""
import json
import logging
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

COACH_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "free_talk": {
        "id": "free_talk",
        "title": "🗣️ Free Conversation / 日常会話",
        "description": "General casual conversation and everyday practice.",
        "icon": "💬",
        "role_ja": "親しみやすい会話パートナーとして、日常の話題について楽しく自然に会話してください。",
        "role_en": "You are a friendly conversation partner. Engage in casual small talk on everyday topics."
    },
    "cafe": {
        "id": "cafe",
        "title": "🍵 Cafe & Dining / カフェ・飲食店",
        "description": "Practice ordering, asking for recommendations, and paying the bill.",
        "icon": "☕",
        "role_ja": "日本の居酒屋またはカフェの店員として、丁寧な接客言葉（いらっしゃいませ、ご注文はお決まりですか、など）で対応してください。",
        "role_en": "You are a polite waiter at a restaurant or cafe. Help the customer order, suggest specials, and take their order."
    },
    "transit": {
        "id": "transit",
        "title": "🚅 Transit & Directions / 道案内・駅",
        "description": "Practice asking for station exits, landmarks, and train lines.",
        "icon": "🗺️",
        "role_ja": "駅員または親切な地元の人として、目的地への道順や電車の乗り換えを分かりやすく案内してください。",
        "role_en": "You are a helpful local resident or station attendant. Guide the user with clear transit directions."
    },
    "hotel": {
        "id": "hotel",
        "title": "🏨 Hotel Check-in / ホテル・旅館",
        "description": "Hotel check-in, asking about breakfast, check-out times, and amenities.",
        "icon": "🛎️",
        "role_ja": "ホテルのフロント係として、丁寧な敬語（かしこまりました、恐れ入ります、など）でチェックイン手続きと案内をしてください。",
        "role_en": "You are a hotel front desk receptionist. Assist the guest with check-in, amenities, and travel queries."
    },
    "business": {
        "id": "business",
        "title": "💼 Business & Interview / 面接・ビジネス",
        "description": "Formal self-introduction, job interview questions, and keigo practice.",
        "icon": "👔",
        "role_ja": "企業の面接官またはビジネス同僚として、礼儀正しいビジネス敬語で対話し、適切な表現を促してください。",
        "role_en": "You are a professional hiring manager or business colleague. Ask career questions and evaluate response structure."
    }
}

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
    scenario_id: str = "free_talk"

class LanguageCoachEngine:
    """Evaluates speech utterances, provides conversational replies, and explains communication improvements."""

    def __init__(
        self,
        provider: str = "builtin",          # "builtin", "ollama", or "api"
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:0.5b",
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_model: str = "gpt-4o-mini",
        scenario: str = "free_talk"
    ):
        self.provider = provider
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.api_url = api_url.rstrip("/") if api_url else None
        self.api_key = api_key
        self.api_model = api_model
        self.scenario = scenario if scenario in COACH_SCENARIOS else "free_talk"

    def set_scenario(self, scenario_id: str) -> bool:
        """Switch active role-play practice scenario."""
        if scenario_id in COACH_SCENARIOS:
            self.scenario = scenario_id
            logger.info(f"Language Coach scenario switched to: {scenario_id}")
            return True
        logger.warning(f"Unknown scenario ID: {scenario_id}")
        return False

    @staticmethod
    def get_available_scenarios() -> Dict[str, Dict[str, Any]]:
        """Return all available coaching role-play scenarios."""
        return COACH_SCENARIOS

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
                grammar_notes="No speech detected.",
                scenario_id=self.scenario
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
        """Analyze Japanese grammar, politeness, and particle usage with scenario awareness."""
        text_clean = text.strip()
        notes = []
        vocab_tips = []
        suggested = text_clean
        is_natural = True

        # Politeness detection
        has_desu_masu = bool(re.search(r'(です|ます|でした|ました|ません|ましょう)', text_clean))
        has_keigo = bool(re.search(r'(いらっしゃ|なさる|おっしゃ|くださ|いたし|存じ|参り|申します|お伺い)', text_clean))
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

        # Pattern 5: Missing polite ending in public/formal context
        if not has_desu_masu and not has_keigo and self.scenario in ("cafe", "transit", "hotel", "business"):
            notes.append("In this situational scenario, ending your sentence with 『〜です』, 『〜ます』, or 『〜でしょうか？』 ensures appropriate respect.")

        # Scenario-specific conversational replies
        sc = self.scenario
        if sc == "cafe":
            if any(w in text_clean for w in ("おすすめ", "何がいい", "人気")):
                reply = "当店のおすすめは特製豚骨ラーメンと焼きたて餃子でございます！どちらにいたしましょうか？"
                vocab_tips.append("『おすすめは何ですか？』 (What do you recommend?)")
            elif any(w in text_clean for w in ("会計", "いくら", "払", "お勘定")):
                reply = "お会計ですね！合計で1,250円になります。現金のほか、交通系ICカードもご利用いただけます。"
                vocab_tips.append("『別々でお願いします』 (Separate checks please)")
            elif any(w in text_clean for w in ("水", "お冷", "メニュー")):
                reply = "かしこまりました！お冷とメニューをお持ちいたします。少々お待ちくださいませ。"
                vocab_tips.append("『お冷をいただけますか？』 (Could I have some cold water?)")
            else:
                reply = "いらっしゃいませ！ご注文はお決まりでしょうか？ごゆっくりお選びくださいね。"
                vocab_tips.append("『これをお願いします』 (I'll have this please)")

        elif sc == "transit":
            if any(w in text_clean for w in ("駅", "改札", "出口", "どこ")):
                reply = "駅ですね！この道をまっすぐ100メートルほど進むと、右手に東口改札が見えてまいりますよ。"
                vocab_tips.append("『徒歩5分』 (5 minutes on foot)")
            elif any(w in text_clean for w in ("何番線", "ホーム", "電車")):
                reply = "新宿方面行きは3番線ホームからの発車となります。階段を上がって右側です。"
                vocab_tips.append("『〜行きは何番線ですか？』 (Which platform for ...?)")
            elif any(w in text_clean for w in ("乗り換え", "どうやって")):
                reply = "次の駅で山手線にお乗り換えいただくと、一番早くてスムーズですよ。"
                vocab_tips.append("『乗り換え』 (Transfer/Connection)")
            else:
                reply = "道案内ですね！どちらの駅や施設をお探しですか？お気軽にお尋ねください。"

        elif sc == "hotel":
            if any(w in text_clean for w in ("チェックイン", "予約")):
                reply = "いらっしゃいませ！ご宿泊のご予約ですね。恐れ入りますが、ご予約のお名前とお電話番号をお伺いできますでしょうか？"
                vocab_tips.append("『予約してある田中です』 (I have a reservation under Tanaka)")
            elif any(w in text_clean for w in ("朝食", "ご飯", "時間")):
                reply = "朝食は1階レストランにて、朝7時から9時半まで和洋バイキングをご用意しております。"
                vocab_tips.append("『朝食は何時からですか？』 (What time is breakfast?)")
            elif any(w in text_clean for w in ("荷物", "預け")):
                reply = "はい、チェックイン前のお荷物はこちらのフロントにて喜んでお預かりいたします！"
                vocab_tips.append("『荷物を預かっていただけますか？』 (Could you hold my luggage?)")
            else:
                reply = "ホテルへようこそ！ご滞在中に何かご不明な点やお困りのことはございますか？"

        elif sc == "business":
            if any(w in text_clean for w in ("初めまして", "自己紹介", "申します")):
                reply = "初めまして！本日は貴重なお時間をいただきありがとうございます。どうぞよろしくお願いいたします。"
                vocab_tips.append("『どうぞよろしくお願いいたします』 (Pleased to meet you / Looking forward to working together)")
            elif any(w in text_clean for w in ("志望動機", "経験", "仕事")):
                reply = "素晴らしいご経歴ですね！弊社で特に力を発揮したいプロジェクトや強みについて、詳しくお聞かせいただけますか？"
                vocab_tips.append("『私の強みは〜です』 (My strong point is...)")
            else:
                reply = "ご説明ありがとうございます。ビジネスの場にふさわしい、非常に丁寧で明瞭な話し方ですね！"

        else: # free_talk
            if "駅" in text_clean or "どこ" in text_clean:
                reply = "駅ですね！この道をまっすぐ歩いて、2つ目の交差点を右に曲がると見えてきますよ。"
                vocab_tips.append("『徒歩5分』 (5 minutes on foot) is a great phrase when discussing distances.")
            elif "何" in text_clean and ("食べ" in text_clean or "お腹" in text_clean):
                reply = "お腹が空きましたね！近くに美味しいラーメン屋さんとお寿司屋さんがありますが、どちらがいいですか？"
                vocab_tips.append("『おすすめは何ですか？』 (What do you recommend?)")
            elif "元気" in text_clean or "こんにちは" in text_clean or "初めまして" in text_clean:
                reply = "こんにちは！お会いできて嬉しいです。今日の日本語の練習、一緒に楽しく頑張りましょう！"
            else:
                reply = "なるほど、よく分かりました！とても自然な話し方ですね。続けてもっと詳しく教えてもらえますか？"

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
            vocabulary_tips=vocab_tips,
            scenario_id=self.scenario
        )

    def _evaluate_english_builtin(self, text: str) -> CoachingResult:
        """Analyze English grammar, phrasing, and formality with scenario awareness."""
        text_clean = text.strip()
        notes = []
        vocab_tips = []
        suggested = text_clean
        is_natural = True

        # Politeness / Formality detection
        has_polite = bool(re.search(r'\b(could you|would you|please|may i|i would like|appreciate|excuse me)\b', text_clean, re.I))
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

        # Scenario-specific conversational replies
        sc = self.scenario
        lower = text_clean.lower()

        if sc == "cafe":
            if any(w in lower for w in ("recommend", "special", "popular")):
                reply = "Our house special today is the grilled salmon bowl and iced matcha latte! Would you like to try that?"
                vocab_tips.append("'What do you recommend?' is the most natural way to ask for suggestions.")
            elif any(w in lower for w in ("bill", "check", "pay", "how much")):
                reply = "Certainly! The total comes to $14.50. Will you be paying with cash or card?"
                vocab_tips.append("'Could we have the check, please?' is polite and standard.")
            else:
                reply = "Welcome to our cafe! Take your time with the menu, and let me know whenever you're ready to order."
                vocab_tips.append("'I'll have the...' is natural when ordering.")

        elif sc == "transit":
            if any(w in lower for w in ("station", "where", "how to get", "exit")):
                reply = "You can take the central line right from here! It's just a 5-minute walk down the main street."
                vocab_tips.append("'Within walking distance' is a natural native idiom.")
            elif any(w in lower for w in ("platform", "train", "line")):
                reply = "Trains toward downtown depart from Platform 2. Take the escalator up on your left."
                vocab_tips.append("'Which platform for...?' is concise and clear.")
            else:
                reply = "I'd be glad to help with transit! Which destination or landmark are you trying to reach?"

        elif sc == "hotel":
            if any(w in lower for w in ("check in", "reservation", "booking")):
                reply = "Welcome! May I have the name and phone number on the reservation, please?"
                vocab_tips.append("'I have a reservation under the name...'")
            elif any(w in lower for w in ("breakfast", "morning", "time")):
                reply = "Breakfast is served in the main dining room on the second floor between 7:00 and 10:00 AM."
            elif any(w in lower for w in ("luggage", "bag", "hold")):
                reply = "Of course! We can securely hold your luggage behind the front desk until your room is ready."
                vocab_tips.append("'Could you hold my bags for a few hours?'")
            else:
                reply = "Welcome to the hotel! Please let us know if there is anything we can do to make your stay comfortable."

        elif sc == "business":
            if any(w in lower for w in ("introduce", "pleasure", "meet you")):
                reply = "It's a pleasure to meet you as well! Thank you for joining us today. Let's get started."
                vocab_tips.append("'It's a pleasure to make your acquaintance' is formal and polished.")
            elif any(w in lower for w in ("experience", "project", "role")):
                reply = "That sounds like a very impactful initiative. What was your specific leadership contribution to that outcome?"
            else:
                reply = "Thank you for sharing that. Your communication style is clear, articulate, and well-structured!"

        else: # free_talk
            if "station" in lower or "where" in lower:
                reply = "You can take the central line right from here! It's just a 5-minute walk down the main street."
                vocab_tips.append("'Within walking distance' is a natural native idiom.")
            elif "food" in lower or "eat" in lower or "hungry" in lower:
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
            vocabulary_tips=vocab_tips,
            scenario_id=self.scenario
        )

    def _query_ollama(self, text: str, lang: str) -> Optional[CoachingResult]:
        """Query local Ollama instance for conversational partner response and structured grammar coaching."""
        sc_info = COACH_SCENARIOS.get(self.scenario, COACH_SCENARIOS["free_talk"])
        role_prompt = sc_info.get(f"role_{lang}", sc_info["role_ja"])

        system_prompt = (
            f"You are a friendly, encouraging AI Language Tutor helping the user master {('Japanese' if lang == 'ja' else 'English')}.\n"
            f"ROLE-PLAY SCENARIO: {sc_info['title']}\n"
            f"SCENARIO INSTRUCTION: {role_prompt}\n"
            "Analyze what the user said, continue the conversation naturally in the practice language while staying in character, and provide constructive feedback.\n"
            "Respond ONLY with valid JSON in this exact structure:\n"
            "{\n"
            '  "reply": "In-character conversational reply in the practice language",\n'
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
            "stream": False
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
                    vocabulary_tips=parsed.get("vocabulary_tips", []),
                    scenario_id=self.scenario
                )
        except Exception as e:
            logger.info(f"Ollama coach query failed ({e}), falling back to builtin offline engine.")
            return None

    def _query_api(self, text: str, lang: str) -> Optional[CoachingResult]:
        """Query external OpenAI-compatible API endpoint for coaching."""
        sc_info = COACH_SCENARIOS.get(self.scenario, COACH_SCENARIOS["free_talk"])
        role_prompt = sc_info.get(f"role_{lang}", sc_info["role_ja"])

        try:
            system_prompt = (
                f"You are an encouraging AI Language Tutor for {('Japanese' if lang == 'ja' else 'English')}. "
                f"Current scenario: {sc_info['title']}. Role instruction: {role_prompt}. "
                "Analyze the user's sentence, stay in character with your reply, and output pure JSON: "
                "{\"reply\": \"...\", \"correction\": \"...\", \"is_natural\": bool, \"politeness\": \"...\", \"grammar_notes\": \"...\", \"vocabulary_tips\": [\"...\"]}"
            )
            payload = {
                "model": self.api_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
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
                    vocabulary_tips=parsed.get("vocabulary_tips", []),
                    scenario_id=self.scenario
                )
        except Exception as e:
            logger.warning(f"Cloud API coach query failed ({e}), falling back to builtin engine.")
            return None
