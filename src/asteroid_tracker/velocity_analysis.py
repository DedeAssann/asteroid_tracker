"""Pure, deterministic encounter kinematics; no file I/O or plotting.

Populations are selected per observable, so a missing distance does not discard
an otherwise usable velocity. Each CSV row remains a separate encounter.
"""

from bisect import bisect_right
from collections import Counter
import math

import pandas as pd

from .pipeline import AU_KM, LUNAR_DISTANCE_KM

MU_EARTH_KM3_S2 = 398600.4418
FIELDS = ("dist", "v_rel", "v_inf")
STATES = ("valid", "missing", "nonnumeric", "nonfinite", "negative")


def text_or_none(value):
    """Normalize scalar labels and explicit null tokens from a text CSV."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return None if text.lower() in ("", "null", "none", "na", "n/a") else text


def nonnegative_number(value):
    """Return a usable scalar and a mutually exclusive completeness category."""
    # Actual NaN and textual NaN/Infinity are nonfinite, not invented zeros.
    if isinstance(value, float) and not math.isfinite(value):
        return None, "nonfinite"
    text = text_or_none(value)
    if text is None:
        return None, "missing"
    try:
        number = float(text)
    except (ValueError, TypeError, OverflowError):
        return None, "nonnumeric"
    if not math.isfinite(number):
        return None, "nonfinite"
    if number < 0:
        return None, "negative"
    return number, "valid"


def descriptive_statistics(values):
    """Describe the observed sample without distributional or error assumptions."""
    values = sorted(values)
    count = len(values)
    if not count:
        return dict(count=0, minimum=None, maximum=None, median=None, mean=None)
    middle = count // 2
    # Halving before adding avoids overflow for large finite values.
    median = values[middle] if count % 2 else values[middle - 1] / 2 + values[middle] / 2
    return dict(count=count, minimum=values[0], maximum=values[-1], median=median,
                mean=math.fsum(value / count for value in values))


def energy_residual(distance_au, v_rel, v_inf):
    """Compute R in km²/s² for validated scalars and positive radius.

    r is center-to-center distance, not altitude. This diagnostic assumes a
    massless small body in an isolated Earth two-body hyperbolic encounter.
    """
    parsed = [nonnegative_number(value) for value in (distance_au, v_rel, v_inf)]
    if any(state != "valid" for _, state in parsed):
        raise ValueError("Energy inputs must be finite nonnegative numbers")
    distance_au, v_rel, v_inf = (value for value, _ in parsed)
    if distance_au <= 0:
        raise ValueError("Energy radius must be strictly positive")
    radius = distance_au * AU_KM
    if not math.isfinite(radius) or radius == 0:
        raise ValueError("Radius outside floating-point range")
    # Multiplication (rather than exponentiation) lets us detect overflow as inf.
    gravitational_term = 2 * MU_EARTH_KM3_S2 / radius
    residual = v_rel * v_rel - v_inf * v_inf - gravitational_term
    if not math.isfinite(residual):
        raise ValueError("Residual outside floating-point range")
    return residual


def _histogram(values):
    """Use ten deterministic equal-width bins from zero to the sample maximum."""
    if not values:
        return {"edges_km_s": [], "counts": []}
    upper = max(values) or 1.0  # Give an all-zero sample a visible finite bin.
    edges = [upper * (index / 10) for index in range(11)]
    counts = [0] * 10
    for value in values:
        counts[min(9, bisect_right(edges, value) - 1)] += 1
    return {"edges_km_s": edges, "counts": counts}


def analyze_velocity_frame(frame, assume_body=None):
    """Analyze every row; retain explicit reasons for skipped energy checks.

    An explicit Earth assumption fills absent bodies only. Configuration alone
    cannot identify the body of an older cached CSV and is never used here.
    """
    if assume_body not in (None, "Earth"):
        raise ValueError("Only an explicit Earth body assumption is supported")
    if len(frame) and not any(field in frame for field in FIELDS):
        raise ValueError("CSV must contain at least one of dist, v_rel, v_inf")
    completeness = {field: dict.fromkeys(STATES, 0) for field in FIELDS}
    events, statuses = [], Counter()
    for index, row in enumerate(frame.to_dict(orient="records"), start=1):
        values = {}
        for field in FIELDS:
            values[field], state = nonnegative_number(row.get(field))
            completeness[field][state] += 1
        distance, relative, infinity = (values[field] for field in FIELDS)
        body = text_or_none(row.get("body"))
        body_source = "csv" if body else ("explicit_assumption" if assume_body else "unknown")
        body = body or assume_body
        lunar = None if distance is None else distance * (AU_KM / LUNAR_DISTANCE_KM)
        if lunar is not None and not math.isfinite(lunar):
            lunar = None
        # One primary skip reason per encounter, in the documented order below.
        residual = None
        if body is None:
            status = "unknown_body"
        elif body.casefold() != "earth":
            status = "non_earth"
        elif any(value is None for value in values.values()):
            status = "missing_or_invalid_input"
        elif distance == 0:
            status = "zero_distance"
        else:
            try:
                residual = energy_residual(distance, relative, infinity)
                status = "evaluated"
            except ValueError:
                status = "numerical_range_error"
        statuses[status] += 1
        events.append({
            "source_record": index, "designation": text_or_none(row.get("des")),
            "body": body, "body_source": body_source,
            "distance_au": distance, "distance_ld": lunar,
            "v_rel_km_s": relative, "v_inf_km_s": infinity,
            "energy_status": status, "energy_residual_km2_s2": residual,
        })

    # Select independent populations: no top-ten truncation or listwise deletion.
    relative = [e["v_rel_km_s"] for e in events if e["v_rel_km_s"] is not None]
    infinity = [e["v_inf_km_s"] for e in events if e["v_inf_km_s"] is not None]
    distances = [e["distance_ld"] for e in events if e["distance_ld"] is not None]
    distance_pairs = [e for e in events if e["distance_ld"] is not None and e["v_rel_km_s"] is not None]
    velocity_pairs = [e for e in events if e["v_rel_km_s"] is not None and e["v_inf_km_s"] is not None]
    residuals = [e["energy_residual_km2_s2"] for e in events if e["energy_status"] == "evaluated"]
    return {
        "schema_version": "0.2.2", "records_analyzed": len(events),
        "assume_body": assume_body,
        "units": {"au_km": AU_KM, "lunar_distance_km": LUNAR_DISTANCE_KM,
                  "mu_earth_km3_s2": MU_EARTH_KM3_S2},
        "completeness": completeness,
        "distance_ld_conversion_failures": sum(
            e["distance_au"] is not None and e["distance_ld"] is None for e in events),
        "absent_columns": [field for field in (*FIELDS, "body") if field not in frame],
        "body_counts": dict(sorted(Counter(e["body"] or "unknown" for e in events).items())),
        "assumed_body_records": sum(e["body_source"] == "explicit_assumption" for e in events),
        "statistics": {"v_rel_km_s": descriptive_statistics(relative),
                       "v_inf_km_s": descriptive_statistics(infinity),
                       "distance_ld": descriptive_statistics(distances)},
        "samples": {
            "velocity_distribution": len(relative), "distance_vs_velocity": len(distance_pairs),
            "relative_vs_infinity_velocity": len(velocity_pairs)},
        "velocity_histogram": _histogram(relative),
        "energy_consistency": {
            "formula": "R = v_rel^2 - v_inf^2 - 2*mu_E/(dist_au*AU_KM)",
            "units": "km^2/s^2", "status_counts": dict(sorted(statuses.items())),
            "records_evaluated": len(residuals), "records_skipped": len(events) - len(residuals),
            "residual_statistics": descriptive_statistics(residuals),
            "absolute_residual_statistics": descriptive_statistics([abs(r) for r in residuals]),
            "earth_evaluated_v_rel_below_v_inf": sum(
                e["v_rel_km_s"] < e["v_inf_km_s"] for e in events if e["energy_status"] == "evaluated"),
            "interpretation": "Simplified two-body diagnostic; R near zero is expected in that model. "
                              "No physical pass/fail tolerance or uncertainty is assumed. "
                              "Not independent validation of JPL trajectories or an impact-risk score.",
        },
        "events": events,
    }
