import sqlite3
import json

conn = sqlite3.connect("moderation.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in c.fetchall()]

print("Database Tables in moderation.db:")
for t in tables:
    c.execute(f'SELECT count(*) FROM "{t}"')
    cnt = c.fetchone()[0]
    print(f" - {t}: {cnt} rows")

    # print sample row and columns
    c.execute(f'PRAGMA table_info("{t}")')
    cols = [col[1] for col in c.fetchall()]
    print(f"   Columns: {cols}")
    c.execute(f'SELECT * FROM "{t}" LIMIT 2')
    rows = c.fetchall()
    print(f"   Sample: {rows}\n")
