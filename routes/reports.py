from datetime import datetime, timedelta

from flask import Blueprint, redirect, render_template, request, session

from database.db import get_db_connection


reports = Blueprint("reports", __name__)


@reports.route("/reports")
def reports_page():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    # Read the selected date filter from the URL.
    filter_type = request.args.get("filter", "all")

    allowed_filters = {
        "all",
        "today",
        "7days",
        "30days",
    }

    if filter_type not in allowed_filters:
        filter_type = "all"

    now = datetime.now()
    start_date = None

    if filter_type == "today":
        start_date = now.strftime("%Y-%m-%d 00:00:00")

    elif filter_type == "7days":
        start_date = (
            now - timedelta(days=6)
        ).strftime("%Y-%m-%d 00:00:00")

    elif filter_type == "30days":
        start_date = (
            now - timedelta(days=29)
        ).strftime("%Y-%m-%d 00:00:00")

    conn = get_db_connection()

    try:
        # Build one reusable date condition.
        date_condition = ""
        query_parameters = [user_id]

        if start_date:
            date_condition = "AND created_at >= ?"
            query_parameters.append(start_date)

        # Get filtered mood records.
        records = conn.execute(
            f"""
            SELECT
                emotion,
                input_type,
                confidence,
                note,
                created_at
            FROM mood_records
            WHERE user_id = ?
            {date_condition}
            ORDER BY created_at DESC
            """,
            tuple(query_parameters)
        ).fetchall()

        # Get all filtered summary counts in one query.
        summary = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN input_type = 'Face'
                        THEN 1
                        ELSE 0
                    END
                ) AS face,
                SUM(
                    CASE
                        WHEN input_type = 'Text'
                        THEN 1
                        ELSE 0
                    END
                ) AS text,
                SUM(
                    CASE
                        WHEN input_type = 'Voice'
                        THEN 1
                        ELSE 0
                    END
                ) AS voice
            FROM mood_records
            WHERE user_id = ?
            {date_condition}
            """,
            tuple(query_parameters)
        ).fetchone()

        total = summary["total"] or 0
        face = summary["face"] or 0
        text = summary["text"] or 0
        voice = summary["voice"] or 0

    finally:
        conn.close()

    return render_template(
        "reports.html",
        name=session.get("user_name", "User"),
        records=records,
        total=total,
        face=face,
        text=text,
        voice=voice,
        filter_type=filter_type
    )