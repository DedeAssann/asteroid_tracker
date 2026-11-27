"""Offline photometry and JPL catalog diameter coverage."""

from collections import Counter, defaultdict
import math

from .velocity_analysis import nonnegative_number, text_or_none

FIELDS = ("h", "diameter", "diameter_sigma")
HYPOTHETICAL_ALBEDOS = (0.05, 0.14, 0.25)
REFERENCE_H_RANGE = (10, 35)


def photometric_diameter_km(h, geometric_albedo):
    """Return a model estimate for an explicitly supplied geometric albedo."""
    if not math.isfinite(h) or not (0 < geometric_albedo <= 1):
        raise ValueError("Expected finite H and geometric albedo in (0, 1]")
    return 1329 / math.sqrt(geometric_albedo) * 10 ** (-h / 5)


def _classify(raw, field):
    value, state = nonnegative_number(raw)
    # Magnitude is logarithmic and its zero point permits finite negative H.
    if state == "negative" and field == "h":
        return float(raw), "valid"
    if state == "valid" and field == "diameter" and value == 0:
        return None, "zero"
    return value, state


def _identifier(value):
    label = text_or_none(value)
    return None if label is None or label.casefold() == "nan" else label


def _coverage(states, valid_key="known"):
    counts = Counter(states)
    return {
        valid_key: counts["valid"],
        "missing": counts["missing"],
        "invalid": sum(count for state, count in counts.items() if state not in ("valid", "missing")),
    }


def _magnitude_stats(values):
    if not values:
        return dict(count=0, minimum=None, median=None, maximum=None)
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = ordered[middle]
    if len(ordered) % 2 == 0:
        median = ordered[middle - 1] / 2 + median / 2
    return dict(count=len(ordered), minimum=ordered[0], median=median, maximum=ordered[-1])


def analyze_physical_frame(frame):
    """Compute encounter statistics and deduplicated coverage using CSV labels."""
    records = frame.to_dict(orient="records")
    identifiers = [(_identifier(row.get("des")), _identifier(row.get("fullname"))) for row in records]

    # Link a full-name-only row to a designation only when the CSV supports
    # an unambiguous link. Namespace the keys to avoid accidental text matches.
    designations_by_name = defaultdict(set)
    for designation, name in identifiers:
        if designation and name:
            designations_by_name[name].add(designation)

    object_states = defaultdict(set)
    unidentified = 0
    magnitudes = []
    pairs = []
    field_states = {field: Counter() for field in FIELDS}

    for index, (row, (designation, name)) in enumerate(zip(records, identifiers), start=1):
        values = {}
        for field in FIELDS:
            values[field], state = _classify(row.get(field), field)
            field_states[field][state] += 1
            if field == "diameter":
                diameter_state = state

        aliases = designations_by_name.get(name, set())
        if designation:
            object_states[("des", designation)].add(diameter_state)
        elif len(aliases) == 1:
            object_states[("des", next(iter(aliases)))].add(diameter_state)
        elif name and not aliases:
            object_states[("fullname", name)].add(diameter_state)
        else:
            unidentified += 1

        h, diameter, sigma = (values[field] for field in FIELDS)
        if h is not None:
            magnitudes.append(h)
            if diameter is not None:
                # The reported uncertainty stays with the diameter on its own row.
                pairs.append({
                    "source_record": index, "absolute_magnitude_h": h,
                    "catalog_diameter_km": diameter, "reported_diameter_sigma_km": sigma,
                })

    # One valid diameter establishes coverage. Otherwise, retain evidence of
    # an invalid supplied value ahead of rows with missing values.
    object_coverage = _coverage(
        "valid" if "valid" in states else "missing" if states == {"missing"} else "invalid"
        for states in object_states.values()
    )
    return {
        "analysis_version": "0.2.3",
        "encounters": {
            "count": len(records),
            "field_completeness": {
                field: {
                    "column_present": field in frame.columns,
                    **_coverage(states, valid_key="valid" if field != "diameter" else "known"),
                    "invalid_by_reason": {
                        reason: states[reason] for reason in ("negative", "zero", "nonnumeric", "nonfinite")
                    },
                }
                for field, states in field_states.items()
            },
        },
        "identified_objects": {
            "count": len(object_states),
            "encounters_without_resolvable_identifier": unidentified,
            "identifier_rule": "Exact trimmed des, then unambiguous fullname match or fullname-only group.",
            "diameter_coverage": object_coverage,
        },
        "absolute_magnitude": {
            "unit": "mag", "sample": "encounters",
            "statistics": _magnitude_stats(magnitudes), "values": magnitudes,
        },
        "catalog_diameters": {
            "unit": "km", "uncertainty": "reported absolute 1-sigma in km",
            "sample": "encounters with valid H and positive JPL CAD diameter",
            "pair_count": len(pairs),
            "pairs_with_valid_sigma": sum(p["reported_diameter_sigma_km"] is not None for p in pairs),
            "pairs": pairs,
        },
        "hypothetical_photometric_model": {
            "equation": "D_km = 1329 / sqrt(pV) * 10**(-H/5)",
            "diameter_unit": "km", "albedo_unit": "dimensionless",
            "hypothetical_geometric_albedos": list(HYPOTHETICAL_ALBEDOS),
            "reference_h_range_mag": list(REFERENCE_H_RANGE),
            "scope": "Reference curves only; no albedo or photometric diameter assigned to any object.",
        },
        "limitations": [
            "H is absolute magnitude, not apparent brightness at encounter.",
            "Encounter selection, discovery bias and selective diameter follow-up limit representativeness.",
            "The processed CSV may already have converted malformed source values to blanks.",
            "Object counts depend on available labels and do not resolve undocumented aliases.",
        ],
    }
