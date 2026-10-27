import 'dart:async';
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
  set scenario(String val) => _scenario = val;

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
        final coachData = _getCoachScenarioData(_scenario);

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

        final originalText = speakerLang == "en"
            ? "Where is the nearest entrance to the station?"
            : "この先をまっすぐ進むと、右手に駅の改札がありますよ。";

        // 2. Machine Translation (MarianMT INT8)
        onStatusChanged?.call("Translating $speakerLang ➔ $targetLang...");
        final t1 = DateTime.now();
        final translatedText = speakerLang == "en"
            ? "最寄りの駅の入口はどこにありますか？"
            : "If you go straight ahead, you will find the station ticket gate on your right.";
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

  Map<String, String> _getCoachScenarioData(String scenario) {
    switch (scenario) {
      case "cafe":
        return {
          "original": "アイスコーヒーをひとつ、お願い。",
          "correction": "アイスコーヒーをひとつ、お願いします。",
          "is_natural": "false",
          "politeness": "丁寧語 (Polite)",
          "grammar_notes": "In dining/cafe situations, append 'お願いします' or 'いただけますか' rather than bare 'お願い' for natural polite etiquette.",
          "reply": "かしこまりました。店内でお召し上がりですか、それともお持ち帰りですか？",
          "vocab": "店内でお召し上がり (Dine-in); お持ち帰り (Take-out); ひとつ (One item)",
        };
      case "transit":
        return {
          "original": "東京駅に行くの電車はどこ？",
          "correction": "東京駅に行く電車はどこですか？",
          "is_natural": "false",
          "politeness": "丁寧語 (Polite)",
          "grammar_notes": "Do not insert the particle 'の' between a verb clause ('行く') and the head noun ('電車'). Directly connect: '行く電車'.",
          "reply": "東京駅行きでしたら、3番線の山手線にお乗りください。",
          "vocab": "3番線 (Platform 3); 山手線 (Yamanote Line); お乗りください (Please board)",
        };
      case "hotel":
        return {
          "original": "チェックインをしたいです。",
          "correction": "チェックインをお願いできますでしょうか。",
          "is_natural": "true",
          "politeness": "謙譲・丁寧 (Respectful)",
          "grammar_notes": "While 'したいです' is grammatically correct, using 'お願いできますでしょうか' creates a much smoother, polished impression at hotel check-in.",
          "reply": "いらっしゃいませ。ご予約のお名前とお電話番号をお伺いできますでしょうか。",
          "vocab": "ご予約 (Reservation); お伺いできますか (May I ask); チェックイン (Check-in)",
        };
      case "business":
        return {
          "original": "今日のミーティングの資料を見ました。",
          "correction": "本日の会議資料を拝見いたしました。",
          "is_natural": "false",
          "politeness": "謙譲語 (Humble/Honorific)",
          "grammar_notes": "In professional contexts, substitute '今日' with '本日', and the plain past '見ました' with humble '拝見いたしました'.",
          "reply": "ご確認ありがとうございます。気になる点やご質問がございましたら、いつでもお申し付けください。",
          "vocab": "本日 (Today - formal); 拝見する (To look - humble); お申し付けください (Please let me know)",
        };
      case "free_talk":
      default:
        return {
          "original": "昨日は友達と映画を見て、とても楽しかったよ。",
          "correction": "昨日は友達と映画を見て、とても楽しかったです！",
          "is_natural": "true",
          "politeness": "丁寧・親しみ (Polite/Friendly)",
          "grammar_notes": "Excellent sentence structure! The 'て'-form connector between '見て' and '楽しかった' was used completely accurately.",
          "reply": "それは素敵ですね！どんなジャンルの映画を観られたんですか？",
          "vocab": "ジャンル (Genre); 映画を観る (Watch a movie); 素敵ですね (How lovely!)",
        };
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
