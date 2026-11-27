"""Cross-platform project commands.

Local Windows/Linux usage prefers a repository-local .venv.
Notebook/cloud runtimes such as Google Colab use the current interpreter instead,
because creating a nested venv there is unnecessary and may fail when ensurepip
is unavailable.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / (
    "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
)


def running_in_colab():
    """Return True when running inside a Google Colab runtime."""
    return bool(
        os.environ.get("COLAB_RELEASE_TAG")
        or os.environ.get("COLAB_BACKEND_VERSION")
        or "google.colab" in sys.modules
    )


def selected_python(force_current=False):
    """Choose the interpreter for project commands."""
    if force_current or running_in_colab():
        return sys.executable
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["setup", "test", "download", "run", "analyze", "analyze-velocity", "check-secrets"],
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Use the current Python (Conda/Colab) instead of .venv",
    )
    args, extra = parser.parse_known_args()

    if args.command == "setup":
        if sys.version_info < (3, 10):
            parser.error("Python 3.10 or newer is required")

        use_current = args.current or running_in_colab()

        if not use_current:
            venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
            python = str(VENV_PYTHON)
        else:
            python = sys.executable

        command = [
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
        ]
    else:
        python = selected_python(force_current=args.current)
        command = {
            "test": ["-m", "pytest"],
            "download": ["scripts/download_data.py"],
            "run": ["scripts/run_pipeline.py"],
            "analyze": ["scripts/analyze_data.py"],
            "analyze-velocity": ["scripts/analyze_velocity.py"],
            "check-secrets": ["scripts/check_secrets.py"],
        }[args.command]

    subprocess.run(
        [python, *command, *extra],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
