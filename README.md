# Greetings Bot

Configurable Telegram onboarding bot for welcoming new group members and guiding them through administrator-defined questionnaires.

## Highlights

- Per-chat onboarding questions and answer choices.
- Quiz and regular poll support.
- Private or group-based questionnaire delivery.
- Resumable questionnaire sessions and timeout cleanup.
- Completion feedback and user-record persistence.
- PostgreSQL storage with SQLAlchemy and Alembic.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python run.py
```

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

## Security

Keep bot tokens, database credentials, questionnaire results, user identifiers, and runtime logs outside the repository.
