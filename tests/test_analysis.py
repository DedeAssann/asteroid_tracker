"""Deterministic offline checks of units, ranking, provenance and the CLI."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from asteroid_tracker.analysis import analyze_csv, analyze_frame, au_to_ld
from asteroid_tracker.plotting import plot_closest_approaches


@pytest.mark.parametrize("au, expected", [(0, 0), (1, 389.1724003642039),
                                         (384400 / 149597870.7, 1)])
def test_unit_conversion(au, expected):
    """Anchor the conversion to independent numerical reference values."""
    assert au_to_ld(au) == pytest.approx(expected, rel=1e-12)


def test_nominal_and_asymmetric_bounds_use_au_not_cached_ld():
    """All three scientific values must be converted independently from au."""
    result = analyze_frame(pd.DataFrame([{
        "dist": 1, "dist_min": 0.5, "dist_max": 3, "distance_ld": 999,
    }]))["top_10"][0]
    assert result["distance_ld"] == pytest.approx(389.1724003642039)
    assert result["distance_min_3sigma_ld"] == pytest.approx(194.58620018210195)
    assert result["distance_max_3sigma_ld"] == pytest.approx(1167.5172010926117)


def test_top_ten_and_ties_are_deterministic_without_mutation():
    """Designation, date and original record order resolve tied distances."""
    frame = pd.DataFrame([
        {"des": "B", "dist": 1, "jd": 2},
        {"des": "A", "dist": 1, "jd": 3},
        {"des": "A", "dist": 1, "jd": 2},
        {"des": "A", "dist": 1, "jd": 2},
        *({"des": str(i), "dist": i} for i in range(2, 15)),
    ])
    original = frame.copy(deep=True)
    summary = analyze_frame(frame)
    assert summary == analyze_frame(frame)
    pd.testing.assert_frame_equal(frame, original)
    assert summary["records_rankable"] == 17
    assert len(summary["top_10"]) == 10
    assert [r["source_record"] for r in summary["top_10"][:4]] == [3, 4, 2, 1]
    assert [r["distance_au"] for r in summary["top_10"]] == [1, 1, 1, 1, 2, 3, 4, 5, 6, 7]


def test_null_invalid_and_partial_bounds():
    """Missing and malformed values are counted, never ranked as zero."""
    frame = pd.DataFrame([
        {"dist": None}, {"dist": "bad"}, {"dist": "inf"}, {"dist": -1},
        {"dist": 0, "des": None, "fullname": None, "dist_max": 1},
        {"dist": 2, "dist_min": 3, "dist_max": 1},
    ])
    result = analyze_frame(frame)
    assert result["records_analyzed"] == 6
    assert result["records_rankable"] == 2
    assert result["records_excluded_missing_or_invalid_distance"] == 4
    assert result["missing_value_counts"]["dist"] == 1
    assert result["missing_value_counts"]["dist_min"] == 5
    assert result["invalid_numeric_counts"]["dist"] == 3
    assert result["records_with_inconsistent_bounds"] == 1
    assert result["top_10"][0]["display_name"] == "Record 5"
    assert result["top_10"][0]["distance_min_3sigma_ld"] is None
    assert result["top_10"][0]["distance_max_3sigma_ld"] is not None
    assert not result["top_10"][1]["bounds_consistent"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("content", ["", "\n", "des,dist,dist_min,dist_max\n"])
def test_empty_csv_and_provenance(tmp_path, content):
    """Support both normal header-only CSVs and v0.1's blank zero-row CSV."""
    path = tmp_path / "empty.csv"
    path.write_bytes(content.encode())
    result = analyze_csv(path)
    assert result["records_analyzed"] == 0
    assert result["top_10"] == []
    assert result["input_provenance"]["sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert result["query_context"] is None
    assert all(count == 0 for count in result["missing_value_counts"].values())


def test_missing_schema_and_missing_input(tmp_path):
    """A malformed nonempty CSV or missing file must not silently look empty."""
    with pytest.raises(ValueError, match="dist"):
        analyze_frame(pd.DataFrame([{"des": "A"}]))
    with pytest.raises(FileNotFoundError):
        analyze_csv(tmp_path / "absent.csv")


def test_csv_preserves_designation_and_hash(tmp_path):
    """Identifier strings and original bytes remain traceable."""
    path = tmp_path / "data.csv"
    content = b"des,dist,dist_min,dist_max\n0001,1,,2\n"
    path.write_bytes(content)
    result = analyze_csv(path)
    assert result["top_10"][0]["designation"] == "0001"
    assert result["missing_value_counts"]["dist_min"] == 1
    assert result["input_provenance"]["sha256"] == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("rows", [[], [{"dist": None}], [{"dist": 1}],
                                    [{"dist": 1, "dist_min": 0.5, "dist_max": 2}],
                                    [{"dist": 1, "dist_min": 2, "dist_max": 0}]])
def test_plot_handles_empty_missing_and_inconsistent_bounds(tmp_path, rows):
    """The headless plot must produce a PNG for every supported data condition."""
    summary = analyze_frame(pd.DataFrame(rows))
    before = json.dumps(summary, sort_keys=True)
    destination = plot_closest_approaches(summary, tmp_path / "figures" / "plot.png")
    assert destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert json.dumps(summary, sort_keys=True) == before


def test_manage_analyze_offline_and_repeatable(tmp_path):
    """Exercise the public command from another directory with network disabled."""
    root = Path(__file__).resolve().parents[1]
    data = tmp_path / "data" / "processed"
    data.mkdir(parents=True)
    (data / "cad_close_approaches.csv").write_text(
        "des,dist,dist_min,dist_max,cd\nB,0.02,,,2030-Jan-01\nA,0.01,0.009,0.012,2030-Jan-02\n",
        encoding="utf-8",
    )
    # sitecustomize is loaded in both command interpreters and blocks sockets.
    (tmp_path / "sitecustomize.py").write_text(
        "import socket\ndef blocked(*a, **k):\n    raise AssertionError('Network forbidden')\n"
        "socket.socket.connect = blocked\nsocket.socket.connect_ex = blocked\nsocket.create_connection = blocked\n", encoding="utf-8")
    env = dict(os.environ, SCI_DATA_DIR=str(tmp_path / "data"),
               SCI_OUTPUT_DIR=str(tmp_path / "outputs"),
               PYTHONPATH=os.pathsep.join([str(tmp_path), str(root / "src")]))
    command = [sys.executable, str(root / "manage.py"), "analyze", "--current"]
    subprocess.run(command, cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    path = tmp_path / "outputs" / "analysis_summary.json"
    first = path.read_bytes()
    result = json.loads(first)
    assert result["records_analyzed"] == 2
    assert result["top_10"][0]["designation"] == "A"
    assert result["query_context"]["verified_for_input"] is False
    assert result["query_context"]["query"]["body"] == "Earth"
    assert (tmp_path / "outputs" / "figures" / "closest_approaches.png").is_file()
    subprocess.run(command, cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    assert path.read_bytes() == first
