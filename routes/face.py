import base64
import os
import uuid

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    session,
    redirect,
)

from ai.face_detection import detect_face_emotion
from ai.ai_response import generate_ai_response
from database.db import get_db_connection


face = Blueprint("face", __name__)

UPLOAD_FOLDER = "static/uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@face.route("/face_detection")
def face_detection():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("face_detection.html")


@face.route("/analyze_live_face", methods=["POST"])
def analyze_live_face():
    if "user_id" not in session:
        return jsonify({
            "error": "Please login first."
        }), 401

    data = request.get_json(silent=True)

    if not data or "image" not in data:
        return jsonify({
            "error": "No camera frame received."
        }), 400

    image_data = data["image"]

    image_path = None

    try:
        _, encoded = image_data.split(",", 1)

        image_bytes = base64.b64decode(encoded)

        filename = f"live_{uuid.uuid4().hex}.jpg"

        image_path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        emotion = detect_face_emotion(image_path)

        if emotion == "Unknown":
            return jsonify({
                "error":
                    "Face could not be detected clearly. Please try again."
            }), 422

        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO mood_records
            (user_id, input_type, emotion, confidence, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                "Face",
                emotion,
                0,
                "Live camera face emotion analysis"
            )
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "emotion": emotion
        })

    except ValueError:
        return jsonify({
            "error": "Invalid camera image received."
        }), 400

    except Exception as error:
        print("Live Face Analysis Error:", error)

        return jsonify({
            "error":
                "Unable to analyze face. Please try again."
        }), 500

    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)


@face.route("/face_support_chat", methods=["POST"])
def face_support_chat():
    if "user_id" not in session:
        return jsonify({
            "error": "Please login first."
        }), 401

    data = request.get_json(silent=True) or {}

    user_message = data.get(
        "message",
        ""
    ).strip()

    emotion = data.get(
        "emotion",
        "Unknown"
    )

    if not user_message:
        return jsonify({
            "error": "Please enter a message."
        }), 400

    reply = generate_ai_response(
        user_message,
        emotion
    )

    return jsonify({
        "reply": reply
    })