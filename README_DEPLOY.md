# NPL 2026–27 Public Live Tournament System

## What this package provides
- Public tournament portal
- Live match center
- Public player directory
- Fixtures, points, statistics and awards
- Admin login and management
- SQLite database

## Deploy
Use a Python web host that supports Flask/Gunicorn.

Build/install command:
`pip install -r requirements.txt`

Start command:
`gunicorn --bind 0.0.0.0:$PORT NPL_2026_27_Public_Live_Tournament_System:app`

Important:
- Set `NPL_SECRET_KEY` to a long random secret in the host's environment variables.
- For a real tournament with multiple admins/users, move the database to managed PostgreSQL rather than relying on local SQLite.
- Uploaded photos/logos need persistent storage on the host.
