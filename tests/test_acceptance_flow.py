import io

from interview_simulator.models import InterviewSession, Question


def test_acceptance_end_to_end_flow(client, app, monkeypatch):
    register_response = client.post(
        "/register",
        data={
            "name": "Acceptance User",
            "email": "accept@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        },
        follow_redirects=True,
    )
    assert register_response.status_code == 200

    setup_response = client.post(
        "/interview/setup",
        data={
            "question_source": "bank",
            "category": "Technical",
            "difficulty_level": "Easy",
            "question_count": "2",
            "timer_seconds": "90",
            "practice_mode": "balanced",
        },
        follow_redirects=False,
    )
    assert setup_response.status_code == 302

    with client.session_transaction() as session_data:
        state = session_data["interview_state"]

    with app.app_context():
        first_question = Question.query.get(state["question_ids"][0])
        selected_option = first_question.correct_option

    submit_response = client.post(
        "/interview/submit",
        data={"selected_option": selected_option, "time_taken": "15"},
        follow_redirects=False,
    )
    assert submit_response.status_code == 302

    result_page = client.get(submit_response.headers["Location"])
    assert result_page.status_code == 200

    dashboard_page = client.get("/dashboard")
    assert dashboard_page.status_code == 200

    history_page = client.get("/history")
    assert history_page.status_code == 200

    export_page = client.get("/history/export")
    assert export_page.status_code == 200
    assert "text/csv" in export_page.content_type

    def fake_extract_text(_file_obj):
        return "Python Flask SQL APIs"

    def fake_analyze_resume(**kwargs):
        return {
            "overall_score": 82.0,
            "role_fit": "High",
            "experience_level": "Mid",
            "summary": "Strong backend profile",
            "detected_skills": ["Python", "Flask"],
            "strengths": ["API design"],
            "improvement_areas": ["Testing depth"],
            "recommended_skills": ["Docker"],
            "ats_tips": ["Use role keywords"],
            "jd_alignment_score": 80.0,
            "jd_gap_summary": "Add cloud projects",
            "jd_recommendations": ["Highlight deployments"],
            "recruiter_highlights": ["Clear project impact"],
        }

    monkeypatch.setattr("interview_simulator.routes.resume.extract_text_from_pdf", fake_extract_text)
    monkeypatch.setattr("interview_simulator.routes.resume.analyze_resume_with_ai", fake_analyze_resume)

    resume_response = client.post(
        "/resume/analyzer",
        data={
            "role": "Backend Developer",
            "job_description": "Build APIs",
            "resume": (io.BytesIO(b"%PDF-1.4 fake"), "resume.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resume_response.status_code == 200
    assert b"Resume analyzed successfully" in resume_response.data

    with app.app_context():
        assert InterviewSession.query.count() >= 1
