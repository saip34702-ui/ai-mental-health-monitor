from flask import Blueprint, render_template, request, session, redirect
import speech_recognition as sr

from ai.text_analysis import analyze_text_mood
from ai.ai_response import generate_ai_response
from database.db import get_db_connection


voice = Blueprint("voice", __name__)


@voice.route("/voice_analysis", methods=["GET", "POST"])
def voice_analysis():
    if "user_id" not in session:
        return redirect("/login")

    converted_text = ""
    emotion = None
    confidence = None
    ai_reply = None
    message = ""

    if request.method == "POST":
        recognizer = sr.Recognizer()

        try:
            message = "Listening..."

            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source)

                audio = recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=10
                )

            converted_text = recognizer.recognize_google(audio)

            emotion, confidence = analyze_text_mood(converted_text)

            ai_reply = generate_ai_response(converted_text, emotion)

            conn = get_db_connection()
            conn.execute(
                """
                INSERT INTO mood_records
                (user_id, input_type, emotion, confidence, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    "Voice",
                    emotion,
                    confidence,
                    converted_text
                )
            )
            conn.commit()
            conn.close()

            message = "Voice analysis completed successfully."

        except Exception:
            message = "Voice not detected. Please try again."

    return render_template(
        "voice_analysis.html",
        message=message,
        text=converted_text,
        emotion=emotion,
        confidence=confidence,
        ai_reply=ai_reply
    )