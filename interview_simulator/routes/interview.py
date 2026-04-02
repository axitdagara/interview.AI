import json
import csv
import io
import random
from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import InterviewResponse, InterviewSession, Question
from ..services.ai_question_generator import AIQuestionGenerationError, generate_ai_mcq_questions
from ..services.evaluator import evaluate_answer


interview_bp = Blueprint("interview", __name__, url_prefix="/interview")

DIFFICULTY_TO_VALUE = {
    "All": None,
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
}

PRACTICE_MODES = {"balanced", "accuracy", "speed", "executive"}
MAX_ROUND_QUESTION_COUNT = 100

EXTRA_CATEGORIES = [
    "Data Structures",
    "Algorithms",
    "DBMS",
    "Operating Systems",
    "Computer Networks",
    "System Design",
    "Cloud Computing",
    "DevOps",
    "Cybersecurity",
    "Machine Learning",
]


def _to_utc_naive(dt_value):
    if dt_value is None:
        return None

    if dt_value.tzinfo is not None:
        return dt_value.astimezone(timezone.utc).replace(tzinfo=None)

    return dt_value


def _get_categories():
    rows = (
        Question.query.with_entities(Question.category)
        .filter(Question.options_json.isnot(None), Question.correct_option.isnot(None))
        .distinct()
        .all()
    )
    db_categories = {row[0] for row in rows if row[0]}
    if db_categories:
        return sorted(db_categories)

    return sorted(EXTRA_CATEGORIES)


def _persist_generated_questions(items):
    created = []
    for item in items:
        record = Question(
            category=item["category"],
            prompt=item["prompt"],
            ideal_answer=item["ideal_answer"],
            difficulty=item["difficulty"],
            options_json=json.dumps(item["options"], ensure_ascii=True),
            correct_option=item["correct_option"],
        )
        db.session.add(record)
        created.append(record)

    db.session.commit()
    return created


def _get_groq_runtime_config():
    api_key = (
        (current_app.config.get("GROQ_API_KEY", "") or "").strip()
        or (current_app.config.get("GROK_API_KEY", "") or "").strip()
        or (current_app.config.get("AI_API_KEY", "") or "").strip()
    )
    base_url = (
        (current_app.config.get("GROQ_API_BASE_URL", "") or "").strip()
        or (current_app.config.get("GROK_API_BASE_URL", "") or "").strip()
        or "https://api.groq.com/openai/v1"
    )
    model = (
        (current_app.config.get("GROQ_MODEL", "") or "").strip()
        or (current_app.config.get("GROK_MODEL", "") or "").strip()
        or "llama-3.3-70b-versatile"
    )

    # Auto-correct common mismatch: Groq key with xAI endpoint.
    if api_key.startswith("gsk_") and "api.x.ai" in base_url:
        base_url = "https://api.groq.com/openai/v1"

    return {
        "api_key": api_key,
        "base_url": base_url or "https://api.groq.com/openai/v1",
        "model": model or "llama-3.3-70b-versatile",
    }


def _generate_questions_with_grok(*, category, difficulty_level, count, role_context, focus_topics):
    cfg = _get_groq_runtime_config()
    if not cfg["api_key"]:
        raise AIQuestionGenerationError(
            "Groq API key is missing. Set GROQ_API_KEY (or GROK_API_KEY) in environment variables."
        )

    return generate_ai_mcq_questions(
        api_key=cfg["api_key"],
        api_base_url=cfg["base_url"],
        model=cfg["model"],
        category=category,
        difficulty_label=difficulty_level,
        count=count,
        role=role_context,
        focus_topics=focus_topics,
    )


def _normalize_level(level_value):
    candidate = (level_value or "All").strip().title()
    return candidate if candidate in DIFFICULTY_TO_VALUE else "All"


def _normalize_practice_mode(mode_value):
    candidate = (mode_value or "balanced").strip().lower()
    return candidate if candidate in PRACTICE_MODES else "balanced"


def _build_availability_map():
    levels = ["All", "Easy", "Medium", "Hard"]
    categories = ["All", *_get_categories()]

    availability = {
        category: {level: 0 for level in levels}
        for category in categories
    }

    questions = (
        Question.query.filter(Question.options_json.isnot(None), Question.correct_option.isnot(None))
        .all()
    )

    for item in questions:
        level = item.difficulty_label
        availability["All"]["All"] += 1
        availability["All"][level] += 1

        if item.category not in availability:
            availability[item.category] = {entry: 0 for entry in levels}

        availability[item.category]["All"] += 1
        availability[item.category][level] += 1

    return availability


def _get_last_session_question_ids(user_id):
    last_session = (
        InterviewSession.query.filter_by(user_id=user_id)
        .order_by(InterviewSession.start_time.desc(), InterviewSession.id.desc())
        .first()
    )
    if not last_session:
        return set()

    rows = (
        InterviewResponse.query.with_entities(InterviewResponse.question_id)
        .filter_by(session_id=last_session.id)
        .all()
    )
    return {row[0] for row in rows}


def _select_questions_for_round(available_questions, question_count, user_id):
    if question_count >= len(available_questions):
        selected = list(available_questions)
        random.shuffle(selected)
        return selected

    previous_ids = _get_last_session_question_ids(user_id)
    fresh_pool = [question for question in available_questions if question.id not in previous_ids]
    reused_pool = [question for question in available_questions if question.id in previous_ids]

    if len(fresh_pool) >= question_count:
        return random.sample(fresh_pool, question_count)

    selected = list(fresh_pool)
    needed = question_count - len(selected)

    if needed > 0 and reused_pool:
        selected.extend(random.sample(reused_pool, min(needed, len(reused_pool))))

    random.shuffle(selected)
    return selected


def _build_option_order_map(selected_questions):
    option_orders = {}
    for question in selected_questions:
        options = list(question.options)
        if len(options) < 2:
            continue
        random.shuffle(options)
        option_orders[str(question.id)] = options
    return option_orders


def _get_question_options_for_session(state, question_record):
    option_orders = state.get("option_orders", {})
    question_key = str(question_record.id)
    options = list(question_record.options)

    if not options:
        return []

    ordered = option_orders.get(question_key)
    if ordered and sorted(ordered, key=str.casefold) == sorted(options, key=str.casefold):
        return ordered

    shuffled = list(options)
    if len(shuffled) > 1:
        random.shuffle(shuffled)
    option_orders[question_key] = shuffled
    state["option_orders"] = option_orders
    session["interview_state"] = state
    return shuffled


def _evaluate_mcq_answer(question_record, selected_option):
    selected = (selected_option or "").strip()
    correct = (question_record.correct_option or "").strip()

    if not selected:
        return {
            "score": 0.0,
            "feedback": f"No option selected. Correct answer: {correct}. {question_record.ideal_answer}",
            "missing_keywords": [],
        }

    is_correct = selected.lower() == correct.lower()
    if is_correct:
        return {
            "score": 100.0,
            "feedback": f"Correct answer. {question_record.ideal_answer}",
            "missing_keywords": [],
        }

    return {
        "score": 0.0,
        "feedback": f"Incorrect answer. Correct answer: {correct}. {question_record.ideal_answer}",
        "missing_keywords": [],
    }


def _score_band(score):
    if score >= 80:
        return "Outstanding"
    if score >= 60:
        return "Strong"
    if score >= 40:
        return "Moderate"
    return "Needs Improvement"


def _save_current_answer_in_state(state, form_data):
    question_ids = state.get("question_ids", [])
    if not question_ids:
        return state

    index = int(state.get("index", 0))
    if index < 0 or index >= len(question_ids):
        return state

    selected_option = form_data.get("selected_option", "").strip()
    text_answer = form_data.get("answer", "").strip()
    voice_answer = form_data.get("voice_answer", "").strip()
    answer_value = selected_option or text_answer or voice_answer

    answers = state.get("answers", {})
    if answer_value:
        answers[str(index)] = answer_value
    else:
        answers.pop(str(index), None)

    state["answers"] = answers

    try:
        time_taken = float(form_data.get("time_taken", 0.0))
    except (TypeError, ValueError):
        time_taken = 0.0

    if time_taken > 0:
        time_map = state.get("time_taken", {})
        previous_value = float(time_map.get(str(index), 0.0) or 0.0)
        time_map[str(index)] = round(max(previous_value, time_taken), 2)
        state["time_taken"] = time_map

    return state


def _find_first_unanswered_index(question_ids, answers):
    for index in range(len(question_ids)):
        if not answers.get(str(index)):
            return index
    return None


def _find_previous_skipped_index(question_ids, answers, current_index):
    for index in range(current_index - 1, -1, -1):
        if not answers.get(str(index)):
            return index

    for index in range(len(question_ids) - 1, current_index, -1):
        if not answers.get(str(index)):
            return index

    return max(current_index - 1, 0)


def _finalize_session(session_id):
    interview_session = db.session.get(InterviewSession, session_id)
    if not interview_session:
        return None

    average = (
        db.session.query(func.avg(InterviewResponse.score))
        .filter_by(session_id=session_id)
        .scalar()
    )
    average = float(average or 0.0)

    interview_session.average_score = round(average, 2)
    interview_session.end_time = datetime.utcnow()

    if interview_session.start_time:
        start_time = _to_utc_naive(interview_session.start_time)
        end_time = _to_utc_naive(interview_session.end_time)

        if start_time and end_time:
            interview_session.duration_seconds = max(0, int((end_time - start_time).total_seconds()))

    db.session.commit()
    session.pop("interview_state", None)
    return interview_session


@interview_bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    categories = _get_categories()
    difficulty_levels = list(DIFFICULTY_TO_VALUE.keys())
    availability_map = _build_availability_map()

    if request.method == "POST":
        question_source = (request.form.get("question_source", "bank") or "bank").strip().lower()
        if question_source not in {"bank", "ai"}:
            question_source = "bank"

        selected_category = request.form.get("category", "All")
        custom_category = request.form.get("custom_category", "").strip()
        role_context = request.form.get("role_context", "").strip()
        focus_topics = request.form.get("focus_topics", "").strip()
        practice_mode = _normalize_practice_mode(request.form.get("practice_mode", "balanced"))

        category = custom_category or selected_category
        difficulty_level = _normalize_level(request.form.get("difficulty_level", "All"))

        try:
            question_count = int(request.form.get("question_count", 20))
        except ValueError:
            question_count = 20

        try:
            timer_seconds = int(request.form.get("timer_seconds", 90))
        except ValueError:
            timer_seconds = 90

        question_count = max(1, min(question_count, MAX_ROUND_QUESTION_COUNT))
        timer_seconds = max(30, min(timer_seconds, 300))

        if practice_mode == "accuracy":
            timer_seconds = max(timer_seconds, 120)
            if difficulty_level == "All":
                difficulty_level = "Medium"
        elif practice_mode == "speed":
            timer_seconds = min(timer_seconds, 60)
            question_count = max(question_count, 10)
            if difficulty_level == "All":
                difficulty_level = "Medium"
        elif practice_mode == "executive":
            timer_seconds = min(timer_seconds, 75)
            question_count = max(question_count, 12)
            if difficulty_level == "All":
                difficulty_level = "Hard"

        if question_source == "ai":
            if not category or category == "All":
                flash("For AI mode, select a specific category or enter a custom category.", "warning")
                return redirect(url_for("interview.setup"))

            if difficulty_level == "All":
                flash("For AI mode, choose Easy, Medium, or Hard difficulty.", "warning")
                return redirect(url_for("interview.setup"))

            try:
                generated_questions = _generate_questions_with_grok(
                    category=category,
                    difficulty_level=difficulty_level,
                    count=question_count,
                    role_context=role_context,
                    focus_topics=focus_topics,
                )
            except AIQuestionGenerationError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("interview.setup"))

            selected_questions = _persist_generated_questions(generated_questions)
            selected_count = len(selected_questions)

            if selected_count < question_count:
                flash(
                    (
                        f"Grok returned {selected_count} valid questions for this request. "
                        f"Starting with available generated questions."
                    ),
                    "warning",
                )
            else:
                flash("Grok generated fresh questions for this round.", "success")
        else:
            query = Question.query.filter(Question.options_json.isnot(None), Question.correct_option.isnot(None))
            if category != "All":
                query = query.filter_by(category=category)

            difficulty_value = DIFFICULTY_TO_VALUE[difficulty_level]
            if difficulty_value is not None:
                query = query.filter_by(difficulty=difficulty_value)

            available_questions = query.all()
            if not available_questions:
                flash("No MCQ questions available for selected category and level.", "warning")
                return redirect(url_for("interview.setup"))

            selected_count = min(question_count, len(available_questions))
            if selected_count < question_count:
                flash(
                    (
                        f"Only {selected_count} unique questions are available for this filter. "
                        f"Starting a {selected_count}-question round."
                    ),
                    "warning",
                )

            selected_questions = _select_questions_for_round(
                available_questions,
                selected_count,
                current_user.id,
            )

        interview_session = InterviewSession(
            user_id=current_user.id,
            category=category,
            difficulty_level=difficulty_level,
            total_questions=selected_count,
        )
        db.session.add(interview_session)
        db.session.commit()

        session["interview_state"] = {
            "session_id": interview_session.id,
            "question_ids": [question.id for question in selected_questions],
            "index": 0,
            "timer_seconds": timer_seconds,
            "difficulty_level": difficulty_level,
            "practice_mode": practice_mode,
            "answers": {},
            "time_taken": {},
            "question_source": question_source,
            "option_orders": _build_option_order_map(selected_questions),
        }

        return redirect(url_for("interview.question"))

    return render_template(
        "interview_setup.html",
        categories=categories,
        difficulty_levels=difficulty_levels,
        availability_map=availability_map,
        default_source="bank",
        default_practice_mode="balanced",
    )


@interview_bp.route("/question")
@login_required
def question():
    state = session.get("interview_state")
    if not state:
        flash("Start an interview first.", "warning")
        return redirect(url_for("interview.setup"))

    question_ids = state.get("question_ids", [])
    if not question_ids:
        flash("No active interview found.", "warning")
        session.pop("interview_state", None)
        return redirect(url_for("interview.setup"))

    index = int(state.get("index", 0))
    if index < 0:
        index = 0
    if index >= len(question_ids):
        index = len(question_ids) - 1
    if index != state.get("index"):
        state["index"] = index
        session["interview_state"] = state

    answers = state.get("answers", {})

    question_record = db.session.get(Question, question_ids[index])
    if not question_record:
        flash("Question not found. Please restart the interview.", "danger")
        session.pop("interview_state", None)
        return redirect(url_for("interview.setup"))

    question_options = _get_question_options_for_session(state, question_record)

    selected_answer = answers.get(str(index), "")
    attempted_count = sum(1 for pos in range(len(question_ids)) if answers.get(str(pos)))
    skipped_count = len(question_ids) - attempted_count
    progress = int((attempted_count / max(len(question_ids), 1)) * 100)
    attempt_flags = [bool(answers.get(str(pos))) for pos in range(len(question_ids))]

    return render_template(
        "interview_question.html",
        question=question_record,
        question_options=question_options,
        question_number=index + 1,
        total_questions=len(question_ids),
        timer_seconds=state.get("timer_seconds", 90),
        progress=progress,
        selected_level=state.get("difficulty_level", "All"),
        selected_answer=selected_answer,
        attempted_count=attempted_count,
        skipped_count=skipped_count,
        attempt_flags=attempt_flags,
        question_source=state.get("question_source", "bank"),
        practice_mode=state.get("practice_mode", "balanced"),
    )


@interview_bp.route("/submit", methods=["POST"])
@login_required
def submit_answer():
    state = session.get("interview_state")
    if not state:
        flash("Interview session expired. Please start again.", "warning")
        return redirect(url_for("interview.setup"))

    question_ids = state.get("question_ids", [])
    if not question_ids:
        flash("No active interview found.", "warning")
        session.pop("interview_state", None)
        return redirect(url_for("interview.setup"))

    state = _save_current_answer_in_state(state, request.form)
    session["interview_state"] = state

    answers = state.get("answers", {})
    time_map = state.get("time_taken", {})
    session_id = state["session_id"]

    InterviewResponse.query.filter_by(session_id=session_id).delete(synchronize_session=False)

    for index, question_id in enumerate(question_ids):
        question_record = db.session.get(Question, question_id)
        if not question_record:
            continue

        answer_value = (answers.get(str(index), "") or "").strip()

        if question_record.is_mcq:
            evaluation = _evaluate_mcq_answer(question_record, answer_value)
        else:
            if not answer_value:
                evaluation = {
                    "score": 0.0,
                    "feedback": "No answer submitted.",
                    "missing_keywords": [],
                }
            else:
                evaluation = evaluate_answer(answer_value, question_record.ideal_answer)

        response = InterviewResponse(
            session_id=session_id,
            question_id=question_record.id,
            user_answer=answer_value or "Not attempted",
            score=evaluation["score"],
            feedback=evaluation["feedback"],
            missing_keywords=",".join(evaluation["missing_keywords"]),
            time_taken=round(float(time_map.get(str(index), 0.0) or 0.0), 2),
        )
        db.session.add(response)

    db.session.commit()

    interview_session = _finalize_session(session_id)
    if not interview_session:
        flash("Could not finalize interview session.", "danger")
        return redirect(url_for("interview.setup"))

    return redirect(url_for("interview.result", session_id=interview_session.id))


@interview_bp.route("/next", methods=["POST"])
@login_required
def next_question():
    state = session.get("interview_state")
    if not state:
        flash("Interview session expired. Please start again.", "warning")
        return redirect(url_for("interview.setup"))

    question_ids = state.get("question_ids", [])
    if not question_ids:
        flash("No active interview found.", "warning")
        session.pop("interview_state", None)
        return redirect(url_for("interview.setup"))

    state = _save_current_answer_in_state(state, request.form)
    answers = state.get("answers", {})

    current_index = int(state.get("index", 0))
    next_index = current_index + 1

    if next_index >= len(question_ids):
        unanswered_index = _find_first_unanswered_index(question_ids, answers)
        if unanswered_index is not None:
            next_index = unanswered_index
            flash("Reached end. Jumped to first skipped question.", "info")
        else:
            next_index = len(question_ids) - 1
            flash("All questions attempted. Click Submit Final Result.", "info")

    state["index"] = next_index
    session["interview_state"] = state

    return redirect(url_for("interview.question"))


@interview_bp.route("/previous", methods=["POST"])
@login_required
def previous_question():
    state = session.get("interview_state")
    if not state:
        flash("Interview session expired. Please start again.", "warning")
        return redirect(url_for("interview.setup"))

    question_ids = state.get("question_ids", [])
    if not question_ids:
        flash("No active interview found.", "warning")
        session.pop("interview_state", None)
        return redirect(url_for("interview.setup"))

    state = _save_current_answer_in_state(state, request.form)
    answers = state.get("answers", {})

    current_index = int(state.get("index", 0))
    previous_index = _find_previous_skipped_index(question_ids, answers, current_index)

    if previous_index != current_index and not answers.get(str(previous_index)):
        flash("Moved to a skipped question.", "info")

    state["index"] = previous_index
    session["interview_state"] = state

    return redirect(url_for("interview.question"))


@interview_bp.route("/jump-skipped", methods=["POST"])
@login_required
def jump_skipped():
    state = session.get("interview_state")
    if not state:
        flash("Interview session expired. Please start again.", "warning")
        return redirect(url_for("interview.setup"))

    question_ids = state.get("question_ids", [])
    if not question_ids:
        flash("No active interview found.", "warning")
        session.pop("interview_state", None)
        return redirect(url_for("interview.setup"))

    state = _save_current_answer_in_state(state, request.form)
    answers = state.get("answers", {})
    skipped_index = _find_first_unanswered_index(question_ids, answers)

    if skipped_index is None:
        flash("No skipped questions left.", "info")
    else:
        state["index"] = skipped_index
        flash("Jumped to first skipped question.", "info")

    session["interview_state"] = state

    return redirect(url_for("interview.question"))


@interview_bp.route("/result/<int:session_id>")
@login_required
def result(session_id):
    interview_session = InterviewSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()

    responses = (
        InterviewResponse.query.filter_by(session_id=interview_session.id)
        .order_by(InterviewResponse.id.asc())
        .all()
    )

    enriched_rows = []
    for row in responses:
        missing = [token for token in (row.missing_keywords or "").split(",") if token]
        enriched_rows.append(
            {
                "question": row.question.prompt,
                "difficulty": row.question.difficulty_label,
                "answer": row.user_answer,
                "correct_option": row.question.correct_option,
                "score": row.score,
                "status": "True" if row.score >= 100 else "False",
                "feedback": row.feedback,
                "missing": missing,
                "time_taken": row.time_taken,
            }
        )

    return render_template(
        "interview_result.html",
        interview_session=interview_session,
        responses=enriched_rows,
        score_band=_score_band(interview_session.average_score),
    )


@interview_bp.route("/export/<int:session_id>")
@login_required
def export_csv(session_id):
    interview_session = InterviewSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()

    responses = (
        InterviewResponse.query.filter_by(session_id=interview_session.id)
        .order_by(InterviewResponse.id.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Question",
            "Difficulty",
            "Answer",
            "Correct Option",
            "Outcome",
            "Score",
            "Feedback",
            "Missing Keywords",
            "Time Taken (s)",
        ]
    )

    for row in responses:
        writer.writerow(
            [
                row.question.prompt,
                row.question.difficulty_label,
                row.user_answer,
                row.question.correct_option,
                "True" if row.score >= 100 else "False",
                row.score,
                row.feedback,
                row.missing_keywords,
                row.time_taken,
            ]
        )

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    csv_bytes.seek(0)

    filename = f"interview_report_{interview_session.id}.csv"
    return send_file(
        csv_bytes,
        as_attachment=True,
        download_name=filename,
        mimetype="text/csv",
    )
