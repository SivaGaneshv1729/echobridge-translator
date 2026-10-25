import 'dart:math';
import 'package:flutter/material.dart';

/// 32-band reactive dynamic audio soundwave visualizer matching EchoBridge desktop aesthetics.
class SoundwaveVisualizerWidget extends StatefulWidget {
  final double currentAudioLevel; // 0.0 to 1.0
  final bool isActive;

  const SoundwaveVisualizerWidget({
    Key? key,
    required this.currentAudioLevel,
    required this.isActive,
  }) : super(key: key);

  @override
  State<SoundwaveVisualizerWidget> createState() => _SoundwaveVisualizerWidgetState();
}

class _SoundwaveVisualizerWidgetState extends State<SoundwaveVisualizerWidget>
    with SingleTickerProviderStateMixin {
  static const int numBars = 32;
  late final AnimationController _ticker;
  final List<double> _barHeights = List.filled(numBars, 0.0);
  final List<double> _targetHeights = List.filled(numBars, 0.0);
  double _phase = 0.0;
  final Random _rand = Random();

  @override
  void initState() {
    super.initState();
    _ticker = AnimationController(vsync: this, duration: const Duration(seconds: 1))
      ..addListener(_tick)
      ..repeat();
  }

  @override
  void didUpdateWidget(SoundwaveVisualizerWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isActive && widget.currentAudioLevel > 0.01) {
      final center = numBars / 2.0;
      for (int i = 0; i < numBars; i++) {
        final dist = (i - center).abs() / center;
        final falloff = exp(-2.5 * dist * dist);
        final noise = 0.7 + _rand.nextDouble() * 0.6;
        final h = (widget.currentAudioLevel * falloff * noise * 1.6).clamp(0.0, 1.0);
        _targetHeights[i] = max(_targetHeights[i], h);
      }
    }
  }

  void _tick() {
    _phase += 0.08;
    for (int i = 0; i < numBars; i++) {
      if (_targetHeights[i] > _barHeights[i]) {
        _barHeights[i] = _barHeights[i] * 0.4 + _targetHeights[i] * 0.6;
      } else {
        _barHeights[i] *= 0.82;
      }
      _targetHeights[i] *= 0.88;

      if (widget.isActive && _barHeights[i] < 0.08) {
        final idle = 0.06 + 0.04 * sin(_phase + i * 0.35);
        _barHeights[i] = max(_barHeights[i], idle);
      }
    }
    setState(() {});
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: const Size(double.infinity, 38),
      painter: _SoundwavePainter(barHeights: _barHeights),
    );
  }
}

class _SoundwavePainter extends CustomPainter {
  final List<double> barHeights;

  _SoundwavePainter({required this.barHeights});

  @override
  void paint(Canvas canvas, Size size) {
    final numBars = barHeights.length;
    const spacing = 3.0;
    final totalSpacing = spacing * (numBars - 1);
    final barWidth = max(2.0, (size.width - totalSpacing) / numBars);

    final cy = size.height / 2.0;
    const minH = 3.0;
    final maxH = size.height - 4.0;

    for (int i = 0; i < numBars; i++) {
      final h = minH + barHeights[i] * (maxH - minH);
      final x = i * (barWidth + spacing);
      final y = cy - (h / 2.0);

      final ratio = i / numBars.toDouble();
      final Color color;
      if (ratio < 0.5) {
        color = Color.lerp(
          const Color(0xFF10B981), // Emerald
          const Color(0xFF06B6D4), // Cyan
          ratio * 2.0,
        )!;
      } else {
        color = Color.lerp(
          const Color(0xFF06B6D4), // Cyan
          const Color(0xFFF59E0B), // Amber
          (ratio - 0.5) * 2.0,
        )!;
      }

      final paint = Paint()
        ..color = color
        ..style = PaintingStyle.fill;

      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x, y, barWidth, h),
          const Radius.circular(3),
        ),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _SoundwavePainter oldDelegate) => true;
}
