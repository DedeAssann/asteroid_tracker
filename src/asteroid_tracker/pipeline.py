"""Normalize JPL CAD data and produce a compact scientific summary."""

from __future__ import annotations

import hashlib
import json

import pandas as pd

from .jpl_cad import validate_payload
from .paths import child_path, directories

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
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    frame = payload_to_dataframe(payload, expected_version)

    processed_path = child_path(
        data_dir / "processed",
        pipeline.get("processed_csv", "cad_close_approaches.csv"),
    )
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(processed_path, index=False)

    summary = {
        "records": int(len(frame)),
        "api_version": str((payload.get("signature") or {}).get("version", "")),
        "input_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
    }

    if not frame.empty:
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
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    return {
        "processed_csv": processed_path,
        "summary_json": summary_path,
        "records": len(frame),
    }
