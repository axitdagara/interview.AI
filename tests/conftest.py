import os

import pytest

from interview_simulator import create_app
from interview_simulator.extensions import db
from interview_simulator.models import User
from interview_simulator.seed import seed_questions


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test_app.db"
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Patch config class attributes before create_app() instantiates Flask app.
    from interview_simulator.config import Config

    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
    Config.SECRET_KEY = "test-secret"
    Config.UPLOAD_FOLDER = str(uploads_dir)
    Config.GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "test-groq-key")
    Config.GROK_API_KEY = Config.GROQ_API_KEY
    Config.AI_API_KEY = Config.GROQ_API_KEY

    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_questions()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def create_user(app):
    def _make_user(name="Test User", email="tester@example.com", password="secret123"):
        with app.app_context():
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return user

    return _make_user


@pytest.fixture
def login(client, create_user):
    def _login(email="tester@example.com", password="secret123"):
        create_user(email=email, password=password)
        return client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    return _login
