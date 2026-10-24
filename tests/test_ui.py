"""Test PySide6 Desktop UI initialization and widget lifecycle."""
import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ui.main_window import MainWindow
from ui.settings_view import SettingsDialog
from ui.conversation_view import ConversationView, ChatBubble

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_main_window_instantiation(qapp):
    """Verify MainWindow initializes cleanly without GUI thread deadlocks."""
    window = MainWindow("config/settings.json")
    assert window.windowTitle().startswith("EchoBridge")
    assert window.src_combo.count() >= 2
    assert window.tgt_combo.count() >= 2
    assert window.mic_btn is not None
    assert window.ptt_btn is not None
    assert window.mute_btn is not None
    window.close()

def test_settings_dialog(qapp):
    """Verify SettingsDialog loads and parses devices and configs."""
    dialog = SettingsDialog("config/settings.json")
    assert dialog.input_combo.count() >= 1
    assert dialog.output_combo.count() >= 1
    assert dialog.model_combo.count() >= 2
    dialog.close()

def test_conversation_view(qapp):
    """Verify ConversationView handles turns and bubble creation."""
    conv = ConversationView()
    turn_sample = {
        "speaker_lang": "en",
        "target_lang": "ja",
        "original_text": "Good morning",
        "translated_text": "おはようございます",
        "total_latency_ms": 780.5,
        "time_str": "12:00:00"
    }
    conv.add_turn(turn_sample)
    assert conv.container_layout.count() >= 2
    conv.clear()
    assert conv.container_layout.count() == 1 # Only the stretch remains
