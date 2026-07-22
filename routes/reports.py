from datetime import datetime, timedelta

from flask import Blueprint, redirect, render_template, request, session

from database.db import get_db_connection

from ai.wellness_ai import build_analytics_summary


reports = Blueprint("reports", __name__)


def build_wellness_insight(total, emotion_stats, filter_type):
    """Create a supportive insight from the filtered mood records."""

    period_names = {
        "all": "your recorded wellness history",
        "today": "today",
        "7days": "the last 7 days",
        "30days": "the last 30 days",
    }

    period_name = period_names.get(
        filter_type,
        "the selected period"
    )

    if total == 0:
        return {
            "title": "Start your wellness journey",
            "message": (
                f"No emotional check-ins were found for {period_name}. "
                "Try a Face, Text, or Voice analysis to begin tracking "
                "your emotional patterns."
            ),
            "status": "No data",
        }

    emotion_counts = {
        str(row["emotion"]).lower(): row["total"]
        for row in emotion_stats
        if row["emotion"]
    }

    dominant_emotion = max(
        emotion_counts,
        key=emotion_counts.get
    )

    dominant_count = emotion_counts[dominant_emotion]

    dominant_percentage = round(
        (dominant_count / total) * 100
    )

    positive_emotions = {
        "happy",
        "neutral",
        "surprise",
    }

    difficult_emotions = {
        "sad",
        "angry",
        "fear",
        "disgust",
    }

    positive_count = sum(
        emotion_counts.get(emotion, 0)
        for emotion in positive_emotions
    )

    difficult_count = sum(
        emotion_counts.get(emotion, 0)
        for emotion in difficult_emotions
    )

    if difficult_count > positive_count:
        title = "Take a gentle moment for yourself"

        message = (
            f"Across {period_name}, your most common recorded emotion was "
            f"{dominant_emotion}, appearing in {dominant_percentage}% of "
            "your check-ins. Consider taking a short break, writing down "
            "what is affecting you, or speaking with someone you trust."
        )

        status = "Needs attention"

    elif positive_count > difficult_count:
        title = "Your recent pattern looks encouraging"

        message = (
            f"Across {period_name}, your most common recorded emotion was "
            f"{dominant_emotion}, appearing in {dominant_percentage}% of "
            "your check-ins. Your recent records show a generally stable "
            "or positive pattern. Continue with the habits that support you."
        )

        status = "Positive trend"

    else:
        title = "Your emotional pattern looks balanced"

        message = (
            f"Across {period_name}, your most common recorded emotion was "
            f"{dominant_emotion}, appearing in {dominant_percentage}% of "
            "your check-ins. Your records show a mixed emotional pattern, "
            "so regular check-ins may help you understand what influences "
            "your mood."
        )

        status = "Balanced"

    return {
        "title": title,
        "message": message,
        "status": status,
    }


@reports.route("/reports")
def reports_page():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    filter_type = request.args.get(
        "filter",
        "all"
    )

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
        start_date = now.strftime(
            "%Y-%m-%d 00:00:00"
        )

    elif filter_type == "7days":
        start_date = (
            now - timedelta(days=6)
        ).strftime(
            "%Y-%m-%d 00:00:00"
        )

    elif filter_type == "30days":
        start_date = (
            now - timedelta(days=29)
        ).strftime(
            "%Y-%m-%d 00:00:00"
        )

    conn = get_db_connection()

    try:
        date_condition = ""
        query_parameters = [user_id]

        if start_date:
            date_condition = "AND created_at >= ?"
            query_parameters.append(start_date)

        parameters = tuple(query_parameters)

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
            parameters
        ).fetchall()

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
            parameters
        ).fetchone()

        total = summary["total"] or 0
        face = summary["face"] or 0
        text = summary["text"] or 0
        voice = summary["voice"] or 0

        emotion_stats = conn.execute(
            f"""
            SELECT
                emotion,
                COUNT(*) AS total
            FROM mood_records
            WHERE user_id = ?
            {date_condition}
            GROUP BY emotion
            ORDER BY total DESC
            """,
            parameters
        ).fetchall()

        wellness_insight = build_wellness_insight(
            total=total,
            emotion_stats=emotion_stats,
            filter_type=filter_type
        )

        analytics = build_analytics_summary(
            emotion_stats,
            records
        )

    finally:
        conn.close()

    return render_template(
        "reports.html",
        name=session.get(
            "user_name",
            "User"
        ),
        records=records,
        total=total,
        face=face,
        text=text,
        voice=voice,
        filter_type=filter_type,
        emotion_stats=emotion_stats,
        wellness_insight=wellness_insight,
        analytics=analytics
    )