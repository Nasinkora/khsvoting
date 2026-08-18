import sqlite3

conn = sqlite3.connect("database.db")
conn.row_factory = sqlite3.Row

cursor = conn.cursor()

cursor.execute("SELECT * FROM admins")

admins = cursor.fetchall()

for admin in admins:
    print(dict(admin))

conn.close()