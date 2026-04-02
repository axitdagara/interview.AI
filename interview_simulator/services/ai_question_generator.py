import json
import random
import re
from typing import List

import requests


DIFFICULTY_TO_VALUE = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
}

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


class AIQuestionGenerationError(RuntimeError):
    pass


def _build_model_candidates(api_base_url: str, model: str):
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
    for entry in candidates:
        if entry and entry not in seen:
            seen.add(entry)
            ordered.append(entry)

    return ordered


def _fetch_available_model_ids(api_base_url: str, api_key: str):
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


def _extract_json_block(text: str):
    candidate = (text or "").strip()
    if not candidate:
        raise AIQuestionGenerationError("AI returned an empty response.")

    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate).strip()
        candidate = re.sub(r"```$", "", candidate).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[\s*\{.*\}\s*\]", candidate, flags=re.DOTALL)
    if not match:
        raise AIQuestionGenerationError("Could not parse AI response as JSON list.")

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AIQuestionGenerationError("AI response JSON is invalid.") from exc


def _normalize_item(raw_item, category, difficulty_label):
    if not isinstance(raw_item, dict):
        return None

    prompt = str(raw_item.get("prompt", "")).strip()
    ideal_answer = str(raw_item.get("ideal_answer", "")).strip()
    correct_option = str(raw_item.get("correct_option", "")).strip()

    options = raw_item.get("options", [])
    if not isinstance(options, list):
        options = []

    normalized_options = []
    for option in options:
        text = str(option).strip()
        if text:
            normalized_options.append(text)

    deduped_options = []
    seen = set()
    for option in normalized_options:
        key = option.casefold()
        if key not in seen:
            seen.add(key)
            deduped_options.append(option)

    if correct_option and all(correct_option.casefold() != item.casefold() for item in deduped_options):
        deduped_options.insert(0, correct_option)

    if len(deduped_options) < 4 or not prompt or not ideal_answer or not correct_option:
        return None

    deduped_options = deduped_options[:4]
    random.shuffle(deduped_options)

    if all(correct_option.casefold() != item.casefold() for item in deduped_options):
        return None

    canonical_correct = next(item for item in deduped_options if item.casefold() == correct_option.casefold())

    return {
        "category": category,
        "difficulty_label": difficulty_label,
        "difficulty": DIFFICULTY_TO_VALUE[difficulty_label],
        "prompt": prompt,
        "ideal_answer": ideal_answer,
        "options": deduped_options,
        "correct_option": canonical_correct,
    }


def generate_ai_mcq_questions(
    *,
    api_key: str,
    api_base_url: str,
    model: str,
    category: str,
    difficulty_label: str,
    count: int,
    role: str,
    focus_topics: str,
):
    if not api_key:
        raise AIQuestionGenerationError("API key is missing. Configure GROQ_API_KEY (or GROK_API_KEY).")

    if difficulty_label not in DIFFICULTY_TO_VALUE:
        raise AIQuestionGenerationError("Invalid difficulty value.")

    count = max(1, min(int(count), 20))
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
        raise AIQuestionGenerationError("Model name is missing. Configure GROQ_MODEL.")

    system_prompt = (
        "You are an expert interview designer. Return only valid JSON. "
        "Generate practical interview MCQ questions."
    )

    user_prompt = (
        f"Generate {count} unique interview MCQ questions for category '{category}' and difficulty '{difficulty_label}'. "
        f"Role context: {role or 'General'}; Focus topics: {focus_topics or 'General interview preparation'}. "
        "Return STRICT JSON array with this schema per item: "
        "{\"prompt\": string, \"options\": [string, string, string, string], \"correct_option\": string, \"ideal_answer\": string}. "
        "Rules: exactly 4 options; correct_option must match one option exactly; no markdown; no explanation text outside JSON."
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
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            raise AIQuestionGenerationError(f"Could not reach AI provider: {exc}") from exc

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
            raise AIQuestionGenerationError(
                "Model lookup failed on xAI endpoint with a Groq-style API key. "
                "Set GROQ_API_BASE_URL=https://api.groq.com/openai/v1."
            )

        if is_model_not_found and "api.groq.com" in normalized_base:
            available_model_ids = _fetch_available_model_ids(api_base_url, api_key)
            fallback_model = _pick_best_groq_fallback_model(available_model_ids)
            if fallback_model and fallback_model not in attempted_models:
                model_candidates.append(fallback_model)
                continue

        raise AIQuestionGenerationError(
            f"AI provider error ({response.status_code}) using model '{model_name}': {detail}"
        )
    else:
        attempted = ", ".join(attempted_models)
        raise AIQuestionGenerationError(
            f"Could not generate questions. Tried models: {attempted}. Last error: {last_error_detail}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIQuestionGenerationError("Unexpected AI provider response format.") from exc

    parsed = _extract_json_block(content)
    if not isinstance(parsed, list):
        raise AIQuestionGenerationError("AI response must be a JSON array.")

    normalized: List[dict] = []
    for item in parsed:
        normalized_item = _normalize_item(item, category, difficulty_label)
        if normalized_item:
            normalized.append(normalized_item)

    unique_questions = []
    seen_prompts = set()
    for item in normalized:
        key = item["prompt"].casefold()
        if key not in seen_prompts:
            seen_prompts.add(key)
            unique_questions.append(item)

    if not unique_questions:
        raise AIQuestionGenerationError("AI returned no valid questions after validation.")

    return unique_questions[:count]
