"""SQLite storage: learner profile, plans, topics, quiz attempts."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime

DB_PATH = "learning_coach.db"


class DatabaseError(Exception):
    """Raised for any database problem, with a friendly message."""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    try:
        with closing(_connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS learner_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL, goal TEXT NOT NULL, level TEXT NOT NULL,
                    duration_days INTEGER NOT NULL, daily_minutes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL REFERENCES learner_profile(id),
                    plan_json TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL REFERENCES plans(id),
                    day INTEGER NOT NULL, title TEXT NOT NULL, objective TEXT NOT NULL,
                    est_minutes INTEGER NOT NULL, activities_json TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                );
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL REFERENCES topics(id),
                    questions_json TEXT NOT NULL, user_answers_json TEXT NOT NULL,
                    score INTEGER NOT NULL, total INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not initialise the database: {e}") from e


def save_profile(subject, goal, level, duration_days, daily_minutes):
    try:
        with closing(_connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO learner_profile (subject, goal, level, duration_days, daily_minutes, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (subject, goal, level, duration_days, daily_minutes, _now()),
            )
            return cur.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not save the learner profile: {e}") from e


def save_plan(profile_id, plan):
    """Deactivate old plans, store the new one and its topics. Returns plan id."""
    try:
        with closing(_connect()) as conn, conn:
            conn.execute("UPDATE plans SET is_active = 0")
            cur = conn.execute(
                "INSERT INTO plans (profile_id, plan_json, is_active, created_at) VALUES (?,?,1,?)",
                (profile_id, json.dumps(plan), _now()),
            )
            plan_id = cur.lastrowid
            for d in plan["days"]:
                conn.execute(
                    "INSERT INTO topics (plan_id, day, title, objective, est_minutes, activities_json)"
                    " VALUES (?,?,?,?,?,?)",
                    (plan_id, d["day"], d["topic"], d["objective"], d["est_minutes"],
                     json.dumps(d.get("activities", []))),
                )
            return plan_id
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not save the study plan: {e}") from e


def get_active_plan():
    try:
        with closing(_connect()) as conn:
            row = conn.execute(
                "SELECT p.id, p.profile_id, p.created_at, l.subject, l.goal, l.level,"
                " l.duration_days, l.daily_minutes FROM plans p"
                " JOIN learner_profile l ON l.id = p.profile_id"
                " WHERE p.is_active = 1 ORDER BY p.id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not load the study plan: {e}") from e


def get_topics(plan_id):
    try:
        with closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM topics WHERE plan_id = ? ORDER BY day", (plan_id,)
            ).fetchall()
            topics = []
            for r in rows:
                t = dict(r)
                t["activities"] = json.loads(t.pop("activities_json") or "[]")
                topics.append(t)
            return topics
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not load topics: {e}") from e


def update_topic_status(topic_id, status):
    try:
        with closing(_connect()) as conn, conn:
            conn.execute("UPDATE topics SET status = ? WHERE id = ?", (status, topic_id))
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not update topic status: {e}") from e


def save_attempt(topic_id, questions, user_answers, score, total):
    try:
        with closing(_connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO quiz_attempts (topic_id, questions_json, user_answers_json, score, total, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (topic_id, json.dumps(questions), json.dumps(user_answers), score, total, _now()),
            )
            return cur.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not save the quiz attempt: {e}") from e


def get_attempts(plan_id):
    """All attempts for a plan, newest first, with topic title."""
    try:
        with closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT a.id, a.topic_id, t.day, t.title, a.score, a.total, a.created_at"
                " FROM quiz_attempts a JOIN topics t ON t.id = a.topic_id"
                " WHERE t.plan_id = ? ORDER BY a.id DESC",
                (plan_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        raise DatabaseError(f"Could not load quiz history: {e}") from e
