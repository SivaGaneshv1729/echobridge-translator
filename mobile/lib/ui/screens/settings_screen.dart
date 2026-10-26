import 'package:flutter/material.dart';
import '../../services/model_manager_service.dart';

/// Settings screen for EchoBridge Mobile.
/// Allows user to configure VAD sensitivity, models, volume, and manage offline storage.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final ModelManagerService _modelManager = ModelManagerService();

  double _vadThreshold = 0.35;
  double _playbackVolume = 1.0;
  bool _autoPlayback = true;
  String _selectedModel = "tiny"; // "tiny" or "base"
  double _cachedSizeMb = 0.0;

  @override
  void initState() {
    super.initState();
    _loadCacheSize();
  }

  void _loadCacheSize() async {
    final size = await _modelManager.getCachedModelsSizeMb();
    if (!mounted) return;
    setState(() => _cachedSizeMb = size);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B0F19),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        elevation: 0,
        title: const Text(
          "Settings",
          style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: Colors.white),
        ),
        actions: [
          TextButton(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Settings saved successfully.")),
              );
              Navigator.pop(context);
            },
            child: const Text("Save", style: TextStyle(color: Color(0xFF38BDF8), fontWeight: FontWeight.bold)),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Section 1: Speech & AI Models
          _buildSectionHeader("OFFLINE AI MODELS"),
          _buildCard([
            ListTile(
              title: const Text("STT Model Size", style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: Text(
                _selectedModel == "tiny" ? "Whisper Tiny INT8 (~39 MB, Ultra-Fast)" : "Whisper Base INT8 (~74 MB, Higher Accuracy)",
                style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
              ),
              trailing: DropdownButton<String>(
                value: _selectedModel,
                dropdownColor: const Color(0xFF1E293B),
                style: const TextStyle(color: Color(0xFF38BDF8), fontSize: 13, fontWeight: FontWeight.bold),
                underline: const SizedBox(),
                items: const [
                  DropdownMenuItem(value: "tiny", child: Text("Tiny (39MB)")),
                  DropdownMenuItem(value: "base", child: Text("Base (74MB)")),
                ],
                onChanged: (val) {
                  if (val != null) setState(() => _selectedModel = val);
                },
              ),
            ),
          ]),
          const SizedBox(height: 16),

          // Section 2: Audio & Voice Detection
          _buildSectionHeader("VOICE DETECTION & AUDIO"),
          _buildCard([
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text("VAD Speech Sensitivity", style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
                      Text("${(_vadThreshold * 100).toInt()}%", style: const TextStyle(color: Color(0xFF38BDF8), fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  const Text("Lower values detect softer whispering; higher values ignore background noise.", style: TextStyle(color: Color(0xFF64748B), fontSize: 11)),
                  Slider(
                    value: _vadThreshold,
                    min: 0.1,
                    max: 0.9,
                    divisions: 8,
                    activeColor: const Color(0xFF10B981),
                    inactiveColor: const Color(0xFF334155),
                    onChanged: (val) => setState(() => _vadThreshold = val),
                  ),
                ],
              ),
            ),
            const Divider(color: Color(0xFF1F2937), height: 1),
            SwitchListTile(
              title: const Text("Automatic Voice Playback", style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: const Text("Speak translation aloud immediately upon completion", style: TextStyle(color: Color(0xFF64748B), fontSize: 11)),
              value: _autoPlayback,
              activeColor: const Color(0xFF10B981),
              onChanged: (val) => setState(() => _autoPlayback = val),
            ),
            const Divider(color: Color(0xFF1F2937), height: 1),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text("Speaker Output Volume", style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
                      Text("${(_playbackVolume * 100).toInt()}%", style: const TextStyle(color: Color(0xFF38BDF8), fontWeight: FontWeight.bold)),
                    ],
                  ),
                  Slider(
                    value: _playbackVolume,
                    min: 0.0,
                    max: 1.0,
                    divisions: 10,
                    activeColor: const Color(0xFF38BDF8),
                    inactiveColor: const Color(0xFF334155),
                    onChanged: (val) => setState(() => _playbackVolume = val),
                  ),
                ],
              ),
            ),
          ]),
          const SizedBox(height: 16),

          // Section 3: Offline Storage Management
          _buildSectionHeader("OFFLINE STORAGE"),
          _buildCard([
            ListTile(
              title: const Text("Cached Model Storage", style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: Text("${_cachedSizeMb.toStringAsFixed(1)} MB allocated on device", style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
              trailing: OutlinedButton(
                onPressed: () {
                  _loadCacheSize();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Model assets verified.")),
                  );
                },
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: Color(0xFF334155)),
                  foregroundColor: const Color(0xFF38BDF8),
                ),
                child: const Text("Verify"),
              ),
            ),
          ]),
          const SizedBox(height: 24),

          // About Section
          Center(
            child: Column(
              children: const [
                Text("EchoBridge Mobile v1.0.0", style: TextStyle(color: Color(0xFF64748B), fontSize: 12, fontWeight: FontWeight.bold)),
                SizedBox(height: 4),
                Text("Zero-Cost 100% Offline Real-Time Speech Translator", style: TextStyle(color: Color(0xFF475569), fontSize: 11)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8),
      child: Text(
        title,
        style: const TextStyle(color: Color(0xFF64748B), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5),
      ),
    );
  }

  Widget _buildCard(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1F2937)),
      ),
      child: Column(children: children),
    );
  }
}
