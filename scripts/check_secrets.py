"""Heuristic secret audit of the Git index, or distributable source files.

Never prints matching values. Does not inspect Git history.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "data", "outputs", "build", "dist"}
PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(rb"(?i)(?:api[_-]?key|token|secret|password)\s*[:=]\s*[\"']?([A-Za-z0-9_+/=-]{16,})"),
]


def suspicious(path, content):
    name = Path(path).name.lower()
    forbidden = (name == ".env" or (name.startswith(".env.") and name != ".env.example")
                 or name.endswith((".pem", ".key")) or name in {"kaggle.json", "credentials.json"}
                 or "service-account" in name)
    return forbidden or any(pattern.search(content) for pattern in PATTERNS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tree", action="store_true", help="Audit source files before Git initialization")
    args = parser.parse_args()
    findings = []
    count = 0
    if args.source_tree:
        entries = [(str(p.relative_to(ROOT)), p.read_bytes()) for p in ROOT.rglob("*")
                   if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP)
                   and not any(part.endswith(".egg-info") for part in p.relative_to(ROOT).parts)]
    else:
        try:
            git_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
            if Path(git_root).resolve() != ROOT.resolve():
                raise RuntimeError("Initialize a Git repository in this template first")
            paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
            entries = [(p, subprocess.check_output(["git", "show", ":" + p], cwd=ROOT)) for p in paths if p]
            if not entries:
                raise RuntimeError("Git index is empty; run git add before checking")
        except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError) as error:
            print(f"Audit unavailable: {error}. Use --source-tree for an unversioned template.", file=sys.stderr)
            return 2
    for path, content in entries:
        count += 1
        if suspicious(path, content):
            findings.append(path)
    if findings:
        print("Potential secrets or sensitive files (values hidden):")
        print("\n".join(findings))
        return 1
    print(f"OK: {count} files checked; no recognized secret pattern. History not checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
