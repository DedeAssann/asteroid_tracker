"""Cross-platform commands; setup creates .venv without shell activation."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["setup", "test", "download", "run", "check-secrets"])
    parser.add_argument("--current", action="store_true", help="Use current Python (Conda/Colab)")
    args, extra = parser.parse_known_args()
    if args.command == "setup":
        if sys.version_info < (3, 10):
            parser.error("Python 3.10 or newer is required")
        if not args.current:
            venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
        python = sys.executable if args.current else str(VENV_PYTHON)
        command = ["-m", "pip", "install", "-r", "requirements.txt"]
    else:
        python = str(VENV_PYTHON) if VENV_PYTHON.exists() and not args.current else sys.executable
        command = {"test": ["-m", "pytest"], "download": ["scripts/download_data.py"],
                   "run": ["scripts/run_pipeline.py"], "check-secrets": ["scripts/check_secrets.py"]}[args.command]
    subprocess.run([python, *command, *extra], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
