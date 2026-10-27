import 'package:flutter/material.dart';
import '../../models/deck_card.dart';
import '../../services/deck_service.dart';

/// Modern Dark-Mode Flashcard Review Screen for EchoBridge Mobile.
class FlashcardScreen extends StatefulWidget {
  final VoidCallback? onReplayAudio;

  const FlashcardScreen({Key? key, this.onReplayAudio}) : super(key: key);

  @override
  State<FlashcardScreen> createState() => _FlashcardScreenState();
}

class _FlashcardScreenState extends State<FlashcardScreen> {
  final DeckService _deckService = DeckService();
  int _currentIndex = 0;
  bool _isFlipped = false;
  String _filter = "all"; // "all", "unmastered", "mastered"

  List<DeckCard> get _filteredCards {
    if (_filter == "unmastered") {
      return _deckService.cards.where((c) => !c.mastered).toList();
    } else if (_filter == "mastered") {
      return _deckService.cards.where((c) => c.mastered).toList();
    }
    return _deckService.cards;
  }

  void _nextCard() {
    if (_filteredCards.isEmpty) return;
    setState(() {
      _currentIndex = (_currentIndex + 1) % _filteredCards.length;
      _isFlipped = false;
    });
  }

  void _prevCard() {
    if (_filteredCards.isEmpty) return;
    setState(() {
      _currentIndex = (_currentIndex - 1 + _filteredCards.length) % _filteredCards.length;
      _isFlipped = false;
    });
  }

  void _toggleMastered(bool mastered) {
    if (_filteredCards.isEmpty) return;
    final card = _filteredCards[_currentIndex];
    setState(() {
      _deckService.toggleMastered(card.id, mastered);
      if (_filteredCards.isNotEmpty) {
        _currentIndex = _currentIndex % _filteredCards.length;
      }
      _isFlipped = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final cards = _filteredCards;
    final total = cards.length;
    if (_currentIndex >= total && total > 0) {
      _currentIndex = total - 1;
    }

    final card = total > 0 ? cards[_currentIndex] : null;

    return Scaffold(
      backgroundColor: const Color(0xFF0B0F19),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        elevation: 0,
        title: const Text(
          "Practice Flashcards",
          style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: Colors.white),
        ),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            alignment: Alignment.center,
            child: Text(
              "${_deckService.masteredCount} / ${_deckService.totalCount} Mastered",
              style: const TextStyle(color: Color(0xFF34D399), fontSize: 12, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter Row
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: const Color(0xFF111827),
            child: Row(
              children: [
                _buildFilterChip("all", "All (${_deckService.totalCount})"),
                const SizedBox(width: 8),
                _buildFilterChip("unmastered", "Review (${_deckService.totalCount - _deckService.masteredCount})"),
                const SizedBox(width: 8),
                _buildFilterChip("mastered", "Mastered (${_deckService.masteredCount})"),
              ],
            ),
          ),

          // Progress Bar
          LinearProgressIndicator(
            value: total == 0 ? 0 : (_currentIndex + 1) / total,
            backgroundColor: const Color(0xFF1E293B),
            valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF6366F1)),
            minHeight: 4,
          ),

          // Card Area
          Expanded(
            child: card == null
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: const [
                        Text("🎴", style: TextStyle(fontSize: 48)),
                        SizedBox(height: 12),
                        Text("No Flashcards in this filter", style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                        SizedBox(height: 4),
                        Text("Save cards from AI Coach conversations to practice!", style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
                      ],
                    ),
                  )
                : Padding(
                    padding: const EdgeInsets.all(16),
                    child: GestureDetector(
                      onTap: () => setState(() => _isFlipped = !_isFlipped),
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 300),
                        child: _isFlipped ? _buildBackCard(card) : _buildFrontCard(card),
                      ),
                    ),
                  ),
          ),

          // Bottom Controls
          if (card != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: const BoxDecoration(
                color: Color(0xFF111827),
                border: Border(top: BorderSide(color: Color(0xFF1F2937))),
              ),
              child: SafeArea(
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back_ios_rounded, color: Color(0xFF94A3B8)),
                      onPressed: _prevCard,
                    ),
                    Expanded(
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.replay_rounded, size: 16),
                        label: const Text("NEEDS REVIEW", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF451A03),
                          foregroundColor: const Color(0xFFFBBF24),
                          side: const BorderSide(color: Color(0xFFD97706)),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                          minimumSize: const Size(0, 44),
                        ),
                        onPressed: () => _toggleMastered(false),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.check_circle_outline_rounded, size: 16),
                        label: const Text("MASTERED", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF064E3B),
                          foregroundColor: const Color(0xFF34D399),
                          side: const BorderSide(color: Color(0xFF059669)),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                          minimumSize: const Size(0, 44),
                        ),
                        onPressed: () => _toggleMastered(true),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.arrow_forward_ios_rounded, color: Color(0xFF94A3B8)),
                      onPressed: _nextCard,
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildFrontCard(DeckCard card) {
    return Container(
      key: const ValueKey("front"),
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF4F46E5), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF4F46E5).withOpacity(0.15),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF1E1B4B),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFF4338CA)),
                ),
                child: Text(
                  _scenarioLabel(card.scenarioId),
                  style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 11, fontWeight: FontWeight.bold),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: card.mastered ? const Color(0xFF064E3B) : const Color(0xFF1E293B),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  card.mastered ? "✓ MASTERED" : "🌱 PRACTICE",
                  style: TextStyle(
                    color: card.mastered ? const Color(0xFF34D399) : const Color(0xFF94A3B8),
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const Spacer(),
          const Center(
            child: Text(
              "PROMPT / WHAT YOU SAID",
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
            ),
          ),
          const SizedBox(height: 12),
          Center(
            child: Text(
              card.originalText,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700, height: 1.4),
            ),
          ),
          const Spacer(),
          Center(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFF334155)),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.touch_app_rounded, size: 14, color: Color(0xFF38BDF8)),
                  SizedBox(width: 6),
                  Text("Tap to reveal correction", style: TextStyle(color: Color(0xFF38BDF8), fontSize: 12, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBackCard(DeckCard card) {
    return Container(
      key: const ValueKey("back"),
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF059669), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF059669).withOpacity(0.15),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF064E3B),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFF059669)),
                ),
                child: Text(
                  card.politenessLevel.isNotEmpty ? card.politenessLevel : "丁寧語 (Polite)",
                  style: const TextStyle(color: Color(0xFF34D399), fontSize: 11, fontWeight: FontWeight.bold),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.volume_up_rounded, color: Color(0xFF38BDF8)),
                onPressed: () => widget.onReplayAudio?.call(),
                tooltip: "Listen",
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Center(
            child: Text(
              "NATURAL CORRECTION",
              style: TextStyle(color: Color(0xFF34D399), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
            ),
          ),
          const SizedBox(height: 8),
          Center(
            child: Text(
              card.suggestedCorrection,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800, height: 1.4),
            ),
          ),
          const SizedBox(height: 16),
          if (card.grammarNotes.isNotEmpty) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF334155)),
              ),
              child: Text(
                "💡 Note: ${card.grammarNotes}",
                style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12, height: 1.4),
              ),
            ),
            const SizedBox(height: 12),
          ],
          if (card.vocabularyTips.isNotEmpty)
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: card.vocabularyTips.map((v) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1E1B4B),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: const Color(0xFF4338CA)),
                    ),
                    child: Text(
                      "🏷️ $v",
                      style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 10, fontWeight: FontWeight.bold),
                    ),
                  )).toList(),
            ),
          const Spacer(),
          const Center(
            child: Text("Tap card to flip back", style: TextStyle(color: Color(0xFF64748B), fontSize: 11)),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String id, String label) {
    final isSelected = _filter == id;
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: () {
        setState(() {
          _filter = id;
          _currentIndex = 0;
          _isFlipped = false;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF4F46E5) : const Color(0xFF1E293B),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: isSelected ? const Color(0xFF6366F1) : const Color(0xFF334155)),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : const Color(0xFF94A3B8),
            fontSize: 11,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }

  String _scenarioLabel(String id) {
    switch (id) {
      case 'cafe':
        return '🍵 Cafe & Dining';
      case 'transit':
        return '🚅 Transit & Nav';
      case 'hotel':
        return '🏨 Hotel Check-in';
      case 'business':
        return '💼 Business';
      case 'free_talk':
      default:
        return '🗣️ Daily Talk';
    }
  }
}
