import 'package:flutter/material.dart';
import '../../models/conversation_turn.dart';
import '../widgets/soundwave_visualizer.dart';
import '../widgets/chat_bubble.dart';

/// Main conversational screen for EchoBridge Mobile.
class ConversationScreen extends StatefulWidget {
  const ConversationScreen({Key? key}) : super(key: key);

  @override
  State<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends State<ConversationScreen> {
  bool _isListening = false;
  double _audioLevel = 0.0;
  String _mode = "auto"; // "auto", "en", "ja"
  final List<ConversationTurn> _history = [];
  final ScrollController _scrollController = ScrollController();

  void _toggleListening() {
    setState(() {
      _isListening = !_isListening;
      _audioLevel = _isListening ? 0.65 : 0.0;
    });

    // Simulate speech detection in demo mode if empty
    if (_isListening && _history.isEmpty) {
      Future.delayed(const Duration(milliseconds: 1600), () {
        if (!mounted || !_isListening) return;
        _addTurn(
          speakerLang: "en",
          targetLang: "ja",
          originalText: "Hello! Welcome to Japan. Where can I find the nearest subway station?",
          translatedText: "こんにちは！日本へようこそ。最寄りの地下鉄の駅はどこですか？",
          sttMs: 380,
          mtMs: 110,
          ttsMs: 190,
        );
      });
    }
  }

  void _addTurn({
    required String speakerLang,
    required String targetLang,
    required String originalText,
    required String translatedText,
    required double sttMs,
    required double mtMs,
    required double ttsMs,
  }) {
    final turn = ConversationTurn(
      id: _history.length + 1,
      timestamp: DateTime.now(),
      speakerLang: speakerLang,
      targetLang: targetLang,
      originalText: originalText,
      translatedText: translatedText,
      sttLatencyMs: sttMs,
      mtLatencyMs: mtMs,
      ttsLatencyMs: ttsMs,
      totalLatencyMs: sttMs + mtMs + ttsMs,
    );

    setState(() {
      _history.add(turn);
    });

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

  void _simulateViceVersa() {
    _addTurn(
      speakerLang: "ja",
      targetLang: "en",
      originalText: "この通りをまっすぐ行って、右に曲がると駅がありますよ。",
      translatedText: "Go straight down this street and turn right, and you will find the station.",
      sttMs: 410,
      mtMs: 125,
      ttsMs: 200,
    );
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
            icon: const Icon(Icons.download_rounded, color: Color(0xFF94A3B8)),
            tooltip: "Export Transcript",
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Transcript exported to Downloads folder.")),
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
                      _mode == "auto" ? "✨ AUTO VICE-VERSA (EN ⇄ JA)" : (_mode == "en" ? "EN ➔ JA" : "JA ➔ EN"),
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
                          const Text("🎙️ ⇄ 🌐", style: TextStyle(fontSize: 42)),
                          const SizedBox(height: 12),
                          const Text(
                            "Ready for Real-Time Translation",
                            style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            "Tap the microphone button below to start.\nEchoBridge automatically translates between English and Japanese 100% offline.",
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13, height: 1.4),
                          ),
                          const SizedBox(height: 20),
                          ElevatedButton.icon(
                            onPressed: _simulateViceVersa,
                            icon: const Icon(Icons.flash_on_rounded, size: 16),
                            label: const Text("Simulate Conversation Turn"),
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
                      return ChatBubbleWidget(
                        turn: _history[index],
                        onReplay: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text("Replaying offline audio: ${_history[index].translatedText}"),
                              duration: const Duration(milliseconds: 1000),
                            ),
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
                        _isListening ? "STOP LISTENING" : "START LISTENING",
                        style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, letterSpacing: 0.5),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _isListening ? const Color(0xFFDC2626) : const Color(0xFF059669),
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
                        if (_mode == "auto") {
                          _mode = "en";
                        } else if (_mode == "en") {
                          _mode = "ja";
                        } else {
                          _mode = "auto";
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
}
