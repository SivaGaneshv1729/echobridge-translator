import 'dart:async';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:record/record.dart';

/// Service managing microphone capture, 16kHz PCM streaming, and RMS audio level calculation.
class AudioRecorderService {
  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _recordSubscription;
  bool _isRecording = false;
  bool get isRecording => _isRecording;

  /// Callback reporting normalized RMS audio level (0.0 to 1.0) for the visualizer.
  void Function(double level)? onAudioLevel;

  /// Checks and requests runtime microphone permission.
  Future<bool> checkPermission() async {
    return await _recorder.hasPermission();
  }

  /// Starts live streaming 16kHz 16-bit mono PCM chunks.
  Future<bool> startStreaming({required void Function(Uint8List pcmChunk) onData}) async {
    if (_isRecording) return true;

    final hasPerm = await checkPermission();
    if (!hasPerm) {
      debugPrint("Microphone permission denied.");
      return false;
    }

    try {
      const config = RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        bitRate: 256000,
      );

      final stream = await _recorder.startStream(config);
      _isRecording = true;

      _recordSubscription = stream.listen(
        (data) {
          // Calculate RMS level for reactive soundwave visualizer
          final level = _calculateRmsLevel(data);
          onAudioLevel?.call(level);

          // Forward PCM bytes to speech pipeline
          onData(data);
        },
        onError: (err) {
          debugPrint("Audio recording stream error: $err");
          stopStreaming();
        },
        cancelOnError: true,
      );

      debugPrint("✓ 16kHz PCM Audio streaming started.");
      return true;
    } catch (e) {
      debugPrint("Error starting audio stream: $e");
      _isRecording = false;
      return false;
    }
  }

  /// Stops streaming and closes the microphone session.
  Future<void> stopStreaming() async {
    if (!_isRecording) return;
    try {
      await _recordSubscription?.cancel();
      _recordSubscription = null;
      await _recorder.stop();
    } catch (e) {
      debugPrint("Error stopping audio recorder: $e");
    } finally {
      _isRecording = false;
      onAudioLevel?.call(0.0);
      debugPrint("✓ Audio streaming stopped.");
    }
  }

  /// Computes normalized Root-Mean-Square (RMS) amplitude from 16-bit PCM bytes.
  double _calculateRmsLevel(Uint8List bytes) {
    if (bytes.length < 2) return 0.0;
    final int16List = Int16List.view(bytes.buffer, bytes.offsetInBytes, bytes.lengthInBytes ~/ 2);
    if (int16List.isEmpty) return 0.0;

    double sumSquares = 0.0;
    for (int i = 0; i < int16List.length; i++) {
      final sample = int16List[i] / 32768.0;
      sumSquares += sample * sample;
    }

    final rms = sqrt(sumSquares / int16List.length);
    // Non-linear perceptual scaling
    return (rms * 4.5).clamp(0.0, 1.0);
  }

  void dispose() {
    stopStreaming();
    _recorder.dispose();
  }
}
