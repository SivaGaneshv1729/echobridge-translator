"""Check available offline models for STT, MT, and TTS."""
import urllib.request
import json
import ssl

ctx = ssl.create_default_context()

def check_piper_voices():
    print("--- Checking Piper Voices ---")
    url = "https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            ja_voices = [k for k in data.keys() if k.startswith('ja')]
            en_voices = [k for k in data.keys() if k.startswith('en_US')]
            print(f"Total Piper voices: {len(data)}")
            print(f"Japanese voices ({len(ja_voices)}): {ja_voices}")
            print(f"Sample English voices: {en_voices[:5]}")
            return {"ja": ja_voices, "en": en_voices[:5]}
    except Exception as e:
        print(f"Error checking Piper voices: {e}")
        return {}

def check_argos_packages():
    print("\n--- Checking Argos Translate Index ---")
    url = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            en_ja = [pkg for pkg in data if pkg.get("from_code") == "en" and pkg.get("to_code") == "ja"]
            ja_en = [pkg for pkg in data if pkg.get("from_code") == "ja" and pkg.get("to_code") == "en"]
            print(f"Argos en->ja packages: {len(en_ja)}")
            if en_ja:
                print(f"  en->ja: {en_ja[0].get('package_version')} ({en_ja[0].get('links')})")
            print(f"Argos ja->en packages: {len(ja_en)}")
            if ja_en:
                print(f"  ja->en: {ja_en[0].get('package_version')} ({ja_en[0].get('links')})")
            return {"en_ja": en_ja, "ja_en": ja_en}
    except Exception as e:
        print(f"Error checking Argos index: {e}")
        return {}

def check_huggingface_opus_mt():
    print("\n--- Checking Hugging Face OPUS-MT models ---")
    models = ["Helsinki-NLP/opus-mt-en-jap", "Helsinki-NLP/opus-mt-jap-en"]
    for m in models:
        url = f"https://huggingface.co/api/models/{m}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print(f"Found HF model: {m} (id: {data.get('id')}, downloads: {data.get('downloads')})")
        except Exception as e:
            print(f"HF model {m}: {e}")

if __name__ == "__main__":
    check_piper_voices()
    check_argos_packages()
    check_huggingface_opus_mt()
