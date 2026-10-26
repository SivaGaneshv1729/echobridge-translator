"""Test suite for UI components: SoundwaveVisualizer, ConversationView, and MainWindow."""
import sys
import pytest
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_soundwave_visualizer(qapp):
    from ui.visualizer import SoundwaveVisualizer
    viz = SoundwaveVisualizer(num_bars=36)
    assert viz.num_bars == 36
    viz.set_active(True)
    assert viz.is_active is True
    viz.set_level(0.75)
    # Check that heights are populated
    assert viz.target_heights.max() > 0.0
    viz._animate_tick()
    viz.set_active(False)
    assert viz.is_active is False
    viz.deleteLater()

def test_conversation_view(qapp):
    from ui.conversation_view import ConversationView
    cv = ConversationView()
    turn_data = {
        "speaker_lang": "en",
        "target_lang": "ja",
        "original_text": "Good morning!",
        "translated_text": "おはようございます！",
        "total_latency_ms": 1120.0,
        "stt_latency_ms": 500.0,
        "mt_latency_ms": 320.0,
        "tts_latency_ms": 300.0,
        "time_str": "08:30:00"
    }
    cv.add_turn(turn_data)
    # empty hero should now be hidden
    assert cv.empty_hero.isHidden()

    replayed = []
    cv.replay_requested.connect(lambda text, lang: replayed.append((text, lang)))
    # simulate replay
    cv.replay_requested.emit("おはようございます！", "ja")
    assert len(replayed) == 1
    assert replayed[0] == ("おはようございます！", "ja")

    cv.clear()
    assert not cv.empty_hero.isHidden()
    cv.deleteLater()

def test_settings_dialog(qapp):
    from ui.settings_view import SettingsDialog
    dialog = SettingsDialog("config/settings.json")
    assert dialog.windowTitle() == "EchoBridge Settings"
    dialog.deleteLater()

def test_main_window_instantiation(qapp):
    from ui.main_window import MainWindow
    window = MainWindow("config/settings.json")
    assert window.windowTitle() == "EchoBridge — Offline Real-Time Speech Translator"
    assert window.visualizer is not None
    assert window.conversation_view is not None
    assert window.tabs.count() == 2
    window.close()
    window.deleteLater()

def test_subtitle_overlay_window(qapp):
    from ui.overlay_window import SubtitleOverlayWindow
    overlay = SubtitleOverlayWindow()
    overlay.update_transcription("Hello world", "en")
    assert "Hello world" in overlay.orig_label.text()
    overlay.update_translation("こんにちは世界")
    assert overlay.trans_label.text() == "こんにちは世界"
    overlay.set_active_state(True, is_speaking=True)
    assert "SPEAKING" in overlay.status_pill.text()
    overlay.set_active_state(False)
    assert "IDLE" in overlay.status_pill.text()
    overlay._increase_font()
    overlay._decrease_font()
    overlay.close()
    overlay.deleteLater()
