"""YAML configuration loader."""

import yaml

from .paths import resolve_path


def load_config(path="configs/default.yaml"):
    with resolve_path(path).open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a YAML mapping")

    for section in ("paths", "jpl_cad", "pipeline"):
        if section in config and not isinstance(config[section], dict):
            raise ValueError(f"Section {section} must be a mapping")

    return config
