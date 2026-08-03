"""
Migration: rename UserAccount.username → email
Run once: python3 migrate_email_login.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'topgee.db')
if not os.path.exists(DB_PATH):
    # Try alternate path
    DB_PATH = os.path.join(os.path.dirname(__file__), 'topgee.db')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check if column already renamed
cur.execute("PRAGMA table_info(user_account)")
cols = [row[1] for row in cur.fetchall()]
print("Current columns:", cols)

if 'username' in cols and 'email' not in cols:
    print("Renaming username → email...")
    cur.execute("ALTER TABLE user_account RENAME COLUMN username TO email")
    conn.commit()
    print("✅ Done — username column renamed to email")
elif 'email' in cols:
    print("✅ Already migrated — email column exists")
else:
    print("⚠️ username column not found — may need manual check")

conn.close()
