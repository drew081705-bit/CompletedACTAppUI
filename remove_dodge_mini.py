"""
One-time maintenance script.

Your live database was already seeded with "Dodge Mini" before this change,
so removing it from app.py's seed list alone won't remove it from the
database that's already running. Run this once, after pulling the new
code, to remove it safely (unassigning anyone currently in it first).

Usage (on PythonAnywhere, inside the project folder, with the venv active):
    python3 remove_dodge_mini.py

Safe to run more than once — it just reports "not found" if already removed.
"""

from app import app, db, Van

with app.app_context():
    van = Van.query.filter_by(name="Dodge Mini").first()
    if van is None:
        print("Dodge Mini not found — already removed, nothing to do.")
    else:
        for student in van.students:
            student.van_id = None
        for teacher in van.teachers:
            teacher.van_id = None
        db.session.delete(van)
        db.session.commit()
        print("Dodge Mini removed. Anyone who was assigned to it is now unassigned.")
