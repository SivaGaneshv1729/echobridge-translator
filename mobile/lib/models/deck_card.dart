/// Data model representing a saved language practice flashcard.
class DeckCard {
  final String id;
  final String originalText;
  final String suggestedCorrection;
  final String grammarNotes;
  final List<String> vocabularyTips;
  final String politenessLevel;
  final String scenarioId;
  bool mastered;
  int reviewCount;
  final DateTime createdAt;

  DeckCard({
    required this.id,
    required this.originalText,
    required this.suggestedCorrection,
    this.grammarNotes = '',
    this.vocabularyTips = const [],
    this.politenessLevel = '',
    this.scenarioId = 'free_talk',
    this.mastered = false,
    this.reviewCount = 0,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
        'id': id,
        'original_text': originalText,
        'suggested_correction': suggestedCorrection,
        'grammar_notes': grammarNotes,
        'vocabulary_tips': vocabularyTips,
        'politeness_level': politenessLevel,
        'scenario_id': scenarioId,
        'mastered': mastered,
        'review_count': reviewCount,
        'created_at': createdAt.toIso8601String(),
      };

  factory DeckCard.fromJson(Map<String, dynamic> json) => DeckCard(
        id: json['id'] as String? ?? 'card_${DateTime.now().millisecondsSinceEpoch}',
        originalText: json['original_text'] as String? ?? '',
        suggestedCorrection: json['suggested_correction'] as String? ?? '',
        grammarNotes: json['grammar_notes'] as String? ?? '',
        vocabularyTips: (json['vocabulary_tips'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
        politenessLevel: json['politeness_level'] as String? ?? '',
        scenarioId: json['scenario_id'] as String? ?? 'free_talk',
        mastered: json['mastered'] as bool? ?? false,
        reviewCount: json['review_count'] as int? ?? 0,
        createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at']) : null,
      );
}
