from datetime import datetime, timedelta

from flask import Blueprint, redirect, render_template, session

from database.db import get_db_connection


dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db_connection()

    # Latest mood
    latest_mood = conn.execute(
        """
        SELECT emotion, input_type, created_at
        FROM mood_records
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()

    today_mood = (
        latest_mood["emotion"]
        if latest_mood
        else "Neutral"
    )

    # Total analysis count
    total_records = conn.execute(
        """
        SELECT COUNT(*)
        FROM mood_records
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()[0]

    # Recent activity
    recent_records = conn.execute(
        """
        SELECT
            emotion,
            input_type,
            confidence,
            note,
            created_at
        FROM mood_records
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    # Last 7 days records
    seven_days_ago = (
        datetime.now() - timedelta(days=6)
    ).strftime("%Y-%m-%d 00:00:00")

    weekly_records = conn.execute(
        """
        SELECT emotion, created_at
        FROM mood_records
        WHERE user_id = ?
        AND created_at >= ?
        ORDER BY created_at ASC
        """,
        (user_id, seven_days_ago)
    ).fetchall()

    # Distinct activity dates for streak calculation
    streak_rows = conn.execute(
        """
        SELECT DISTINCT DATE(created_at) AS activity_date
        FROM mood_records
        WHERE user_id = ?
        ORDER BY activity_date DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    # Wellness score
    positive_moods = {
        "happy",
        "surprise",
        "neutral"
    }

    if recent_records:
        positive_count = sum(
            1
            for record in recent_records
            if record["emotion"].lower()
            in positive_moods
        )

        wellness_score = round(
            (
                positive_count
                / len(recent_records)
            ) * 100
        )
    else:
        wellness_score = 0

    # Weekly chart data
    mood_scores = {
        "happy": 90,
        "surprise": 80,
        "neutral": 65,
        "fear": 40,
        "sad": 30,
        "angry": 25,
        "disgust": 20
    }

    day_labels = []
    day_scores = []

    for day_offset in range(6, -1, -1):
        current_day = (
            datetime.now()
            - timedelta(days=day_offset)
        )

        current_date = current_day.strftime(
            "%Y-%m-%d"
        )

        day_labels.append(
            current_day.strftime("%a")
        )

        matching_scores = [
            mood_scores.get(
                record["emotion"].lower(),
                50
            )
            for record in weekly_records
            if str(record["created_at"]).startswith(
                current_date
            )
        ]

        if matching_scores:
            average_score = round(
                sum(matching_scores)
                / len(matching_scores)
            )
        else:
            average_score = 0

        day_scores.append(average_score)

    # Current streak calculation
    activity_dates = {
        datetime.strptime(
            row["activity_date"],
            "%Y-%m-%d"
        ).date()
        for row in streak_rows
        if row["activity_date"]
    }

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    if today in activity_dates:
        streak_cursor = today
    elif yesterday in activity_dates:
        streak_cursor = yesterday
    else:
        streak_cursor = None

    current_streak = 0

    while (
        streak_cursor
        and streak_cursor in activity_dates
    ):
        current_streak += 1
        streak_cursor -= timedelta(days=1)

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        mood=today_mood,
        total_records=total_records,
        wellness_score=wellness_score,
        recent_records=recent_records,
        day_labels=day_labels,
        day_scores=day_scores,
        current_streak=current_streak
    )