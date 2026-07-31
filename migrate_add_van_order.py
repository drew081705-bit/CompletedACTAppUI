"""
One-time migration script.

This adds the new order_index column to the Van table for your already-live
database (a fresh install doesn't need this — it gets built with the column
from the start). Run this once, after pulling the new code and BEFORE
clicking Reload on the Web tab, so the app doesn't start up and immediately
query a column that doesn't exist yet.

Usage (on PythonAnywhere, inside the project folder, with the venv active):
    python3 migrate_add_van_order.py

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

if "order_index" in columns:
    print("Already migrated — order_index column exists. Nothing to do.")
else:
    cur.execute("ALTER TABLE van ADD COLUMN order_index INTEGER DEFAULT 0")
    cur.execute("SELECT id FROM van ORDER BY id")
    for position, (van_id,) in enumerate(cur.fetchall()):
        cur.execute("UPDATE van SET order_index = ? WHERE id = ?", (position, van_id))
    conn.commit()
    print("Migration applied: order_index column added, existing vans ordered by id.")

conn.close()
