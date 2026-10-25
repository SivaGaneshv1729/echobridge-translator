/// Conversation Turn model representing a single spoken utterance and its translation.
class ConversationTurn {
  final int id;
  final DateTime timestamp;
  final String speakerLang; // 'en' or 'ja'
  final String targetLang;  // 'ja' or 'en'
  final String originalText;
  final String translatedText;
  final double sttLatencyMs;
  final double mtLatencyMs;
  final double ttsLatencyMs;
  final double totalLatencyMs;

  ConversationTurn({
    required this.id,
    required this.timestamp,
    required this.speakerLang,
    required this.targetLang,
    required this.originalText,
    required this.translatedText,
    required this.sttLatencyMs,
    required this.mtLatencyMs,
    required this.ttsLatencyMs,
    required this.totalLatencyMs,
  });

  bool get isEnglishSpeaker => speakerLang == 'en';
}
