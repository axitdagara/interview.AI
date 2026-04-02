import io

from interview_simulator.services.resume_parser import (
    AIResumeAnalysisError,
    _extract_json_object,
    analyze_resume_with_ai,
    extract_text_from_pdf,
)


class DummyResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_extract_json_object_from_fenced_block():
    result = _extract_json_object("```json\n{\"overall_score\": 81}\n```")
    assert result["overall_score"] == 81


def test_extract_text_from_pdf_reads_pages(monkeypatch):
    class DummyPage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class DummyReader:
        def __init__(self, _stream):
            self.pages = [DummyPage("Hello"), DummyPage("World")]

    monkeypatch.setattr("interview_simulator.services.resume_parser.PdfReader", DummyReader)

    output = extract_text_from_pdf(io.BytesIO(b"pdf-bytes"))
    assert output == "Hello\nWorld"


def test_analyze_resume_with_ai_success(monkeypatch):
    def fake_get(*args, **kwargs):
        return DummyResponse(
            200,
            payload={"data": [{"id": "llama-3.3-70b-versatile"}]},
            text="ok",
        )

    def fake_post(*args, **kwargs):
        return DummyResponse(
            200,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"overall_score":88,"role_fit":"High","experience_level":"Mid",'
                                '"summary":"Good profile","detected_skills":["Python","Flask"],'
                                '"strengths":["APIs"],"improvement_areas":["Testing"],'
                                '"recommended_skills":["Docker"],"ats_tips":["Use keywords"],'
                                '"jd_alignment_score":84,"jd_gap_summary":"Minor gaps",'
                                '"jd_recommendations":["Add CI"],"recruiter_highlights":["Impact"]}'
                            )
                        }
                    }
                ]
            },
            text="ok",
        )

    monkeypatch.setattr("interview_simulator.services.resume_parser.requests.get", fake_get)
    monkeypatch.setattr("interview_simulator.services.resume_parser.requests.post", fake_post)

    result = analyze_resume_with_ai(
        api_key="gsk_dummy",
        api_base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        resume_text="Python Flask SQL",
        role="Backend Developer",
        job_description="Build APIs",
    )

    assert result["overall_score"] == 88.0
    assert result["role_fit"] == "High"
    assert "Python" in result["detected_skills"]


def test_analyze_resume_with_ai_raises_on_empty_resume():
    try:
        analyze_resume_with_ai(
            api_key="gsk_dummy",
            api_base_url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            resume_text="",
            role="Backend Developer",
        )
    except AIResumeAnalysisError as exc:
        assert "Resume text is empty" in str(exc)
    else:
        raise AssertionError("Expected AIResumeAnalysisError")
