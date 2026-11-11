
from flask import Flask, render_template, request, jsonify
import secrets
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

DB = "gps.db"


def database():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = database()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            share_token TEXT PRIMARY KEY,
            view_token TEXT UNIQUE,
            latitude REAL,
            longitude REAL,
            updated_at TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create():
    share_token = secrets.token_urlsafe(24)
    view_token = secrets.token_urlsafe(24)

    conn = database()
    conn.execute("""
        INSERT INTO locations
        (share_token, view_token)
        VALUES (?, ?)
    """, (share_token, view_token))
    conn.commit()
    conn.close()

    return jsonify({
        "share_url": request.host_url + "share/" + share_token,
        "view_url": request.host_url + "view/" + view_token
    })


@app.route("/share/<token>")
def share(token):
    conn = database()
    data = conn.execute(
        "SELECT active FROM locations WHERE share_token=?",
        (token,)
    ).fetchone()
    conn.close()

    if not data or not data["active"]:
        return "Sesi tidak tersedia atau sudah dihentikan.", 404

    return render_template("share.html", token=token)


@app.route("/view/<token>")
def view(token):
    conn = database()
    data = conn.execute(
        "SELECT share_token FROM locations WHERE view_token=?",
        (token,)
    ).fetchone()
    conn.close()

    if not data:
        return "Tautan tidak valid.", 404

    return render_template("view.html", token=token)


@app.route("/update/<token>", methods=["POST"])
def update(token):
    data = request.get_json(silent=True) or {}

    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Koordinat tidak valid"}), 400

    conn = database()
    result = conn.execute("""
        UPDATE locations
        SET latitude=?, longitude=?, updated_at=?
        WHERE share_token=? AND active=1
    """, (
        lat, lon, datetime.utcnow().isoformat(),
        token
    ))
    conn.commit()
    conn.close()

    if result.rowcount == 0:
        return jsonify({"error": "Sesi sudah tidak aktif"}), 404

    return jsonify({"status": "success"})


@app.route("/location/<token>")
def location(token):
    conn = database()
    data = conn.execute("""
        SELECT latitude, longitude, updated_at, active
        FROM locations
        WHERE view_token=?
    """, (token,)).fetchone()
    conn.close()

    if not data:
        return jsonify({"error": "Tidak ditemukan"}), 404

    return jsonify(dict(data))


@app.route("/stop/<token>", methods=["POST"])
def stop(token):
    conn = database()
    conn.execute("""
        UPDATE locations SET active=0
        WHERE share_token=?
    """, (token,))
    conn.commit()
    conn.close()

    return jsonify({"status": "stopped"})


init_db()

if __name__ == "__main__":
    app.run(debug=False)
