from flask import Blueprint, render_template, request, session
from ai.face_detection import detect_face_emotion
from database.db import get_db_connection
import os
from werkzeug.utils import secure_filename


face = Blueprint("face", __name__)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@face.route("/face_detection", methods=["GET", "POST"])
def face_detection():

    emotion = None

    if request.method == "POST":

        if "image" not in request.files:
            return "No image found"

        image = request.files["image"]

        if image.filename == "":
            return "No file selected"

        filename = secure_filename(image.filename)

        image_path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        image.save(image_path)

        emotion = detect_face_emotion(image_path)

        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO mood_records
            (user_id, input_tpe, emotion, confidence, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                "face",
                emotion,
                0,
                "Face emotion analysis"
            )
        )

        conn.commit()
        conn.close()


    return render_template(
        "face_detection.html",
        emotion=emotion
    )