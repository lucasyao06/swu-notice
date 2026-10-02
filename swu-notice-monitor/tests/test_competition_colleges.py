import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock

from backend.store import Store
from backend.competition_store import CompetitionStore
from backend.competition_collector import start_collection, parse_listing, scheduler_loop
from backend.server import MonitorServer

ROOT=Path(__file__).resolve().parents[1]


class CollegeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.campus=Store(Path(self.temp.name)/'college.db',ROOT/'data/sites.json')
        self.store=CompetitionStore(self.campus)
        self.source=self.store.sources('challenge')[0]
        self.item={'title':'挑战杯报名通知','kind':'报名','published_at':date.today().isoformat(),
                   'url':'https://2025.tiaozhanbei.net/fixture/shared','attachments':[]}

    def tearDown(self):
        self.store.cancel.set()
        if self.store.thread:self.store.thread.join(5)
        self.campus.close();self.temp.cleanup()

    def test_exact_coverage_shared_identity_and_categories(self):
        cis=self.store.list_catalog()['items'];law=self.store.list_catalog(college_id='law')['items']
        self.assertEqual(44,len(cis));self.assertEqual(17,len(law))
        self.assertEqual(59,self.store.list_catalog(scope='all')['total'])
        self.assertEqual({'innovation','challenge'},{x['id'] for x in cis}&{x['id'] for x in law})
        self.assertEqual(12,self.store.list_catalog(college_id='law',category='专业技能')['total'])
        self.assertEqual(3,self.store.list_catalog(college_id='law',category='学术科技')['total'])
        self.assertEqual(2,self.store.list_catalog(college_id='law',category='创新创业')['total'])
        self.assertEqual(15,len({x['id'] for x in law}-{x['id'] for x in cis}))
        self.assertEqual('innovation',self.store.list_catalog(college_id='law',q='互联网＋')['items'][0]['id'])
        self.assertEqual('innovation',self.store.list_catalog(college_id='law',q='中国国际“互联网＋”大学生创新创业大赛')['items'][0]['id'])
        for college in self.store.colleges()['items']:
            self.assertIn('适用学年尚未确认',college['policy']['label'])

    def test_law_professional_six_levels_and_fractional_scores(self):
        rule=self.store.reference('yingming-zhili-moot','law')['reference_rules'][0]
        self.assertEqual(['国际级','国家级','省市级','校际级','校级','院级'],[x['name'] for x in rule['levels']])
        self.assertEqual([[20,19,18,6],[18,15,12,10,5],[12,10,8,3],[8,6,4,2],[5,4,3,1.5],[2.5,2,1.5]],
                         [x['scores'] for x in rule['levels']])
        self.assertNotIn('特等',rule['levels'][0]['awards'])
        self.assertNotIn('优秀奖',rule['levels'][-1]['awards'])
        self.assertIn('单项奖',rule['levels'][0]['awards'][-1])

    def test_academic_four_levels_and_two_challenges(self):
        law={x['id']:x for x in self.store.list_catalog(college_id='law')['items']}
        cis={x['id']:x for x in self.store.list_catalog()['items']}
        self.assertEqual(30,cis['challenge']['scores'][0]);self.assertEqual(25,law['challenge']['scores'][0])
        self.assertEqual([[25,22,20,18,5],[15,12,10,8,3],[8,6,4,2],[4,3,2,1]],
                         [x['scores'] for x in law['challenge']['reference_rules'][0]['levels']])
        self.assertEqual([4,3,2,1],law['yingming-academic']['scores'])
        self.assertEqual('优秀奖',law['yingming-academic']['awards'][-1])
        self.assertIn('创业计划',law['challenge-business']['name'])
        self.assertNotEqual(law['challenge']['id'],law['challenge-business']['id'])
        for id in ('innovation','challenge-business'):
            rule=law[id]['reference_rules'][0]
            self.assertEqual(law['challenge']['scores'],law[id]['scores'])
            self.assertIn('25分',rule['conflicts'][0]);self.assertIn('20分',rule['conflicts'][0])
            self.assertIn('待学院确认',rule['conflicts'][0]);self.assertTrue(any('相应标准' in x for x in rule['notes']))

    def test_cross_college_never_inherits_another_colleges_points(self):
        rows={x['id']:x for x in self.store.list_catalog(college_id='law',scope='all')['items']}
        self.assertEqual([],rows['cumcm']['reference_rules']);self.assertEqual([],rows['cumcm']['scores'])
        self.assertEqual([],rows['cumcm']['awards'])
        self.assertEqual('当前学院截图未列名，分值认定待确认',rows['cumcm']['recognition_note'])
        self.assertNotIn('不认可',rows['cumcm']['recognition_note'])
        for context in ({'college_id':'bad'},{'scope':'bad'},{'college_id':'cis','category':'专业技能'}):
            with self.assertRaises(ValueError):self.store.list_catalog(**context)

    def test_shared_notices_are_saved_and_alerted_once_in_both_contexts(self):
        self.store.save_subscriptions(['challenge'])
        n,_=self.store.upsert_notice(self.source,self.item)
        self.assertEqual(0,self.store.list_messages()['total'])
        self.store.checkpoint(self.source['id'],{},'正常',complete=True)
        new={**self.item,'url':self.item['url']+'/new'}
        n,_=self.store.upsert_notice(self.source,new);self.store.upsert_notice(self.source,new)
        self.assertEqual(1,self.store.list_messages(college_id='law')['unread'])
        self.assertEqual(1,self.store.list_messages(college_id='cis')['unread'])
        self.assertEqual(2,self.store.list_notices(college_id='law')['total'])
        self.assertEqual(2,self.store.list_notices(college_id='cis')['total'])
        self.assertEqual(25,self.store.get_notice(n['id'],'law')['reference_rules'][0]['levels'][0]['scores'][0])
        self.assertEqual(30,self.store.get_notice(n['id'],'cis')['reference_rules'][0]['levels'][0]['scores'][0])

    def test_personal_records_stay_global_with_college_context(self):
        source=self.store.sources('cumcm')[0]
        self.store.save_subscriptions(['cumcm']);self.store.checkpoint(source['id'],{},'正常',complete=True)
        for i in range(13):
            n,_=self.store.upsert_notice(source,{**self.item,'url':f'https://www.mcm.edu.cn/fixture/{i}'})
            self.store.update_notice(n['id'],{'favorite':True})
        self.assertEqual(0,self.store.list_notices(college_id='law')['total'])
        self.assertEqual(13,self.store.list_notices(college_id='law',scope='all')['total'])
        for tab in ('following','favorite'):
            result=self.store.list_notices(college_id='law',tab=tab,offset=10)
            self.assertEqual(13,result['total']);self.assertEqual(3,len(result['items']))
            self.assertEqual([],result['items'][0]['reference_rules'])
        self.assertEqual(13,self.store.list_messages(college_id='law')['unread'])
        self.store.update_notice(n['id'],{'read':True},'law')
        self.assertTrue(self.store.get_notice(n['id'],'cis')['read'])
        self.store.save_subscriptions([]);self.store.upsert_notice(source,{**self.item,'url':'https://www.mcm.edu.cn/fixture/unfollowed'})
        self.store.save_subscriptions(['cumcm']);self.assertEqual(13,self.store.list_messages()['total'])

    def snapshot(self,exclude=()):
        names=[r[0] for r in self.campus.db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0] not in exclude]
        return {name:[tuple(r) for r in self.campus.db.execute(f'SELECT * FROM "{name}" ORDER BY rowid')] for name in names}

    def test_incremental_migration_preserves_every_original_table(self):
        self.store.save_subscriptions(['challenge']);self.store.checkpoint(self.source['id'],{'visited':['keep']},'正常',complete=True)
        n,_=self.store.upsert_notice(self.source,self.item);self.store.update_notice(n['id'],{'favorite':True,'read':True})
        # Recreate the exact pre-college schema/data; only the new association tables are absent.
        self.campus.db.execute('DROP TABLE competition_college_rules');self.campus.db.execute('DROP TABLE competition_colleges');self.campus.db.commit()
        before=self.snapshot()
        self.store=CompetitionStore(self.campus)
        after=self.snapshot(exclude=('competition_colleges','competition_college_rules'))
        self.assertEqual(before,after)
        self.assertEqual(61,self.campus.db.execute('SELECT COUNT(*) FROM competition_college_rules').fetchone()[0])

    def test_scoring_updates_do_not_reset_baseline_checkpoint_or_personal_state(self):
        self.store.save_subscriptions(['challenge']);self.store.checkpoint(self.source['id'],{'visited':['keep']},'正常',complete=True)
        n,_=self.store.upsert_notice(self.source,self.item);self.store.update_notice(n['id'],{'favorite':True,'read':True})
        before=self.snapshot(exclude=('competition_college_rules',))
        config=json.loads((ROOT/'data/college_competition_rules.json').read_text(encoding='utf-8'))
        next(x for x in config['rules'] if x['college_id']=='law' and x['competition_id']=='challenge')['levels'][0]['scores'][0]=24
        path=Path(self.temp.name)/'rules.json';path.write_text(json.dumps(config),encoding='utf-8')
        self.store=CompetitionStore(self.campus,rules_path=path)
        self.assertEqual(before,self.snapshot(exclude=('competition_college_rules',)))
        self.assertEqual(24,self.store.reference('challenge','law')['reference_rules'][0]['levels'][0]['scores'][0])

    def test_manual_college_collection_scope_and_persisted_resume(self):
        expected={x['competition_id'] for x in self.store.sources(college_id='law')}
        with patch('backend.competition_collector.collect_source',return_value={'processed':1,'inserted':0,'status':'正常'}) as collect:
            self.assertTrue(start_collection(self.store,college_id='law'));self.store.thread.join(5)
            self.assertEqual(expected,{call.args[1]['competition_id'] for call in collect.call_args_list})
        self.assertTrue(self.store.claim(None,'law'));self.store.stop(resume=True)
        self.store=CompetitionStore(self.campus)
        self.assertTrue(self.store.resume_requested);self.assertEqual('law',self.store.resume_college_id)
        with self.assertRaises(ValueError):start_collection(self.store,'cumcm','law')
        with self.assertRaises(ValueError):start_collection(self.store,college_id='invalid')

    def test_law_official_samples_reject_publicity_and_other_competitions(self):
        config=self.store.sources('hanhong-academic')[0]['config']
        html='''<li><a href="/info/1006/1.htm">关于举办第十届含弘杯学生课外学术科技作品竞赛的通知</a>2026-10-01</li>
          <li><a href="/info/1006/2.htm">关于举办含弘杯大学生创业计划竞赛的通知</a>2026-09-30</li>
          <li><a href="/info/1006/3.htm">喜报：含弘杯学术科技作品竞赛获奖</a>2026-09-30</li>'''
        rows,_=parse_listing(html,config['list_url'],config)
        self.assertEqual(1,len(rows));self.assertEqual('2026-10-01',rows[0]['published_at'])
        config=self.store.sources('challenge-business')[0]['config']
        html='''<a href="/article/1/">关于举办第十五届挑战杯中国大学生创业计划竞赛的通知</a>
          <a href="/article/2/">关于举办第二十届挑战杯全国大学生课外学术科技作品竞赛的通知</a>
          <a href="/article/3/">挑战杯中国大学生创业计划竞赛培训交流顺利举办</a>'''
        rows,_=parse_listing(html,config['list_url'],config)
        self.assertEqual(1,len(rows));self.assertTrue(rows[0]['url'].endswith('/article/1/'))

    def test_due_scheduler_always_collects_all_after_a_college_manual_run(self):
        self.store.progress({'college_id':'law'},finished=True)
        self.store.db.execute('UPDATE competition_crawl_state SET last_finished=?',
                             ((datetime.now().astimezone()-timedelta(hours=6)).isoformat(),))
        self.store.db.commit()
        stop=Mock();stop.wait.side_effect=[False,True]
        with patch('backend.competition_collector.start_collection',return_value=True) as start:
            scheduler_loop(self.store,stop)
            start.assert_called_once_with(self.store)


class CollegeApiTests(unittest.TestCase):
    def test_context_api_defaults_all_scope_and_invalid_parameters(self):
        with tempfile.TemporaryDirectory() as temp:
            campus=Store(Path(temp)/'api.db',ROOT/'data/sites.json');server=MonitorServer(('127.0.0.1',0),campus)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_address[1]}/api/competition/'
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def read(path):
                with opener.open(base+path) as response:return json.load(response)
            try:
                self.assertEqual(2,len(read('colleges')['items']))
                self.assertEqual(44,read('catalog')['total']);self.assertEqual(17,read('catalog?college=law')['total'])
                self.assertEqual(59,read('catalog?college=law&scope=all')['total'])
                self.assertEqual(25,read('catalog/challenge?college=law')['scores'][0])
                self.assertEqual([],read('catalog/cumcm?college=law')['reference_rules'])
                for path in ('catalog?college=bad','catalog?scope=bad','notices?college=bad','messages?college=bad','catalog?college=cis&category='+urllib.parse.quote('专业技能')):
                    with self.assertRaises(urllib.error.HTTPError) as error:read(path)
                    self.assertEqual(400,error.exception.code)
            finally:server.shutdown();server.server_close();thread.join();campus.close()
