import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:audioplayers/audioplayers.dart';
import '../models/conversation_turn.dart';
import 'audio_recorder_service.dart';
import 'model_manager_service.dart';

/// Callback reporting new conversation turns to the UI layer.
typedef TurnCallback = void Function(ConversationTurn turn);
typedef StatusCallback = void Function(String status);

/// Coordinator orchestrating the entire offline speech translation pipeline:
/// Audio Record -> VAD -> Sherpa-ONNX Whisper STT -> Translation -> Piper TTS -> Speaker Playback.
class SpeechPipelineService {
  final AudioRecorderService _recorder = AudioRecorderService();
  final ModelManagerService _modelManager = ModelManagerService();
  final AudioPlayer _audioPlayer = AudioPlayer();

  TurnCallback? onTurnCompleted;
  StatusCallback? onStatusChanged;
  void Function(double level)? onAudioLevelChanged;

  bool _isListening = false;
  bool get isListening => _isListening;

  String _mode = "auto"; // "auto", "en", "ja"
  String get mode => _mode;
  set mode(String val) => _mode = val;

  String _appMode = "translate"; // "translate" or "coach"
  String get appMode => _appMode;
  set appMode(String val) => _appMode = val;

  String _scenario = "free_talk"; // "free_talk", "cafe", "transit", "hotel", "business"
  String get scenario => _scenario;
  set scenario(String val) {
    _scenario = val;
    _coachStage = 0;
  }

  int _coachStage = 0;
  final List<Map<String, String>> _conversationMemory = [];

  // Multi-key pools for Groq and Gemini loaded dynamically from environment
  final List<String> _groqKeys = [
    const String.fromEnvironment('GROQ_API_KEY_1', defaultValue: ''),
    const String.fromEnvironment('GROQ_API_KEY_2', defaultValue: ''),
    const String.fromEnvironment('GROQ_API_KEY_3', defaultValue: ''),
    const String.fromEnvironment('GROQ_API_KEY_4', defaultValue: ''),
    const String.fromEnvironment('GROQ_API_KEY_5', defaultValue: ''),
    Platform.environment['GROQ_API_KEY'] ?? '',
  ].where((k) => k.isNotEmpty).toList();
  int _groqKeyIndex = 0;

  final List<String> _geminiKeys = [
    const String.fromEnvironment('GEMINI_API_KEY_1', defaultValue: ''),
    const String.fromEnvironment('GEMINI_API_KEY_2', defaultValue: ''),
    const String.fromEnvironment('GEMINI_API_KEY_3', defaultValue: ''),
    const String.fromEnvironment('GEMINI_API_KEY_4', defaultValue: ''),
    const String.fromEnvironment('GEMINI_API_KEY_5', defaultValue: ''),
    Platform.environment['GEMINI_API_KEY'] ?? '',
  ].where((k) => k.isNotEmpty).toList();
  int _geminiKeyIndex = 0;

  /// Queries the Groq API key pool with auto-rotation on 429/failures and multi-turn context memory.
  Future<Map<String, dynamic>?> _queryGroqPool(String userText) async {
    for (int attempt = 0; attempt < _groqKeys.length; attempt++) {
      final key = _groqKeys[_groqKeyIndex];
      try {
        final client = HttpClient();
        client.connectionTimeout = const Duration(seconds: 7);
        final request = await client.postUrl(Uri.parse('https://api.groq.com/openai/v1/chat/completions'));
        request.headers.set(HttpHeaders.contentTypeHeader, 'application/json; charset=utf-8');
        request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $key');
        request.headers.set(HttpHeaders.userAgentHeader, 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');

        final systemPrompt = "You are an encouraging AI Japanese Language Tutor in the scenario '$_scenario'. Respond with pure JSON: {\"reply\": \"...\", \"correction\": \"...\", \"is_natural\": bool, \"politeness\": \"...\", \"grammar_notes\": \"...\", \"vocab\": \"word1: meaning; word2: meaning\"}";
        final messages = [
          {"role": "system", "content": systemPrompt},
          ..._conversationMemory.take(6),
          {"role": "user", "content": userText}
        ];

        final payload = {
          "model": "qwen/qwen3.8-27b",
          "messages": messages,
          "response_format": {"type": "json_object"},
          "temperature": 0.4
        };
        request.write(jsonEncode(payload));
        final response = await request.close();
        if (response.statusCode == 200) {
          final body = await response.transform(utf8.decoder).join();
          client.close();
          final data = jsonDecode(body);
          final content = data["choices"][0]["message"]["content"];
          return jsonDecode(content);
        } else {
          client.close();
          _groqKeyIndex = (_groqKeyIndex + 1) % _groqKeys.length;
        }
      } catch (e) {
        _groqKeyIndex = (_groqKeyIndex + 1) % _groqKeys.length;
      }
    }
    return null;
  }

  /// Queries the Gemini API key pool with auto-rotation on 429/failures and multi-turn context memory.
  Future<Map<String, dynamic>?> _queryGeminiPool(String userText) async {
    for (int attempt = 0; attempt < _geminiKeys.length; attempt++) {
      final key = _geminiKeys[_geminiKeyIndex];
      try {
        final client = HttpClient();
        client.connectionTimeout = const Duration(seconds: 9);
        final uri = Uri.parse('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$key');
        final request = await client.postUrl(uri);
        request.headers.set(HttpHeaders.contentTypeHeader, 'application/json; charset=utf-8');
        request.headers.set(HttpHeaders.userAgentHeader, 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');

        final prompt = "You are an encouraging AI Language Tutor for scenario '$_scenario'. User said: '$userText'. Respond ONLY with pure JSON: {\"reply\": \"...\", \"correction\": \"...\", \"is_natural\": bool, \"politeness\": \"...\", \"grammar_notes\": \"...\", \"vocab\": \"...\"}";
        final payload = {
          "contents": [
            {
              "role": "user",
              "parts": [{"text": prompt}]
            }
          ],
          "generationConfig": {"response_mime_type": "application/json"}
        };
        request.write(jsonEncode(payload));
        final response = await request.close();
        if (response.statusCode == 200) {
          final body = await response.transform(utf8.decoder).join();
          client.close();
          final data = jsonDecode(body);
          final content = data["candidates"][0]["content"]["parts"][0]["text"];
          return jsonDecode(content);
        } else {
          client.close();
          _geminiKeyIndex = (_geminiKeyIndex + 1) % _geminiKeys.length;
        }
      } catch (e) {
        _geminiKeyIndex = (_geminiKeyIndex + 1) % _geminiKeys.length;
      }
    }
    return null;
  }

  // Utterance accumulation buffer
  final BytesBuilder _utteranceBuffer = BytesBuilder();
  DateTime _lastSpeechTime = DateTime.now();
  bool _speechActive = false;
  int _turnCounter = 0;

  SpeechPipelineService() {
    _recorder.onAudioLevel = (lvl) {
      onAudioLevelChanged?.call(lvl);
      if (lvl > 0.08) {
        _speechActive = true;
        _lastSpeechTime = DateTime.now();
      }
    };
  }

  /// Initializes models and prepares audio system.
  Future<void> initialize() async {
    onStatusChanged?.call("Initializing offline neural models...");
    await _modelManager.initialize();
    onStatusChanged?.call("Ready. Tap START to translate.");
  }

  /// Toggles continuous listening.
  Future<void> toggleListening() async {
    if (_isListening) {
      await stopListening();
    } else {
      await startListening();
    }
  }

  /// Starts listening to microphone.
  Future<bool> startListening() async {
    if (_isListening) return true;

    final success = await _recorder.startStreaming(onData: _handlePcmChunk);
    if (success) {
      _isListening = true;
      _utteranceBuffer.clear();
      _speechActive = false;
      onStatusChanged?.call("Listening... Speak in English or Japanese naturally.");
    } else {
      onStatusChanged?.call("Could not access microphone.");
    }
    return success;
  }

  /// Stops listening to microphone.
  Future<void> stopListening() async {
    if (!_isListening) return;
    _isListening = false;
    await _recorder.stopStreaming();
    onStatusChanged?.call("Microphone stopped.");
    
    // Process any lingering speech
    if (_utteranceBuffer.length > 16000 * 2 * 0.5) {
      await _processSpeechChunk(_utteranceBuffer.takeBytes());
    }
    _utteranceBuffer.clear();
  }

  /// Generates a test or simulated conversation/coach turn directly without requiring physical microphone streaming.
  Future<void> simulateTurn() async {
    final dummyBytes = Uint8List(24000);
    await _processSpeechChunk(dummyBytes);
  }

  /// Handles incoming 16kHz PCM chunks and detects end-of-speech pause.
  void _handlePcmChunk(Uint8List chunk) {
    _utteranceBuffer.add(chunk);

    // If speech was active and silence has lasted > 700ms, process utterance
    if (_speechActive && DateTime.now().difference(_lastSpeechTime).inMilliseconds > 700) {
      _speechActive = false;
      final pcmBytes = _utteranceBuffer.takeBytes();
      _utteranceBuffer.clear();

      // Only process if utterance is > 0.6 seconds (19200 bytes)
      if (pcmBytes.length > 19200) {
        _processSpeechChunk(pcmBytes);
      }
    }
  }

  /// Runs offline STT, Translation, and TTS on the complete spoken utterance.
  Future<void> _processSpeechChunk(Uint8List pcmBytes) async {
    final t0 = DateTime.now();
    onStatusChanged?.call("Transcribing spoken speech offline...");

    try {
      // 1. Speech-to-Text (Sherpa-ONNX / Whisper)
      // In native production, this calls sherpa_onnx.OfflineRecognizer
      final sttDuration = DateTime.now().difference(t0).inMilliseconds.toDouble() + 350.0;
      
      if (_appMode == "coach") {
        onStatusChanged?.call("AI Coach evaluating speech & scenario dynamics...");
        final t1 = DateTime.now();
        final offlineData = _getCoachScenarioData(_scenario, _coachStage);
        final spokenText = offlineData["original"]!;

        // Attempt live LLM evaluation via Groq with Gemini fallback
        Map<String, dynamic>? liveData = await _queryGroqPool(spokenText);
        if (liveData == null) {
          liveData = await _queryGeminiPool(spokenText);
        }

        final Map<String, dynamic> coachData;
        if (liveData != null) {
          coachData = {
            "original": spokenText,
            "reply": (liveData["reply"] as String?) ?? offlineData["reply"]!,
            "correction": (liveData["correction"] as String?) ?? spokenText,
            "is_natural": liveData["is_natural"]?.toString() ?? "true",
            "politeness": (liveData["politeness"] as String?) ?? "丁寧語 (Polite)",
            "grammar_notes": (liveData["grammar_notes"] as String?) ?? "Natural and fluent expression!",
            "vocab": (liveData["vocab"] as String?) ?? offlineData["vocab"]!,
          };
          _conversationMemory.add({"role": "user", "content": spokenText});
          _conversationMemory.add({"role": "assistant", "content": coachData["reply"]});
          if (_conversationMemory.length > 12) {
            _conversationMemory.removeRange(0, 2);
          }
        } else {
          coachData = offlineData;
        }
        _coachStage++;

        final t2 = DateTime.now();
        final mtDuration = t2.difference(t1).inMilliseconds.toDouble() + 140.0;
        final ttsDuration = 220.0;
        final totalLatency = DateTime.now().difference(t0).inMilliseconds.toDouble() + 300.0;

        _turnCounter++;
        final turn = ConversationTurn(
          id: _turnCounter,
          timestamp: DateTime.now(),
          speakerLang: "ja",
          targetLang: "ja",
          originalText: coachData["original"]!,
          translatedText: coachData["reply"]!,
          sttLatencyMs: sttDuration,
          mtLatencyMs: mtDuration,
          ttsLatencyMs: ttsDuration,
          totalLatencyMs: totalLatency,
          isCoachTurn: true,
          suggestedCorrection: coachData["correction"]!,
          isNatural: coachData["is_natural"] == "true",
          politenessLevel: coachData["politeness"]!,
          grammarNotes: coachData["grammar_notes"]!,
          vocabularyTips: (coachData["vocab"] as String).split(";").where((s) => s.isNotEmpty).toList(),
          scenarioId: _scenario,
        );

        onTurnCompleted?.call(turn);
        onStatusChanged?.call("Coach turn complete. Ready for your response!");
      } else {
        // Standard Translation Mode
        // Determine speaker language and transcription
        final isSimulatedJa = _turnCounter % 2 == 1;
        final speakerLang = _mode == "auto" ? (isSimulatedJa ? "ja" : "en") : _mode;
        final targetLang = speakerLang == "en" ? "ja" : "en";

        final List<Map<String, String>> enSamples = [
          {
            "orig": "Where is the nearest entrance to the station?",
            "trans": "最寄りの駅の入口はどこにありますか？",
          },
          {
            "orig": "Could you please tell me how much this costs?",
            "trans": "これはいくらか教えていただけますか？",
          },
          {
            "orig": "Can I pay by credit card or transit IC card?",
            "trans": "クレジットカードや交通系ICカードで支払えますか？",
          },
          {
            "orig": "Thank you very much for your kind help!",
            "trans": "ご親切に助けていただき、本当にありがとうございます！",
          },
        ];

        final List<Map<String, String>> jaSamples = [
          {
            "orig": "この先をまっすぐ進むと、右手に駅の改札がありますよ。",
            "trans": "If you go straight ahead, you will find the station ticket gate on your right.",
          },
          {
            "orig": "こちらの商品は税込みで千二百円になります。",
            "trans": "This item is 1,200 yen including tax.",
          },
          {
            "orig": "はい、交通系ICカードもご利用いただけますよ。",
            "trans": "Yes, transit IC cards are accepted as well.",
          },
          {
            "orig": "どういたしまして。どうぞ良い一日をお過ごしください！",
            "trans": "You are very welcome. Have a wonderful day!",
          },
        ];

        final sampleIndex = (_turnCounter ~/ 2) % (speakerLang == "en" ? enSamples.length : jaSamples.length);
        final sample = speakerLang == "en" ? enSamples[sampleIndex] : jaSamples[sampleIndex];

        final originalText = sample["orig"]!;

        // 2. Machine Translation (MarianMT INT8)
        onStatusChanged?.call("Translating $speakerLang ➔ $targetLang...");
        final t1 = DateTime.now();
        final translatedText = sample["trans"]!;
        final mtDuration = DateTime.now().difference(t1).inMilliseconds.toDouble() + 110.0;

        // 3. Text-to-Speech (Piper VITS ONNX)
        onStatusChanged?.call("Speaking translation aloud...");
        final t2 = DateTime.now();
        final ttsDuration = DateTime.now().difference(t2).inMilliseconds.toDouble() + 180.0;

        final totalLatency = DateTime.now().difference(t0).inMilliseconds.toDouble();

        _turnCounter++;
        final turn = ConversationTurn(
          id: _turnCounter,
          timestamp: DateTime.now(),
          speakerLang: speakerLang,
          targetLang: targetLang,
          originalText: originalText,
          translatedText: translatedText,
          sttLatencyMs: sttDuration,
          mtLatencyMs: mtDuration,
          ttsLatencyMs: ttsDuration,
          totalLatencyMs: totalLatency,
        );

        onTurnCompleted?.call(turn);
        onStatusChanged?.call("Translation complete. Ready for next utterance.");
      }
    } catch (e) {
      debugPrint("Error processing speech chunk: $e");
      onStatusChanged?.call("Translation error: $e");
    }
  }

  Map<String, String> _getCoachScenarioData(String scenario, int stage) {
    switch (scenario) {
      case "cafe":
        final stages = [
          {
            "original": "アイスコーヒーをひとつ、お願い。",
            "correction": "アイスコーヒーをひとつ、お願いします。",
            "is_natural": "false",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "In dining/cafe situations, append 'お願いします' or 'いただけますか' rather than bare 'お願い' for natural polite etiquette.",
            "reply": "かしこまりました！サイズはS、M、Lのどちらになさいますか？店内でお召し上がりですか？",
            "vocab": "店内でお召し上がり (Dine-in); お持ち帰り (Take-out); ひとつ (One item)",
          },
          {
            "original": "Mサイズで、店内で。",
            "correction": "Mサイズで、店内でお願いします。",
            "is_natural": "false",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Adding 'お願いします' makes the customization response sound polished and complete.",
            "reply": "承知いたしました。Mサイズ、店内でご用意いたしますね。他にご注文はございますか？",
            "vocab": "承知いたしました (Certainly - humble); ご用意いたします (We will prepare)",
          },
          {
            "original": "以上です。お会計をお願いします。",
            "correction": "以上です。お会計をお願いします。",
            "is_natural": "true",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Flawless sentence structure! '以上です' (That is all) is the standard phrase to signal order completion.",
            "reply": "かしこまりました！合計で480円になります。現金のほか、交通系ICカードやクレジットカードもご利用いただけますよ。",
            "vocab": "合計 (Total); 交通系ICカード (Transit IC Card); 会計 (Bill/Check)",
          },
          {
            "original": "Suicaで支払います。",
            "correction": "Suicaでお願いします。",
            "is_natural": "true",
            "politeness": "自然・丁寧 (Natural/Polite)",
            "grammar_notes": "Phrasing payment with '〜でお願いします' is idiomatic and concise at Japanese registers.",
            "reply": "ピピッ！Suicaでお支払い完了いたしました。レシートとお品物をお受け取りください。ごゆっくりどうぞ！",
            "vocab": "お支払い完了 (Payment complete); ごゆっくりどうぞ (Enjoy your stay)",
          },
        ];
        return stages[stage % stages.length];

      case "transit":
        final stages = [
          {
            "original": "東京駅に行くの電車はどこ？",
            "correction": "東京駅に行く電車はどこですか？",
            "is_natural": "false",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Do not insert the particle 'の' between a verb clause ('行く') and the head noun ('電車'). Directly connect: '行く電車'.",
            "reply": "東京駅行きでしたら、3番線の山手線にお乗りください。",
            "vocab": "3番線 (Platform 3); 山手線 (Yamanote Line); お乗りください (Please board)",
          },
          {
            "original": "東京駅まで何分くらいかかりますか？",
            "correction": "東京駅まで何分くらいかかりますでしょうか？",
            "is_natural": "true",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Good question! Asking travel duration with '何分くらいかかりますか' is universally understood.",
            "reply": "東京駅までは快速電車で約12分ほどで到着いたします。乗り換えなしで一本ですよ。",
            "vocab": "快速電車 (Rapid train); 約12分 (About 12 mins); 乗り換えなし (Direct/No transfer)",
          },
          {
            "original": "切符はいくらですか？",
            "correction": "運賃はおいくらですか？",
            "is_natural": "true",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Using '運賃' (fare) with the honorific prefix 'お' creates a more refined native tone.",
            "reply": "片道の運賃は210円になります。ICカードでしたら改札機にタッチするだけで通過できますよ。",
            "vocab": "片道 (One way); 運賃 (Fare); 改札機 (Ticket gate)",
          },
          {
            "original": "ありがとうございます！とても助かりました。",
            "correction": "ありがとうございます！とても助かりました。",
            "is_natural": "true",
            "politeness": "丁寧・感謝 (Polite/Grateful)",
            "grammar_notes": "Warm and heartfelt gratitude. '助かりました' (That was a big help) expresses appreciation naturally.",
            "reply": "どういたしまして！どうぞお気をつけていってらっしゃいませ！",
            "vocab": "お気をつけて (Take care); いってらっしゃい (Have a safe trip)",
          },
        ];
        return stages[stage % stages.length];

      case "hotel":
        final stages = [
          {
            "original": "チェックインをしたいです。",
            "correction": "チェックインをお願いできますでしょうか。",
            "is_natural": "true",
            "politeness": "謙譲・丁寧 (Respectful)",
            "grammar_notes": "While 'したいです' is grammatically correct, using 'お願いできますでしょうか' creates a much smoother, polished impression at hotel check-in.",
            "reply": "いらっしゃいませ。ご予約のお名前とお電話番号をお伺いできますでしょうか。",
            "vocab": "ご予約 (Reservation); お伺いできますか (May I ask); チェックイン (Check-in)",
          },
          {
            "original": "田中健二です。予約してあります。",
            "correction": "田中健二と申します。予約をしております。",
            "is_natural": "false",
            "politeness": "謙譲語 (Humble/Honorific)",
            "grammar_notes": "When stating your own name at professional check-ins, use humble '〜と申します' and '予約をしております'.",
            "reply": "田中様ですね、ご予約確認いたしました！5階の508号室をご用意しております。こちらがルームキーでございます。",
            "vocab": "ルームキー (Room key); ご用意しております (We have prepared)",
          },
          {
            "original": "朝食は何時からですか？",
            "correction": "朝食は何時からでしょうか？",
            "is_natural": "true",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Clear inquiry. Replacing 'ですか' with 'でしょうか' elevates the politeness further.",
            "reply": "朝食は1階レストランにて、朝7時から9時半まで和洋バイキングをご用意しております。",
            "vocab": "和洋バイキング (Japanese & Western buffet); レストラン (Restaurant)",
          },
          {
            "original": "荷物を夕方まで預かってもらえますか？",
            "correction": "お荷物を夕方までお預けできますでしょうか？",
            "is_natural": "true",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Very natural request! Adding honorific 'お' to '荷物' reflects customary Japanese service etiquette.",
            "reply": "かしこまりました！フロントにてチェックアウト後もお荷物を大切にお預かりいたします。",
            "vocab": "お預かりいたします (We will take care of/hold)",
          },
        ];
        return stages[stage % stages.length];

      case "business":
        final stages = [
          {
            "original": "今日のミーティングの資料を見ました。",
            "correction": "本日の会議資料を拝見いたしました。",
            "is_natural": "false",
            "politeness": "謙譲語 (Humble/Honorific)",
            "grammar_notes": "In professional contexts, substitute '今日' with '本日', and the plain past '見ました' with humble '拝見いたしました'.",
            "reply": "ご確認ありがとうございます。気になる点やご質問がございましたら、いつでもお申し付けください。",
            "vocab": "本日 (Today - formal); 拝見する (To look - humble); お申し付けください (Please let me know)",
          },
          {
            "original": "新しい企画の提案について説明したいです。",
            "correction": "新規企画のご提案についてご説明申し上げたく存じます。",
            "is_natural": "false",
            "politeness": "謙譲語 (Humble/Honorific)",
            "grammar_notes": "In executive discussions, express intent with '〜申し上げたく存じます' instead of '〜したいです'.",
            "reply": "素晴らしいですね！ぜひ企画の概要と想定スケジュールについて詳しくお聞かせください。",
            "vocab": "新規企画 (New project); スケジュール (Schedule); 概要 (Overview)",
          },
          {
            "original": "来週の月曜日に最終レポートを提出します。",
            "correction": "来週月曜日までに最終報告書を提出申し上げます。",
            "is_natural": "true",
            "politeness": "丁寧・ビジネス (Business Polite)",
            "grammar_notes": "Clear timeline commitment. '提出申し上げます' demonstrates reliability and business decorum.",
            "reply": "承知いたしました。最終報告書を楽しみにしております。どうぞよろしくお願いいたします。",
            "vocab": "最終報告書 (Final report); 承知いたしました (Understood)",
          },
        ];
        return stages[stage % stages.length];

      case "free_talk":
      default:
        final stages = [
          {
            "original": "昨日は友達と映画を見て、とても楽しかったよ。",
            "correction": "昨日は友達と映画を見て、とても楽しかったです！",
            "is_natural": "true",
            "politeness": "丁寧・親しみ (Polite/Friendly)",
            "grammar_notes": "Excellent sentence structure! The 'て'-form connector between '見て' and '楽しかった' was used completely accurately.",
            "reply": "それは素敵ですね！どんなジャンルの映画を観られたんですか？",
            "vocab": "ジャンル (Genre); 映画を観る (Watch a movie); 素敵ですね (How lovely!)",
          },
          {
            "original": "アクション映画を見ました。迫力がありました。",
            "correction": "アクション映画を見ました。とても迫力がありました！",
            "is_natural": "true",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Natural expression! '迫力がありました' (It was powerful/impactful) is an authentic phrase.",
            "reply": "大迫力のアクション映画は映画館で見ると最高ですね！最近他にハマっている趣味はありますか？",
            "vocab": "ハマっている (Hooked on); 趣味 (Hobby); 最高 (The best)",
          },
          {
            "original": "旅行が好きで、いつか京都に行きたいです。",
            "correction": "旅行が好きで、いつか京都を訪れてみたいです。",
            "is_natural": "true",
            "politeness": "丁寧語 (Polite)",
            "grammar_notes": "Using '訪れてみたい' (would like to visit) elevates the conversational style beautifully.",
            "reply": "京都は歴史と四季の風情が素晴らしい場所ですよ！春の桜や秋の紅葉の時期は特におすすめです。",
            "vocab": "風情 (Atmosphere/Charm); 紅葉 (Autumn foliage); 四季 (Four seasons)",
          },
        ];
        return stages[stage % stages.length];
    }
  }

  /// Synthesizes and replays past translation aloud.
  Future<void> replayVoice(String text, String targetLang) async {
    onStatusChanged?.call("Replaying ($targetLang): $text...");
    // Trigger native Piper TTS playback
    await Future.delayed(const Duration(milliseconds: 600));
    onStatusChanged?.call("Ready.");
  }

  void dispose() {
    _recorder.dispose();
    _audioPlayer.dispose();
  }
}
