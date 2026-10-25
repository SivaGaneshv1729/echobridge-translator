# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

datas = [
    ('config', 'config'),
    ('models_cache', 'models_cache'),
]

# Collect package data and dynamic libraries
datas += collect_data_files('faster_whisper')
datas += collect_data_files('piper')
datas += collect_data_files('_sounddevice_data')

binaries = []
binaries += collect_dynamic_libs('ctranslate2')
binaries += collect_dynamic_libs('onnxruntime')

hiddenimports = [
    'ctranslate2',
    'faster_whisper',
    'argostranslate',
    'argostranslate.package',
    'argostranslate.translate',
    'piper',
    'piper.voice',
    'onnxruntime',
    'sounddevice',
    '_sounddevice_data',
    'scipy',
    'scipy.signal',
    'numpy',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'audio',
    'audio.capture',
    'audio.playback',
    'audio.vad',
    'engines',
    'engines.speech_recognition',
    'engines.translation',
    'engines.text_to_speech',
    'pipeline',
    'pipeline.translator',
    'pipeline.conversation',
    'ui',
    'ui.main_window',
    'ui.conversation_view',
    'ui.visualizer',
    'ui.settings_view',
    'models',
    'models.model_manager',
]

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'torch', 'torchaudio', 'IPython', 'notebook', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EchoBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EchoBridge',
)
