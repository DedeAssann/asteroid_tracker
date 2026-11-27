# Asteroid Tracker

Portable scientific Python project for exploring **near-Earth object (NEO) close approaches** using official NASA/JPL SSD/CNEOS data.

## Current milestone — v0.2.2 close-approach kinematics

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

## Offline close-approach kinematics (v0.2.2)

Use the existing processed CSV; this command never downloads or normalizes data:

```bash
python manage.py analyze-velocity
# If you know the input contains Earth encounters but it has no body column:
python manage.py analyze-velocity --assume-body Earth
# Optional configuration and interpreter selection:
python manage.py analyze-velocity --current --config configs/default.yaml
```

No new dependencies are required. Existing commands and artifacts are preserved.
The new files are:

```text
outputs/figures/velocity_distribution.png
outputs/figures/distance_vs_velocity.png
outputs/figures/relative_vs_infinity_velocity.png
outputs/velocity_analysis_summary.json
```

All input encounters are considered, including repeated objects; there is no
ranking or top-ten truncation. Each observable has its own valid population:

- The relative-velocity histogram uses every valid `v_rel`, with sample count,
  median and minimum–maximum range. Ten equal-width bins span zero to the sample
  maximum (zero-only samples use a 0–1 km/s plotting interval).
- The distance–velocity scatter uses rows with valid `dist` and `v_rel`.
  Distance is recomputed from au using the existing fixed LD convention.
- The velocity comparison uses rows with both `v_inf` (horizontal axis) and
  `v_rel` (vertical axis), with equal axis scales and a 1:1 reference line.

The JSON reports count, mean, median, minimum and maximum for each observable,
plot sample sizes, input SHA-256/path/byte size/columns, completeness categories,
body assumptions, and all encounter-level residuals or skip reasons. Statistics
are descriptive of this selected CSV, not a debiased asteroid population.
Mixed bodies are included in descriptive plots; body counts are reported in JSON.
Neither speed nor distance is a hazard score.

### Earth two-body consistency diagnostic

For eligible Earth encounters, compute

```text
r = dist_au * 149597870.7 km
R = v_rel² - v_inf² - 2 * 398600.4418 / r   [km²/s²]
```

Here `mu_E = 398600.4418 km³/s²`, and `r` is nominal **center-to-center distance**,
not altitude. In an isolated Earth–massless-object two-body model, conservation
of specific orbital energy implies R near zero. This is a **simplified
consistency check**, not independent validation of JPL's numerical trajectory.
Other bodies, non-two-body effects, the CAD velocity definitions and rounding
can affect this relation. The [JPL CAD documentation](https://ssd-api.jpl.nasa.gov/doc/cad.html)
defines `v_rel` relative to the approach body and `v_inf` relative to a massless
body. We do not fit a trajectory, infer velocity uncertainties, propagate distance
bounds as velocity errors, or turn residuals into impact probabilities.

Signed and absolute residual statistics are included, together with the count of
evaluated Earth encounters where `v_rel < v_inf`. No observational uncertainties
or physical acceptance tolerance are supplied, so **no pass/fail verdict** is
assigned to JPL records. Numerical tests use exact synthetic two-body references.

The CSV `body` label is authoritative for selection (case-insensitive Earth).
When absent, the body remains unknown unless `--assume-body Earth` is explicitly
provided. That assumption fills missing bodies only, never overrides a recorded
non-Earth body, and is counted and saved per event. The current configured query
is unverified context, not evidence about an older cached CSV; it does not trigger
Earth classification. This matters because single-body CAD results can omit
`body`, and v0.1 did not preserve historical query metadata.

### Invalid data and reproducibility

Numeric fields are classified independently as valid, missing, nonnumeric,
nonfinite, or negative; counts sum to the total records for each field. Empty
cells and null tokens (`null`, `none`, `na`, `n/a`, case-insensitive) are missing;
explicit `NaN`/infinities are nonfinite. Missing columns are counted and listed.
Finite zero velocities and zero distances remain usable for descriptive plots,
but zero distance cannot enter the energy formula. Negative, nonnumeric and
nonfinite values are excluded only from calculations requiring that field.
Unrepresentable derived LD values are counted separately. Energy overflow is
reported as a numerical-range error, never serialized as NaN or infinity.

One primary energy status is recorded per row, in this precedence order:
unknown body, non-Earth, missing/invalid input, zero distance, numerical-range
error, or evaluated. Statistics with no observations are `null` with count zero;
empty CSVs (including v0.1's blank zero-record file) and entirely invalid samples
produce labeled no-data figures. A nonempty CSV with none of `dist`, `v_rel`,
`v_inf` fails clearly. No values or uncertainties are imputed.

The same bytes, paths, configuration and explicit assumption produce identical
JSON. The SHA-256 covers exactly the bytes read once for analysis. Plotting uses
Agg without a GUI. WSL and Colab use the same pathlib-based paths and existing
`SCI_DATA_DIR` / `SCI_OUTPUT_DIR` overrides. PNG bytes may vary with Matplotlib
and font versions. No SBDB, Horizons, Sentry or interactive dashboard is added.

### Colab validation of this increment

In a fresh Colab notebook, run these cells. Cloning and installing dependencies
need network access; the tests and analysis use local data only.

```python
!git clone --branch feat/v0.2.2-close-approach-kinematics https://github.com/DedeAssann/asteroid_tracker.git
%cd asteroid_tracker
!python manage.py setup --current
!python manage.py test --current -q
```

For a self-contained **synthetic** smoke test (not real JPL observations), use
isolated directories so an existing processed CSV is not overwritten:

```python
from pathlib import Path
import os

root = Path.cwd() / "work" / "colab_kinematics_validation"
processed = root / "data" / "processed"
processed.mkdir(parents=True, exist_ok=True)
(processed / "cad_close_approaches.csv").write_text(
    "des,dist,v_rel,v_inf,body\n"
    "SYNTHETIC-A,0.01,8,7,Earth\n"
    "SYNTHETIC-B,0.02,12,11,Earth\n"
    "SYNTHETIC-C,0.03,9,,Earth\n",
    encoding="utf-8",
)
os.environ["SCI_DATA_DIR"] = str(root / "data")
os.environ["SCI_OUTPUT_DIR"] = str(root / "outputs")
!python manage.py analyze-velocity --current
```

Inspect the artifacts and provenance:

```python
import hashlib
import json
from IPython.display import Image, display

out = root / "outputs"
report = json.loads((out / "velocity_analysis_summary.json").read_text())
assert report["records_analyzed"] == 3
assert report["energy_consistency"]["records_evaluated"] == 2
assert report["input_provenance"]["sha256"] == hashlib.sha256(
    (processed / "cad_close_approaches.csv").read_bytes()
).hexdigest()
for name in ("velocity_distribution", "distance_vs_velocity", "relative_vs_infinity_velocity"):
    display(Image(filename=str(out / "figures" / f"{name}.png")))
```

For real-data validation, point `SCI_DATA_DIR` at your existing cached processed
CSV directory and `SCI_OUTPUT_DIR` at a separate validation output directory.
Use the Earth assumption only if the original query body is known. No download
command is needed. Automated CLI tests block socket connections, check repeated
JSON, and verify that previous outputs and input bytes are unchanged.

## v0.2.3 — Absolute magnitude and diameter

```bash
python manage.py analyze-physical
```

This command reads the existing `data/processed/cad_close_approaches.csv`.
It writes `outputs/physical_analysis_summary.json` and four PNGs under
`outputs/figures`. Use `--config`, `SCI_DATA_DIR`, or `SCI_OUTPUT_DIR`
with the same path conventions as the other analyses. Rendering uses Agg
and all analysis is offline.

| Figure | Population and quantities |
| --- | --- |
| `absolute_magnitude_distribution.png` | Encounters with valid H, annotated with count, median and range |
| `diameter_completeness.png` | Identified objects, counted once each across all encounters |
| `diameter_albedo_sensitivity.png` | Theoretical curves on a fixed reference grid from H = 10 to 35 mag |
| `h_vs_known_diameter.png` | Encounters with valid H and positive JPL CAD diameter, with reported ±1σ where present |

H is absolute magnitude in magnitudes, defined at standardized observing
geometry. It does not give the apparent brightness during an Earth encounter.
Finite negative H is allowed. Catalog diameter must be finite and positive.
A finite, nonnegative `diameter_sigma` is a reported absolute 1-sigma
uncertainty in km. An absent or invalid sigma leaves the point visible
without error bars. Both quantities come from the same CSV record.

The reference curves use the uniform-surface spherical photometric model:

```text
D_km = 1329 / sqrt(pV) * 10**(-H/5)
```

The geometric albedos pV = 0.05, 0.14 and 0.25 are hypothetical and dimensionless.
They illustrate sensitivity to surface reflectivity. No object is assigned an
albedo or a photometric diameter. The curves are separate from the JPL catalog
diameters and do not represent empirical uncertainty bands. H and the model
assumptions also contribute uncertainty. The analysis makes no hazard inference.
See the [CNEOS size estimator](https://cneos.jpl.nasa.gov/tools/ast_size_est.html)
and the [JPL CAD field documentation](https://ssd-api.jpl.nasa.gov/doc/cad.html).

Object coverage groups exact trimmed `des` labels. For rows with no designation,
`fullname` can link to a single designation observed in the CSV or form its own
group if there is no such link. Ambiguous or absent identifiers are counted
separately. An object is known if any encounter supplies a valid diameter,
invalid if it has unusable values but no valid diameter, and missing if all of
its entries are missing. Repeated encounters still contribute individually to
the H distribution and scatter. Undocumented aliases can affect the object count.

Missing fields and blank cells are tracked. Invalid numeric values are broken out
by reason. The ingestion pipeline can coerce unusable source values to blanks
before this analysis sees them. The JSON records the CSV columns and SHA-256 of
the exact bytes read. Query filters, discovery bias toward easier-to-detect
objects, and selective follow-up for diameter determination limit the sample.
The coverage describes this CSV and cannot establish the fraction of all
asteroids with known diameters.

### Colab validation with an actual cached JPL CSV

In a fresh notebook, clone the feature branch containing this increment and run
the suite. Clone and setup need network access.

```python
!git clone --branch feat/v0.2.3-physical-analysis https://github.com/DedeAssann/asteroid_tracker.git
%cd asteroid_tracker
!python manage.py setup --current
!python manage.py test --current -q
```

Upload your existing processed JPL CAD CSV when prompted. This example copies
it to an isolated local directory. For an existing mounted cache, set
`SCI_DATA_DIR` to the parent of its `processed` directory instead.

```python
from pathlib import Path
from google.colab import files
import os

uploaded = files.upload()
source = Path("/content/physical-validation/data/processed/cad_close_approaches.csv")
source.parent.mkdir(parents=True, exist_ok=True)
source.write_bytes(uploaded["cad_close_approaches.csv"])
os.environ["SCI_DATA_DIR"] = str(source.parent.parent)
os.environ["SCI_OUTPUT_DIR"] = "/content/physical-validation/outputs"
!python manage.py analyze-physical --current
```

```python
import hashlib
import json
from IPython.display import Image, display

out = Path(os.environ["SCI_OUTPUT_DIR"])
report = json.loads((out / "physical_analysis_summary.json").read_text())
assert report["input_provenance"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
objects = report["identified_objects"]
assert sum(objects["diameter_coverage"].values()) == objects["count"]
print(report["encounters"], objects)
for name in (
    "absolute_magnitude_distribution", "diameter_completeness",
    "diameter_albedo_sensitivity", "h_vs_known_diameter",
):
    display(Image(filename=str(out / "figures" / f"{name}.png")))
```

## v0.2.4 — Scientific provenance

The existing commands record a local chain from the HTTP request to the
scientific outputs:

```bash
python manage.py download
python manage.py run
python manage.py analyze
python manage.py analyze-velocity
python manage.py analyze-physical
```

With the default names, the raw sidecar is
`data/raw/cad_close_approaches.json.acquisition.json` and the processed sidecar
is `data/processed/cad_close_approaches.csv.processing.json`. Both default
directories and customizable artifact names work with the same path settings as
the data files.

### Sidecar schema v1

| Location | Meaning |
| --- | --- |
| Acquisition `request` | Initial endpoint and ordered, decoded query parameters from the actual prepared HTTP request. `final_url` records the request URL after redirects, with user information, fragments and undocumented query values removed or redacted. Keep credentials out of configured URL paths and public CAD parameters. |
| Acquisition `request.relative_date_inputs` and `request.final_relative_date_inputs` | Relative input literals such as `now` and `+30`. The client does not resolve them or know the exact bounds used internally by JPL. |
| Acquisition `acquired_at_utc` | ISO 8601 UTC client time after receiving and validating a new response, before local publication. The sidecar also records the source, CAD API version, returned record count, and the raw artifact descriptor. |
| Acquisition `download_status` | `new_acquisition` identifies the event that created the sidecar. A subsequent `cache_hit` is reported by the command and does not change the acquisition time or original request. |
| Processing `processed_at_utc` | ISO 8601 UTC client time after creating the CSV bytes, before local publication. The sidecar records the normalization settings, Python and pandas versions, normalization and implementation versions, row count, and raw and CSV artifact descriptors. |
| Artifact descriptor | Historical path, byte count and SHA-256 of exactly the bytes saved or consumed. Paths are informative. A relocated archive remains verifiable. Hash matches establish local byte identity relative to a receipt. They do not authenticate the external source. |
| Processing `acquisition` | Snapshot of the acquisition receipt verified against the raw bytes at processing time, or a `missing` status for a legacy raw file. |
| Analysis `input_provenance.chain` | All three analyses verify the local CSV hash and row count against the processing receipt, then check the embedded acquisition linkage. `complete` means the CSV was checked during analysis and the raw acquisition was checked at processing time. Archive verification against the raw file itself is shown below. |
| Analysis `analysis_execution` | Each execution is offline. Reports omit execution timestamps so reruns against the same CSV, receipts and analysis options remain deterministic. Reprocessing creates a new processing timestamp and receipt. |

A default download reuses existing raw data and verifies its receipt when
available. Legacy raw files with no receipt remain usable, with unknown
historical request details. A hash mismatch or unusable acquisition receipt
blocks the cache hit and processing, with no automatic network refresh. Restore
a matching pair or explicitly issue `download --force` for a new acquisition.
An analysis can still use a standalone readable CSV with missing, invalid or
stale processing metadata. Its chain is marked incomplete and historical query
details are withheld. Existing distance and velocity reports can still show
current configuration as explicitly unverified context.

### Interrupted writes and recovery

Writers stage and flush a receipt before atomically replacing the data file.
They then replace the committed receipt with the staged receipt. If a write
stops before the data replacement, the old data and receipt remain usable. If
it stops after replacement, the matching `.pending` receipt is recognized by
hash and labeled as pending. A cache hit can promote a matching acquisition
receipt. Re-run the pipeline to publish a processing receipt after an
interruption. A failed HTTP request or an invalid new response leaves the
existing raw file and receipt intact.

Writers use an exclusive `.provenance.lock` directory. After an abrupt process
termination, confirm that no writer is active before removing a leftover
lock directory. Keep both receipts while recovering and preserve whichever
matches the data. A leftover temporary file from a killed writer can be
removed once activity has stopped. If neither receipt matches, restore the
archived pair, explicitly acquire new raw data, or reprocess a verified raw
file as appropriate. These guarantees rely on atomic same-directory
replacement on the local filesystem. Use the local Colab filesystem for
processing, then copy both artifacts and their receipts to durable storage.

### Verify an archive in Colab

Clone the feature branch containing v0.2.4 and install the project:

```python
!git clone --branch feat/v0.2.4-scientific-provenance https://github.com/DedeAssann/asteroid_tracker.git
%cd asteroid_tracker
!python manage.py setup --current
!python manage.py test --current -q
```

Copy your archive's `raw` and `processed` directories, including their receipts,
to `/content/cad-archive`. Run the three analyses against that CSV. To assemble
a new chain, start with an empty archive directory and uncomment the optional
download and processing commands. Archive the resulting data and both receipts.
Repeating a live query at a later date is a new acquisition even when its query
text is identical.

```python
import os

os.environ["SCI_DATA_DIR"] = "/content/cad-archive"
os.environ["SCI_OUTPUT_DIR"] = "/content/cad-validation"
# For a new acquisition in an empty archive, uncomment these commands.
# !python manage.py download --current
# !python manage.py run --current
# !python manage.py download --current  # Demonstrate a cache hit.
!python manage.py analyze --current
!python manage.py analyze-velocity --current
!python manage.py analyze-physical --current
```

```python
from hashlib import sha256
import json
from pathlib import Path

root = Path(os.environ["SCI_DATA_DIR"])
raw = root / "raw/cad_close_approaches.json"
csv = root / "processed/cad_close_approaches.csv"
out = Path(os.environ["SCI_OUTPUT_DIR"])
acquisition = json.loads(raw.with_suffix(".json.acquisition.json").read_bytes())
processing = json.loads(csv.with_suffix(".csv.processing.json").read_bytes())
raw_digest = sha256(raw.read_bytes()).hexdigest()
csv_digest = sha256(csv.read_bytes()).hexdigest()

assert acquisition["raw"]["sha256"] == processing["raw"]["sha256"] == raw_digest
assert processing["acquisition"]["metadata"] == acquisition
assert processing["csv"]["sha256"] == csv_digest
for name in ("analysis_summary", "velocity_analysis_summary", "physical_analysis_summary"):
    report = json.loads((out / f"{name}.json").read_bytes())
    provenance = report["input_provenance"]
    assert provenance["sha256"] == csv_digest
    assert provenance["chain"]["status"] == "complete"
    assert provenance["chain"]["processing"]["metadata"] == processing
print(acquisition["acquired_at_utc"], acquisition["request"]["relative_date_inputs"])
```

When using a legacy archive, run the analysis and inspect the incomplete status
instead of expecting these assertions to pass. Retain the original raw bytes,
CSV bytes and both sidecars for a complete archive. Use the recorded Python
and pandas versions and CSV line terminator when checking byte-for-byte regeneration.

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
│   ├── analyze_physical.py
│   ├── analyze_velocity.py
│   ├── download_data.py
│   └── run_pipeline.py
├── src/
│   └── asteroid_tracker/
│       ├── provenance.py
│       ├── physical_analysis.py
│       ├── physical_plotting.py
│       ├── velocity_analysis.py
│       ├── velocity_plotting.py
│       ├── analysis.py
│       ├── plotting.py
│       ├── config.py
│       ├── jpl_cad.py
│       ├── paths.py
│       └── pipeline.py
├── tests/
│   ├── test_provenance.py
│   ├── test_physical_analysis.py
│   ├── test_velocity_analysis.py
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
Implemented: closest-approach ranking with JPL 3-sigma bounds, v0.2.2 encounter kinematics, and v0.2.3 photometry and catalog diameter coverage.
Other exploratory plots and rankings remain future work:
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

**v0.1 ingestion plus v0.2 closest-approach analysis and v0.2.2 kinematics.**
