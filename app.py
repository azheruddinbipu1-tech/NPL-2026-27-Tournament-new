import os
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me-in-production')
db_url = os.getenv('DATABASE_URL', 'sqlite:///npl_tracker.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif db_url.startswith('postgresql://'):
    db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    coach = db.Column(db.String(120), default='')
    budget = db.Column(db.Integer, default=0)
    logo_url = db.Column(db.String(500), default='')
    players = db.relationship('Player', backref='team', cascade='all, delete-orphan')
    home_matches = db.relationship('Match', foreign_keys='Match.team1_id', cascade='all, delete-orphan')
    away_matches = db.relationship('Match', foreign_keys='Match.team2_id', cascade='all, delete-orphan')

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(80), default='')
    jersey = db.Column(db.Integer, default=0)
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    yellow_cards = db.Column(db.Integer, default=0)
    red_cards = db.Column(db.Integer, default=0)
    fouls = db.Column(db.Integer, default=0)
    matches_played = db.Column(db.Integer, default=0)
    purchase_price = db.Column(db.Integer, default=0)
    photo_url = db.Column(db.String(500), default='')

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team1_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    team2_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), default='')
    venue = db.Column(db.String(160), default='TBD')
    score1 = db.Column(db.Integer, default=0)
    score2 = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='upcoming')
    minute = db.Column(db.Integer, default=0)
    finalized = db.Column(db.Boolean, default=False)
    story = db.Column(db.Text, default='')
    events = db.relationship('Event', backref='match', cascade='all, delete-orphan', order_by='Event.minute')

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    team_id = db.Column(db.Integer, nullable=False)
    player_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(30), nullable=False)
    minute = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'ok': False, 'error': 'Admin login required'}), 401
        return fn(*args, **kwargs)
    return wrapper

def team_stats(team_id):
    matches = Match.query.filter((Match.team1_id == team_id) | (Match.team2_id == team_id), Match.status == 'played').all()
    played = win = draw = loss = gf = ga = points = 0
    for m in matches:
        played += 1
        if m.team1_id == team_id:
            a, b = m.score1, m.score2
        else:
            a, b = m.score2, m.score1
        gf += a; ga += b
        if a > b: win += 1; points += 3
        elif a == b: draw += 1; points += 1
        else: loss += 1
    return dict(played=played, win=win, draw=draw, loss=loss, goalsFor=gf, goalsAgainst=ga, points=points)

def serialize_team(t):
    return {'id': t.id, 'name': t.name, 'coach': t.coach or '', 'budget': t.budget or 0, 'logoUrl': t.logo_url or '', 'stats': team_stats(t.id)}

def serialize_player(p):
    return {'id': p.id, 'teamId': p.team_id, 'teamName': p.team.name, 'name': p.name, 'position': p.position or '', 'jersey': p.jersey or 0, 'goals': p.goals or 0, 'assists': p.assists or 0, 'yellowCards': p.yellow_cards or 0, 'redCards': p.red_cards or 0, 'fouls': p.fouls or 0, 'matchesPlayed': p.matches_played or 0, 'purchasePrice': p.purchase_price or 0, 'photoUrl': p.photo_url or ''}

def serialize_match(m):
    t1 = db.session.get(Team, m.team1_id); t2 = db.session.get(Team, m.team2_id)
    return {'id': m.id, 'team1Id': m.team1_id, 'team2Id': m.team2_id, 'team1': t1.name, 'team2': t2.name, 'date': m.date, 'time': m.time or '', 'venue': m.venue or 'TBD', 'score1': m.score1 or 0, 'score2': m.score2 or 0, 'status': m.status, 'minute': m.minute or 0, 'story': m.story or '', 'events': [serialize_event(e) for e in m.events]}

def serialize_event(e):
    p = db.session.get(Player, e.player_id); t = db.session.get(Team, e.team_id)
    return {'id': e.id, 'teamId': e.team_id, 'teamName': t.name if t else '?', 'playerId': e.player_id, 'playerName': p.name if p else '?', 'type': e.type, 'minute': e.minute}

@app.get('/')
def index():
    return render_template('index.html')

@app.post('/api/login')
def login():
    password = request.json.get('password', '')
    if password == os.getenv('ADMIN_PASSWORD', 'admin123'):
        session['admin'] = True
        return jsonify(ok=True)
    return jsonify(ok=False, error='ভুল পাসওয়ার্ড'), 401

@app.post('/api/logout')
def logout():
    session.clear(); return jsonify(ok=True)

@app.get('/api/state')
def state():
    teams = [serialize_team(t) for t in Team.query.order_by(Team.name).all()]
    players = [serialize_player(p) for p in Player.query.order_by(Player.name).all()]
    matches = [serialize_match(m) for m in Match.query.order_by(Match.id.desc()).all()]
    live = [m for m in matches if m['status'] == 'live']
    standings = sorted(teams, key=lambda x: (x['stats']['points'], x['stats']['goalsFor'] - x['stats']['goalsAgainst']), reverse=True)
    leaderboard = sorted(players, key=lambda x: (x['goals'], x['assists']), reverse=True)
    return jsonify(ok=True, admin=bool(session.get('admin')), teams=teams, players=players, matches=matches, live=live, standings=standings, leaderboard=leaderboard)

@app.post('/api/teams')
@admin_required
def add_team():
    data = request.json or {}; name = data.get('name','').strip()
    if not name: return jsonify(ok=False,error='দলের নাম দিন'),400
    if Team.query.filter(db.func.lower(Team.name)==name.lower()).first(): return jsonify(ok=False,error='এই নামে দল আছে'),400
    db.session.add(Team(name=name, coach=data.get('coach','').strip(), budget=int(data.get('budget') or 0), logo_url=data.get('logoUrl','').strip())); db.session.commit(); return jsonify(ok=True)

@app.delete('/api/teams/<int:team_id>')
@admin_required
def delete_team(team_id):
    t = db.session.get(Team, team_id)
    if not t: return jsonify(ok=False,error='দল পাওয়া যায়নি'),404
    db.session.delete(t); db.session.commit(); return jsonify(ok=True)

@app.post('/api/players')
@admin_required
def add_player():
    d=request.json or {}; name=d.get('name','').strip(); team_id=int(d.get('teamId') or 0)
    if not name or not db.session.get(Team, team_id): return jsonify(ok=False,error='দল ও নাম দিন'),400
    p=Player(team_id=team_id,name=name,position=d.get('position','').strip(),jersey=int(d.get('jersey') or 0), purchase_price=int(d.get('purchasePrice') or 0), photo_url=d.get('photoUrl','').strip())
    db.session.add(p); db.session.commit(); return jsonify(ok=True)

@app.delete('/api/players/<int:player_id>')
@admin_required
def delete_player(player_id):
    p=db.session.get(Player,player_id)
    if not p: return jsonify(ok=False,error='প্লেয়ার পাওয়া যায়নি'),404
    db.session.delete(p); db.session.commit(); return jsonify(ok=True)

@app.put('/api/teams/<int:team_id>')
@admin_required
def edit_team(team_id):
    t=db.session.get(Team,team_id); d=request.json or {}
    if not t: return jsonify(ok=False,error='দল পাওয়া যায়নি'),404
    name=d.get('name',t.name).strip()
    if not name: return jsonify(ok=False,error='দলের নাম দিন'),400
    t.name=name; t.coach=d.get('coach',t.coach).strip(); t.budget=int(d.get('budget',t.budget) or 0); t.logo_url=d.get('logoUrl',t.logo_url).strip(); db.session.commit(); return jsonify(ok=True)

@app.put('/api/players/<int:player_id>')
@admin_required
def edit_player(player_id):
    p=db.session.get(Player,player_id); d=request.json or {}
    if not p: return jsonify(ok=False,error='প্লেয়ার পাওয়া যায়নি'),404
    p.name=d.get('name',p.name).strip(); p.team_id=int(d.get('teamId',p.team_id)); p.position=d.get('position',p.position).strip(); p.jersey=int(d.get('jersey',p.jersey) or 0); p.purchase_price=int(d.get('purchasePrice',p.purchase_price) or 0); p.photo_url=d.get('photoUrl',p.photo_url).strip(); db.session.commit(); return jsonify(ok=True)

@app.post('/api/matches')
@admin_required
def create_match():
    d=request.json or {}; a=int(d.get('team1Id') or 0); b=int(d.get('team2Id') or 0)
    if not a or not b or a==b: return jsonify(ok=False,error='দুটি ভিন্ন দল নির্বাচন করুন'),400
    m=Match(team1_id=a,team2_id=b,date=d.get('date') or datetime.now().strftime('%Y-%m-%d'),time=d.get('time',''),venue=d.get('venue','TBD'), story=d.get('story','').strip())
    db.session.add(m); db.session.commit(); return jsonify(ok=True,id=m.id)

@app.delete('/api/matches/<int:match_id>')
@admin_required
def delete_match(match_id):
    m=db.session.get(Match,match_id)
    if not m: return jsonify(ok=False,error='ম্যাচ পাওয়া যায়নি'),404
    db.session.delete(m); db.session.commit(); return jsonify(ok=True)

@app.post('/api/live/start')
@admin_required
def start_live():
    d=request.json or {}; m=db.session.get(Match,int(d.get('matchId') or 0))
    if not m: return jsonify(ok=False,error='ম্যাচ নির্বাচন করুন'),400
    Match.query.filter(Match.status=='live').update({Match.status:'upcoming'})
    m.status='live'; m.finalized=False; m.score1=0; m.score2=0; m.minute=0
    Event.query.filter_by(match_id=m.id).delete(); db.session.commit(); return jsonify(ok=True)

@app.post('/api/live/pause')
@admin_required
def pause_live():
    for m in Match.query.filter_by(status='live').all(): m.status='paused'
    db.session.commit(); return jsonify(ok=True)

@app.post('/api/live/minute')
@admin_required
def update_minute():
    d=request.json or {}; m=db.session.get(Match,int(d.get('matchId') or 0)); minute=int(d.get('minute') or 0)
    if not m: return jsonify(ok=False,error='ম্যাচ নেই'),404
    m.minute=max(0,minute); db.session.commit(); return jsonify(ok=True)

@app.post('/api/events')
@admin_required
def add_event():
    d=request.json or {}; m=db.session.get(Match,int(d.get('matchId') or 0))
    if not m or m.status!='live': return jsonify(ok=False,error='লাইভ ম্যাচ চলছে না'),400
    team_id=int(d.get('teamId') or 0); player_id=int(d.get('playerId') or 0); typ=d.get('type',''); minute=int(d.get('minute') or m.minute or 0)
    p=db.session.get(Player,player_id)
    if not p or p.team_id!=team_id or team_id not in (m.team1_id,m.team2_id): return jsonify(ok=False,error='সঠিক দল/প্লেয়ার নির্বাচন করুন'),400
    e=Event(match_id=m.id,team_id=team_id,player_id=player_id,type=typ,minute=minute); m.minute=minute
    if typ=='goal':
        if team_id==m.team1_id: m.score1 += 1
        else: m.score2 += 1
    db.session.add(e); db.session.commit(); return jsonify(ok=True)

@app.delete('/api/events/<int:event_id>')
@admin_required
def delete_event(event_id):
    e=db.session.get(Event,event_id)
    if not e: return jsonify(ok=False,error='ইভেন্ট নেই'),404
    m=e.match
    if e.type=='goal':
        if e.team_id==m.team1_id: m.score1=max(0,m.score1-1)
        elif e.team_id==m.team2_id: m.score2=max(0,m.score2-1)
    db.session.delete(e); db.session.commit(); return jsonify(ok=True)

@app.post('/api/live/end')
@admin_required
def end_live():
    d=request.json or {}; m=db.session.get(Match,int(d.get('matchId') or 0))
    if not m: return jsonify(ok=False,error='ম্যাচ নেই'),404
    if m.finalized: return jsonify(ok=False,error='ম্যাচ আগেই শেষ করা হয়েছে'),400
    for e in m.events:
        p=db.session.get(Player,e.player_id)
        if not p: continue
        if e.type=='goal': p.goals+=1
        elif e.type=='assist': p.assists+=1
        elif e.type=='yellow': p.yellow_cards+=1
        elif e.type=='red': p.red_cards+=1
        elif e.type=='foul': p.fouls+=1
    touched=set([m.team1_id,m.team2_id])
    for tid in touched:
        for p in Player.query.filter_by(team_id=tid).all(): p.matches_played += 1
    m.status='played'; m.finalized=True; db.session.commit(); return jsonify(ok=True)

@app.delete('/api/matches/<int:match_id>/events')
@admin_required
def clear_events(match_id):
    m=db.session.get(Match,match_id)
    if not m: return jsonify(ok=False,error='ম্যাচ নেই'),404
    Event.query.filter_by(match_id=match_id).delete(); m.score1=0; m.score2=0; m.minute=0; db.session.commit(); return jsonify(ok=True)

@app.get('/health')
def health():
    db.session.execute(text('SELECT 1')); return jsonify(status='ok')

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
