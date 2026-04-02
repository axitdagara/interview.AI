from interview_simulator.services.evaluator import (
    build_feedback,
    evaluate_answer,
    extract_keywords,
    normalize_text,
)


def test_normalize_text_strips_noise():
    assert normalize_text("Python!!! 3.10 + Flask") == "python flask"


def test_extract_keywords_returns_ranked_tokens():
    keywords = extract_keywords("Flask Flask routing blueprint session request response", limit=3)
    assert len(keywords) == 3
    assert keywords[0] == "flask"


def test_build_feedback_includes_missing_keywords_when_present():
    feedback = build_feedback(65, ["api", "token"])
    assert "Good answer" in feedback
    assert "api, token" in feedback


def test_evaluate_answer_empty_response():
    result = evaluate_answer("", "Python supports classes and functions")
    assert result["score"] == 0.0
    assert "No answer submitted" in result["feedback"]
    assert len(result["missing_keywords"]) > 0


def test_evaluate_answer_non_empty_response_has_score():
    result = evaluate_answer(
        "Python classes and functions help structure code",
        "Python supports classes and functions",
    )
    assert 0.0 <= result["score"] <= 100.0
    assert isinstance(result["feedback"], str)
    assert isinstance(result["missing_keywords"], list)
