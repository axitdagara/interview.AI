import json

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import InterviewSession, Question
from ..services.ai_question_generator import AIQuestionGenerationError, generate_ai_mcq_questions


ai_generator_bp = Blueprint("ai_generator", __name__, url_prefix="/ai")


DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "grok-4-1-fast-non-reasoning"


def _get_categories():
    rows = Question.query.with_entities(Question.category).distinct().all()
    return sorted({row[0] for row in rows})


def _save_generated_questions(items):
    existing_by_prompt = {}
    rows = Question.query.with_entities(Question.id, Question.prompt).all()
    for question_id, prompt in rows:
        if not prompt:
            continue

        key = prompt.casefold()
        if key not in existing_by_prompt:
            existing_by_prompt[key] = question_id

    inserted = 0
    duplicates = 0
    ordered_question_ids = []

    for item in items:
        prompt_key = item["prompt"].casefold()
        existing_id = existing_by_prompt.get(prompt_key)
        if existing_id:
            duplicates += 1
            ordered_question_ids.append(existing_id)
            continue

        record = Question(
            category=item["category"],
            prompt=item["prompt"],
            ideal_answer=item["ideal_answer"],
            difficulty=item["difficulty"],
            options_json=json.dumps(item["options"], ensure_ascii=True),
            correct_option=item["correct_option"],
        )
        db.session.add(record)
        db.session.flush()

        inserted += 1
        existing_by_prompt[prompt_key] = record.id
        ordered_question_ids.append(record.id)

    if inserted:
        db.session.commit()

    return inserted, duplicates, ordered_question_ids


def _clamp_timer_seconds(raw_value):
    try:
        timer_seconds = int(raw_value)
    except (TypeError, ValueError):
        timer_seconds = 90

    return max(30, min(timer_seconds, 300))


def _resolve_groq_config():
    api_key = (
        current_app.config.get("GROQ_API_KEY", "").strip()
        or current_app.config.get("GROK_API_KEY", "").strip()
        or current_app.config.get("AI_API_KEY", "").strip()
    )
    api_base_url = (
        current_app.config.get("GROQ_API_BASE_URL", "").strip()
        or current_app.config.get("GROK_API_BASE_URL", "").strip()
        or current_app.config.get("AI_API_BASE_URL", "").strip()
        or DEFAULT_GROQ_BASE_URL
    )
    model = (
        current_app.config.get("GROQ_MODEL", "").strip()
        or current_app.config.get("GROK_MODEL", "").strip()
        or current_app.config.get("AI_MODEL", "").strip()
        or DEFAULT_GROQ_MODEL
    )

    if api_key.startswith("gsk_") and "api.x.ai" in api_base_url:
        api_base_url = DEFAULT_GROQ_BASE_URL

    return {
        "api_key": api_key,
        "api_key_name": "GROQ_API_KEY",
        "api_base_url": api_base_url,
        "model": model,
    }


@ai_generator_bp.route("/generator", methods=["GET", "POST"])
@login_required
def generator():
    categories = _get_categories()
    groq_cfg = _resolve_groq_config()
    ready_bundle = session.get("ai_interview_bundle", {})
    ready_question_count = len(ready_bundle.get("question_ids", [])) if isinstance(ready_bundle, dict) else 0

    if request.method == "POST":
        selected_category = request.form.get("category", "").strip()
        custom_category = request.form.get("custom_category", "").strip()
        difficulty_level = request.form.get("difficulty_level", "Medium").strip().title()
        role = request.form.get("role", "").strip()
        focus_topics = request.form.get("focus_topics", "").strip()
        timer_seconds = _clamp_timer_seconds(request.form.get("timer_seconds", 90))

        try:
            count = int(request.form.get("count", 10))
        except ValueError:
            count = 10
        count = max(1, min(count, 20))

        target_category = custom_category or selected_category
        if not target_category:
            flash("Select a category or enter a custom category.", "warning")
            return render_template(
                "ai_generator.html",
                categories=categories,
                groq_cfg=groq_cfg,
                ready_bundle=ready_bundle,
                ready_question_count=ready_question_count,
            )

        if difficulty_level not in {"Easy", "Medium", "Hard"}:
            flash("Please select a valid difficulty level.", "warning")
            return render_template(
                "ai_generator.html",
                categories=categories,
                groq_cfg=groq_cfg,
                ready_bundle=ready_bundle,
                ready_question_count=ready_question_count,
            )

        groq_cfg = _resolve_groq_config()
        if not groq_cfg["api_key"]:
            flash(
                (
                    "Groq API key is missing. "
                    f"Set {groq_cfg['api_key_name']} (or GROK_API_KEY) in your environment."
                ),
                "danger",
            )
            return render_template(
                "ai_generator.html",
                categories=categories,
                groq_cfg=groq_cfg,
                ready_bundle=ready_bundle,
                ready_question_count=ready_question_count,
            )

        try:
            generated_questions = generate_ai_mcq_questions(
                api_key=groq_cfg["api_key"],
                api_base_url=groq_cfg["api_base_url"],
                model=groq_cfg["model"],
                category=target_category,
                difficulty_label=difficulty_level,
                count=count,
                role=role,
                focus_topics=focus_topics,
            )
        except AIQuestionGenerationError as exc:
            flash(str(exc), "danger")
            return render_template(
                "ai_generator.html",
                categories=categories,
                groq_cfg=groq_cfg,
                ready_bundle=ready_bundle,
                ready_question_count=ready_question_count,
            )

        inserted, duplicates, question_ids = _save_generated_questions(generated_questions)
        if not question_ids:
            flash("No valid questions available for interview. Please regenerate.", "warning")
            return render_template(
                "ai_generator.html",
                categories=categories,
                groq_cfg=groq_cfg,
                ready_bundle=ready_bundle,
                ready_question_count=ready_question_count,
            )

        ready_bundle = {
            "question_ids": question_ids,
            "category": target_category,
            "difficulty_level": difficulty_level,
            "timer_seconds": timer_seconds,
        }
        session["ai_interview_bundle"] = ready_bundle
        ready_question_count = len(question_ids)

        flash(
            (
                f"Groq generated {len(generated_questions)} questions. "
                f"Saved {inserted}, reused {duplicates} existing questions. "
                "Questions are hidden for interview integrity."
            ),
            "success",
        )

        if target_category not in categories:
            categories.append(target_category)
            categories.sort()

    return render_template(
        "ai_generator.html",
        categories=categories,
        groq_cfg=groq_cfg,
        ready_bundle=ready_bundle,
        ready_question_count=ready_question_count,
    )


@ai_generator_bp.route("/start-interview", methods=["POST"])
@login_required
def start_interview():
    bundle = session.get("ai_interview_bundle")
    if not isinstance(bundle, dict) or not bundle.get("question_ids"):
        flash("Generate questions first, then start interview.", "warning")
        return redirect(url_for("ai_generator.generator"))

    raw_ids = bundle.get("question_ids", [])
    ordered_ids = []
    seen_ids = set()
    for value in raw_ids:
        try:
            question_id = int(value)
        except (TypeError, ValueError):
            continue

        if question_id in seen_ids:
            continue

        seen_ids.add(question_id)
        ordered_ids.append(question_id)

    if not ordered_ids:
        flash("No valid generated questions found. Please generate again.", "warning")
        return redirect(url_for("ai_generator.generator"))

    available_rows = (
        Question.query.with_entities(Question.id)
        .filter(
            Question.id.in_(ordered_ids),
            Question.options_json.isnot(None),
            Question.correct_option.isnot(None),
        )
        .all()
    )
    available_ids = {row[0] for row in available_rows}
    final_question_ids = [question_id for question_id in ordered_ids if question_id in available_ids]

    if not final_question_ids:
        flash("Generated questions are unavailable now. Please regenerate.", "warning")
        return redirect(url_for("ai_generator.generator"))

    category = (bundle.get("category") or "AI Generated").strip() or "AI Generated"
    difficulty_level = (bundle.get("difficulty_level") or "All").strip().title()
    timer_seconds = _clamp_timer_seconds(bundle.get("timer_seconds", 90))

    interview_session = InterviewSession(
        user_id=current_user.id,
        category=category,
        difficulty_level=difficulty_level,
        total_questions=len(final_question_ids),
    )
    db.session.add(interview_session)
    db.session.commit()

    session["interview_state"] = {
        "session_id": interview_session.id,
        "question_ids": final_question_ids,
        "index": 0,
        "timer_seconds": timer_seconds,
        "difficulty_level": difficulty_level,
        "answers": {},
        "time_taken": {},
        "question_source": "ai",
    }
    session.pop("ai_interview_bundle", None)

    return redirect(url_for("interview.question"))
