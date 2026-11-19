"""Portable project paths."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def resolve_path(value, root=ROOT):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def directories(config):
    settings = config.get("paths", {})
    return (
        resolve_path(os.environ.get("SCI_DATA_DIR") or settings.get("data", "data")),
        resolve_path(
            os.environ.get("SCI_OUTPUT_DIR")
            or settings.get("outputs", "outputs")
        ),
    )


def child_path(directory, name):
    directory = Path(directory).resolve()
    result = (directory / name).resolve()
    if Path(name).is_absolute() or result == directory or directory not in result.parents:
        raise ValueError("Artifact name must stay inside its configured directory")
    return result
