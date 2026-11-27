"""Numerical, completeness, headless rendering and offline CLI checks."""

import hashlib
from io import BytesIO
import json
import os
import subprocess
import sys

from matplotlib.backends.backend_agg import FigureCanvasAgg
import pandas as pd
import pytest

from asteroid_tracker.physical_analysis import analyze_physical_frame, photometric_diameter_km
from asteroid_tracker.physical_plotting import physical_figures

FILENAMES = {
    "absolute_magnitude_distribution.png", "diameter_completeness.png",
    "diameter_albedo_sensitivity.png", "h_vs_known_diameter.png",
}


@pytest.mark.parametrize(("h", "albedo", "expected_km"), [
    # At pV=0.25 the square-root denominator is 1/2. Every five
    # magnitudes correspond to a factor of ten in diameter.
    (0, 0.25, 2658),
    (20, 0.25, 0.2658),
    (25, 0.25, 0.02658),
    (20, 0.05, 0.5943468684),
    (20, 0.14, 0.3551901905),
])
def test_photometric_reference_values(h, albedo, expected_km):
    assert photometric_diameter_km(h, albedo) == pytest.approx(expected_km, rel=1e-6)


def test_albedo_is_explicit():
    with pytest.raises(TypeError):
        photometric_diameter_km(20)
    with pytest.raises(ValueError):
        photometric_diameter_km(20, 0)


def test_object_deduplication_and_numeric_status():
    frame = pd.DataFrame([
        ("001", "A", "-2", "2", "0.3"),
        ("001", "A", "20", "", ""),
        ("", "A", "bad", "0", "nan"),
        ("002", "B", "inf", "-1", "-0.2"),
        ("002", "B", "", "", "bad"),
        ("003", "B", "22", "malformed", ""),
        ("", "B", "23", "inf", ""),
        ("", "C", "24", "", ""),
        ("", "C", "24", "", ""),
        ("", "", "25", "0.5", "0"),
    ], columns=["des", "fullname", "h", "diameter", "diameter_sigma"])
    report = analyze_physical_frame(frame)
    assert report["encounters"]["count"] == 10
    assert report["identified_objects"]["count"] == 4
    assert report["identified_objects"]["encounters_without_resolvable_identifier"] == 2
    assert report["identified_objects"]["diameter_coverage"] == dict(known=1, missing=1, invalid=2)
    fields = report["encounters"]["field_completeness"]
    assert fields["diameter"]["known"] == 2
    assert fields["diameter"]["invalid_by_reason"] == dict(negative=1, zero=1, nonnumeric=1, nonfinite=1)
    assert fields["h"]["invalid"] == 2
    assert fields["h"]["missing"] == 1
    assert fields["diameter_sigma"]["invalid"] == 3
    assert report["absolute_magnitude"]["statistics"] == dict(count=7, minimum=-2, median=23, maximum=25)
    catalog = report["catalog_diameters"]
    assert catalog["pair_count"] == catalog["pairs_with_valid_sigma"] == 2
    assert [pair["reported_diameter_sigma_km"] for pair in catalog["pairs"]] == [0.3, 0]


def test_catalog_uncertainty_is_absolute_and_from_same_row():
    frame = pd.DataFrame({
        "des": ["A"] * 4, "h": [20, 21, 22, ""],
        "diameter": [2, 1, 1, 2], "diameter_sigma": [0.3, "-1", "", 0.5],
    })
    report = analyze_physical_frame(frame)
    assert [p["reported_diameter_sigma_km"] for p in report["catalog_diameters"]["pairs"]] == [0.3, None, None]
    figures = physical_figures(report)
    scatter = figures["h_vs_known_diameter.png"].axes[0]
    segments = scatter.containers[0].lines[2][0].get_segments()
    assert len(segments) == 1
    assert list(segments[0][:, 1]) == pytest.approx([1.7, 2.3])


@pytest.mark.parametrize("frame", [pd.DataFrame(), pd.DataFrame({"des": ["A"], "h": [20]})])
def test_missing_diameter_and_albedo_headless(frame):
    report = analyze_physical_frame(frame)
    assert report["identified_objects"]["diameter_coverage"] == dict(known=0, missing=len(frame), invalid=0)
    assert report["encounters"]["field_completeness"]["diameter"]["column_present"] is False
    assert report["catalog_diameters"]["pairs"] == []
    figures = physical_figures(report)
    assert set(figures) == FILENAMES
    assert "No encounters" in figures["h_vs_known_diameter.png"].axes[0].texts[0].get_text()
    lines = figures["diameter_albedo_sensitivity.png"].axes[0].lines
    assert [line.get_label() for line in lines] == [
        "Hypothetical pV = 0.05", "Hypothetical pV = 0.14", "Hypothetical pV = 0.25",
    ]
    for figure in figures.values():
        assert isinstance(figure.canvas, FigureCanvasAgg)
        target = BytesIO()
        figure.savefig(target, format="png")
        assert target.getvalue().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("csv", [b"", b"des,h,diameter,diameter_sigma\nA,20,2,0.3\nA,21,,\n"])
def test_public_command_offline_and_deterministic(tmp_path, csv):
    data = tmp_path / "data"
    processed = data / "processed"
    processed.mkdir(parents=True)
    source = processed / "cad_close_approaches.csv"
    source.write_bytes(csv)
    output = tmp_path / "outputs"
    output.mkdir()
    prior = output / "velocity_analysis_summary.json"
    prior.write_text("existing output", encoding="utf-8")
    (tmp_path / "sitecustomize.py").write_text(
        "import socket\n"
        "def blocked(*args, **kwargs):\n"
        "    raise AssertionError('Network access was attempted')\n"
        "socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked\n",
        encoding="utf-8",
    )
    env = dict(os.environ, SCI_DATA_DIR=str(data), SCI_OUTPUT_DIR=str(output), PYTHONPATH=str(tmp_path))
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    command = [sys.executable, "manage.py", "analyze-physical", "--current"]
    destination = output / "physical_analysis_summary.json"
    subprocess.run(command, env=env, check=True)
    first = destination.read_bytes()
    subprocess.run(command, env=env, check=True)
    assert destination.read_bytes() == first
    report = json.loads(first)
    assert report["encounters"]["count"] == (2 if csv else 0)
    assert report["input_provenance"]["sha256"] == hashlib.sha256(csv).hexdigest()
    assert {path.name for path in (output / "figures").iterdir()} == FILENAMES
    assert prior.read_text(encoding="utf-8") == "existing output"
    assert source.read_bytes() == csv
