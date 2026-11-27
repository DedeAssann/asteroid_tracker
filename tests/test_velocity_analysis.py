"""Offline numerical, completeness, rendering and public-command regression tests."""

import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from asteroid_tracker.velocity_analysis import (
    analyze_velocity_frame, energy_residual, nonnegative_number,
)
from asteroid_tracker.velocity_plotting import velocity_figures


@pytest.mark.parametrize("value, state", [
    (None, "missing"), ("", "missing"), ("null", "missing"), (pd.NA, "missing"),
    ("garbage", "nonnumeric"), (True, "nonnumeric"), (-1, "negative"),
    (float("nan"), "nonfinite"), ("NaN", "nonfinite"), ("inf", "nonfinite"),
    ("-Infinity", "nonfinite"), (0, "valid"), ("2.5", "valid"),
])
def test_explicit_value_classification(value, state):
    """Malformed, missing, nonfinite and negative inputs are distinct categories."""
    number, actual = nonnegative_number(value)
    assert actual == state
    assert (number is not None) == (state == "valid")


def test_independent_energy_reference_and_units():
    """At r=797200.8836 km, 2*mu/r is 1 km²/s²: R=25-16-1=8."""
    distance = 797200.8836 / 149597870.7
    assert energy_residual(distance, 5, 4) == pytest.approx(8, abs=1e-12)
    assert energy_residual(distance, math.sqrt(17), 4) == pytest.approx(0, abs=1e-12)
    assert energy_residual(distance, 3, 4) == pytest.approx(-8, abs=1e-12)
    assert energy_residual(distance, 0, 0) == pytest.approx(-1)
    # Verify a direct au-to-km conversion independently at one au.
    assert energy_residual(1, 5, 4) == pytest.approx(9 - 797200.8836 / 149597870.7)


@pytest.mark.parametrize("distance, relative, infinity", [
    (0, 1, 1), (-1, 1, 1), (1, -1, 1), (1, 1, None),
    (1, float("inf"), 1), (1e308, 1, 1), (1, 1e308, 1),
])
def test_energy_rejects_unusable_inputs(distance, relative, infinity):
    """Do not hide undefined radius or overflow behind a fabricated residual."""
    with pytest.raises(ValueError):
        energy_residual(distance, relative, infinity)


def test_all_events_statistics_and_pairwise_populations():
    """Use more than ten rows, preserve duplicates, and avoid listwise deletion."""
    rows = [{"dist": 1, "v_rel": i, "v_inf": i, "body": "Earth"} for i in range(12)]
    rows += [{"v_rel": 20}, {"dist": 2, "v_inf": 30}, {"dist": 0, "v_rel": 0, "v_inf": 0}]
    frame = pd.DataFrame(rows, dtype=object)
    original = frame.copy(deep=True)
    summary = analyze_velocity_frame(frame)
    pd.testing.assert_frame_equal(frame, original)
    assert summary == analyze_velocity_frame(frame)
    assert summary["records_analyzed"] == 15
    assert summary["samples"] == {"velocity_distribution": 14, "distance_vs_velocity": 13,
                                  "relative_vs_infinity_velocity": 13}
    stats = summary["statistics"]["v_rel_km_s"]
    assert stats == {"count": 14, "minimum": 0, "maximum": 20, "median": 5.5, "mean": 86 / 14}
    assert summary["events"][0]["distance_ld"] == pytest.approx(389.1724003642039)
    assert sum(summary["velocity_histogram"]["counts"]) == 14
    assert all(sum(counts.values()) == 15 for counts in summary["completeness"].values())


def test_body_selection_assumption_and_skip_reasons():
    """Current config is not evidence; explicit bodies always override assumptions."""
    rows = [
        {"body": " Earth ", "dist": 1, "v_rel": 3, "v_inf": 4},
        {"body": "Mars", "dist": 1, "v_rel": 3, "v_inf": 4},
        {"body": "", "dist": 1, "v_rel": 3, "v_inf": 4},
        {"body": "Earth", "dist": 0, "v_rel": 0, "v_inf": 0},
        {"body": "Earth", "dist": -1, "v_rel": 3, "v_inf": 4},
        {"body": "Earth", "dist": 1, "v_rel": 1e308, "v_inf": 4},
    ]
    summary = analyze_velocity_frame(pd.DataFrame(rows))
    assert [e["energy_status"] for e in summary["events"]] == [
        "evaluated", "non_earth", "unknown_body", "zero_distance",
        "missing_or_invalid_input", "numerical_range_error"]
    energy = summary["energy_consistency"]
    assert energy["records_evaluated"] == 1
    assert energy["records_skipped"] == 5
    assert energy["earth_evaluated_v_rel_below_v_inf"] == 1
    assert energy["residual_statistics"]["minimum"] < 0
    assumed = analyze_velocity_frame(pd.DataFrame(rows), assume_body="Earth")
    assert assumed["assumed_body_records"] == 1
    assert assumed["energy_consistency"]["records_evaluated"] == 2
    assert assumed["events"][1]["energy_status"] == "non_earth"
    json.dumps(summary, allow_nan=False)


def test_missing_columns_invalid_data_and_empty_samples():
    """Absent observables are reported as missing rather than synthesized."""
    summary = analyze_velocity_frame(pd.DataFrame({"v_rel": ["", "bad", "inf", "-2"]}))
    assert summary["completeness"]["v_rel"] == {
        "valid": 0, "missing": 1, "nonnumeric": 1, "nonfinite": 1, "negative": 1}
    assert summary["completeness"]["v_inf"]["missing"] == 4
    assert summary["statistics"]["v_rel_km_s"]["median"] is None
    assert summary["samples"]["velocity_distribution"] == 0
    with pytest.raises(ValueError, match="at least one"):
        analyze_velocity_frame(pd.DataFrame({"unrelated": [1]}))
    with pytest.raises(ValueError, match="Earth"):
        analyze_velocity_frame(pd.DataFrame(), assume_body="Mars")


@pytest.mark.parametrize("rows", [[], [{"v_rel": "invalid"}], [{"v_rel": 0, "v_inf": 0, "dist": 0}],
                                    [{"v_rel": 5, "v_inf": 4, "dist": 0.01}] * 12])
def test_headless_plots_and_reference_line(rows):
    """Render all three PNGs and inspect labels, populations and the 1:1 line."""
    summary = analyze_velocity_frame(pd.DataFrame(rows))
    before = json.dumps(summary, sort_keys=True)
    figures = velocity_figures(summary)
    assert set(figures) == {"velocity_distribution.png", "distance_vs_velocity.png",
                            "relative_vs_infinity_velocity.png"}
    for figure in figures.values():
        stream = BytesIO()
        figure.savefig(stream, format="png")
        assert stream.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
    comparison = figures["relative_vs_infinity_velocity.png"].axes[0]
    line = next(line for line in comparison.lines if line.get_label() == "1:1 reference")
    assert list(line.get_xdata()) == list(line.get_ydata())
    assert comparison.get_xlabel() == "Infinity velocity (km/s)"
    assert comparison.get_ylabel() == "Relative velocity (km/s)"
    if summary["samples"]["relative_vs_infinity_velocity"]:
        assert len(comparison.collections[0].get_offsets()) == summary["samples"]["relative_vs_infinity_velocity"]
    scatter = figures["distance_vs_velocity.png"].axes[0]
    if summary["samples"]["distance_vs_velocity"]:
        assert len(scatter.collections[0].get_offsets()) == summary["samples"]["distance_vs_velocity"]
    distribution = figures["velocity_distribution.png"].axes[0]
    if summary["samples"]["velocity_distribution"]:
        assert "Median =" in distribution.texts[0].get_text()
        assert "Range =" in distribution.texts[0].get_text()
    else:
        assert "No valid" in distribution.texts[0].get_text()
    assert json.dumps(summary, sort_keys=True) == before
    for figure in figures.values():
        figure.clear()


@pytest.mark.parametrize("content", [b"", b"des,dist,v_rel,v_inf\n",
    b"des,dist,v_rel,v_inf,body\n0001,0.01,5,4,Earth\n0002,0.02,6,,\n0003,0.03,NaN,inf,Mars\n"])
def test_cli_offline_provenance_repeatability_and_preserved_outputs(tmp_path, content):
    """Exercise the real command with blocked networking and redirected paths."""
    root = Path(__file__).resolve().parents[1]
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    csv = processed / "custom.csv"
    csv.write_bytes(content)
    config = tmp_path / "settings.yaml"
    config.write_text("pipeline:\n  processed_csv: custom.csv\njpl_cad:\n  query:\n    body: Earth\n", encoding="utf-8")
    output = tmp_path / "outputs"
    (output / "figures").mkdir(parents=True)
    # Existing artifacts must remain byte-for-byte unchanged.
    old = [output / "summary.json", output / "analysis_summary.json", output / "figures" / "closest_approaches.png"]
    for path in old:
        path.write_bytes(b"existing artifact")
    (tmp_path / "sitecustomize.py").write_text(
        "import socket\ndef blocked(*a, **k):\n    raise AssertionError('Network forbidden')\n"
        "socket.socket.connect = blocked\nsocket.socket.connect_ex = blocked\nsocket.create_connection = blocked\n",
        encoding="utf-8")
    env = dict(os.environ, SCI_DATA_DIR=str(tmp_path / "data"), SCI_OUTPUT_DIR=str(output),
               MPLCONFIGDIR=str(tmp_path / "mpl"),
               PYTHONPATH=os.pathsep.join([str(tmp_path), str(root / "src")]))
    command = [sys.executable, str(root / "manage.py"), "analyze-velocity", "--current",
               "--config", str(config)]
    subprocess.run(command, cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    target = output / "velocity_analysis_summary.json"
    first = target.read_bytes()
    summary = json.loads(first)
    assert summary["input_provenance"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert summary["input_provenance"]["size_bytes"] == len(content)
    assert summary["assumed_body_records"] == 0
    assert summary["query_context"]["verified_for_input"] is False
    if summary["records_analyzed"]:
        assert summary["events"][0]["designation"] == "0001"
        assert summary["events"][1]["energy_status"] == "unknown_body"
        assert summary["completeness"]["v_rel"]["nonfinite"] == 1
    subprocess.run(command, cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    assert target.read_bytes() == first
    subprocess.run([*command, "--assume-body", "Earth"], cwd=tmp_path, env=env,
                   check=True, capture_output=True, text=True)
    assert json.loads(target.read_bytes())["assume_body"] == "Earth"
    assert csv.read_bytes() == content
    assert all(path.read_bytes() == b"existing artifact" for path in old)
    assert len(list((output / "figures").glob("*.png"))) == 4
    # Missing input fails without fetching a replacement.
    csv.unlink()
    failed = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert failed.returncode != 0
    assert "No download was attempted" in failed.stderr
