"""Quiz generation, Python-based scoring, and recommendations."""
import ai_service
import database as db

PASS_LOW = 0.6   # below this -> needs revision
PASS_HIGH = 0.8  # above this -> move forward


class QuizError(Exception):
    """Raised when the AI quiz is unusable."""


def build_quiz_prompt(topic, objective, level):
    return f"""Create a practice quiz.
Topic: {topic}
Objective: {objective}
Learner level: {level}

Rules:
- Exactly 5 multiple-choice questions, each with exactly 4 options (no "A)" prefixes).
- correct_index is the 0-based index (0-3) of the right option.
- Explanations should suit a {level} learner. Do not calculate any score.
- Return ONLY JSON in exactly this shape:
{{"questions":[{{"question":"...","options":["...","...","...","..."],"correct_index":1,"explanation":"..."}}]}}"""


def validate_quiz(data):
    qs = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(qs, list) or len(qs) < 5:
        raise QuizError("The AI quiz has fewer than 5 questions.")
    clean = []
    for i, q in enumerate(qs[:5], 1):
        if not isinstance(q, dict):
            raise QuizError(f"Question {i} is not valid.")
        text = str(q.get("question", "")).strip()
        options = q.get("options")
        if not text or not isinstance(options, list) or len(options) != 4:
            raise QuizError(f"Question {i} needs text and exactly 4 options.")
        try:
            idx = int(q.get("correct_index"))
        except (TypeError, ValueError):
            raise QuizError(f"Question {i} has no valid answer key.")
        if not 0 <= idx <= 3:
            raise QuizError(f"Question {i} answer key is out of range.")
        clean.append({
            "question": text,
            "options": [str(o) for o in options],
            "correct_index": idx,
            "explanation": str(q.get("explanation", "")).strip(),
        })
    return clean


def generate_quiz(topic, objective, level, attempts=2):
    prompt = build_quiz_prompt(topic, objective, level)
    last = None
    for _ in range(attempts):
        data = ai_service.call_llm_json(prompt)  # may raise LLMError
        try:
            return validate_quiz(data)
        except QuizError as e:
            last = e
    raise QuizError(f"The AI gave an unusable quiz. {last}")


def score_quiz(questions, answers):
    """Pure Python scoring from the answer key (the LLM never scores)."""
    return sum(1 for q, a in zip(questions, answers) if a == q["correct_index"])


def recommend(score, total):
    pct = score / total if total else 0
    if pct < PASS_LOW:
        return {"status": "needs_revision",
                "message": "Performance suggests this topic needs more practice. "
                           "Revise it and retake the quiz."}
    if pct <= PASS_HIGH:
        return {"status": "completed",
                "message": "Performance suggests a fair understanding. "
                           "Do some light practice, then continue."}
    return {"status": "completed",
            "message": "Strong result on this short quiz. Move to the next topic "
                       "or try harder practice. One quiz is only a small sample."}


def weak_topics(topics):
    return [t for t in topics if t["status"] == "needs_revision"]


def next_action(topics):
    weak = weak_topics(topics)
    if weak:
        return f"Revise '{weak[0]['title']}' and retake its quiz."
    pending = [t for t in topics if t["status"] == "pending"]
    if pending:
        return f"Continue with Day {pending[0]['day']}: {pending[0]['title']}."
    return "All topics attempted. Review your scores or create a new plan."
