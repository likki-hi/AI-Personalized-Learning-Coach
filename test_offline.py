"""Offline tests (no API needed). Run: python test_offline.py"""
import os
import tempfile

import ai_service
import database as db
import learning_plan as lp
import quiz_manager as qm

db.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
db.init_db()

PROFILE = {"subject": "Python", "goal": "Basics", "level": "Beginner",
           "duration_days": 3, "daily_minutes": 45}
FAKE_PLAN = {"days": [{"day": i, "topic": f"T{i}", "objective": "obj", "est_minutes": 90,
                       "activities": ["a"]} for i in range(1, 4)]}
FAKE_QUIZ = {"questions": [{"question": f"Q{i}", "options": ["a", "b", "c", "d"],
                            "correct_index": 1, "explanation": "e"} for i in range(5)]}

# valid plan + time capping
ai_service.call_llm_json = lambda p: FAKE_PLAN
pid = lp.create_plan(PROFILE)
topics = db.get_topics(pid)
assert len(topics) == 3 and all(t["est_minutes"] == 45 for t in topics)

# invalid plan / quiz
for bad in ({}, {"days": []}, {"days": [{"topic": "", "objective": "x", "est_minutes": 5}]}):
    try:
        lp.validate_plan(bad); raise SystemExit("should fail")
    except lp.PlanError:
        pass
try:
    qm.validate_quiz({"questions": [{"question": "q", "options": ["a"], "correct_index": 9}] * 5})
    raise SystemExit("should fail")
except qm.QuizError:
    pass

# scoring + recommendations
qs = qm.validate_quiz(FAKE_QUIZ)
assert qm.score_quiz(qs, [1, 1, 1, 1, 1]) == 5
assert qm.score_quiz(qs, [0, 0, 0, 0, 0]) == 0
assert qm.recommend(2, 5)["status"] == "needs_revision"
assert qm.recommend(3, 5)["status"] == "completed"
assert qm.recommend(5, 5)["status"] == "completed"

# repeated attempts + persistence
tid = topics[0]["id"]
db.save_attempt(tid, qs, [0] * 5, 0, 5)
db.save_attempt(tid, qs, [1] * 5, 5, 5)
db.update_topic_status(tid, "needs_revision")
assert len(db.get_attempts(pid)) == 2
assert qm.weak_topics(db.get_topics(pid))[0]["id"] == tid
assert db.get_active_plan()["id"] == pid  # still there on re-read

# regeneration deactivates old plan
pid2 = lp.create_plan(PROFILE)
assert db.get_active_plan()["id"] == pid2

# API failure / missing key
ai_service.os.environ.pop("GEMINI_API_KEY", None)
import importlib; importlib.reload(ai_service)
try:
    ai_service.call_llm_json("hi"); raise SystemExit("should fail")
except ai_service.LLMError as e:
    print("Friendly error:", e)

print("ALL TESTS PASSED")
