"""File I/O and orchestration for offline v0.2.2 kinematics."""

import argparse
import hashlib
from io import BytesIO
import json

import pandas as pd

from asteroid_tracker.config import load_config
from asteroid_tracker.paths import child_path, directories
from asteroid_tracker.velocity_analysis import analyze_velocity_frame
from asteroid_tracker.velocity_plotting import velocity_figures


def run_velocity_analysis(config, assume_body=None):
    """Hash the exact CSV bytes analyzed, then save only the new output files."""
    data_dir, output_dir = directories(config)
    path = child_path(data_dir / "processed", config.get("pipeline", {}).get(
        "processed_csv", "cad_close_approaches.csv"))
    content = path.read_bytes()
    try:
        # Preserve IDs and distinguish explicit nonfinite tokens from empty cells.
        frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        frame = pd.DataFrame()
    summary = analyze_velocity_frame(frame, assume_body=assume_body)
    summary["input_provenance"] = {
        "processed_csv": path.resolve().as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content),
        "columns": list(frame.columns), "source_record_definition": "1-based data record excluding header",
    }
    # Current settings remain useful context, but cannot authenticate cached data.
    summary["query_context"] = {
        "source": "current_configuration", "verified_for_input": False,
        "settings": config.get("jpl_cad"),
        "note": "Historical query unknown; configuration is not used to infer encounter body.",
    }
    serialized = json.dumps(summary, indent=2, allow_nan=False) + "\n"
    destination = output_dir / "figures"
    destination.mkdir(parents=True, exist_ok=True)
    figures = velocity_figures(summary)
    try:
        for name, figure in figures.items():
            figure.savefig(destination / name, dpi=160)
    finally:
        for figure in figures.values():
            figure.clear()
    target = output_dir / "velocity_analysis_summary.json"
    target.write_text(serialized, encoding="utf-8")
    return {"summary": target, "figures": [destination / name for name in figures],
            "records_analyzed": summary["records_analyzed"],
            "energy_records_evaluated": summary["energy_consistency"]["records_evaluated"]}


def main():
    """Expose portable paths and an auditable optional body assumption."""
    parser = argparse.ArgumentParser(description="Analyze cached encounter velocities offline")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--assume-body", choices=["Earth"],
                        help="Explicitly assume Earth only for rows with no body; recorded in JSON")
    args = parser.parse_args()
    try:
        result = run_velocity_analysis(load_config(args.config), args.assume_body)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Velocity analysis failed: {error}\nNo download was attempted.\n")
    print(result)


if __name__ == "__main__":
    main()
