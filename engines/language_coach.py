"""AI Language Tutor and Conversational Coach Engine for EchoBridge.
Supports Stateful Multi-Turn Conversational Memory, Contextual Grammar Analysis,
Hybrid Local Heuristic Engine, Local Ollama (Qwen2.5/Llama3), and OpenAI-compatible endpoints.
Includes Situational Role-Play Scenarios (Dining, Transit, Hotel, Business, Free Talk).
"""
import os
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
        "description": "General casual conversation, hobbies, daily life, and dynamic topic exploration.",
        "icon": "💬",
        "role_ja": "親しみやすい会話パートナーとして、日常の話題について楽しく自然に会話してください。前の発言を覚えて文脈を繋げてください。",
        "role_en": "You are a friendly conversation partner. Engage in casual small talk on everyday topics and remember previous turns."
    },
    "cafe": {
        "id": "cafe",
        "title": "🍵 Cafe & Dining / カフェ・飲食店",
        "description": "Practice greeting, ordering items, customization (size/hot/ice), dine-in/take-out, and paying the bill.",
        "icon": "☕",
        "role_ja": "日本の居酒屋またはカフェの店員として、丁寧な接客言葉（いらっしゃいませ、ご注文はお決まりですか、など）で対応してください。",
        "role_en": "You are a polite waiter at a restaurant or cafe. Help the customer order, suggest specials, take customizations, and process payment."
    },
    "transit": {
        "id": "transit",
        "title": "🚅 Transit & Directions / 道案内・駅",
        "description": "Practice asking for station exits, landmarks, train lines, platforms, travel times, and fares.",
        "icon": "🗺️",
        "role_ja": "駅員または親切な地元の人として、目的地への道順、ホーム番号、電車の乗り換えや所要時間を分かりやすく案内してください。",
        "role_en": "You are a helpful local resident or station attendant. Guide the user with clear transit directions, platforms, and fares."
    },
    "hotel": {
        "id": "hotel",
        "title": "🏨 Hotel Check-in / ホテル・旅館",
        "description": "Hotel check-in, name confirmation, room key, breakfast times, Wi-Fi, and luggage storage.",
        "icon": "🛎️",
        "role_ja": "ホテルのフロント係として、丁寧な敬語（かしこまりました、恐れ入ります、など）でチェックイン手続きと館内案内をしてください。",
        "role_en": "You are a hotel front desk receptionist. Assist the guest with check-in, room amenities, and luggage storage."
    },
    "business": {
        "id": "business",
        "title": "💼 Business & Interview / 面接・ビジネス",
        "description": "Formal self-introduction, work experience, project leadership, and polite honorifics (Keigo).",
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
    """Evaluates speech utterances with multi-turn conversation memory, context tracking, and granular grammar coaching."""

    def __init__(
        self,
        provider: Optional[str] = None,     # "builtin", "groq", "gemini", "ollama", or "api"
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:0.5b",
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_model: str = "gpt-4o-mini",
        scenario: str = "free_talk",
        groq_model: str = "qwen/qwen3.8-27b",
        gemini_model: str = "gemini-2.5-flash",
        api_keys_file: str = "config/api_keys.json",
        groq_keys: Optional[List[str]] = None,
        gemini_keys: Optional[List[str]] = None,
        rotation_enabled: bool = True,
        fallback_to_offline: bool = True
    ):
        self.provider = provider
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.api_url = api_url.rstrip("/") if api_url else None
        self.api_key = api_key
        self.api_model = api_model
        self.scenario = scenario if scenario in COACH_SCENARIOS else "free_talk"
        self.groq_model = groq_model
        self.gemini_model = gemini_model
        self.api_keys_file = api_keys_file
        self.rotation_enabled = rotation_enabled
        self.fallback_to_offline = fallback_to_offline

        self.groq_keys: List[str] = list(groq_keys or [])
        self.gemini_keys: List[str] = list(gemini_keys or [])
        self.groq_key_index: int = 0
        self.gemini_key_index: int = 0

        # Load key pools from config file and environment
        self._load_keys_from_config(self.api_keys_file, explicit_provider=provider)

        # Multi-turn conversational memory & entity store
        self.conversation_history: List[Dict[str, str]] = []
        self.memory_store: Dict[str, Any] = {
            "user_name": None,
            "destination": None,
            "ordered_items": [],
            "scenario_stage": 0,
            "topics": []
        }

    def _load_keys_from_config(self, filepath: str, explicit_provider: Optional[str] = None):
        """Loads API keys for Groq and Gemini from json file and environment variables."""
        paths_to_check = [
            filepath,
            os.path.join(os.path.dirname(os.path.dirname(__file__)), filepath),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "api_keys.json"),
            "config/api_keys.json"
        ]

        for p in paths_to_check:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    if "groq" in cfg:
                        if not self.groq_keys and "keys" in cfg["groq"]:
                            self.groq_keys = [k.strip() for k in cfg["groq"]["keys"] if k.strip()]
                        if "model" in cfg["groq"] and cfg["groq"]["model"]:
                            self.groq_model = cfg["groq"]["model"]
                    if "gemini" in cfg:
                        if not self.gemini_keys and "keys" in cfg["gemini"]:
                            self.gemini_keys = [k.strip() for k in cfg["gemini"]["keys"] if k.strip()]
                        if "model" in cfg["gemini"] and cfg["gemini"]["model"]:
                            self.gemini_model = cfg["gemini"]["model"]
                    break
                except Exception as e:
                    logger.warning(f"Error loading API keys from {p}: {e}")

        # Supplement with environment variables if available
        for i in range(1, 10):
            gk = os.environ.get(f"GROQ_API_KEY_{i}") or (os.environ.get("GROQ_API_KEY") if i == 1 else None)
            if gk and gk.strip() and gk.strip() not in self.groq_keys:
                self.groq_keys.append(gk.strip())
            
            gemk = os.environ.get(f"GEMINI_API_KEY_{i}") or (os.environ.get("GEMINI_API_KEY") if i == 1 else None)
            if gemk and gemk.strip() and gemk.strip() not in self.gemini_keys:
                self.gemini_keys.append(gemk.strip())

        # Check settings.json for coach provider preference if not explicitly provided
        if explicit_provider is None:
            settings_paths = ["config/settings.json", os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "settings.json")]
            for sp in settings_paths:
                if os.path.exists(sp):
                    try:
                        with open(sp, "r", encoding="utf-8") as f:
                            scfg = json.load(f)
                        c_cfg = scfg.get("coach", {})
                        if "provider" in c_cfg:
                            self.provider = c_cfg["provider"]
                        if "groq_model" in c_cfg and c_cfg["groq_model"]:
                            self.groq_model = c_cfg["groq_model"]
                        if "gemini_model" in c_cfg and c_cfg["gemini_model"]:
                            self.gemini_model = c_cfg["gemini_model"]
                        break
                    except Exception:
                        pass

        if not self.provider:
            self.provider = "builtin"

        if self.provider == "groq" and not self.groq_keys:
            self.provider = "builtin"
        elif self.provider == "gemini" and not self.gemini_keys:
            self.provider = "builtin"

        logger.info(f"LanguageCoachEngine initialized (provider: {self.provider}): {len(self.groq_keys)} Groq keys, {len(self.gemini_keys)} Gemini keys loaded.")

    def get_key_pool_status(self) -> Dict[str, Any]:
        """Returns the operational status of external LLM key pools."""
        return {
            "provider": self.provider,
            "groq_keys_count": len(self.groq_keys),
            "groq_active_index": self.groq_key_index,
            "gemini_keys_count": len(self.gemini_keys),
            "gemini_active_index": self.gemini_key_index,
            "groq_model": self.groq_model,
            "gemini_model": self.gemini_model,
            "fallback_to_offline": self.fallback_to_offline
        }

    def clear_history(self):
        """Reset conversation memory and dialogue state."""
        self.conversation_history.clear()
        self.memory_store = {
            "user_name": None,
            "destination": None,
            "ordered_items": [],
            "scenario_stage": 0,
            "topics": []
        }
        logger.info("Language Coach conversation history and context memory cleared.")

    def set_scenario(self, scenario_id: str) -> bool:
        """Switch active role-play practice scenario and reset stage."""
        if scenario_id in COACH_SCENARIOS:
            self.scenario = scenario_id
            self.memory_store["scenario_stage"] = 0
            self.memory_store["destination"] = None
            self.memory_store["ordered_items"] = []
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
        Evaluate user's spoken sentence and generate a conversational reply + coaching notes
        with multi-turn conversational memory, key rotation, and seamless offline fallback.
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

        # 1. Try Groq Pool if configured
        if self.provider == "groq":
            result = self._query_groq_pool(user_text, practice_lang)
            if result:
                self._record_turn(user_text, result.reply_text)
                return result
            elif self.fallback_to_offline:
                logger.info("Groq pool exhausted. Attempting Gemini pool fallback...")
                result = self._query_gemini_pool(user_text, practice_lang)
                if result:
                    self._record_turn(user_text, result.reply_text)
                    return result

        # 2. Try Gemini Pool if configured
        if self.provider == "gemini":
            result = self._query_gemini_pool(user_text, practice_lang)
            if result:
                self._record_turn(user_text, result.reply_text)
                return result
            elif self.fallback_to_offline:
                logger.info("Gemini pool exhausted. Attempting Groq pool fallback...")
                result = self._query_groq_pool(user_text, practice_lang)
                if result:
                    self._record_turn(user_text, result.reply_text)
                    return result

        # 3. Try Ollama if configured
        if self.provider == "ollama":
            result = self._query_ollama(user_text, practice_lang)
            if result:
                self._record_turn(user_text, result.reply_text)
                return result

        # 4. Try Cloud / Custom API if configured
        if self.provider == "api" and self.api_url and self.api_key:
            result = self._query_api(user_text, practice_lang)
            if result:
                self._record_turn(user_text, result.reply_text)
                return result

        # 5. Default: High-performance Builtin Multi-Turn Heuristic Evaluator (100% Offline)
        result = self._evaluate_builtin(user_text, practice_lang)
        self._record_turn(user_text, result.reply_text)
        return result

    def _record_turn(self, user_text: str, reply_text: str):
        """Append turn to conversation memory and retain up to 16 turns."""
        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": reply_text})
        if len(self.conversation_history) > 16:
            self.conversation_history = self.conversation_history[-16:]

    def _evaluate_builtin(self, text: str, lang: str) -> CoachingResult:
        """
        Instant 100% offline rule-based & linguistic pattern analyzer for Japanese and English
        with multi-turn state tracking and entity memory.
        """
        if lang == "ja":
            return self._evaluate_japanese_builtin(text)
        else:
            return self._evaluate_english_builtin(text)

    def _evaluate_japanese_builtin(self, text: str) -> CoachingResult:
        """Analyze Japanese grammar, politeness, and particle usage with multi-turn memory."""
        text_clean = text.strip()
        notes = []
        vocab_tips = []
        suggested = text_clean
        is_natural = True

        # Extract name entity if introduced
        name_match = re.search(r'(?:私|僕|自分)は\s*([^\s、。]+?)\s*(?:です|と申します|だ)', text_clean)
        if not name_match:
            name_match = re.search(r'([^\s、。]+?)\s*と申します', text_clean)
        if name_match:
            self.memory_store["user_name"] = name_match.group(1).strip()

        # Politeness detection
        has_desu_masu = bool(re.search(r'(です|ます|でした|ました|ません|ましょう|でしょうか)', text_clean))
        has_keigo = bool(re.search(r'(いらっしゃ|なさる|おっしゃ|くださ|いたし|存じ|参り|申します|お伺い|恐れ入り|拝見)', text_clean))
        has_casual = bool(re.search(r'(だ|だよ|ね|よ|じゃない|ちゃう|てる|とく)[。！？\s]*$', text_clean))

        if has_keigo:
            politeness = "Honorific (敬語 - Keigo)"
        elif has_desu_masu:
            politeness = "Polite (丁寧語 - Teineigo)"
        elif has_casual:
            politeness = "Casual (普通体 - Plain Form)"
        else:
            politeness = "Informal / Incomplete"

        # --- Granular Japanese Grammar & Particle Diagnostics ---
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

        # Pattern 3: '〜が好きです' vs '〜を好きです'
        if "を好き" in text_clean:
            suggested = suggested.replace("を好き", "が好き")
            notes.append("In Japanese, 好き (suki) is a na-adjective. The object of affection is marked with 『が』, not 『を』.")
            is_natural = False

        # Pattern 4: '〜ができる' vs '〜をできる'
        if "をできる" in text_clean or "をできます" in text_clean:
            suggested = suggested.replace("をできる", "ができる").replace("をできます", "ができます")
            notes.append("Potential verbs like できる (can do) take the particle 『が』 rather than 『を』.")
            is_natural = False

        # Pattern 5: '電車を乗る' -> '電車に乗る'
        if re.search(r'(電車|バス|タクシー|新幹線)を乗[るり]', text_clean):
            suggested = re.sub(r'(電車|バス|タクシー|新幹線)を(乗[るり])', r'\1に\2', suggested)
            notes.append("Boarding transportation takes the particle 『に』 rather than 『を』 (e.g. 『電車に乗る』).")
            is_natural = False

        # Pattern 6: Bare request in service scenario: '〜ちょうだい', '〜お願い' -> '〜をお願いします'
        if re.search(r'(お願い|ちょうだい|くれ)[。！？\s]*$', text_clean) and self.scenario in ("cafe", "transit", "hotel"):
            suggested = re.sub(r'(お願い|ちょうだい|くれ)[。！？\s]*$', r'をお願いします。', suggested)
            notes.append("In dining or public services, phrase your request politely with 『〜をお願いします』 or 『〜をいただけますか』.")
            is_natural = False

        # Pattern 7: Missing polite ending in formal situational context
        if not has_desu_masu and not has_keigo and self.scenario in ("cafe", "transit", "hotel", "business"):
            if not any(w in text_clean for w in ("はい", "いいえ", "どうも", "ありがとう")):
                suggested += "です。"
                notes.append("In this situational scenario, ending sentences with 『〜です』 or 『〜ます』 ensures polite etiquette.")
                is_natural = False

        # --- Stateful Scenario Multi-Turn Dialogues ---
        sc = self.scenario
        stage = self.memory_store.get("scenario_stage", 0)
        user_name = self.memory_store.get("user_name")
        honorific_name = f"{user_name}様、" if user_name else ""

        if sc == "cafe":
            # Intent: Asking recommendation
            if any(w in text_clean for w in ("おすすめ", "何がいい", "人気", "人気メニュー")):
                reply = "当店のおすすめは、挽きたてのアイスカフェラテと季節限定の抹茶スフレパンケーキでございます！どちらにいたしましょうか？"
                vocab_tips.append("『おすすめは何ですか？』 (What do you recommend?)")
                vocab_tips.append("『一番人気はどれですか？』 (Which is the most popular?)")
                self.memory_store["scenario_stage"] = 1

            # Intent: Customization (only when already ordered or specifically saying size/dine-in)
            elif (stage >= 2 and any(w in text_clean.lower() for w in ("店内", "ここ", "お持ち帰り", "持ち帰り", "テイクアウト", "sサイズ", "mサイズ", "lサイズ", "サイズ", "ホットで", "アイスで", "ホット", "アイス"))) or any(w in text_clean.lower() for w in ("店内", "お持ち帰り", "テイクアウト", "sサイズ", "mサイズ", "lサイズ")):
                reply = "かしこまりました！それでは合計で680円になります。現金のほか、交通系ICカードやクレジットカードもご利用いただけますよ。"
                vocab_tips.append("『カードで支払えますか？』 (Can I pay by card?)")
                vocab_tips.append("『領収書をいただけますか？』 (Could I have a receipt?)")
                self.memory_store["scenario_stage"] = 3

            # Intent: Ordering item
            elif any(w in text_clean for w in ("コーヒー", "ラテ", "お茶", "紅茶", "ケーキ", "パン", "サンド", "注文", "これ", "ひとつ", "二つ", "ください", "お願いします")):
                # Extract ordered item name if present
                for item in ("アイスカフェラテ", "アイスコーヒー", "コーヒー", "カフェラテ", "ラテ", "抹茶ラテ", "紅茶", "パンケーキ"):
                    if item in text_clean:
                        self.memory_store["ordered_items"].append(item)
                        break

                ordered_name = self.memory_store["ordered_items"][-1] if self.memory_store["ordered_items"] else "ご注文のお品物"

                if stage <= 1:
                    reply = f"かしこまりました！{ordered_name}ですね。サイズはS、M、Lのどれにいたしましょうか？また、店内でお召し上がりですか、それともお持ち帰りですか？"
                    vocab_tips.append("『Mサイズでお願いします』 (Medium size, please)")
                    vocab_tips.append("『店内で』 (For here) / 『持ち帰りで』 (To go)")
                    self.memory_store["scenario_stage"] = 2
                else:
                    reply = f"承知いたしました。{ordered_name}をご用意いたしますね。他にご注文やお好みのトッピングはございますか？"
                    self.memory_store["scenario_stage"] = 3

            # Intent: Water or amenities
            elif any(w in text_clean for w in ("水", "お冷", "メニュー", "砂糖", "ミルク")):
                reply = "かしこまりました！すぐにお冷とメニューをお持ちいたしますね。ごゆっくりお過ごしください。"
                vocab_tips.append("『お冷をいただけますか？』 (Could I have some cold water?)")

            else:
                if stage == 0:
                    reply = f"いらっしゃいませ！{honorific_name}カフェ・エコーブリッジへようこそ。店内でお召し上がりですか？メニューをお持ちいたしますね。"
                    vocab_tips.append("『メニューを見せていただけますか？』 (May I see the menu?)")
                    self.memory_store["scenario_stage"] = 1
                else:
                    reply = "かしこまりました！その他に気になる点や追加のご注文はございますでしょうか？"
                    self.memory_store["scenario_stage"] = stage + 1

        elif sc == "transit":
            # Extract destination
            dest_match = re.search(r'([^\s、。]+?)(?:駅|行き|まで|へ行きたい|に行きたい)', text_clean)
            if dest_match and dest_match.group(1) not in ("どこ", "何"):
                self.memory_store["destination"] = dest_match.group(1).strip() + "駅"

            dest = self.memory_store.get("destination", "目的地")

            if any(w in text_clean for w in ("駅", "改札", "出口", "どこ", "行き方", "どうやって")):
                reply = f"{dest}ですね！この先の連絡通路をまっすぐ進んでいただくと、右手に3番線ホームへの階段がございますよ。"
                vocab_tips.append("『〜行きは何番線ですか？』 (Which platform for ...?)")
                vocab_tips.append("『徒歩5分』 (5 minutes on foot)")
                self.memory_store["scenario_stage"] = 1

            elif any(w in text_clean for w in ("何番線", "ホーム", "電車", "線")):
                reply = f"{dest}方面行きでしたら、4番線の快速電車が一番早いです！約12分で到着いたします。"
                vocab_tips.append("『快速電車』 (Rapid train) / 『各駅停車』 (Local train)")
                self.memory_store["scenario_stage"] = 2

            elif any(w in text_clean for w in ("時間", "何分", "いくら", "運賃", "切符", "乗り換え")):
                reply = f"{dest}までの運賃は220円でございます。交通系ICカードでしたらタッチするだけでスムーズにご乗車いただけますよ。"
                vocab_tips.append("『ICカードのチャージ』 (Transit card top-up)")
                self.memory_store["scenario_stage"] = 3

            else:
                reply = "駅のご案内ですね！どちらの駅や観光地をお探しでしょうか？路線図を見ながら詳しくご案内いたします。"
                vocab_tips.append("『すみません、道を教えていただけますか？』 (Excuse me, could you tell me the way?)")

        elif sc == "hotel":
            if any(w in text_clean for w in ("チェックイン", "予約")):
                reply = f"いらっしゃいませ！ホテル・エコーブリッジへようこそ。ご宿泊のご予約ですね。恐れ入りますが、{honorific_name}お名前とお電話番号をお伺いできますでしょうか？"
                vocab_tips.append("『予約してある田中です』 (I have a reservation under Tanaka)")
                self.memory_store["scenario_stage"] = 1

            elif user_name or any(w in text_clean for w in ("名前", "予約の")):
                reply = f"{honorific_name}ご予約確認いたしました！本日より2泊、禁煙デラックスルームでございます。こちらがお部屋のカードキーになります。"
                vocab_tips.append("『カードキーをお受け取りください』 (Please take your keycard)")
                self.memory_store["scenario_stage"] = 2

            elif any(w in text_clean for w in ("朝食", "ご飯", "レストラン", "時間")):
                reply = "朝食は1階ダイニングにて、毎朝7時から9時半まで焼きたてパンと和食バイキングをご用意しております。"
                vocab_tips.append("『朝食は何時からですか？』 (What time is breakfast?)")
                self.memory_store["scenario_stage"] = 3

            elif any(w in text_clean for w in ("荷物", "預け", "チェックアウト")):
                reply = "はい！チェックイン前やチェックアウト後のお荷物は、フロントにていつでも無料でお預かりいたします。"
                vocab_tips.append("『荷物を夕方まで預かっていただけますか？』 (Could you hold my bags until evening?)")

            else:
                reply = f"ご滞在はいかがでしょうか？{honorific_name}何かご不明な点や観光案内など、いつでもお気軽にフロントへお声がけください。"

        elif sc == "business":
            if any(w in text_clean for w in ("初めまして", "自己紹介", "申します", "よろしく")):
                reply = f"初めまして！{honorific_name}本日はお忙しい中お時間をいただき誠にありがとうございます。どうぞよろしくお願いいたします。"
                vocab_tips.append("『どうぞよろしくお願い申し上げます』 (Extremely polite greeting)")
                self.memory_store["scenario_stage"] = 1

            elif any(w in text_clean for w in ("経験", "プロジェクト", "仕事", "開発", "担当")):
                reply = "素晴らしいご経歴ですね！特にそのプロジェクトで課題に直面した際、どのように解決されたか詳しくお聞かせいただけますでしょうか？"
                vocab_tips.append("『課題解決に向けて〜に取り組みました』 (I worked on ... to solve the challenge)")
                self.memory_store["scenario_stage"] = 2

            elif any(w in text_clean for w in ("強み", "スキル", "長所", "貢献")):
                reply = "非常に具体的で説得力のあるご説明ですね。弊社のグローバル展開においても大いに活躍していただけると感じております。"
                self.memory_store["scenario_stage"] = 3

            else:
                reply = "明瞭で礼儀正しいビジネス敬語ですね！続けてこれまでの実績や今後の展望についてお話しください。"

        else: # free_talk
            # Dynamic topic memory recognition
            if any(w in text_clean for w in ("映画", "アニメ", "ドラマ", "観", "見")):
                reply = "映画やエンタメがお好きなんですね！最近何かおすすめの作品を観られましたか？どんなジャンルが一番好きですか？"
                vocab_tips.append("『〜にハマっています』 (I'm hooked on / obsessed with ...)")
            elif any(w in text_clean for w in ("音楽", "バンド", "曲", "聴")):
                reply = "音楽のお話ですね！普段はどんなジャンルのアーティストをよく聴かれるんですか？"
                vocab_tips.append("『気分転換に聴きます』 (I listen to it to refresh my mood)")
            elif any(w in text_clean for w in ("料理", "食べ", "美味しい", "好き", "ラーメン", "寿司", "肉")):
                reply = "美味しいものの話題は楽しいですね！自分で料理を作られることもありますか？一番の大好物は何ですか？"
                vocab_tips.append("『大好物は〜です』 (My favorite food is...)")
            elif any(w in text_clean for w in ("旅行", "日本", "東京", "京都", "行きたい", "観光")):
                reply = "旅行は素晴らしい体験になりますよね！日本の観光地で特に行ってみたい場所や印象に残っている場所はどこですか？"
                vocab_tips.append("『一度は訪れてみたいです』 (I'd like to visit at least once)")
            elif any(w in text_clean for w in ("元気", "こんにちは", "初めまして", "おはよう")):
                greeting_name = f"{user_name}さん、" if user_name else ""
                reply = f"こんにちは！{greeting_name}お話しできて嬉しいです。今日の会話練習、リラックスして楽しく進めましょうね！"
            elif any(w in text_clean for w in ("ありがとう", "助かった")):
                reply = "どういたしまして！お力になれて嬉しいです。他にも日本語で話してみたいトピックはありますか？"
            else:
                # Context-aware continuation
                reply = f"なるほど、とても興味深いお話ですね！{text_clean[:18]}...について、もう少し詳しく聞かせてもらえますか？"

        if is_natural and not notes:
            notes.append("Your sentence structure, particle connectors, and polite rhythm are completely natural!")

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
        """Analyze English grammar, phrasing, and formality with multi-turn memory."""
        text_clean = text.strip()
        notes = []
        vocab_tips = []
        suggested = text_clean
        is_natural = True

        # Extract user name
        name_match = re.search(r'\b(?:my name is|i am|i\'m)\s+([A-Za-z]+)\b', text_clean, re.I)
        if name_match:
            self.memory_store["user_name"] = name_match.group(1).capitalize()

        # Politeness / Formality detection
        has_polite = bool(re.search(r'\b(could you|would you|please|may i|i would like|appreciate|excuse me|kindly)\b', text_clean, re.I))
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

        # Pattern 4: Bare request in service situation: 'I want this' -> 'Could I please have this?'
        if re.search(r'\bi want (this|that|water|coffee|tea|bill|check)\b', text_clean, re.I) and self.scenario in ("cafe", "transit", "hotel"):
            suggested = re.sub(r'\bi want\b', "I would like", suggested, flags=re.I)
            notes.append("In dining or customer service, 'I would like...' or 'Could I have...?' is much more polite than 'I want'.")
            is_natural = False

        # Scenario-specific stateful replies
        sc = self.scenario
        lower = text_clean.lower()
        user_name = self.memory_store.get("user_name")
        name_prefix = f"{user_name}, " if user_name else ""

        if sc == "cafe":
            if any(w in lower for w in ("recommend", "special", "popular")):
                reply = "Our house special today is the grilled salmon bowl and iced matcha latte! Would you like to try that?"
                vocab_tips.append("'What do you recommend?' is natural when asking for suggestions.")
                self.memory_store["scenario_stage"] = 1
            elif any(w in lower for w in ("coffee", "latte", "tea", "cake", "sandwich", "order", "have", "please")):
                reply = "Excellent choice! What size would you like — small, medium, or large? And would that be for here or to go?"
                vocab_tips.append("'For here or to go?' is the standard dining question.")
                vocab_tips.append("'A medium latte, to go, please.'")
                self.memory_store["scenario_stage"] = 2
            elif any(w in lower for w in ("here", "to go", "small", "medium", "large", "hot", "iced")):
                reply = "Got it! That comes to $6.50. Will you be paying with credit card, Apple Pay, or cash?"
                vocab_tips.append("'Can I tap to pay?'")
                self.memory_store["scenario_stage"] = 3
            elif any(w in lower for w in ("card", "cash", "pay", "bill", "check")):
                reply = "Payment approved! Here is your receipt. We'll have your order ready at the pickup counter in just a moment!"
                vocab_tips.append("'Keep the change!'")
                self.memory_store["scenario_stage"] = 4
            else:
                reply = f"Welcome to EchoBridge Cafe! {name_prefix}Take your time looking over the menu, and let me know whenever you're ready."
                vocab_tips.append("'I'm ready to order.'")

        elif sc == "transit":
            if any(w in lower for w in ("station", "where", "how to get", "exit", "direction")):
                reply = "You can take the central subway line right from here! It's just a 3-minute walk down this avenue on your right."
                vocab_tips.append("'Within walking distance' is an authentic native idiom.")
                self.memory_store["scenario_stage"] = 1
            elif any(w in lower for w in ("platform", "track", "train", "line")):
                reply = "Trains bound for the airport depart from Platform 3. Take the escalator down on your left."
                vocab_tips.append("'Which platform for the airport express?'")
                self.memory_store["scenario_stage"] = 2
            elif any(w in lower for w in ("time", "how long", "fare", "cost", "ticket", "much")):
                reply = "The journey takes about 18 minutes, and a single ticket is $3.25. You can tap your contactless card directly at the fare gate."
                vocab_tips.append("'Does this train run direct?'")
                self.memory_store["scenario_stage"] = 3
            else:
                reply = "I'd be glad to help with navigation! Which station, terminal, or landmark are you trying to reach?"

        elif sc == "hotel":
            if any(w in lower for w in ("check in", "reservation", "booking")):
                reply = f"Welcome to EchoBridge Hotel! {name_prefix}May I have your last name and phone number on the booking, please?"
                vocab_tips.append("'I have a reservation under the name of...'")
                self.memory_store["scenario_stage"] = 1
            elif user_name or any(w in lower for w in ("name is", "booked")):
                reply = f"Thank you, {user_name}! I found your reservation for 2 nights in our King Deluxe room. Here is your keycard for room 405."
                self.memory_store["scenario_stage"] = 2
            elif any(w in lower for w in ("breakfast", "morning", "time", "wifi", "internet")):
                reply = "Complimentary breakfast is served in the main lounge from 7:00 to 10:00 AM, and high-speed Wi-Fi details are on your key sleeve."
                vocab_tips.append("'What is the Wi-Fi password?'")
            elif any(w in lower for w in ("luggage", "bag", "hold", "store", "checkout")):
                reply = "Certainly! We can securely hold your luggage in our storage room for as long as you need after checkout."
                vocab_tips.append("'Could you hold my bags for a few hours?'")
            else:
                reply = f"Welcome! {name_prefix}Please let our front desk team know if there is anything we can do to make your stay comfortable."

        elif sc == "business":
            if any(w in lower for w in ("meet you", "pleasure", "introduce", "morning", "afternoon")):
                reply = f"It's a pleasure to meet you as well, {name_prefix}! Thank you for joining us today. Let's begin our discussion."
                vocab_tips.append("'It's a pleasure to make your acquaintance.'")
                self.memory_store["scenario_stage"] = 1
            elif any(w in lower for w in ("experience", "project", "role", "work", "team")):
                reply = "That sounds like a very high-impact initiative. Could you highlight your specific strategy for managing project risks?"
                self.memory_store["scenario_stage"] = 2
            elif any(w in lower for w in ("strength", "skill", "leadership")):
                reply = "Thank you for that thorough explanation. Your structured communication style is clear, professional, and convincing."
            else:
                reply = "Thank you for sharing. Please continue and tell us more about your background and core technical strengths."

        else: # free_talk
            if any(w in lower for w in ("movie", "film", "watch", "anime", "series")):
                reply = "Movies are great! What's the best film you've seen recently? Do you prefer action, sci-fi, or drama?"
                vocab_tips.append("'I was on the edge of my seat' (Very exciting film)")
            elif any(w in lower for w in ("music", "song", "band", "listen")):
                reply = "What kind of music do you like to listen to when you're relaxing or working?"
            elif any(w in lower for w in ("food", "eat", "cook", "restaurant", "hungry")):
                reply = "Food is always a wonderful conversation topic! Do you enjoy cooking at home, or do you prefer dining out?"
                vocab_tips.append("'I have a sweet tooth' (I love desserts)")
            elif any(w in lower for w in ("travel", "trip", "visit", "japan", "tokyo")):
                reply = "Traveling is so enriching! Have you been to Japan before, or are you planning an upcoming trip?"
            elif any(w in lower for w in ("hello", "hi", "how are you", "good morning")):
                reply = f"Hello {name_prefix}! It's wonderful to speak with you today. What would you like to chat about?"
            elif any(w in lower for w in ("thank", "appreciate", "helpful")):
                reply = "You're very welcome! I'm happy to help. Feel free to keep chatting and practicing!"
            else:
                reply = f"That's really interesting! Could you tell me a little more about {text_clean[:20]}...?"

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
        """Query local Ollama instance with full multi-turn conversation memory."""
        sc_info = COACH_SCENARIOS.get(self.scenario, COACH_SCENARIOS["free_talk"])
        role_prompt = sc_info.get(f"role_{lang}", sc_info["role_ja"])

        system_prompt = (
            f"You are a friendly, encouraging AI Language Tutor helping the user master {('Japanese' if lang == 'ja' else 'English')}.\n"
            f"ROLE-PLAY SCENARIO: {sc_info['title']}\n"
            f"SCENARIO INSTRUCTION: {role_prompt}\n"
            "Maintain conversational context from previous turns. Continue the dialogue naturally in character while providing constructive corrections.\n"
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

        # Construct multi-turn messages array
        messages = [{"role": "system", "content": system_prompt}]
        for turn in self.conversation_history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": text})

        payload = {
            "model": self.ollama_model,
            "messages": messages,
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
        """Query external OpenAI-compatible API endpoint with full multi-turn conversation memory."""
        sc_info = COACH_SCENARIOS.get(self.scenario, COACH_SCENARIOS["free_talk"])
        role_prompt = sc_info.get(f"role_{lang}", sc_info["role_ja"])

        try:
            system_prompt = (
                f"You are an encouraging AI Language Tutor for {('Japanese' if lang == 'ja' else 'English')}. "
                f"Current scenario: {sc_info['title']}. Role instruction: {role_prompt}. "
                "Maintain conversational context from previous turns. Stay in character and output pure JSON: "
                "{\"reply\": \"...\", \"correction\": \"...\", \"is_natural\": bool, \"politeness\": \"...\", \"grammar_notes\": \"...\", \"vocabulary_tips\": [\"...\"]}"
            )
            messages = [{"role": "system", "content": system_prompt}]
            for turn in self.conversation_history[-6:]:
                messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({"role": "user", "content": text})

            payload = {
                "model": self.api_model,
                "messages": messages,
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

    def _query_groq_pool(self, text: str, lang: str) -> Optional[CoachingResult]:
        """Query Groq High-Speed LLM pool with key rotation and multi-turn context memory."""
        if not self.groq_keys:
            logger.warning("No Groq API keys available.")
            return None

        sc_info = COACH_SCENARIOS.get(self.scenario, COACH_SCENARIOS["free_talk"])
        role_prompt = sc_info.get(f"role_{lang}", sc_info["role_ja"])

        system_prompt = (
            f"You are an encouraging, highly skilled AI Language Tutor helping the user master {('Japanese' if lang == 'ja' else 'English')}.\n"
            f"ROLE-PLAY SCENARIO: {sc_info['title']}\n"
            f"SCENARIO INSTRUCTION: {role_prompt}\n"
            "Maintain conversational context from previous turns. Continue dialogue naturally in character while providing constructive grammar & politeness coaching.\n"
            "Respond ONLY with valid JSON in this exact structure:\n"
            "{\n"
            '  "reply": "In-character conversational reply in the practice language",\n'
            '  "correction": "Natural, corrected sentence (or exact user text if already natural)",\n'
            '  "is_natural": true or false,\n'
            '  "politeness": "Casual / Polite (丁寧語) / Honorific (敬語) / Formal",\n'
            '  "grammar_notes": "Concise English explanation of grammar, particles, or nuance",\n'
            '  "vocabulary_tips": ["Tip 1", "Tip 2"]\n'
            "}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        for turn in self.conversation_history[-8:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": text})

        payload = {
            "model": self.groq_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.4
        }
        encoded_data = json.dumps(payload).encode("utf-8")

        max_attempts = len(self.groq_keys)
        for attempt in range(max_attempts):
            cur_key = self.groq_keys[self.groq_key_index]
            masked_key = cur_key[:8] + "..." + cur_key[-4:] if len(cur_key) > 12 else "key"
            try:
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=encoded_data,
                    headers={
                        "Authorization": f"Bearer {cur_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    content = resp_data["choices"][0]["message"]["content"]
                    parsed = self._parse_llm_json(content)
                    is_nat = bool(parsed.get("is_natural", True))
                    corr = parsed.get("correction") or text
                    notes = parsed.get("grammar_notes") or ("Natural and fluent expression!" if is_nat else "Good practice!")
                    tips = parsed.get("vocabulary_tips") or []
                    if not isinstance(tips, list):
                        tips = [str(tips)]

                    return CoachingResult(
                        user_text=text,
                        practice_lang=lang,
                        reply_text=parsed.get("reply") or "Understood!",
                        reply_lang=lang,
                        suggested_correction=corr,
                        is_natural=is_nat,
                        politeness_level=parsed.get("politeness") or "Polite",
                        grammar_notes=notes,
                        vocabulary_tips=tips,
                        scenario_id=self.scenario
                    )
            except urllib.error.HTTPError as e:
                logger.warning(f"Groq API key {masked_key} error HTTP {e.code}. Rotating key...")
                self.groq_key_index = (self.groq_key_index + 1) % len(self.groq_keys)
            except Exception as e:
                logger.warning(f"Groq API query error with key {masked_key}: {e}. Rotating key...")
                self.groq_key_index = (self.groq_key_index + 1) % len(self.groq_keys)

        logger.warning("All Groq API keys in pool failed or exhausted.")
        return None

    def _query_gemini_pool(self, text: str, lang: str) -> Optional[CoachingResult]:
        """Query Google Gemini LLM pool with key rotation and multi-turn context memory."""
        if not self.gemini_keys:
            logger.warning("No Gemini API keys available.")
            return None

        sc_info = COACH_SCENARIOS.get(self.scenario, COACH_SCENARIOS["free_talk"])
        role_prompt = sc_info.get(f"role_{lang}", sc_info["role_ja"])

        prompt_lines = [
            f"You are an encouraging, expert AI Language Tutor helping the user master {('Japanese' if lang == 'ja' else 'English')}.",
            f"ROLE-PLAY SCENARIO: {sc_info['title']}",
            f"SCENARIO INSTRUCTION: {role_prompt}",
            "Maintain conversational context from previous turns. Stay in character.",
            "Respond ONLY with valid JSON with keys: reply, correction, is_natural, politeness, grammar_notes, vocabulary_tips.",
            "\n--- RECENT CONVERSATION CONTEXT ---"
        ]
        for turn in self.conversation_history[-8:]:
            prompt_lines.append(f"{turn['role'].upper()}: {turn['content']}")
        prompt_lines.append(f"USER: {text}")
        prompt_lines.append("\nOutput pure JSON matching the specified schema:")

        full_prompt = "\n".join(prompt_lines)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": full_prompt}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }
        encoded_data = json.dumps(payload).encode("utf-8")

        max_attempts = len(self.gemini_keys)
        for attempt in range(max_attempts):
            cur_key = self.gemini_keys[self.gemini_key_index]
            masked_key = cur_key[:8] + "..." + cur_key[-4:] if len(cur_key) > 12 else "key"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={cur_key}"
            try:
                req = urllib.request.Request(
                    url,
                    data=encoded_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                with urllib.request.urlopen(req, timeout=12.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = self._parse_llm_json(content)
                    is_nat = bool(parsed.get("is_natural", True))
                    corr = parsed.get("correction") or text
                    notes = parsed.get("grammar_notes") or ("Natural and fluent expression!" if is_nat else "Good practice!")
                    tips = parsed.get("vocabulary_tips") or []
                    if not isinstance(tips, list):
                        tips = [str(tips)]

                    return CoachingResult(
                        user_text=text,
                        practice_lang=lang,
                        reply_text=parsed.get("reply") or "Understood!",
                        reply_lang=lang,
                        suggested_correction=corr,
                        is_natural=is_nat,
                        politeness_level=parsed.get("politeness") or "Polite",
                        grammar_notes=notes,
                        vocabulary_tips=tips,
                        scenario_id=self.scenario
                    )
            except urllib.error.HTTPError as e:
                logger.warning(f"Gemini API key {masked_key} error HTTP {e.code}. Rotating key...")
                self.gemini_key_index = (self.gemini_key_index + 1) % len(self.gemini_keys)
            except Exception as e:
                logger.warning(f"Gemini API query error with key {masked_key}: {e}. Rotating key...")
                self.gemini_key_index = (self.gemini_key_index + 1) % len(self.gemini_keys)

        logger.warning("All Gemini API keys in pool failed or exhausted.")
        return None

    @staticmethod
    def _parse_llm_json(raw: str) -> Dict[str, Any]:
        """Safely parse LLM responses that may include code fences or leading commentary."""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        match = re.search(r'(\{[\s\S]*\})', raw)
        if match:
            raw = match.group(1)
        return json.loads(raw)
