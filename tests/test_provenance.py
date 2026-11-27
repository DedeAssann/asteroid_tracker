"""Offline regression tests for local CAD artifact publication and lineage."""

from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from asteroid_tracker import jpl_cad, provenance
from asteroid_tracker.analysis import analyze_csv
from asteroid_tracker.pipeline import payload_to_dataframe, run_pipeline
from test_asteroid_pipeline import SAMPLE

ENDPOINT = "https://example.invalid/cad.api"


def _bytes(payload):
    # Unusual whitespace tests that hashing/archiving uses the exact response.
    return (" \n" + json.dumps(payload, separators=(",", ":")) + " \n").encode()


def _read_receipt(path, kind):
    return json.loads(provenance.receipt_path(path, kind).read_bytes())


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    data = tmp_path / "directory with spaces" / "data"
    outputs = tmp_path / "outputs"
    monkeypatch.setenv("SCI_DATA_DIR", str(data))
    monkeypatch.setenv("SCI_OUTPUT_DIR", str(outputs))
    config = {
        "jpl_cad": {
            "endpoint": ENDPOINT + "?api_key=SECRET",
            "expected_version": "1.5",
            "query": {"date-min": "now", "date-max": "+30", "body": "Earth",
                      "access_token": "SECRET", "diameter": True},
        },
        "pipeline": {"raw_json": "custom CAD.json", "processed_csv": "custom CAD.csv"},
    }
    return config, data / "raw" / "custom CAD.json", data / "processed" / "custom CAD.csv"


def _mock_download(monkeypatch, *payloads, redirect=False):
    responses = iter(payloads)
    calls = []

    def get(endpoint, *, params, **kwargs):
        calls.append((endpoint, params))
        initial = requests.Request("GET", endpoint, params=params).prepare()
        response = requests.Response()
        response.status_code = 200
        response._content = _bytes(next(responses))
        response.request = initial
        if redirect:
            first = requests.Response()
            first.request = initial
            response.history = [first]
            response.request = requests.Request(
                "GET", "https://username:SECRET@redirect.invalid/cad.api?date-max=%2B60&token=SECRET",
            ).prepare()
        return response

    monkeypatch.setattr(jpl_cad.requests, "get", get)
    return calls


def test_new_download_records_sent_request_then_cache_and_force(dataset, monkeypatch):
    config, raw, _ = dataset
    zero = {"signature": {"version": "1.5"}, "count": 0}
    calls = _mock_download(monkeypatch, SAMPLE, zero, redirect=True)
    acquired = jpl_cad.acquire_close_approaches(config)
    assert acquired == {
        "path": raw, "download_status": "new_acquisition", "acquisition_metadata_status": "verified",
    }
    stored = raw.read_bytes()
    receipt_path = provenance.receipt_path(raw, "acquisition")
    receipt_bytes = receipt_path.read_bytes()
    metadata = json.loads(receipt_bytes)
    assert b"SECRET" not in receipt_bytes
    assert stored == _bytes(SAMPLE)
    assert "NASA/JPL SSD CAD API" == metadata["source"]
    assert metadata["download_status"] == "new_acquisition"
    assert metadata["record_count"] == 1
    assert metadata["api_version"] == "1.5"
    assert datetime.fromisoformat(metadata["acquired_at_utc"]).utcoffset() == timedelta(0)
    assert metadata["raw"]["sha256"] == sha256(stored).hexdigest()
    request = metadata["request"]
    assert request["endpoint"] == ENDPOINT
    assert request["relative_date_inputs"] == [
        {"name": "date-min", "value": "now"}, {"name": "date-max", "value": "+30"},
    ]
    assert {pair["name"]: pair["value"] for pair in request["parameters"]}["diameter"] == "True"
    assert request["final_relative_date_inputs"] == [{"name": "date-max", "value": "+60"}]
    final = urlsplit(request["final_url"])
    assert final.netloc == "redirect.invalid"
    assert parse_qs(final.query) == {"date-max": ["+60"], "token": ["[redacted]"]}

    config["jpl_cad"]["query"]["date-max"] = "+90"
    for _ in range(2):
        hit = jpl_cad.acquire_close_approaches(config)
        assert hit["download_status"] == "cache_hit"
        assert hit["acquisition_metadata_status"] == "verified"
    assert len(calls) == 1
    assert raw.read_bytes() == stored
    assert receipt_path.read_bytes() == receipt_bytes
    assert jpl_cad.acquire_close_approaches(config, force=True)["download_status"] == "new_acquisition"
    assert len(calls) == 2
    assert raw.read_bytes() == _bytes(zero)
    assert _read_receipt(raw, "acquisition")["record_count"] == 0


def test_legacy_provenance_is_incomplete_and_corruption_is_reported(dataset, monkeypatch):
    config, raw, csv = dataset
    calls = _mock_download(monkeypatch)
    raw.parent.mkdir(parents=True)
    raw.write_bytes(_bytes(SAMPLE))
    status = jpl_cad.acquire_close_approaches(config)
    assert status["download_status"] == "cache_hit"
    assert status["acquisition_metadata_status"] == "missing"
    assert not provenance.receipt_path(raw, "acquisition").exists()
    run_pipeline(config)
    processing = _read_receipt(csv, "processing")
    assert processing["raw"]["sha256"] == sha256(raw.read_bytes()).hexdigest()
    chain = analyze_csv(csv)["input_provenance"]["chain"]
    assert chain["status"] == "incomplete"
    assert chain["processing"]["status"] == "verified"
    assert chain["acquisition"]["status"] == "missing"

    raw.write_bytes(b"{broken")
    with pytest.raises(ValueError, match="Corrupted raw cache"):
        jpl_cad.acquire_close_approaches(config)
    assert not calls


def test_failed_refresh_leaves_prior_bytes_and_metadata_intact(dataset, monkeypatch):
    config, raw, _ = dataset
    _mock_download(monkeypatch, SAMPLE)
    jpl_cad.acquire_close_approaches(config)
    receipt = provenance.receipt_path(raw, "acquisition")
    prior = raw.read_bytes(), receipt.read_bytes()

    def failed(*args, **kwargs):
        raise requests.ConnectionError("mock offline")

    monkeypatch.setattr(jpl_cad.requests, "get", failed)
    with pytest.raises(requests.ConnectionError):
        jpl_cad.acquire_close_approaches(config, force=True)
    assert prior == (raw.read_bytes(), receipt.read_bytes())
    _mock_download(monkeypatch, dict(SAMPLE, count=2))
    with pytest.raises(ValueError, match="record count"):
        jpl_cad.acquire_close_approaches(config, force=True)
    assert prior == (raw.read_bytes(), receipt.read_bytes())


@pytest.mark.parametrize("interrupt_before", ["artifact", "receipt"])
def test_interrupted_refresh_remains_auditable(dataset, monkeypatch, interrupt_before):
    config, raw, _ = dataset
    changed = dict(SAMPLE, count=0, data=[])
    _mock_download(monkeypatch, SAMPLE, changed)
    jpl_cad.acquire_close_approaches(config)
    receipt = provenance.receipt_path(raw, "acquisition")
    before = receipt.read_bytes()
    replace = Path.replace

    def interrupt(self, target):
        failing_target = raw if interrupt_before == "artifact" else receipt
        if target == failing_target:
            raise OSError("simulated interrupted publication")
        return replace(self, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", interrupt)
        with pytest.raises(OSError, match="interrupted"):
            jpl_cad.acquire_close_approaches(config, force=True)
    assert receipt.read_bytes() == before
    assert not list(raw.parent.glob("*.tmp"))
    assert not (raw.parent / (raw.name + ".provenance.lock")).exists()
    assert jpl_cad.acquire_close_approaches(config)["acquisition_metadata_status"] == "verified"
    count = 1 if interrupt_before == "artifact" else 0
    assert _read_receipt(raw, "acquisition")["record_count"] == count


def test_raw_hash_mismatch_is_explicit_and_never_used_for_processing(dataset, monkeypatch):
    config, raw, _ = dataset
    calls = _mock_download(monkeypatch, SAMPLE)
    jpl_cad.acquire_close_approaches(config)
    raw.write_bytes(raw.read_bytes() + b"\n")
    for action in (jpl_cad.acquire_close_approaches, run_pipeline):
        with pytest.raises(ValueError, match="hash_mismatch"):
            action(config)
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [SAMPLE, {"signature": {"version": "1.5"}, "count": 0}])
def test_raw_to_csv_to_three_offline_reports(dataset, monkeypatch, tmp_path, payload):
    config, raw, csv = dataset
    _mock_download(monkeypatch, payload)
    jpl_cad.acquire_close_approaches(config)
    # The configured query was edited after acquisition.
    config["jpl_cad"]["query"]["date-max"] = "+120"
    output = run_pipeline(config)
    processing = _read_receipt(csv, "processing")
    raw_hash = sha256(raw.read_bytes()).hexdigest()
    csv_hash = sha256(csv.read_bytes()).hexdigest()
    assert processing["raw"]["sha256"] == raw_hash
    assert processing["csv"]["sha256"] == csv_hash
    assert processing["record_count"] == payload["count"]
    assert processing["acquisition"]["metadata"]["raw"]["sha256"] == raw_hash
    assert datetime.fromisoformat(processing["processed_at_utc"]).utcoffset() == timedelta(0)
    prior_csv = tmp_path / "prior format.csv"
    payload_to_dataframe(payload).to_csv(prior_csv, index=False)
    assert csv.read_bytes() == prior_csv.read_bytes()
    assert json.loads(output["summary_json"].read_bytes())["input_sha256"] == raw_hash

    # Archive independence: a processed snapshot can move without the raw cache.
    relocated = tmp_path / "relocated data" / "processed"
    relocated.mkdir(parents=True)
    for path in (csv, provenance.receipt_path(csv, "processing")):
        path.rename(relocated / path.name)
    config_path = tmp_path / "config with spaces.yaml"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "sitecustomize.py").write_text(
        "import socket\n"
        "def blocked(*args, **kwargs):\n"
        "    raise AssertionError('Network access was attempted')\n"
        "socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked\n",
        encoding="utf-8",
    )
    env = dict(os.environ, SCI_DATA_DIR=str(relocated.parent), PYTHONPATH=str(tmp_path))
    for command, output_file in (
        ("analyze", "analysis_summary.json"),
        ("analyze-velocity", "velocity_analysis_summary.json"),
        ("analyze-physical", "physical_analysis_summary.json"),
    ):
        subprocess.run(
            [sys.executable, "manage.py", command, "--current", "--config", str(config_path)],
            env=env, check=True,
        )
        report_path = output["summary_json"].parent / output_file
        report = json.loads(report_path.read_bytes())
        assert report["input_provenance"]["sha256"] == csv_hash
        chain = report["input_provenance"]["chain"]
        assert chain["status"] == "complete"
        assert chain["acquisition"]["status"] == "verified_at_processing"
        assert chain["analysis_execution"]["timestamp_recorded"] is False
        declared = chain["processing"]["metadata"]["acquisition"]["metadata"]["request"]
        assert {"name": "date-max", "value": "+30"} in declared["relative_date_inputs"]
        if "query_context" in report:
            assert report["query_context"]["query"]["date-max"] == "+30"


def test_invalid_stale_and_conflicting_processing_receipts(dataset, monkeypatch):
    config, _, csv = dataset
    _mock_download(monkeypatch, SAMPLE)
    jpl_cad.acquire_close_approaches(config)
    run_pipeline(config)
    receipt = provenance.receipt_path(csv, "processing")
    raw, saved_csv = receipt.read_bytes(), csv.read_bytes()
    complete = analyze_csv(csv)
    assert complete == analyze_csv(csv)

    metadata = json.loads(raw)
    metadata["acquisition"]["metadata"]["raw"]["sha256"] = "0" * 64
    receipt.write_text(json.dumps(metadata), encoding="utf-8")
    chain = analyze_csv(csv)["input_provenance"]["chain"]
    assert chain["status"] == "incomplete"
    assert chain["acquisition"]["status"] == "hash_mismatch"

    receipt.write_bytes(raw)
    csv.write_bytes(saved_csv.replace(b"19.7", b"19.8"))
    report = analyze_csv(csv)
    assert report["input_provenance"]["chain"]["processing"]["status"] == "hash_mismatch"
    assert report["query_context"] is None

    csv.write_bytes(saved_csv)
    receipt.write_bytes(b'{')
    assert analyze_csv(csv)["input_provenance"]["chain"]["processing"]["status"] == "invalid_metadata"
    receipt.unlink()
    assert analyze_csv(csv)["input_provenance"]["chain"]["processing"]["status"] == "missing"


def test_interrupted_csv_publication_is_readable_without_promoting_receipt(dataset, monkeypatch):
    config, raw, csv = dataset
    _mock_download(monkeypatch, SAMPLE)
    jpl_cad.acquire_close_approaches(config)
    receipt = provenance.receipt_path(csv, "processing")
    replace = Path.replace

    def interrupt(self, target):
        if target == receipt:
            raise OSError("simulated interrupted CSV publication")
        return replace(self, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", interrupt)
        with pytest.raises(OSError, match="interrupted CSV"):
            run_pipeline(config)
    assert not receipt.exists()
    chain = analyze_csv(csv)["input_provenance"]["chain"]
    assert chain["status"] == "complete"
    assert chain["processing"]["publication"] == "pending"
    assert not receipt.exists()

    run_pipeline(config)
    chain = analyze_csv(csv)["input_provenance"]["chain"]
    assert chain["processing"]["publication"] == "committed"
    assert not receipt.with_name(receipt.name + ".pending").exists()


def test_writer_lock_rejects_an_overlapping_write(dataset, monkeypatch):
    config, raw, _ = dataset
    calls = _mock_download(monkeypatch)
    with provenance.artifact_writer(raw):
        with pytest.raises(OSError, match="Artifact locked"):
            jpl_cad.acquire_close_approaches(config)
    assert calls == []
