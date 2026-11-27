"""Headless views of precomputed kinematics; no scientific calculations or I/O."""

import math

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


def _canvas(title, xlabel, ylabel):
    """Build a display-independent figure usable on Windows, WSL and Colab."""
    figure = Figure(figsize=(8, 5), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots()
    axes.set(title=title, xlabel=xlabel, ylabel=ylabel)
    axes.grid(alpha=0.2)
    return figure, axes


def _empty(axes):
    """Keep missing populations explicit rather than inventing data points."""
    axes.text(0.5, 0.5, "No valid observations (n = 0)", ha="center", va="center",
              transform=axes.transAxes)


def velocity_figures(summary):
    """Return named figures for a caller to save; leave the summary unchanged."""
    figures = {}
    figure, axes = _canvas("Relative velocity distribution — all valid encounters",
                           "Relative velocity (km/s)", "Encounter count")
    stats = summary["statistics"]["v_rel_km_s"]
    if stats["count"]:
        histogram = summary["velocity_histogram"]
        axes.stairs(histogram["counts"], histogram["edges_km_s"], fill=True, alpha=0.55)
        axes.axvline(stats["median"], color="tab:orange", linestyle="--", label="Median")
        axes.legend(loc="upper right")
        axes.text(0.02, 0.96, f'n = {stats["count"]}\nMedian = {stats["median"]:.4g} km/s\n'
                  f'Range = [{stats["minimum"]:.4g}, {stats["maximum"]:.4g}] km/s',
                  transform=axes.transAxes, va="top", bbox={"facecolor": "white", "alpha": 0.85})
    else:
        _empty(axes)
    figures["velocity_distribution.png"] = figure

    # Pairwise selection mirrors the populations explicitly counted in JSON.
    pairs = [e for e in summary["events"] if e["distance_ld"] is not None and e["v_rel_km_s"] is not None]
    figure, axes = _canvas(f'Nominal distance versus relative velocity (n = {len(pairs)})',
                           "Nominal close-approach distance (LD)", "Relative velocity (km/s)")
    if pairs:
        axes.scatter([e["distance_ld"] for e in pairs], [e["v_rel_km_s"] for e in pairs], alpha=0.65)
    else:
        _empty(axes)
    axes.set_xlim(left=0)
    axes.set_ylim(bottom=0)
    figures["distance_vs_velocity.png"] = figure

    pairs = [e for e in summary["events"] if e["v_rel_km_s"] is not None and e["v_inf_km_s"] is not None]
    figure, axes = _canvas(f'Relative versus infinity velocity (n = {len(pairs)})',
                           "Infinity velocity (km/s)", "Relative velocity (km/s)")
    if pairs:
        axes.scatter([e["v_inf_km_s"] for e in pairs], [e["v_rel_km_s"] for e in pairs], alpha=0.65)
        upper = max(max(e["v_inf_km_s"], e["v_rel_km_s"]) for e in pairs) or 1
    else:
        upper = 1
        _empty(axes)
    # Pad both axes equally so endpoint and zero-speed markers are not clipped.
    padded = upper * 1.05
    upper = padded if math.isfinite(padded) else upper
    lower = -0.03 * upper
    axes.plot([0, upper], [0, upper], "--", color="tab:gray", label="1:1 reference")
    axes.set(xlim=(lower, upper), ylim=(lower, upper), aspect="equal")
    axes.legend(loc="upper left")
    figures["relative_vs_infinity_velocity.png"] = figure
    return figures
