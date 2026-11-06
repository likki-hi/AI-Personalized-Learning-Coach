"""Study plan creation and validation."""
import ai_service
import database as db


class PlanError(Exception):
    """Raised when the AI plan is unusable."""


def build_plan_prompt(p):
    return f"""You are a study-planning assistant.
Create a day-wise study plan.
Subject: {p['subject']}
Goal: {p['goal']}
Current level: {p['level']}
Target duration: {p['duration_days']} days
Daily study time: {p['daily_minutes']} minutes

Rules:
- Return exactly {p['duration_days']} days, one entry per day.
- Each day's est_minutes must be at most {p['daily_minutes']}.
- Suit the {p['level']} level. Put revision/quiz practice near the end.
- Return ONLY JSON in exactly this shape:
{{"days":[{{"day":1,"topic":"...","objective":"...","est_minutes":45,"activities":["...","..."]}}]}}"""


def validate_plan(data, profile=None):
    """Check structure; return a cleaned plan. Raises PlanError if unusable."""
    days = data.get("days") if isinstance(data, dict) else None
    if not isinstance(days, list) or not days:
        raise PlanError("The AI plan has no days.")
    if profile:
        days = days[: int(profile["duration_days"])]
    clean = []
    for i, d in enumerate(days, 1):
        if not isinstance(d, dict):
            raise PlanError(f"Day {i} is not valid.")
        topic = str(d.get("topic", "")).strip()
        objective = str(d.get("objective", "")).strip()
        if not topic or not objective:
            raise PlanError(f"Day {i} is missing a topic or objective.")
        try:
            minutes = int(d.get("est_minutes"))
        except (TypeError, ValueError):
            raise PlanError(f"Day {i} has no valid estimated time.")
        if minutes <= 0:
            raise PlanError(f"Day {i} has an invalid estimated time.")
        if profile:
            minutes = min(minutes, int(profile["daily_minutes"]))
        acts = d.get("activities") or []
        if not isinstance(acts, list):
            acts = [str(acts)]
        clean.append({
            "day": i, "topic": topic, "objective": objective,
            "est_minutes": minutes, "activities": [str(a) for a in acts],
        })
    return {"days": clean}


def create_plan(profile, attempts=2):
    """Ask the LLM, validate, save profile + plan. Returns plan id."""
    prompt = build_plan_prompt(profile)
    last = None
    for _ in range(attempts):
        data = ai_service.call_llm_json(prompt)  # may raise LLMError
        try:
            plan = validate_plan(data, profile)
            break
        except PlanError as e:
            last = e
    else:
        raise PlanError(f"The AI gave an unusable plan. {last}")
    profile_id = db.save_profile(
        profile["subject"], profile["goal"], profile["level"],
        profile["duration_days"], profile["daily_minutes"],
    )
    return db.save_plan(profile_id, plan)
