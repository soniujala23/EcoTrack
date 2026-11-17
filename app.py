from flask import Flask, render_template, jsonify, request
import sqlite3
import random
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
DB_PATH = Path(__file__).with_name("database.db")

SEED_BINS = [
    ("BIN-001", "College", "26.8500", "75.8000", 35, 22, 18),
    ("BIN-002", "Canteen", "26.8510", "75.8015", 78, 65, 48),
    ("BIN-003", "Hostel", "26.8485", "75.8030", 96, 82, 85),
    ("BIN-004", "Library", "26.8520", "75.7980", 54, 35, 27),
    ("BIN-005", "Main Gate", "26.8490", "75.7960", 18, 15, 12),
    ("BIN-006", "Parking", "26.8530", "75.8040", 67, 43, 39),
]

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def status_for(level):
    if level >= 90:
        return "Critical"
    if level >= 75:
        return "Warning"
    return "Normal"

def init_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS bins (
                id TEXT PRIMARY KEY, location TEXT NOT NULL,
                lat REAL, lon REAL, fill INTEGER, moisture INTEGER,
                gas INTEGER, status TEXT, updated_at TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_id TEXT, fill INTEGER, moisture INTEGER,
                gas INTEGER, recorded_at TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_id TEXT, location TEXT, message TEXT,
                severity TEXT, created_at TEXT, acknowledged INTEGER DEFAULT 0
            )
        """)
        count = con.execute("SELECT COUNT(*) FROM bins").fetchone()[0]
        if count == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for row in SEED_BINS:
                bid, loc, lat, lon, fill, moisture, gas = row
                status = status_for(fill)
                con.execute("INSERT INTO bins VALUES (?,?,?,?,?,?,?,?,?)",
                            (bid, loc, float(lat), float(lon), fill, moisture, gas, status, now))
                con.execute("INSERT INTO readings(bin_id,fill,moisture,gas,recorded_at) VALUES(?,?,?,?,?)",
                            (bid, fill, moisture, gas, now))
                if status != "Normal":
                    msg = "Bin is almost full!" if status == "Critical" else "Bin needs collection soon."
                    con.execute("INSERT INTO alerts(bin_id,location,message,severity,created_at) VALUES(?,?,?,?,?)",
                                (bid, loc, msg, status, now))

def simulate():
    """Update virtual sensor readings. These are generated values, not physical measurements."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect() as con:
        bins = con.execute("SELECT * FROM bins").fetchall()
        for b in bins:
            # Fill level generally rises slowly. It can occasionally dip slightly.
            delta = random.choices([0, 1, 2, 3, -1], weights=[20, 35, 25, 12, 8])[0]
            fill = max(0, min(100, b["fill"] + delta))
            moisture = max(0, min(100, b["moisture"] + random.randint(-3, 3)))
            gas = max(0, min(100, b["gas"] + random.randint(-4, 4)))
            status = status_for(fill)
            con.execute("UPDATE bins SET fill=?, moisture=?, gas=?, status=?, updated_at=? WHERE id=?",
                        (fill, moisture, gas, status, now, b["id"]))
            con.execute("INSERT INTO readings(bin_id,fill,moisture,gas,recorded_at) VALUES(?,?,?,?,?)",
                        (b["id"], fill, moisture, gas, now))
            # Avoid creating the same active alert repeatedly.
            active = con.execute(
                "SELECT id FROM alerts WHERE bin_id=? AND acknowledged=0 AND severity=?",
                (b["id"], status)
            ).fetchone()
            if status in ("Warning", "Critical") and not active:
                message = "Bin is almost full!" if status == "Critical" else "Bin needs collection soon."
                con.execute("INSERT INTO alerts(bin_id,location,message,severity,created_at) VALUES(?,?,?,?,?)",
                            (b["id"], b["location"], message, status, now))
        # Keep the local demo database small.
        con.execute("DELETE FROM readings WHERE id NOT IN (SELECT id FROM readings ORDER BY id DESC LIMIT 1500)")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/dashboard")
def dashboard_data():
    simulate()
    with connect() as con:
        bins = [dict(r) for r in con.execute("SELECT * FROM bins ORDER BY id").fetchall()]
        alerts = [dict(r) for r in con.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT 8").fetchall()]
        total = len(bins)
        critical = sum(b["status"] == "Critical" for b in bins)
        warning = sum(b["status"] == "Warning" for b in bins)
        normal = sum(b["status"] == "Normal" for b in bins)
        active_alerts = con.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged=0").fetchone()[0]
        # Recent trend: average fill level grouped by minute.
        trend = con.execute("""
            SELECT substr(recorded_at,1,16) AS minute, ROUND(AVG(fill),1) AS average
            FROM readings GROUP BY minute ORDER BY minute DESC LIMIT 12
        """).fetchall()
        weekly = con.execute("""
            SELECT substr(recorded_at,1,10) AS day, ROUND(AVG(fill),1) AS average
            FROM readings GROUP BY day ORDER BY day DESC LIMIT 7
        """).fetchall()
    return jsonify({
        "bins": bins, "alerts": alerts,
        "summary": {"total": total, "critical": critical, "warning": warning,
                    "normal": normal, "active_alerts": active_alerts},
        "trend": [dict(r) for r in reversed(trend)],
        "weekly": [dict(r) for r in reversed(weekly)],
        "updated": datetime.now().strftime("%I:%M:%S %p"),
        "simulation": True
    })

@app.route("/api/collect/<bin_id>", methods=["POST"])
def collect_bin(bin_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect() as con:
        b = con.execute("SELECT * FROM bins WHERE id=?", (bin_id,)).fetchone()
        if not b:
            return jsonify({"error": "Bin not found"}), 404
        con.execute("UPDATE bins SET fill=0, status='Normal', updated_at=? WHERE id=?", (now, bin_id))
        con.execute("UPDATE alerts SET acknowledged=1 WHERE bin_id=? AND acknowledged=0", (bin_id,))
        con.execute("INSERT INTO readings(bin_id,fill,moisture,gas,recorded_at) VALUES(?,?,?,?,?)",
                    (bin_id, 0, b["moisture"], b["gas"], now))
    return jsonify({"ok": True, "message": f"{bin_id} marked as collected"})

@app.route("/api/alerts/acknowledge/<int:alert_id>", methods=["POST"])
def acknowledge_alert(alert_id):
    with connect() as con:
        con.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))
    return jsonify({"ok": True})

@app.route("/api/bins", methods=["POST"])
def add_bin():
    data = request.get_json(silent=True) or {}
    location = (data.get("location") or "").strip()
    if not location:
        return jsonify({"error": "Location is required"}), 400
    with connect() as con:
        number = con.execute("SELECT COUNT(*) FROM bins").fetchone()[0] + 1
        bin_id = f"BIN-{number:03d}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        con.execute("INSERT INTO bins VALUES (?,?,?,?,?,?,?,?,?)",
                    (bin_id, location, float(data.get("lat", 26.85)),
                     float(data.get("lon", 75.80)), 0, 0, 0, "Normal", now))
    return jsonify({"ok": True, "id": bin_id})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
