import 'dart:convert';
import 'package:flutter/foundation.dart';
import '../models/deck_card.dart';
import '../models/conversation_turn.dart';

/// Singleton manager for mobile practice flashcards and vocabulary deck.
class DeckService {
  static final DeckService _instance = DeckService._internal();
  factory DeckService() => _instance;

  final List<DeckCard> _cards = [];
  List<DeckCard> get cards => List.unmodifiable(_cards);

  DeckService._internal() {
    _seedDefaultCards();
  }

  void _seedDefaultCards() {
    if (_cards.isNotEmpty) return;
    _cards.addAll([
      DeckCard(
        id: "seed_1",
        originalText: "アイスコーヒーをひとつ、お願い。",
        suggestedCorrection: "アイスコーヒーをひとつ、お願いします。",
        grammarNotes: "In cafes, append お願いします to be natural and polite to service staff.",
        vocabularyTips: ["ひとつ (One item)", "店内でお召し上がり (Dine-in)"],
        politenessLevel: "丁寧語 (Polite)",
        scenarioId: "cafe",
      ),
      DeckCard(
        id: "seed_2",
        originalText: "東京駅に行くの電車はどこ？",
        suggestedCorrection: "東京駅に行く電車はどこですか？",
        grammarNotes: "Do not put の between a verb modifier clause (行く) and the noun (電車).",
        vocabularyTips: ["行く電車 (Train heading to...)", "山手線 (Yamanote Line)"],
        politenessLevel: "丁寧語 (Polite)",
        scenarioId: "transit",
      ),
      DeckCard(
        id: "seed_3",
        originalText: "チェックインをしたいです。",
        suggestedCorrection: "チェックインをお願いできますでしょうか。",
        grammarNotes: "Creates a much more polite and refined impression at hotel reception.",
        vocabularyTips: ["ご予約 (Reservation)", "チェックイン (Check-in)"],
        politenessLevel: "謙譲・丁寧 (Respectful)",
        scenarioId: "hotel",
      ),
      DeckCard(
        id: "seed_4",
        originalText: "今日のミーティングの資料を見ました。",
        suggestedCorrection: "本日の会議資料を拝見いたしました。",
        grammarNotes: "In business meetings, use humble forms: 本日 and 拝見いたしました.",
        vocabularyTips: ["本日 (Today - formal)", "拝見する (To look - humble)"],
        politenessLevel: "謙譲語 (Humble)",
        scenarioId: "business",
      ),
      DeckCard(
        id: "seed_5",
        originalText: "昨日は友達と映画を見て、とても楽しかったよ。",
        suggestedCorrection: "昨日は友達と映画を見て、とても楽しかったです！",
        grammarNotes: "Great sentence! Connecting clauses with て-form is used completely accurately.",
        vocabularyTips: ["映画を観る (Watch a movie)", "楽しかったです (Was fun!)"],
        politenessLevel: "丁寧・親しみ (Polite)",
        scenarioId: "free_talk",
      ),
    ]);
  }

  DeckCard addCard({
    required String originalText,
    required String suggestedCorrection,
    String grammarNotes = '',
    List<String> vocabularyTips = const [],
    String politenessLevel = '',
    String scenarioId = 'free_talk',
  }) {
    for (final c in _cards) {
      if (c.originalText == originalText && c.suggestedCorrection == suggestedCorrection) {
        return c;
      }
    }

    final card = DeckCard(
      id: "card_${DateTime.now().millisecondsSinceEpoch}",
      originalText: originalText,
      suggestedCorrection: suggestedCorrection,
      grammarNotes: grammarNotes,
      vocabularyTips: vocabularyTips,
      politenessLevel: politenessLevel,
      scenarioId: scenarioId,
    );
    _cards.insert(0, card);
    return card;
  }

  DeckCard addFromTurn(ConversationTurn turn) {
    return addCard(
      originalText: turn.originalText,
      suggestedCorrection: turn.suggestedCorrection.isNotEmpty ? turn.suggestedCorrection : turn.originalText,
      grammarNotes: turn.grammarNotes,
      vocabularyTips: turn.vocabularyTips,
      politenessLevel: turn.politenessLevel,
      scenarioId: turn.scenarioId,
    );
  }

  void removeCard(String id) {
    _cards.removeWhere((c) => c.id == id);
  }

  void toggleMastered(String id, bool mastered) {
    for (final c in _cards) {
      if (c.id == id) {
        c.mastered = mastered;
        c.reviewCount++;
        break;
      }
    }
  }

  int get totalCount => _cards.length;
  int get masteredCount => _cards.where((c) => c.mastered).length;
}
