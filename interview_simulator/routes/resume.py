import io

from flask import Blueprint, flash, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import desc
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import ResumeProfile
from ..services.resume_parser import ROLE_SKILLS, compute_role_match, extract_skills, extract_text_from_pdf


resume_bp = Blueprint("resume", __name__, url_prefix="/resume")


def _allowed_file(filename):
    return filename.lower().endswith(".pdf")


@resume_bp.route("/analyzer", methods=["GET", "POST"])
@login_required
def analyzer():
    roles = sorted(ROLE_SKILLS.keys())
    result = None

    if request.method == "POST":
        role = request.form.get("role", roles[0] if roles else "Software Engineer")
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

        skills = extract_skills(resume_text)
        match_score, matched_skills, missing_skills = compute_role_match(skills, role)

        profile = ResumeProfile(
            user_id=current_user.id,
            filename=filename,
            extracted_skills=", ".join(skills),
            role=role,
            match_score=match_score,
        )
        db.session.add(profile)
        db.session.commit()

        result = {
            "filename": filename,
            "role": role,
            "skills": skills,
            "match_score": match_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
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
