#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPL 2026-27 Ultimate Tournament Manager
Single-file Flask application for Termux.

Features:
- 6 predefined NPL teams
- All Players directory across the whole tournament
- Team/player photo and logo uploads
- Live match center
- Goal, Assist, Foul, Yellow Card, Red Card events
- Player of the Match for every match
- Match history + match story + delete
- Player statistics and POTM count
- Points table
- Player purchase/transfer fee
- Team income/expense ledger
- Sponsors
- Facebook Page settings
- SQLite WAL + busy timeout + retry protection

Run:
    pip install flask
    python NPL_2026_27_Tournament_Manager_Ultimate.py
Then open:
    http://127.0.0.1:8080
"""

import os
import sqlite3
import time
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, render_template_string,
    jsonify, flash, send_from_directory, session
)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "npl_tracker_ultimate.db")
MEDIA_DIR = os.path.join(BASE_DIR, "npl_media")
PLAYER_DIR = os.path.join(MEDIA_DIR, "players")
TEAM_DIR = os.path.join(MEDIA_DIR, "teams")
SPONSOR_DIR = os.path.join(MEDIA_DIR, "sponsors")

for folder in (MEDIA_DIR, PLAYER_DIR, TEAM_DIR, SPONSOR_DIR):
    os.makedirs(folder, exist_ok=True)

app = Flask(__name__)
app.secret_key = "npl-2026-27-local-secret"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

TEAMS = [
    "Noyagoan Friends Society",
    "Noyagoan Gentlemant",
    "FC Noyagoan",
    "Noyagaon Seven Star",
    "The Vanquished Of Noyagoan",
    "Noyagaon Flower's",
]

ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}



ADMIN_USER = "admin"
ADMIN_PASSWORD = "npl2026"


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def execute(sql, params=(), commit=False, retries=5):
    last = None
    for i in range(retries):
        conn = None
        try:
            conn = get_db()
            cur = conn.execute(sql, params)
            if commit:
                conn.commit()
            return cur
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e).lower():
                raise
            time.sleep(0.25 * (i + 1))
        finally:
            if conn:
                conn.close()
    raise last


def query(sql, params=()):
    conn = get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def query_one(sql, params=()):
    conn = get_db()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def init_db():
    conn = get_db()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            logo TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            jersey TEXT DEFAULT '',
            photo TEXT DEFAULT '',
            purchase_fee REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            match_date TEXT DEFAULT '',
            match_time TEXT DEFAULT '',
            status TEXT DEFAULT 'scheduled',
            home_score INTEGER DEFAULT 0,
            away_score INTEGER DEFAULT 0,
            story TEXT DEFAULT '',
            potm_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(home_team_id) REFERENCES teams(id),
            FOREIGN KEY(away_team_id) REFERENCES teams(id),
            FOREIGN KEY(potm_id) REFERENCES players(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            player_id INTEGER,
            event_type TEXT NOT NULL,
            minute TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS finance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            entry_type TEXT NOT NULL,
            category TEXT DEFAULT '',
            amount REAL NOT NULL DEFAULT 0,
            note TEXT DEFAULT '',
            entry_date TEXT DEFAULT '',
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sponsors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL DEFAULT 0,
            logo TEXT DEFAULT '',
            contact TEXT DEFAULT '',
            note TEXT DEFAULT ''
        );


        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT DEFAULT '',
            photo TEXT DEFAULT '',
            note TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS referees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            note TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS match_referees (
            match_id INTEGER NOT NULL,
            referee_id INTEGER NOT NULL,
            role TEXT DEFAULT 'Referee',
            PRIMARY KEY(match_id, referee_id),
            FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
            FOREIGN KEY(referee_id) REFERENCES referees(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS substitutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            player_in_id INTEGER,
            player_out_id INTEGER,
            minute TEXT DEFAULT '',
            note TEXT DEFAULT '',
            FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
            FOREIGN KEY(player_in_id) REFERENCES players(id) ON DELETE SET NULL,
            FOREIGN KEY(player_out_id) REFERENCES players(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS goalkeeper_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            saves INTEGER DEFAULT 0,
            goals_conceded INTEGER DEFAULT 0,
            penalty_saves INTEGER DEFAULT 0,
            clean_sheet INTEGER DEFAULT 0,
            UNIQUE(match_id, player_id),
            FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            player_id INTEGER,
            team_id INTEGER,
            note TEXT DEFAULT '',
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE SET NULL,
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            photo TEXT DEFAULT '',
            published_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            caption TEXT DEFAULT '',
            photo TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
        """)

        # Backward-compatible columns for the original database.
        for sql in (
            "ALTER TABLE matches ADD COLUMN venue_id INTEGER",
            "ALTER TABLE matches ADD COLUMN referee_report TEXT DEFAULT ''",
            "ALTER TABLE matches ADD COLUMN referee_id INTEGER",
        ):
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass

        for team in TEAMS:
            conn.execute("INSERT OR IGNORE INTO teams(name) VALUES (?)", (team,))
        conn.commit()
    finally:
        conn.close()


def save_upload(file, folder):
    if not file or not file.filename:
        return ""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED:
        return ""
    filename = secure_filename(file.filename)
    stem, suffix = os.path.splitext(filename)
    filename = f"{stem}_{int(time.time()*1000)}{suffix.lower()}"
    file.save(os.path.join(folder, filename))
    return filename


def stat_counts(player_id):
    row = query_one("""
        SELECT
          COUNT(DISTINCT CASE WHEN e.event_type IN ('goal','assist','foul','yellow','red') THEN e.match_id END) matches,
          SUM(CASE WHEN e.event_type='goal' THEN 1 ELSE 0 END) goals,
          SUM(CASE WHEN e.event_type='assist' THEN 1 ELSE 0 END) assists,
          SUM(CASE WHEN e.event_type='foul' THEN 1 ELSE 0 END) fouls,
          SUM(CASE WHEN e.event_type='yellow' THEN 1 ELSE 0 END) yellow,
          SUM(CASE WHEN e.event_type='red' THEN 1 ELSE 0 END) red,
          (SELECT COUNT(*) FROM matches m WHERE m.potm_id=?) potm
        FROM events e WHERE e.player_id=?
    """, (player_id, player_id))
    return dict(row) if row else {}


@app.template_filter("money")
def money(v):
    try:
        return f"৳{float(v or 0):,.0f}"
    except Exception:
        return "৳0"


@app.context_processor
def inject():
    return {
        "teams": query("SELECT * FROM teams ORDER BY name"),
        "now": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }


STYLE = """
<style>
:root{--bg:#08111f;--card:#101d31;--card2:#14243c;--text:#eef5ff;--muted:#9fb0c7;--accent:#31d17c;--gold:#ffd166;--danger:#ff5c67;--line:#243650}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:linear-gradient(145deg,#06101d,#0c1b2e);color:var(--text)}
a{color:inherit;text-decoration:none}.wrap{max-width:1250px;margin:auto;padding:18px}.top{position:sticky;top:0;z-index:5;background:#08111fe8;backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.nav{max-width:1250px;margin:auto;padding:12px 18px;display:flex;gap:8px;align-items:center;overflow:auto}.brand{font-weight:900;font-size:20px;margin-right:12px;white-space:nowrap}.nav a{padding:9px 12px;border-radius:10px;color:var(--muted);white-space:nowrap}.nav a:hover{background:var(--card);color:#fff}
.hero{padding:28px 0}.hero h1{font-size:clamp(30px,5vw,54px);margin:0 0 6px}.hero p{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.card{background:linear-gradient(160deg,var(--card),#0c1829);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 12px 30px #0003}.stat{font-size:30px;font-weight:900}.muted{color:var(--muted)}.gold{color:var(--gold)}.green{color:var(--accent)}.danger{color:var(--danger)}
table{width:100%;border-collapse:collapse}th,td{padding:11px 9px;border-bottom:1px solid var(--line);text-align:left}th{color:#aebed2;font-size:12px;text-transform:uppercase}
input,select,textarea{width:100%;padding:11px 12px;background:#091526;color:#fff;border:1px solid var(--line);border-radius:10px;outline:none}textarea{min-height:100px}.form{display:grid;gap:10px}.btn{display:inline-block;border:0;border-radius:10px;padding:10px 14px;background:var(--accent);color:#04110a;font-weight:800;cursor:pointer}.btn.secondary{background:#20324d;color:#fff}.btn.danger{background:var(--danger);color:#210307}.btn.gold{background:var(--gold);color:#211a00}.actions{display:flex;gap:8px;flex-wrap:wrap}
.team-logo,.avatar{width:56px;height:56px;border-radius:50%;object-fit:cover;background:#17283f;border:1px solid var(--line)}.avatar.big{width:90px;height:90px}.team-logo.big{width:78px;height:78px}.row{display:flex;align-items:center;gap:12px}.space{display:flex;justify-content:space-between;align-items:center;gap:12px}
.badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#20324d;color:#c8d7e9;font-size:12px}.live{background:#5d1520;color:#ff9ca4}.event{border-left:3px solid var(--accent);padding:8px 12px;margin:7px 0;background:#0c192b;border-radius:8px}
.score{font-size:48px;font-weight:950;text-align:center}.versus{text-align:center;color:var(--muted);font-weight:800}.teamname{text-align:center;font-weight:800}.flash{padding:12px 14px;border-radius:10px;background:#123c29;border:1px solid #206d49;margin-bottom:12px}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}.nav{padding-left:10px}.wrap{padding:12px}}
@media(max-width:520px){.grid{grid-template-columns:1fr 1fr}.card{padding:13px}.stat{font-size:24px}th,td{padding:8px 5px;font-size:13px}.hide-sm{display:none}}
</style>
"""

BASE = """
<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} — NPL 2026-27</title>""" + STYLE + """</head><body>
<div class="top"><div class="nav">
<a class="brand" href="/">⚽ NPL 2026–27</a>
<a href="/">Dashboard</a><a href="/public">🌐 Public</a><a href="/live">🔴 Live</a><a href="/players">All Players</a><a href="/teams">Teams</a><a href="/matches">Matches</a><a href="/fixtures">Fixtures</a><a href="/points">Points</a><a href="/stats">Stats</a><a href="/awards">Awards</a><a href="/discipline">Cards</a><a href="/venues">Venues</a><a href="/referees">Referees</a><a href="/news">News</a><a href="/sponsors">Sponsors</a><a href="/finance">Finance</a><a href="/settings">Settings</a>{% if session.get("admin") %}<a href="/logout">Logout</a>{% else %}<a href="/login">Admin</a>{% endif %}
</div></div><main class="wrap">
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
{{body|safe}}
</main></body></html>
"""


def page(title, body, **ctx):
    return render_template_string(BASE, title=title, body=render_template_string(body, **ctx))




@app.route("/public")
def public_portal():
    matches = query("""SELECT m.*,h.name home_name,a.name away_name,v.name venue_name
                       FROM matches m JOIN teams h ON h.id=m.home_team_id
                       JOIN teams a ON a.id=m.away_team_id
                       LEFT JOIN venues v ON v.id=m.venue_id
                       ORDER BY CASE WHEN m.status='live' THEN 0 WHEN m.status='scheduled' THEN 1 ELSE 2 END,
                                m.match_date,m.match_time,m.id LIMIT 20""")
    top_scorers = query("""SELECT p.name,t.name team_name,
                           COALESCE(SUM(CASE WHEN e.event_type='goal' THEN 1 ELSE 0 END),0) goals,
                           COALESCE(SUM(CASE WHEN e.event_type='assist' THEN 1 ELSE 0 END),0) assists
                           FROM players p JOIN teams t ON t.id=p.team_id
                           LEFT JOIN events e ON e.player_id=p.id
                           GROUP BY p.id ORDER BY goals DESC,assists DESC,p.name LIMIT 10""")
    teams = query("SELECT * FROM teams ORDER BY name")
    news_rows = query("SELECT * FROM news ORDER BY id DESC LIMIT 6")
    body = """
    <div class="hero">
      <div><span class="badge live">NPL 2026–27</span>
      <h1>⚽ NPL Night Football Premier League</h1>
      <p>🌐 Public Live Portal — সবাই দেখতে পারবেন</p></div>
      <a class="btn" href="/login">🔐 Admin Panel</a>
    </div>
    <div class="grid2">
      <div class="card"><h2>🔴 Live / Upcoming Matches</h2>
      {% for m in matches %}
        <div class="card soft" style="margin:8px 0">
          <div class="space"><b>{{m.home_name}} vs {{m.away_name}}</b>
          <span class="badge {% if m.status=='live' %}live{% endif %}">{{m.status}}</span></div>
          <p class="muted">📅 {{m.match_date}} {{m.match_time}} • 🏟️ {{m.venue_name or 'Venue TBA'}}</p>
          <a class="btn secondary" href="/matches/{{m.id}}">View Match</a>
        </div>
      {% else %}<p class="muted">কোনো ম্যাচ নেই।</p>{% endfor %}
      </div>
      <div class="card"><h2>🥇 Top Scorers</h2>
      {% for p in top_scorers %}
        <p>{{loop.index}}. <b>{{p.name}}</b> — {{p.team_name}}
        <span class="gold">{{p.goals}} ⚽</span> {{p.assists}} 🎯</p>
      {% else %}<p class="muted">কোনো player data নেই।</p>{% endfor %}
      </div>
    </div>
    <div class="card" style="margin-top:14px"><h2>👥 Teams</h2><div class="grid">
      {% for t in teams %}<div class="card soft"><h3>{{t.name}}</h3>
      <a class="btn secondary" href="/teams/{{t.id}}">View Team</a></div>{% endfor %}
    </div></div>
    <div class="card" style="margin-top:14px"><h2>📢 Latest News</h2>
      {% for n in news_rows %}<div style="padding:10px 0;border-bottom:1px solid #eee">
      <h3>{{n.title}}</h3><p>{{n.body}}</p></div>
      {% else %}<p class="muted">News নেই।</p>{% endfor %}
    </div>
    """
    return page("NPL Public Portal", body, matches=matches, top_scorers=top_scorers,
                teams=teams, news_rows=news_rows)


@app.route("/live")
def public_live():
    rows = query("""SELECT m.*,h.name home_name,a.name away_name
                    FROM matches m JOIN teams h ON h.id=m.home_team_id
                    JOIN teams a ON a.id=m.away_team_id
                    WHERE m.status='live' ORDER BY m.id DESC""")
    body = """
    <h1>🔴 LIVE MATCH CENTER</h1>
    {% for m in rows %}
    <div class="card"><h2>{{m.home_name}} {{m.home_score}} — {{m.away_score}} {{m.away_name}}</h2>
    <a class="btn" href="/matches/{{m.id}}">Open Live Match</a></div>
    {% else %}<div class="card"><h2>এই মুহূর্তে কোনো Live Match নেই।</h2></div>{% endfor %}
    """
    return page("Live Match Center", body, rows=rows)


@app.route("/public/players")
def public_players():
    rows = query("""SELECT p.name,t.name team_name,
        COALESCE(SUM(CASE WHEN e.event_type='goal' THEN 1 ELSE 0 END),0) goals,
        COALESCE(SUM(CASE WHEN e.event_type='assist' THEN 1 ELSE 0 END),0) assists,
        COALESCE(SUM(CASE WHEN e.event_type='yellow' THEN 1 ELSE 0 END),0) yellow,
        COALESCE(SUM(CASE WHEN e.event_type='red' THEN 1 ELSE 0 END),0) red,
        (SELECT COUNT(*) FROM matches m WHERE m.potm_id=p.id) potm
        FROM players p JOIN teams t ON t.id=p.team_id LEFT JOIN events e ON e.player_id=p.id
        GROUP BY p.id ORDER BY t.name,p.name""")
    body = """
    <h1>👥 All Tournament Players</h1>
    <div class="card"><table><tr><th>Player</th><th>Team</th><th>⚽</th><th>🎯</th>
    <th>🏅 POTM</th><th>🟨</th><th>🟥</th></tr>
    {% for p in rows %}<tr><td>{{p.name}}</td><td>{{p.team_name}}</td><td>{{p.goals}}</td>
    <td>{{p.assists}}</td><td>{{p.potm}}</td><td>{{p.yellow}}</td><td>{{p.red}}</td></tr>{% endfor %}
    </table></div>
    """
    return page("Public Players", body, rows=rows)


@app.route("/public/points")
def public_points():
    return redirect(url_for("points"))


@app.route("/public/stats")
def public_stats():
    return redirect(url_for("stats"))


@app.route("/public/awards")
def public_awards():
    return redirect(url_for("awards"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(request.args.get("next") or url_for("index"))
        flash("ভুল username বা password।")
    body = """
    <div style="max-width:460px;margin:70px auto"><div class="card">
    <h1>🔐 NPL Admin Login</h1><p class="muted">ডাটা পরিবর্তন করার আগে Admin Login করুন।</p>
    <form class="form" method="post"><input name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button class="btn">Login</button></form>
    <p class="muted">প্রথমে: admin / npl2026</p></div></div>
    """
    return page("Admin Login", body)


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/")
def index():
    players = query("SELECT COUNT(*) c FROM players")[0]["c"]
    matches = query("SELECT COUNT(*) c FROM matches")[0]["c"]
    finished = query("SELECT COUNT(*) c FROM matches WHERE status='finished'")[0]["c"]
    potm = query("SELECT COUNT(*) c FROM matches WHERE potm_id IS NOT NULL")[0]["c"]
    recent = query("""
      SELECT m.*, h.name home_name, a.name away_name, p.name potm_name
      FROM matches m JOIN teams h ON h.id=m.home_team_id JOIN teams a ON a.id=m.away_team_id
      LEFT JOIN players p ON p.id=m.potm_id ORDER BY m.id DESC LIMIT 8
    """)
    body = """
    <section class="hero"><div class="badge">৮ম বর্ষ • 2026–2027</div><p><a class="btn" href="/public">🌐 Open Public Tournament Website</a></p><h1>NPL Night Football Premier League</h1>
    <p>Powered By: Sky Star Boys Club (Noyagaon) • Live Tournament Manager</p></section>
    <div class="grid">
      <div class="card"><div class="muted">মোট দল</div><div class="stat">{{teams|length}}</div></div>
      <div class="card"><div class="muted">সব খেলোয়াড়</div><div class="stat">{{players}}</div></div>
      <div class="card"><div class="muted">মোট ম্যাচ</div><div class="stat">{{matches}}</div></div>
      <div class="card"><div class="muted">Player of the Match</div><div class="stat gold">{{potm}}</div></div>
    </div>
    <div class="space" style="margin:24px 0 12px"><h2>সাম্প্রতিক ম্যাচ</h2><a class="btn" href="/matches/new">+ নতুন ম্যাচ</a></div>
    <div class="grid2">
    {% for m in recent %}
      <a class="card" href="/matches/{{m.id}}"><div class="space"><span class="badge {% if m.status=='live' %}live{% endif %}">{{m.status}}</span><span class="muted">{{m.match_date}} {{m.match_time}}</span></div>
      <div class="teamname">{{m.home_name}}</div><div class="score">{{m.home_score}} – {{m.away_score}}</div><div class="teamname">{{m.away_name}}</div>
      {% if m.potm_name %}<p class="gold">🏅 {{m.potm_name}}</p>{% endif %}</a>
    {% else %}<div class="card">এখনও কোনো ম্যাচ তৈরি করা হয়নি।</div>{% endfor %}
    </div>
    """
    return page("Dashboard", body, players=players, matches=matches, finished=finished, potm=potm, recent=recent)


@app.route("/players")
def players():
    team_id = request.args.get("team_id")
    sql = """SELECT p.*, t.name team_name FROM players p JOIN teams t ON t.id=p.team_id"""
    params = []
    if team_id:
        sql += " WHERE p.team_id=?"
        params.append(team_id)
    sql += " ORDER BY t.name,p.name"
    rows = query(sql, params)
    data = []
    for p in rows:
        s = stat_counts(p["id"])
        data.append({**dict(p), **s})
    body = """
    <div class="space"><div><h1>👥 All Players</h1><p class="muted">পুরো টুর্নামেন্টের সব দলের সব খেলোয়াড় এক জায়গায়</p></div><a class="btn" href="/players/new">+ খেলোয়াড় যোগ</a></div>
    <form class="card" method="get" style="margin-bottom:14px"><select name="team_id" onchange="this.form.submit()"><option value="">সব দল</option>{% for t in teams %}<option value="{{t.id}}" {% if request.args.get('team_id')==t.id|string %}selected{% endif %}>{{t.name}}</option>{% endfor %}</select></form>
    <div class="grid2">
    {% for p in rows %}<div class="card"><div class="row">
      {% if p.photo %}<img class="avatar" src="/media/players/{{p.photo}}">{% else %}<div class="avatar"></div>{% endif %}
      <div><h3 style="margin:0">{{p.name}}</h3><div class="muted">{{p.team_name}} {% if p.jersey %}• #{{p.jersey}}{% endif %}</div></div>
    </div><div class="grid" style="margin-top:14px">
      <div><span class="muted">Matches</span><br><b>{{p.matches or 0}}</b></div><div><span class="muted">Goals</span><br><b>{{p.goals or 0}}</b></div><div><span class="muted">Assists</span><br><b>{{p.assists or 0}}</b></div><div><span class="muted">POTM</span><br><b class="gold">{{p.potm or 0}}</b></div>
    </div><p class="muted">Foul {{p.fouls or 0}} • 🟨 {{p.yellow or 0}} • 🟥 {{p.red or 0}}</p><div class="actions"><a class="btn secondary" href="/players/{{p.id}}/edit">Edit</a></div></div>
    {% else %}<div class="card">কোনো খেলোয়াড় নেই।</div>{% endfor %}
    </div>
    """
    return page("All Players", body, rows=data)


@app.route("/players/new", methods=["GET","POST"])
@admin_required
def new_player():
    if request.method == "POST":
        photo = save_upload(request.files.get("photo"), PLAYER_DIR)
        execute("INSERT INTO players(team_id,name,jersey,photo,purchase_fee) VALUES (?,?,?,?,?)",
                (request.form["team_id"], request.form["name"], request.form.get("jersey",""), photo, float(request.form.get("purchase_fee") or 0)), True)
        flash("খেলোয়াড় যোগ হয়েছে।")
        return redirect(url_for("players"))
    body = """
    <h1>➕ নতুন খেলোয়াড়</h1><form class="card form" method="post" enctype="multipart/form-data">
    <label>দল<select name="team_id">{% for t in teams %}<option value="{{t.id}}">{{t.name}}</option>{% endfor %}</select></label>
    <label>নাম<input name="name" required></label><label>জার্সি নম্বর<input name="jersey"></label>
    <label>ক্রয়/ট্রান্সফার মূল্য (৳)<input type="number" step="0.01" name="purchase_fee" value="0"></label>
    <label>ছবি<input type="file" name="photo" accept="image/*"></label><button class="btn">Save Player</button></form>
    """
    return page("New Player", body)


@app.route("/players/<int:pid>/edit", methods=["GET","POST"])
@admin_required
def edit_player(pid):
    p = query_one("SELECT * FROM players WHERE id=?", (pid,))
    if not p: return "Player not found", 404
    if request.method == "POST":
        photo = p["photo"]
        new_photo = save_upload(request.files.get("photo"), PLAYER_DIR)
        if new_photo: photo = new_photo
        execute("""UPDATE players SET team_id=?,name=?,jersey=?,photo=?,purchase_fee=? WHERE id=?""",
                (request.form["team_id"], request.form["name"], request.form.get("jersey",""), photo,
                 float(request.form.get("purchase_fee") or 0), pid), True)
        flash("খেলোয়াড় আপডেট হয়েছে।")
        return redirect(url_for("players"))
    body = """
    <h1>✏️ খেলোয়াড় সম্পাদনা</h1><form class="card form" method="post" enctype="multipart/form-data">
    <label>দল<select name="team_id">{% for t in teams %}<option value="{{t.id}}" {% if t.id==p.team_id %}selected{% endif %}>{{t.name}}</option>{% endfor %}</select></label>
    <label>নাম<input name="name" value="{{p.name}}" required></label><label>জার্সি নম্বর<input name="jersey" value="{{p.jersey}}"></label>
    <label>ক্রয়/ট্রান্সফার মূল্য (৳)<input type="number" step="0.01" name="purchase_fee" value="{{p.purchase_fee}}"></label>
    <label>নতুন ছবি<input type="file" name="photo" accept="image/*"></label><button class="btn">Update</button></form>
    """
    return page("Edit Player", body, p=p)


@app.route("/teams")
def team_list():
    rows = query("""SELECT t.*,COUNT(p.id) player_count FROM teams t LEFT JOIN players p ON p.team_id=t.id GROUP BY t.id ORDER BY t.name""")
    body = """
    <h1>🏳️ Teams</h1><div class="grid2">{% for t in rows %}<div class="card row">
    {% if t.logo %}<img class="team-logo big" src="/media/teams/{{t.logo}}">{% else %}<div class="team-logo big"></div>{% endif %}
    <div><h2>{{t.name}}</h2><p class="muted">{{t.player_count}} players</p><a class="btn secondary" href="/teams/{{t.id}}/edit">Team Settings</a></div></div>{% endfor %}</div>
    """
    return page("Teams", body, rows=rows)


@app.route("/teams/<int:tid>/edit", methods=["GET","POST"])
@admin_required
def edit_team(tid):
    t = query_one("SELECT * FROM teams WHERE id=?", (tid,))
    if not t: return "Team not found",404
    if request.method=="POST":
        logo=t["logo"]; new=save_upload(request.files.get("logo"),TEAM_DIR)
        if new: logo=new
        execute("UPDATE teams SET logo=? WHERE id=?", (logo,tid), True)
        flash("Team logo updated.")
        return redirect(url_for("team_list"))
    body="""
    <h1>🏳️ {{t.name}}</h1><form class="card form" method="post" enctype="multipart/form-data">
    <label>Team Logo<input type="file" name="logo" accept="image/*"></label><button class="btn">Save Logo</button></form>
    """
    return page("Team Settings",body,t=t)


@app.route("/matches")
def match_list():
    rows=query("""SELECT m.*,h.name home_name,a.name away_name,p.name potm_name
    FROM matches m JOIN teams h ON h.id=m.home_team_id JOIN teams a ON a.id=m.away_team_id
    LEFT JOIN players p ON p.id=m.potm_id ORDER BY COALESCE(m.match_date,'') DESC,m.id DESC""")
    body="""
    <div class="space"><h1>⚡ Matches</h1><a class="btn" href="/matches/new">+ নতুন ম্যাচ</a></div>
    {% for m in rows %}<div class="card" style="margin-bottom:10px"><div class="space"><span class="badge {% if m.status=='live' %}live{% endif %}">{{m.status}}</span><span class="muted">{{m.match_date}} {{m.match_time}}</span></div>
    <div class="grid2"><div class="teamname">{{m.home_name}}<div class="score">{{m.home_score}}</div></div><div class="teamname">{{m.away_name}}<div class="score">{{m.away_score}}</div></div></div>
    {% if m.potm_name %}<p class="gold">🏅 Player of the Match: <b>{{m.potm_name}}</b></p>{% endif %}
    <div class="actions"><a class="btn" href="/matches/{{m.id}}">Open Match</a><form method="post" action="/matches/{{m.id}}/delete" onsubmit="return confirm('এই ম্যাচ ও এর সব events মুছে ফেলবেন?')"><button class="btn danger">Delete Match</button></form></div></div>
    {% else %}<div class="card">কোনো ম্যাচ নেই।</div>{% endfor %}
    """
    return page("Matches",body,rows=rows)


@app.route("/matches/new", methods=["GET","POST"])
@admin_required
def new_match():
    if request.method=="POST":
        execute("""INSERT INTO matches(home_team_id,away_team_id,match_date,match_time,status,story)
        VALUES(?,?,?,?,?,?)""",(request.form["home_team_id"],request.form["away_team_id"],request.form.get("match_date",""),
        request.form.get("match_time",""),request.form.get("status","scheduled"),request.form.get("story","")),True)
        flash("নতুন ম্যাচ তৈরি হয়েছে।")
        return redirect(url_for("match_list"))
    body="""
    <h1>➕ নতুন ম্যাচ</h1><form class="card form" method="post">
    <label>Home Team<select name="home_team_id">{% for t in teams %}<option value="{{t.id}}">{{t.name}}</option>{% endfor %}</select></label>
    <label>Away Team<select name="away_team_id">{% for t in teams %}<option value="{{t.id}}">{{t.name}}</option>{% endfor %}</select></label>
    <div class="grid2"><label>তারিখ<input type="date" name="match_date"></label><label>সময়<input type="time" name="match_time"></label></div>
    <label>Status<select name="status"><option value="scheduled">Scheduled</option><option value="live">Live</option><option value="finished">Finished</option></select></label>
    <label>Match Story<textarea name="story" placeholder="ম্যাচের গল্প/বর্ণনা"></textarea></label><button class="btn">Create Match</button></form>
    """
    return page("New Match",body)


@app.route("/matches/<int:mid>")
def match_detail(mid):
    m=query_one("""SELECT m.*,h.name home_name,a.name away_name,p.name potm_name,p.photo potm_photo
    FROM matches m JOIN teams h ON h.id=m.home_team_id JOIN teams a ON a.id=m.away_team_id
    LEFT JOIN players p ON p.id=m.potm_id WHERE m.id=?""",(mid,))
    if not m:return "Match not found",404
    events=query("""SELECT e.*,p.name player_name,t.name team_name FROM events e LEFT JOIN players p ON p.id=e.player_id
    LEFT JOIN teams t ON t.id=p.team_id WHERE e.match_id=? ORDER BY e.id DESC""",(mid,))
    players=query("""SELECT p.*,t.name team_name FROM players p JOIN teams t ON t.id=p.team_id WHERE p.team_id IN (?,?) ORDER BY t.name,p.name""",(m["home_team_id"],m["away_team_id"]))
    body="""
    <div class="space"><div><span class="badge {% if m.status=='live' %}live{% endif %}">{{m.status}}</span><h1>{{m.home_name}} vs {{m.away_name}}</h1></div>
    <a class="btn secondary" href="/matches">← Matches</a></div>
    <div class="card"><div class="grid2"><div class="teamname">{{m.home_name}}<div class="score">{{m.home_score}}</div></div><div class="teamname">{{m.away_name}}<div class="score">{{m.away_score}}</div></div></div>
    <p class="muted" style="text-align:center">{{m.match_date}} {{m.match_time}}</p></div>
    <div class="grid2" style="margin-top:14px">
    <div class="card"><h2>⚡ Live Event যোগ</h2><form class="form" method="post" action="/matches/{{m.id}}/event">
      <select name="event_type"><option value="goal">⚽ Goal</option><option value="assist">🎯 Assist</option><option value="foul">⚠️ Foul</option><option value="yellow">🟨 Yellow Card</option><option value="red">🟥 Red Card</option></select>
      <select name="player_id"><option value="">Player নির্বাচন</option>{% for p in players %}<option value="{{p.id}}">{{p.name}} — {{p.team_name}}</option>{% endfor %}</select>
      <input name="minute" placeholder="মিনিট, যেমন 37'"><input name="note" placeholder="নোট (ঐচ্ছিক)"><button class="btn">Add Event</button></form></div>
    <div class="card"><h2>🏅 Player of the Match</h2><form class="form" method="post" action="/matches/{{m.id}}/potm">
      <select name="potm_id"><option value="">নির্বাচন করুন</option>{% for p in players %}<option value="{{p.id}}" {% if m.potm_id==p.id %}selected{% endif %}>{{p.name}} — {{p.team_name}}</option>{% endfor %}</select><button class="btn gold">Save POTM</button></form>
      {% if m.potm_name %}<p class="gold"><b>🏆 {{m.potm_name}}</b></p>{% endif %}</div></div>

    <div class="grid2" style="margin-top:14px">
    <div class="card"><h2>🔄 Substitution</h2><form class="form" method="post" action="/matches/{{m.id}}/substitution">
      <select name="player_out_id"><option value="">Player Out</option>{% for p in players %}<option value="{{p.id}}">{{p.name}} — {{p.team_name}}</option>{% endfor %}</select>
      <select name="player_in_id"><option value="">Player In</option>{% for p in players %}<option value="{{p.id}}">{{p.name}} — {{p.team_name}}</option>{% endfor %}</select>
      <input name="minute" placeholder="মিনিট"><input name="note" placeholder="Note"><button class="btn">Save Substitution</button>
    </form></div>
    <div class="card"><h2>🧤 Goalkeeper Stats</h2><form class="form" method="post" action="/matches/{{m.id}}/goalkeeper">
      <select name="player_id">{% for p in players %}<option value="{{p.id}}">{{p.name}} — {{p.team_name}}</option>{% endfor %}</select>
      <div class="grid"><input type="number" name="saves" placeholder="Saves"><input type="number" name="goals_conceded" placeholder="Conceded"><input type="number" name="penalty_saves" placeholder="Penalty Saves"><select name="clean_sheet"><option value="0">No Clean Sheet</option><option value="1">Clean Sheet</option></select></div>
      <button class="btn">Save GK Stats</button>
    </form></div></div>

    <div class="card" style="margin-top:14px"><h2>📖 Match Story</h2><form class="form" method="post" action="/matches/{{m.id}}/story"><textarea name="story">{{m.story or ''}}</textarea><button class="btn secondary">Save Story</button></form></div>
    <div class="card" style="margin-top:14px"><h2>📋 Live Events</h2>{% for e in events %}<div class="event"><b>{{e.event_type|upper}}</b> {% if e.minute %}• {{e.minute}}{% endif %} — {{e.player_name or 'Unknown'}} <span class="muted">({{e.team_name or ''}})</span>{% if e.note %}<div class="muted">{{e.note}}</div>{% endif %}<form method="post" action="/events/{{e.id}}/delete" style="margin-top:5px"><button class="btn danger">Delete</button></form></div>{% else %}<p class="muted">এখনও কোনো event নেই।</p>{% endfor %}</div>
    """
    return page("Match Center",body,m=m,events=events,players=players)


@app.route("/matches/<int:mid>/event",methods=["POST"])
@admin_required
def add_event(mid):
    event=request.form["event_type"]; pid=request.form.get("player_id") or None
    execute("INSERT INTO events(match_id,player_id,event_type,minute,note) VALUES(?,?,?,?,?)",
            (mid,pid,event,request.form.get("minute",""),request.form.get("note","")),True)
    # Recalculate goals from events.
    m=query_one("SELECT home_team_id,away_team_id FROM matches WHERE id=?",(mid,))
    hs=query_one("""SELECT COUNT(*) c FROM events e JOIN players p ON p.id=e.player_id
                    WHERE e.match_id=? AND e.event_type='goal' AND p.team_id=?""",(mid,m["home_team_id"]))["c"]
    aw=query_one("""SELECT COUNT(*) c FROM events e JOIN players p ON p.id=e.player_id
                    WHERE e.match_id=? AND e.event_type='goal' AND p.team_id=?""",(mid,m["away_team_id"]))["c"]
    execute("UPDATE matches SET home_score=?,away_score=? WHERE id=?",(hs,aw,mid),True)
    flash("Live event যোগ হয়েছে।")
    return redirect(url_for("match_detail",mid=mid))


@app.route("/events/<int:eid>/delete",methods=["POST"])
@admin_required
def delete_event(eid):
    e=query_one("SELECT match_id FROM events WHERE id=?",(eid,))
    if e:
        mid=e["match_id"]; execute("DELETE FROM events WHERE id=?",(eid,),True)
        m=query_one("SELECT home_team_id,away_team_id FROM matches WHERE id=?",(mid,))
        hs=query_one("""SELECT COUNT(*) c FROM events e JOIN players p ON p.id=e.player_id
                        WHERE e.match_id=? AND e.event_type='goal' AND p.team_id=?""",(mid,m["home_team_id"]))["c"]
        aw=query_one("""SELECT COUNT(*) c FROM events e JOIN players p ON p.id=e.player_id
                        WHERE e.match_id=? AND e.event_type='goal' AND p.team_id=?""",(mid,m["away_team_id"]))["c"]
        execute("UPDATE matches SET home_score=?,away_score=? WHERE id=?",(hs,aw,mid),True)
        return redirect(url_for("match_detail",mid=mid))
    return "Event not found",404


@app.route("/matches/<int:mid>/potm",methods=["POST"])
@admin_required
def set_potm(mid):
    execute("UPDATE matches SET potm_id=? WHERE id=?",(request.form.get("potm_id") or None,mid),True)
    flash("Player of the Match সংরক্ষণ হয়েছে।")
    return redirect(url_for("match_detail",mid=mid))


@app.route("/matches/<int:mid>/story",methods=["POST"])
@admin_required
def save_story(mid):
    execute("UPDATE matches SET story=? WHERE id=?",(request.form.get("story",""),mid),True)
    flash("Match Story সংরক্ষণ হয়েছে।")
    return redirect(url_for("match_detail",mid=mid))


@app.route("/matches/<int:mid>/delete",methods=["POST"])
@admin_required
def delete_match(mid):
    execute("DELETE FROM matches WHERE id=?",(mid,),True)
    flash("ম্যাচ ও তার সব events মুছে দেওয়া হয়েছে।")
    return redirect(url_for("match_list"))


@app.route("/points")
def points():
    rows=[]
    for t in query("SELECT * FROM teams ORDER BY name"):
        played=won=draw=lost=gf=ga=0
        ms=query("""SELECT * FROM matches WHERE status='finished' AND (home_team_id=? OR away_team_id=?)""",(t["id"],t["id"]))
        for m in ms:
            if m["home_team_id"]==t["id"]:
                gf+=m["home_score"];ga+=m["away_score"]
                if m["home_score"]>m["away_score"]:won+=1
                elif m["home_score"]==m["away_score"]:draw+=1
                else:lost+=1
            else:
                gf+=m["away_score"];ga+=m["home_score"]
                if m["away_score"]>m["home_score"]:won+=1
                elif m["home_score"]==m["away_score"]:draw+=1
                else:lost+=1
            played+=1
        rows.append(dict(name=t["name"],played=played,won=won,draw=draw,lost=lost,gf=gf,ga=ga,gd=gf-ga,points=won*3+draw))
    rows.sort(key=lambda x:(-x["points"],-x["gd"],-x["gf"],x["name"]))
    body="""
    <h1>🏆 Points Table</h1><div class="card"><table><tr><th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th></tr>
    {% for r in rows %}<tr><td><b>{{loop.index}}</b></td><td>{{r.name}}</td><td>{{r.played}}</td><td>{{r.won}}</td><td>{{r.draw}}</td><td>{{r.lost}}</td><td>{{r.gf}}</td><td>{{r.ga}}</td><td>{{r.gd}}</td><td><b class="gold">{{r.points}}</b></td></tr>{% endfor %}</table></div>
    """
    return page("Points Table",body,rows=rows)


@app.route("/sponsors",methods=["GET","POST"])
@admin_required
def sponsors():
    if request.method=="POST":
        logo=save_upload(request.files.get("logo"),SPONSOR_DIR)
        execute("INSERT INTO sponsors(name,amount,logo,contact,note) VALUES(?,?,?,?,?)",
                (request.form["name"],float(request.form.get("amount") or 0),logo,request.form.get("contact",""),request.form.get("note","")),True)
        flash("Sponsor যোগ হয়েছে।")
        return redirect(url_for("sponsors"))
    rows=query("SELECT * FROM sponsors ORDER BY id DESC")
    body="""
    <h1>🤝 Sponsors</h1><div class="grid2"><form class="card form" method="post" enctype="multipart/form-data"><h2>নতুন Sponsor</h2>
    <input name="name" placeholder="Sponsor name" required><input type="number" step="0.01" name="amount" placeholder="Amount (৳)">
    <input name="contact" placeholder="Contact"><input type="file" name="logo" accept="image/*"><textarea name="note" placeholder="Note"></textarea><button class="btn">Add Sponsor</button></form>
    <div>{% for s in rows %}<div class="card" style="margin-bottom:10px"><div class="row">{% if s.logo %}<img class="team-logo" src="/media/sponsors/{{s.logo}}">{% endif %}<div><h3>{{s.name}}</h3><b class="gold">{{s.amount|money}}</b><p class="muted">{{s.contact}}</p></div></div><form method="post" action="/sponsors/{{s.id}}/delete"><button class="btn danger">Delete</button></form></div>{% else %}<div class="card">Sponsor নেই।</div>{% endfor %}</div></div>
    """
    return page("Sponsors",body,rows=rows)


@app.route("/sponsors/<int:sid>/delete",methods=["POST"])
@admin_required
def delete_sponsor(sid):
    execute("DELETE FROM sponsors WHERE id=?",(sid,),True)
    return redirect(url_for("sponsors"))


@app.route("/finance",methods=["GET","POST"])
@admin_required
def finance():
    if request.method=="POST":
        execute("""INSERT INTO finance(team_id,entry_type,category,amount,note,entry_date)
        VALUES(?,?,?,?,?,?)""",(request.form["team_id"],request.form["entry_type"],request.form.get("category",""),
        float(request.form.get("amount") or 0),request.form.get("note",""),request.form.get("entry_date","")),True)
        flash("হিসাব সংরক্ষণ হয়েছে।")
        return redirect(url_for("finance"))
    rows=query("""SELECT f.*,t.name team_name FROM finance f JOIN teams t ON t.id=f.team_id ORDER BY f.id DESC""")
    total_income=sum(float(x["amount"]) for x in rows if x["entry_type"]=="income")
    total_expense=sum(float(x["amount"]) for x in rows if x["entry_type"]=="expense")
    purchase_total=query_one("SELECT COALESCE(SUM(purchase_fee),0) x FROM players")["x"]
    body="""
    <h1>💰 Tournament Finance</h1><div class="grid"><div class="card"><div class="muted">Income</div><div class="stat green">{{total_income|money}}</div></div><div class="card"><div class="muted">Expense</div><div class="stat danger">{{total_expense|money}}</div></div><div class="card"><div class="muted">Balance</div><div class="stat gold">{{(total_income-total_expense)|money}}</div></div><div class="card"><div class="muted">Player Purchase Total</div><div class="stat">{{purchase_total|money}}</div></div></div>
    <div class="grid2" style="margin-top:14px"><form class="card form" method="post"><h2>নতুন হিসাব</h2><select name="team_id">{% for t in teams %}<option value="{{t.id}}">{{t.name}}</option>{% endfor %}</select><select name="entry_type"><option value="income">Income</option><option value="expense">Expense</option></select><input name="category" placeholder="Category"><input type="number" step="0.01" name="amount" placeholder="Amount" required><input type="date" name="entry_date"><textarea name="note" placeholder="Note"></textarea><button class="btn">Save Entry</button></form>
    <div class="card"><h2>Ledger</h2><table><tr><th>Team</th><th>Type</th><th>Category</th><th>Amount</th><th></th></tr>{% for r in rows %}<tr><td>{{r.team_name}}</td><td>{{r.entry_type}}</td><td>{{r.category}}</td><td>{{r.amount|money}}</td><td><form method="post" action="/finance/{{r.id}}/delete"><button class="btn danger">×</button></form></td></tr>{% endfor %}</table></div></div>
    """
    return page("Finance",body,rows=rows,total_income=total_income,total_expense=total_expense,purchase_total=purchase_total)


@app.route("/finance/<int:fid>/delete",methods=["POST"])
@admin_required
def delete_finance(fid):
    execute("DELETE FROM finance WHERE id=?",(fid,),True)
    return redirect(url_for("finance"))


@app.route("/settings",methods=["GET","POST"])
@admin_required
def settings():
    keys=["facebook_page_name","facebook_page_url","powered_by","co_sponsors"]
    if request.method=="POST":
        for k in keys:
            execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k,request.form.get(k,"")),True)
        flash("Settings saved.")
        return redirect(url_for("settings"))
    data={k:(query_one("SELECT value FROM settings WHERE key=?",(k,)) or {"value":""})["value"] for k in keys}
    body="""
    <h1>⚙️ Tournament Settings</h1><form class="card form" method="post">
    <label>Facebook Page Name<input name="facebook_page_name" value="{{data.facebook_page_name}}"></label>
    <label>Facebook Page URL<input name="facebook_page_url" placeholder="https://facebook.com/..." value="{{data.facebook_page_url}}"></label>
    <label>Powered By<input name="powered_by" value="{{data.powered_by}}"></label>
    <label>Co-Sponsors<input name="co_sponsors" value="{{data.co_sponsors}}"></label>
    <button class="btn">Save Settings</button></form>
    <div class="card" style="margin-top:14px"><h3>Facebook</h3><p class="muted">এখানে Page-এর তথ্য রাখা যাবে। সরাসরি automatic posting চালাতে Facebook-এর অনুমোদিত API credentials প্রয়োজন; fake token এই অ্যাপে রাখা হয়নি।</p></div>
    """
    return page("Settings",body,data=data)



@app.route("/fixtures")
def fixtures():
    rows = query("""SELECT m.*,h.name home_name,a.name away_name,v.name venue_name,r.name referee_name
                    FROM matches m JOIN teams h ON h.id=m.home_team_id JOIN teams a ON a.id=m.away_team_id
                    LEFT JOIN venues v ON v.id=m.venue_id LEFT JOIN referees r ON r.id=m.referee_id
                    ORDER BY m.match_date,m.match_time,m.id""")
    body = """
    <div class="space"><div><h1>📅 Complete Fixtures</h1><p class="muted">তারিখ, সময়, মাঠ ও রেফারি সহ পুরো সূচি</p></div>
    <a class="btn" href="/matches/new">+ Match</a></div>
    {% for m in rows %}<div class="card" style="margin-bottom:10px">
      <div class="space"><span class="badge {% if m.status=='live' %}live{% endif %}">{{m.status}}</span><span>{{m.match_date}} {{m.match_time}}</span></div>
      <h2>{{m.home_name}} <span class="muted">vs</span> {{m.away_name}}</h2>
      <p class="muted">🏟️ {{m.venue_name or 'Venue not set'}} • 👨‍⚖️ {{m.referee_name or 'Referee not set'}}</p>
      <a class="btn secondary" href="/matches/{{m.id}}">Match Center</a>
    </div>{% else %}<div class="card">কোনো fixture নেই।</div>{% endfor %}
    """
    return page("Fixtures", body, rows=rows)


@app.route("/stats")
def stats():
    players = query("""SELECT p.*,t.name team_name,
        SUM(CASE WHEN e.event_type='goal' THEN 1 ELSE 0 END) goals,
        SUM(CASE WHEN e.event_type='assist' THEN 1 ELSE 0 END) assists,
        SUM(CASE WHEN e.event_type='foul' THEN 1 ELSE 0 END) fouls,
        SUM(CASE WHEN e.event_type='yellow' THEN 1 ELSE 0 END) yellow,
        SUM(CASE WHEN e.event_type='red' THEN 1 ELSE 0 END) red,
        (SELECT COUNT(*) FROM matches m WHERE m.potm_id=p.id) potm
        FROM players p JOIN teams t ON t.id=p.team_id
        LEFT JOIN events e ON e.player_id=p.id
        GROUP BY p.id ORDER BY goals DESC, assists DESC, potm DESC, p.name""")
    gks = query("""SELECT p.name,t.name team_name,COALESCE(SUM(g.saves),0) saves,
        COALESCE(SUM(g.goals_conceded),0) conceded,COALESCE(SUM(g.penalty_saves),0) penalty_saves,
        COALESCE(SUM(g.clean_sheet),0) clean_sheets
        FROM goalkeeper_stats g JOIN players p ON p.id=g.player_id JOIN teams t ON t.id=p.team_id
        GROUP BY p.id ORDER BY clean_sheets DESC,saves DESC""")
    body = """
    <h1>📊 Advanced Statistics</h1>
    <div class="card"><h2>⚽ Player Ranking</h2><table><tr><th>Player</th><th>Team</th><th>G</th><th>A</th><th>POTM</th><th>Foul</th><th>🟨</th><th>🟥</th></tr>
    {% for p in players %}<tr><td>{{p.name}}</td><td>{{p.team_name}}</td><td><b>{{p.goals or 0}}</b></td><td>{{p.assists or 0}}</td><td class="gold">{{p.potm or 0}}</td><td>{{p.fouls or 0}}</td><td>{{p.yellow or 0}}</td><td>{{p.red or 0}}</td></tr>{% endfor %}</table></div>
    <div class="card" style="margin-top:14px"><h2>🧤 Goalkeeper Stats</h2><table><tr><th>GK</th><th>Team</th><th>Saves</th><th>Conceded</th><th>Penalty Saves</th><th>Clean Sheet</th></tr>
    {% for g in gks %}<tr><td>{{g.name}}</td><td>{{g.team_name}}</td><td>{{g.saves}}</td><td>{{g.conceded}}</td><td>{{g.penalty_saves}}</td><td>{{g.clean_sheets}}</td></tr>{% else %}<tr><td colspan="6">কোনো goalkeeper data নেই।</td></tr>{% endfor %}</table></div>
    """
    return page("Statistics", body, players=players, gks=gks)


@app.route("/awards")
def awards():
    rows = query("""SELECT a.*,p.name player_name,t.name team_name FROM awards a
                    LEFT JOIN players p ON p.id=a.player_id LEFT JOIN teams t ON t.id=a.team_id ORDER BY a.id DESC""")
    top = query("""SELECT p.name,t.name team_name,COUNT(m.id) potm FROM players p JOIN teams t ON t.id=p.team_id
                   LEFT JOIN matches m ON m.potm_id=p.id GROUP BY p.id ORDER BY potm DESC LIMIT 10""")
    body = """
    <div class="space"><h1>🏅 Tournament Awards</h1><a class="btn" href="/awards/new">+ Award</a></div>
    <div class="grid2"><div class="card"><h2>⭐ Most POTM</h2>{% for p in top %}<p>{{loop.index}}. <b>{{p.name}}</b> — {{p.team_name}} <span class="gold">{{p.potm}}</span></p>{% endfor %}</div>
    <div class="card"><h2>🏆 Awards</h2>{% for a in rows %}<p><b>{{a.name}}</b> — {{a.player_name or a.team_name or ''}}<br><span class="muted">{{a.note}}</span></p>{% else %}<p class="muted">Award নেই।</p>{% endfor %}</div></div>
    """
    return page("Awards", body, rows=rows, top=top)


@app.route("/awards/new", methods=["GET","POST"])
@admin_required
def new_award():
    if request.method == "POST":
        execute("INSERT INTO awards(name,player_id,team_id,note) VALUES(?,?,?,?)",
                (request.form["name"], request.form.get("player_id") or None,
                 request.form.get("team_id") or None, request.form.get("note","")), True)
        flash("Award যোগ হয়েছে।")
        return redirect(url_for("awards"))
    ps=query("SELECT p.*,t.name team_name FROM players p JOIN teams t ON t.id=p.team_id ORDER BY p.name")
    body="""<h1>🏅 New Award</h1><form class="card form" method="post">
    <input name="name" placeholder="Golden Boot / Best Player..." required>
    <select name="player_id"><option value="">Player</option>{% for p in ps %}<option value="{{p.id}}">{{p.name}} — {{p.team_name}}</option>{% endfor %}</select>
    <select name="team_id"><option value="">Team (optional)</option>{% for t in teams %}<option value="{{t.id}}">{{t.name}}</option>{% endfor %}</select>
    <textarea name="note" placeholder="Note"></textarea><button class="btn">Save Award</button></form>"""
    return page("New Award", body, ps=ps)


@app.route("/discipline")
def discipline():
    rows=query("""SELECT p.name,t.name team_name,
      SUM(CASE WHEN e.event_type='yellow' THEN 1 ELSE 0 END) yellow,
      SUM(CASE WHEN e.event_type='red' THEN 1 ELSE 0 END) red,
      SUM(CASE WHEN e.event_type='foul' THEN 1 ELSE 0 END) fouls
      FROM players p JOIN teams t ON t.id=p.team_id LEFT JOIN events e ON e.player_id=p.id
      GROUP BY p.id HAVING yellow>0 OR red>0 OR fouls>0 ORDER BY red DESC,yellow DESC,fouls DESC""")
    body="""<h1>🟨 Disciplinary List</h1><div class="card"><table><tr><th>Player</th><th>Team</th><th>Foul</th><th>Yellow</th><th>Red</th></tr>
    {% for r in rows %}<tr><td>{{r.name}}</td><td>{{r.team_name}}</td><td>{{r.fouls}}</td><td>🟨 {{r.yellow}}</td><td>🟥 {{r.red}}</td></tr>{% else %}<tr><td colspan="5">কোনো disciplinary record নেই।</td></tr>{% endfor %}</table></div>"""
    return page("Discipline", body, rows=rows)


@app.route("/venues", methods=["GET","POST"])
def venues():
    if request.method=="POST":
        execute("INSERT INTO venues(name,location,note) VALUES(?,?,?)",
                (request.form["name"],request.form.get("location",""),request.form.get("note","")),True)
        flash("Venue যোগ হয়েছে।")
        return redirect(url_for("venues"))
    rows=query("SELECT * FROM venues ORDER BY name")
    body="""<h1>🏟️ Venue Management</h1><div class="grid2"><form class="card form" method="post"><input name="name" placeholder="মাঠের নাম" required><input name="location" placeholder="Location"><textarea name="note" placeholder="Note"></textarea><button class="btn">Add Venue</button></form>
    <div>{% for v in rows %}<div class="card" style="margin-bottom:10px"><h3>{{v.name}}</h3><p class="muted">{{v.location}}</p><form method="post" action="/venues/{{v.id}}/delete"><button class="btn danger">Delete</button></form></div>{% else %}<div class="card">Venue নেই।</div>{% endfor %}</div></div>"""
    return page("Venues", body, rows=rows)


@app.route("/venues/<int:vid>/delete", methods=["POST"])
@admin_required
def delete_venue(vid):
    execute("DELETE FROM venues WHERE id=?",(vid,),True)
    return redirect(url_for("venues"))


@app.route("/referees", methods=["GET","POST"])
def referees():
    if request.method=="POST":
        execute("INSERT INTO referees(name,phone,note) VALUES(?,?,?)",
                (request.form["name"],request.form.get("phone",""),request.form.get("note","")),True)
        flash("Referee যোগ হয়েছে।")
        return redirect(url_for("referees"))
    rows=query("SELECT * FROM referees ORDER BY name")
    body="""<h1>👨‍⚖️ Referee Management</h1><div class="grid2"><form class="card form" method="post"><input name="name" placeholder="Referee name" required><input name="phone" placeholder="Phone"><textarea name="note" placeholder="Note"></textarea><button class="btn">Add Referee</button></form>
    <div>{% for r in rows %}<div class="card" style="margin-bottom:10px"><h3>{{r.name}}</h3><p class="muted">{{r.phone}}</p><form method="post" action="/referees/{{r.id}}/delete"><button class="btn danger">Delete</button></form></div>{% else %}<div class="card">Referee নেই।</div>{% endfor %}</div></div>"""
    return page("Referees", body, rows=rows)


@app.route("/referees/<int:rid>/delete", methods=["POST"])
@admin_required
def delete_referee(rid):
    execute("DELETE FROM referees WHERE id=?",(rid,),True)
    return redirect(url_for("referees"))


@app.route("/matches/<int:mid>/substitution", methods=["POST"])
@admin_required
def add_substitution(mid):
    execute("""INSERT INTO substitutions(match_id,player_in_id,player_out_id,minute,note)
               VALUES(?,?,?,?,?)""",
            (mid, request.form.get("player_in_id") or None, request.form.get("player_out_id") or None,
             request.form.get("minute",""), request.form.get("note","")), True)
    flash("Substitution যোগ হয়েছে।")
    return redirect(url_for("match_detail", mid=mid))


@app.route("/matches/<int:mid>/goalkeeper", methods=["POST"])
@admin_required
def save_goalkeeper(mid):
    execute("""INSERT INTO goalkeeper_stats(match_id,player_id,saves,goals_conceded,penalty_saves,clean_sheet)
               VALUES(?,?,?,?,?,?) ON CONFLICT(match_id,player_id) DO UPDATE SET
               saves=excluded.saves,goals_conceded=excluded.goals_conceded,
               penalty_saves=excluded.penalty_saves,clean_sheet=excluded.clean_sheet""",
            (mid,request.form["player_id"],int(request.form.get("saves") or 0),
             int(request.form.get("goals_conceded") or 0),int(request.form.get("penalty_saves") or 0),
             int(request.form.get("clean_sheet") or 0)), True)
    flash("Goalkeeper stats saved.")
    return redirect(url_for("match_detail",mid=mid))


@app.route("/news", methods=["GET","POST"])
def news():
    if request.method=="POST":
        photo=save_upload(request.files.get("photo"), MEDIA_DIR)
        execute("INSERT INTO news(title,body,photo) VALUES(?,?,?)",
                (request.form["title"],request.form.get("body",""),photo),True)
        flash("News published.")
        return redirect(url_for("news"))
    rows=query("SELECT * FROM news ORDER BY id DESC")
    body="""<div class="space"><h1>📢 Tournament News</h1><a class="btn" href="/news/new">+ News</a></div>
    {% for n in rows %}<div class="card" style="margin-bottom:10px"><h2>{{n.title}}</h2><p>{{n.body}}</p><form method="post" action="/news/{{n.id}}/delete"><button class="btn danger">Delete</button></form></div>{% else %}<div class="card">News নেই।</div>{% endfor %}"""
    return page("News", body, rows=rows)


@app.route("/news/new", methods=["GET","POST"])
@admin_required
def new_news():
    if request.method=="POST":
        photo=save_upload(request.files.get("photo"),MEDIA_DIR)
        execute("INSERT INTO news(title,body,photo) VALUES(?,?,?)",
                (request.form["title"],request.form.get("body",""),photo),True)
        flash("News published.")
        return redirect(url_for("news"))
    body="""<h1>📢 Publish News</h1><form class="card form" method="post" enctype="multipart/form-data"><input name="title" placeholder="Title" required><textarea name="body" placeholder="News"></textarea><input type="file" name="photo" accept="image/*"><button class="btn">Publish</button></form>"""
    return page("Publish News",body)


@app.route("/news/<int:nid>/delete", methods=["POST"])
@admin_required
def delete_news(nid):
    execute("DELETE FROM news WHERE id=?",(nid,),True)
    return redirect(url_for("news"))


@app.route("/media/<folder>/<filename>")
def media(folder,filename):
    mapping={"players":PLAYER_DIR,"teams":TEAM_DIR,"sponsors":SPONSOR_DIR}
    if folder not in mapping: return "Not found",404
    return send_from_directory(mapping[folder],filename)


@app.route("/api/matches/<int:mid>")
def api_match(mid):
    m=query_one("""SELECT m.*,h.name home_name,a.name away_name,p.name potm_name,p.photo potm_photo
    FROM matches m JOIN teams h ON h.id=m.home_team_id JOIN teams a ON a.id=m.away_team_id
    LEFT JOIN players p ON p.id=m.potm_id WHERE m.id=?""",(mid,))
    if not m:return jsonify({"error":"not found"}),404
    ev=query("""SELECT e.id,e.event_type,e.minute,e.note,p.name player_name,t.name team_name
                FROM events e LEFT JOIN players p ON p.id=e.player_id LEFT JOIN teams t ON t.id=p.team_id
                WHERE e.match_id=? ORDER BY e.id""",(mid,))
    return jsonify({"match":dict(m),"events":[dict(x) for x in ev]})


@app.errorhandler(413)
def too_large(e):
    return "File too large. Maximum 8 MB.", 413


init_db()

if __name__ == "__main__":
    print("\nNPL Tracker Ultimate: http://127.0.0.1:8080")
    print("Database:", DB_PATH)
    print("Media:", MEDIA_DIR)
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
