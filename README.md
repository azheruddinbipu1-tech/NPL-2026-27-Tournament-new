# NPL Night Football Premier League 2026/2027

Flask + PostgreSQL based tournament management system.

## Included
- Separate Public and Admin views
- Admin login with environment password
- Teams: coach, budget, logo URL
- Players: position, jersey, photo URL, purchase price
- Match schedule + venue + match story
- Live match: score, minute, goals, assists, cards, fouls, substitutions
- Event delete and score rollback
- Match finalization and player statistics
- Points table and player leaderboard
- PostgreSQL via SQLAlchemy
- Render deployment configuration

## Local
1. Copy `.env.example` to `.env` and set `SECRET_KEY`, `ADMIN_PASSWORD`, and `DATABASE_URL`.
2. `pip install -r requirements.txt`
3. `python app.py`
4. Open `http://localhost:5000`

For PostgreSQL, use a connection string such as `postgresql://USER:PASSWORD@HOST:5432/DBNAME`.

## Render
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Add environment variables `DATABASE_URL` and `ADMIN_PASSWORD`.
- `SECRET_KEY` is configured to auto-generate in `render.yaml`.

## Important
For an existing production database, schema changes should be handled with a migration tool (Alembic/Flask-Migrate) before upgrading. A fresh Render PostgreSQL database can start directly with this project.
