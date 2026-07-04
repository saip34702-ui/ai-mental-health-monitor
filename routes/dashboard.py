from flask import Blueprint, render_template, redirect, session
from database.db import get_db_connection

dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect("/login")
    
    conn = get_db_connection()

    mood = conn.execute(
        """
        SELECT emotion
        FROM mood_records
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    count = conn.exexute(
        """
        SELECT COUNT(*) as count
        FROM mood_records
        WHERE user_id = ?
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    conn.close()

    if mood:
        today_mood = mood["emotion"]

    else:
        today_mood = "Neutral"

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        mood=today_mood,
        total_records=count
    )


    return render_template("dashboard.html", name=session["user_name"])