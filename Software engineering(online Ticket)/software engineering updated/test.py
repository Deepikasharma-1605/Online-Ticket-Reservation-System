import sqlite3
conn = sqlite3.connect('tickets.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(tickets);")
print("tickets columns:", cur.fetchall())          # each item: (cid, name, type, notnull, dflt_value, pk)
cur.execute("SELECT * FROM tickets LIMIT 1;")
row = cur.fetchone()
if row is not None:
    print("sample row:", row)
conn.close()
