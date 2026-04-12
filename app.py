from flask import Flask, request, render_template, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import requests as req
import stripe
import os

app = Flask(__name__)
app.secret_key = "shiftcare2024secure"

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///shiftcare.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "alih03331@gmail.com")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME", "alih03331@gmail.com")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "alih03331@gmail.com")

db = SQLAlchemy(app)
mail = Mail(app)

PLANS = {
    "basic": {
        "name": "Basic",
        "price": 29,
        "currency": "gbp",
        "features": ["Up to 10 staff", "Email alerts", "Weekly schedule", "Staff matching"],
    },
    "pro": {
        "name": "Pro",
        "price": 79,
        "currency": "gbp",
        "features": ["Unlimited staff", "Email alerts", "Weekly schedule", "Staff matching", "Priority support", "Advanced reports"],
    }
}

class Agency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    plan = db.Column(db.String(20), default="trial")
    trial_ends = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=14))
    subscription_active = db.Column(db.Boolean, default=True)
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    stripe_subscription_id = db.Column(db.String(100), nullable=True)
    carers = db.relationship("Carer", backref="agency", lazy=True, cascade="all, delete-orphan")
    shifts = db.relationship("Shift", backref="agency", lazy=True, cascade="all, delete-orphan")

    def is_active(self):
        if self.is_admin:
            return True
        if self.plan == "trial":
            return datetime.utcnow() < self.trial_ends
        return self.subscription_active

    def trial_days_left(self):
        if self.plan == "trial":
            delta = self.trial_ends - datetime.utcnow()
            return max(0, delta.days)
        return 0


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



def send_shift_assigned_email(carer_name, carer_email, shift_name, location, notes, urgent, agency_name):
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
        """
        msg = Message(subject=subject, recipients=[carer_email], body=body)
        mail.send(msg)
        print(f"✅ Email sent to: {carer_email}")
    except Exception as e:
        print(f"❌ Email error: {e}")


def send_admin_shift_notification(carer_name, shift_name, location, urgent, agency_name):
    try:
        subject = f"{'🔴 URGENT: ' if urgent else ''}Shift Assigned - {agency_name}"
        body = f"""
ShiftCare Notification
Agency: {agency_name}
Carer: {carer_name}
Shift: {shift_name}
Location: {location}
{'⚠️ URGENT' if urgent else 'Status: Normal'}
View: https://care-ai-app-hqsi.onrender.com
        """
        msg = Message(subject=subject, recipients=[ADMIN_EMAIL], body=body)
        mail.send(msg)
    except Exception as e:
        print(f"❌ Admin email error: {e}")


def send_new_carer_email(carer_name, agency_name):
    try:
        subject = f"New Staff Added - {agency_name}"
        body = f"""
New staff member registered:
Name: {carer_name}
Agency: {agency_name}
Time: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC
        """
        msg = Message(subject=subject, recipients=[ADMIN_EMAIL], body=body)
        mail.send(msg)
    except Exception as e:
        print(f"❌ New carer email error: {e}")


def send_urgent_alert(shift_name, agency_name, location):
    try:
        subject = f"🔴 URGENT SHIFT - {agency_name}"
        body = f"""
⚠️ URGENT SHIFT ALERT
Agency: {agency_name}
Shift: {shift_name}
Location: {location}
Time: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC
View: https://care-ai-app-hqsi.onrender.com/admin
        """
        msg = Message(subject=subject, recipients=[ADMIN_EMAIL], body=body)
        mail.send(msg)
    except Exception as e:
        print(f"❌ Urgent email error: {e}")


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
            if not agency.is_active():
                return redirect("/pricing")
            return redirect("/")
        else:
            error = "Wrong username or password!"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/pricing")
def pricing():
    if "agency_id" not in session:
        return redirect("/login")
    agency = Agency.query.get(session["agency_id"])
    if not agency:
        session.clear()
        return redirect("/login")
    return render_template("pricing.html",
                           agency=agency,
                           plans=PLANS,
                           stripe_key=STRIPE_PUBLISHABLE_KEY)


@app.route("/create_checkout/<plan>")
def create_checkout(plan):
    if "agency_id" not in session:
        return redirect("/login")
    if plan not in PLANS:
        return redirect("/pricing")
    agency = Agency.query.get(session["agency_id"])
    if not agency:
        session.clear()
        return redirect("/login")
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=agency.email,
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "unit_amount": PLANS[plan]["price"] * 100,
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": f"ShiftCare {PLANS[plan]['name']} Plan",
                        "description": ", ".join(PLANS[plan]["features"])
                    }
                },
                "quantity": 1
            }],
            success_url=url_for("payment_success", plan=plan, _external=True),
            cancel_url=url_for("pricing", _external=True),
            metadata={"agency_id": agency.id, "plan": plan}
        )
        return redirect(checkout_session.url)
    except Exception as e:
        print(f"❌ Stripe error: {e}")
        return redirect("/pricing")


@app.route("/payment_success/<plan>")
def payment_success(plan):
    if "agency_id" not in session:
        return redirect("/login")
    agency = Agency.query.get(session["agency_id"])
    if not agency:
        session.clear()
        return redirect("/login")
    agency.plan = plan
    agency.subscription_active = True
    db.session.commit()
    return redirect("/")


@app.route("/payment_cancel")
def payment_cancel():
    return redirect("/pricing")


@app.route("/")
def home():
    if "agency_id" not in session:
        return redirect("/login")
    if session.get("is_admin"):
        return redirect("/admin")

    agency = Agency.query.get(session["agency_id"])
    if not agency:
        session.clear()
        return redirect("/login")
    if not agency.is_active():
        return redirect("/pricing")

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
                           agency_name=session["agency_name"],
                           agency=agency)


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

    if carer_name and carer_name != "none":
        carer = Carer.query.filter_by(name=carer_name, agency_id=agency_id).first()
        if carer and carer.email:
            send_shift_assigned_email(carer.name, carer.email, shift_name,
                                      shift_location, notes, urgent, agency_name)
        send_admin_shift_notification(carer_name, shift_name, shift_location, urgent, agency_name)

    if urgent:
        send_urgent_alert(shift_name, agency_name, shift_location)

    return redirect("/#schedule")


@app.route("/match", methods=["POST"])
def match():
    if "agency_id" not in session:
        return redirect("/login")
    agency_id = session["agency_id"]
    agency = Agency.query.get(agency_id)
    if not agency:
        session.clear()
        return redirect("/login")
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
                           agency_name=session["agency_name"],
                           agency=agency)


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
    return render_template("admin_view.html", agency=agency, carers=carers, shifts=shifts)


@app.route("/admin/toggle_subscription/<int:agency_id>")
def toggle_subscription(agency_id):
    if not session.get("is_admin"):
        return redirect("/login")
    agency = Agency.query.get(agency_id)
    if agency and not agency.is_admin:
        agency.subscription_active = not agency.subscription_active
        db.session.commit()
    return redirect("/admin")


init_db()

if __name__ == "__main__":
    app.run(debug=True)