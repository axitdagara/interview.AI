import csv
import io
import math
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, func

from ..models import InterviewResponse, InterviewSession, Question, ResumeProfile


dashboard_bp = Blueprint("dashboard", __name__)

HISTORY_SORT_OPTIONS = {"recent", "score_desc", "score_asc", "duration_desc", "duration_asc"}


def _build_coach_plan(*, sessions, avg_score, weak_category):
    total_sessions = len(sessions)
    total_questions = sum(int(item.total_questions or 0) for item in sessions)

    latest_score = round(float(sessions[0].average_score), 2) if sessions else None
    previous_score = round(float(sessions[1].average_score), 2) if len(sessions) > 1 else None

    momentum_value = None
    momentum_text = "No previous session"
    momentum_tone = "steady"

    if latest_score is not None and previous_score is not None:
        momentum_value = round(latest_score - previous_score, 2)
        if momentum_value > 0:
            momentum_text = f"+{momentum_value}% vs last session"
            momentum_tone = "up"
        elif momentum_value < 0:
            momentum_text = f"{momentum_value}% vs last session"
            momentum_tone = "down"
        else:
            momentum_text = "No change from last session"

    focus_category = weak_category if weak_category != "N/A" else "General Practice"

    if avg_score < 40:
        title = "Foundation Reset"
        summary = "Prioritize fundamentals and build confidence with slower, focused rounds."
        target_questions = 8
        target_timer = 120
        objective = "Stabilize score above 50%"
    elif avg_score < 70:
        title = "Consistency Sprint"
        summary = "You have strong basics. Improve speed and accuracy with moderate-length rounds."
        target_questions = 12
        target_timer = 90
        objective = "Push average score above 75%"
    else:
        title = "Challenge Mode"
        summary = "Performance is strong. Increase pressure to simulate difficult real interviews."
        target_questions = 15
        target_timer = 60
        objective = "Sustain score above 80%"

    return {
        "total_sessions": total_sessions,
        "total_questions": total_questions,
        "latest_score": latest_score,
        "momentum_value": momentum_value,
        "momentum_text": momentum_text,
        "momentum_tone": momentum_tone,
        "title": title,
        "summary": summary,
        "focus_category": focus_category,
        "target_questions": target_questions,
        "target_timer": target_timer,
        "objective": objective,
    }


def _build_monthly_activity(*, sessions, window_months=6):
    now = datetime.utcnow()
    cursor = datetime(now.year, now.month, 1)
    keys = []

    for _ in range(window_months):
        keys.append((cursor.year, cursor.month))
        if cursor.month == 1:
            cursor = datetime(cursor.year - 1, 12, 1)
        else:
            cursor = datetime(cursor.year, cursor.month - 1, 1)

    keys.reverse()
    counts = {key: 0 for key in keys}

    for item in sessions:
        if not item.start_time:
            continue

        key = (item.start_time.year, item.start_time.month)
        if key in counts:
            counts[key] += 1

    labels = [datetime(year, month, 1).strftime("%b %y") for year, month in keys]
    values = [counts[key] for key in keys]
    return labels, values


def _build_enterprise_insights(*, sessions, avg_score, weak_category, coach_plan, response_rows, difficulty_rows):
    recent_scores = [float(item.average_score or 0.0) for item in sessions[:8]]
    if not recent_scores:
        consistency_score = 0.0
    elif len(recent_scores) == 1:
        consistency_score = 100.0
    else:
        average = sum(recent_scores) / len(recent_scores)
        variance = sum((score - average) ** 2 for score in recent_scores) / len(recent_scores)
        deviation = math.sqrt(variance)
        consistency_score = round(max(0.0, min(100.0, 100.0 - deviation * 2.1)), 2)

    answer_times = [float(row[0]) for row in response_rows if float(row[0] or 0.0) > 0.0]
    avg_time_per_question = round(sum(answer_times) / len(answer_times), 2) if answer_times else 0.0

    if avg_time_per_question <= 0:
        speed_index = 0.0
    elif avg_time_per_question <= 45:
        speed_index = 95.0
    else:
        speed_index = round(max(35.0, 95.0 - ((avg_time_per_question - 45.0) * 0.7)), 2)

    momentum_value = coach_plan.get("momentum_value")
    if momentum_value is None:
        momentum_factor = 50.0
    else:
        momentum_factor = max(25.0, min(75.0, 50.0 + (float(momentum_value) * 4.0)))

    readiness_index = round(
        max(
            0.0,
            min(
                100.0,
                (avg_score * 0.45)
                + (consistency_score * 0.25)
                + (speed_index * 0.15)
                + (momentum_factor * 0.15),
            ),
        ),
        2,
    )

    if readiness_index >= 80:
        readiness_band = "Enterprise Ready"
        readiness_tone = "up"
    elif readiness_index >= 65:
        readiness_band = "Interview Ready"
        readiness_tone = "steady"
    else:
        readiness_band = "Build Phase"
        readiness_tone = "down"

    difficulty_labels = ["Easy", "Medium", "Hard"]
    difficulty_score_map = {label: 0.0 for label in difficulty_labels}
    for difficulty_value, score in difficulty_rows:
        difficulty_label = Question.DIFFICULTY_LABELS.get(int(difficulty_value or 1), "Easy")
        difficulty_score_map[difficulty_label] = round(float(score or 0.0), 2)

    quality_gate = "Pass" if avg_score >= 70 and consistency_score >= 65 else "Watchlist"

    action_items = []
    if avg_score < 70:
        action_items.append("Schedule two focused rounds this week to lift average score above 70%.")
    if weak_category != "N/A":
        action_items.append(f"Prioritize weak category '{weak_category}' with at least one targeted simulation.")
    if avg_time_per_question > 85:
        action_items.append("Run a speed drill mode with lower timer to improve response velocity.")
    if consistency_score < 70:
        action_items.append("Maintain same difficulty for three sessions to stabilize scoring variance.")
    if coach_plan.get("momentum_tone") == "down":
        action_items.append("Review last interview feedback and retry the same category within 24 hours.")

    if len(action_items) < 4:
        action_items.append("Run resume analyzer weekly and align interview rounds with target role requirements.")

    return {
        "readiness_index": readiness_index,
        "readiness_band": readiness_band,
        "readiness_tone": readiness_tone,
        "consistency_score": consistency_score,
        "avg_time_per_question": avg_time_per_question,
        "speed_index": speed_index,
        "quality_gate": quality_gate,
        "difficulty_labels": difficulty_labels,
        "difficulty_scores": [difficulty_score_map[label] for label in difficulty_labels],
        "action_items": action_items[:4],
    }


def _normalize_history_filters(args):
    category = (args.get("category", "All") or "All").strip() or "All"
    if category.casefold() == "all":
        category = "All"

    difficulty = (args.get("difficulty", "All") or "All").strip().title()
    if difficulty not in {"All", "Easy", "Medium", "Hard"}:
        difficulty = "All"

    keyword = (args.get("q", "") or "").strip()

    sort_by = (args.get("sort", "recent") or "recent").strip().lower()
    if sort_by not in HISTORY_SORT_OPTIONS:
        sort_by = "recent"

    min_score_raw = (args.get("min_score", "") or "").strip()
    min_score = None
    if min_score_raw:
        try:
            min_score = max(0.0, min(100.0, float(min_score_raw)))
        except ValueError:
            min_score = None

    start_date_raw = (args.get("start_date", "") or "").strip()
    end_date_raw = (args.get("end_date", "") or "").strip()

    def parse_filter_date(raw_value):
        if not raw_value:
            return None

        # Accept both browser-native ISO dates and common typed date formats.
        candidates = [
            lambda value: datetime.fromisoformat(value),
            lambda value: datetime.strptime(value, "%d-%m-%Y"),
            lambda value: datetime.strptime(value, "%d/%m/%Y"),
            lambda value: datetime.strptime(value, "%Y/%m/%d"),
        ]
        for parser in candidates:
            try:
                return parser(raw_value)
            except ValueError:
                continue

        return None

    start_dt = parse_filter_date(start_date_raw)
    end_dt = parse_filter_date(end_date_raw)
    end_date_display = end_dt.strftime("%Y-%m-%d") if end_dt else ""

    if end_dt:
        end_dt = end_dt + timedelta(days=1)

    return {
        "category": category,
        "difficulty": difficulty,
        "keyword": keyword,
        "sort": sort_by,
        "min_score": min_score,
        "min_score_raw": min_score_raw,
        "start_date": start_dt.strftime("%Y-%m-%d") if start_dt else "",
        "end_date": end_date_display,
        "start_dt": start_dt,
        "end_dt": end_dt,
    }


def _build_history_query(*, user_id, filters):
    query = InterviewSession.query.filter_by(user_id=user_id)

    if filters["category"] != "All":
        query = query.filter(func.lower(func.trim(InterviewSession.category)) == filters["category"].casefold())

    if filters["difficulty"] != "All":
        query = query.filter(
            func.lower(func.trim(InterviewSession.difficulty_level)) == filters["difficulty"].casefold()
        )

    if filters["min_score"] is not None:
        query = query.filter(InterviewSession.average_score >= filters["min_score"])

    if filters["keyword"]:
        match = f"%{filters['keyword']}%"
        query = query.filter(InterviewSession.category.ilike(match))

    if filters["start_dt"]:
        query = query.filter(InterviewSession.start_time >= filters["start_dt"])

    if filters["end_dt"]:
        query = query.filter(InterviewSession.start_time < filters["end_dt"])

    if filters["sort"] == "score_desc":
        query = query.order_by(InterviewSession.average_score.desc(), InterviewSession.start_time.desc())
    elif filters["sort"] == "score_asc":
        query = query.order_by(InterviewSession.average_score.asc(), InterviewSession.start_time.desc())
    elif filters["sort"] == "duration_desc":
        query = query.order_by(InterviewSession.duration_seconds.desc(), InterviewSession.start_time.desc())
    elif filters["sort"] == "duration_asc":
        query = query.order_by(InterviewSession.duration_seconds.asc(), InterviewSession.start_time.desc())
    else:
        query = query.order_by(desc(InterviewSession.start_time))

    return query


def _build_history_summary(sessions):
    session_count = len(sessions)
    if not sessions:
        return {
            "session_count": 0,
            "avg_score": 0.0,
            "best_score": 0.0,
            "avg_duration": 0.0,
        }

    avg_score = round(sum(float(item.average_score or 0.0) for item in sessions) / session_count, 2)
    best_score = round(max(float(item.average_score or 0.0) for item in sessions), 2)
    avg_duration = round(sum(float(item.duration_seconds or 0.0) for item in sessions) / session_count, 1)

    return {
        "session_count": session_count,
        "avg_score": avg_score,
        "best_score": best_score,
        "avg_duration": avg_duration,
    }


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    sessions = (
        InterviewSession.query.filter_by(user_id=current_user.id)
        .order_by(desc(InterviewSession.start_time))
        .all()
    )
    latest_session = sessions[0] if sessions else None

    avg_score = round(sum(item.average_score for item in sessions) / len(sessions), 2) if sessions else 0.0
    best_score = round(max((item.average_score for item in sessions), default=0.0), 2)
    total_interviews = len(sessions)

    if len(sessions) >= 2:
        improvement_score = round(float(sessions[0].average_score or 0.0) - float(sessions[1].average_score or 0.0), 2)
    else:
        improvement_score = 0.0

    category_rows = (
        InterviewResponse.query.with_entities(Question.category, func.avg(InterviewResponse.score))
        .join(Question, Question.id == InterviewResponse.question_id)
        .join(InterviewSession, InterviewSession.id == InterviewResponse.session_id)
        .filter(InterviewSession.user_id == current_user.id)
        .group_by(Question.category)
        .all()
    )

    difficulty_rows = (
        InterviewResponse.query.with_entities(Question.difficulty, func.avg(InterviewResponse.score))
        .join(Question, Question.id == InterviewResponse.question_id)
        .join(InterviewSession, InterviewSession.id == InterviewResponse.session_id)
        .filter(InterviewSession.user_id == current_user.id)
        .group_by(Question.difficulty)
        .all()
    )

    response_rows = (
        InterviewResponse.query.with_entities(InterviewResponse.time_taken, InterviewResponse.score)
        .join(InterviewSession, InterviewSession.id == InterviewResponse.session_id)
        .filter(InterviewSession.user_id == current_user.id)
        .all()
    )

    weak_category = "N/A"
    if category_rows:
        weak_category = min(category_rows, key=lambda row: float(row[1]))[0]

    coach_plan = _build_coach_plan(
        sessions=sessions,
        avg_score=avg_score,
        weak_category=weak_category,
    )

    enterprise = _build_enterprise_insights(
        sessions=sessions,
        avg_score=avg_score,
        weak_category=weak_category,
        coach_plan=coach_plan,
        response_rows=response_rows,
        difficulty_rows=difficulty_rows,
    )

    monthly_labels, monthly_counts = _build_monthly_activity(sessions=sessions)

    timeline_source = list(reversed(sessions[:8]))
    timeline_labels = [item.start_time.strftime("%d %b") for item in timeline_source]
    timeline_scores = [round(item.average_score, 2) for item in timeline_source]

    # Skill buckets are modeled from interview outcomes to visualize recruiter-facing readiness signals.
    technical_skill = round(max(0.0, min(100.0, avg_score)), 2)
    communication_skill = round(max(0.0, min(100.0, (enterprise["consistency_score"] * 0.45) + (avg_score * 0.55))), 2)
    confidence_skill = round(max(0.0, min(100.0, enterprise["readiness_index"])), 2)
    skill_labels = ["Communication", "Technical", "Confidence"]
    skill_scores = [communication_skill, technical_skill, confidence_skill]

    category_labels = [row[0] for row in category_rows]
    category_scores = [round(float(row[1]), 2) for row in category_rows]

    weak_responses = []
    if latest_session:
        weak_responses = (
            InterviewResponse.query.join(Question, Question.id == InterviewResponse.question_id)
            .filter(InterviewResponse.session_id == latest_session.id)
            .filter(InterviewResponse.score < 50)
            .order_by(InterviewResponse.score.asc())
            .limit(5)
            .all()
        )

    recent_resumes = (
        ResumeProfile.query.filter_by(user_id=current_user.id)
        .order_by(desc(ResumeProfile.created_at))
        .limit(3)
        .all()
    )

    return render_template(
        "dashboard.html",
        sessions=sessions[:10],
        recent_sessions=sessions[:5],
        avg_score=avg_score,
        best_score=best_score,
        total_interviews=total_interviews,
        improvement_score=improvement_score,
        weak_category=weak_category,
        timeline_labels=timeline_labels,
        timeline_scores=timeline_scores,
        category_labels=category_labels,
        category_scores=category_scores,
        skill_labels=skill_labels,
        skill_scores=skill_scores,
        difficulty_labels=enterprise["difficulty_labels"],
        difficulty_scores=enterprise["difficulty_scores"],
        monthly_labels=monthly_labels,
        monthly_counts=monthly_counts,
        coach_plan=coach_plan,
        enterprise=enterprise,
        weak_responses=weak_responses,
        latest_session=latest_session,
        recent_resumes=recent_resumes,
    )


@dashboard_bp.route("/history")
@login_required
def history():
    filters = _normalize_history_filters(request.args)
    sessions = _build_history_query(user_id=current_user.id, filters=filters).all()
    total_sessions_count = InterviewSession.query.filter_by(user_id=current_user.id).count()

    has_active_filters = any(
        [
            filters["category"] != "All",
            filters["difficulty"] != "All",
            bool(filters["keyword"]),
            filters["min_score"] is not None,
            filters["start_dt"] is not None,
            filters["end_dt"] is not None,
            filters["sort"] != "recent",
        ]
    )

    category_rows = (
        InterviewSession.query.with_entities(InterviewSession.category)
        .filter_by(user_id=current_user.id)
        .distinct()
        .all()
    )
    history_categories = sorted({row[0] for row in category_rows if row[0]})

    export_url = url_for("dashboard.export_history", **request.args.to_dict())

    return render_template(
        "history.html",
        sessions=sessions,
        history_categories=history_categories,
        history_summary=_build_history_summary(sessions),
        filters=filters,
        export_url=export_url,
        has_active_filters=has_active_filters,
        total_sessions_count=total_sessions_count,
    )


@dashboard_bp.route("/history/export")
@login_required
def export_history():
    filters = _normalize_history_filters(request.args)
    sessions = _build_history_query(user_id=current_user.id, filters=filters).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Difficulty", "Questions", "Average Score", "Duration (s)"])

    for item in sessions:
        writer.writerow(
            [
                item.start_time.strftime("%Y-%m-%d %H:%M:%S") if item.start_time else "",
                item.category,
                item.difficulty_level,
                item.total_questions,
                round(float(item.average_score or 0.0), 2),
                int(item.duration_seconds or 0),
            ]
        )

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    csv_bytes.seek(0)

    return send_file(
        csv_bytes,
        as_attachment=True,
        download_name="interview_history_filtered.csv",
        mimetype="text/csv",
    )
