"""Versioned receipts for local artifact integrity and offline lineage."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

SCHEMA_VERSION = 1
CAD_SOURCE = "NASA/JPL SSD CAD API"
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def json_bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")


def artifact_record(path, content):
    return {
        "path": path.resolve().as_posix(),
        "sha256": sha256_bytes(content),
        "size_bytes": len(content),
    }


def receipt_path(path, kind):
    return path.with_name(f"{path.name}.{kind}.json")


def _pending(receipt):
    return receipt.with_name(receipt.name + ".pending")


def _timestamp_valid(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.utcoffset() == timezone.utc.utcoffset(stamp)
    except (AttributeError, ValueError):
        return False


def _artifact_valid(record):
    return (
        isinstance(record, dict)
        and isinstance(record.get("path"), str)
        and isinstance(record.get("sha256"), str)
        and _HEX_DIGEST.fullmatch(record["sha256"]) is not None
        and type(record.get("size_bytes")) is int
        and record["size_bytes"] >= 0
    )


def _receipt_valid(record, kind):
    if (
        not isinstance(record, dict)
        or type(record.get("schema_version")) is not int
        or record["schema_version"] != SCHEMA_VERSION
        or record.get("kind") != kind
        or type(record.get("record_count")) is not int
        or record["record_count"] < 0
    ):
        return False
    if kind == "acquisition":
        request = record.get("request")
        return (
            _artifact_valid(record.get("raw"))
            and _timestamp_valid(record.get("acquired_at_utc"))
            and record.get("download_status") == "new_acquisition"
            and record.get("source") == CAD_SOURCE
            and isinstance(record.get("api_version"), str)
            and isinstance(request, dict)
            and all(isinstance(request.get(key), str) and request[key]
                    for key in ("endpoint", "final_url"))
            and all(isinstance(request.get(key), list) and all(
                isinstance(pair, dict) and isinstance(pair.get("name"), str)
                and isinstance(pair.get("value"), str) for pair in request[key]
            ) for key in ("parameters", "relative_date_inputs", "final_relative_date_inputs"))
        )
    configuration = record.get("configuration")
    software = record.get("software")
    return (
        _artifact_valid(record.get("csv"))
        and _artifact_valid(record.get("raw"))
        and _timestamp_valid(record.get("processed_at_utc"))
        and isinstance(configuration, dict)
        and all(isinstance(configuration.get(key), str) and configuration[key]
                for key in ("expected_cad_api_version", "cad_api_version", "csv_encoding"))
        and isinstance(software, dict)
        and type(software.get("normalization_schema_version")) is int
        and all(isinstance(software.get(key), str) and software[key]
                for key in ("provenance_implementation_version", "python", "pandas"))
    )


def _same_bytes(left, right):
    """Paths are historical context, so archived files can be moved."""
    return all(left[key] == right[key] for key in ("sha256", "size_bytes"))


def read_receipt(path, kind, artifact):
    """Validate metadata against a byte snapshot, including interrupted writes."""
    receipt = receipt_path(path, kind)
    artifact_key = "raw" if kind == "acquisition" else "csv"
    initial_status = "missing"
    for candidate in (receipt, _pending(receipt)):
        try:
            record = json.loads(candidate.read_bytes())
        except FileNotFoundError:
            status = "missing"
        except (OSError, ValueError):
            status = "invalid_metadata"
        else:
            if not _receipt_valid(record, kind):
                status = "invalid_metadata"
            elif not _same_bytes(record[artifact_key], artifact):
                status = "hash_mismatch"
            else:
                return {
                    "status": "verified",
                    "receipt": candidate.name,
                    "publication": "committed" if candidate == receipt else "pending",
                    "metadata": record,
                }
        if initial_status == "missing":
            initial_status = status
    return {"status": initial_status, "receipt": receipt.name}


@contextmanager
def artifact_writer(path):
    """Serialize writers using a portable, exclusive lock directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".provenance.lock")
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise OSError(f"Artifact locked: {lock}. Check for an active writer before recovery.") from error
    try:
        yield
    finally:
        lock.rmdir()


def _atomic_write(path, content):
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # Close the handle before replacement for Windows compatibility.
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def publish_artifact(path, content, kind, metadata):
    """Publish a staged receipt before replacing bytes; caller holds the lock."""
    receipt = receipt_path(path, kind)
    staged = _pending(receipt)
    # Preserve the only matching receipt from a prior interrupted write before
    # overwriting its staging slot.
    if staged.exists() and path.exists():
        previous = read_receipt(path, kind, artifact_record(path, path.read_bytes()))
        recover_receipt(path, kind, previous)
    _atomic_write(staged, json_bytes(metadata))
    _atomic_write(path, content)
    staged.replace(receipt)


def recover_receipt(path, kind, verification):
    """Promote a matching staged receipt while holding the artifact lock."""
    if verification.get("publication") == "pending":
        receipt = receipt_path(path, kind)
        _pending(receipt).replace(receipt)


def acquisition_for_raw(raw_path, raw):
    verification = read_receipt(raw_path, "acquisition", raw)
    if verification["status"] not in ("verified", "missing"):
        raise ValueError(f"Raw cache integrity error ({verification['status']}): {raw_path}. "
                         "Restore matching files or use download --force.")
    return verification


def analysis_input_provenance(path, content, frame, source_record_definition):
    """Check the CSV receipt and its raw linkage without reading the raw cache."""
    artifact = artifact_record(path, content)
    processing = read_receipt(path, "processing", artifact)
    acquisition = {"status": "unavailable"}
    if processing["status"] == "verified":
        metadata = processing["metadata"]
        if metadata["record_count"] != len(frame):
            processing = {"status": "record_count_mismatch", "receipt": processing["receipt"]}
        else:
            snapshot = metadata.get("acquisition")
            if isinstance(snapshot, dict) and snapshot.get("status") == "missing":
                acquisition = {"status": "missing"}
            elif isinstance(snapshot, dict) and snapshot.get("status") == "verified":
                record = snapshot.get("metadata")
                if not _receipt_valid(record, "acquisition"):
                    acquisition = {"status": "invalid_metadata"}
                elif not _same_bytes(record["raw"], metadata["raw"]):
                    acquisition = {"status": "hash_mismatch"}
                elif record["api_version"] != metadata["configuration"]["cad_api_version"]:
                    acquisition = {"status": "api_version_mismatch"}
                elif record["record_count"] != metadata["record_count"]:
                    acquisition = {"status": "record_count_mismatch"}
                else:
                    acquisition = {"status": "verified_at_processing", "receipt": snapshot.get("receipt")}
            else:
                acquisition = {"status": "invalid_metadata"}

    return {
        "processed_csv": artifact["path"],
        "sha256": artifact["sha256"],
        "size_bytes": artifact["size_bytes"],
        "columns": list(frame.columns),
        "source_record_definition": source_record_definition,
        "chain": {
            "schema_version": SCHEMA_VERSION,
            "status": "complete" if acquisition["status"] == "verified_at_processing" else "incomplete",
            "analysis_execution": {"mode": "offline", "timestamp_recorded": False},
            "processing": processing,
            "acquisition": acquisition,
        },
    }


def historical_query_context(input_provenance, fallback):
    """Expose actual request details only when both links have been verified."""
    chain = input_provenance["chain"]
    if chain["status"] != "complete":
        return fallback
    acquisition = chain["processing"]["metadata"]["acquisition"]["metadata"]
    return {
        "source": "acquisition_metadata",
        "verified_for_input": True,
        "endpoint": acquisition["request"]["endpoint"],
        "query": {pair["name"]: pair["value"] for pair in acquisition["request"]["parameters"]},
        "relative_date_inputs": acquisition["request"]["relative_date_inputs"],
    }
