import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# ──────────────────────────────────────────────────────────────
# DATABASE SETUP
# ──────────────────────────────────────────────────────────────
# SQLite file lives next to app.py while developing locally.
# On PythonAnywhere this same code works unchanged — it just points
# at a SQLite file living in the persistent filesystem there instead.
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "data.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ──────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────

class Van(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)

    students = db.relationship("Student", backref="van", lazy=True)
    teachers = db.relationship("Teacher", backref="van", lazy=True)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    present = db.Column(db.Boolean, nullable=False, default=True)
    class_name = db.Column(db.String(40), nullable=False, default="Yellow")
    van_id = db.Column(db.Integer, db.ForeignKey("van.id"), nullable=True)


class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    van_id = db.Column(db.Integer, db.ForeignKey("van.id"), nullable=True)


# ──────────────────────────────────────────────────────────────
# LOGIC — same rules as before, now backed by the database
# ──────────────────────────────────────────────────────────────

def total_occupants(van):
    return len(van.students) + len(van.teachers)


def can_assign_student(van):
    if total_occupants(van) + 1 > van.capacity:
        return False, "Adding a student would exceed van capacity."
    if len(van.teachers) == 0:
        return False, "Each van must have at least one teacher before assigning students."
    if len(van.students) + 1 > 2 * len(van.teachers):
        return False, "Cannot assign more than 2 students per 1 teacher."
    return True, ""


def can_assign_teacher(van):
    if total_occupants(van) + 1 > van.capacity:
        return False, "Adding a teacher would exceed van capacity."
    return True, ""


def assign_student_to_van(student_name, van_name):
    student = Student.query.filter_by(name=student_name).first()
    if student is None:
        return f"{student_name} is not in the student list."
    if not student.present:
        return f"{student_name} is not present and cannot be assigned."
    if student.van_id is not None:
        return f"{student_name} is already assigned to a van."
    van = Van.query.filter_by(name=van_name).first()
    if van is None:
        return "Van does not exist."
    can_assign, message = can_assign_student(van)
    if not can_assign:
        return message
    student.van_id = van.id
    db.session.commit()
    return f"{student_name} assigned to {van_name}."


def assign_teacher_to_van(teacher_name, van_name):
    teacher = Teacher.query.filter_by(name=teacher_name).first()
    if teacher is None:
        return f"{teacher_name} is not in the teacher list."
    if teacher.van_id is not None:
        return f"{teacher_name} is already assigned to a van."
    van = Van.query.filter_by(name=van_name).first()
    if van is None:
        return "Van does not exist."
    can_assign, message = can_assign_teacher(van)
    if not can_assign:
        return message
    teacher.van_id = van.id
    db.session.commit()
    return f"{teacher_name} assigned to {van_name}."


def add_student(name, present=True):
    name = name.strip()
    if not name:
        return "Student name cannot be blank."
    if Student.query.filter_by(name=name).first() is not None:
        return f"{name} is already in the student list."
    db.session.add(Student(name=name, present=present, class_name="Yellow"))
    db.session.commit()
    return f"Student {name} added."


def toggle_student_attendance(student_name):
    student = Student.query.filter_by(name=student_name).first()
    if student is None:
        return f"{student_name} is not in the student list."
    student.present = not student.present
    if not student.present:
        student.van_id = None  # an absent student can't stay assigned to a van
    db.session.commit()
    status = "present" if student.present else "absent"
    return f"{student_name} marked {status}."


def add_teacher(name):
    name = name.strip()
    if not name:
        return "Teacher name cannot be blank."
    if Teacher.query.filter_by(name=name).first() is not None:
        return f"{name} is already in the teacher list."
    db.session.add(Teacher(name=name))
    db.session.commit()
    return f"Teacher {name} added."


def delete_student(student_name):
    student = Student.query.filter_by(name=student_name).first()
    if student is None:
        return f"{student_name} is not in the student list."
    db.session.delete(student)
    db.session.commit()
    return f"Student {student_name} deleted."


def delete_teacher(teacher_name):
    teacher = Teacher.query.filter_by(name=teacher_name).first()
    if teacher is None:
        return f"{teacher_name} is not in the teacher list."
    db.session.delete(teacher)
    db.session.commit()
    return f"Teacher {teacher_name} deleted."


def remove_student_from_van(student_name):
    student = Student.query.filter_by(name=student_name).first()
    if student is None or student.van_id is None:
        return f"{student_name} is not assigned to any van."
    van_name = student.van.name
    student.van_id = None
    db.session.commit()
    return f"{student_name} removed from {van_name}."


def remove_teacher_from_van(teacher_name):
    teacher = Teacher.query.filter_by(name=teacher_name).first()
    if teacher is None or teacher.van_id is None:
        return f"{teacher_name} is not assigned to any van."
    van_name = teacher.van.name
    teacher.van_id = None
    db.session.commit()
    return f"{teacher_name} removed from {van_name}."


def reset_assignments():
    Student.query.update({Student.van_id: None})
    Teacher.query.update({Teacher.van_id: None})
    db.session.commit()


# ──────────────────────────────────────────────────────────────
# STATE SERIALIZATION — turns the database into JSON for the browser
# ──────────────────────────────────────────────────────────────

def get_state():
    return {
        "students": {
            s.name: {
                "present": s.present,
                "class": s.class_name,
                "assigned_van": s.van.name if s.van_id else None,
            }
            for s in Student.query.all()
        },
        "teachers": {
            t.name: {"assigned_van": t.van.name if t.van_id else None}
            for t in Teacher.query.all()
        },
        "vans": {
            v.name: {
                "capacity": v.capacity,
                "students": [s.name for s in v.students],
                "teachers": [t.name for t in v.teachers],
                "occupants": total_occupants(v),
            }
            for v in Van.query.all()
        },
    }


# ──────────────────────────────────────────────────────────────
# SEED DATA — only runs the very first time, when the database is empty.
# After that, whatever is in the database (including all your edits)
# is what persists, forever, across restarts and deploys.
# ──────────────────────────────────────────────────────────────

def seed_if_empty():
    if Van.query.count() > 0:
        return  # database already has real data — never overwrite it

    db.session.add_all([
        Van(name="Mobility Van", capacity=7),
        Van(name="Toyota Mini", capacity=6),
        Van(name="Dodge Mini", capacity=6),
        Van(name="Red Van", capacity=15),
        Van(name="White Pass Van", capacity=15),
        Van(name="Black Van", capacity=12),
    ])
    db.session.add_all([
        Student(name="Jeff", present=True, class_name="Yellow"),
        Student(name="Emily", present=False, class_name="Yellow"),
        Student(name="Michael", present=True, class_name="Orange"),
    ])
    db.session.add_all([
        Teacher(name="Heather"),
        Teacher(name="Jessica"),
        Teacher(name="Chelsea"),
    ])
    db.session.commit()


with app.app_context():
    db.create_all()  # creates tables only if they don't already exist
    seed_if_empty()


# ──────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    return jsonify(get_state())


@app.route("/api/assign_student", methods=["POST"])
def api_assign_student():
    data = request.get_json()
    message = assign_student_to_van(data["student"], data["van"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/assign_teacher", methods=["POST"])
def api_assign_teacher():
    data = request.get_json()
    message = assign_teacher_to_van(data["teacher"], data["van"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/remove_student", methods=["POST"])
def api_remove_student():
    data = request.get_json()
    message = remove_student_from_van(data["student"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/remove_teacher", methods=["POST"])
def api_remove_teacher():
    data = request.get_json()
    message = remove_teacher_from_van(data["teacher"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/add_student", methods=["POST"])
def api_add_student():
    data = request.get_json()
    message = add_student(data["name"], data.get("present", True))
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/toggle_attendance", methods=["POST"])
def api_toggle_attendance():
    data = request.get_json()
    message = toggle_student_attendance(data["name"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/add_teacher", methods=["POST"])
def api_add_teacher():
    data = request.get_json()
    message = add_teacher(data["name"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/delete_student", methods=["POST"])
def api_delete_student():
    data = request.get_json()
    message = delete_student(data["name"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/delete_teacher", methods=["POST"])
def api_delete_teacher():
    data = request.get_json()
    message = delete_teacher(data["name"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    reset_assignments()
    return jsonify({"message": "All assignments cleared.", "state": get_state()})


if __name__ == "__main__":
    app.run(debug=True)
