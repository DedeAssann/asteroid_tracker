import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from scientific_project.config import load_config
from scientific_project.data import download_data
from scientific_project.paths import ROOT, child_path, directories
from scientific_project.pipeline import run_pipeline


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("SCI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SCI_OUTPUT_DIR", str(tmp_path / "outputs"))
    return load_config()


def test_offline_pipeline_from_other_directory(config, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = download_data(config)
    output = run_pipeline(load_config())
    result = json.loads(output.read_text())
    assert (result["count"], result["mean"], result["min"], result["max"]) == (5, 3, 1, 5)
    assert result["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        download_data(config)


def test_paths(monkeypatch, tmp_path):
    monkeypatch.delenv("SCI_DATA_DIR", raising=False)
    monkeypatch.delenv("SCI_OUTPUT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert directories(load_config()) == (ROOT / "data", ROOT / "outputs")
    with pytest.raises(ValueError):
        child_path(tmp_path, "../escape.csv")


@pytest.mark.parametrize("contents", ["other\n1\n", "value\n", "value\nnan\n", "value\nabc\n"])
def test_bad_data(config, contents):
    source = download_data(config)
    source.write_text(contents)
    with pytest.raises(ValueError):
        run_pipeline(config)


def test_download_integrity(config, monkeypatch):
    import io
    import scientific_project.data as module
    class Response(io.BytesIO):
        def geturl(self):
            return "https://example.org/data.csv"
    body = b"value\n8\n"
    monkeypatch.setattr(module, "urlopen", lambda *a, **kw: Response(body))
    config["download"].update(url="https://example.org/data.csv", sha256="0" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        download_data(config)
    assert not list((directories(config)[0] / "raw").iterdir())
    config["download"]["sha256"] = hashlib.sha256(body).hexdigest()
    assert download_data(config).read_bytes() == body


def test_secret_patterns():
    spec = importlib.util.spec_from_file_location("audit", ROOT / "scripts/check_secrets.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    assert audit.suspicious(".env", b"")
    assert audit.suspicious("config.txt", ("ghp_" + "a" * 36).encode())
    assert not audit.suspicious(".env.example", b"SCI_DATA_DIR=data")
