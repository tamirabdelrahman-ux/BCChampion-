"""Hospital-hosted blood-culture compliance dashboard."""

from __future__ import annotations

import json
import io
import os
import secrets
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from blood_engine import ReportValidationError, aggregate_report, process_reports
from exports import FIGURE_NAMES, create_excel, create_figure, prepare_export_data


BASE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
DATA_DIR = Path(os.getenv("BLOOD_DASHBOARD_DATA_DIR", BASE_DIR / "data"))
DATABASE_PATH = Path(os.getenv("BLOOD_DASHBOARD_DATABASE", DATA_DIR / "dashboard.sqlite3"))
UPLOAD_DIR = DATA_DIR / "temporary_uploads"


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(RESOURCE_DIR / "templates"),
        static_folder=str(RESOURCE_DIR / "static"),
    )
    app.config.update(
        SECRET_KEY=os.getenv("BLOOD_DASHBOARD_SECRET_KEY", secrets.token_hex(32)),
        MAX_CONTENT_LENGTH=75 * 1024 * 1024,
        AUTH_MODE=os.getenv("BLOOD_DASHBOARD_AUTH_MODE", "development").lower(),
        ADMIN_USERS={value.strip().lower() for value in os.getenv("BLOOD_DASHBOARD_ADMINS", "admin").split(";") if value.strip()},
        DATABASE=str(DATABASE_PATH),
        UPLOAD_FOLDER=str(UPLOAD_DIR),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    init_database(app.config["DATABASE"])

    @app.errorhandler(Exception)
    def log_unhandled_exception(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return exc
        log_path = Path(app.config["DATABASE"]).parent / "BCChampion_error.log"
        try:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("\n=== BCChampion v1.0.0 error ===\n")
                fh.write(f"Path: {request.path}\n")
                fh.write(traceback.format_exc())
        except Exception:
            pass
        return (
            "<h1>BCChampion could not load this page</h1>"
            "<p>The error has been recorded locally in <b>BCChampion_error.log</b>.</p>"
            "<p>Please close BCChampion and send that log file back for diagnosis.</p>",
            500,
        )

    @app.before_request
    def establish_identity():
        mode = app.config["AUTH_MODE"]
        if mode == "iis":
            # IIS must overwrite this header and the backend must listen on localhost only.
            raw_user = request.environ.get("REMOTE_USER") or request.headers.get("X-Remote-User", "")
            if not raw_user:
                abort(401)
            username = raw_user.split("\\")[-1].strip()
        elif mode == "development":
            username = request.headers.get("X-Debug-User", "admin").strip()
        else:
            raise RuntimeError("BLOOD_DASHBOARD_AUTH_MODE must be 'development' or 'iis'.")
        if not username:
            abort(401)
        request.current_user = username
        request.current_role = "admin" if username.lower() in app.config["ADMIN_USERS"] else "viewer"
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

    @app.context_processor
    def inject_identity():
        return {
            "current_user": getattr(request, "current_user", ""),
            "current_role": getattr(request, "current_role", "viewer"),
            "csrf_token": session.get("csrf_token", ""),
        }

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.current_role != "admin":
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    def validate_csrf():
        if not secrets.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
            abort(400, "Invalid form token")

    @app.get("/")
    def dashboard():
        with connect(app.config["DATABASE"]) as db:
            report = db.execute("SELECT * FROM reports WHERE status='published' ORDER BY published_at DESC LIMIT 1").fetchone()
            if not report:
                return render_template("dashboard.html", report=None)
            rows = db.execute("SELECT month, location, total, compliant, above_maximum FROM aggregates WHERE report_id=?", (report["id"],)).fetchall()

        months = sorted({row["month"] for row in rows if row["month"] >= "2026-01"})
        heatmap_months = months[-12:]
        locations = sorted({row["location"] for row in rows})
        selected_month = request.args.get("month")
        if selected_month not in months:
            selected_month = months[-1] if months else "All months"
        selected_locations = request.args.getlist("location") or locations
        filtered = [row for row in rows if (selected_month == "All months" or row["month"] == selected_month) and row["location"] in selected_locations]
        total = sum(row["total"] for row in filtered)
        compliant = sum(row["compliant"] for row in filtered)
        high = sum(row["above_maximum"] for row in filtered)
        rate = compliant / total * 100 if total else 0
        by_location = []
        for location in selected_locations:
            location_rows = [row for row in filtered if row["location"] == location]
            location_total = sum(row["total"] for row in location_rows)
            location_compliant = sum(row["compliant"] for row in location_rows)
            location_above = sum(row["above_maximum"] for row in location_rows)
            if location_total:
                by_location.append({
                    "location": location,
                    "total": location_total,
                    "compliant": location_compliant,
                    "above_maximum": location_above,
                    "rate": location_compliant / location_total * 100,
                    "overfilled_rate": location_above / location_total * 100,
                })
        by_location.sort(key=lambda item: item["rate"], reverse=True)
        high_volume = [item for item in by_location if item["total"] >= 10]
        low_volume = [item for item in by_location if item["total"] < 10]
        trend_series = []
        for location in selected_locations:
            values = []
            for month in heatmap_months:
                month_rows = [row for row in rows if row["location"] == location and row["month"] == month]
                month_total = sum(row["total"] for row in month_rows)
                month_compliant = sum(row["compliant"] for row in month_rows)
                values.append({
                    "month": month,
                    "total": month_total,
                    "compliant": month_compliant,
                    "above_maximum": sum(row["above_maximum"] for row in month_rows),
                    "rate": month_compliant / month_total * 100 if month_total else None,
                    "overfilled_rate": sum(row["above_maximum"] for row in month_rows) / month_total * 100 if month_total else None,
                })
            if any(value["total"] for value in values):
                trend_series.append({"location": location, "values": values})
        return render_template(
            "dashboard.html", report=report, months=months, heatmap_months=heatmap_months, locations=locations,
            selected_month=selected_month, selected_locations=selected_locations, total=total,
            compliant=compliant, high=high, rate=rate, by_location=by_location,
            high_volume=high_volume, low_volume=low_volume, trend_series=trend_series,
            export_query=urlencode({"month": selected_month, "location": selected_locations}, doseq=True),
        )

    def export_rows(include_all_months=False):
        with connect(app.config["DATABASE"]) as db:
            report = db.execute("SELECT id, title FROM reports WHERE status='published' ORDER BY published_at DESC LIMIT 1").fetchone()
            if not report:
                abort(404)
            rows = db.execute("SELECT month, location, total, compliant, above_maximum FROM aggregates WHERE report_id=?", (report["id"],)).fetchall()
        selected_month = "All months" if include_all_months else request.args.get("month", "All months")
        selected_locations = request.args.getlist("location")
        filtered = [row for row in rows if (selected_month == "All months" or row["month"] == selected_month) and (not selected_locations or row["location"] in selected_locations)]
        return report, prepare_export_data(filtered)

    @app.get("/export/figure/<figure_name>.<file_format>")
    def export_figure(figure_name, file_format):
        if figure_name not in FIGURE_NAMES or file_format not in {"png", "svg"}:
            abort(404)
        report, frame = export_rows(include_all_months=figure_name in {"compliance_heatmap", "overfilled_heatmap"})
        output = create_figure(frame, figure_name, file_format)
        return send_file(
            output, mimetype="image/png" if file_format == "png" else "image/svg+xml",
            as_attachment=True, download_name=f"{secure_filename(report['title'])}_{figure_name}.{file_format}",
        )

    @app.get("/export/excel/<dataset_name>")
    def export_excel(dataset_name):
        if dataset_name not in FIGURE_NAMES:
            abort(404)
        report, frame = export_rows(include_all_months=dataset_name in {"compliance_heatmap", "overfilled_heatmap"})
        return send_file(
            create_excel(frame, dataset_name),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name=f"{secure_filename(report['title'])}_{dataset_name}.xlsx",
        )

    @app.get("/export/excel-all")
    def export_excel_all():
        report, frame = export_rows()
        return send_file(
            create_excel(frame),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name=f"{secure_filename(report['title'])}_all_figures.xlsx",
        )

    @app.route("/admin", methods=["GET", "POST"])
    @admin_required
    def admin():
        if request.method == "POST":
            validate_csrf()
            title = request.form.get("title", "").strip()
            files = [request.files.get(name) for name in ("virtuo_1", "virtuo_2", "icis")]
            champion_name = request.form.get("champion_name", "").strip()
            champion_month = request.form.get("champion_month", "").strip()
            champion_file = request.files.get("champion_photo")
            if not title or not all(files) or not all(file.filename for file in files):
                flash("Enter a report title and select all three Excel files.", "error")
                return redirect(url_for("admin"))
            upload_id = secrets.token_hex(8)
            folder = Path(app.config["UPLOAD_FOLDER"]) / upload_id
            folder.mkdir(parents=True, exist_ok=False)
            paths = []
            try:
                champion_photo, champion_photo_mime = validate_champion_photo(champion_file)
                for index, file in enumerate(files):
                    suffix = Path(secure_filename(file.filename)).suffix.lower()
                    if suffix not in {".xlsx", ".xls"}:
                        raise ReportValidationError("Only Excel .xlsx or .xls files are accepted.")
                    path = folder / f"input_{index}{suffix}"
                    file.save(path)
                    paths.append(path)
                result = process_reports(*paths)
                aggregates = aggregate_report(result.data)
                report_id = save_draft(
                    app.config["DATABASE"], title, request.current_user, result.stats.__dict__, aggregates,
                    champion_name, champion_month, champion_photo, champion_photo_mime,
                )
                audit(app.config["DATABASE"], request.current_user, "draft_created", report_id)
                flash("Reports processed successfully. Review the draft before publishing.", "success")
                return redirect(url_for("review", report_id=report_id))
            except ReportValidationError as exc:
                flash(str(exc), "error")
            finally:
                for path in paths:
                    path.unlink(missing_ok=True)
                try:
                    folder.rmdir()
                except OSError:
                    pass
            return redirect(url_for("admin"))

        with connect(app.config["DATABASE"]) as db:
            reports = db.execute("SELECT * FROM reports WHERE status IN ('draft','published') ORDER BY created_at DESC LIMIT 50").fetchall()
        return render_template("admin.html", reports=reports)

    @app.get("/champion-photo/<int:report_id>")
    def champion_photo(report_id):
        with connect(app.config["DATABASE"]) as db:
            report = db.execute(
                "SELECT status, champion_photo, champion_photo_mime FROM reports WHERE id=?", (report_id,)
            ).fetchone()
        if not report or (report["status"] != "published" and request.current_role != "admin") or not report["champion_photo"]:
            abort(404)
        return send_file(io.BytesIO(report["champion_photo"]), mimetype=report["champion_photo_mime"], max_age=3600)

    @app.get("/admin/review/<int:report_id>")
    @admin_required
    def review(report_id):
        with connect(app.config["DATABASE"]) as db:
            report = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            if not report:
                abort(404)
            rows = db.execute("SELECT * FROM aggregates WHERE report_id=? ORDER BY month, location", (report_id,)).fetchall()
        return render_template("review.html", report=report, rows=rows, stats=json.loads(report["stats_json"]))

    @app.post("/admin/publish/<int:report_id>")
    @admin_required
    def publish(report_id):
        validate_csrf()
        now = utc_now()
        with connect(app.config["DATABASE"]) as db:
            report = db.execute("SELECT status FROM reports WHERE id=?", (report_id,)).fetchone()
            if not report:
                abort(404)
            previous = db.execute("SELECT id FROM reports WHERE status='published' ORDER BY published_at DESC LIMIT 1").fetchone()
            if previous and previous["id"] != report_id:
                db.execute(
                    """INSERT INTO aggregates(report_id, month, location, total, compliant, above_maximum)
                       SELECT ?, month, location, total, compliant, above_maximum
                       FROM aggregates
                       WHERE report_id=? AND month NOT IN (SELECT month FROM aggregates WHERE report_id=?)""",
                    (report_id, previous["id"], report_id),
                )
            db.execute("UPDATE reports SET status='archived' WHERE status='published'")
            db.execute("UPDATE reports SET status='published', published_at=?, published_by=? WHERE id=?", (now, request.current_user, report_id))
            db.commit()
        audit(app.config["DATABASE"], request.current_user, "report_published", report_id)
        flash("Dashboard published successfully.", "success")
        return redirect(url_for("dashboard"))

    return app


def connect(path: str):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_database(path: str):
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
          stats_json TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL,
          published_at TEXT, published_by TEXT
        );
        CREATE TABLE IF NOT EXISTS aggregates (
          id INTEGER PRIMARY KEY AUTOINCREMENT, report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
          month TEXT NOT NULL, location TEXT NOT NULL, total INTEGER NOT NULL,
          compliant INTEGER NOT NULL, above_maximum INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_at TEXT NOT NULL, username TEXT NOT NULL,
          action TEXT NOT NULL, report_id INTEGER
        );
        """)
        report_columns = {row[1] for row in db.execute("PRAGMA table_info(reports)")}
        for column, definition in {
            "champion_name": "TEXT",
            "champion_month": "TEXT",
            "champion_photo": "BLOB",
            "champion_photo_mime": "TEXT",
        }.items():
            if column not in report_columns:
                db.execute(f"ALTER TABLE reports ADD COLUMN {column} {definition}")
        db.commit()


def save_draft(
    path: str, title: str, user: str, stats: dict, aggregates: pd.DataFrame,
    champion_name: str = "", champion_month: str = "", champion_photo: bytes | None = None,
    champion_photo_mime: str | None = None,
) -> int:
    with connect(path) as db:
        cursor = db.execute(
            """INSERT INTO reports(
                title, stats_json, created_at, created_by, champion_name, champion_month,
                champion_photo, champion_photo_mime
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (title, json.dumps(stats), utc_now(), user, champion_name, champion_month, champion_photo, champion_photo_mime),
        )
        report_id = cursor.lastrowid
        db.executemany(
            "INSERT INTO aggregates(report_id, month, location, total, compliant, above_maximum) VALUES(?,?,?,?,?,?)",
            [(report_id, str(row.month), str(row.location), int(row.total), int(row.compliant), int(row.above_maximum)) for row in aggregates.itertuples(index=False)],
        )
        db.commit()
    return report_id


def audit(path: str, user: str, action: str, report_id: int | None):
    with connect(path) as db:
        db.execute("INSERT INTO audit_log(event_at, username, action, report_id) VALUES(?,?,?,?)", (utc_now(), user, action, report_id))
        db.commit()


def validate_champion_photo(file_storage) -> tuple[bytes | None, str | None]:
    if not file_storage or not file_storage.filename:
        return None, None
    data = file_storage.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise ReportValidationError("Champion photograph must be 5 MB or smaller.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    raise ReportValidationError("Champion photograph must be a PNG or JPEG image.")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8790, debug=True)
