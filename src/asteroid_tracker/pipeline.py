"""Normalize JPL CAD data and produce a compact scientific summary."""

from __future__ import annotations

import json
import os
import platform

import pandas as pd

from .jpl_cad import validate_payload
from .paths import child_path, directories
from .provenance import (
    SCHEMA_VERSION, acquisition_for_raw, artifact_record, artifact_writer,
    publish_artifact, utc_timestamp,
)

AU_KM = 149_597_870.7
LUNAR_DISTANCE_KM = 384_400.0


def payload_to_dataframe(payload, expected_version="1.5"):
    validate_payload(payload, expected_version)

    if int(payload.get("count", 0)) == 0:
        return pd.DataFrame()

    frame = pd.DataFrame(payload["data"], columns=payload["fields"])

    numeric_columns = [
        "jd",
        "dist",
        "dist_min",
        "dist_max",
        "v_rel",
        "v_inf",
        "h",
        "diameter",
        "diameter_sigma",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if "fullname" in frame.columns:
        frame["fullname"] = frame["fullname"].astype("string").str.strip()

    if "dist" in frame.columns:
        frame["distance_km"] = frame["dist"] * AU_KM
        frame["distance_ld"] = frame["distance_km"] / LUNAR_DISTANCE_KM

    if "diameter" in frame.columns:
        frame["diameter_m"] = frame["diameter"] * 1000.0

    return frame


def run_pipeline(config):
    data_dir, output_dir = directories(config)
    pipeline = config.get("pipeline", {})
    expected_version = config.get("jpl_cad", {}).get("expected_version", "1.5")

    raw_path = child_path(
        data_dir / "raw",
        pipeline.get("raw_json", "cad_close_approaches.json"),
    )
    with artifact_writer(raw_path):
        raw_content = raw_path.read_bytes()
        raw = artifact_record(raw_path, raw_content)
        acquisition = acquisition_for_raw(raw_path, raw)
    payload = json.loads(raw_content)
    frame = payload_to_dataframe(payload, expected_version)
    api_version = str(payload["signature"]["version"])
    if acquisition["status"] == "verified":
        receipt = acquisition["metadata"]
        if receipt["record_count"] != len(frame) or receipt["api_version"] != api_version:
            raise ValueError("Raw cache integrity error: acquisition version or record count mismatch.")

    processed_path = child_path(
        data_dir / "processed",
        pipeline.get("processed_csv", "cad_close_approaches.csv"),
    )
    # Match the existing Pandas CSV format and hash the same bytes we publish.
    csv_content = frame.to_csv(index=False, lineterminator=os.linesep).encode("utf-8")
    processing = {
        "schema_version": SCHEMA_VERSION,
        "kind": "processing",
        "processed_at_utc": utc_timestamp(),
        "raw": raw,
        "csv": artifact_record(processed_path, csv_content),
        "acquisition": acquisition,
        "record_count": len(frame),
        "configuration": {
            "expected_cad_api_version": str(expected_version),
            "cad_api_version": api_version,
            "csv_encoding": "utf-8",
            "csv_index": False,
            "csv_line_terminator": os.linesep,
            "au_km": AU_KM,
            "lunar_distance_km": LUNAR_DISTANCE_KM,
        },
        "software": {
            "normalization_schema_version": 1,
            "provenance_implementation_version": "0.2.4",
            "python": platform.python_version(),
            "pandas": pd.__version__,
        },
    }

    summary = {
        "records": int(len(frame)),
        "api_version": api_version,
        "input_sha256": raw["sha256"],
    }

    if not frame.empty and {"distance_ld", "cd", "v_rel"} <= set(frame.columns):
        nearest = frame.sort_values("distance_ld").iloc[0]
        summary["nearest"] = {
            "designation": str(nearest.get("fullname") or nearest.get("des")),
            "calendar_date_tdb": str(nearest.get("cd", "")),
            "distance_au": float(nearest["dist"]),
            "distance_km": float(nearest["distance_km"]),
            "distance_lunar": float(nearest["distance_ld"]),
            "relative_velocity_km_s": float(nearest["v_rel"]),
        }

    summary_path = child_path(
        output_dir,
        pipeline.get("summary_json", "summary.json"),
    )
    serialized_summary = json.dumps(summary, indent=2, allow_nan=False) + "\n"
    with artifact_writer(processed_path):
        publish_artifact(processed_path, csv_content, "processing", processing)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(serialized_summary, encoding="utf-8")

    return {
        "processed_csv": processed_path,
        "summary_json": summary_path,
        "records": len(frame),
    }
