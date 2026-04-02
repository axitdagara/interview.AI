import io

from flask import Blueprint, current_app, flash, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import desc
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import ResumeProfile
from ..services.resume_parser import (
    AIResumeAnalysisError,
    DEFAULT_ROLE_OPTIONS,
    analyze_resume_with_ai,
    extract_text_from_pdf,
)


resume_bp = Blueprint("resume", __name__, url_prefix="/resume")


DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def _allowed_file(filename):
    return filename.lower().endswith(".pdf")


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
        "api_base_url": api_base_url,
        "model": model,
    }


@resume_bp.route("/analyzer", methods=["GET", "POST"])
@login_required
def analyzer():
    roles = list(DEFAULT_ROLE_OPTIONS)
    result = None

    if request.method == "POST":
        role = request.form.get("role", roles[0] if roles else "Software Engineer").strip()
        job_description = request.form.get("job_description", "").strip()
        uploaded_file = request.files.get("resume")

        if not uploaded_file or not uploaded_file.filename:
            flash("Please upload a resume PDF file.", "warning")
            return render_template("resume_analyzer.html", roles=roles, result=result)

        if not _allowed_file(uploaded_file.filename):
            flash("Invalid file type. Upload only PDF files.", "danger")
            return render_template("resume_analyzer.html", roles=roles, result=result)

        filename = secure_filename(uploaded_file.filename)

        try:
            file_bytes = uploaded_file.read()
            resume_text = extract_text_from_pdf(io.BytesIO(file_bytes))
        except Exception:
            flash("Could not read the PDF. Please upload a valid text-based resume.", "danger")
            return render_template("resume_analyzer.html", roles=roles, result=result)

        groq_cfg = _resolve_groq_config()
        if not groq_cfg["api_key"]:
            flash("Groq API key is missing. Set GROQ_API_KEY (or GROK_API_KEY).", "danger")
            return render_template("resume_analyzer.html", roles=roles, result=result)

        try:
            analysis = analyze_resume_with_ai(
                api_key=groq_cfg["api_key"],
                api_base_url=groq_cfg["api_base_url"],
                model=groq_cfg["model"],
                resume_text=resume_text,
                role=role,
                job_description=job_description,
            )
        except AIResumeAnalysisError as exc:
            flash(str(exc), "danger")
            return render_template("resume_analyzer.html", roles=roles, result=result)

        detected_skills = analysis.get("detected_skills", [])
        overall_score = float(analysis.get("overall_score", 0.0))

        profile = ResumeProfile(
            user_id=current_user.id,
            filename=filename,
            extracted_skills=", ".join(detected_skills),
            role=role,
            match_score=overall_score,
        )
        db.session.add(profile)
        db.session.commit()

        result = {
            "filename": filename,
            "role": role,
            "overall_score": overall_score,
            "ats_accuracy_score": float(analysis.get("ats_accuracy_score", overall_score)),
            "role_fit": analysis.get("role_fit", "Unknown"),
            "experience_level": analysis.get("experience_level", "Unknown"),
            "summary": analysis.get("summary", ""),
            "detected_skills": detected_skills,
            "strengths": analysis.get("strengths", []),
            "improvement_areas": analysis.get("improvement_areas", []),
            "recommended_skills": analysis.get("recommended_skills", []),
            "ats_tips": analysis.get("ats_tips", []),
            "jd_alignment_score": analysis.get("jd_alignment_score", overall_score),
            "jd_gap_summary": analysis.get("jd_gap_summary", ""),
            "jd_recommendations": analysis.get("jd_recommendations", []),
            "recruiter_highlights": analysis.get("recruiter_highlights", []),
            "job_description": job_description,
            "word_count": len((resume_text or "").split()),
        }

        flash("Resume analyzed successfully.", "success")

    recent_profiles = (
        ResumeProfile.query.filter_by(user_id=current_user.id)
        .order_by(desc(ResumeProfile.created_at))
        .limit(5)
        .all()
    )

    return render_template(
        "resume_analyzer.html",
        roles=roles,
        result=result,
        recent_profiles=recent_profiles,
    )
