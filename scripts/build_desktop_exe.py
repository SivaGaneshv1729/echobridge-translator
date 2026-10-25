"""Build and package EchoBridge into a standalone Windows executable distribution."""
import os
import sys
import shutil
import zipfile
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("builder")

def build_windows_executable():
    logger.info("Starting standalone Windows executable build via PyInstaller...")
    
    # 1. Run PyInstaller
    cmd = [
        os.path.join(".venv", "Scripts", "pyinstaller.exe"),
        "--clean",
        "--noconfirm",
        "echobridge.spec"
    ]
    logger.info(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        logger.error(f"PyInstaller build failed with exit code {result.returncode}")
        return False

    dist_dir = os.path.join("dist", "EchoBridge")
    exe_path = os.path.join(dist_dir, "EchoBridge.exe")

    if not os.path.exists(exe_path):
        logger.error(f"Expected executable not found at {exe_path}")
        return False

    exe_size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    logger.info(f"✓ Standalone executable created: {exe_path} ({exe_size_mb:.2f} MB)")

    # 2. Package into a portable ZIP archive
    zip_path = os.path.join("dist", "EchoBridge-Windows-Portable.zip")
    logger.info(f"Compressing distribution folder into {zip_path}...")
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, "dist")
                zipf.write(full_path, rel_path)

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    logger.info(f"✓ Portable distribution archive ready: {zip_path} ({zip_size_mb:.2f} MB)")
    logger.info("EchoBridge standalone packaging completed successfully!")
    return True

if __name__ == "__main__":
    success = build_windows_executable()
    sys.exit(0 if success else 1)
