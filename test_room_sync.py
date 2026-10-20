import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch
from flask import Flask
from room_sync import install_room_routes, normalize_question_set

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
        with closing(db()) as conn, conn:
            conn.execute('CREATE TABLE rooms_v2 (code TEXT, host_uid TEXT, host_name TEXT, host_photo TEXT, config TEXT, questions TEXT, players TEXT, status TEXT, current_question INTEGER)')
            players = [dict(uid=uid, name=uid, score=0, combo=0, answers=[]) for uid in ['a', 'b']]
            conn.execute('INSERT INTO rooms_v2 VALUES (?,?,?,?,?,?,?,?,?)', ('ROOM', 'a', 'a', '', json.dumps({'timePerQuestion':15}), json.dumps(normalize_question_set([{'question':'Who built the ark?', 'options':['Yes','No','Maybe','Never'], 'correct':'Yes', 'explanation':'Noah built the ark (Genesis 6:14).'}, {'question':'Who denied Jesus three times?', 'options':['Yes','No','Maybe','Never'], 'correct':'No', 'explanation':'Peter denied Jesus (Luke 22:61).'}])), json.dumps(players), 'waiting', 0))
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
        return self.client.post('/api/rooms/ROOM/'+action, json=({'uid':'a'} if data is None else data)).get_json()['room']
    def get(self):
        return self.client.get('/api/rooms/ROOM').get_json()['room']
    def answer(self, uid, index=0, selected='Yes'):
        question_id = self.get()['questions'][index]['id']
        return self.post('score', {'uid':uid,'answers':[{'questionIndex':index,'questionId':question_id,'selected':selected}], 'score':999999})
    def ready(self, uid='b'):
        room=self.get()
        return self.post('ready',{'uid':uid,'currentQuestion':room['currentQuestion'],'questionId':room['currentQuestionId']})
    def test_host_manually_advances_and_finishes_once(self):
        self.post('start')
        self.answer('a'); self.answer('b')
        self.now.return_value = 500
        self.assertEqual(self.get()['status'], 'reveal')
        self.assertEqual(self.get()['currentQuestion'], 0)
        self.ready()
        room = self.post('next', {'uid':'a', 'currentQuestion':0})
        self.assertEqual(room['currentQuestion'], 1)
        self.assertEqual(room['deadline'], 515)
        self.now.return_value = 516
        self.assertEqual(self.get()['status'], 'reveal')
        self.ready()
        self.post('next', {'uid':'a', 'currentQuestion':1})
        self.assertEqual(self.get()['status'], 'finished')
        self.client.post('/api/rooms/ROOM/next', json={'uid':'a','currentQuestion':1})
        self.assertEqual(self.finished, ['ROOM'])

    def test_guest_early_and_stale_advances_are_rejected(self):
        self.post('start')
        response = self.client.post('/api/rooms/ROOM/next', json={'uid':'a','currentQuestion':0})
        self.assertEqual(response.status_code, 409)
        self.answer('a'); self.answer('b')
        for uid in ['b', None]:
            response = self.client.post('/api/rooms/ROOM/next', json={'uid':uid,'currentQuestion':0})
            self.assertEqual(response.status_code, 409)
        self.ready()
        self.post('next', {'uid':'a','currentQuestion':0})
        self.now.return_value = 116
        self.get()
        response = self.client.post('/api/rooms/ROOM/next', json={'uid':'a','currentQuestion':0})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.get()['currentQuestion'], 1)
        self.assertEqual(self.get()['status'], 'reveal')

    def test_duplicate_answer_does_not_rescore(self):
        self.post('start')
        room=self.answer('a');score=room['players'][0]['score']
        response=self.client.post('/api/rooms/ROOM/score',json={'uid':'a','answers':[{'questionIndex':0,'questionId':self.get()['questions'][0]['id'],'selected':'No'}]})
        self.assertEqual(response.status_code,409)
        room=self.get()
        self.assertEqual(room['players'][0]['score'],score)
        self.assertEqual(room['players'][0]['answers'][0]['selected'],'Yes')
    def test_concurrent_answers_preserve_both_players(self):
        self.post('start')
        question_id=self.get()['questions'][0]['id']
        def send(uid):
            with self.app.test_client() as client:
                return client.post('/api/rooms/ROOM/score',json={'uid':uid,'answers':[{'questionIndex':0,'questionId':question_id,'selected':'Yes'}]}).status_code
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

    def test_two_clients_receive_identical_order_ids_and_insights_through_full_round(self):
        second = self.app.test_client()
        self.post('start')
        for index, correct in [(0, 'Yes'), (1, 'No')]:
            host = self.get()
            guest = second.get('/api/rooms/ROOM').get_json()['room']
            self.assertEqual(host['questions'], guest['questions'])
            self.assertEqual(host['currentQuestionId'], guest['currentQuestionId'])
            self.assertEqual(host['currentQuestion'], index)
            self.answer('a', index, correct)
            self.answer('b', index, correct)
            self.now.return_value += 100
            self.assertEqual(self.get()['status'], 'reveal')
            self.assertEqual(self.get()['currentQuestion'], index)
            self.ready()
            self.post('next', {'uid':'a','currentQuestion':index})
        self.assertEqual(self.get()['status'], 'finished')
        self.assertEqual(self.finished, ['ROOM'])
        for player in self.get()['players']:
            self.assertEqual([a['questionIndex'] for a in player['answers']], [0,1])

    def test_wrong_question_id_and_invalid_option_cannot_be_scored(self):
        self.post('start')
        room=self.get()
        for question_id, selected in [(room['questions'][1]['id'],'Yes'), (room['questions'][0]['id'],'Not an option')]:
            response=self.client.post('/api/rooms/ROOM/score',json={'uid':'a','answers':[{'questionIndex':0,'questionId':question_id,'selected':selected}]})
            self.assertEqual(response.status_code,409)
        self.assertEqual(self.get()['players'][0]['score'],0)
        self.assertFalse(self.get()['players'][0]['answers'])

    def test_only_host_can_start_or_prepare_questions_and_set_is_immutable(self):
        questions=self.get()['questions']
        self.assertEqual(self.client.post('/api/rooms/ROOM/start',json={'uid':'b'}).status_code,409)
        self.assertEqual(self.client.post('/api/rooms/ROOM/questions',json={'uid':'b','questions':questions}).status_code,409)
        self.post('questions',{'uid':'a','questions':questions})
        questions[0]['options'].reverse()
        self.assertEqual(self.client.post('/api/rooms/ROOM/questions',json={'uid':'a','questions':questions}).status_code,409)

    def test_host_exit_transfers_control_and_lost_answer_reply_is_idempotent(self):
        self.post('start')
        first=self.answer('b')
        self.assertEqual(self.answer('b')['players'][1]['score'],first['players'][1]['score'])
        room=self.post('forfeit',{'uid':'a'})
        self.assertEqual(room['hostId'],'b')
        self.assertEqual(room['status'],'reveal')
        self.assertEqual(self.post('next',{'uid':'b','currentQuestion':0})['currentQuestion'],1)

    def test_question_set_rejects_duplicates_and_mismatched_insights(self):
        question=self.get()['questions'][0]
        for questions in [[question,question], [{**question,'correct':'Missing'}], [{**question,'explanation':''}], [{**question,'options':['Yes',' yes ','Maybe','Never']}]]:
            with self.assertRaises(ValueError): normalize_question_set(questions)

    def test_host_cannot_skip_a_guest_review_and_stale_ready_cannot_unlock_next_question(self):
        self.post('start')
        self.answer('a'); self.answer('b')
        self.assertEqual(self.client.post('/api/rooms/ROOM/next',json={'uid':'a','currentQuestion':0}).status_code,409)
        old=self.get()
        self.ready()
        self.post('next',{'uid':'a','currentQuestion':0})
        self.answer('a',1,'No'); self.answer('b',1,'No')
        stale=self.client.post('/api/rooms/ROOM/ready',json={'uid':'b','currentQuestion':0,'questionId':old['currentQuestionId']})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(self.client.post('/api/rooms/ROOM/next',json={'uid':'a','currentQuestion':1}).status_code,409)
        self.ready()
        self.assertEqual(self.post('next',{'uid':'a','currentQuestion':1})['status'],'finished')

if __name__ == '__main__': unittest.main()
