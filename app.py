"""AI Personalized Learning Coach - Streamlit app."""
import uuid

import pandas as pd
import streamlit as st

import database as db
import learning_plan as lp
import quiz_manager as qm
from ai_service import LLMError

st.set_page_config(page_title="AI Personalized Learning Coach", page_icon="🎓", layout="wide")

try:
    db.init_db()
except db.DatabaseError as e:
    st.error(str(e))
    st.stop()

ERRORS = (LLMError, lp.PlanError, qm.QuizError, db.DatabaseError)


def make_plan(profile):
    try:
        with st.spinner("Generating your study plan..."):
            lp.create_plan(profile)
        st.session_state.pop("quiz", None)
        st.session_state.pop("quiz_result", None)
        st.success("Plan created! Open 'Study Plan' in the sidebar.")
    except ERRORS as e:
        st.error(f"{e} Click the button again to retry.")


# ---------------- Pages ----------------
def home_page():
    st.title("🎓 AI Personalized Learning Coach")
    st.write(
        "Tell the coach what you want to learn and how much time you have. "
        "It builds a day-wise study plan, quizzes you on each topic, checks your "
        "answers, flags topics that need revision and saves your progress."
    )
    st.markdown(
        "1. **Learner Setup** - enter subject, goal, level and time\n"
        "2. **Study Plan** - view your plan\n"
        "3. **Practice Quiz** - take a 5-question quiz\n"
        "4. **Progress Dashboard** - see scores and next steps"
    )


def setup_page():
    st.header("Learner Setup")
    with st.form("setup"):
        subject = st.text_input("Subject", placeholder="e.g. Python")
        goal = st.text_input("Goal", placeholder="e.g. Learn Python fundamentals")
        level = st.selectbox("Current level", ["Beginner", "Intermediate", "Advanced"])
        days = st.number_input("Target duration (days)", min_value=1, max_value=60, value=7)
        minutes = st.number_input("Daily study time (minutes)", min_value=10, max_value=480,
                                  value=45, step=5)
        submitted = st.form_submit_button("Generate study plan")
    if submitted:
        if not subject.strip() or not goal.strip():
            st.error("Please fill in both the subject and the goal.")
            return
        make_plan({"subject": subject.strip(), "goal": goal.strip(), "level": level,
                   "duration_days": int(days), "daily_minutes": int(minutes)})


def plan_page():
    st.header("Study Plan")
    try:
        plan = db.get_active_plan()
        if not plan:
            st.info("No plan yet. Create one on the Learner Setup page.")
            return
        topics = db.get_topics(plan["id"])
    except db.DatabaseError as e:
        st.error(str(e))
        return
    st.caption(f"{plan['subject']} | Goal: {plan['goal']} | Level: {plan['level']} | "
               f"{plan['duration_days']} days x {plan['daily_minutes']} min")
    df = pd.DataFrame([{"Day": t["day"], "Topic": t["title"], "Objective": t["objective"],
                        "Minutes": t["est_minutes"], "Status": t["status"]} for t in topics])
    st.dataframe(df, use_container_width=True, hide_index=True)
    for t in topics:
        with st.expander(f"Day {t['day']}: {t['title']} - activities"):
            for a in t["activities"]:
                st.write(f"- {a}")
    st.divider()
    st.write("Goal or schedule changed? Edit it on **Learner Setup**, or regenerate with the same settings:")
    if st.button("Regenerate plan (same settings)"):
        make_plan({k: plan[k] for k in ("subject", "goal", "level", "duration_days", "daily_minutes")})


def show_result(result):
    st.subheader(f"Result: {result['score']} / {result['total']}")
    st.info(result["message"])
    for i, q in enumerate(result["questions"]):
        chosen = result["answers"][i]
        ok = chosen == q["correct_index"]
        box = st.success if ok else st.error
        box(f"Q{i+1}. {q['question']}\n\n"
            f"Your answer: {q['options'][chosen]}\n\n"
            f"Correct answer: {q['options'][q['correct_index']]}\n\n"
            f"Why: {q['explanation']}")


def quiz_page():
    st.header("Practice Quiz")
    try:
        plan = db.get_active_plan()
        if not plan:
            st.info("Create a study plan first.")
            return
        topics = db.get_topics(plan["id"])
    except db.DatabaseError as e:
        st.error(str(e))
        return

    labels = {t["id"]: f"Day {t['day']}: {t['title']} ({t['status']})" for t in topics}
    topic_id = st.selectbox("Choose a topic", list(labels), format_func=labels.get)
    if st.button("Generate quiz"):
        topic = next(t for t in topics if t["id"] == topic_id)
        try:
            with st.spinner("Generating quiz..."):
                questions = qm.generate_quiz(topic["title"], topic["objective"], plan["level"])
            st.session_state.quiz = {"uid": uuid.uuid4().hex, "topic_id": topic_id,
                                     "title": topic["title"], "questions": questions}
            st.session_state.pop("quiz_result", None)
        except ERRORS as e:
            st.error(f"{e} Click 'Generate quiz' again to retry.")

    quiz = st.session_state.get("quiz")
    if quiz:
        st.subheader(f"Quiz: {quiz['title']}")
        with st.form(f"form_{quiz['uid']}"):
            answers = []
            for i, q in enumerate(quiz["questions"]):
                st.markdown(f"**Q{i+1}. {q['question']}**")
                a = st.radio("Choose one", range(4), index=None, key=f"{quiz['uid']}_{i}",
                             format_func=lambda j, o=q["options"]: o[j],
                             label_visibility="collapsed")
                answers.append(a)
            submitted = st.form_submit_button("Submit answers")
        if submitted:
            if None in answers:
                st.warning("Please answer every question before submitting.")
            else:
                score = qm.score_quiz(quiz["questions"], answers)
                total = len(quiz["questions"])
                rec = qm.recommend(score, total)
                try:
                    db.save_attempt(quiz["topic_id"], quiz["questions"], answers, score, total)
                    db.update_topic_status(quiz["topic_id"], rec["status"])
                except db.DatabaseError as e:
                    st.error(str(e))
                    return
                st.session_state.quiz_result = {
                    "score": score, "total": total, "message": rec["message"],
                    "questions": quiz["questions"], "answers": answers}
                st.session_state.quiz = None
                st.rerun()
    elif st.session_state.get("quiz_result"):
        show_result(st.session_state.quiz_result)


def dashboard_page():
    st.header("Progress Dashboard")
    try:
        plan = db.get_active_plan()
        if not plan:
            st.info("No saved plan yet.")
            return
        topics = db.get_topics(plan["id"])
        attempts = db.get_attempts(plan["id"])
    except db.DatabaseError as e:
        st.error(str(e))
        return

    done = sum(t["status"] == "completed" for t in topics)
    weak = qm.weak_topics(topics)
    pending = sum(t["status"] == "pending" for t in topics)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Completed", done)
    c2.metric("Pending", pending)
    c3.metric("Needs revision", len(weak))
    c4.metric("Quiz attempts", len(attempts))
    st.progress(done / len(topics) if topics else 0.0)

    st.success(f"**Next action:** {qm.next_action(topics)}")
    if weak:
        st.warning("Topics flagged for revision: " + ", ".join(t["title"] for t in weak))

    st.subheader("Recent scores")
    if attempts:
        df = pd.DataFrame(attempts)
        df["Percent"] = (df["score"] / df["total"] * 100).round(0)
        st.dataframe(
            df.rename(columns={"day": "Day", "title": "Topic", "score": "Score",
                               "total": "Out of", "created_at": "Date"})
              [["Date", "Day", "Topic", "Score", "Out of", "Percent"]].head(10),
            use_container_width=True, hide_index=True)
        st.subheader("Score trend")
        st.line_chart(df.sort_values("id").set_index("created_at")["Percent"])
    else:
        st.info("No quiz attempts yet.")

    st.subheader("Topic status")
    st.dataframe(pd.DataFrame([{"Day": t["day"], "Topic": t["title"], "Status": t["status"]}
                               for t in topics]), use_container_width=True, hide_index=True)


PAGES = {"Home": home_page, "Learner Setup": setup_page, "Study Plan": plan_page,
         "Practice Quiz": quiz_page, "Progress Dashboard": dashboard_page}
choice = st.sidebar.radio("Navigate", list(PAGES))
PAGES[choice]()
