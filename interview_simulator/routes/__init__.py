from .ai_generator import ai_generator_bp
from .auth import auth_bp
from .dashboard import dashboard_bp
from .interview import interview_bp
from .main import main_bp
from .resume import resume_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ai_generator_bp)
    app.register_blueprint(interview_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(resume_bp)
