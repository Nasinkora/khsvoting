import sqlite3
from werkzeug.security import generate_password_hash

# Connect to database
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# ======================================================
# SETTINGS TABLE
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (

    id INTEGER PRIMARY KEY,

    school_name TEXT NOT NULL DEFAULT 'Kigezi High School',

    school_logo TEXT NOT NULL DEFAULT 'logo.png',

    voting_status TEXT NOT NULL DEFAULT 'Closed',

    results_published INTEGER NOT NULL DEFAULT 0,

    start_date TEXT,

    end_date TEXT

)
""")

cursor.execute("""
INSERT OR IGNORE INTO settings (

    id,
    school_name,
    school_logo,
    voting_status,
    results_published,
    start_date,
    end_date

)

VALUES(

    1,
    'Kigezi High School',
    'logo.png',
    'Closed',
    0,
    '',
    ''

)
""")

# ======================================================
# VOTES TABLE
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS votes (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    student_id TEXT NOT NULL,

    candidate_id INTEGER NOT NULL,

    FOREIGN KEY(candidate_id)
        REFERENCES candidates(id)

)
""")

# ======================================================
# ADMINS TABLE
# ======================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    username TEXT UNIQUE NOT NULL,

    password TEXT NOT NULL,

    role TEXT NOT NULL DEFAULT 'admin',

    photo TEXT NOT NULL DEFAULT 'default.png',

    status TEXT NOT NULL DEFAULT 'Active',

    email TEXT,

    phone TEXT

)
""")

# ======================================================
# DEFAULT SUPER ADMIN
# ======================================================

hashed_password = generate_password_hash("admin123")

cursor.execute("""

INSERT OR IGNORE INTO admins(

    id,
    username,
    password,
    role,
    photo,
    status,
    email,
    phone

)

VALUES(

    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?,
    ?

)

""",(

    1,
    "admin",
    hashed_password,
    "superadmin",
    "default.png",
    "Active",
    "",
    ""

))

# ======================================================
# SAVE CHANGES
# ======================================================

conn.commit()
conn.close()

print("="*55)
print("DATABASE CREATED SUCCESSFULLY")
print("="*55)
print("Default Super Administrator Account")
print("---------------------------------------")
print("Username : Edwin")
print("Password : eddy")
print("Role     : Super Administrator")
print("Status   : Active")
print("="*55)