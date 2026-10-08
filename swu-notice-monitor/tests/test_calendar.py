import tempfile,unittest
from pathlib import Path
from backend.store import Store
class CalendarTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'calendar.sqlite3';self.sites=Path(__file__).resolve().parents[1]/'data/sites.json';self.store=Store(self.path,self.sites)
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def body(self,**changes):return dict(title='提交奖学金材料',date='2026-09-30',time='14:00',end_time='15:00',notes='带学生证',priority='high',reminder_minutes=30,timezone_offset=480,source_url='https://www.swu.edu.cn/',**changes)
 def test_create_edit_complete_delete_persist(self):
  event=self.store.create_event(self.body());self.assertEqual(event['remind_at'],'2026-09-30T05:30:00+00:00');self.assertFalse(event['completed'])
  self.store.close();self.store=Store(self.path,self.sites);self.assertEqual(len(self.store.list_events()),1)
  changed=self.store.update_event(event['id'],{'completed':True});self.assertTrue(changed['completed'])
  self.store.update_event(event['id'],{'completed':False});self.assertFalse(self.store.list_events()[0]['completed'])
  self.assertTrue(self.store.delete_event(event['id']));self.assertEqual(self.store.list_events(),[])
 def test_validation(self):
  for patch in [{'title':' '},{'date':'2026-02-30'},{'time':'25:00'},{'end_time':'13:00'},{'priority':'bad'},{'category':'invalid'},{'location':'x'*201},{'reminder_minutes':-1},{'source_url':'javascript:alert(1)'},{'completed':'yes'},{'surprise':1}]:
   body=self.body();body.update(patch)
   with self.assertRaises(ValueError):self.store.create_event(body)
 def test_reminder_ack_and_reschedule(self):
  event=self.store.create_event(self.body());self.store.update_event(event['id'],{'reminded':True});self.assertTrue(self.store.list_events()[0]['reminded'])
  self.store.update_event(event['id'],{'time':'14:30'});self.assertFalse(self.store.list_events()[0]['reminded'])
 def test_missing_record(self):self.assertIsNone(self.store.update_event(999,{'completed':True}));self.assertFalse(self.store.delete_event(999))

 def test_categories_location_and_old_payload(self):
  event=self.store.create_event(self.body(category='study',location='北区教学楼'))
  self.assertEqual(event['category'],'study');self.assertEqual(event['location'],'北区教学楼')
  self.store.update_event(event['id'],{'category':'work','location':'会议室'})
  self.store.close();self.store=Store(self.path,self.sites)
  self.assertEqual(self.store.list_events()[0]['category'],'work')
  plain=self.store.create_event(self.body());self.assertEqual(plain['category'],'other')

 def test_inbox_and_list_lifecycle(self):
  inbox=self.store.create_event({'title':'稍后安排','date':''})
  self.assertEqual(inbox['list_id'],None);self.assertEqual(inbox['subtasks'],[])
  group=self.store.create_calendar_list({'name':' 学习 ','color':'teal'})
  self.assertEqual(group['name'],'学习')
  event=self.store.create_event({**self.body(),'list_id':group['id']})
  self.assertEqual(self.store.update_calendar_list(group['id'],{'name':'课程'})['name'],'课程')
  self.store.close();self.store=Store(self.path,self.sites)
  self.assertEqual(self.store.list_calendar_lists()[0]['name'],'课程')
  self.assertTrue(self.store.delete_calendar_list(group['id']))
  moved=next(e for e in self.store.list_events() if e['id']==event['id'])
  self.assertIsNone(moved['list_id']);self.assertEqual(moved['date'],event['date'])
  with self.assertRaises(ValueError):self.store.update_event(event['id'],{'list_id':group['id']})
  self.assertIsNone(self.store.update_calendar_list(999,{'name':'Missing'}))
  self.assertFalse(self.store.delete_calendar_list(999))

 def test_new_field_validation(self):
  for patch in [{'list_id':True},{'list_id':999},{'subtasks':None},{'subtasks':[{'id':'a','title':'','completed':False}]},{'subtasks':[{'id':'a','title':'ok','completed':1}]},{'subtasks':[{'id':'a','title':'ok','completed':False}]*2},{'repeat':'yearly'},{'repeat_until':'2026-02-30'},{'repeat_until':'2026-01-01'}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):self.store.create_event({**self.body(),**patch})
  for patch in [{'time':'12:00'},{'end_time':'13:00'},{'reminder_minutes':0},{'repeat':'daily'},{'repeat_until':'2027-01-01'}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):self.store.create_event({'title':'Inbox','date':'',**patch})
  for body in [{'name':' '},{'name':'a'*61},{'name':'ok','color':'red'},{'name':'ok','unknown':1}]:
   with self.assertRaises(ValueError):self.store.create_calendar_list(body)

 def test_recurring_completion_is_persistent_and_idempotent(self):
  event=self.store.create_event({**self.body(),'repeat':'daily','subtasks':[{'id':'a','title':'准备','completed':True}],'reminded':True})
  result=self.store.update_event(event['id'],{'completed':True});child=result['next_event']
  self.assertEqual(child['date'],'2026-10-01');self.assertFalse(child['completed']);self.assertFalse(child['reminded']);self.assertFalse(child['subtasks'][0]['completed'])
  self.assertEqual(child['remind_at'],'2026-10-01T05:30:00+00:00')
  self.store.close();self.store=Store(self.path,self.sites)
  self.store.update_event(event['id'],{'completed':False})
  self.assertEqual(self.store.update_event(event['id'],{'completed':True})['next_event']['id'],child['id'])
  self.assertEqual(len(self.store.list_events()),2)
  self.assertEqual(self.store.update_event(event['id'],{'completed':True})['next_event']['id'],child['id'])
  self.store.delete_event(child['id']);self.store.update_event(event['id'],{'completed':False});self.store.update_event(event['id'],{'completed':True})
  self.assertEqual(len(self.store.list_events()),1)

 def test_repeat_calendar_rules_and_cutoff(self):
  for repeat,day,want in [('weekly','2026-12-28','2027-01-04'),('monthly','2027-01-31','2027-02-28'),('monthly','2028-01-31','2028-02-29')]:
   event=self.store.create_event({**self.body(),'date':day,'repeat':repeat})
   self.assertEqual(self.store.update_event(event['id'],{'completed':True})['next_event']['date'],want)
  event=self.store.create_event({**self.body(),'repeat':'daily','repeat_until':'2026-09-30'})
  self.assertNotIn('next_event',self.store.update_event(event['id'],{'completed':True}))

 def test_old_payload_receives_new_defaults(self):
  import json
  event=self.store.create_event(self.body())
  payload={k:v for k,v in event.items() if k not in ('id','created_at','updated_at','list_id','subtasks','repeat','repeat_until')}
  self.store.db.execute('UPDATE calendar_events SET payload=? WHERE id=?',(json.dumps(payload),event['id']));self.store.db.commit()
  loaded=self.store.list_events()[0]
  self.assertEqual(loaded['repeat'],'none');self.assertEqual(loaded['subtasks'],[])
  self.assertTrue(self.store.update_event(event['id'],{'completed':True})['completed'])

 def test_list_api_routes(self):
  from backend.server import APIHandler
  from types import SimpleNamespace
  handler=object.__new__(APIHandler)
  handler.server=SimpleNamespace(store=self.store);handler.headers={}
  responses=[];handler._send=lambda status,payload:responses.append((status,payload))
  handler.path='/api/calendar/lists';handler._body=lambda:{'name':'课程','color':'purple'}
  handler._mutate('POST');self.assertEqual(responses[-1][0],201)
  list_id=responses[-1][1]['id'];handler._get();self.assertEqual(responses[-1][1]['items'][0]['id'],list_id)
  handler.path=f'/api/calendar/lists/{list_id}';handler._body=lambda:{'color':'gray'}
  handler._mutate('PATCH');self.assertEqual(responses[-1][1]['color'],'gray')
  handler._body=lambda:{};handler._mutate('DELETE');self.assertEqual(responses[-1],(200,{'ok':True}))
  handler._mutate('DELETE');self.assertEqual(responses[-1][0],404)

 def test_recurrence_rolls_back_if_completion_write_fails(self):
  import sqlite3
  event=self.store.create_event({**self.body(),'repeat':'daily'})
  self.store.db.execute("CREATE TRIGGER reject_completion BEFORE UPDATE ON calendar_events BEGIN SELECT RAISE(ABORT, 'test failure'); END;")
  self.store.db.commit()
  with self.assertRaises(sqlite3.IntegrityError):self.store.update_event(event['id'],{'completed':True})
  self.assertEqual(len(self.store.list_events()),1);self.assertFalse(self.store.list_events()[0]['completed'])

 def test_concurrent_completion_creates_one_successor(self):
  from concurrent.futures import ThreadPoolExecutor
  event=self.store.create_event({**self.body(),'repeat':'daily'})
  with ThreadPoolExecutor(max_workers=4) as pool:
   results=list(pool.map(lambda _:self.store.update_event(event['id'],{'completed':True}),range(8)))
  self.assertEqual(len(self.store.list_events()),2)
  self.assertEqual(len({r['next_event']['id'] for r in results}),1)

 def test_subtasks_limit_and_repeat_date_boundaries(self):
  tasks=[{'id':str(i),'title':'步骤','completed':False} for i in range(100)]
  event=self.store.create_event({**self.body(),'subtasks':tasks})
  self.assertEqual(len(event['subtasks']),100)
  with self.assertRaises(ValueError):self.store.update_event(event['id'],{'subtasks':tasks+[{'id':'100','title':'超额','completed':False}]})
  for invalid in [None,[],123,'20260101']:
   with self.assertRaises(ValueError):self.store.create_event({**self.body(),'date':invalid})
  event=self.store.create_event({'title':'边界','date':'9999-12-31','repeat':'daily'})
  self.assertNotIn('next_event',self.store.update_event(event['id'],{'completed':True}))
  event=self.store.create_event({**self.body(),'repeat':'daily','repeat_until':'2026-10-01'})
  child=self.store.update_event(event['id'],{'completed':True})['next_event']
  self.assertEqual(child['date'],'2026-10-01')
  self.assertNotIn('next_event',self.store.update_event(child['id'],{'completed':True}))
