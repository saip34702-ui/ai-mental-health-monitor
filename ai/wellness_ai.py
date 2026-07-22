from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List


POSITIVE_EMOTIONS = {
    "happy",
    "neutral",
    "surprise",
}

DIFFICULT_EMOTIONS = {
    "sad",
    "angry",
    "fear",
    "disgust",
}

EMOTION_SCORES = {
    "happy": 100,
    "surprise": 80,
    "neutral": 70,
    "fear": 40,
    "sad": 30,
    "angry": 25,
    "disgust": 20,
}


def normalize_emotion_stats(
    emotion_stats: Iterable[Any]
) -> Dict[str, int]:
    """
    Convert database emotion rows into a clean dictionary.
    """

    counts: Dict[str, int] = {}

    for row in emotion_stats:
        emotion = row["emotion"]
        total = row["total"]

        if not emotion:
            continue

        emotion_name = str(emotion).strip().lower()
        emotion_total = int(total or 0)

        counts[emotion_name] = emotion_total

    return counts


def calculate_wellness_score(
    emotion_stats: Iterable[Any]
) -> int:
    """
    Calculate a weighted wellness score from 0 to 100.
    """

    emotion_counts = normalize_emotion_stats(
        emotion_stats
    )

    total_records = sum(
        emotion_counts.values()
    )

    if total_records == 0:
        return 0

    weighted_total = sum(
        EMOTION_SCORES.get(emotion, 50) * count
        for emotion, count in emotion_counts.items()
    )

    return round(
        weighted_total / total_records
    )


def get_dominant_emotion(
    emotion_stats: Iterable[Any]
) -> Dict[str, Any]:
    """
    Return the most frequent emotion and its percentage.
    """

    emotion_counts = normalize_emotion_stats(
        emotion_stats
    )

    total_records = sum(
        emotion_counts.values()
    )

    if total_records == 0:
        return {
            "emotion": "unknown",
            "count": 0,
            "percentage": 0,
        }

    emotion = max(
        emotion_counts,
        key=emotion_counts.get
    )

    count = emotion_counts[emotion]

    percentage = round(
        (count / total_records) * 100
    )

    return {
        "emotion": emotion,
        "count": count,
        "percentage": percentage,
    }


def get_emotion_recommendation(
    emotion: str
) -> Dict[str, str]:
    """
    Return a supportive recommendation based on emotion.
    """

    emotion_name = (
        emotion or "unknown"
    ).strip().lower()

    recommendations = {
        "happy": {
            "title": "Keep supporting this positive pattern",
            "message": (
                "Notice what helped you feel good today and try "
                "to include more of those healthy habits in your routine."
            ),
        },

        "neutral": {
            "title": "Use this calm moment for a check-in",
            "message": (
                "Take a few minutes to notice your thoughts, energy, "
                "sleep, and stress level without judging yourself."
            ),
        },

        "surprise": {
            "title": "Give yourself time to process",
            "message": (
                "Unexpected events can affect your emotions. Pause, "
                "breathe slowly, and reflect on what changed."
            ),
        },

        "sad": {
            "title": "Be gentle with yourself",
            "message": (
                "Consider writing down what is affecting you or talking "
                "with someone you trust. You do not have to handle "
                "everything alone."
            ),
        },

        "angry": {
            "title": "Create a little space before reacting",
            "message": (
                "Step away briefly, breathe slowly, and return to the "
                "situation when you feel more settled."
            ),
        },

        "fear": {
            "title": "Focus on one manageable step",
            "message": (
                "Write down what is worrying you and separate what you "
                "can control from what you cannot control."
            ),
        },

        "disgust": {
            "title": "Notice what is making you uncomfortable",
            "message": (
                "Try to identify the situation, thought, or experience "
                "behind this feeling and give yourself time to process it."
            ),
        },

        "unknown": {
            "title": "Continue checking in with yourself",
            "message": (
                "Regular emotional check-ins can help you understand "
                "your patterns over time."
            ),
        },
    }

    return recommendations.get(
        emotion_name,
        recommendations["unknown"]
    )


def build_emotion_distribution(
    emotion_stats: Iterable[Any]
) -> List[Dict[str, Any]]:
    """
    Prepare emotion distribution data for charts.
    """

    emotion_counts = normalize_emotion_stats(
        emotion_stats
    )

    total_records = sum(
        emotion_counts.values()
    )

    if total_records == 0:
        return []

    distribution: List[Dict[str, Any]] = []

    for emotion, count in sorted(
        emotion_counts.items(),
        key=lambda item: item[1],
        reverse=True
    ):
        percentage = round(
            (count / total_records) * 100
        )

        distribution.append(
            {
                "emotion": emotion,
                "count": count,
                "percentage": percentage,
            }
        )

    return distribution


def _parse_record_date(
    created_at: Any
) -> datetime | None:
    """
    Convert a database timestamp into a datetime object.
    """

    if created_at is None:
        return None

    if isinstance(created_at, datetime):
        return created_at

    date_text = str(created_at).strip()

    supported_formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    )

    for date_format in supported_formats:
        try:
            return datetime.strptime(
                date_text,
                date_format
            )
        except ValueError:
            continue

    return None


def build_weekly_trend(
    mood_records: Iterable[Any]
) -> Dict[str, List[Any]]:
    """
    Build chart-ready wellness scores for the latest seven days.

    Each day's score is the average weighted score of all
    mood records created on that date.
    """

    records = list(mood_records)

    today = datetime.now().date()

    labels: List[str] = []
    scores: List[int] = []
    record_counts: List[int] = []

    for day_offset in range(6, -1, -1):
        current_date = (
            today - timedelta(days=day_offset)
        )

        labels.append(
            current_date.strftime("%a")
        )

        daily_scores: List[int] = []

        for record in records:
            record_date = _parse_record_date(
                record["created_at"]
            )

            if (
                record_date is None
                or record_date.date() != current_date
            ):
                continue

            emotion = str(
                record["emotion"] or ""
            ).strip().lower()

            daily_scores.append(
                EMOTION_SCORES.get(
                    emotion,
                    50
                )
            )

        record_counts.append(
            len(daily_scores)
        )

        if daily_scores:
            scores.append(
                round(
                    sum(daily_scores)
                    / len(daily_scores)
                )
            )
        else:
            scores.append(0)

    return {
        "labels": labels,
        "scores": scores,
        "record_counts": record_counts,
    }


def build_analytics_summary(
    emotion_stats: Iterable[Any],
    mood_records: Iterable[Any] | None = None
) -> Dict[str, Any]:
    """
    Build the complete analytics summary for the Reports page.
    """

    wellness_score = calculate_wellness_score(
        emotion_stats
    )

    dominant = get_dominant_emotion(
        emotion_stats
    )

    recommendation = get_emotion_recommendation(
        dominant["emotion"]
    )

    distribution = build_emotion_distribution(
        emotion_stats
    )

    weekly_trend = build_weekly_trend(
        mood_records or []
    )

    return {
        "wellness_score": wellness_score,
        "dominant_emotion": dominant["emotion"],
        "dominant_count": dominant["count"],
        "dominant_percentage": dominant["percentage"],
        "recommendation_title": recommendation["title"],
        "recommendation_message": recommendation["message"],
        "emotion_distribution": distribution,
        "weekly_trend": weekly_trend,
    }