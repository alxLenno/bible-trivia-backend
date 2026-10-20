"""Server-owned room clock and serialized multiplayer updates."""
import json
import hashlib
import re
import unicodedata
import time
from contextlib import closing
from flask import request, jsonify


def normalize_question_set(questions):
    if not isinstance(questions, list) or not questions or len(questions) > 50:
        raise ValueError('Provide a complete set of 1 to 50 questions.')
    def key(text):
        return re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', text).casefold()).strip()
    result, seen = [], set()
    for raw in questions:
        if not isinstance(raw, dict):
            raise ValueError('Each question must include its options, answer and insight.')
        q = dict(raw)
        for field in ('question', 'correct', 'explanation'):
            if not isinstance(q.get(field), str) or not q[field].strip():
                raise ValueError('Every question needs text, a correct answer and an insight.')
            q[field] = q[field].strip()
        options = q.get('options')
        if not isinstance(options, list) or len(options) != 4 or any(not isinstance(o, str) or not o.strip() for o in options):
            raise ValueError('Every question needs four distinct options.')
        q['options'] = [o.strip() for o in options]
        if len({key(o) for o in q['options']}) != 4:
            raise ValueError('A question contains duplicate options.')
        matches = [o for o in q['options'] if key(o) == key(q['correct'])]
        if len(matches) != 1:
            raise ValueError('The correct answer must match exactly one option.')
        q['correct'] = matches[0]
        if not re.search(r'\d+:\d+', q['explanation']):
            raise ValueError('Every insight needs a scripture citation.')
        fingerprint = key(q['question'])
        if fingerprint in seen:
            raise ValueError('The question set contains repeated questions.')
        seen.add(fingerprint)
        content = {k:q[k] for k in ('question', 'options', 'correct', 'explanation')}
        q['id'] = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
        result.append(q)
    return result


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
        if room['deadline'] is None and room['status'] == 'playing':
            room['deadline'] = now + room['config'].get('timePerQuestion', 15)
        active = [p for p in room['players'] if not p.get('forfeited')]
        index = room['current_question']
        all_answered = active and all(any(a['questionIndex'] == index for a in p.get('answers', [])) for p in active)
        if not active:
            finish(conn, room)
        elif room['status'] == 'playing' and (now >= room['deadline'] or all_answered):
            for player in active:
                if not any(a['questionIndex'] == index for a in player.get('answers', [])):
                    player.setdefault('answers', []).append({'questionIndex': index, 'selected': None,
                        'correct': room['questions'][index]['correct'], 'questionId': room['questions'][index].get('id'), 'isCorrect': False})
                    player['combo'] = 0
            room['status'] = 'reveal'
            room['deadline'] = None

    def snapshot(room, now):
        return dict(code=room['code'], hostId=room['host_uid'], hostName=room['host_name'],
                    hostPhoto=room['host_photo'], config=room['config'], questions=room['questions'],
                    players=room['players'], status=room['status'], currentQuestion=room['current_question'],
                    deadline=room['deadline'], serverTime=now, revision=room['revision'],
                    currentQuestionId=room['questions'][room['current_question']].get('id') if room['questions'] else None)

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
            if action == 'join' and player and player.get('forfeited'):
                error = 'You have left this round. Join a new room to play again.'
            elif action == 'join' and not player:
                if room['status'] != 'waiting':
                    error = 'This round has already started. Join the next room.'
                elif len(room['players']) >= 8:
                    error = 'This room is full.'
                else:
                    room['players'].append(dict(uid=data['uid'], name=data['name'], photo=data.get('photo', ''),
                        score=0, combo=0, highest_combo=0, finished=False, forfeited=False, answers=[]))
            elif action == 'start' and room['status'] == 'waiting':
                if data.get('uid') != room['host_uid'] or not player or player.get('forfeited'):
                    error = 'Only the host can start this round.'
                elif not room['questions'] or len([p for p in room['players'] if not p.get('forfeited')]) < 2:
                    error = 'Wait for questions and at least two players before starting.'
                else:
                    try:
                        room['questions'] = normalize_question_set(room['questions'])
                    except ValueError as exc:
                        error = str(exc)
                    if not error:
                        room['status'] = 'playing'
                        room['deadline'] = now + room['config'].get('timePerQuestion', 15)
            elif action in ('next', 'end'):
                expected = data.get('currentQuestion')
                if data.get('uid') != room['host_uid'] or not player or player.get('forfeited'):
                    error = 'Only the host can advance the round.'
                elif expected != room['current_question']:
                    error = 'The room has already moved. Wait for synchronization.'
                elif room['status'] != 'reveal':
                    error = 'Wait until the answers are revealed before continuing.'
                elif any(p.get('reviewedQuestion') != room['current_question'] for p in room['players'] if not p.get('forfeited') and p['uid'] != room['host_uid']):
                    error = 'Wait for the other players to finish reviewing this answer.'
                elif room['current_question'] + 1 >= len(room['questions']):
                    finish(conn, room)
                elif action == 'end':
                    error = 'Complete the remaining questions first.'
                else:
                    room['current_question'] += 1
                    room['status'] = 'playing'
                    room['deadline'] = now + room['config'].get('timePerQuestion', 15)
            elif action == 'questions':
                if data.get('uid') != room['host_uid'] or not player or player.get('forfeited'):
                    error = 'Only the host can prepare the question set.'
                elif room['status'] != 'waiting':
                    error = 'Questions cannot change after the round starts.'
                else:
                    try:
                        candidate = normalize_question_set(data.get('questions'))
                        if len(candidate) != room['config'].get('numQuestions', len(candidate)):
                            error = 'The generated question count does not match this room.'
                        elif room['questions'] and candidate != normalize_question_set(room['questions']):
                            error = 'This room already has its question set. Create a new room for different questions.'
                        else:
                            room['questions'] = candidate
                    except ValueError as exc:
                        error = str(exc)
            elif action == 'score':
                index = room['current_question']
                submitted = data.get('answers')
                answer = next((a for a in submitted if isinstance(a, dict) and a.get('questionIndex') == index), None) if isinstance(submitted, list) else None
                existing = next((a for a in (player or {}).get('answers', []) if a['questionIndex'] == index), None)
                question = room['questions'][index] if room['questions'] else None
                if not player or player.get('forfeited'):
                    error = 'This player is not active in the round.'
                elif not answer or not question or answer.get('questionId') != question.get('id'):
                    error = 'This answer belongs to a different question. Wait for synchronization.'
                elif answer.get('selected') is not None and answer['selected'] not in question['options']:
                    error = 'Select one of the displayed options.'
                elif existing:
                    if existing['selected'] != answer.get('selected'):
                        error = 'Your answer has already been recorded.'
                elif room['status'] != 'playing':
                    error = 'This question is no longer accepting answers.'
                else:
                    selected = answer.get('selected')
                    correct = question['correct']
                    good = selected is not None and selected == correct
                    player['combo'] = player.get('combo', 0) + 1 if good else 0
                    if good:
                        duration = max(1, room['config'].get('timePerQuestion', 15))
                        remaining = max(0, min(duration, room['deadline'] - now))
                        combo = player['combo']
                        player['score'] += 100 + int(remaining / duration * 50) + (combo * 10 if combo > 1 else 0)
                    player['highest_combo'] = max(player.get('highest_combo', 0), player['combo'])
                    player.setdefault('answers', []).append(dict(questionIndex=index, questionId=question['id'], selected=selected, correct=correct, isCorrect=good))
                    tick(conn, room, now)
            elif action == 'ready':
                question = room['questions'][room['current_question']] if room['questions'] else None
                if not player or player.get('forfeited'):
                    error = 'This player is not active in the round.'
                elif room['status'] != 'reveal' or data.get('currentQuestion') != room['current_question'] or not question or data.get('questionId') != question.get('id'):
                    error = 'Wait for the current answer review before continuing.'
                else:
                    player['reviewedQuestion'] = room['current_question']
            elif action == 'forfeit' and player and room['status'] != 'finished':
                player['forfeited'] = True
                player['finished'] = True
                active = [p for p in room['players'] if not p.get('forfeited')]
                if player['uid'] == room['host_uid'] and active:
                    replacement = active[0]
                    room['host_uid'] = replacement['uid']
                    room['host_name'] = replacement['name']
                    room['host_photo'] = replacement.get('photo', '')
                tick(conn, room, now)
            # Reveal requests cannot bypass the shared answer deadline.
            if before != json.dumps(room, sort_keys=True):
                room['revision'] += 1
                conn.execute('UPDATE rooms_v2 SET players=?, questions=?, status=?, current_question=?, deadline=?, revision=?, host_uid=?, host_name=?, host_photo=? WHERE code=?',
                    (json.dumps(room['players']), json.dumps(room['questions']), room['status'], room['current_question'], room['deadline'], room['revision'], room['host_uid'], room['host_name'], room['host_photo'], code))
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

    app.add_url_rule('/api/rooms/<code>/ready', 'review_ready', lambda code: handle(code, 'ready'), methods=['POST'])
