import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Add role column
try:
    cursor.execute("""
        ALTER TABLE admins
        ADD COLUMN role TEXT DEFAULT 'admin'
    """)
except:
    pass

# Add photo column
try:
    cursor.execute("""
        ALTER TABLE admins
        ADD COLUMN photo TEXT DEFAULT 'default.png'
    """)
except:
    pass

# Add status column
try:
    cursor.execute("""
        ALTER TABLE admins
        ADD COLUMN status TEXT DEFAULT 'Active'
    """)
except:
    pass

# Make the first admin the Super Admin
cursor.execute("""
    UPDATE admins
    SET role='superadmin'
    WHERE id=1
""")

conn.commit()
conn.close()

print("Admin table updated successfully.")