# AI Personalized Learning Coach

A Streamlit web app that builds a personalised, day-wise study plan with a Gemini LLM,
generates topic quizzes, scores them in Python, flags weak topics and saves everything in SQLite.

## Features
- Learner setup: subject, goal, level, duration, daily study time
- LLM-generated structured study plan (validated before use), regenerate anytime
- 5-question multiple-choice quiz per topic
- Scoring done in Python from the answer key (the LLM never scores)
- Feedback and explanations, weak-topic detection, next-step recommendations
- Progress dashboard: completed/pending topics, recent scores, score trend, next action
- Error handling for empty inputs, invalid AI output, API failures and database errors

## Tech stack
Python, Streamlit, Google Gemini API, SQLite, python-dotenv, pandas, Git/GitHub

## Setup
```bash
git clone <your-repo-url>
cd ai-personalized-learning-coach
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env
# open .env and paste your Gemini API key
streamlit run app.py
```

## Folder structure
```
app.py             Streamlit UI (5 pages)
ai_service.py      Gemini call, JSON mode, retries
learning_plan.py   Plan prompt, validation, creation
quiz_manager.py    Quiz prompt, validation, scoring, recommendations
database.py        SQLite tables and queries
test_offline.py    Tests that run without an API key
sample_data/       Example plan (not used by the app)
```

## Database
`learner_profile` -> `plans` -> `topics` -> `quiz_attempts` (linked by foreign keys).
Topic status: pending / completed / needs_revision.

## Recommendation rules
Below 60% -> needs revision; 60-80% -> completed, light practice; above 80% -> move forward.

## Testing
`python test_offline.py` checks validation, scoring, recommendations, persistence,
repeated attempts and the missing-key error. UI cases were tested manually.

## Limitations
- A 5-question quiz is a weak signal of mastery
- LLM questions or answer keys may occasionally be wrong
- No user login; one shared local database
- Needs internet and a valid API key

## Author : Likitha Kalal
