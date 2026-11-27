"""Offline scientific calculations for the first v0.2 analysis increment.

Each row is an encounter, not a unique object. Distances describe geometry;
this module deliberately does not infer impact probability or danger.
"""

from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path

import pandas as pd

from .pipeline import AU_KM, LUNAR_DISTANCE_KM
from .provenance import analysis_input_provenance, historical_query_context

DISTANCE_FIELDS = ("dist", "dist_min", "dist_max")
TEXT_FIELDS = ("des", "fullname", "cd", "orbit_id", "body")
ANALYSIS_FIELDS = (*TEXT_FIELDS, "jd", *DISTANCE_FIELDS)
RANKING_RULE = "dist ascending, des lexical, jd ascending, cd, orbit_id, body, source_record"


def _text(value):
    """Normalize absent labels without ever displaying the string 'nan'."""
    return None if pd.isna(value) or not str(value).strip() else str(value).strip()


def _number(value):
    """Accept finite numeric values only; JSON cannot represent NaN/infinity."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def au_to_ld(value):
    """Convert au using the same fixed mean lunar distance as the v0.1 pipeline."""
    number = _number(value)
    return None if number is None else number * AU_KM / LUNAR_DISTANCE_KM


def analyze_frame(frame):
    """Rank at most ten encounters without modifying the supplied DataFrame.

    Missing/invalid nominal distances exclude a row from the ranking. Bounds
    are optional and never imputed. Original record order breaks exact ties.
    """
    if len(frame) and "dist" not in frame.columns:
        raise ValueError("Processed CSV must contain the nominal distance column 'dist' (au)")

    # Count missing cells separately from nonempty, unusable numeric values.
    missing = {}
    invalid = {field: 0 for field in (*DISTANCE_FIELDS, "jd")}
    for field in sorted(set(frame.columns) | set(ANALYSIS_FIELDS)):
        values = frame[field] if field in frame else [None] * len(frame)
        missing[field] = sum(_text(value) is None for value in values)

    encounters = []
    inconsistent_bounds = 0
    for position, row in enumerate(frame.to_dict(orient="records"), start=1):
        numbers = {}
        for field in invalid:
            raw = row.get(field)
            value = _number(raw)
            if value is not None and field in DISTANCE_FIELDS and value < 0:
                value = None
            if value is None and _text(raw) is not None:
                invalid[field] += 1
            numbers[field] = value

        nominal, lower, upper = (numbers[field] for field in DISTANCE_FIELDS)
        # Retain reported finite bounds, but flag physically inconsistent pairs.
        bad_bounds = (
            (lower is not None and upper is not None and lower > upper)
            or (nominal is not None and lower is not None and lower > nominal)
            or (nominal is not None and upper is not None and upper < nominal)
        )
        inconsistent_bounds += int(bad_bounds)
        if nominal is None:
            continue
        labels = {field: _text(row.get(field)) for field in TEXT_FIELDS}
        encounters.append({
            "source_record": position,
            "designation": labels["des"],
            "display_name": labels["fullname"] or labels["des"] or f"Record {position}",
            "calendar_date_tdb": labels["cd"],
            "jd_tdb": numbers["jd"],
            "orbit_id": labels["orbit_id"],
            "body": labels["body"],
            "distance_au": nominal,
            "distance_ld": au_to_ld(nominal),
            "distance_min_3sigma_ld": au_to_ld(lower),
            "distance_max_3sigma_ld": au_to_ld(upper),
            "bounds_consistent": not bad_bounds,
        })

    # Missing tie-break labels/dates sort last. Lexical designation order avoids
    # assumptions about numbered versus provisional asteroid designations.
    encounters.sort(key=lambda item: (
        item["distance_au"], item["designation"] is None, item["designation"] or "",
        item["jd_tdb"] if item["jd_tdb"] is not None else math.inf,
        item["calendar_date_tdb"] or "", item["orbit_id"] or "",
        item["body"] or "", item["source_record"],
    ))
    top = [dict(item, rank=rank) for rank, item in enumerate(encounters[:10], start=1)]
    return {
        "schema_version": "0.2",
        "records_analyzed": len(frame),
        "records_rankable": len(encounters),
        "records_excluded_missing_or_invalid_distance": len(frame) - len(encounters),
        "records_ranked": len(top),
        "missing_value_counts": missing,
        "invalid_numeric_counts": invalid,
        "records_with_inconsistent_bounds": inconsistent_bounds,
        "ranking_rule": RANKING_RULE,
        "units": {"input_distance": "au", "output_distance": "LD",
                  "au_km": AU_KM, "lunar_distance_km": LUNAR_DISTANCE_KM},
        "interpretation": "Closest encounters in this input only; not a danger score or impact probability.",
        "top_10": top,
    }


def analyze_csv(path, query_context=None):
    """Read one local snapshot and hash exactly the bytes used for analysis."""
    path = Path(path)
    content = path.read_bytes()
    try:
        # Keep identifiers as text (e.g. leading zeros); convert numbers explicitly.
        frame = pd.read_csv(BytesIO(content), dtype=str)
    except pd.errors.EmptyDataError:
        # v0.1 writes a blank CSV for a zero-record response.
        frame = pd.DataFrame()
    result = analyze_frame(frame)
    result["input_provenance"] = analysis_input_provenance(
        path, content, frame, "1-based data record, excluding the header",
    )
    result["query_context"] = historical_query_context(result["input_provenance"], query_context)
    return result
