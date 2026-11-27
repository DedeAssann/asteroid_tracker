"""Headless figures for absolute magnitude, catalog coverage, and model sensitivity."""

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from .physical_analysis import photometric_diameter_km


def _figure(title, x_label, y_label):
    figure = Figure(figsize=(8, 5), layout="constrained")
    FigureCanvasAgg(figure)
    ax = figure.subplots()
    ax.set(title=title, xlabel=x_label, ylabel=y_label)
    return figure, ax


def _empty(ax, message):
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)


def physical_figures(summary):
    """Build four independent figures from the computed report."""
    histogram, ax = _figure("Absolute magnitude distribution", "Absolute magnitude H (mag)", "Encounters")
    magnitudes = summary["absolute_magnitude"]
    stats = magnitudes["statistics"]
    if stats["count"]:
        ax.hist(magnitudes["values"], bins="sturges", color="#32668a", edgecolor="white")
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        annotation = (
            f"n = {stats['count']:,}\nMedian = {stats['median']:.4g} mag\n"
            f"Range = {stats['minimum']:.4g} to {stats['maximum']:.4g} mag"
        )
        ax.text(0.98, 0.98, annotation, ha="right", va="top", transform=ax.transAxes,
                bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "none"})
    else:
        _empty(ax, "No valid absolute magnitudes (n = 0)")

    coverage, ax = _figure("JPL diameter completeness", "Catalog diameter status", "Identified objects")
    objects = summary["identified_objects"]
    counts = [objects["diameter_coverage"][state] for state in ("known", "missing", "invalid")]
    bars = ax.bar(["Known", "Missing", "Invalid"], counts, color=["#32668a", "#929aa2", "#ac6236"])
    ax.bar_label(bars, padding=4)
    ax.set_ylim(0, max(1, max(counts) * 1.2))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    coverage.supxlabel(
        f"{objects['count']:,} identified objects · "
        f"{objects['encounters_without_resolvable_identifier']:,} encounters excluded for unresolved ID",
        fontsize=10,
    )

    sensitivity, ax = _figure(
        "Photometric diameter sensitivity to hypothetical albedo",
        "Reference absolute magnitude H (mag)", "Hypothetical diameter (km)",
    )
    model = summary["hypothetical_photometric_model"]
    start, stop = model["reference_h_range_mag"]
    reference_h = [start + index * (stop - start) / 100 for index in range(101)]
    for albedo in model["hypothetical_geometric_albedos"]:
        ax.plot(reference_h, [photometric_diameter_km(h, albedo) for h in reference_h],
                label=f"Hypothetical pV = {albedo:.2f}")
    ax.set_yscale("log")
    ax.grid(alpha=0.25)
    ax.legend()

    scatter, ax = _figure(
        "Absolute magnitude vs. JPL catalog diameter",
        "Absolute magnitude H (mag)", "JPL catalog diameter (km)",
    )
    pairs = summary["catalog_diameters"]["pairs"]
    if pairs:
        ax.scatter([p["absolute_magnitude_h"] for p in pairs],
                   [p["catalog_diameter_km"] for p in pairs],
                   color="#32668a", label=f"Catalog diameters ({len(pairs):,} encounters)")
        with_sigma = [pair for pair in pairs if pair["reported_diameter_sigma_km"] is not None]
        if with_sigma:
            ax.errorbar([p["absolute_magnitude_h"] for p in with_sigma],
                        [p["catalog_diameter_km"] for p in with_sigma],
                        yerr=[p["reported_diameter_sigma_km"] for p in with_sigma],
                        fmt="none", ecolor="#32668a", capsize=3, label="Reported ±1σ (km)")
        ax.legend()
    else:
        _empty(ax, "No encounters with both valid H and a JPL catalog diameter")

    return {
        "absolute_magnitude_distribution.png": histogram,
        "diameter_completeness.png": coverage,
        "diameter_albedo_sensitivity.png": sensitivity,
        "h_vs_known_diameter.png": scatter,
    }
