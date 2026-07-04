from deepface import DeepFace


def detect_face_emotion(image_path):

    try:

        result = DeepFace.analyze(
            img_path=image_path,
            actions=["emotion"],
            enforce_detection=False
        )


        emotion = result[0]["dominant_emotion"]

        return emotion


    except Exception as e:

        print("Face Emotion Error:", e)

        return "Unknown"