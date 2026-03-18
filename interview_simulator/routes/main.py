from flask import Blueprint, render_template
from flask_login import current_user

from ..models import Question


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    categories = sorted({row[0] for row in Question.query.with_entities(Question.category).all()})
    return render_template(
        "index.html",
        current_user=current_user,
        total_questions=Question.query.count(),
        total_categories=len(categories),
        categories=categories,
    )
