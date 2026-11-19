import csv
import hashlib
import json
import math
import statistics
from .paths import child_path, directories


def run_pipeline(config):
    data_dir, output_dir = directories(config)
    settings = config.get("pipeline", {})
    source = child_path(data_dir / "raw", settings.get("input", "example.csv"))
    with source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if "value" not in (reader.fieldnames or []):
            raise ValueError("Input CSV must contain a 'value' column")
        values = [float(row["value"]) for row in reader]
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("Input must contain finite numeric values")
    result = {"count": len(values), "mean": statistics.mean(values),
              "min": min(values), "max": max(values),
              "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    target = child_path(output_dir, settings.get("summary", "summary.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return target
