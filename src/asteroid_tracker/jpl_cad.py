"""NASA/JPL SBDB Close-Approach Data API client."""

from __future__ import annotations

import json
from pathlib import Path

import requests

from .paths import child_path, directories

DEFAULT_USER_AGENT = (
    "AsteroidTracker/0.1 "
    "(https://github.com/DedeAssann/asteroid_tracker)"
)


def validate_payload(payload, expected_version="1.5"):
    signature = payload.get("signature") or {}
    version = str(signature.get("version", ""))

    if version != str(expected_version):
        raise ValueError(
            f"Unsupported JPL CAD API version {version!r}; "
            f"expected {expected_version!r}"
        )

    count = int(payload.get("count", 0))
    if count and ("fields" not in payload or "data" not in payload):
        raise ValueError("Malformed JPL CAD payload: missing fields/data")

    return payload


def fetch_close_approaches(config, timeout=30):
    settings = config.get("jpl_cad", {})
    endpoint = settings.get(
        "endpoint",
        "https://ssd-api.jpl.nasa.gov/cad.api",
    )
    query = dict(settings.get("query", {}))

    response = requests.get(
        endpoint,
        params=query,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()

    payload = response.json()
    return validate_payload(
        payload,
        expected_version=settings.get("expected_version", "1.5"),
    )


def download_close_approaches(config, force=False):
    data_dir, _ = directories(config)
    filename = config.get("pipeline", {}).get(
        "raw_json",
        "cad_close_approaches.json",
    )
    target = child_path(data_dir / "raw", filename)

    if target.exists() and not force:
        raise FileExistsError(
            f"File already exists: {target}; use --force to replace it"
        )

    payload = fetch_close_approaches(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return target
