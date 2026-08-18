# Deployment

1. Create a virtual environment locally.
2. Install `requirements.txt`.
3. Set a strong `SECRET_KEY` environment variable.
4. Ensure `database.db` is present and run `python database/create_db.py` once to migrate it safely.
5. Start with `gunicorn app:app`.

The repository must not include `venv/`, `.git/`, or database backups.
