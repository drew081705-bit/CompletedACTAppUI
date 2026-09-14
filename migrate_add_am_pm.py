"""
One-time migration script.

Your live database currently has a single van_id column per student/teacher
(one assignment). This adds separate am_van_id and pm_van_id columns, and
carries over any existing assignment into AM (leaving PM blank to start).

Usage (on PythonAnywhere, inside the project folder, with the venv active,
BEFORE clicking Reload):
    python3 migrate_add_am_pm.py

Safe to run more than once.
"""

import sqlite3
import os

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, "data.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()


def existing_columns(table):
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


changed = False

for table in ("student", "teacher"):
    columns = existing_columns(table)

    if "am_van_id" not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN am_van_id INTEGER")
        if "van_id" in columns:
            cur.execute(f"UPDATE {table} SET am_van_id = van_id")
        changed = True

    if "pm_van_id" not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN pm_van_id INTEGER")
        changed = True

conn.commit()
conn.close()

if changed:
    print("Migration applied: am_van_id/pm_van_id added. Existing assignments carried over to AM; PM starts empty.")
else:
    print("Already migrated — nothing to do.")
