from sqlalchemy import text

from .extensions import db


def _table_exists(connection, table_name):
    query = text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name")
    return connection.execute(query, {"table_name": table_name}).scalar() is not None


def _get_sqlite_columns(connection, table_name):
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    return {row["name"] for row in rows}


def _add_column_if_missing(connection, table_name, column_name, definition):
    columns = _get_sqlite_columns(connection, table_name)
    if column_name in columns:
        return

    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))


def run_startup_migrations():
    if db.engine.dialect.name != "sqlite":
        return

    with db.engine.begin() as connection:
        if _table_exists(connection, "questions"):
            _add_column_if_missing(connection, "questions", "options_json", "TEXT")
            _add_column_if_missing(connection, "questions", "correct_option", "VARCHAR(255)")

        if _table_exists(connection, "interview_sessions"):
            _add_column_if_missing(
                connection,
                "interview_sessions",
                "difficulty_level",
                "VARCHAR(20) NOT NULL DEFAULT 'All'",
            )
