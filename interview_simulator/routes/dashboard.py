from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import desc, func

from ..models import InterviewResponse, InterviewSession, Question, ResumeProfile


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    sessions = (
        InterviewSession.query.filter_by(user_id=current_user.id)
        .order_by(desc(InterviewSession.start_time))
        .all()
    )

    avg_score = round(sum(item.average_score for item in sessions) / len(sessions), 2) if sessions else 0.0
    best_score = round(max((item.average_score for item in sessions), default=0.0), 2)

    category_rows = (
        InterviewResponse.query.with_entities(Question.category, func.avg(InterviewResponse.score))
        .join(Question, Question.id == InterviewResponse.question_id)
        .join(InterviewSession, InterviewSession.id == InterviewResponse.session_id)
        .filter(InterviewSession.user_id == current_user.id)
        .group_by(Question.category)
        .all()
    )

    weak_category = "N/A"
    if category_rows:
        weak_category = min(category_rows, key=lambda row: float(row[1]))[0]

    timeline_source = list(reversed(sessions[:8]))
    timeline_labels = [item.start_time.strftime("%d %b") for item in timeline_source]
    timeline_scores = [round(item.average_score, 2) for item in timeline_source]

    category_labels = [row[0] for row in category_rows]
    category_scores = [round(float(row[1]), 2) for row in category_rows]

    weak_responses = (
        InterviewResponse.query.join(InterviewSession, InterviewSession.id == InterviewResponse.session_id)
        .join(Question, Question.id == InterviewResponse.question_id)
        .filter(InterviewSession.user_id == current_user.id)
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
        avg_score=avg_score,
        best_score=best_score,
        weak_category=weak_category,
        timeline_labels=timeline_labels,
        timeline_scores=timeline_scores,
        category_labels=category_labels,
        category_scores=category_scores,
        weak_responses=weak_responses,
        recent_resumes=recent_resumes,
    )


@dashboard_bp.route("/history")
@login_required
def history():
    sessions = (
        InterviewSession.query.filter_by(user_id=current_user.id)
        .order_by(desc(InterviewSession.start_time))
        .all()
    )
    return render_template("history.html", sessions=sessions)
