import sqlite3
db = sqlite3.connect('data/coordinator/coordinator.sqlite3')
cur = db.cursor()
cur.execute("PRAGMA table_info(phone_accounts)")
for row in cur.fetchall():
    print(row)
