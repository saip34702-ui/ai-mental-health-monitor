from datetime import datetime, timedelta
from io import BytesIO

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    send_file,
    session,
)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ai.wellness_ai import build_analytics_summary
from database.db import get_db_connection


reports = Blueprint("reports", __name__)


ALLOWED_FILTERS = {
    "all",
    "today",
    "7days",
    "30days",
}


def get_filter_details(filter_type):
    """Validate the report filter and calculate its starting date."""

    if filter_type not in ALLOWED_FILTERS:
        filter_type = "all"

    now = datetime.now()
    start_date = None

    if filter_type == "today":
        start_date = now.strftime("%Y-%m-%d 00:00:00")

    elif filter_type == "7days":
        start_date = (
            now - timedelta(days=6)
        ).strftime("%Y-%m-%d 00:00:00")

    elif filter_type == "30days":
        start_date = (
            now - timedelta(days=29)
        ).strftime("%Y-%m-%d 00:00:00")

    return filter_type, start_date


def get_filter_label(filter_type):
    """Return a readable name for the selected report period."""

    labels = {
        "all": "All Recorded History",
        "today": "Today",
        "7days": "Last 7 Days",
        "30days": "Last 30 Days",
    }

    return labels.get(
        filter_type,
        "All Recorded History"
    )


def fetch_report_data(user_id, start_date=None):
    """Fetch mood records and summary information for one user."""

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
                        WHEN LOWER(input_type) = 'face'
                        THEN 1
                        ELSE 0
                    END
                ) AS face,

                SUM(
                    CASE
                        WHEN LOWER(input_type) = 'text'
                        THEN 1
                        ELSE 0
                    END
                ) AS text,

                SUM(
                    CASE
                        WHEN LOWER(input_type) = 'voice'
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

        user = conn.execute(
            """
            SELECT name, email
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

    finally:
        conn.close()

    total = summary["total"] or 0
    face = summary["face"] or 0
    text = summary["text"] or 0
    voice = summary["voice"] or 0

    return {
        "records": records,
        "emotion_stats": emotion_stats,
        "total": total,
        "face": face,
        "text": text,
        "voice": voice,
        "user": user,
    }


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

    if not emotion_counts:
        return {
            "title": "No emotion information available",
            "message": (
                "Mood records were found, but their emotion information "
                "is currently unavailable."
            ),
            "status": "No data",
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
        "calm",
    }

    difficult_emotions = {
        "sad",
        "angry",
        "fear",
        "disgust",
        "stressed",
        "anxious",
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
            "or positive pattern. Continue with habits that support you."
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


def format_confidence(confidence):
    """Convert confidence into a readable value."""

    if confidence is None:
        return "Not available"

    try:
        confidence_value = float(confidence)

        if 0 <= confidence_value <= 1:
            return f"{confidence_value * 100:.1f}%"

        return f"{confidence_value:.1f}%"

    except (TypeError, ValueError):
        return str(confidence)


def add_pdf_page_number(canvas, document):
    """Add footer and page number to every PDF page."""

    canvas.saveState()

    page_width, _ = A4

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#667085"))

    canvas.drawString(
        20 * mm,
        12 * mm,
        "MindAI - AI Mental Health Monitor"
    )

    canvas.drawRightString(
        page_width - 20 * mm,
        12 * mm,
        f"Page {document.page}"
    )

    canvas.restoreState()


@reports.route("/reports")
def reports_page():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    filter_type, start_date = get_filter_details(
        request.args.get("filter", "all")
    )

    report_data = fetch_report_data(
        user_id=user_id,
        start_date=start_date
    )

    records = report_data["records"]
    emotion_stats = report_data["emotion_stats"]
    total = report_data["total"]
    face = report_data["face"]
    text = report_data["text"]
    voice = report_data["voice"]

    wellness_insight = build_wellness_insight(
        total=total,
        emotion_stats=emotion_stats,
        filter_type=filter_type
    )

    analytics = build_analytics_summary(
        emotion_stats,
        records
    )

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


@reports.route("/reports/download")
def download_report():
    """Generate and download the logged-in user's wellness PDF report."""

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    filter_type, start_date = get_filter_details(
        request.args.get("filter", "all")
    )

    report_data = fetch_report_data(
        user_id=user_id,
        start_date=start_date
    )

    records = report_data["records"]
    emotion_stats = report_data["emotion_stats"]
    total = report_data["total"]
    face = report_data["face"]
    text = report_data["text"]
    voice = report_data["voice"]
    user = report_data["user"]

    user_name = (
        user["name"]
        if user and user["name"]
        else session.get("user_name", "User")
    )

    user_email = (
        user["email"]
        if user and user["email"]
        else session.get("email", "Not available")
    )

    wellness_insight = build_wellness_insight(
        total=total,
        emotion_stats=emotion_stats,
        filter_type=filter_type
    )

    dominant_emotion = "No data"
    dominant_count = 0

    if emotion_stats:
        first_emotion = emotion_stats[0]

        dominant_emotion = (
            first_emotion["emotion"]
            if first_emotion["emotion"]
            else "Unknown"
        )

        dominant_count = first_emotion["total"] or 0

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="MindAI Wellness Report",
        author="MindAI",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MindAITitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=27,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#3448C5"),
        spaceAfter=5 * mm,
    )

    subtitle_style = ParagraphStyle(
        "MindAISubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#667085"),
        spaceAfter=8 * mm,
    )

    section_style = ParagraphStyle(
        "MindAISection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#263238"),
        spaceBefore=5 * mm,
        spaceAfter=3 * mm,
    )

    normal_style = ParagraphStyle(
        "MindAINormal",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#344054"),
    )

    small_style = ParagraphStyle(
        "MindAISmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475467"),
    )

    story = []

    story.append(
        Paragraph(
            "MindAI Wellness Report",
            title_style
        )
    )

    story.append(
        Paragraph(
            "Personal Emotional Wellness Analysis",
            subtitle_style
        )
    )

    user_information = [
        [
            Paragraph("<b>User Name</b>", normal_style),
            Paragraph(str(user_name), normal_style),
        ],
        [
            Paragraph("<b>Email</b>", normal_style),
            Paragraph(str(user_email), normal_style),
        ],
        [
            Paragraph("<b>Report Period</b>", normal_style),
            Paragraph(
                get_filter_label(filter_type),
                normal_style
            ),
        ],
        [
            Paragraph("<b>Generated On</b>", normal_style),
            Paragraph(
                datetime.now().strftime(
                    "%d %B %Y, %I:%M %p"
                ),
                normal_style
            ),
        ],
    ]

    user_table = Table(
        user_information,
        colWidths=[
            45 * mm,
            115 * mm,
        ]
    )

    user_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EEF2FF"),
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, -1),
                colors.HexColor("#344054"),
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D0D5DD"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
        ])
    )

    story.append(user_table)
    story.append(Spacer(1, 6 * mm))

    story.append(
        Paragraph(
            "Analysis Summary",
            section_style
        )
    )

    summary_data = [
        [
            Paragraph("<b>Total Check-ins</b>", small_style),
            Paragraph("<b>Face Analysis</b>", small_style),
            Paragraph("<b>Text Analysis</b>", small_style),
            Paragraph("<b>Voice Analysis</b>", small_style),
        ],
        [
            Paragraph(str(total), normal_style),
            Paragraph(str(face), normal_style),
            Paragraph(str(text), normal_style),
            Paragraph(str(voice), normal_style),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            40 * mm,
            40 * mm,
            40 * mm,
            40 * mm,
        ]
    )

    summary_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#3448C5"),
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white,
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                colors.HexColor("#F8FAFC"),
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER",
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D0D5DD"),
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
        ])
    )

    story.append(summary_table)
    story.append(Spacer(1, 5 * mm))

    story.append(
        Paragraph(
            "Overall Wellness Insight",
            section_style
        )
    )

    insight_data = [
        [
            Paragraph("<b>Status</b>", normal_style),
            Paragraph(
                wellness_insight["status"],
                normal_style
            ),
        ],
        [
            Paragraph("<b>Insight</b>", normal_style),
            Paragraph(
                wellness_insight["title"],
                normal_style
            ),
        ],
        [
            Paragraph(
                "<b>Recommendation</b>",
                normal_style
            ),
            Paragraph(
                wellness_insight["message"],
                normal_style
            ),
        ],
    ]

    insight_table = Table(
        insight_data,
        colWidths=[
            42 * mm,
            118 * mm,
        ]
    )

    insight_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#ECFDF3"),
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#D0D5DD"),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
        ])
    )

    story.append(insight_table)

    story.append(
        Paragraph(
            "Emotion Distribution",
            section_style
        )
    )

    if emotion_stats:
        emotion_table_data = [
            [
                Paragraph("<b>Emotion</b>", small_style),
                Paragraph("<b>Check-ins</b>", small_style),
                Paragraph("<b>Percentage</b>", small_style),
            ]
        ]

        for row in emotion_stats:
            emotion = row["emotion"] or "Unknown"
            count = row["total"] or 0

            percentage = (
                round((count / total) * 100, 1)
                if total
                else 0
            )

            emotion_table_data.append([
                Paragraph(
                    str(emotion).title(),
                    normal_style
                ),
                Paragraph(
                    str(count),
                    normal_style
                ),
                Paragraph(
                    f"{percentage}%",
                    normal_style
                ),
            ])

        emotion_table = Table(
            emotion_table_data,
            colWidths=[
                70 * mm,
                45 * mm,
                45 * mm,
            ],
            repeatRows=1
        )

        emotion_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#3448C5"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "ALIGN",
                    (1, 1),
                    (-1, -1),
                    "CENTER",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F8FAFC"),
                    ],
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ])
        )

        story.append(emotion_table)

        story.append(Spacer(1, 4 * mm))

        dominant_text = (
            f"The most frequently recorded emotion was "
            f"<b>{str(dominant_emotion).title()}</b>, "
            f"with {dominant_count} check-in(s)."
        )

        story.append(
            Paragraph(
                dominant_text,
                normal_style
            )
        )

    else:
        story.append(
            Paragraph(
                "No emotion records are available for the selected period.",
                normal_style
            )
        )

    story.append(PageBreak())

    story.append(
        Paragraph(
            "Recent Mood History",
            section_style
        )
    )

    if records:
        history_table_data = [
            [
                Paragraph("<b>Date and Time</b>", small_style),
                Paragraph("<b>Type</b>", small_style),
                Paragraph("<b>Emotion</b>", small_style),
                Paragraph("<b>Confidence</b>", small_style),
                Paragraph("<b>Note</b>", small_style),
            ]
        ]

        for record in records[:30]:
            note = record["note"] or "-"
            created_at = record["created_at"] or "-"

            history_table_data.append([
                Paragraph(
                    str(created_at),
                    small_style
                ),
                Paragraph(
                    str(
                        record["input_type"] or "Unknown"
                    ),
                    small_style
                ),
                Paragraph(
                    str(
                        record["emotion"] or "Unknown"
                    ).title(),
                    small_style
                ),
                Paragraph(
                    format_confidence(
                        record["confidence"]
                    ),
                    small_style
                ),
                Paragraph(
                    str(note),
                    small_style
                ),
            ])

        history_table = Table(
            history_table_data,
            colWidths=[
                36 * mm,
                25 * mm,
                28 * mm,
                28 * mm,
                48 * mm,
            ],
            repeatRows=1
        )

        history_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#3448C5"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F8FAFC"),
                    ],
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ])
        )

        story.append(history_table)

        if len(records) > 30:
            story.append(Spacer(1, 4 * mm))

            story.append(
                Paragraph(
                    (
                        f"This PDF displays the latest 30 records "
                        f"from a total of {len(records)} records."
                    ),
                    small_style
                )
            )

    else:
        story.append(
            Paragraph(
                (
                    "No mood records were found for this period. "
                    "Use Face, Text, or Voice Analysis to create "
                    "your first emotional check-in."
                ),
                normal_style
            )
        )

    story.append(Spacer(1, 8 * mm))

    disclaimer = (
        "<b>Important:</b> This report is intended for emotional wellness "
        "awareness only. MindAI does not provide medical diagnosis, treatment, "
        "or emergency services. Consider contacting a qualified professional "
        "when you need additional support."
    )

    story.append(
        Paragraph(
            disclaimer,
            small_style
        )
    )

    document.build(
        story,
        onFirstPage=add_pdf_page_number,
        onLaterPages=add_pdf_page_number
    )

    buffer.seek(0)

    safe_name = "".join(
        character
        for character in str(user_name)
        if character.isalnum() or character in ("-", "_")
    )

    if not safe_name:
        safe_name = "user"

    file_name = (
        f"MindAI_Wellness_Report_"
        f"{safe_name}_"
        f"{datetime.now().strftime('%Y%m%d')}.pdf"
    )

    return send_file(
        buffer,
        as_attachment=True,
        download_name=file_name,
        mimetype="application/pdf"
    )