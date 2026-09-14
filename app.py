import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.json.sort_keys = False  # preserve our van ordering — Flask sorts JSON keys by default

# ──────────────────────────────────────────────────────────────
# DATABASE SETUP
# ──────────────────────────────────────────────────────────────
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "data.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

PERIODS = ("AM", "PM")


# ──────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────
# Students and teachers each carry TWO independent van assignments —
# one for the AM run, one for the PM run — so the same roster and the
# same fleet of vans can be routed differently morning vs afternoon.

class Van(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    present = db.Column(db.Boolean, nullable=False, default=True)
    class_name = db.Column(db.String(40), nullable=False, default="Yellow")
    am_van_id = db.Column(db.Integer, db.ForeignKey("van.id"), nullable=True)
    pm_van_id = db.Column(db.Integer, db.ForeignKey("van.id"), nullable=True)


class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    am_van_id = db.Column(db.Integer, db.ForeignKey("van.id"), nullable=True)
    pm_van_id = db.Column(db.Integer, db.ForeignKey("van.id"), nullable=True)


def _van_field(period):
    return "am_van_id" if period == "AM" else "pm_van_id"


# ──────────────────────────────────────────────────────────────
# LOGIC
# ──────────────────────────────────────────────────────────────

def van_students(van, period):
    field = _van_field(period)
    return Student.query.filter(getattr(Student, field) == van.id).all()


def van_teachers(van, period):
    field = _van_field(period)
    return Teacher.query.filter(getattr(Teacher, field) == van.id).all()


def total_occupants(van, period):
    return len(van_students(van, period)) + len(van_teachers(van, period))


def can_assign_student(van, period):
    if total_occupants(van, period) + 1 > van.capacity:
        return False, "Adding a student would exceed van capacity."
    if len(van_teachers(van, period)) == 0:
        return False, "Each van must have at least one teacher before assigning students."
    return True, ""


def can_assign_teacher(van, period):
    if total_occupants(van, period) + 1 > van.capacity:
        return False, "Adding a teacher would exceed van capacity."
    return True, ""


def assign_student_to_van(student_name, van_name, period):
    student = Student.query.filter_by(name=student_name).first()
    if student is None:
        return f"{student_name} is not in the student list."
    if not student.present:
        return f"{student_name} is not present and cannot be assigned."
    field = _van_field(period)
    if getattr(student, field) is not None:
        return f"{student_name} is already assigned to a van for {period}."
    van = Van.query.filter_by(name=van_name).first()
    if van is None:
        return "Van does not exist."
    can_assign, message = can_assign_student(van, period)
    if not can_assign:
        return message
    setattr(student, field, van.id)
    db.session.commit()
    return f"{student_name} assigned to {van_name} ({period})."


def assign_teacher_to_van(teacher_name, van_name, period):
    teacher = Teacher.query.filter_by(name=teacher_name).first()
    if teacher is None:
        return f"{teacher_name} is not in the teacher list."
    field = _van_field(period)
    if getattr(teacher, field) is not None:
        return f"{teacher_name} is already assigned to a van for {period}."
    van = Van.query.filter_by(name=van_name).first()
    if van is None:
        return "Van does not exist."
    can_assign, message = can_assign_teacher(van, period)
    if not can_assign:
        return message
    setattr(teacher, field, van.id)
    db.session.commit()
    return f"{teacher_name} assigned to {van_name} ({period})."


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
        # an absent student can't stay assigned to either run
        student.am_van_id = None
        student.pm_van_id = None
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


def remove_student_from_van(student_name, period):
    student = Student.query.filter_by(name=student_name).first()
    field = _van_field(period)
    if student is None or getattr(student, field) is None:
        return f"{student_name} is not assigned to a van for {period}."
    van = Van.query.get(getattr(student, field))
    setattr(student, field, None)
    db.session.commit()
    return f"{student_name} removed from {van.name if van else 'their van'} ({period})."


def remove_teacher_from_van(teacher_name, period):
    teacher = Teacher.query.filter_by(name=teacher_name).first()
    field = _van_field(period)
    if teacher is None or getattr(teacher, field) is None:
        return f"{teacher_name} is not assigned to a van for {period}."
    van = Van.query.get(getattr(teacher, field))
    setattr(teacher, field, None)
    db.session.commit()
    return f"{teacher_name} removed from {van.name if van else 'their van'} ({period})."


def reset_assignments():
    Student.query.update({Student.am_van_id: None, Student.pm_van_id: None})
    Teacher.query.update({Teacher.am_van_id: None, Teacher.pm_van_id: None})
    db.session.commit()


def add_van(name, capacity):
    name = name.strip()
    if not name:
        return "Van name cannot be blank."
    if Van.query.filter_by(name=name).first() is not None:
        return f"{name} already exists."
    try:
        capacity = int(capacity)
    except (TypeError, ValueError):
        return "Capacity must be a number."
    if capacity < 1:
        return "Capacity must be at least 1."
    max_order = db.session.query(db.func.max(Van.order_index)).scalar()
    next_order = (max_order + 1) if max_order is not None else 0
    db.session.add(Van(name=name, capacity=capacity, order_index=next_order))
    db.session.commit()
    return f"Van {name} added."


def delete_van(van_name):
    van = Van.query.filter_by(name=van_name).first()
    if van is None:
        return f"{van_name} does not exist."
    affected = 0
    for student in Student.query.filter(
        (Student.am_van_id == van.id) | (Student.pm_van_id == van.id)
    ).all():
        if student.am_van_id == van.id:
            student.am_van_id = None
            affected += 1
        if student.pm_van_id == van.id:
            student.pm_van_id = None
            affected += 1
    for teacher in Teacher.query.filter(
        (Teacher.am_van_id == van.id) | (Teacher.pm_van_id == van.id)
    ).all():
        if teacher.am_van_id == van.id:
            teacher.am_van_id = None
            affected += 1
        if teacher.pm_van_id == van.id:
            teacher.pm_van_id = None
            affected += 1
    db.session.delete(van)
    db.session.commit()
    return f"Van {van_name} deleted. Anyone assigned to it (AM or PM) is now unassigned."


def reorder_vans(ordered_names):
    vans_by_name = {v.name: v for v in Van.query.all()}
    for index, name in enumerate(ordered_names):
        van = vans_by_name.get(name)
        if van is not None:
            van.order_index = index
    db.session.commit()


# ──────────────────────────────────────────────────────────────
# STATE SERIALIZATION — always returns BOTH periods at once, so the
# frontend can switch between AM/PM instantly without a round trip,
# and the print export can show both in one document.
# ──────────────────────────────────────────────────────────────

def get_state():
    vans = Van.query.order_by(Van.order_index).all()
    students = Student.query.all()
    teachers = Teacher.query.all()
    van_name_by_id = {v.id: v.name for v in vans}

    van_data = {}
    for v in vans:
        am_students = [s.name for s in students if s.am_van_id == v.id]
        pm_students = [s.name for s in students if s.pm_van_id == v.id]
        am_teachers = [t.name for t in teachers if t.am_van_id == v.id]
        pm_teachers = [t.name for t in teachers if t.pm_van_id == v.id]
        van_data[v.name] = {
            "capacity": v.capacity,
            "am": {
                "students": am_students,
                "teachers": am_teachers,
                "occupants": len(am_students) + len(am_teachers),
            },
            "pm": {
                "students": pm_students,
                "teachers": pm_teachers,
                "occupants": len(pm_students) + len(pm_teachers),
            },
        }

    return {
        "students": {
            s.name: {
                "present": s.present,
                "class": s.class_name,
                "am_van": van_name_by_id.get(s.am_van_id),
                "pm_van": van_name_by_id.get(s.pm_van_id),
            }
            for s in students
        },
        "teachers": {
            t.name: {
                "am_van": van_name_by_id.get(t.am_van_id),
                "pm_van": van_name_by_id.get(t.pm_van_id),
            }
            for t in teachers
        },
        "vans": van_data,
    }


# ──────────────────────────────────────────────────────────────
# SEED DATA — only runs the very first time, when the database is empty.
# ──────────────────────────────────────────────────────────────

def seed_if_empty():
    if Van.query.count() > 0:
        return

    db.session.add_all([
        Van(name="Mobility Van", capacity=7, order_index=0),
        Van(name="Toyota Mini", capacity=6, order_index=1),
        Van(name="Red Van", capacity=15, order_index=2),
        Van(name="White Pass Van", capacity=15, order_index=3),
        Van(name="Black Van", capacity=12, order_index=4),
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
    db.create_all()
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
    message = assign_student_to_van(data["student"], data["van"], data["period"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/assign_teacher", methods=["POST"])
def api_assign_teacher():
    data = request.get_json()
    message = assign_teacher_to_van(data["teacher"], data["van"], data["period"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/remove_student", methods=["POST"])
def api_remove_student():
    data = request.get_json()
    message = remove_student_from_van(data["student"], data["period"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/remove_teacher", methods=["POST"])
def api_remove_teacher():
    data = request.get_json()
    message = remove_teacher_from_van(data["teacher"], data["period"])
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


@app.route("/api/add_van", methods=["POST"])
def api_add_van():
    data = request.get_json()
    message = add_van(data["name"], data["capacity"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/delete_van", methods=["POST"])
def api_delete_van():
    data = request.get_json()
    message = delete_van(data["name"])
    return jsonify({"message": message, "state": get_state()})


@app.route("/api/reorder_vans", methods=["POST"])
def api_reorder_vans():
    data = request.get_json()
    reorder_vans(data["order"])
    return jsonify({"message": "Van order updated.", "state": get_state()})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    reset_assignments()
    return jsonify({"message": "All AM and PM assignments cleared.", "state": get_state()})


if __name__ == "__main__":
    app.run(debug=True)
