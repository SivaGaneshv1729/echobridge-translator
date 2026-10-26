import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import '../../models/conversation_turn.dart';

/// Interactive modal allowing users to export, copy, or save conversation transcripts.
class ExportTranscriptDialog extends StatelessWidget {
  final List<ConversationTurn> history;

  const ExportTranscriptDialog({Key? key, required this.history}) : super(key: key);

  String _formatTextTranscript() {
    final buffer = StringBuffer();
    buffer.writeln("=" * 60);
    buffer.writeln("   EchoBridge Conversation & Language Coaching Transcript");
    buffer.writeln("   Exported: ${DateTime.now().toLocal()}");
    buffer.writeln("=" * 60);
    buffer.writeln();

    for (final t in history) {
      final timeStr = "${t.timestamp.hour.toString().padLeft(2, '0')}:${t.timestamp.minute.toString().padLeft(2, '0')}:${t.timestamp.second.toString().padLeft(2, '0')}";
      if (t.isCoachTurn) {
        final tgt = t.targetLang.toUpperCase();
        buffer.writeln("[$timeStr] [AI COACH - $tgt PRACTICE] (Total Latency: ${t.totalLatencyMs.toStringAsFixed(0)}ms)");
        buffer.writeln("  Student Said:       ${t.originalText}");
        if (!t.isNatural || t.suggestedCorrection.isNotEmpty) {
          buffer.writeln("  Suggested Phrasing: ${t.suggestedCorrection}");
        }
        if (t.grammarNotes.isNotEmpty) {
          buffer.writeln("  Grammar Coaching:   ${t.grammarNotes}");
        }
        if (t.politenessLevel.isNotEmpty) {
          buffer.writeln("  Politeness Level:   ${t.politenessLevel}");
        }
        buffer.writeln("  Coach Spoken Reply: ${t.translatedText}");
      } else {
        final dir = t.isEnglishSpeaker ? "EN ➔ JA" : "JA ➔ EN";
        buffer.writeln("[$timeStr] [$dir] (Total Latency: ${t.totalLatencyMs.toStringAsFixed(0)}ms)");
        buffer.writeln("  Spoken:     ${t.originalText}");
        buffer.writeln("  Translated: ${t.translatedText}");
      }
      buffer.writeln();
    }
    return buffer.toString();
  }

  String _formatJsonTranscript() {
    final list = history.map((t) => {
      "id": t.id,
      "timestamp": t.timestamp.toIso8601String(),
      "speaker_lang": t.speakerLang,
      "target_lang": t.targetLang,
      "original_text": t.originalText,
      "translated_text": t.translatedText,
      "stt_latency_ms": t.sttLatencyMs,
      "mt_latency_ms": t.mtLatencyMs,
      "tts_latency_ms": t.ttsLatencyMs,
      "total_latency_ms": t.totalLatencyMs,
      "is_coach_turn": t.isCoachTurn,
      "suggested_correction": t.suggestedCorrection,
      "is_natural": t.isNatural,
      "politeness_level": t.politenessLevel,
      "grammar_notes": t.grammarNotes,
      "vocabulary_tips": t.vocabularyTips,
    }).toList();
    return const JsonEncoder.withIndent("  ").convert(list);
  }

  @override
  Widget build(BuildContext context) {
    final avgLat = history.isEmpty
        ? 0.0
        : history.map((e) => e.totalLatencyMs).reduce((a, b) => a + b) / history.length;

    return Dialog(
      backgroundColor: const Color(0xFF111827),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Color(0xFF1F2937)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: const [
                Icon(Icons.download_rounded, color: Color(0xFF38BDF8), size: 22),
                SizedBox(width: 8),
                Text(
                  "Export Transcript",
                  style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF0F172A),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF334155)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildStatItem("Turns", "${history.length}"),
                  _buildStatItem("Avg Latency", "${avgLat.toStringAsFixed(0)} ms"),
                  _buildStatItem("Mode", "100% Offline"),
                ],
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              "Choose an export format:",
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 10),

            // Option 1: Copy to clipboard
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const CircleAvatar(
                backgroundColor: Color(0xFF1E293B),
                child: Icon(Icons.copy_rounded, color: Color(0xFF38BDF8), size: 18),
              ),
              title: const Text("Copy to Clipboard", style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
              subtitle: const Text("Copies formatted text to system clipboard", style: TextStyle(color: Color(0xFF64748B), fontSize: 11)),
              onTap: () {
                Clipboard.setData(ClipboardData(text: _formatTextTranscript()));
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text("Transcript copied to clipboard!")),
                );
              },
            ),

            // Option 2: Save as Text
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const CircleAvatar(
                backgroundColor: Color(0xFF1E293B),
                child: Icon(Icons.description_outlined, color: Color(0xFF10B981), size: 18),
              ),
              title: const Text("Save as Plain Text (.txt)", style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
              subtitle: const Text("Saves formatted document to app folder", style: TextStyle(color: Color(0xFF64748B), fontSize: 11)),
              onTap: () async {
                final dir = await getApplicationDocumentsDirectory();
                final file = File("${dir.path}/echobridge_transcript_${DateTime.now().millisecondsSinceEpoch}.txt");
                await file.writeAsString(_formatTextTranscript());
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text("Saved to ${file.path}")),
                );
              },
            ),

            // Option 3: Export as JSON
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const CircleAvatar(
                backgroundColor: Color(0xFF1E293B),
                child: Icon(Icons.data_object_rounded, color: Color(0xFFF59E0B), size: 18),
              ),
              title: const Text("Export as JSON (.json)", style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
              subtitle: const Text("Raw timestamps, text, and telemetry data", style: TextStyle(color: Color(0xFF64748B), fontSize: 11)),
              onTap: () async {
                final dir = await getApplicationDocumentsDirectory();
                final file = File("${dir.path}/echobridge_data_${DateTime.now().millisecondsSinceEpoch}.json");
                await file.writeAsString(_formatJsonTranscript());
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text("Saved JSON to ${file.path}")),
                );
              },
            ),
            const SizedBox(height: 12),

            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text("Cancel", style: TextStyle(color: Color(0xFF94A3B8))),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatItem(String label, String value) {
    return Column(
      children: [
        Text(value, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w800)),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(color: Color(0xFF64748B), fontSize: 10, fontWeight: FontWeight.w600)),
      ],
    );
  }
}
