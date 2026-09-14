# BCChampion

**BCChampion** is a local desktop blood-culture quality-improvement dashboard for monitoring adult blood-culture fill-volume compliance. It processes two VIRTUO Excel exports plus one ICIS Excel export, matches records by accession number for processing, and retains only aggregate month/unit/volume metrics in the local dashboard database.

## Publication release
Version: **1.0.0**  
Release type: publication-safe desktop/reference implementation.
10.5281/zenodo.22753805

## Core rule
A blood-culture bottle is considered compliant when the estimated volume is **≥5 mL**. Bottles with volume **>10 mL** are additionally counted as overfilled.

## Privacy
Uploaded source workbooks are processed locally. The processing engine returns only month, nursing unit and volume for aggregation; accession identifiers are discarded before aggregate storage. Do not publish or redistribute real patient-level exports.

## Windows desktop build (no Python required by end users)
The GitHub Actions workflow in `.github/workflows/windows-build.yml` builds self-contained Windows executables with PyInstaller. End users download the Release ZIP and do not need Python installed.

## Input columns
VIRTUO files: `accession_id`, `sample_volume`  
ICIS file: `formattedaccessnumber`, `collect_dt_tm`, `loc_nurse_unit`

## Run from source (developers only)
`pip install -r requirements.txt` then `python desktop_launcher.py`.

## Citation
See `CITATION.cff`. Before the first commit, replace `YOUR-GITHUB-USERNAME` with the repository owner's GitHub username. After Zenodo archiving, add the assigned version DOI to the repository and manuscript.

## Licence
BCChampion is released under the MIT License. See `LICENSE.txt`.

## Disclaimer
BCChampion is a quality-improvement and research-support tool. It is not a medical device and does not provide diagnostic or treatment recommendations. Local validation and governance approval are required before operational use.
