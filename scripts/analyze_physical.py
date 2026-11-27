"""Read the cached processed CSV and write offline v0.2.3 analysis outputs."""

import argparse
import hashlib
from io import BytesIO
import json

import pandas as pd

from asteroid_tracker.config import load_config
from asteroid_tracker.paths import child_path, directories
from asteroid_tracker.physical_analysis import analyze_physical_frame
from asteroid_tracker.physical_plotting import physical_figures


def run_physical_analysis(config):
    data_dir, output_dir = directories(config)
    filename = config.get("pipeline", {}).get("processed_csv", "cad_close_approaches.csv")
    path = child_path(data_dir / "processed", filename)
    content = path.read_bytes()
    try:
        # Keep leading zeros in identifiers and preserve malformed numeric tokens.
        frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        frame = pd.DataFrame()
    summary = analyze_physical_frame(frame)
    summary["input_provenance"] = {
        "processed_csv": path.resolve().as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
        "columns": list(frame.columns),
        "source_record_definition": "1-based data record excluding header",
    }

    serialized = json.dumps(summary, indent=2, allow_nan=False) + "\n"
    destination = output_dir / "figures"
    destination.mkdir(parents=True, exist_ok=True)
    for name, figure in physical_figures(summary).items():
        figure.savefig(destination / name, dpi=160)
        figure.clear()
    target = output_dir / "physical_analysis_summary.json"
    target.write_text(serialized, encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description="Analyze cached H and JPL diameters offline")
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    try:
        target = run_physical_analysis(load_config(args.config))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Physical analysis failed: {error}\n")
    print(f"Physical analysis summary: {target}")


if __name__ == "__main__":
    main()
