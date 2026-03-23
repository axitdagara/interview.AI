import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024

    AI_PROVIDER_DEFAULT = os.environ.get("AI_PROVIDER_DEFAULT", "groq").strip().lower()

    # Groq defaults (OpenAI-compatible endpoint style).
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", os.environ.get("GROK_API_KEY", "")).strip()
    GROQ_API_BASE_URL = os.environ.get(
        "GROQ_API_BASE_URL",
        os.environ.get("GROK_API_BASE_URL", "https://api.groq.com/openai/v1"),
    ).strip()
    GROQ_MODEL = os.environ.get(
        "GROQ_MODEL",
        os.environ.get("GROK_MODEL", "llama-3.3-70b-versatile"),
    ).strip()

    # Backward-compatible aliases used by existing code paths.
    GROK_API_KEY = GROQ_API_KEY
    GROK_API_BASE_URL = GROQ_API_BASE_URL
    GROK_MODEL = GROQ_MODEL

    # Legacy generic aliases kept for compatibility.
    AI_API_KEY = os.environ.get("AI_API_KEY", GROQ_API_KEY).strip()
    AI_API_BASE_URL = os.environ.get("AI_API_BASE_URL", GROQ_API_BASE_URL).strip()
    AI_MODEL = os.environ.get("AI_MODEL", GROQ_MODEL).strip()
