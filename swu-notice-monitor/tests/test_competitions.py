import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch, Mock

from backend.store import Store
from backend.competition_store import CompetitionStore
from backend.competition_collector import (classify, parse_listing, collect_source, start_collection,
    check_url, public_date, article_publication, scheduler_loop, KINDS)
from backend.server import MonitorServer

ROOT = Path(__file__).resolve().parents[1]


class CompetitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.campus = Store(Path(self.temp.name)/'test.db', ROOT/'data/sites.json')
        self.store = CompetitionStore(self.campus)
        self.source = self.store.sources('cumcm')[0]
        self.item = {'title':'全国大学生数学建模竞赛报名通知','kind':'报名','published_at':date.today().isoformat(),
                     'url':'https://www.mcm.edu.cn/notice/123','attachments':[]}

    def tearDown(self):
        self.store.cancel.set()
        if self.store.thread: self.store.thread.join(5)
        self.campus.close(); self.temp.cleanup()

    def test_catalog_exact_scores_and_named_tracks(self):
        rows = {x['id']:x for x in self.store.list_catalog()['items']}
        expected=[(['innovation'],[None,30,25,20,4]),(['challenge'],[30,25,20,15,4]),
            ('nuedc ccpc icpc cumcm robomaster robocon robotac'.split(),[25,25,20,12,4]),
            (['mcm-icm'],[25,20,10,4,0]),
            ('smartcar ciscn iot caairobot robotcontest software-cup h3c system-capability embedded datang robocom robocup computer-design c4-bigdata c4-ladder c4-app c4-network c4-ai c4-miniprogram'.split(),[18,18,12,9,4]),
            (['lanqiao'],[12,12,10,6,3]),
            ('vr math ai-future digital-skills ncccu digital-media information-literacy'.split(),[12,12,8,6,0]),
            ('cq-electronics cq-programming cq-database cq-security'.split(),[9,9,7,5,2]),
            (['bayu'],[5,5,4,3,0]),(['certification','swu-modeling'],[3,3,2,1,0]),(['hanhong-academic'],[None]*5)]
        self.assertEqual(set(rows),{id for ids,_ in expected for id in ids})
        for ids,scores in expected:
            for id in ids:self.assertEqual(scores,rows[id]['scores'],id)
        self.assertEqual([None,30,25,20,4],rows['innovation']['scores'])
        self.assertEqual([25,20,10,4,0],rows['mcm-icm']['scores'])
        self.assertEqual(['O','F','M','H','S'],rows['mcm-icm']['awards'])
        self.assertEqual(6,len([x for x in rows.values() if x.get('parent')=='中国高校计算机大赛']))
        for id in ('robomaster','robocon','robotac'): self.assertIn(id,rows)
        self.assertIn('仅国赛',rows['ncccu']['restriction'])
        self.assertIn('只加一次',rows['certification']['restriction'])
        self.assertEqual(89,len(self.campus.list_sites()))

    def test_first_backfill_does_not_notify_then_new_notice_once(self):
        self.store.save_subscriptions(['cumcm'])
        self.store.upsert_notice(self.source,self.item)
        self.assertEqual(0,self.store.list_messages()['total'])
        self.store.checkpoint(self.source['id'],{},'正常',complete=True)
        item = {**self.item,'url':self.item['url']+'new'}
        notice,_ = self.store.upsert_notice(self.source,item)
        self.store.upsert_notice(self.source,item)
        self.assertEqual(1,self.store.list_messages()['unread'])
        self.assertEqual(0,self.campus.list_messages('live')['unread'])
        self.store.update_notice(notice['id'],{'read':True,'favorite':True})
        self.assertEqual(0,self.store.list_messages()['unread'])
        self.assertEqual(1,self.store.list_notices(tab='favorite')['total'])

    def test_refollow_never_replays_historical_notices(self):
        self.store.checkpoint(self.source['id'],{},'正常',complete=True)
        self.store.save_subscriptions(['cumcm']); self.store.save_subscriptions([])
        self.store.upsert_notice(self.source,self.item)
        self.store.save_subscriptions(['cumcm'])
        self.assertEqual(0,self.store.list_messages()['total'])
        self.store.upsert_notice(self.source,{**self.item,'url':self.item['url']+'2'})
        self.assertEqual(1,self.store.list_messages()['total'])

    def test_metadata_repair_preserves_state_and_verified_date(self):
        n,_ = self.store.upsert_notice(self.source,self.item)
        self.store.update_notice(n['id'],{'read':True,'favorite':True})
        self.store.upsert_notice(self.source,{**self.item,'title':'数学建模竞赛变更通知','published_at':''})
        n = self.store.get_notice(n['id'])
        self.assertTrue(n['read'] and n['favorite'] and n['date_verified'])
        self.assertEqual(self.item['published_at'],n['published_at'])

    def test_window_pagination_filters_and_unknown_date(self):
        for i in range(13): self.store.upsert_notice(self.source,{**self.item,'url':self.item['url']+str(i)})
        self.store.upsert_notice(self.source,{**self.item,'url':self.item['url']+'unknown','published_at':''})
        self.store.upsert_notice(self.source,{**self.item,'url':self.item['url']+'old','published_at':(date.today()-timedelta(days=366)).isoformat()})
        self.assertEqual(14,self.store.list_notices(limit=10)['total'])
        self.assertEqual(4,len(self.store.list_notices(limit=10,offset=10)['items']))
        self.assertEqual(14,self.store.list_notices(kind='报名',q='数学建模')['total'])
        self.assertEqual(0,self.store.list_notices(tab='following')['total'])
        self.store.save_subscriptions(['cumcm'])
        self.assertEqual(14,self.store.list_notices(tab='following')['total'])
        for limit,offset in [(0,0),(101,0),(10,-1)]:
            with self.assertRaises(ValueError): self.store.list_notices(limit=limit,offset=offset)

    def test_settings_subscriptions_persist_and_are_isolated(self):
        campus_settings = self.campus.get_settings()
        self.store.save_subscriptions(['ccpc','cumcm','cumcm'])
        self.store.save_settings({'interval_minutes':120,'scheduler_enabled':False})
        other = CompetitionStore(self.campus)
        self.assertEqual(['ccpc','cumcm'],other.subscriptions()['competitions'])
        self.assertEqual(120,other.settings()['interval_minutes'])
        self.assertEqual(campus_settings,self.campus.get_settings())
        with self.assertRaises(ValueError): self.store.save_subscriptions(['nonexistent'])
        self.assertEqual(['ccpc','cumcm'],self.store.subscriptions()['competitions'])

    def test_html_listing_non_campus_urls_and_pdf(self):
        today = date.today().isoformat()
        content = f'<ul><li><a href="/press/update?id=2">全国大学生数学建模竞赛报名通知</a><time>{today}</time></li><li><a href="/files/rules.pdf">全国大学生数学建模竞赛规则发布</a><span>{today}</span></li><li><a href="/news/1">全国大学生数学建模竞赛圆满落幕</a>{today}</li></ul><a href="?page=2">下一页</a>'
        items,links = parse_listing(content,'https://www.mcm.edu.cn/',{})
        self.assertEqual(2,len(items)); self.assertEqual(today,items[0]['published_at'])
        self.assertTrue(items[1]['url'].endswith('.pdf')); self.assertEqual(1,len(links))

    def test_json_rss_english_and_jsonld(self):
        today = date.today().isoformat()
        json_data = json.dumps({'data':{'records':[{'title':'MCM ICM registration announcement','url':'/register.php','datePublished':today},{'title':'MCM ICM results announced','url':'/results.php','publishTime':today}]}})
        rows,_ = parse_listing(json_data,'https://comap.org/',{'keywords':['MCM','ICM']})
        self.assertEqual(['报名','成绩'],[x['kind'] for x in rows])
        self.assertEqual(today,rows[0]['published_at'])
        rows,_ = parse_listing(f'<script type="application/ld+json">{json_data}</script>','https://comap.org/',{})
        self.assertEqual(2,len(rows))
        rss = '<rss><channel><item><title>MCM registration announcement</title><link>https://comap.org/register</link><pubDate>Mon, 01 Dec 2025 10:00:00 GMT</pubDate></item></channel></rss>'
        rows,_ = parse_listing(rss,'https://comap.org/',{})
        self.assertEqual('2025-12-01',rows[0]['published_at'])
        self.assertEqual('2026-05-08',article_publication('<div>Written on <time datetime="2026-05-08T13:39:02-04:00">May 8, 2026</time>. Posted in Math Contests.</div><h1>2026 MCM/ICM results</h1>'))
        self.assertEqual('',article_publication('<article>比赛时间 <time datetime="2026-05-08">May 8, 2026</time></article>'))

    def test_missing_year_and_future_dates_never_invented(self):
        self.assertEqual('',public_date('09-22'))
        self.assertEqual('',public_date('2099-09-22'))
        self.assertEqual('',public_date('2026-02-30'))
        rows,_ = parse_listing('<li><a href="/n/1">数学建模竞赛报名通知</a><span>09-22</span></li>','https://www.mcm.edu.cn/',{})
        self.assertEqual('',rows[0]['published_at'])

    def test_official_json_field_mapping_and_pagination(self):
        content=json.dumps({'result':{'pageIndex':1,'totalPages':2,'records':[
            {'InfoTitle':'全国大学生计算机系统能力大赛章程','LinkUrl':'https://mp.weixin.qq.com/s/official','InfoDate':'2026-04-21T00:00:00'},
            {'InfoTitle':'新书出版推荐','LinkUrl':'https://mp.weixin.qq.com/s/book','InfoDate':'2026-04-21T00:00:00'}]}})
        config={'json_fields':{'title':['InfoTitle'],'url':['LinkUrl'],'date':['InfoDate']},'json_pagination':'PageStart','keywords':['系统能力大赛']}
        rows,links=parse_listing(content,'https://www.csc-he.cn/GetInformationList?PageStart=1&PageSize=100',config)
        self.assertEqual(1,len(rows));self.assertEqual('2026-04-21',rows[0]['published_at'])
        self.assertIn('PageStart=2',links[0])

    def test_checkpoint_resume_and_no_duplicate_insert(self):
        entry = self.source['config']['url']; second=entry+'?page=2'; today=date.today().isoformat()
        pages = {entry:f'<li><a href="/files/1.pdf">数学建模竞赛报名通知</a><time>{today}</time></li><a href="?page=2">下一页</a>',
                 second:f'<li><a href="/files/2.pdf">数学建模竞赛获奖名单公示</a><time>{today}</time></li>'}
        fetch=lambda url:(pages[url],url)
        first=collect_source(self.store,self.source,fetch,budget=1)
        self.assertEqual('待继续',first['status'])
        self.assertFalse(self.store.sources('cumcm')[0]['baseline'])
        second_result=collect_source(self.store,self.store.sources('cumcm')[0],fetch,budget=1)
        self.assertEqual('正常',second_result['status'])
        self.assertEqual(2,self.store.list_notices()['total'])
        self.assertTrue(self.store.sources('cumcm')[0]['baseline'])
        self.assertEqual(0,self.store.list_messages()['total'])

    def test_dated_html_notice_keeps_official_detail_attachments(self):
        entry=self.source['config']['url'];article=entry+'notice/123'
        pages={entry:f'<li><a href="{article}">数学建模竞赛报名通知</a><time>{date.today().isoformat()}</time></li>',
            article:'<article><a href="/files/entry.pdf">参赛通知附件</a></article>'}
        result=collect_source(self.store,self.source,lambda url:(pages[url],url))
        self.assertEqual('正常',result['status'])
        self.assertEqual(entry+'files/entry.pdf',self.store.list_notices()['items'][0]['attachments'][0]['url'])

    def test_errors_and_parser_limitations_are_not_empty_success(self):
        result=collect_source(self.store,self.source,lambda url:('<div>JavaScript required</div>',url))
        self.assertEqual('解析受限',result['status'])
        self.assertFalse(self.store.sources('cumcm')[0]['baseline'])
        def failing(url): raise TimeoutError('fixture timeout')
        result=collect_source(self.store,self.store.sources('cumcm')[0],failing)
        self.assertEqual('失败',result['status'])
        self.assertIn('timeout',self.store.sources('cumcm')[0]['error'])
        self.assertTrue(self.store.sources('cumcm')[0]['checkpoint']['pending'])

    def test_old_detail_date_never_sends_a_new_announcement(self):
        self.store.save_subscriptions(['cumcm'])
        self.store.checkpoint(self.source['id'],{},'正常',complete=True)
        source=self.store.sources('cumcm')[0];entry=source['config']['url'];article=entry+'notice/old'
        old=(date.today()-timedelta(days=366)).isoformat()
        pages={entry:f'<a href="{article}">数学建模竞赛报名通知</a>',article:f'<meta name="publishdate" content="{old}"><h1>数学建模竞赛报名通知</h1>'}
        collect_source(self.store,source,lambda url:(pages[url],url))
        self.assertEqual(0,self.store.list_notices()['total']);self.assertEqual(0,self.store.list_messages()['total'])
        n,_=self.store.upsert_notice(source,{**self.item,'published_at':''})
        self.store.upsert_notice(source,{**self.item,'published_at':old})
        self.assertEqual(old,self.store.get_notice(n['id'])['published_at'])
        self.assertEqual(0,self.store.list_notices()['total'])

    def test_stopped_and_restart_state(self):
        self.assertTrue(self.store.claim('cumcm')); self.assertFalse(self.store.claim('cumcm'))
        self.store.stop(resume=True)
        resumed=CompetitionStore(self.campus)
        self.assertTrue(resumed.resume_requested); self.assertEqual('cumcm',resumed.resume_id)
        resumed.claim('ccpc'); resumed.stop()
        stopped=CompetitionStore(self.campus)
        self.assertFalse(stopped.resume_requested)

    def test_scheduler_preserves_interval_after_restart(self):
        self.store.progress({},finished=True)
        stop=Mock();stop.wait.side_effect=[False,True]
        with patch('backend.competition_collector.start_collection') as start:
            scheduler_loop(self.store,stop)
            start.assert_not_called()

    def test_registered_host_only_and_private_dns(self):
        with self.assertRaises(ValueError): check_url('https://evil.test/a',self.source['config'],{},False)
        with self.assertRaises(ValueError): check_url('http://www.mcm.edu.cn/a',self.source['config'],{},False)
        with patch('backend.competition_collector.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError): check_url(self.item['url'],self.source['config'],{})

    def test_message_pagination_and_all_read(self):
        self.store.save_subscriptions(['cumcm']);self.store.checkpoint(self.source['id'],{},'正常',complete=True)
        for i in range(13): self.store.upsert_notice(self.source,{**self.item,'url':self.item['url']+str(i)})
        self.assertEqual(3,len(self.store.list_messages(10,10)['items']))
        self.store.read_messages(); self.assertEqual(0,self.store.list_messages()['unread'])


class CompetitionApiTests(unittest.TestCase):
    def test_namespace_and_origin_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            campus=Store(Path(temp)/'api.db',ROOT/'data/sites.json')
            server=MonitorServer(('127.0.0.1',0),campus)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            base=f'http://127.0.0.1:{server.server_address[1]}/api/'
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def request(path,method='GET',body=None,origin='http://127.0.0.1:5173'):
                req=urllib.request.Request(base+path,method=method,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':origin})
                with opener.open(req) as r:return json.load(r)
            try:
                self.assertGreater(request('competition/catalog')['total'],40)
                request('competition/subscriptions','PUT',{'competitions':['cumcm']})
                self.assertEqual(['cumcm'],request('competition/subscriptions')['competitions'])
                self.assertNotIn('cumcm',request('subscriptions')['sources'])
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('competition/subscriptions','PUT',{'competitions':[]},origin='https://evil.test')
                self.assertEqual(403,error.exception.code)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('competition/notices?limit=0')
                self.assertEqual(400,error.exception.code)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('competition/notices/999999')
                self.assertEqual(404,error.exception.code)
            finally:
                server.shutdown(); server.server_close(); thread.join(); campus.close()
