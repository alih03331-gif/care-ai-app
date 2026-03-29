from flask import Flask, request, render_template, redirect, session
import requests
import json
import os

app = Flask(__name__)
app.secret_key = "carematcher2024secure"

DATA_FILE = "data.json"

default_data = {
    "carers": [
        {"name": "Alice", "skills": ["dementia", "elderly"], "location": "Leeds, UK", "available": True},
        {"name": "Bob", "skills": ["general"], "location": "Manchester, UK", "available": True},
        {"name": "Charlie", "skills": ["dementia"], "location": "Bradford, UK", "available": False}
    ],
    "schedule": [
        {"shift": "Monday Morning",     "carer": None},
        {"shift": "Monday Afternoon",   "carer": None},
        {"shift": "Tuesday Morning",    "carer": None},
        {"shift": "Tuesday Afternoon",  "carer": None},
        {"shift": "Wednesday Morning",  "carer": None},
        {"shift": "Wednesday Afternoon","carer": None},
        {"shift": "Thursday Morning",   "carer": None},
        {"shift": "Thursday Afternoon", "carer": None},
        {"shift": "Friday Morning",     "carer": None},
        {"shift": "Friday Afternoon",   "carer": None},
    ]
}

# ✅ Login credentials — change these to your own
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "care1234"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return default_data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


data = load_data()
carers = data["carers"]
schedule = data["schedule"]


def get_coordinates(place_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place_name, "format": "json", "limit": 1}
    headers = {"User-Agent": "CareMatcherApp/1.0"}
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None


def get_road_distance_km(place1, place2):
    coords1 = get_coordinates(place1)
    coords2 = get_coordinates(place2)
    if not coords1 or not coords2:
        return 9999
    lat1, lon1 = coords1
    lat2, lon2 = coords2
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    response = requests.get(url, params={"overview": "false"})
    data = response.json()
    if data.get("routes"):
        return data["routes"][0]["distance"] / 1000
    return 9999


def find_best_match(skill, shift_location):
    best_match = None
    best_score = -1
    for carer in carers:
        if not carer["available"]:
            continue
        score = 0
        if skill.lower() in [s.lower() for s in carer["skills"]]:
            score += 50
        distance_km = get_road_distance_km(carer["location"], shift_location)
        score += max(0, 50 - int(distance_km))
        if score > best_score:
            best_score = score
            best_match = carer["name"]
    return best_match, best_score


# ✅ LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["user"] = username
            return redirect("/")
        else:
            error = "Wrong username or password!"
    return render_template("login.html", error=error)


# ✅ LOGOUT
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")


@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    return render_template("index.html", carers=carers, schedule=schedule)


@app.route("/add_carer", methods=["POST"])
def add_carer():
    if "user" not in session:
        return redirect("/login")
    name = request.form["name"]
    skills = request.form["skills"]
    location = request.form["location"]
    available = request.form.get("available") == "on"
    carers.append({
        "name": name,
        "skills": [s.strip() for s in skills.split(",")],
        "location": location,
        "available": available
    })
    save_data({"carers": carers, "schedule": schedule})
    return redirect("/")


@app.route("/toggle/<int:index>")
def toggle(index):
    if "user" not in session:
        return redirect("/login")
    carers[index]["available"] = not carers[index]["available"]
    save_data({"carers": carers, "schedule": schedule})
    return redirect("/")


@app.route("/delete/<int:index>")
def delete(index):
    if "user" not in session:
        return redirect("/login")
    carers.pop(index)
    save_data({"carers": carers, "schedule": schedule})
    return redirect("/")


@app.route("/assign_shift", methods=["POST"])
def assign_shift():
    if "user" not in session:
        return redirect("/login")
    shift_index = int(request.form["shift_index"])
    carer_name = request.form["carer_name"]
    schedule[shift_index]["carer"] = carer_name if carer_name != "none" else None
    save_data({"carers": carers, "schedule": schedule})
    return redirect("/")


@app.route("/match", methods=["POST"])
def match():
    if "user" not in session:
        return redirect("/login")
    skill = request.form["skill"]
    location = request.form["location"]
    result, score = find_best_match(skill, location)
    return render_template("index.html", carers=carers, schedule=schedule,
                           result=result, score=score, location=location)


if __name__ == "__main__":
    app.run(debug=True)