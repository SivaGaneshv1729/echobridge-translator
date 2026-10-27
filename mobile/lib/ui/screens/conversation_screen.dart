import 'package:flutter/material.dart';
import '../../models/conversation_turn.dart';
import '../../services/speech_pipeline_service.dart';
import '../widgets/soundwave_visualizer.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/coaching_bubble.dart';
import '../widgets/export_dialog.dart';
import 'settings_screen.dart';
import 'analytics_screen.dart';
import 'flashcard_screen.dart';

/// Main conversational screen for EchoBridge Mobile.
class ConversationScreen extends StatefulWidget {
  const ConversationScreen({Key? key}) : super(key: key);

  @override
  State<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends State<ConversationScreen> {
  final SpeechPipelineService _pipeline = SpeechPipelineService();
  bool _isListening = false;
  double _audioLevel = 0.0;
  String _statusText = "Ready. Tap START to translate.";
  final List<ConversationTurn> _history = [];
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _pipeline.onTurnCompleted = (turn) {
      if (!mounted) return;
      setState(() => _history.add(turn));
      _scrollToBottom();
    };
    _pipeline.onStatusChanged = (status) {
      if (!mounted) return;
      setState(() => _statusText = status);
    };
    _pipeline.onAudioLevelChanged = (level) {
      if (!mounted) return;
      setState(() => _audioLevel = level);
    };
    _pipeline.initialize();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _toggleListening() async {
    await _pipeline.toggleListening();
    if (!mounted) return;
    setState(() {
      _isListening = _pipeline.isListening;
    });
  }

  void _simulateViceVersa() {
    _pipeline.toggleListening();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B0F19),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        elevation: 0,
        title: Row(
          children: [
            const Text(
              "EchoBridge",
              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 19, color: Colors.white),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: const Color(0xFF064E3B),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF059669)),
              ),
              child: const Text(
                "OFFLINE",
                style: TextStyle(color: Color(0xFF34D399), fontSize: 9, fontWeight: FontWeight.w900),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.bar_chart_rounded, color: Color(0xFF38BDF8)),
            tooltip: "Fluency & Analytics",
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => AnalyticsScreen(history: _history)),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.style_rounded, color: Color(0xFFA78BFA)),
            tooltip: "Practice Flashcards",
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => FlashcardScreen(
                    onReplayAudio: () => _pipeline.replayVoice(
                      "アイスコーヒーをひとつ、お願いします。",
                      "ja",
                    ),
                  ),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.download_rounded, color: Color(0xFF94A3B8)),
            tooltip: "Export Transcript",
            onPressed: () {
              if (_history.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text("No conversation turns to export yet.")),
                );
                return;
              }
              showDialog(
                context: context,
                builder: (_) => ExportTranscriptDialog(history: _history),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined, color: Color(0xFF94A3B8)),
            tooltip: "Settings",
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SettingsScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline_rounded, color: Color(0xFF94A3B8)),
            tooltip: "Clear History",
            onPressed: () {
              setState(() => _history.clear());
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Mode Switcher Tabs
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF1F2937)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: () {
                      setState(() {
                        _pipeline.appMode = "translate";
                        _statusText = "Ready. Tap START to translate.";
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: _pipeline.appMode == "translate" ? const Color(0xFF0284C7) : Colors.transparent,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        "🌐 Live Translate",
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: _pipeline.appMode == "translate" ? Colors.white : const Color(0xFF94A3B8),
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: () {
                      setState(() {
                        _pipeline.appMode = "coach";
                        _statusText = "AI Language Coach active. Speak Japanese!";
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: _pipeline.appMode == "coach" ? const Color(0xFF4F46E5) : Colors.transparent,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        "🎓 AI Coach",
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: _pipeline.appMode == "coach" ? Colors.white : const Color(0xFF94A3B8),
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Role-Play Scenario Chips (When Coach Mode is Active)
          if (_pipeline.appMode == "coach")
            Container(
              height: 38,
              margin: const EdgeInsets.only(top: 4, bottom: 4),
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                children: [
                  _buildScenarioChip('free_talk', '🗣️ Daily Talk'),
                  _buildScenarioChip('cafe', '🍵 Cafe & Dining'),
                  _buildScenarioChip('transit', '🚅 Transit & Nav'),
                  _buildScenarioChip('hotel', '🏨 Hotel'),
                  _buildScenarioChip('business', '💼 Business'),
                ],
              ),
            ),

          // Audio Visualizer Card
          Container(
            margin: const EdgeInsets.all(12),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFF111827),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFF1F2937)),
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      _pipeline.appMode == "coach"
                          ? "🎓 AI COACH SCENARIO: ${_pipeline.scenario.toUpperCase()}"
                          : (_pipeline.mode == "auto" ? "✨ AUTO VICE-VERSA (EN ⇄ JA)" : (_pipeline.mode == "en" ? "EN ➔ JA" : "JA ➔ EN")),
                      style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w700),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: _isListening ? const Color(0xFF064E3B) : const Color(0xFF1F2937),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        _isListening ? "MIC ACTIVE" : "MIC IDLE",
                        style: TextStyle(
                          color: _isListening ? const Color(0xFF34D399) : const Color(0xFF64748B),
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                SoundwaveVisualizerWidget(
                  currentAudioLevel: _audioLevel,
                  isActive: _isListening,
                ),
                const SizedBox(height: 8),
                Text(
                  _statusText,
                  style: const TextStyle(color: Color(0xFF64748B), fontSize: 11, fontStyle: FontStyle.italic),
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          // Conversation Stream Feed
          Expanded(
            child: _history.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(_pipeline.appMode == "coach" ? "🎓 ⇄ 💬" : "🎙️ ⇄ 🌐", style: const TextStyle(fontSize: 42)),
                          const SizedBox(height: 12),
                          Text(
                            _pipeline.appMode == "coach" ? "AI Language Coach Ready" : "Ready for Real-Time Translation",
                            style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _pipeline.appMode == "coach"
                                ? "Practice Japanese naturally. The AI partner replies aloud and provides instant grammar, fluency, and politeness tips."
                                : "Tap the microphone button below to start.\nEchoBridge automatically translates between English and Japanese 100% offline.",
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13, height: 1.4),
                          ),
                          const SizedBox(height: 20),
                          ElevatedButton.icon(
                            onPressed: _simulateViceVersa,
                            icon: const Icon(Icons.flash_on_rounded, size: 16),
                            label: Text(_pipeline.appMode == "coach" ? "Simulate Coach Practice" : "Simulate Conversation Turn"),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF1E293B),
                              foregroundColor: const Color(0xFF38BDF8),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                                side: const BorderSide(color: Color(0xFF0284C7)),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    itemCount: _history.length,
                    itemBuilder: (context, index) {
                      final turn = _history[index];
                      if (turn.isCoachTurn) {
                        return CoachingBubbleWidget(
                          turn: turn,
                          onReplay: () {
                            _pipeline.replayVoice(
                              turn.translatedText,
                              turn.targetLang,
                            );
                          },
                        );
                      }
                      return ChatBubbleWidget(
                        turn: turn,
                        onReplay: () {
                          _pipeline.replayVoice(
                            turn.translatedText,
                            turn.targetLang,
                          );
                        },
                      );
                    },
                  ),
          ),

          // Bottom Control Dock
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: const BoxDecoration(
              color: Color(0xFF111827),
              border: Border(top: BorderSide(color: Color(0xFF1F2937))),
            ),
            child: SafeArea(
              child: Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _toggleListening,
                      icon: Icon(_isListening ? Icons.stop_rounded : Icons.mic_rounded),
                      label: Text(
                        _isListening
                            ? "STOP LISTENING"
                            : (_pipeline.appMode == "coach" ? "START PRACTICE" : "START LISTENING"),
                        style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, letterSpacing: 0.5),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _isListening
                            ? const Color(0xFFDC2626)
                            : (_pipeline.appMode == "coach" ? const Color(0xFF4F46E5) : const Color(0xFF059669)),
                        foregroundColor: Colors.white,
                        minimumSize: const Size(0, 48),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  IconButton(
                    onPressed: () {
                      setState(() {
                        if (_pipeline.mode == "auto") {
                          _pipeline.mode = "en";
                        } else if (_pipeline.mode == "en") {
                          _pipeline.mode = "ja";
                        } else {
                          _pipeline.mode = "auto";
                        }
                      });
                    },
                    icon: const Icon(Icons.swap_horiz_rounded, color: Color(0xFF38BDF8)),
                    tooltip: "Switch Direction",
                    style: IconButton.styleFrom(
                      backgroundColor: const Color(0xFF1F2937),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                        side: const BorderSide(color: Color(0xFF374151)),
                      ),
                      minimumSize: const Size(48, 48),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildScenarioChip(String id, String label) {
    final isSelected = _pipeline.scenario == id;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        selected: isSelected,
        label: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : const Color(0xFF94A3B8),
            fontSize: 11,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: const Color(0xFF1E293B),
        selectedColor: const Color(0xFF4338CA),
        checkmarkColor: Colors.white,
        side: BorderSide(
          color: isSelected ? const Color(0xFF6366F1) : const Color(0xFF334155),
        ),
        onSelected: (val) {
          setState(() {
            _pipeline.scenario = id;
            _statusText = "Switched to $label. Speak Japanese to practice!";
          });
        },
      ),
    );
  }
}

