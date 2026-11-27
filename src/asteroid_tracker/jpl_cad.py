"""NASA/JPL SBDB Close-Approach Data API client."""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from .paths import child_path, directories
from .provenance import (
    CAD_SOURCE, SCHEMA_VERSION, acquisition_for_raw, artifact_record,
    artifact_writer, publish_artifact, recover_receipt, utc_timestamp,
)

DEFAULT_USER_AGENT = (
    "AsteroidTracker/0.1 "
    "(https://github.com/DedeAssann/asteroid_tracker)"
)
DEFAULT_ENDPOINT = "https://ssd-api.jpl.nasa.gov/cad.api"

# Only public, documented CAD query parameter values are safe to retain.
PUBLIC_QUERY_FIELDS = frozenset("""
    date-min date-max dist-min dist-max min-dist-min min-dist-max h-min h-max
    v-inf-min v-inf-max v-rel-min v-rel-max class pha nea comet nea-comet neo
    kind spk des body sort limit limit-from total-only diameter fullname
""".split())


def _record_count(payload):
    value = payload.get("count")
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    # CAD total-only responses can omit count and contain only a match total.
    total = payload.get("total")
    if "count" not in payload and type(total) is int and total >= 0:
        return 0
    raise ValueError("Malformed JPL CAD payload: invalid record count")


def validate_payload(payload, expected_version="1.5"):
    if not isinstance(payload, dict) or not isinstance(payload.get("signature"), dict):
        raise ValueError("Malformed JPL CAD payload: missing signature")
    version = str(payload["signature"].get("version", ""))

    if version != str(expected_version):
        raise ValueError(
            f"Unsupported JPL CAD API version {version!r}; "
            f"expected {expected_version!r}"
        )

    count = _record_count(payload)
    rows = payload.get("data", [])
    fields = payload.get("fields", [])
    if (
        not isinstance(rows, list) or len(rows) != count
        or not isinstance(fields, list)
        or (count and not fields)
        or any(not isinstance(field, str) for field in fields)
        or len(fields) != len(set(fields))
        or any(not isinstance(row, list) or len(row) != len(fields) for row in rows)
    ):
        raise ValueError("Malformed JPL CAD payload: record count or fields/data are inconsistent")
    return payload


def _safe_parameters(pairs):
    return [(key, value if key in PUBLIC_QUERY_FIELDS else "[redacted]") for key, value in pairs]


def _safe_url(url):
    parts = urlsplit(url)
    pairs = _safe_parameters(parse_qsl(parts.query, keep_blank_values=True))
    return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1],
                       parts.path, urlencode(pairs), ""))


def unverified_configuration(settings):
    """Preserve old report context without publishing configured credentials."""
    if not settings:
        return settings
    return {
        **({"expected_version": settings["expected_version"]} if "expected_version" in settings else {}),
        "endpoint": _safe_url(settings["endpoint"]) if settings.get("endpoint") else None,
        "query": dict(_safe_parameters((settings.get("query") or {}).items())),
    }


def _request_parameters(url):
    pairs = _safe_parameters(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    return [{"name": key, "value": value} for key, value in pairs]


def _relative_dates(parameters):
    return [
        item for item in parameters
        if item["name"] in ("date-min", "date-max")
        and re.fullmatch(r"now|[+-]\d+", item["value"], re.IGNORECASE)
    ]


def _request_details(response):
    initial = response.history[0].request if response.history else response.request
    parts = urlsplit(initial.url)
    parameters = _request_parameters(initial.url)
    final_url = response.request.url
    return {
        "endpoint": _safe_url(urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))),
        "parameters": parameters,
        "final_url": _safe_url(final_url),
        "relative_date_inputs": _relative_dates(parameters),
        "final_relative_date_inputs": _relative_dates(_request_parameters(final_url)),
    }


def _fetch_response(config, timeout):
    settings = config.get("jpl_cad", {})
    response = requests.get(
        settings.get("endpoint", DEFAULT_ENDPOINT),
        params=dict(settings.get("query", {})),
        headers={"User-Agent": DEFAULT_USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    # Parse the exact bytes that will be archived.
    payload = validate_payload(json.loads(response.content),
                               settings.get("expected_version", "1.5"))
    return response, payload


def fetch_close_approaches(config, timeout=30):
    """Fetch and validate a CAD payload without writing files."""
    _, payload = _fetch_response(config, timeout)
    return payload


def acquire_close_approaches(config, force=False):
    """Return the raw path and cache status while preserving the original receipt."""
    data_dir, _ = directories(config)
    filename = config.get("pipeline", {}).get("raw_json", "cad_close_approaches.json")
    target = child_path(data_dir / "raw", filename)

    with artifact_writer(target):
        if target.exists() and not force:
            content = target.read_bytes()
            verification = acquisition_for_raw(target, artifact_record(target, content))
            try:
                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise ValueError("Expected a JSON object")
            except ValueError as error:
                raise ValueError(f"Corrupted raw cache: {target}. Restore it or use download --force.") from error
            if verification["status"] == "verified":
                metadata = verification["metadata"]
                validate_payload(payload, metadata["api_version"])
                if _record_count(payload) != metadata["record_count"]:
                    raise ValueError("Raw cache integrity error: acquisition record count mismatch.")
            recover_receipt(target, "acquisition", verification)
            return {"path": target, "download_status": "cache_hit",
                    "acquisition_metadata_status": verification["status"]}

        response, payload = _fetch_response(config, timeout=30)
        content = response.content
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "kind": "acquisition",
            "source": CAD_SOURCE,
            "download_status": "new_acquisition",
            "acquired_at_utc": utc_timestamp(),
            "request": _request_details(response),
            "api_version": str(payload["signature"]["version"]),
            "record_count": _record_count(payload),
            "raw": artifact_record(target, content),
        }
        publish_artifact(target, content, "acquisition", metadata)
        return {"path": target, "download_status": "new_acquisition",
                "acquisition_metadata_status": "verified"}


def download_close_approaches(config, force=False):
    """Return the raw JSON path for existing Python callers."""
    return acquire_close_approaches(config, force)["path"]
