"""Server-owned room clock and serialized multiplayer updates."""
import json
import time
from contextlib import closing
from flask import request, jsonify


def install_room_routes(app, get_db, generate_code, process_game_finish):
    with closing(get_db()) as conn, conn:
        columns = {row[1] for row in conn.execute('PRAGMA table_info(rooms_v2)')}
        for name, definition in [('deadline', 'REAL'), ('revision', 'INTEGER NOT NULL DEFAULT 0')]:
            if name not in columns:
                conn.execute(f'ALTER TABLE rooms_v2 ADD COLUMN {name} {definition}')

    def finish(conn, room):
        if room['status'] == 'finished':
            return
        room['status'] = 'finished'
        room['deadline'] = None
        for player in room['players']:
            player['finished'] = True
        process_game_finish(conn, room['code'], room['players'], {**room['config'], 'questions': room['questions']})

    def tick(conn, room, now):
        if room['status'] not in ('playing', 'reveal'):
            return
        if room['deadline'] is None:
            room['deadline'] = now + (room['config'].get('timePerQuestion', 15) if room['status'] == 'playing' else 5)
        active = [p for p in room['players'] if not p.get('forfeited')]
        index = room['current_question']
        all_answered = active and all(any(a['questionIndex'] == index for a in p.get('answers', [])) for p in active)
        if not active:
            finish(conn, room)
        elif room['status'] == 'playing' and (now >= room['deadline'] or all_answered):
            for player in active:
                if not any(a['questionIndex'] == index for a in player.get('answers', [])):
                    player.setdefault('answers', []).append({'questionIndex': index, 'selected': None,
                        'correct': room['questions'][index]['correct'], 'isCorrect': False})
                    player['combo'] = 0
            room['status'] = 'reveal'
            room['deadline'] = now + 5
        elif room['status'] == 'reveal' and now >= room['deadline']:
            if index + 1 >= len(room['questions']):
                finish(conn, room)
            else:
                room['current_question'] += 1
                room['status'] = 'playing'
                room['deadline'] = now + room['config'].get('timePerQuestion', 15)

    def snapshot(room, now):
        return dict(code=room['code'], hostId=room['host_uid'], hostName=room['host_name'],
                    hostPhoto=room['host_photo'], config=room['config'], questions=room['questions'],
                    players=room['players'], status=room['status'], currentQuestion=room['current_question'],
                    deadline=room['deadline'], serverTime=now, revision=room['revision'])

    def handle(code, action):
        conn = get_db()
        try:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM rooms_v2 WHERE code = ?', (code,)).fetchone()
            if not row:
                return jsonify(success=False, error='Room not found'), 404
            room = dict(row)
            for key in ('players', 'questions', 'config'):
                room[key] = json.loads(room[key])
            before = json.dumps(room, sort_keys=True)
            now = time.time()
            tick(conn, room, now)
            data = request.get_json(silent=True) or {}
            player = next((p for p in room['players'] if p['uid'] == data.get('uid')), None)
            error = None
            if action == 'join' and not player:
                if room['status'] != 'waiting':
                    error = 'This round has already started. Join the next room.'
                elif len(room['players']) >= 8:
                    error = 'This room is full.'
                else:
                    room['players'].append(dict(uid=data['uid'], name=data['name'], photo=data.get('photo', ''),
                        score=0, combo=0, highest_combo=0, finished=False, forfeited=False, answers=[]))
            elif action == 'start' and room['status'] == 'waiting':
                if not room['questions'] or len(room['players']) < 2:
                    error = 'Wait for questions and at least two players before starting.'
                else:
                    room['status'] = 'playing'
                    room['deadline'] = now + room['config'].get('timePerQuestion', 15)
            elif action == 'questions':
                if room['status'] != 'waiting':
                    error = 'Questions cannot change after the round starts.'
                elif not isinstance(data.get('questions'), list) or not data['questions']:
                    error = 'No questions were generated. Please create a new room.'
                else:
                    room['questions'] = data['questions']
            elif action == 'score' and player and not player.get('forfeited') and room['status'] == 'playing':
                index = room['current_question']
                answer = next((a for a in data.get('answers', []) if a.get('questionIndex') == index), None)
                if answer and not any(a['questionIndex'] == index for a in player.get('answers', [])):
                    selected = answer.get('selected')
                    correct = room['questions'][index]['correct']
                    good = selected is not None and selected == correct
                    player['combo'] = player.get('combo', 0) + 1 if good else 0
                    if good:
                        duration = max(1, room['config'].get('timePerQuestion', 15))
                        remaining = max(0, min(duration, room['deadline'] - now))
                        combo = player['combo']
                        player['score'] += 100 + int(remaining / duration * 50) + (combo * 10 if combo > 1 else 0)
                    player['highest_combo'] = max(player.get('highest_combo', 0), player['combo'])
                    player.setdefault('answers', []).append(dict(questionIndex=index, selected=selected, correct=correct, isCorrect=good))
                    tick(conn, room, now)
            elif action == 'forfeit' and player and room['status'] != 'finished':
                player['forfeited'] = True
                player['finished'] = True
                tick(conn, room, now)
            # Legacy reveal/next/end requests only tick the clock. They cannot rewind or skip a question.
            if before != json.dumps(room, sort_keys=True):
                room['revision'] += 1
                conn.execute('UPDATE rooms_v2 SET players=?, questions=?, status=?, current_question=?, deadline=?, revision=? WHERE code=?',
                    (json.dumps(room['players']), json.dumps(room['questions']), room['status'], room['current_question'], room['deadline'], room['revision'], code))
            conn.commit()
            if error:
                return jsonify(success=False, error=error), 409
            response = jsonify(success=True, room=snapshot(room, now))
            response.headers['Cache-Control'] = 'no-store'
            return response
        except Exception:
            conn.rollback()
            app.logger.exception('Room update failed')
            return jsonify(success=False, error='Room update failed. Please retry.'), 500
        finally:
            conn.close()

    for endpoint, action in [('get_room', 'get'), ('join_room', 'join'), ('start_room', 'start'),
                             ('next_question', 'next'), ('reveal_room', 'reveal'), ('end_room', 'end'),
                             ('update_questions', 'questions'), ('forfeit_room', 'forfeit'), ('update_score', 'score')]:
        app.view_functions[endpoint] = lambda code, action=action: handle(code, action)
