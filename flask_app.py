from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import random
import time
import os
import xml.etree.ElementTree as ET
import requests
from ai_handler import handle_chat, handle_generate_trivia

app = Flask(__name__)
# Allow CORS from your Vercel address and localhost
CORS(app, origins=["https://app-chi-brown-16.vercel.app", "https://scriptorium-trivia-frontend1.vercel.app", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175"])

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rooms.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    print(f"[*] Initializing database at {DB_PATH}")
    try:
        conn = get_db()
        
        # Active Rooms
        conn.execute('''CREATE TABLE IF NOT EXISTS rooms_v2 (
            code TEXT PRIMARY KEY,
            host_uid TEXT NOT NULL,
            host_name TEXT,
            host_photo TEXT,
            config TEXT NOT NULL,
            questions TEXT DEFAULT '[]',
            players TEXT NOT NULL,
            status TEXT DEFAULT 'waiting',
            current_question INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        )''')
        
        # Global User Stats
        conn.execute('''CREATE TABLE IF NOT EXISTS users_stats (
            uid TEXT PRIMARY KEY,
            nickname TEXT,
            photo TEXT,
            total_score INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            highest_combo INTEGER DEFAULT 0,
            updated_at REAL NOT NULL
        )''')
        
        # Match History
        conn.execute('''CREATE TABLE IF NOT EXISTS match_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            winner_uid TEXT,
            players TEXT,
            config TEXT,
            created_at REAL NOT NULL
        )''')
        
        # AI Chat Sessions (multi-session support)
        conn.execute('''CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            session_id TEXT PRIMARY KEY,
            uid TEXT NOT NULL,
            title TEXT,
            messages_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        )''')
        
        conn.commit()
        conn.close()
        print("[+] Database initialized successfully.")
    except Exception as e:
        print(f"[!] Database initialization error: {e}")

# Run init on start
init_db()

def generate_code():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(6))

def cleanup_old_rooms():
    try:
        conn = get_db()
        cutoff = time.time() - 7200
        conn.execute('DELETE FROM rooms_v2 WHERE created_at < ?', (cutoff,))
        conn.commit()
        conn.close()
    except: pass

def upsert_user_stats(conn, uid, nickname, photo, score=0, is_winner=False, highest_combo=0):
    row = conn.execute('SELECT * FROM users_stats WHERE uid = ?', (uid,)).fetchone()
    if row:
        new_total_score = row['total_score'] + score
        new_games_played = row['games_played'] + 1
        new_games_won = row['games_won'] + (1 if is_winner else 0)
        best_combo = max(row['highest_combo'], highest_combo)
        conn.execute('''UPDATE users_stats 
            SET nickname=?, photo=?, total_score=?, games_played=?, games_won=?, highest_combo=?, updated_at=?
            WHERE uid=?''', (nickname, photo, new_total_score, new_games_played, new_games_won, best_combo, time.time(), uid))
    else:
        conn.execute('''INSERT INTO users_stats (uid, nickname, photo, total_score, games_played, games_won, highest_combo, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (uid, nickname, photo, score, 1, 1 if is_winner else 0, highest_combo, time.time()))

def process_game_finish(conn, code, players, config):
    if not players: return
    valid_players = [p for p in players if not p.get('forfeited', False)]
    winner_uid = None
    if valid_players:
        valid_players.sort(key=lambda x: x.get('score', 0), reverse=True)
        winner_uid = valid_players[0]['uid']
        
    for p in players:
        uid = p['uid']
        nickname = p.get('name', 'Unknown')
        photo = p.get('photo', '')
        score = p.get('score', 0)
        combo = p.get('highest_combo', 0)
        upsert_user_stats(conn, uid, nickname, photo, score, uid == winner_uid, combo)
        
    conn.execute('INSERT INTO match_history (code, winner_uid, players, config, created_at) VALUES (?, ?, ?, ?, ?)',
                 (code, winner_uid, json.dumps(players), json.dumps(config), time.time()))


# --- API ENDPOINTS ---

@app.route('/api/stats/leaderboard', methods=['GET'])
def get_leaderboard():
    try:
        conn = get_db()
        rows = conn.execute('SELECT * FROM users_stats ORDER BY total_score DESC LIMIT 100').fetchall()
        conn.close()
        return jsonify({'success': True, 'leaderboard': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    try:
        conn = get_db()
        rows = conn.execute('SELECT * FROM users_stats ORDER BY updated_at DESC').fetchall()
        conn.close()
        return jsonify({'success': True, 'users': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats/user/<uid>', methods=['GET'])
def get_user_stats(uid):
    try:
        conn = get_db()
        stats = conn.execute('SELECT * FROM users_stats WHERE uid = ?', (uid,)).fetchone()
        history = conn.execute('SELECT * FROM match_history WHERE players LIKE ? ORDER BY created_at DESC LIMIT 20', (f'%"{uid}"%',)).fetchall()
        conn.close()
        
        formatted_history = []
        for h in history:
            row = dict(h)
            try:
                players_data = json.loads(row['players'])
                me = next((p for p in players_data if p.get('uid') == uid), None)
                if not me: continue
                config_data = json.loads(row['config']) if row['config'] else {}
                formatted_history.append({
                    'id': row['id'],
                    'timestamp': row['created_at'] * 1000,
                    'won': row['winner_uid'] == uid,
                    'score': me.get('score', 0),
                    'multiplayer': len(players_data) > 1,
                    'code': row['code'],
                    'questions': config_data.get('questions', []),
                    'userAnswers': me.get('answers', [])
                })
            except Exception:
                pass
                
        return jsonify({
            'success': True, 
            'stats': dict(stats) if stats else None,
            'history': formatted_history
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats/user/<uid>/solo', methods=['POST'])
def save_solo_game(uid):
    try:
        data = request.json
        conn = get_db()
        is_winner = data.get('won', False)
        upsert_user_stats(conn, uid, data.get('nickname', 'Player'), data.get('photo', ''), 
                          data.get('score', 0), is_winner, data.get('combo', 0))
        
        player_info = [{
            'uid': uid, 'name': data.get('nickname'), 'photo': data.get('photo'),
            'score': data.get('score', 0), 'combo': data.get('combo', 0),
            'answers': data.get('userAnswers', [])
        }]
        
        config_data = data.get('config', {})
        config_data['questions'] = data.get('questions', [])
        
        conn.execute('INSERT INTO match_history (code, winner_uid, players, config, created_at) VALUES (?, ?, ?, ?, ?)',
                     ('SOLO', uid if is_winner else None, json.dumps(player_info), json.dumps(config_data), time.time()))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms', methods=['POST'])
def create_room():
    try:
        data = request.json
        code = generate_code()
        player = {
            'uid': data['uid'], 'name': data['name'], 'photo': data.get('photo', ''),
            'score': 0, 'combo': 0, 'highest_combo': 0, 'finished': False, 'forfeited': False
        }
        conn = get_db()
        conn.execute(
            'INSERT INTO rooms_v2 (code, host_uid, host_name, host_photo, config, questions, players, status, current_question, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (code, data['uid'], data['name'], data.get('photo', ''),
             json.dumps(data.get('config', {})), '[]',
             json.dumps([player]), 'waiting', 0, time.time())
        )
        conn.commit()
        conn.close()
        cleanup_old_rooms()
        return jsonify({'success': True, 'code': code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>', methods=['GET'])
def get_room(code):
    try:
        conn = get_db()
        row = conn.execute('SELECT * FROM rooms_v2 WHERE code = ?', (code,)).fetchone()
        conn.close()
        if not row:
            return jsonify({'success': False, 'error': 'Room not found'}), 404
        return jsonify({
            'success': True,
            'room': {
                'code': row['code'], 'hostId': row['host_uid'], 'hostName': row['host_name'],
                'hostPhoto': row['host_photo'], 'config': json.loads(row['config']),
                'questions': json.loads(row['questions']), 'players': json.loads(row['players']),
                'status': row['status'], 'currentQuestion': row['current_question']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/join', methods=['POST'])
def join_room(code):
    try:
        data = request.json
        conn = get_db()
        row = conn.execute('SELECT * FROM rooms_v2 WHERE code = ?', (code,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Room not found'}), 404
        players = json.loads(row['players'])
        if not any(p['uid'] == data['uid'] for p in players):
            players.append({
                'uid': data['uid'], 'name': data['name'], 'photo': data.get('photo', ''),
                'score': 0, 'combo': 0, 'highest_combo': 0, 'finished': False, 'forfeited': False
            })
            conn.execute('UPDATE rooms_v2 SET players = ? WHERE code = ?', (json.dumps(players), code))
            conn.commit()
        room_data = {
            'code': row['code'], 'hostId': row['host_uid'], 'config': json.loads(row['config']),
            'questions': json.loads(row['questions']), 'players': players,
            'status': row['status'], 'currentQuestion': row['current_question']
        }
        conn.close()
        return jsonify({'success': True, 'room': room_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/start', methods=['POST'])
def start_room(code):
    try:
        conn = get_db()
        conn.execute('UPDATE rooms_v2 SET status = ?, current_question = 0 WHERE code = ?', ('playing', code))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/next', methods=['POST'])
def next_question(code):
    try:
        data = request.json
        new_index = data.get('index', 0)
        conn = get_db()
        conn.execute('UPDATE rooms_v2 SET current_question = ?, status = ? WHERE code = ?', (new_index, 'playing', code))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/reveal', methods=['POST'])
def reveal_room(code):
    try:
        conn = get_db()
        conn.execute('UPDATE rooms_v2 SET status = ? WHERE code = ?', ('reveal', code))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/end', methods=['POST'])
def end_room(code):
    try:
        conn = get_db()
        row = conn.execute('SELECT players, config, status, questions FROM rooms_v2 WHERE code = ?', (code,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Room not found'}), 404
        players = json.loads(row['players'])
        for p in players: p['finished'] = True
        conn.execute('UPDATE rooms_v2 SET players = ?, status = ? WHERE code = ?', (json.dumps(players), 'finished', code))
        if row['status'] != 'finished':
            config_data = json.loads(row['config'])
            config_data['questions'] = json.loads(row['questions']) if row['questions'] else []
            process_game_finish(conn, code, players, config_data)
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/questions', methods=['POST'])
def update_questions(code):
    try:
        data = request.json
        conn = get_db()
        conn.execute('UPDATE rooms_v2 SET questions = ? WHERE code = ?', (json.dumps(data['questions']), code))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/forfeit', methods=['POST'])
def forfeit_room(code):
    try:
        data = request.json
        uid = data['uid']
        conn = get_db()
        row = conn.execute('SELECT players, config, status, questions FROM rooms_v2 WHERE code = ?', (code,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Room not found'}), 404
        players = json.loads(row['players'])
        config = json.loads(row['config'])
        for p in players:
            if p['uid'] == uid:
                p['forfeited'] = True
                p['finished'] = True
        conn.execute('UPDATE rooms_v2 SET players = ?, status = ? WHERE code = ?', (json.dumps(players), 'finished', code))
        if row['status'] != 'finished':
            config['questions'] = json.loads(row['questions']) if row['questions'] else []
            process_game_finish(conn, code, players, config)
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
         return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<code>/score', methods=['POST'])
def update_score(code):
    try:
        data = request.json
        conn = get_db()
        row = conn.execute('SELECT players, config, status, questions FROM rooms_v2 WHERE code = ?', (code,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Room not found'}), 404
        players = json.loads(row['players'])
        for p in players:
            if p['uid'] == data['uid']:
                p['score'] = data['score']
                p['combo'] = data.get('combo', 0)
                p['highest_combo'] = max(p.get('highest_combo', 0), data.get('combo', 0))
                if 'answers' in data:
                    p['answers'] = data['answers']
                if data.get('finished'): p['finished'] = True
        all_finished = all(p.get('finished', False) for p in players)
        status = 'finished' if all_finished else 'playing'
        conn.execute('UPDATE rooms_v2 SET players = ?, status = ? WHERE code = ?', (json.dumps(players), status, code))
        if status == 'finished' and row['status'] != 'finished':
            config_data = json.loads(row['config'])
            config_data['questions'] = json.loads(row['questions']) if row['questions'] else []
            process_game_finish(conn, code, players, config_data)
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/<uid>', methods=['GET'])
def get_chat_sessions(uid):
    try:
        conn = get_db()
        # Return summary of sessions, not full messages
        rows = conn.execute('SELECT session_id, title, updated_at FROM ai_chat_sessions WHERE uid = ? ORDER BY updated_at DESC', (uid,)).fetchall()
        conn.close()
        return jsonify({'success': True, 'sessions': [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/session/<session_id>', methods=['GET'])
def get_chat_session(session_id):
    try:
        conn = get_db()
        row = conn.execute('SELECT * FROM ai_chat_sessions WHERE session_id = ?', (session_id,)).fetchone()
        conn.close()
        if row:
            return jsonify({'success': True, 'session': dict(row)})
        return jsonify({'success': False, 'error': 'Session not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/<uid>', methods=['POST'])
def save_chat_session(uid):
    try:
        data = request.json
        session_id = data.get('session_id')
        messages = data.get('messages', [])
        title = data.get('title', 'New Conversion')
        
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        # Force types and debug
        session_id = str(session_id)
        uid = str(uid)
        title = str(title) if title else "New Dialogue"
        msg_json = json.dumps(messages)
        timestamp = time.time()

        print(f"[*] Saving Chat: Session={session_id}, UID={uid}, Title={title}")

        conn = get_db()
        conn.execute('''
            INSERT INTO ai_chat_sessions (session_id, uid, title, messages_json, updated_at) 
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET 
                messages_json=excluded.messages_json, 
                title=excluded.title,
                updated_at=excluded.updated_at
        ''', (session_id, uid, title, msg_json, timestamp))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'session_id': session_id})
    except Exception as e:
        print(f"[ERROR] save_chat_session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/session/<session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM ai_chat_sessions WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

BIBLE_CACHE = {}

def get_bible_tree(version="KJV"):
    if version not in BIBLE_CACHE:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bible_path = os.path.join(base_dir, 'bible', f'{version}.xml')
        print(f"[*] Loading Bible from: {bible_path}")
        if not os.path.exists(bible_path):
            raise Exception(f"Bible version {version} not found at {bible_path}")
        tree = ET.parse(bible_path)
        BIBLE_CACHE[version] = tree.getroot()
    return BIBLE_CACHE[version]

@app.route('/api/bible/lookup', methods=['POST'])
def lookup_verses():
    try:
        data = request.json
        queries = data.get('queries', []) 
        version = data.get('version', 'KJV')
        print(f"[*] Lookup request for {version}: {queries}")
        root = get_bible_tree(version)
        results = []
        for q in queries:
            book_name = q.get('book', '').strip()
            chapter_num = str(q.get('chapter'))
            v_nums = [str(v) for v in q.get('verses', [])]
            book_node = None
            all_books = root.findall('b')
            for b in all_books:
                if b.get('n').lower() == book_name.lower():
                    book_node = b
                    break
            if not book_node:
                print(f"[!] Book '{book_name}' not found.")
                continue
            chapter_node = None
            for c in book_node.findall('c'):
                if c.get('n') == chapter_num:
                    chapter_node = c
                    break
            if not chapter_node:
                print(f"[!] Chapter {chapter_num} not found in {book_name}.")
                continue
            verse_texts = []
            for v_node in chapter_node.findall('v'):
                if v_node.get('n') in v_nums:
                    verse_texts.append({"verse": int(v_node.get('n')), "text": v_node.text})
            if verse_texts:
                results.append({"book": book_node.get('n'), "chapter": int(chapter_num), "verses": verse_texts})
        print(f"[*] Lookup results found: {len(results)} matches")
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        print(f"[ERROR] Bible lookup failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# --- AI ENDPOINTS (using ai_handler module) ---

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat_route():
    data = request.json
    result = handle_chat(data.get('message'), data.get('history', []), data.get('model_id', 'llama-3-8b'))
    return jsonify(result)

@app.route('/api/ai/generate_trivia', methods=['POST'])
def ai_trivia_route():
    data = request.json
    result = handle_generate_trivia(data.get('prompt'))
    return jsonify(result)

@app.route('/api/export', methods=['POST'])
def export_results():
    try:
        from export import generate_export_file, generate_filename
        import io
        from flask import send_file
        
        data = request.json
        fmt = data.get('format', 'pdf')
        score = data.get('score', 0)
        questions = data.get('questions', [])
        user_answers = data.get('userAnswers', [])
        config = data.get('config', {})
        
        file_bytes = generate_export_file(score, questions, user_answers, config, fmt)
        filename = generate_filename(config, fmt)
        mimetype = 'image/png' if fmt == 'png' else 'application/pdf'
        
        return send_file(
            io.BytesIO(file_bytes),
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"[ERROR] Export failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5555)
