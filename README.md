# Asteroid Tracker

Portable scientific Python project for exploring **near-Earth object (NEO) close approaches** using official NASA/JPL SSD/CNEOS data.

## Current milestone — v0.1

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
python manage.py test
```

### Conda / Colab / ENSMA

In Google Colab, `manage.py` now detects the notebook runtime automatically and uses the current Python interpreter instead of creating a nested virtual environment.

```bash
python manage.py setup
python manage.py download
python manage.py run
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
```

These generated files are ignored by Git and can be recreated from the API.

The processed table adds, when possible:

- nominal distance in au;
- distance in km;
- distance in lunar distances;
- relative velocity in km/s;
- diameter in metres when JPL provides a measured/estimated diameter.

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
│   ├── download_data.py
│   └── run_pipeline.py
├── src/
│   └── asteroid_tracker/
│       ├── config.py
│       ├── jpl_cad.py
│       ├── paths.py
│       └── pipeline.py
├── tests/
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
Exploratory plots and rankings:
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

**v0.1 implementation in progress.**
