"""Validated VIRTUO and ICIS processing without retaining patient identifiers."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


class ReportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ProcessingStats:
    virtuo_rows_loaded: int
    virtuo_rows_after_cleaning: int
    monthly_rows_loaded: int
    matched_rows: int
    unmatched_rows: int
    invalid_volume_rows: int


@dataclass(frozen=True)
class ProcessingResult:
    data: pd.DataFrame
    stats: ProcessingStats


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip().lower().replace(" ", "_") for column in frame.columns]
    return frame


def _read(path: str | Path, label: str) -> pd.DataFrame:
    try:
        return _normalise(pd.read_excel(path))
    except Exception as exc:
        raise ReportValidationError(f"Could not read {label}: {exc}") from exc


def _require(frame: pd.DataFrame, columns: Iterable[str], label: str):
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ReportValidationError(f"{label} is missing: {', '.join(missing)}")


def _accessions(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True).str.strip()


def process_reports(virtuo_1, virtuo_2, icis) -> ProcessingResult:
    first, second, monthly = _read(virtuo_1, "VIRTUO report 1"), _read(virtuo_2, "VIRTUO report 2"), _read(icis, "ICIS report")
    virtuo = pd.concat([first, second], ignore_index=True, sort=False)
    loaded = len(virtuo)
    _require(virtuo, ("accession_id", "sample_volume"), "VIRTUO reports")
    _require(monthly, ("formattedaccessnumber", "collect_dt_tm", "loc_nurse_unit"), "ICIS report")
    accession = virtuo["accession_id"].astype(str)
    volume = virtuo["sample_volume"].astype(str).str.strip()
    virtuo = virtuo[~accession.str.contains("ML", case=False, na=False) & accession.str.contains(r"[A-Za-z]$", na=False) & volume.str.contains(r"ml$", case=False, na=False)].copy()
    virtuo["accession_number"] = _accessions(virtuo["accession_id"])
    virtuo = virtuo[virtuo["accession_number"] != ""]
    monthly["accession_clean"] = _accessions(monthly["formattedaccessnumber"])
    lookup = monthly[["accession_clean", "collect_dt_tm", "loc_nurse_unit"]].drop_duplicates("accession_clean", keep="first")
    merged = virtuo.merge(lookup, left_on="accession_number", right_on="accession_clean", how="left", validate="many_to_one")
    matched = merged[merged["accession_clean"].notna()].copy()
    unmatched_count = int(merged["accession_clean"].isna().sum())
    matched["collect_dt_tm"] = pd.to_datetime(matched["collect_dt_tm"], errors="coerce")
    matched["month"] = matched["collect_dt_tm"].dt.to_period("M").astype("string")
    matched["volume_ml"] = pd.to_numeric(matched["sample_volume"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0], errors="coerce")
    stats = ProcessingStats(loaded, len(virtuo), len(monthly), len(matched), unmatched_count, int(matched["volume_ml"].isna().sum()))
    # Return only fields required for aggregate reporting; identifiers are discarded.
    return ProcessingResult(matched[["month", "loc_nurse_unit", "volume_ml"]].copy(), stats)


def aggregate_report(data: pd.DataFrame) -> pd.DataFrame:
    valid = data.dropna(subset=["month", "loc_nurse_unit", "volume_ml"]).copy()
    if valid.empty:
        raise ReportValidationError("No valid matched rows were available to publish.")
    result = valid.groupby(["month", "loc_nurse_unit"]).agg(
        total=("volume_ml", "count"),
        compliant=("volume_ml", lambda values: int((values >= 5).sum())),
        above_maximum=("volume_ml", lambda values: int((values > 10).sum())),
    ).reset_index().rename(columns={"loc_nurse_unit": "location"})
    return result
