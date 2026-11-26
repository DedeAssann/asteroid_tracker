"""Headless plotting of already-computed scientific results (no calculations)."""

from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


def plot_closest_approaches(summary, destination):
    """Draw nominal distances and supplied JPL bounds, including partial bounds."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = summary["top_10"]
    figure = Figure(figsize=(11, max(4, 0.6 * len(rows) + 2.4)), layout="constrained")
    FigureCanvasAgg(figure)  # No desktop display is needed on WSL or Colab.
    axes = figure.subplots()
    if rows:
        for index, row in enumerate(rows):
            nominal = row["distance_ld"]
            lower = row["distance_min_3sigma_ld"]
            upper = row["distance_max_3sigma_ld"]
            axes.plot(nominal, index, "o", color="tab:blue",
                      label="Nominal" if index == 0 else None)
            # Missing bounds stay visibly missing; never invent a zero-width bar.
            if row["bounds_consistent"]:
                if lower is not None and upper is not None:
                    axes.hlines(index, lower, upper, color="tab:gray")
                for bound in (lower, upper):
                    if bound is not None:
                        axes.plot(bound, index, "|", color="tab:gray", markersize=10)
            if lower is None or upper is None or not row["bounds_consistent"]:
                axes.annotate("  [bounds incomplete/invalid]", (nominal, index),
                              xytext=(4, 6), textcoords="offset points", fontsize=8)
        # A legend handle explains ticks even if all rows have missing bounds.
        axes.plot([], [], "|-", color="tab:gray", label="JPL 3-sigma bounds (when available)")
        axes.set_yticks(range(len(rows)), [
            f'{row["rank"]}. {row["display_name"]}\n{row["calendar_date_tdb"] or "Date unknown"} (TDB)'
            for row in rows
        ])
        axes.invert_yaxis()
        axes.legend(loc="best", fontsize=8)
    else:
        axes.text(0.5, 0.5, "No valid nominal distances to rank",
                  ha="center", va="center", transform=axes.transAxes)
        axes.set_yticks([])
    axes.set_xlim(left=0)
    axes.set_xlabel("Close-approach distance (LD; 1 LD = 384,400 km)")
    axes.set_title("Closest approaches in input — up to 10 encounters\nDistance is not a danger score")
    axes.grid(axis="x", alpha=0.25)
    figure.savefig(destination, dpi=160)
    return destination
