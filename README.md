# Expense Tracker (Full-Stack)

A full-stack expense tracker with a Flask REST API, SQLite database, JWT authentication and a vanilla JavaScript front end.

## Features
- Register and log in (passwords hashed with Werkzeug, sessions via JWT)
- Add, edit, delete and filter expenses; per-category summary
- Each user can only access their own data
- Input validation and consistent JSON error responses
- Automated tests with pytest, run on every push through GitHub Actions

## Tech stack
Python, Flask, SQLite (2 tables, foreign key with cascade delete), PyJWT, HTML/CSS/JavaScript

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # open http://127.0.0.1:5000
```
Set `SECRET_KEY` as an environment variable before deploying.

## Run tests
```bash
pytest -v
```

## API
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /api/register | no | Create account |
| POST | /api/login | no | Returns a JWT |
| GET | /api/expenses?category= | yes | List expenses |
| POST | /api/expenses | yes | Create expense |
| PUT | /api/expenses/:id | yes | Update expense |
| DELETE | /api/expenses/:id | yes | Delete expense |
| GET | /api/summary | yes | Total and totals by category |

## Ideas to extend
- Monthly budgets and charts
- Refresh tokens and rate limiting
- Docker and deployment (Render / PythonAnywhere)
- Replace SQLite with PostgreSQL
