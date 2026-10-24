"""Pure-Python Japanese phonemizer using pykakasi for Piper TTS without pyopenjtalk."""
import sys
import os
import time
import pykakasi
from piper.voice import PiperVoice
from piper.phonemize_japanese import OPENJTALK_TO_IPA

sys.stdout.reconfigure(encoding='utf-8')

# Kana / Hepbrun to OpenJTalk phones mapping
ROMAJI_TO_PHONES = {
    "a": ["a"], "i": ["i"], "u": ["u"], "e": ["e"], "o": ["o"],
    "ka": ["k", "a"], "ki": ["ky", "i"], "ku": ["k", "u"], "ke": ["k", "e"], "ko": ["k", "o"],
    "sa": ["s", "a"], "shi": ["sh", "i"], "su": ["s", "u"], "se": ["s", "e"], "so": ["s", "o"],
    "ta": ["t", "a"], "chi": ["ch", "i"], "tsu": ["ts", "u"], "te": ["t", "e"], "to": ["t", "o"],
    "na": ["n", "a"], "ni": ["ny", "i"], "nu": ["n", "u"], "ne": ["n", "e"], "no": ["n", "o"],
    "ha": ["h", "a"], "hi": ["hy", "i"], "fu": ["f", "u"], "he": ["h", "e"], "ho": ["h", "o"],
    "ma": ["m", "a"], "mi": ["my", "i"], "mu": ["m", "u"], "me": ["m", "e"], "mo": ["m", "o"],
    "ya": ["y", "a"], "yu": ["y", "u"], "yo": ["y", "o"],
    "ra": ["r", "a"], "ri": ["ry", "i"], "ru": ["r", "u"], "re": ["r", "e"], "ro": ["r", "o"],
    "wa": ["w", "a"], "wo": ["o"], "n": ["N"],
    "ga": ["g", "a"], "gi": ["gy", "i"], "gu": ["g", "u"], "ge": ["g", "e"], "go": ["g", "o"],
    "za": ["z", "a"], "ji": ["j", "i"], "zu": ["z", "u"], "ze": ["z", "e"], "zo": ["z", "o"],
    "da": ["d", "a"], "de": ["d", "e"], "do": ["d", "o"],
    "ba": ["b", "a"], "bi": ["by", "i"], "bu": ["b", "u"], "be": ["b", "e"], "bo": ["b", "o"],
    "pa": ["p", "a"], "pi": ["py", "i"], "pu": ["p", "u"], "pe": ["p", "e"], "po": ["p", "o"],
    "kya": ["ky", "a"], "kyu": ["ky", "u"], "kyo": ["ky", "o"],
    "sha": ["sh", "a"], "shu": ["sh", "u"], "sho": ["sh", "o"],
    "cha": ["ch", "a"], "chu": ["ch", "u"], "cho": ["ch", "o"],
    "nya": ["ny", "a"], "nyu": ["ny", "u"], "nyo": ["ny", "o"],
    "hya": ["hy", "a"], "hyu": ["hy", "u"], "hyo": ["hy", "o"],
    "mya": ["my", "a"], "myu": ["my", "u"], "myo": ["my", "o"],
    "rya": ["ry", "a"], "ryu": ["ry", "u"], "ryo": ["ry", "o"],
    "gya": ["gy", "a"], "gyu": ["gy", "u"], "gyo": ["gy", "o"],
    "ja": ["j", "a"], "ju": ["j", "u"], "jo": ["j", "o"],
    "bya": ["by", "a"], "byu": ["by", "u"], "byo": ["by", "o"],
    "pya": ["py", "a"], "pyu": ["py", "u"], "pyo": ["py", "o"],
    "desu": ["d", "e", "s", "U"],
    "masu": ["m", "a", "s", "U"],
}

kks = pykakasi.kakasi()

def text_to_ipa(text: str) -> list[str]:
    """Convert Japanese text to IPA phonemes."""
    result = kks.convert(text)
    ipa_phonemes = []
    
    for item in result:
        romaji = item['hepburn'].lower()
        # Parse romaji tokens
        i = 0
        while i < len(romaji):
            matched = False
            # Try 4, 3, 2, 1 char matches
            for l in [4, 3, 2, 1]:
                sub = romaji[i:i+l]
                if sub in ROMAJI_TO_PHONES:
                    phones = ROMAJI_TO_PHONES[sub]
                    for p in phones:
                        ipa = OPENJTALK_TO_IPA.get(p.lower(), p)
                        ipa_phonemes.extend(list(ipa))
                    i += l
                    matched = True
                    break
            if not matched:
                char = romaji[i]
                if char in "?!.,":
                    ipa_phonemes.append(char)
                elif char == " ":
                    ipa_phonemes.append("#")
                i += 1
    
    ipa_phonemes.append(".")
    return ipa_phonemes

def test_japanese_synthesis():
    voice_path = "models_cache/tts/ja_JP-hi_fi_captain-medium.onnx"
    print(f"Loading Piper Japanese voice from {voice_path}...")
    voice = PiperVoice.load(voice_path)

    test_text = "今日はどうですか？ 駅はどこですか？"
    print(f"Input text: {test_text}")

    ipa = text_to_ipa(test_text)
    print(f"IPA Phonemes: {' '.join(ipa)}")

    # Convert phonemes to IDs
    phoneme_ids = voice.phonemes_to_ids(ipa)
    print(f"Phoneme IDs: {phoneme_ids}")

    t0 = time.perf_counter()
    audio = voice.phoneme_ids_to_audio(phoneme_ids)
    latency_ms = (time.perf_counter() - t0) * 1000

    print(f"Synthesized audio length: {len(audio)} bytes ({len(audio)/2/voice.config.sample_rate:.2f} s)")
    print(f"Synthesis latency: {latency_ms:.2f} ms")

if __name__ == "__main__":
    test_japanese_synthesis()
