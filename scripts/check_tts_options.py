"""Test TTS and Translation options in python."""
import sys
import os

print("--- Testing CTranslate2 ---")
try:
    import ctranslate2
    print(f"CTranslate2 version: {ctranslate2.__version__}")
    print(f"Supported compute types (CPU): {ctranslate2.get_supported_compute_types('cpu')}")
except Exception as e:
    print(f"CTranslate2 error: {e}")

print("\n--- Testing Windows SAPI Voices via ctypes ---")
try:
    import ctypes
    from ctypes import wintypes
    # Use PowerShell via subprocess without dollar sign escaping issues
    import subprocess
    cmd = ["powershell", "-NoProfile", "-Command", 
           "[System.Reflection.Assembly]::LoadWithPartialName('System.Speech') | Out-Null; "
           "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
           "$s.GetInstalledVoices() | Select-Object -ExpandProperty VoiceInfo | Select-Object Name, Culture | ConvertTo-Json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Installed Windows Voices:", res.stdout)
except Exception as e:
    print(f"Windows voice check error: {e}")

print("\n--- Testing Spanish/French in Piper (no pyopenjtalk required) ---")
try:
    from piper.voice import PiperVoice
    en_voice = PiperVoice.load("models_cache/tts/en_US-amy-low.onnx")
    chunks = list(en_voice.synthesize("Hello world"))
    print(f"Piper English synthesis success! Generated {len(chunks)} chunks.")
except Exception as e:
    print(f"Piper English error: {e}")
