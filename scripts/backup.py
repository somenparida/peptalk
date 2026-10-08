#!/usr/bin/env python3
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / "backup"


def create_backup():
    print("========================================")
    print("CREATING RELEASE BACKUP BUNDLE")
    print("========================================\n")

    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    demo_inputs = BACKUP_DIR / "demo_inputs"
    demo_outputs = BACKUP_DIR / "demo_outputs"
    source_code = BACKUP_DIR / "source_code"

    demo_inputs.mkdir(exist_ok=True)
    demo_outputs.mkdir(exist_ok=True)
    source_code.mkdir(exist_ok=True)

    # 1. Copy demo inputs & outputs
    demo_dir = BASE_DIR / "data" / "demo"
    if demo_dir.exists():
        for f in demo_dir.glob("*"):
            shutil.copy(f, demo_inputs / f.name)

    outputs_dir = BASE_DIR / "outputs"
    if outputs_dir.exists():
        for item in outputs_dir.glob("demo_*"):
            if item.is_dir():
                shutil.copytree(item, demo_outputs / item.name, dirs_exist_ok=True)

    # 2. Copy source code
    for folder in ["integration", "evaluation", "scripts", "tests", "docs", "ai", "geometry", "reconstruction", "viewer"]:
        src_folder = BASE_DIR / folder
        if src_folder.exists():
            shutil.copytree(src_folder, source_code / folder, dirs_exist_ok=True)

    for f_name in ["README.md", "requirements.txt", "scene_schema.json"]:
        src_file = BASE_DIR / f_name
        if src_file.exists():
            shutil.copy(src_file, source_code / f_name)

    # 3. Export pip freeze environment
    env_txt = BACKUP_DIR / "environment.txt"
    try:
        reqs = subprocess.check_output([sys.executable, "-m", "pip", "freeze"]).decode("utf-8")
        env_txt.write_text(reqs)
        print("Generated environment.txt via pip freeze.")
    except Exception as e:
        print(f"Warning: pip freeze failed: {e}")

    # 4. Create ZIP archive
    zip_path = BASE_DIR / "backup_bundle"
    shutil.make_archive(str(zip_path), "zip", BACKUP_DIR)

    print(f"\nRelease backup completed successfully.")
    print(f"Backup folder: {BACKUP_DIR}")
    print(f"Backup zip:    {zip_path}.zip")


if __name__ == "__main__":
    create_backup()
