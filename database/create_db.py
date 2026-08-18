import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database.db"


def column_names(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    fullname TEXT NOT NULL,
    password TEXT NOT NULL,
    photo TEXT DEFAULT 'default.png',
    has_voted INTEGER DEFAULT 0
)""")
if "photo" not in column_names(conn, "students"):
    cur.execute("ALTER TABLE students ADD COLUMN photo TEXT DEFAULT 'default.png'")

cur.execute("""CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT DEFAULT 'admin',
    photo TEXT DEFAULT 'default.png',
    status TEXT DEFAULT 'Active',
    email TEXT,
    phone TEXT
)""")
for col, definition in {
    "role":"TEXT DEFAULT 'admin'", "photo":"TEXT DEFAULT 'default.png'", "status":"TEXT DEFAULT 'Active'", "email":"TEXT", "phone":"TEXT"
}.items():
    if col not in column_names(conn, "admins"):
        cur.execute(f"ALTER TABLE admins ADD COLUMN {col} {definition}")

cur.execute("""CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_name TEXT UNIQUE NOT NULL
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT,
    position TEXT,
    photo TEXT DEFAULT 'default.png'
)""")
if "photo" not in column_names(conn, "candidates"):
    cur.execute("ALTER TABLE candidates ADD COLUMN photo TEXT DEFAULT 'default.png'")
cur.execute("""CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    candidate_id INTEGER
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    results_published INTEGER NOT NULL DEFAULT 0,
    school_name TEXT DEFAULT 'Kigezi High School',
    school_logo TEXT DEFAULT 'default.png',
    voting_status TEXT DEFAULT 'Open',
    start_date TEXT,
    end_date TEXT
)""")
for col, definition in {
    "results_published":"INTEGER NOT NULL DEFAULT 0", "school_name":"TEXT DEFAULT 'Kigezi High School'", "school_logo":"TEXT DEFAULT 'default.png'", "voting_status":"TEXT DEFAULT 'Open'", "start_date":"TEXT", "end_date":"TEXT"
}.items():
    if col not in column_names(conn, "settings"):
        cur.execute(f"ALTER TABLE settings ADD COLUMN {col} {definition}")
cur.execute("INSERT OR IGNORE INTO settings(id) VALUES(1)")

# Normalize missing values without overwriting real data.
cur.execute("UPDATE students SET photo='default.png' WHERE photo IS NULL OR photo=''")
cur.execute("UPDATE candidates SET photo='default.png' WHERE photo IS NULL OR photo=''")
cur.execute("UPDATE admins SET photo='default.png' WHERE photo IS NULL OR photo=''")

# Hash legacy plain-text student/admin passwords while preserving their values.
for table in ("students", "admins"):
    rows = cur.execute(f"SELECT id,password FROM {table}").fetchall()
    for row_id, password in rows:
        if password and not str(password).startswith(("scrypt:", "pbkdf2:", "argon2:")):
            cur.execute(f"UPDATE {table} SET password=? WHERE id=?", (generate_password_hash(password), row_id))

# Seed positions only if they do not already exist.
for name in ["Head Prefect", "Deputy Head Prefect", "Sports Captain", "Entertainment Prefect", "Dining Hall Prefect"]:
    cur.execute("INSERT OR IGNORE INTO positions(position_name) VALUES(?)", (name,))

conn.commit()
conn.close()
print(f"Database ready: {DB_PATH}")
