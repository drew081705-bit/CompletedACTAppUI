"""
One-time migration script.

Adds a `destination` text column to the Van table for your already-live
database (a fresh install doesn't need this — it gets built with the
column from the start). Run this once, after pulling the new code and
BEFORE clicking Reload on the Web tab.

Usage (on PythonAnywhere, inside the project folder, with the venv active):
    python3 migrate_add_destination.py

Safe to run more than once — it checks first and does nothing if already applied.
"""

import sqlite3
import os

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, "data.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(van)")
columns = [row[1] for row in cur.fetchall()]

if "destination" in columns:
    print("Already migrated — destination column exists. Nothing to do.")
else:
    cur.execute("ALTER TABLE van ADD COLUMN destination VARCHAR(200) DEFAULT ''")
    conn.commit()
    print("Migration applied: destination column added to van table (blank for existing vans).")

conn.close()
