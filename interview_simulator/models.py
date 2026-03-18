import json
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    # SQLite DateTime commonly round-trips as naive values, so use UTC-naive
    # timestamps consistently to avoid arithmetic mismatches.
    return datetime.utcnow()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    sessions = db.relationship("InterviewSession", backref="user", lazy=True, cascade="all, delete-orphan")
    resumes = db.relationship("ResumeProfile", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Question(db.Model):
    __tablename__ = "questions"

    DIFFICULTY_LABELS = {
        1: "Easy",
        2: "Medium",
        3: "Hard",
    }

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    ideal_answer = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer, nullable=False, default=1)
    options_json = db.Column(db.Text)
    correct_option = db.Column(db.String(255))

    @property
    def difficulty_label(self):
        return self.DIFFICULTY_LABELS.get(self.difficulty, "Easy")

    @property
    def options(self):
        if not self.options_json:
            return []

        try:
            raw_options = json.loads(self.options_json)
        except (TypeError, json.JSONDecodeError):
            return []

        if not isinstance(raw_options, list):
            return []

        return [str(option).strip() for option in raw_options if str(option).strip()]

    @property
    def is_mcq(self):
        return bool(self.correct_option and self.options)


class InterviewSession(db.Model):
    __tablename__ = "interview_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, default="All")
    difficulty_level = db.Column(db.String(20), nullable=False, default="All")
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    average_score = db.Column(db.Float, nullable=False, default=0.0)
    start_time = db.Column(db.DateTime, nullable=False, default=utcnow)
    end_time = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer, default=0)

    responses = db.relationship("InterviewResponse", backref="session", lazy=True, cascade="all, delete-orphan")


class InterviewResponse(db.Model):
    __tablename__ = "interview_responses"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("interview_sessions.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    user_answer = db.Column(db.Text, nullable=False)
    score = db.Column(db.Float, nullable=False, default=0.0)
    feedback = db.Column(db.Text, nullable=False)
    missing_keywords = db.Column(db.Text, default="")
    time_taken = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    question = db.relationship("Question")


class ResumeProfile(db.Model):
    __tablename__ = "resume_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    extracted_skills = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(120), nullable=False)
    match_score = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
