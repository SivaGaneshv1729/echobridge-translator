"""Automated environment setup script for EchoBridge."""
import os
import sys
import subprocess
import shutil

def setup():
    print("=" * 60)
    print("   EchoBridge: Environment Setup Script")
    print("=" * 60)

    # 1. Check Python version
    major, minor = sys.version_info[:2]
    if major != 3 or minor < 10:
        print(f"Error: Python 3.10+ required. Found {sys.version}")
        sys.exit(1)
    print(f"✓ Python version: {sys.version.split()[0]}")

    # 2. Check virtual environment
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        print("Note: Running outside a virtual environment.")
        print("Creating .venv if not present...")
        if not os.path.exists(".venv"):
            subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
            print("✓ Created virtual environment .venv")
        pip_cmd = [os.path.abspath(".venv/Scripts/pip")]
    else:
        pip_cmd = [sys.executable, "-m", "pip"]

    # 3. Install requirements
    print("\nInstalling project dependencies from requirements.txt...")
    subprocess.run(pip_cmd + ["install", "-r", "requirements.txt"], check=True)
    print("✓ Dependencies installed successfully.")

    # 4. Verify model cache directory
    os.makedirs("models_cache", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    print("✓ Cache directories verified.")

    print("\nSetup complete! Next step:")
    print("   python scripts/download_models.py")
    print("   python app.py")

if __name__ == "__main__":
    setup()
