from interview_simulator.extensions import db
from interview_simulator.models import Question, User, load_user


def test_user_password_hash_roundtrip(app):
    with app.app_context():
        user = User(name="Alice", email="alice@example.com")
        user.set_password("s3cret42")
        db.session.add(user)
        db.session.commit()

        assert user.password_hash != "s3cret42"
        assert user.check_password("s3cret42") is True
        assert user.check_password("wrong") is False


def test_question_options_parsing_and_mcq_flag(app):
    with app.app_context():
        q = Question(
            category="Technical",
            prompt="What is Python?",
            ideal_answer="A programming language",
            difficulty=1,
            options_json='["Lang", "Snake", "IDE", "OS"]',
            correct_option="Lang",
        )
        assert q.options == ["Lang", "Snake", "IDE", "OS"]
        assert q.is_mcq is True

        q.options_json = "not-json"
        assert q.options == []
        assert q.is_mcq is False


def test_load_user_returns_existing_user(app):
    with app.app_context():
        user = User(name="Bob", email="bob@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        loaded = load_user(str(user.id))
        assert loaded is not None
        assert loaded.id == user.id
