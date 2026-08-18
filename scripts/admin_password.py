from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

hashed = generate_password_hash("eddy")

cursor.execute(
    "UPDATE admins SET password=? WHERE id=1",
    (hashed,)
)

conn.commit()
conn.close()

print("Password updated successfully.")