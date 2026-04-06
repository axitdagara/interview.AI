import json

from interview_simulator.extensions import db
from interview_simulator.models import InterviewSession, Question


def test_interview_setup_requires_login(client):
    response = client.get("/interview/setup", follow_redirects=False)
    assert response.status_code in {302, 401}


def test_interview_round_submission_and_result(client, login, app):
    login()

    setup_response = client.post(
        "/interview/setup",
        data={
            "question_source": "bank",
            "category": "All",
            "difficulty_level": "All",
            "question_count": "1",
            "timer_seconds": "90",
            "practice_mode": "balanced",
        },
        follow_redirects=False,
    )
    assert setup_response.status_code == 302
    assert "/interview/question" in setup_response.headers["Location"]

    with client.session_transaction() as session_data:
        state = session_data["interview_state"]

    with app.app_context():
        question = Question.query.get(state["question_ids"][0])
        assert question is not None
        chosen = question.correct_option

    submit_response = client.post(
        "/interview/submit",
        data={"selected_option": chosen, "time_taken": "12.5"},
        follow_redirects=False,
    )
    assert submit_response.status_code == 302
    assert "/interview/result/" in submit_response.headers["Location"]

    result_response = client.get(submit_response.headers["Location"])
    assert result_response.status_code == 200

    with app.app_context():
        latest = InterviewSession.query.order_by(InterviewSession.id.desc()).first()
        assert latest is not None
        assert latest.total_questions == 1
        assert latest.average_score >= 0


def test_interview_question_page_shows_voice_bot_controls(client, login):
    login()

    setup_response = client.post(
        "/interview/setup",
        data={
            "question_source": "bank",
            "category": "All",
            "difficulty_level": "All",
            "question_count": "1",
            "timer_seconds": "90",
            "practice_mode": "balanced",
        },
        follow_redirects=False,
    )
    assert setup_response.status_code == 302

    question_response = client.get("/interview/question")
    assert question_response.status_code == 200
    assert b"Read Question Aloud" in question_response.data
    assert b"Start Voice Answer" in question_response.data
    assert b"AI Voice Bot" in question_response.data


def test_interview_setup_supports_large_round_count(client, login):
    login()

    setup_response = client.post(
        "/interview/setup",
        data={
            "question_source": "bank",
            "category": "All",
            "difficulty_level": "All",
            "question_count": "50",
            "timer_seconds": "90",
            "practice_mode": "balanced",
        },
        follow_redirects=False,
    )
    assert setup_response.status_code == 302
    assert "/interview/question" in setup_response.headers["Location"]

    with client.session_transaction() as session_data:
        state = session_data["interview_state"]

    assert len(state["question_ids"]) == 50


def test_interview_result_shows_overall_details_for_large_round(client, login, app):
    login()

    setup_response = client.post(
        "/interview/setup",
        data={
            "question_source": "bank",
            "category": "All",
            "difficulty_level": "All",
            "question_count": "25",
            "timer_seconds": "90",
            "practice_mode": "balanced",
        },
        follow_redirects=False,
    )
    assert setup_response.status_code == 302

    with client.session_transaction() as session_data:
        state = session_data["interview_state"]

    with app.app_context():
        question = Question.query.get(state["question_ids"][0])
        assert question is not None

    submit_response = client.post(
        "/interview/submit",
        data={"selected_option": question.correct_option, "time_taken": "10"},
        follow_redirects=False,
    )
    assert submit_response.status_code == 302

    result_response = client.get(submit_response.headers["Location"])
    assert result_response.status_code == 200
    assert b"Overall Details" in result_response.data
    assert b"25 questions" in result_response.data
    assert b"Attempted" in result_response.data


def test_interview_round_has_no_repeated_questions(client, login, app):
    login()

    with app.app_context():
        duplicate_items = [
            Question(
                category="NoRepeatTest",
                difficulty=2,
                prompt="What is polymorphism?",
                ideal_answer="Ability of same interface with different implementations.",
                options_json=json.dumps(
                    [
                        "Same interface, multiple implementations",
                        "Only compile-time optimization",
                        "Data encryption method",
                        "Network protocol",
                    ]
                ),
                correct_option="Same interface, multiple implementations",
            ),
            Question(
                category="NoRepeatTest",
                difficulty=2,
                prompt="What is polymorphism?",
                ideal_answer="Ability of same interface with different implementations.",
                options_json=json.dumps(
                    [
                        "Same interface, multiple implementations",
                        "Only compile-time optimization",
                        "Data encryption method",
                        "Network protocol",
                    ]
                ),
                correct_option="Same interface, multiple implementations",
            ),
            Question(
                category="NoRepeatTest",
                difficulty=2,
                prompt="What is encapsulation?",
                ideal_answer="Bundling data and methods together with controlled access.",
                options_json=json.dumps(
                    [
                        "Bundling data and methods with access control",
                        "Splitting class into many files",
                        "Network packet routing",
                        "Database sharding",
                    ]
                ),
                correct_option="Bundling data and methods with access control",
            ),
        ]
        db.session.add_all(duplicate_items)
        db.session.commit()

    setup_response = client.post(
        "/interview/setup",
        data={
            "question_source": "bank",
            "category": "NoRepeatTest",
            "difficulty_level": "Medium",
            "question_count": "10",
            "timer_seconds": "90",
            "practice_mode": "balanced",
        },
        follow_redirects=False,
    )
    assert setup_response.status_code == 302
    assert "/interview/question" in setup_response.headers["Location"]

    with client.session_transaction() as session_data:
        state = session_data["interview_state"]

    with app.app_context():
        prompts = [Question.query.get(question_id).prompt for question_id in state["question_ids"]]

    normalized = [" ".join(str(prompt).split()).casefold() for prompt in prompts]
    assert len(normalized) == len(set(normalized))
    assert len(state["question_ids"]) == 2


def test_dashboard_history_and_exports(client, login):
    login()

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200

    history_response = client.get("/history")
    assert history_response.status_code == 200

    export_history_response = client.get("/history/export")
    assert export_history_response.status_code == 200
    assert "text/csv" in export_history_response.content_type
