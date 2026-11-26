"""Generate the v0.2 ranking and figure using only an existing local CSV."""

import argparse
import json

from asteroid_tracker.analysis import analyze_csv
from asteroid_tracker.config import load_config
from asteroid_tracker.paths import child_path, directories
from asteroid_tracker.plotting import plot_closest_approaches


def run_analysis(config):
    """Coordinate file I/O while keeping plotting separate from calculations."""
    data_dir, output_dir = directories(config)
    processed = child_path(data_dir / "processed", config.get("pipeline", {}).get(
        "processed_csv", "cad_close_approaches.csv"))
    settings = config.get("jpl_cad", {})
    # v0.1 does not save the actual download query: configuration is context,
    # never proof of the query that produced a possibly older cached CSV.
    context = None
    if settings:
        context = {
            "source": "current_configuration",
            "verified_for_input": False,
            "endpoint": settings.get("endpoint"),
            "query": settings.get("query"),
            "note": "Historical query unavailable in v0.1; relative dates are not resolved.",
        }
    summary = analyze_csv(processed, query_context=context)
    figure = plot_closest_approaches(summary, output_dir / "figures" / "closest_approaches.png")
    summary_path = output_dir / "analysis_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"analysis_summary": summary_path, "figure": figure,
            "records_analyzed": summary["records_analyzed"]}


def main():
    """Use the same configuration and portable paths as the v0.1 commands."""
    parser = argparse.ArgumentParser(description="Analyze cached close approaches offline")
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    try:
        result = run_analysis(load_config(args.config))
    except (FileNotFoundError, ValueError) as error:
        parser.exit(1, f"Analysis failed: {error}\nAn existing processed CSV is required; no download was attempted.\n")
    print(result)


if __name__ == "__main__":
    main()
