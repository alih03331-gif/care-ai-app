from flask import Flask, request, render_template, redirect, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime
import requests as req
import os

app = Flask(__name__)
app.secret_key = "shiftcare2024secure"

# ✅ Database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///shiftcare.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ✅ Email config
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "alih03331@gmail.com")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "ckfs zqbu xckx cbfn")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME", "alih03331@gmail.com")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "alih03331@gmail.com")

db = SQLAlchemy(app)
mail = Mail(app)

# ============================================================
# DATABASE MODELS
# ============================================================

class Agency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    carers = db.relationship("Carer", backref="agency", lazy=True, cascade="all, delete-orphan")
    shifts = db.relationship("Shift", backref="agency", lazy=True, cascade="all, delete-orphan")


class Carer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    skills = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    available = db.Column(db.Boolean, default=True)
    email = db.Column(db.String(100), nullable=True)
    agency_id = db.Column(db.Integer, db.ForeignKey("agency.id"), nullable=False)

    def skills_list(self):
        return [s.strip() for s in self.skills.split(",")]


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_name = db.Column(db.String(50), nullable=False)
    carer_name = db.Column(db.String(100), nullable=True)
    urgent = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(300), default="")
    location = db.Column(db.String(100), default="")
    agency_id = db.Column(db.Integer, db.ForeignKey("agency.id"), nullable=False)


SHIFT_NAMES = [
    "Monday Morning", "Monday Afternoon",
    "Tuesday Morning", "Tuesday Afternoon",
    "Wednesday Morning", "Wednesday Afternoon",
    "Thursday Morning", "Thursday Afternoon",
    "Friday Morning", "Friday Afternoon",
    "Saturday Morning", "Saturday Afternoon",
    "Sunday Morning", "Sunday Afternoon",
]


def init_db():
    with app.app_context():
        db.create_all()
        if not Agency.query.filter_by(username="admin").first():
            admin = Agency(
                name="ShiftCare Admin",
                username="admin",
                password="care1234",
                email=ADMIN_EMAIL,
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin account created!")


# ============================================================
# EMAIL FUNCTIONS
# ============================================================

def send_shift_assigned_email(carer_name, carer_email, shift_name, location, notes, urgent, agency_name):
    """Send email to carer when assigned to a shift"""
    try:
        if not carer_email:
            return

        maps_link = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"

        subject = f"{'🔴 URGENT: ' if urgent else ''}Shift Assignment - {shift_name}"

        body = f"""
Dear {carer_name},

You have been assigned to a shift by {agency_name}.

📅 SHIFT DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shift: {shift_name}
Location: {location}
{'⚠️ THIS IS AN URGENT SHIFT' if urgent else ''}
{f'Notes: {notes}' if notes else ''}

📍 VIEW LOCATION ON MAP:
{maps_link}

Please confirm your availability by contacting your agency.

Best regards,
ShiftCare Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated message from ShiftCare.
        """

        msg = Message(
            subject=subject,
            recipients=[carer_email],
            body=body
        )
        mail.send(msg)
        print(f"✅ Email sent to carer: {carer_email}")
    except Exception as e:
        print(f"❌ Email error: {e}")


def send_admin_shift_notification(carer_name, shift_name, location, urgent, agency_name):
    """Send email to admin when shift is assigned"""
    try:
        subject = f"{'🔴 URGENT SHIFT: ' if urgent else ''}Shift Assigned - {agency_name}"

        body = f"""
ShiftCare Admin Notification

A shift has been assigned:

Agency: {agency_name}
Carer: {carer_name}
Shift: {shift_name}
Location: {location}
{'⚠️ MARKED AS URGENT' if urgent else 'Status: Normal'}

View dashboard: https://care-ai-app-hqsi.onrender.com

ShiftCare Platform
        """

        msg = Message(
            subject=subject,
            recipients=[ADMIN_EMAIL],
            body=body
        )
        mail.send(msg)
        print(f"✅ Admin notification sent!")
    except Exception as e:
        print(f"❌ Admin email error: {e}")


def send_new_carer_email(carer_name, agency_name):
    """Send confirmation email to admin when new carer added"""
    try:
        subject = f"New Staff Added - {agency_name}"

        body = f"""
ShiftCare Admin Notification

A new care staff member has been registered:

Name: {carer_name}
Agency: {agency_name}
Time: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC

View dashboard: https://care-ai-app-hqsi.onrender.com/admin

ShiftCare Platform
        """

        msg = Message(
            subject=subject,
            recipients=[ADMIN_EMAIL],
            body=body
        )
        mail.send(msg)
        print(f"✅ New carer email sent!")
    except Exception as e:
        print(f"❌ New carer email error: {e}")


def send_urgent_alert(shift_name, agency_name, location):
    """Send urgent alert to admin"""
    try:
        subject = f"🔴 URGENT SHIFT ALERT - {agency_name}"

        body = f"""
⚠️ URGENT SHIFT ALERT

An urgent shift has been flagged on ShiftCare!

Agency: {agency_name}
Shift: {shift_name}
Location: {location}
Time: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC

Immediate action required!

View dashboard: https://care-ai-app-hqsi.onrender.com/admin

ShiftCare Platform
        """

        msg = Message(
            subject=subject,
            recipients=[ADMIN_EMAIL],
            body=body
        )
        mail.send(msg)
        print(f"✅ Urgent alert sent!")
    except Exception as e:
        print(f"❌ Urgent email error: {e}")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_coordinates(place_name):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": place_name, "format": "json", "limit": 1}
        headers = {"User-Agent": "ShiftCareApp/1.0"}
        response = req.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        pass
    return None


def get_road_distance_km(place1, place2):
    try:
        coords1 = get_coordinates(place1)
        coords2 = get_coordinates(place2)
        if not coords1 or not coords2:
            return 9999
        lat1, lon1 = coords1
        lat2, lon2 = coords2
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        response = req.get(url, params={"overview": "false"}, timeout=5)
        data = response.json()
        if data.get("routes"):
            return data["routes"][0]["distance"] / 1000
    except:
        pass
    return 9999


def find_best_match(skill, shift_location, agency_id):
    carers = Carer.query.filter_by(agency_id=agency_id, available=True).all()
    best_match = None
    best_score = -1
    best_distance = None
    best_carer = None
    for carer in carers:
        score = 0
        if skill.lower() in [s.lower() for s in carer.skills_list()]:
            score += 50
        distance_km = get_road_distance_km(carer.location, shift_location)
        score += max(0, 50 - int(distance_km))
        if score > best_score:
            best_score = score
            best_match = carer.name
            best_distance = round(distance_km, 1)
            best_carer = carer
    return best_match, best_score, best_distance, best_carer


def get_dashboard_stats(agency_id):
    all_carers = Carer.query.filter_by(agency_id=agency_id).all()
    shifts = Shift.query.filter_by(agency_id=agency_id).all()
    shift_dict = {s.shift_name: s for s in shifts}
    urgent_count = sum(1 for s in shifts if s.urgent)
    assigned_count = sum(1 for s in shifts if s.carer_name)
    available_count = sum(1 for c in all_carers if c.available)
    return all_carers, shift_dict, urgent_count, assigned_count, available_count


# ============================================================
# AUTH ROUTES
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        agency = Agency.query.filter_by(username=username, password=password).first()
        if agency:
            session["agency_id"] = agency.id
            session["agency_name"] = agency.name
            session["is_admin"] = agency.is_admin
            if agency.is_admin:
                return redirect("/admin")
            return redirect("/")
        else:
            error = "Wrong username or password!"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ============================================================
# AGENCY DASHBOARD
# ============================================================

@app.route("/")
def home():
    if "agency_id" not in session:
        return redirect("/login")
    if session.get("is_admin"):
        return redirect("/admin")

    agency_id = session["agency_id"]
    search = request.args.get("search", "").lower()

    all_carers, shift_dict, urgent_count, assigned_count, available_count = get_dashboard_stats(agency_id)

    carers = all_carers
    if search:
        carers = [c for c in all_carers if search in c.name.lower() or
                  any(search in s.lower() for s in c.skills_list())]

    return render_template("index.html",
                           carers=carers,
                           all_carers=all_carers,
                           shift_names=SHIFT_NAMES,
                           shift_dict=shift_dict,
                           search=search,
                           urgent_count=urgent_count,
                           assigned_count=assigned_count,
                           available_count=available_count,
                           result=None,
                           score=None,
                           match_location=None,
                           match_skill=None,
                           distance=None,
                           matched_carer=None,
                           agency_name=session["agency_name"])


@app.route("/add_carer", methods=["POST"])
def add_carer():
    if "agency_id" not in session:
        return redirect("/login")

    name = request.form["name"]
    agency_name = session["agency_name"]

    carer = Carer(
        name=name,
        skills=request.form["skills"],
        location=request.form["location"],
        available=request.form.get("available") == "on",
        email=request.form.get("email", ""),
        agency_id=session["agency_id"]
    )
    db.session.add(carer)
    db.session.commit()

    # ✅ Send admin notification
    send_new_carer_email(name, agency_name)

    return redirect("/")


@app.route("/toggle/<int:carer_id>")
def toggle(carer_id):
    if "agency_id" not in session:
        return redirect("/login")
    carer = Carer.query.filter_by(id=carer_id, agency_id=session["agency_id"]).first()
    if carer:
        carer.available = not carer.available
        db.session.commit()
    return redirect("/")


@app.route("/delete/<int:carer_id>")
def delete(carer_id):
    if "agency_id" not in session:
        return redirect("/login")
    carer = Carer.query.filter_by(id=carer_id, agency_id=session["agency_id"]).first()
    if carer:
        db.session.delete(carer)
        db.session.commit()
    return redirect("/")


@app.route("/assign_shift", methods=["POST"])
def assign_shift():
    if "agency_id" not in session:
        return redirect("/login")

    agency_id = session["agency_id"]
    agency_name = session["agency_name"]
    shift_name = request.form["shift_name"]
    carer_name = request.form["carer_name"]
    notes = request.form.get("notes", "")
    urgent = request.form.get("urgent") == "on"
    shift_location = request.form.get("shift_location", "")

    shift = Shift.query.filter_by(agency_id=agency_id, shift_name=shift_name).first()
    if shift:
        shift.carer_name = carer_name if carer_name != "none" else None
        shift.notes = notes
        shift.urgent = urgent
        shift.location = shift_location
    else:
        shift = Shift(
            shift_name=shift_name,
            carer_name=carer_name if carer_name != "none" else None,
            notes=notes,
            urgent=urgent,
            location=shift_location,
            agency_id=agency_id
        )
        db.session.add(shift)
    db.session.commit()

    # ✅ Send emails if carer assigned
    if carer_name and carer_name != "none":
        carer = Carer.query.filter_by(name=carer_name, agency_id=agency_id).first()
        if carer and carer.email:
            send_shift_assigned_email(
                carer_name=carer.name,
                carer_email=carer.email,
                shift_name=shift_name,
                location=shift_location,
                notes=notes,
                urgent=urgent,
                agency_name=agency_name
            )
        # ✅ Notify admin
        send_admin_shift_notification(carer_name, shift_name, shift_location, urgent, agency_name)

    # ✅ Send urgent alert separately
    if urgent:
        send_urgent_alert(shift_name, agency_name, shift_location)

    return redirect("/#schedule")


@app.route("/match", methods=["POST"])
def match():
    if "agency_id" not in session:
        return redirect("/login")

    agency_id = session["agency_id"]
    skill = request.form.get("skill", "").strip()
    location = request.form.get("location", "").strip()

    result, score, distance, matched_carer = find_best_match(skill, location, agency_id)
    all_carers, shift_dict, urgent_count, assigned_count, available_count = get_dashboard_stats(agency_id)

    return render_template("index.html",
                           carers=all_carers,
                           all_carers=all_carers,
                           shift_names=SHIFT_NAMES,
                           shift_dict=shift_dict,
                           search="",
                           result=result,
                           score=score,
                           match_location=location,
                           match_skill=skill,
                           distance=distance,
                           matched_carer=matched_carer,
                           urgent_count=urgent_count,
                           assigned_count=assigned_count,
                           available_count=available_count,
                           agency_name=session["agency_name"])


# ============================================================
# ADMIN PANEL
# ============================================================

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect("/login")
    agencies = Agency.query.filter_by(is_admin=False).all()
    return render_template("admin.html", agencies=agencies)


@app.route("/admin/create_agency", methods=["POST"])
def create_agency():
    if not session.get("is_admin"):
        return redirect("/login")
    name = request.form["name"]
    username = request.form["username"]
    password = request.form["password"]
    email = request.form["email"]

    if Agency.query.filter_by(username=username).first():
        return redirect("/admin?error=username_taken")

    agency = Agency(name=name, username=username, password=password, email=email)
    db.session.add(agency)
    db.session.commit()
    return redirect("/admin")


@app.route("/admin/delete_agency/<int:agency_id>")
def delete_agency(agency_id):
    if not session.get("is_admin"):
        return redirect("/login")
    agency = Agency.query.get(agency_id)
    if agency and not agency.is_admin:
        db.session.delete(agency)
        db.session.commit()
    return redirect("/admin")


@app.route("/admin/view_agency/<int:agency_id>")
def view_agency(agency_id):
    if not session.get("is_admin"):
        return redirect("/login")
    agency = Agency.query.get(agency_id)
    carers = Carer.query.filter_by(agency_id=agency_id).all()
    shifts = Shift.query.filter_by(agency_id=agency_id).all()
    return render_template("admin_view.html",
                           agency=agency,
                           carers=carers,
                           shifts=shifts)


# ============================================================
# RUN
# ============================================================

init_db()

if __name__ == "__main__":
    app.run(debug=True)