import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/conversation_turn.dart';
import '../../services/deck_service.dart';

/// Modern conversational AI Language Coach card displaying user speech,
/// grammatical feedback, natural corrections, and the coach's spoken conversational reply.
class CoachingBubbleWidget extends StatelessWidget {
  final ConversationTurn turn;
  final VoidCallback onReplay;

  const CoachingBubbleWidget({
    Key? key,
    required this.turn,
    required this.onReplay,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    const cardBorder = Color(0xFF6366F1);
    const cardBg = Color(0xFF0F111A);

    final timeStr = "${turn.timestamp.hour.toString().padLeft(2, '0')}:${turn.timestamp.minute.toString().padLeft(2, '0')}:${turn.timestamp.second.toString().padLeft(2, '0')}";
    final isNatural = turn.isNatural;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: cardBorder, width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.35),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row: Avatar, Politeness, Fluency, and Latency Pill
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 6,
            runSpacing: 6,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF312E81),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFF4F46E5), width: 0.8),
                ),
                child: const Text(
                  "🎓 AI Language Coach",
                  style: TextStyle(
                    color: Color(0xFFC7D2FE),
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF1E293B),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFF334155)),
                ),
                child: Text(
                  turn.targetLang == "ja" ? "🇯🇵 JA Practice" : "🇺🇸 EN Practice",
                  style: const TextStyle(color: Color(0xFFA5B4FC), fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF1E1B4B),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFF4338CA)),
                ),
                child: Text(
                  _scenarioTitle(turn.scenarioId),
                  style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
              if (turn.politenessLevel.isNotEmpty)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFF334155)),
                  ),
                  child: Text(
                    turn.politenessLevel,
                    style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: isNatural ? const Color(0xFF064E3B) : const Color(0xFF451A03),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: isNatural ? const Color(0xFF059669) : const Color(0xFFD97706)),
                ),
                child: Text(
                  isNatural ? "✓ Natural & Fluent" : "⚡ Grammar Tip",
                  style: TextStyle(
                    color: isNatural ? const Color(0xFF34D399) : const Color(0xFFFBBF24),
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Text(
                timeStr,
                style: const TextStyle(color: Color(0xFF64748B), fontSize: 11),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF111827),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF1F2937)),
                ),
                child: Text(
                  "⚡ ${turn.totalLatencyMs.toStringAsFixed(0)} ms",
                  style: const TextStyle(
                    color: Color(0xFF38BDF8),
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // User Spoken Words
          const Text(
            "WHAT YOU SAID",
            style: TextStyle(color: Color(0xFF94A3B8), fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.5),
          ),
          const SizedBox(height: 3),
          SelectableText(
            turn.originalText,
            style: const TextStyle(color: Color(0xFFF1F5F9), fontSize: 15, fontWeight: FontWeight.w500, height: 1.4),
          ),

          // Suggested Phrasing Box (if not natural or correction exists)
          if (turn.suggestedCorrection.isNotEmpty && (!isNatural || turn.suggestedCorrection != turn.originalText)) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF1E1B4B),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF4338CA)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "✨ MORE NATURAL PHRASING:",
                    style: TextStyle(color: Color(0xFFA5B4FC), fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                  ),
                  const SizedBox(height: 4),
                  SelectableText(
                    turn.suggestedCorrection,
                    style: const TextStyle(color: Color(0xFF38BDF8), fontSize: 15, fontWeight: FontWeight.bold, height: 1.3),
                  ),
                ],
              ),
            ),
          ],

          // Grammar Explanation
          if (turn.grammarNotes.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF111827),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF374151)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "💡 COACH'S EXPLANATION & GRAMMAR TIP:",
                    style: TextStyle(color: Color(0xFFFBBF24), fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                  ),
                  const SizedBox(height: 4),
                  SelectableText(
                    turn.grammarNotes,
                    style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 12, height: 1.4),
                  ),
                ],
              ),
            ),
          ],

          // Conversational Reply
          if (turn.translatedText.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF06221D),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF059669)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "🤖 COACH'S CONVERSATIONAL REPLY (Spoken Aloud):",
                    style: TextStyle(color: Color(0xFF34D399), fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                  ),
                  const SizedBox(height: 4),
                  SelectableText(
                    turn.translatedText,
                    style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold, height: 1.4),
                  ),
                ],
              ),
            ),
          ],

          // Vocabulary Tips
          if (turn.vocabularyTips.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: turn.vocabularyTips.map((tip) {
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0xFF334155)),
                  ),
                  child: Text(
                    "🏷️ $tip",
                    style: const TextStyle(color: Color(0xFFCBD5E1), fontSize: 10),
                  ),
                );
              }).toList(),
            ),
          ],

          const SizedBox(height: 12),

          // Footer Controls: Replay Voice & Copy Feedback
          Row(
            children: [
              OutlinedButton.icon(
                onPressed: onReplay,
                icon: const Icon(Icons.play_arrow_rounded, size: 16),
                label: const Text("Replay Voice"),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF34D399),
                  side: const BorderSide(color: Color(0xFF059669)),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  textStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: () {
                  final text = "[EchoBridge AI Language Coach]\n"
                      "Student Said: ${turn.originalText}\n"
                      "Suggested Phrasing: ${turn.suggestedCorrection}\n"
                      "Politeness: ${turn.politenessLevel}\n"
                      "Grammar Notes: ${turn.grammarNotes}\n"
                      "Spoken Reply: ${turn.translatedText}";
                  Clipboard.setData(ClipboardData(text: text));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text("Coaching feedback copied to clipboard!"),
                      duration: Duration(seconds: 2),
                    ),
                  );
                },
                icon: const Icon(Icons.copy_rounded, size: 14),
                label: const Text("Copy Feedback"),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF94A3B8),
                  side: const BorderSide(color: Color(0xFF334155)),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  textStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: () {
                  DeckService().addFromTurn(turn);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text("✓ Saved to Practice Deck!"),
                      duration: Duration(seconds: 2),
                    ),
                  );
                },
                icon: const Icon(Icons.bookmark_add_rounded, size: 14, color: Color(0xFFFBBF24)),
                label: const Text("Save Card"),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFFFBBF24),
                  side: const BorderSide(color: Color(0xFFD97706)),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  textStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                ),
              ),
              const Spacer(),
              Text(
                "STT: ${turn.sttLatencyMs.toStringAsFixed(0)}ms | TTS: ${turn.ttsLatencyMs.toStringAsFixed(0)}ms",
                style: const TextStyle(color: Color(0xFF64748B), fontSize: 9, fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ],
      ),
    );
  }

  static String _scenarioTitle(String id) {
    switch (id) {
      case 'cafe':
        return '🍵 Cafe';
      case 'transit':
        return '🚅 Transit';
      case 'hotel':
        return '🏨 Hotel';
      case 'business':
        return '💼 Business';
      case 'free_talk':
      default:
        return '🗣️ Daily Talk';
    }
  }
}
