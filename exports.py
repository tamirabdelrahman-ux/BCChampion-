"""Publication-quality image and Excel exports for dashboard figures."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile

_matplotlib_config = Path(tempfile.gettempdir()) / "blood-dashboard-matplotlib"
_matplotlib_config.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_config))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


GREEN = "#006b54"
RED = "#bd4238"
GRID = "#dce5e1"
INK = "#26342f"

FIGURE_NAMES = {
    "high_volume",
    "low_volume",
    "performance_compliance",
    "performance_overfilled",
    "compliance_heatmap",
    "overfilled_heatmap",
}


def prepare_export_data(rows) -> pd.DataFrame:
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return pd.DataFrame(columns=["month", "location", "total", "compliant", "above_maximum"])
    for column in ("total", "compliant", "above_maximum"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["compliance_rate"] = np.where(frame["total"] > 0, frame["compliant"] / frame["total"] * 100, np.nan)
    frame["overfilled_rate"] = np.where(frame["total"] > 0, frame["above_maximum"] / frame["total"] * 100, np.nan)
    return frame


def _location_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["location", "total", "compliant", "above_maximum", "compliance_rate", "overfilled_rate"])
    summary = frame.groupby("location", as_index=False)[["total", "compliant", "above_maximum"]].sum()
    summary["compliance_rate"] = np.where(summary["total"] > 0, summary["compliant"] / summary["total"] * 100, np.nan)
    summary["overfilled_rate"] = np.where(summary["total"] > 0, summary["above_maximum"] / summary["total"] * 100, np.nan)
    return summary.sort_values("location")


def _heatmap_frame(frame: pd.DataFrame, value: str) -> pd.DataFrame:
    frame = frame[frame["month"] >= "2026-01"] if not frame.empty else frame
    if frame.empty:
        return pd.DataFrame()
    pivot = frame.pivot_table(index="location", columns="month", values=value, aggfunc="mean").sort_index()
    latest_months = sorted(pivot.columns)[-12:]
    return pivot.reindex(columns=latest_months)


def create_figure(frame: pd.DataFrame, figure_name: str, file_format: str) -> BytesIO:
    if figure_name not in FIGURE_NAMES or file_format not in {"png", "svg"}:
        raise ValueError("Unsupported export request")
    if figure_name in {"high_volume", "low_volume"}:
        figure = _volume_figure(frame, figure_name == "high_volume")
    elif figure_name in {"performance_compliance", "performance_overfilled"}:
        figure = _performance_figure(frame, figure_name == "performance_overfilled")
    else:
        figure = _heatmap_figure(frame, figure_name == "overfilled_heatmap")
    output = BytesIO()
    figure.savefig(output, format=file_format, dpi=300 if file_format == "png" else None, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    output.seek(0)
    return output


def _volume_figure(frame: pd.DataFrame, high_volume: bool):
    summary = _location_summary(frame)
    summary = summary[summary["total"] >= 10] if high_volume else summary[summary["total"] < 10]
    title = "Monthly Volume Compliance — High-Volume Units" if high_volume else "Monthly Volume Compliance — Low-Volume Units"
    figure, axis = plt.subplots(figsize=(10, 6), layout="constrained")
    if summary.empty:
        axis.text(0.5, 0.5, "No data available for the selected scope", ha="center", va="center", color=INK)
        axis.set_axis_off()
        axis.set_title(title, fontsize=16, fontweight="bold", color=INK)
        return figure
    values = summary["compliance_rate"].to_numpy()
    colors = [GREEN if value >= 90 else RED for value in values]
    bars = axis.bar(summary["location"], values, color=colors, width=0.62)
    axis.axhline(90, color="#2c6ea3", linestyle="--", linewidth=1.7, label="90% target")
    axis.set_ylim(0, 105)
    axis.set_yticks(np.arange(0, 101, 10))
    axis.set_yticklabels([f"{value}%" for value in range(0, 101, 10)])
    axis.set_ylabel("Compliance (%)")
    axis.set_title(title, fontsize=16, fontweight="bold", color=INK)
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.legend(frameon=False, loc="upper right")
    for bar, row in zip(bars, summary.itertuples(index=False)):
        axis.text(bar.get_x() + bar.get_width() / 2, min(row.compliance_rate + 2, 102), f"{row.compliance_rate:.1f}%\n({int(row.compliant)}/{int(row.total)})", ha="center", va="bottom", fontsize=9, color=INK)
    return figure


def _performance_figure(frame: pd.DataFrame, overfilled: bool):
    summary = _location_summary(frame)
    value_column = "overfilled_rate" if overfilled else "compliance_rate"
    title = "Overfilled Bottles by Nursing Unit" if overfilled else "Volume Compliance by Nursing Unit"
    figure_height = max(4.5, 0.52 * max(len(summary), 1) + 2)
    figure, axis = plt.subplots(figsize=(10, figure_height), layout="constrained")
    if summary.empty:
        axis.text(0.5, 0.5, "No data available for the selected scope", ha="center", va="center", color=INK)
        axis.set_axis_off()
        axis.set_title(title, fontsize=16, fontweight="bold", color=INK)
        return figure
    summary = summary.sort_values(value_column, ascending=True)
    values = summary[value_column].to_numpy()
    colors = [RED] * len(summary) if overfilled else [GREEN if value >= 90 else RED for value in values]
    bars = axis.barh(summary["location"], values, color=colors, height=0.62)
    target = 10 if overfilled else 90
    axis.axvline(target, color="#2c6ea3", linestyle="--", linewidth=1.7, label=f"{target}% {'limit' if overfilled else 'target'}")
    axis.set_xlim(0, max(100 if not overfilled else 20, float(np.nanmax(values)) * 1.18 if len(values) else 20))
    axis.set_xlabel("Overfilled bottles (%)" if overfilled else "Compliance (%)")
    axis.set_title(title, fontsize=16, fontweight="bold", color=INK)
    axis.grid(axis="x", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.legend(frameon=False, loc="lower right")
    for bar, value in zip(bars, values):
        axis.text(value + axis.get_xlim()[1] * 0.01, bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", va="center", fontsize=10, fontweight="bold", color=INK)
    return figure


def _heatmap_figure(frame: pd.DataFrame, overfilled: bool):
    value_column = "overfilled_rate" if overfilled else "compliance_rate"
    pivot = _heatmap_frame(frame, value_column)
    totals = frame.pivot_table(index="location", columns="month", values="total", aggfunc="sum").reindex(index=pivot.index, columns=pivot.columns)
    title = "Rolling 12-Month Overfilling Status by Unit" if overfilled else "Rolling 12-Month Compliance Status by Unit"
    figure_width = max(8, 1.05 * max(len(pivot.columns), 1) + 4)
    figure_height = max(4.5, 0.55 * max(len(pivot.index), 1) + 2.2)
    figure, axis = plt.subplots(figsize=(figure_width, figure_height), layout="constrained")
    if pivot.empty:
        axis.text(0.5, 0.5, "No data available for the selected scope", ha="center", va="center", color=INK)
        axis.set_axis_off()
        axis.set_title(title, fontsize=16, fontweight="bold", color=INK)
        return figure
    values = pivot.to_numpy(dtype=float)
    status = np.where(np.isnan(values), np.nan, np.where(values <= 10 if overfilled else values >= 90, 1, 0))
    from matplotlib.colors import ListedColormap
    axis.imshow(status, aspect="auto", cmap=ListedColormap(["#f8dfdc", "#d9efe6"]), vmin=0, vmax=1)
    axis.set_xticks(range(len(pivot.columns)), labels=pivot.columns)
    axis.set_yticks(range(len(pivot.index)), labels=pivot.index)
    axis.set_title(title, fontsize=16, fontweight="bold", color=INK, pad=14)
    for row_index in range(values.shape[0]):
        for column_index in range(values.shape[1]):
            value = values[row_index, column_index]
            total = totals.iat[row_index, column_index]
            label = "—" if np.isnan(value) else f"{value:.1f}%\n({int(total)})"
            axis.text(column_index, row_index, label, ha="center", va="center", color=INK, fontsize=9, fontweight="bold")
    axis.set_xticks(np.arange(-0.5, len(pivot.columns), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(pivot.index), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=3)
    axis.tick_params(which="minor", bottom=False, left=False)
    return figure


def create_excel(frame: pd.DataFrame, dataset_name: str | None = None) -> BytesIO:
    if dataset_name is not None and dataset_name not in FIGURE_NAMES:
        raise ValueError("Unsupported export request")
    output = BytesIO()
    datasets = _excel_datasets(frame)
    selected = ({sheet_name: data for sheet_name, data in datasets.values()}
                if dataset_name is None else {datasets[dataset_name][0]: datasets[dataset_name][1]})
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, data in selected.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            sheet = writer.book[sheet_name[:31]]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                width = min(max(len(str(cell.value)) if cell.value is not None else 0 for cell in column) + 2, 42)
                sheet.column_dimensions[column[0].column_letter].width = width
    output.seek(0)
    return output


def _excel_datasets(frame: pd.DataFrame):
    summary = _location_summary(frame)
    summary_export = summary.rename(columns={
        "location": "Location", "total": "Total bottles", "compliant": "Compliant bottles",
        "above_maximum": "Overfilled bottles", "compliance_rate": "Compliance (%)",
        "overfilled_rate": "Overfilled (%)",
    })
    high = summary_export[summary_export["Total bottles"] >= 10].copy()
    low = summary_export[summary_export["Total bottles"] < 10].copy()
    compliance_heat = _heatmap_frame(frame, "compliance_rate").reset_index().rename(columns={"location": "Location"})
    overfilled_heat = _heatmap_frame(frame, "overfilled_rate").reset_index().rename(columns={"location": "Location"})
    return {
        "high_volume": ("High-volume compliance", high),
        "low_volume": ("Low-volume compliance", low),
        "performance_compliance": ("Unit compliance", summary_export[["Location", "Total bottles", "Compliant bottles", "Compliance (%)"]]),
        "performance_overfilled": ("Unit overfilling", summary_export[["Location", "Total bottles", "Overfilled bottles", "Overfilled (%)"]]),
        "compliance_heatmap": ("Compliance heatmap", compliance_heat),
        "overfilled_heatmap": ("Overfilling heatmap", overfilled_heat),
    }
