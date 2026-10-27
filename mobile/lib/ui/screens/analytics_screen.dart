import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/conversation_turn.dart';

/// Modern Dark-Mode Fluency & Learning Analytics Screen for EchoBridge Mobile.
class AnalyticsScreen extends StatelessWidget {
  final List<ConversationTurn> history;

  const AnalyticsScreen({Key? key, required this.history}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final coachTurns = history.where((t) => t.isCoachTurn).toList();
    final naturalTurns = coachTurns.where((t) => t.isNatural).length;
    final needsCorrectionTurns = coachTurns.length - naturalTurns;

    final fluencyScore = coachTurns.isEmpty
        ? 100.0
        : ((naturalTurns / coachTurns.length) * 100.0);

    // Politeness distribution
    int politeCount = 0;
    int humbleCount = 0;
    int respectfulCount = 0;
    int casualCount = 0;

    for (final t in coachTurns) {
      final p = t.politenessLevel.toLowerCase();
      if (t.politenessLevel.contains("謙譲") || p.contains("humble")) {
        humbleCount++;
      } else if (t.politenessLevel.contains("尊敬") || p.contains("respect") || p.contains("honorific")) {
        respectfulCount++;
      } else if (t.politenessLevel.contains("丁寧") || p.contains("polite")) {
        politeCount++;
      } else {
        casualCount++;
      }
    }

    final totalPolite = (politeCount + humbleCount + respectfulCount + casualCount);
    final politeDiv = totalPolite == 0 ? 1 : totalPolite;

    // Scenario distribution
    final Map<String, int> scenarioCounts = {
      'free_talk': 0,
      'cafe': 0,
      'transit': 0,
      'hotel': 0,
      'business': 0,
    };
    for (final t in coachTurns) {
      final sc = t.scenarioId.isEmpty ? 'free_talk' : t.scenarioId;
      scenarioCounts[sc] = (scenarioCounts[sc] ?? 0) + 1;
    }

    // Vocabulary collected
    final Set<String> vocabSet = {};
    for (final t in coachTurns) {
      for (final v in t.vocabularyTips) {
        if (v.trim().isNotEmpty) vocabSet.add(v.trim());
      }
    }

    // Grammar tips
    final grammarCorrections = coachTurns
        .where((t) => !t.isNatural || (t.suggestedCorrection.isNotEmpty && t.suggestedCorrection != t.originalText))
        .toList();

    final scoreColor = fluencyScore >= 80
        ? const Color(0xFF34D399)
        : (fluencyScore >= 60 ? const Color(0xFFFBBF24) : const Color(0xFFF87171));

    return Scaffold(
      backgroundColor: const Color(0xFF0B0F19),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        elevation: 0,
        title: const Text(
          "Fluency & Learning Analytics",
          style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: Colors.white),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_rounded, color: Color(0xFF38BDF8)),
            tooltip: "Share Report",
            onPressed: () {
              final report = _generateReport(fluencyScore, coachTurns.length, naturalTurns, needsCorrectionTurns, politeCount, humbleCount, respectfulCount, casualCount, vocabSet);
              Clipboard.setData(ClipboardData(text: report));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Analytics report copied to clipboard!")),
              );
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 1. Overall Fluency Hero Card
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [const Color(0xFF1E1B4B), const Color(0xFF0F172A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFF4338CA)),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF4338CA).withOpacity(0.2),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              children: [
                // Circular Gauge
                Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox(
                      width: 80,
                      height: 80,
                      child: CircularProgressIndicator(
                        value: fluencyScore / 100.0,
                        strokeWidth: 8,
                        backgroundColor: const Color(0xFF312E81),
                        valueColor: AlwaysStoppedAnimation<Color>(scoreColor),
                      ),
                    ),
                    Text(
                      "${fluencyScore.toStringAsFixed(0)}%",
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                        color: scoreColor,
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "OVERALL FLUENCY",
                        style: TextStyle(color: Color(0xFFA5B4FC), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        fluencyScore >= 80 ? "🏆 Highly Fluent & Natural" : (fluencyScore >= 60 ? "⚡ Good Progress" : "🌱 Needs Practice"),
                        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        "$naturalTurns natural / ${coachTurns.length} coach turns",
                        style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // 2. Metrics Grid
          Row(
            children: [
              Expanded(
                child: _buildMetricTile("TOTAL UTTERANCES", "${history.length}", "${coachTurns.length} evaluated", const Color(0xFF38BDF8)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetricTile("GRAMMAR TIPS", "$needsCorrectionTurns", "Points addressed", const Color(0xFFF43F5E)),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // 3. Politeness & Keigo Balance Card
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFF1F2937)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  "🎎 POLITENESS DYNAMICS (敬語バランス)",
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                ),
                const SizedBox(height: 12),
                _buildPoliteBar("丁寧語 (Polite)", politeCount, politeDiv, const Color(0xFF3B82F6)),
                const SizedBox(height: 8),
                _buildPoliteBar("謙譲語 (Humble)", humbleCount, politeDiv, const Color(0xFF6366F1)),
                const SizedBox(height: 8),
                _buildPoliteBar("尊敬語 (Respectful)", respectfulCount, politeDiv, const Color(0xFF8B5CF6)),
                const SizedBox(height: 8),
                _buildPoliteBar("普通体 (Casual)", casualCount, politeDiv, const Color(0xFF64748B)),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // 4. Role-Play Scenario Distribution
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFF1F2937)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  "🗺️ ROLE-PLAY SCENARIOS",
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _buildScenarioBadge("🗣️ Daily Talk", scenarioCounts['free_talk'] ?? 0, const Color(0xFF38BDF8)),
                    _buildScenarioBadge("🍵 Cafe", scenarioCounts['cafe'] ?? 0, const Color(0xFF10B981)),
                    _buildScenarioBadge("🚅 Transit", scenarioCounts['transit'] ?? 0, const Color(0xFFF59E0B)),
                    _buildScenarioBadge("🏨 Hotel", scenarioCounts['hotel'] ?? 0, const Color(0xFF8B5CF6)),
                    _buildScenarioBadge("💼 Business", scenarioCounts['business'] ?? 0, const Color(0xFFEC4899)),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // 5. Recent Grammar Corrections
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFF1F2937)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  "⚡ RECENT GRAMMAR LEARNING POINTS",
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                ),
                const SizedBox(height: 12),
                if (grammarCorrections.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8),
                    child: Text(
                      "✨ All utterances were natural and fluent!",
                      style: TextStyle(color: Color(0xFF34D399), fontSize: 13, fontStyle: FontStyle.italic),
                    ),
                  )
                else
                  ...grammarCorrections.take(4).map((t) => Container(
                        margin: const EdgeInsets.only(bottom: 8),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0F172A),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFF1E293B)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text("• You: \"${t.originalText}\"", style: const TextStyle(color: Color(0xFFF87171), fontSize: 12)),
                            const SizedBox(height: 2),
                            Text("  Suggested: \"${t.suggestedCorrection}\"", style: const TextStyle(color: Color(0xFF34D399), fontSize: 12, fontWeight: FontWeight.bold)),
                            if (t.grammarNotes.isNotEmpty) ...[
                              const SizedBox(height: 2),
                              Text("  Note: ${t.grammarNotes}", style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontStyle: FontStyle.italic)),
                            ],
                          ],
                        ),
                      )),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // 6. Vocabulary Bank
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFF1F2937)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  "📚 VOCABULARY BANK (${vocabSet.length} items)",
                  style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                ),
                const SizedBox(height: 12),
                if (vocabSet.isEmpty)
                  const Text(
                    "No vocabulary collected yet. Speak with the AI Coach to build your bank!",
                    style: TextStyle(color: Color(0xFF64748B), fontSize: 12, fontStyle: FontStyle.italic),
                  )
                else
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: vocabSet.take(12).map((v) => Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: const Color(0xFF1E1B4B),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFF4338CA)),
                          ),
                          child: Text(
                            "💡 $v",
                            style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 11, fontWeight: FontWeight.bold),
                          ),
                        )).toList(),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricTile(String title, String val, String sub, Color color) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1F2937)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.5)),
          const SizedBox(height: 4),
          Text(val, style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.w900)),
          const SizedBox(height: 2),
          Text(sub, style: const TextStyle(color: Color(0xFF64748B), fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildPoliteBar(String label, int count, int total, Color color) {
    final pct = (count / total * 100).round();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
            Text("$count ($pct%)", style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11)),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: count / total,
          backgroundColor: const Color(0xFF1E293B),
          valueColor: AlwaysStoppedAnimation<Color>(color),
          minHeight: 6,
          borderRadius: BorderRadius.circular(4),
        ),
      ],
    );
  }

  Widget _buildScenarioBadge(String label, int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.bold)),
          const SizedBox(width: 6),
          Text("$count", style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }

  String _generateReport(double score, int coachTotal, int natural, int corrections, int polite, int humble, int respectful, int casual, Set<String> vocab) {
    return """
# 📊 EchoBridge Fluency Report
• Overall Fluency: ${score.toStringAsFixed(1)}%
• Utterances: $coachTotal ($natural natural / $corrections corrections)
• Politeness: Polite: $polite | Humble: $humble | Respectful: $respectful | Casual: $casual
• Mastered Vocabulary: ${vocab.join(', ')}
""";
  }
}
