import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.store import Store
from backend import collector
ROOT=Path(__file__).resolve().parents[1]
BASE='https://smxy.swu.edu.cn/'

def article(i):
    return f'<li><a href="/info/1001/{i}.htm">测试学院公开内容标题{i}</a><span>2026-09-22</span></li>'

class SectionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'db.sqlite',ROOT/'data/sites.json')
        self.site=self.store.get_site(35)
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def crawl(self,pages,limit=80,robots=None):
        def fetch(opener,url,*args):
            if '/info/' in url and url not in pages:
                return '<h2>原文核验测试标题</h2><span>发布时间：2026-09-22</span><div class="v_news_content">正文</div>',url
            value=pages[url]
            if isinstance(value,Exception):raise value
            return value,url
        with patch.object(collector,'validate_fetch_url'),patch.object(collector,'read_robots') as r,patch.object(collector,'fetch_html',side_effect=fetch),patch.object(collector.time,'sleep'):
            r.return_value.can_fetch.side_effect=robots or (lambda agent,url:True)
            return collector.collect_site(self.store,self.site,max_pages=limit)
    def test_sections_children_pagination_and_more_than_50_items(self):
        pages={BASE:'<a href="research.htm">科学研究</a><a href="party.htm">党建工作</a>',BASE+'research.htm':'<a href="results.htm">科研成果</a>'+article(1),BASE+'party.htm':article(2),BASE+'results.htm':''.join(article(i) for i in range(3,65))+'<a href="results/1.htm">下一页</a>',BASE+'results/1.htm':article(65)+'<a href="/results.htm">首页</a>'}
        self.assertEqual(65,self.crawl(pages))
        report=self.store.get_coverage(35)
        self.assertFalse(report['pending']);self.assertEqual(5,len([p for p in report['pages'] if p.get('kind')!='article']))
        self.assertTrue(any(p['label']=='科研成果' for p in report['pages']))
    def test_budget_is_resumable_and_deduplicates(self):
        pages={BASE:'<a href="news.htm">学院新闻</a>',BASE+'news.htm':article(1)+'<a href="news/1.htm">下一页</a>',BASE+'news/1.htm':article(1)+article(2)}
        self.crawl(pages,2);self.assertTrue(self.store.get_coverage(35)['pending'])
        self.crawl(pages,2);self.assertEqual(2,self.store.list_notices(mode='live')['total'])
        
        for _ in range(5):
            if not self.store.get_coverage(35)['pending']:break
            self.crawl(pages,2)
        self.assertFalse(self.store.get_coverage(35)['pending'])
    def test_custom_list_adds_to_home_and_partial_errors_visible(self):
        self.site['list_url']=BASE+'extra.htm'
        pages={BASE:'<a href="party.htm">党建工作</a><a href="broken.htm">规章制度</a><a href="private.htm">内部信息</a>',BASE+'extra.htm':article(1),BASE+'party.htm':article(2),BASE+'broken.htm':TimeoutError('timeout')}
        self.assertEqual(2,self.crawl(pages,robots=lambda agent,url:not url.endswith('private.htm')))
        report=self.store.get_coverage(35)
        self.assertEqual(2,len([p for p in report['pages'] if p['status']!='正常']))
    def test_discovery_rejects_external_assets_detail_and_action_urls(self):
        html='<a href="news.htm#top">学院新闻</a><a href="news.htm">新闻</a><a href="https://other.example/a.htm">学术研究</a><a href="/info/1/2.htm">研究成果新闻</a><a href="a.pdf">资料下载</a><a href="/logout">退出登录</a><a href="javascript:void(0)">党建</a>'
        self.assertEqual([BASE+'news.htm'],[x['url'] for x in collector.discover_sections(html,BASE)])

class ContinuationTests(unittest.TestCase):
 def test_collection_automatically_continues_pending_batches(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(Path(tmp)/'db.sqlite',ROOT/'data/sites.json')
   calls=[]
   def collect(s,site):
    calls.append(site['id']);s.save_coverage(site['id'],{'pages':[],'pending':[{'url':BASE,'label':'测试'}] if len(calls)<3 else [],'round_pages':1})
    return 1
   try:
    with patch.object(collector,'collect_site',side_effect=collect):collector.run_collection(store,35)
    self.assertEqual(3,len(calls));self.assertEqual(3,store.get_site(35)['new_count']);self.assertFalse(store.get_crawl_state()['running'])
   finally:store.close()
 def test_stop_preserves_pending_without_resubmitting(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(Path(tmp)/'db.sqlite',ROOT/'data/sites.json')
   def collect(s,site):
    s.save_coverage(site['id'],{'pages':[],'pending':[{'url':BASE,'label':'待采'}],'round_pages':1});s.crawl_cancel.set();return 0
   try:
    with patch.object(collector,'collect_site',side_effect=collect) as call:collector.run_collection(store,35)
    self.assertEqual(1,call.call_count);self.assertTrue(store.get_coverage(35)['pending']);self.assertTrue(store.get_crawl_state()['stopped'])
   finally:store.close()

class ParserUpgradeTests(unittest.TestCase):
 def test_parser_upgrade_requeues_previously_visited_unverified_article(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db',ROOT/'data/sites.json');url=BASE+'info/1/2.htm'
   n,_=s.upsert_live_notice(35,'明确的文章标题','','校园服务','',url)
   s.save_coverage(35,{'version':2,'pages':[{'url':url,'label':'教学动态','kind':'article','status':'待核验','count':1}], 'pending':[]})
   html='<div class="article-content"><div class="column-name">明确的文章标题</div><div>发布时间：2026-09-22 17:06</div><div class="v_news_content">正文</div></div>'
   try:
    with patch.object(collector,'validate_fetch_url'),patch.object(collector,'read_robots') as robots,patch.object(collector,'fetch_html',return_value=(html,url)),patch.object(collector.time,'sleep'):
     robots.return_value.can_fetch.return_value=True;robots.return_value.crawl_delay.return_value=None
     collector.collect_site(s,s.get_site(35),max_pages=1)
    result=s.get_notice(n['id']);self.assertTrue(result['date_verified']);self.assertEqual('2026-09-22 17:06',result['published_at'])
   finally:s.close()

class LegacyLinkTests(unittest.TestCase):
 def test_legacy_http_article_is_fetched_over_registered_https(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db',ROOT/'data/sites.json');old='http://smxy.swu.edu.cn/info/1/2.htm';secure='https://smxy.swu.edu.cn/info/1/2.htm'
   n,_=s.upsert_live_notice(35,'旧链接通知标题','','校园服务','',old);s.update_notice(n['id'],read=True,favorite=True)
   html='<h2>旧链接通知标题</h2><span>发布时间：2026-09-22 17:06</span>'
   try:
    with patch.object(collector,'validate_fetch_url'),patch.object(collector,'read_robots') as robots,patch.object(collector,'fetch_html',return_value=(html,secure)) as fetch,patch.object(collector.time,'sleep'):
     robots.return_value.can_fetch.return_value=True;robots.return_value.crawl_delay.return_value=None
     collector.collect_site(s,s.get_site(35),max_pages=1)
    self.assertEqual(secure,fetch.call_args.args[1]);result=s.get_notice(n['id']);self.assertTrue(result['date_verified']);self.assertTrue(result['favorite']);self.assertTrue(result['read'])
   finally:s.close()
