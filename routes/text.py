from flask import Blueprint, render_template, request, redirect, session
from ai.text_analysis import analyze_text_mood
from database.db import get_db_connection
from ai.ai_response import generate_ai_response

text = Blueprint("text", __name__)

@text.route("/text_analysis", methods=["GET", "POST"])
def text_analysis():
    if "user_id" not in session:
        return redirect("/login")
    
    emotion = None
    confidence = None
    user_text = ""
    ai_reply = None

    if request.method == "POST":
        user_text = request.form["user_text"]

        emotion, confidence = analyze_text_mood(user_text)
        ai_reply = generate_ai_response(user_text, emotion)

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO mood_records
            (user_id, input_type, emotion, confidence, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                "Text",
                emotion,
                confidence,
                user_text
            )
        )

        conn.commit()
        conn.close()

    return render_template(
        "text_analysis.html",
        emotion=emotion,
        confidence=confidence,
        user_text=user_text,
        ai_reply=ai_reply
    )