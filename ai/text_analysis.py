from textblob import TextBlob


def analyze_text_mood(text):

    analysis = TextBlob(text)

    polarity = analysis.sentiment.polarity


    if polarity > 0.3:

        emotion = "Happy"

    elif polarity < -0.3:

        emotion = "Sad"

    elif polarity < -0.05:

        emotion = "Stressed"

    else:

        emotion = "Neutral"


    confidence = round(
        abs(polarity) * 100,
        2
    )


    return emotion, confidence