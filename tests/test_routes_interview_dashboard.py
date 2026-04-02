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


def test_dashboard_history_and_exports(client, login):
    login()

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200

    history_response = client.get("/history")
    assert history_response.status_code == 200

    export_history_response = client.get("/history/export")
    assert export_history_response.status_code == 200
    assert "text/csv" in export_history_response.content_type
