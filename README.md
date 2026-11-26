# Asteroid Tracker

Portable scientific Python project for exploring **near-Earth object (NEO) close approaches** using official NASA/JPL SSD/CNEOS data.

## Current milestone — first v0.2 analysis increment

The first version intentionally focuses on a small, reproducible pipeline:

1. query the JPL SBDB Close-Approach Data (CAD) API;
2. cache the raw JSON response locally;
3. validate the API payload/version;
4. normalize the records into a CSV table;
5. derive useful physical quantities, including km and lunar distances;
6. produce a compact JSON summary;
7. test the parser offline.

The default query retrieves Earth close approaches by NEOs over the next 30 days, within **0.05 au**, sorted by nominal approach distance.

> A close approach is **not** the same thing as an impact threat. This project does not currently estimate impact probability. A later version may integrate JPL Sentry for that purpose.

## Data source

NASA/JPL SSD/CNEOS — SBDB Close-Approach Data API  
https://ssd-api.jpl.nasa.gov/doc/cad.html

The JPL API is treated as the scientific source of truth. The client checks the advertised API version before parsing and stores the raw response so results can be traced back to the source payload.

## Quick start

Python **3.10+**.

### Windows

```powershell
python manage.py setup
python manage.py download
python manage.py run
python manage.py analyze
python manage.py test
```

### Conda / Colab / ENSMA

In Google Colab, `manage.py` now detects the notebook runtime automatically and uses the current Python interpreter instead of creating a nested virtual environment.

```bash
python manage.py setup
python manage.py download
python manage.py run
python manage.py analyze
python manage.py test
```

If a broken `.venv` was created by an older version of the project in the current Colab session, remove it once before retrying:

```bash
rm -rf .venv
```

The explicit `--current` flag remains available for Conda or other managed environments.

To refresh the locally cached JPL payload:

```bash
python manage.py download --force
```

## Outputs

After a successful run:

```text
data/raw/cad_close_approaches.json
data/processed/cad_close_approaches.csv
outputs/summary.json
outputs/analysis_summary.json
outputs/figures/closest_approaches.png
```

These generated files are ignored by Git and can be recreated from the API.

The processed table adds, when possible:

- nominal distance in au;
- distance in km;
- distance in lunar distances;
- relative velocity in km/s;
- diameter in metres when JPL provides a measured/estimated diameter.

## Offline closest-approach analysis

Once the processed CSV exists, run:

```bash
python manage.py analyze
# Optional, just like the v0.1 commands:
python manage.py analyze --current --config configs/default.yaml
```

This command makes **no network requests** and does not run the downloader or
normalizer. The existing `setup`, `download`, `run`, `test`, and `check-secrets`
commands retain their behavior. Paths follow the existing configuration and
`SCI_DATA_DIR` / `SCI_OUTPUT_DIR` overrides. Matplotlib is the only new direct
dependency; rendering uses the headless Agg canvas on Windows, WSL and Colab.

The ranking contains up to ten **encounters**, not ten distinct asteroids, sorted
by finite, nonnegative nominal `dist` in au. Ties use lexical designation, numeric
JD (missing last), calendar date, orbit ID, body, then original 1-based CSV record
order. Missing text sorts as an empty string except designation (missing last).
Exact duplicate encounters are retained. Identical input bytes and configuration
produce the same JSON; no current timestamp or relative-date evaluation is added.

Distances are recalculated from `dist`, `dist_min`, and `dist_max`, ignoring any
previously derived LD columns. The conversion is
`distance_ld = distance_au * 149597870.7 / 384400.0`:
1 au = 149,597,870.7 km and this project uses a fixed mean lunar distance of
384,400 km (not the instantaneous Earth–Moon separation). According to the
[JPL CAD field definitions](https://ssd-api.jpl.nasa.gov/doc/cad.html), `dist_min`
and `dist_max` are the minimum and maximum **3-sigma** approach distances.
They are not converted into symmetric errors or impact probabilities.
Dates remain in TDB; no UTC conversion is performed.

Missing or invalid nominal distances exclude a record from the ranking, while
zero is retained as a numerical value without interpreting it as an impact.
Missing uncertainty bounds remain JSON `null`; available endpoints are plotted
individually. Nonfinite, nonnumeric and negative distances are invalid. Finite
but inconsistent bounds are retained and flagged in JSON and omitted from the
plot. No missing uncertainty is fabricated. Empty/header-only CSVs, including
the blank CSV produced by v0.1 for zero records, yield an empty ranking and an
explicit no-data figure. A nonempty table without `dist` fails clearly.

`analysis_summary.json` records:

- the input CSV's absolute path, SHA-256, byte size and columns;
- all records analyzed, rankable, excluded and selected;
- missing counts for all input columns plus expected analysis fields (an absent
  expected column counts as missing for every record), separate invalid numeric
  counts, and inconsistent-bound counts across the entire input;
- the unit constants, tie-breaking rule and ranked records with nominal and
  lower/upper 3-sigma distances in LD;
- the current configured query, when available, explicitly **unverified for this
  input**. v0.1 does not persist the historical download query or retrieval time,
  so `now` and `+30` cannot establish the dates of a cached dataset.

The figure describes only the supplied dataset and its selection filters. It is
**not a danger ranking** and provides no impact-risk estimate. This increment
adds no SBDB enrichment, Horizons, Sentry, dashboard, or additional rankings.

Tests use synthetic local CSVs, independent numerical conversion references,
ties, nulls, invalid values, partial bounds, empty inputs and a subprocess with
network connections blocked. Run the full suite with `python manage.py test`.

## Project structure

```text
asteroid_tracker/
├── configs/
│   └── default.yaml
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── outputs/
├── scripts/
│   ├── analyze_data.py
│   ├── download_data.py
│   └── run_pipeline.py
├── src/
│   └── asteroid_tracker/
│       ├── analysis.py
│       ├── plotting.py
│       ├── config.py
│       ├── jpl_cad.py
│       ├── paths.py
│       └── pipeline.py
├── tests/
│   ├── test_analysis.py
│   └── test_asteroid_pipeline.py
├── environment.yml
├── manage.py
├── pyproject.toml
└── requirements.txt
```

## Scientific roadmap

### v0.1 — ingestion
JPL CAD ingestion, local caching, normalized table, basic derived quantities and offline parser tests.

### v0.2 — analysis
First increment implemented: closest-approach ranking with JPL 3-sigma bounds.
Other exploratory plots and rankings remain future work:
- closest approaches;
- relative velocity;
- absolute magnitude;
- diameter where available;
- uncertainty-aware presentation.

### v0.3 — object enrichment
Use the JPL SBDB API to retrieve orbital and physical information for selected objects.

### v0.4 — orbital layer
Optional orbital elements / ephemeris integration, potentially through JPL Horizons.

### v1.0 — tracker
Interactive interface built on top of the validated scientific pipeline.

## Reproducibility

Code, configuration, tests and documentation belong in Git. Raw API data and generated outputs do not.

The goal is for the same repository to run on:
- a local Windows/WSL machine;
- Google Colab;
- ENSMA computers;
- other Linux/cloud environments later.

## JPL API etiquette

The project intentionally performs one request at a time and caches the raw response instead of polling repeatedly. The User-Agent identifies the project and links back to this repository.

## Status

**v0.1 ingestion plus the first v0.2 increment: offline closest-approach analysis.**
