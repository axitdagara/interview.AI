import json
import re

from PyPDF2 import PdfReader
import requests


DEFAULT_ROLE_OPTIONS = [
    "Software Engineer",
    "Backend Developer",
    "Frontend Developer",
    "Data Scientist",
    "AI Engineer",
    "DevOps Engineer",
    "Product Manager",
]


class AIResumeAnalysisError(RuntimeError):
    pass


GROQ_FALLBACK_MODEL_PREFERENCE = [
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
    "moonshotai/kimi-k2-instruct",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "groq/compound-mini",
    "groq/compound",
]


def extract_text_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages)


def _extract_json_object(text):
    candidate = (text or "").strip()
    if not candidate:
        raise AIResumeAnalysisError("AI returned an empty resume analysis response.")

    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate).strip()
        candidate = re.sub(r"```$", "", candidate).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIResumeAnalysisError("Could not parse AI resume analysis JSON response.")

        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AIResumeAnalysisError("AI resume analysis JSON is invalid.") from exc

    if not isinstance(parsed, dict):
        raise AIResumeAnalysisError("AI response must be a JSON object.")

    return parsed


def _normalize_string_list(values, *, max_items=8):
    if not isinstance(values, list):
        return []

    output = []
    seen = set()
    for item in values:
        text = str(item).strip()
        key = text.casefold()
        if not text or key in seen:
            continue

        seen.add(key)
        output.append(text)
        if len(output) >= max_items:
            break

    return output


def _normalize_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0

    return round(max(0.0, min(score, 100.0)), 2)


def _build_model_candidates(api_base_url, model):
    chosen = (model or "").strip()
    if not chosen:
        return []

    candidates = [chosen]
    normalized_base = (api_base_url or "").strip().lower()

    # Groq can expose partner models with provider-prefixed names.
    if "api.groq.com" in normalized_base:
        if chosen.startswith("grok-") and "/" not in chosen:
            candidates.append(f"xai/{chosen}")
        elif chosen.startswith("xai/"):
            candidates.append(chosen.split("/", 1)[1])

    ordered = []
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)

    return ordered


def _fetch_available_model_ids(api_base_url, api_key):
    endpoint = api_base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
    except requests.RequestException:
        return []

    if response.status_code >= 400:
        return []

    try:
        payload = response.json()
        items = payload.get("data", [])
    except (TypeError, ValueError, AttributeError):
        return []

    model_ids = []
    for item in items:
        model_id = str(item.get("id", "")).strip()
        if model_id:
            model_ids.append(model_id)

    return model_ids


def _pick_best_groq_fallback_model(model_ids):
    if not model_ids:
        return None

    available = set(model_ids)
    for preferred in GROQ_FALLBACK_MODEL_PREFERENCE:
        if preferred in available:
            return preferred

    for model_id in model_ids:
        lowered = model_id.lower()
        if "whisper" in lowered or "prompt-guard" in lowered or "safeguard" in lowered or "orpheus" in lowered:
            continue
        return model_id

    return None


def analyze_resume_with_ai(*, api_key, api_base_url, model, resume_text, role, job_description=""):
    if not (api_key or "").strip():
        raise AIResumeAnalysisError("API key is missing. Configure GROQ_API_KEY (or GROK_API_KEY).")

    cleaned_text = (resume_text or "").strip()
    if not cleaned_text:
        raise AIResumeAnalysisError("Resume text is empty. Please upload a text-based PDF.")

    endpoint = api_base_url.rstrip("/") + "/chat/completions"
    model_candidates = _build_model_candidates(api_base_url, model)
    normalized_base = (api_base_url or "").strip().lower()

    if "api.groq.com" in normalized_base:
        available_model_ids = _fetch_available_model_ids(api_base_url, api_key)
        if available_model_ids:
            available = set(available_model_ids)
            if not any(candidate in available for candidate in model_candidates):
                fallback_model = _pick_best_groq_fallback_model(available_model_ids)
                if fallback_model and fallback_model not in model_candidates:
                    model_candidates.append(fallback_model)

    if not model_candidates:
        raise AIResumeAnalysisError("Model name is missing. Configure GROQ_MODEL.")

    trimmed_resume_text = cleaned_text[:12000]
    trimmed_job_description = (job_description or "").strip()[:6000]

    system_prompt = (
        "You are an expert technical recruiter and resume reviewer. "
        "Return only valid JSON and no extra text."
    )
    user_prompt = (
        "Analyze the following resume for the selected role. "
        "Return STRICT JSON object with keys: "
        "overall_score (number 0-100), role_fit (string), experience_level (string), summary (string), "
        "detected_skills (array of strings), strengths (array of strings), "
        "improvement_areas (array of strings), recommended_skills (array of strings), ats_tips (array of strings), "
        "ats_accuracy_score (number 0-100), "
        "jd_alignment_score (number 0-100), jd_gap_summary (string), "
        "jd_recommendations (array of strings), recruiter_highlights (array of strings). "
        "Do not include markdown or explanation outside JSON. "
        f"Target role: {role}. "
        f"Job description (optional): {trimmed_job_description or 'Not provided'}. "
        f"Resume text: {trimmed_resume_text}"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = None
    last_error_detail = ""
    attempted_models = []

    for idx, model_name in enumerate(model_candidates):
        attempted_models.append(model_name)
        payload = {
            "model": model_name,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            raise AIResumeAnalysisError(f"Could not reach AI provider: {exc}") from exc

        if response.status_code < 400:
            break

        detail = response.text[:400]
        last_error_detail = detail
        lowered_detail = detail.lower()
        is_model_not_found = (
            response.status_code in {400, 404}
            and ("model not found" in lowered_detail or "model_not_found" in lowered_detail)
        )

        if is_model_not_found and idx < (len(model_candidates) - 1):
            continue

        if is_model_not_found and api_key.startswith("gsk_") and "api.x.ai" in endpoint:
            raise AIResumeAnalysisError(
                "Model lookup failed on xAI endpoint with a Groq-style API key. "
                "Set GROQ_API_BASE_URL=https://api.groq.com/openai/v1."
            )

        if is_model_not_found and "api.groq.com" in normalized_base:
            available_model_ids = _fetch_available_model_ids(api_base_url, api_key)
            fallback_model = _pick_best_groq_fallback_model(available_model_ids)
            if fallback_model and fallback_model not in attempted_models:
                model_candidates.append(fallback_model)
                continue

        raise AIResumeAnalysisError(
            f"AI provider error ({response.status_code}) using model '{model_name}': {detail}"
        )
    else:
        attempted = ", ".join(attempted_models)
        raise AIResumeAnalysisError(
            f"Could not analyze resume. Tried models: {attempted}. Last error: {last_error_detail}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIResumeAnalysisError("Unexpected AI provider response format.") from exc

    parsed = _extract_json_object(content)

    summary = str(parsed.get("summary", "")).strip()
    role_fit = str(parsed.get("role_fit", "Unknown")).strip() or "Unknown"
    experience_level = str(parsed.get("experience_level", "Unknown")).strip() or "Unknown"

    return {
        "overall_score": _normalize_score(parsed.get("overall_score", 0.0)),
        "role_fit": role_fit,
        "experience_level": experience_level,
        "summary": summary,
        "detected_skills": _normalize_string_list(parsed.get("detected_skills", []), max_items=15),
        "strengths": _normalize_string_list(parsed.get("strengths", []), max_items=8),
        "improvement_areas": _normalize_string_list(parsed.get("improvement_areas", []), max_items=8),
        "recommended_skills": _normalize_string_list(parsed.get("recommended_skills", []), max_items=10),
        "ats_tips": _normalize_string_list(parsed.get("ats_tips", []), max_items=8),
        "ats_accuracy_score": _normalize_score(
            parsed.get("ats_accuracy_score", parsed.get("overall_score", 0.0))
        ),
        "jd_alignment_score": _normalize_score(
            parsed.get(
                "jd_alignment_score",
                parsed.get("overall_score", 0.0) if not trimmed_job_description else 0.0,
            )
        ),
        "jd_gap_summary": str(
            parsed.get(
                "jd_gap_summary",
                "Job description not provided. Add one to get a targeted hiring-gap summary."
                if not trimmed_job_description
                else "",
            )
        ).strip(),
        "jd_recommendations": _normalize_string_list(parsed.get("jd_recommendations", []), max_items=8),
        "recruiter_highlights": _normalize_string_list(parsed.get("recruiter_highlights", []), max_items=8),
    }
