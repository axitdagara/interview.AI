import re
from collections import Counter

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#-]*")


def normalize_text(text):
    tokens = TOKEN_PATTERN.findall((text or "").lower())
    return " ".join(tokens)


def extract_keywords(text, limit=10):
    tokens = TOKEN_PATTERN.findall((text or "").lower())
    filtered = [token for token in tokens if len(token) > 3 and token not in ENGLISH_STOP_WORDS]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(limit)]


def build_feedback(score, missing_keywords):
    if score >= 80:
        tone = "Excellent answer. You explained the concept clearly."
    elif score >= 60:
        tone = "Good answer with solid direction. Add a little more depth."
    elif score >= 40:
        tone = "Average answer. You touched the topic but missed some details."
    else:
        tone = "Needs improvement. The response is too far from the expected points."

    if missing_keywords:
        focus = ", ".join(missing_keywords[:5])
        return f"{tone} Try including these keywords: {focus}."

    return tone


def evaluate_answer(user_answer, ideal_answer):
    user_clean = normalize_text(user_answer)
    ideal_clean = normalize_text(ideal_answer)

    if not user_clean:
        return {
            "score": 0.0,
            "feedback": "No answer submitted. Provide a clear and complete response.",
            "missing_keywords": extract_keywords(ideal_answer, limit=6),
        }

    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        matrix = vectorizer.fit_transform([ideal_clean, user_clean])
        similarity = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    except ValueError:
        similarity = 0.0

    score = round(similarity * 100, 2)

    ideal_keywords = extract_keywords(ideal_answer, limit=10)
    answer_terms = set(TOKEN_PATTERN.findall(user_answer.lower()))
    missing_keywords = [word for word in ideal_keywords if word not in answer_terms]

    return {
        "score": score,
        "feedback": build_feedback(score, missing_keywords),
        "missing_keywords": missing_keywords,
    }
