import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from .extensions import db, login_manager
from .migrations import run_startup_migrations
from .routes import register_blueprints
from .seed import seed_questions


def create_app():
    # Load .env before importing Config so class-level env reads are up to date.
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env", override=True)

    from .config import Config

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    register_blueprints(app)

    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        db.create_all()
        run_startup_migrations()
        seed_questions()

    return app
