from flask import Blueprint, jsonify, redirect, render_template, request, session

from ai.ai_response import generate_ai_response
from database.db import get_db_connection


chatbot = Blueprint("chatbot", __name__)


def get_recent_mood_context(user_id, limit=5):
    """Fetch the user's latest mood records for AI context."""

    conn = get_db_connection()

    try:
        records = conn.execute(
            """
            SELECT emotion, input_type, created_at
            FROM mood_records
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit)
        ).fetchall()

    finally:
        conn.close()

    if not records:
        return "No previous mood records are available."

    context_items = []

    for record in records:
        emotion = record["emotion"] or "Unknown"
        input_type = record["input_type"] or "Unknown"
        created_at = record["created_at"] or "Unknown time"

        context_items.append(
            f"{emotion} detected through {input_type} on {created_at}"
        )

    return "; ".join(context_items)


@chatbot.route("/chatbot")
def chatbot_page():
    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "chatbot.html",
        name=session.get("user_name", "User")
    )


@chatbot.route("/chatbot/message", methods=["POST"])
def chatbot_message():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please login first."
        }), 401

    data = request.get_json(silent=True) or {}

    user_message = str(
        data.get("message", "")
    ).strip()

    if not user_message:
        return jsonify({
            "success": False,
            "error": "Please enter a message."
        }), 400

    if len(user_message) > 1500:
        return jsonify({
            "success": False,
            "error": "Message is too long. Please keep it under 1500 characters."
        }), 400

    user_id = session["user_id"]

    mood_context = get_recent_mood_context(
        user_id=user_id,
        limit=5
    )

    latest_emotion = "Unknown"

    conn = get_db_connection()

    try:
        latest_record = conn.execute(
            """
            SELECT emotion
            FROM mood_records
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        if latest_record and latest_record["emotion"]:
            latest_emotion = latest_record["emotion"]

    finally:
        conn.close()

    contextual_message = f"""
User name: {session.get("user_name", "User")}

Recent mood history:
{mood_context}

Current user message:
{user_message}

Use the recent mood history only as supporting context.
Do not assume that older emotions describe the user's current condition.
Respond naturally, briefly, safely, and supportively.
"""

    ai_reply = generate_ai_response(
        contextual_message,
        latest_emotion
    )

    return jsonify({
        "success": True,
        "reply": ai_reply,
        "emotion": latest_emotion
    })