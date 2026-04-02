from interview_simulator.services.ai_question_generator import (
    AIQuestionGenerationError,
    _build_model_candidates,
    _extract_json_block,
    generate_ai_mcq_questions,
)


class DummyResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_build_model_candidates_adds_groq_alias():
    candidates = _build_model_candidates("https://api.groq.com/openai/v1", "grok-2-latest")
    assert candidates == ["grok-2-latest", "xai/grok-2-latest"]


def test_extract_json_block_from_markdown_fence():
    parsed = _extract_json_block(
        "```json\n[{\"prompt\":\"Q\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"correct_option\":\"A\",\"ideal_answer\":\"X\"}]\n```"
    )
    assert isinstance(parsed, list)
    assert parsed[0]["prompt"] == "Q"


def test_generate_ai_mcq_questions_falls_back_to_second_model(monkeypatch):
    post_calls = {"count": 0}

    def fake_get(*args, **kwargs):
        return DummyResponse(
            200,
            payload={"data": [{"id": "llama-3.3-70b-versatile"}]},
            text="ok",
        )

    def fake_post(*args, **kwargs):
        post_calls["count"] += 1
        model_name = kwargs["json"]["model"]
        if model_name == "bad-model":
            return DummyResponse(404, text="model_not_found")
        return DummyResponse(
            200,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '[{"prompt":"Q1","options":["A","B","C","D"],'
                                '"correct_option":"A","ideal_answer":"Because"}]'
                            )
                        }
                    }
                ]
            },
            text="ok",
        )

    monkeypatch.setattr("interview_simulator.services.ai_question_generator.requests.get", fake_get)
    monkeypatch.setattr("interview_simulator.services.ai_question_generator.requests.post", fake_post)

    result = generate_ai_mcq_questions(
        api_key="gsk_dummy",
        api_base_url="https://api.groq.com/openai/v1",
        model="bad-model",
        category="Technical",
        difficulty_label="Easy",
        count=1,
        role="Software Engineer",
        focus_topics="Python",
    )

    assert len(result) == 1
    assert result[0]["difficulty"] == 1
    assert post_calls["count"] >= 2


def test_generate_ai_mcq_questions_rejects_missing_api_key():
    try:
        generate_ai_mcq_questions(
            api_key="",
            api_base_url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            category="Technical",
            difficulty_label="Easy",
            count=1,
            role="Software Engineer",
            focus_topics="Python",
        )
    except AIQuestionGenerationError as exc:
        assert "API key is missing" in str(exc)
    else:
        raise AssertionError("Expected AIQuestionGenerationError")
