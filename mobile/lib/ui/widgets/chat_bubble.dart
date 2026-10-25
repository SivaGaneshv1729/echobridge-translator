import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/conversation_turn.dart';

/// Modern conversational card with speaker avatar, direction badge, telemetry, and replay controls.
class ChatBubbleWidget extends StatelessWidget {
  final ConversationTurn turn;
  final VoidCallback onReplay;

  const ChatBubbleWidget({
    Key? key,
    required this.turn,
    required this.onReplay,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final isEn = turn.isEnglishSpeaker;
    final cardBorder = isEn ? const Color(0xFF0284C7) : const Color(0xFF059669);
    final cardBg = isEn ? const Color(0xFF0F172A) : const Color(0xFF06221D);
    final badgeBg = isEn ? const Color(0xFF0C4A6E) : const Color(0xFF064E3B);
    final badgeColor = isEn ? const Color(0xFF38BDF8) : const Color(0xFF34D399);

    final timeStr = "${turn.timestamp.hour.toString().padLeft(2, '0')}:${turn.timestamp.minute.toString().padLeft(2, '0')}:${turn.timestamp.second.toString().padLeft(2, '0')}";

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: cardBorder, width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row: Avatar, Direction, Time, and Latency Pill
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: badgeBg,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: cardBorder, width: 0.8),
                ),
                child: Text(
                  isEn ? "🇺🇸 English Speaker" : "🇯🇵 Japanese Speaker",
                  style: TextStyle(
                    color: badgeColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                isEn ? "EN ➔ JA" : "JA ➔ EN",
                style: const TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                timeStr,
                style: const TextStyle(
                  color: Color(0xFF64748B),
                  fontSize: 10,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF111827),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFF1F2937)),
                ),
                child: Text(
                  "⚡ ${turn.totalLatencyMs.toStringAsFixed(0)} ms",
                  style: TextStyle(
                    color: turn.totalLatencyMs < 1500 ? const Color(0xFF34D399) : const Color(0xFFF59E0B),
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Spoken Original Text
          const Text(
            "ORIGINAL SPOKEN",
            style: TextStyle(
              color: Color(0xFF64748B),
              fontSize: 9,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 2),
          SelectableText(
            turn.originalText,
            style: const TextStyle(
              color: Color(0xFFE2E8F0),
              fontSize: 15,
              fontWeight: FontWeight.w500,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 10),
          const Divider(color: Colors.white12, height: 1),
          const SizedBox(height: 10),

          // Translated Output Text
          Text(
            "TRANSLATED OUTPUT",
            style: TextStyle(
              color: badgeColor,
              fontSize: 9,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 2),
          SelectableText(
            turn.translatedText,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 17,
              fontWeight: FontWeight.w700,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 14),

          // Action Toolbar: Replay Voice & Copy Buttons
          Row(
            children: [
              OutlinedButton.icon(
                onPressed: onReplay,
                icon: const Icon(Icons.play_arrow_rounded, size: 16, color: Color(0xFF38BDF8)),
                label: const Text("Replay Voice", style: TextStyle(color: Color(0xFF38BDF8), fontSize: 11, fontWeight: FontWeight.bold)),
                style: OutlinedButton.styleFrom(
                  backgroundColor: const Color(0xFF1E293B),
                  side: const BorderSide(color: Color(0xFF0284C7)),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                  minimumSize: const Size(0, 32),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: turn.translatedText));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text("Translation copied to clipboard!"),
                      duration: Duration(milliseconds: 1200),
                    ),
                  );
                },
                icon: const Icon(Icons.copy_rounded, size: 14, color: Color(0xFF94A3B8)),
                label: const Text("Copy", style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w600)),
                style: OutlinedButton.styleFrom(
                  backgroundColor: const Color(0xFF1E293B),
                  side: const BorderSide(color: Color(0xFF334155)),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                  minimumSize: const Size(0, 32),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                ),
              ),
              const Spacer(),
              Text(
                "STT: ${turn.sttLatencyMs.toStringAsFixed(0)}ms | MT: ${turn.mtLatencyMs.toStringAsFixed(0)}ms | TTS: ${turn.ttsLatencyMs.toStringAsFixed(0)}ms",
                style: const TextStyle(color: Color(0xFF64748B), fontSize: 9, fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
