import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from flask import Flask
from room_sync import install_room_routes

class RoomSyncTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        self.app = Flask(__name__)
        self.finished = []
        def db():
            conn = sqlite3.connect(self.path, timeout=10)
            conn.row_factory = sqlite3.Row
            return conn
        self.db = db
        with db() as conn:
            conn.execute('CREATE TABLE rooms_v2 (code TEXT, host_uid TEXT, host_name TEXT, host_photo TEXT, config TEXT, questions TEXT, players TEXT, status TEXT, current_question INTEGER)')
            players = [dict(uid=uid, name=uid, score=0, combo=0, answers=[]) for uid in ['a', 'b']]
            conn.execute('INSERT INTO rooms_v2 VALUES (?,?,?,?,?,?,?,?,?)', ('ROOM', 'a', 'a', '', json.dumps({'timePerQuestion':15}), json.dumps([{'correct':'Yes'}, {'correct':'No'}]), json.dumps(players), 'waiting', 0))
        routes = [('get_room', '', ['GET']), ('join_room','/join',['POST']), ('start_room','/start',['POST']), ('next_question','/next',['POST']), ('reveal_room','/reveal',['POST']), ('end_room','/end',['POST']), ('update_questions','/questions',['POST']), ('forfeit_room','/forfeit',['POST']), ('update_score','/score',['POST'])]
        for endpoint, suffix, methods in routes:
            self.app.add_url_rule('/api/rooms/<code>'+suffix, endpoint, lambda code: '', methods=methods)
        install_room_routes(self.app, db, lambda: 'ROOM', lambda *args: self.finished.append(args[1]))
        self.clock = patch('room_sync.time.time', return_value=100)
        self.now = self.clock.start()
        self.client = self.app.test_client()
    def tearDown(self):
        self.clock.stop()
        os.unlink(self.path)
    def post(self, action, data=None):
        return self.client.post('/api/rooms/ROOM/'+action, json=data or {}).get_json()['room']
    def get(self):
        return self.client.get('/api/rooms/ROOM').get_json()['room']
    def answer(self, uid, index=0, selected='Yes'):
        return self.post('score', {'uid':uid,'answers':[{'questionIndex':index,'selected':selected}], 'score':999999})
    def test_round_progresses_without_host_and_finishes_once(self):
        self.post('start')
        self.answer('a'); room=self.answer('b')
        self.assertEqual(room['status'], 'reveal')
        self.now.return_value=106
        self.assertEqual(self.get()['currentQuestion'],1)
        self.now.return_value=122
        self.assertEqual(self.get()['status'],'reveal')
        self.now.return_value=128
        self.assertEqual(self.get()['status'],'finished')
        self.post('end');self.post('start');self.post('next',{'index':0})
        self.assertEqual(self.get()['status'],'finished')
        self.assertEqual(self.finished,['ROOM'])
    def test_stale_transitions_and_answers_cannot_rewind_or_skip(self):
        self.post('start')
        self.post('next',{'index':8});self.post('reveal');self.post('end')
        self.assertEqual(self.get()['status'],'playing')
        self.answer('a');self.answer('b')
        self.now.return_value=106
        self.get()
        room=self.answer('a',0)
        self.assertEqual(room['currentQuestion'],1)
        self.assertEqual(len(room['players'][0]['answers']),1)
    def test_duplicate_answer_does_not_rescore(self):
        self.post('start')
        room=self.answer('a');score=room['players'][0]['score']
        room=self.answer('a',selected='No')
        self.assertEqual(room['players'][0]['score'],score)
        self.assertEqual(room['players'][0]['answers'][0]['selected'],'Yes')
    def test_concurrent_answers_preserve_both_players(self):
        self.post('start')
        def send(uid):
            with self.app.test_client() as client:
                return client.post('/api/rooms/ROOM/score',json={'uid':uid,'answers':[{'questionIndex':0,'selected':'Yes'}]}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(send,['a','b'])),[200,200])
        room=self.get()
        self.assertTrue(all(len(p['answers'])==1 for p in room['players']))
        self.assertEqual(room['status'],'reveal')
    def test_forfeit_does_not_end_other_players_round(self):
        self.post('start');self.post('forfeit',{'uid':'a'})
        self.assertEqual(self.get()['status'],'playing')
        self.assertEqual(self.answer('b')['status'],'reveal')
    def test_no_new_players_or_question_changes_mid_round(self):
        self.post('start')
        for action,data in [('join',{'uid':'c','name':'c'}),('questions',{'questions':[{'correct':'different'}]})]:
            self.assertEqual(self.client.post('/api/rooms/ROOM/'+action,json=data).status_code,409)
        self.assertEqual(self.post('join',{'uid':'a'})['status'],'playing')

if __name__ == '__main__': unittest.main()
