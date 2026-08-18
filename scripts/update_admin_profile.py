import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

try:
    cursor.execute("""
        ALTER TABLE admins
        ADD COLUMN email TEXT
    """)
except:
    pass

try:
    cursor.execute("""
        ALTER TABLE admins
        ADD COLUMN phone TEXT
    """)
except:
    pass

conn.commit()
conn.close()

print("Admin profile updated successfully.")