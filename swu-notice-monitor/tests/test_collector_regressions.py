import http.client
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import collector as c
from backend.store import Store

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://smxy.swu.edu.cn/'
URL = BASE + 'info/1/2.htm'
DETAIL = '<h2>课程补退选通知</h2><time datetime="2026-09-22T10:30:00"></time><div class="news-content">请同学们登录教务系统办理课程补退选。</div>'


class ExtractionRegressions(unittest.TestCase):
    def test_news_body_publication_label_is_excluded(self):
        self.assertIsNone(c.extract_article_metadata('<h2>学术活动通知</h2><div class="news-content"><p>转发文件发布时间：2026-09-01</p></div>')['published_at'])

    def test_time_datetime_is_read(self):
        data = c.extract_article_metadata(DETAIL)
        self.assertEqual('2026-09-22 10:30', data['published_time'])

    def test_attachments_and_malformed_links_are_excluded(self):
        html = ''.join(f'<li><a href="{href}">附件通知标题</a><span>2026-09-22</span></li>' for href in ['a.pdf', 'a.DOCX?x=1', 'a.xlsx', '/info/1/2.htm?x=&lt;error message&gt;'])
        self.assertEqual([], c.extract_notices(html, BASE))
        self.assertEqual([], c.discover_articles(html, BASE))
        self.assertEqual([], c.discover_sections(html, BASE))

    def test_list_summary_date_does_not_become_publication(self):
        html = '<li><a href="info/1/2.htm">活动通知</a><div class="summary"><time datetime="2026-09-20">2026-09-20</time></div></li>'
        self.assertEqual([], c.extract_notices(html, BASE))

    def test_old_http_section_is_upgraded(self):
        self.assertEqual([BASE + 'news.htm'], [n['url'] for n in c.discover_sections('<a href="http://smxy.swu.edu.cn/news.htm">学院新闻</a>', BASE)])


class StoreFixture:

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'db'
        self.store = Store(self.path, ROOT / 'data/sites.json')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()


class StoreRegressions(StoreFixture, unittest.TestCase):
    def test_missing_detail_date_preserves_list_date(self):
        n, _ = self.store.upsert_live_notice(35, '通知标题', '2026-09-22', '校园服务', '已有摘要', URL)
        self.store.upsert_live_notice(35, '通知标题', '', '教学教务', '', URL, date_source='原文未识别到发布时间')
        n = self.store.get_notice(n['id'])
        self.assertEqual('2026-09-22', n['published_at'])
        self.assertEqual('已有摘要', n['summary'])
        self.assertEqual('教学教务', n['category'])
        self.assertFalse(n['date_verified'])

    def test_schemes_share_article_identity(self):
        n, _ = self.store.upsert_live_notice(35, '通知标题', '2026-09-22', '校园服务', '', URL.replace('https:', 'http:'))
        self.store.update_notice(n['id'], read=True, favorite=True)
        result, created = self.store.upsert_live_notice(35, '通知标题', '2026-09-22', '校园服务', '', URL)
        self.assertFalse(created)
        self.assertEqual(n['id'], result['id'])
        self.assertTrue(result['read'] and result['favorite'])

    def test_existing_duplicates_merge_state_relations_and_messages(self):
        n, _ = self.store.upsert_live_notice(35, '课程通知', '2026-09-22', '教学教务', '', URL, True, '原文发布时间')
        self.store.db.execute('INSERT INTO notices(source_id,title,published_at,category,summary,url,is_demo,created_at,read,favorite) VALUES(?,?,?,?,?,?,0,?,1,1)', (35, '旧标题', '', '校园服务', '旧摘要', URL.replace('https:', 'http:'), '2026-09-22'))
        other = self.store.db.execute('SELECT last_insert_rowid()').fetchone()[0]
        self.store.add_notice_section(other, BASE + 'news.htm', '教学动态')
        self.store.db.execute("INSERT INTO messages(title,source_name,created_at,notice_id,is_demo) VALUES('旧标题','学院','2026-09-22',?,0)", (other,))
        self.store.db.commit()
        self.store.close()
        self.store = Store(self.path, ROOT / 'data/sites.json')
        items = self.store.list_notices(mode='live')['items']
        self.assertEqual(1, len(items))
        self.assertTrue(items[0]['read'] and items[0]['favorite'])
        self.assertEqual('2026-09-22', items[0]['published_at'])
        self.assertEqual('教学动态', items[0]['sections'])
        self.assertEqual(1, len(self.store.list_messages(mode='live')['items']))

    def test_legacy_attachment_is_hidden_without_losing_user_state(self):
        self.store.db.execute('INSERT INTO notices(source_id,title,published_at,category,summary,url,is_demo,created_at,read,favorite) VALUES(?,?,?,?,?,?,0,?,1,1)', (35, '附件记录', '2026-09-22', '校园服务', '', BASE + 'notice.pdf', '2026-09-22'))
        notice_id = self.store.db.execute('SELECT last_insert_rowid()').fetchone()[0]
        self.store.db.commit()
        self.store.close()
        self.store = Store(self.path, ROOT / 'data/sites.json')
        self.assertEqual(0, self.store.list_notices(mode='live')['total'])
        self.assertTrue(self.store.get_notice(notice_id)['favorite'])
        self.assertEqual([], self.store.unverified_articles(35, include_verified=True))
        with self.assertRaises(ValueError):
            self.store.upsert_live_notice(35, '附件', '2026-09-22', '校园服务', '', BASE + 'another.xlsx')


class CrawlRegressions(StoreFixture, unittest.TestCase):
    def crawl(self, pages, limit=80):
        self.calls = []
        def fetch(opener, url, *args):
            self.calls.append(url)
            value = pages[url]
            if isinstance(value, Exception):
                raise value
            return value, url
        with patch.object(c, 'validate_fetch_url'), patch.object(c, 'read_robots') as robots, patch.object(c, 'fetch_html', side_effect=fetch), patch.object(c.time, 'sleep'):
            robots.return_value.can_fetch.return_value = True
            robots.return_value.crawl_delay.return_value = None
            return c.collect_site(self.store, self.store.get_site(35), max_pages=limit)

    def test_invalid_url_does_not_abort_source(self):
        html = '<a href="bad.htm">坏页面</a><a href="good.htm">正常页面</a>'
        self.crawl({BASE: html, BASE + 'bad.htm': http.client.InvalidURL('bad URL'), BASE + 'good.htm': ''})
        self.assertIn(BASE + 'good.htm', self.calls)
        self.assertEqual(1, sum(p['status'] == '失败' for p in self.store.get_coverage(35)['pages']))

    def test_failed_page_is_retried_while_history_pending(self):
        self.store.save_coverage(35, {'version': 2, 'metadata_version': 5, 'pages': [{'url': BASE + 'bad.htm', 'label': '通知', 'status': '失败'}], 'pending': [{'url': BASE + 'archive.htm', 'label': '历史'}]})
        self.crawl({BASE: '', BASE + 'archive.htm': '', BASE + 'bad.htm': ''}, 3)
        self.assertIn(BASE + 'bad.htm', self.calls)

    def test_finished_round_refreshes_lists_without_refetching_archive(self):
        pages = {BASE: '<a href="news.htm">教学动态</a>', BASE + 'news.htm': '<a href="/info/1/2.htm">课程通知</a><a href="news/1.htm">下一页</a>', BASE + 'news/1.htm': '', URL: DETAIL}
        self.crawl(pages)
        self.crawl(pages)
        self.assertIn(BASE + 'news.htm', self.calls)
        self.assertNotIn(URL, self.calls)
        self.assertNotIn(BASE + 'news/1.htm', self.calls)

    def test_new_undated_article_precedes_history(self):
        self.store.save_coverage(35, {'version': 2, 'metadata_version': 5, 'pages': [], 'pending': [{'url': BASE + 'archive.htm', 'label': '历史'}]})
        self.crawl({BASE: '<a href="/info/1/2.htm">课程补退选通知</a>', URL: DETAIL, BASE + 'archive.htm': ''}, 2)
        self.assertIn(URL, self.calls)
        self.assertEqual(1, self.store.list_notices(mode='live')['total'])

    def test_category_and_summary_reach_persistence_and_subscription(self):
        self.store.save_subscriptions([], [], ['教学教务'], True)
        self.crawl({BASE: '<a href="/info/1/2.htm">课程补退选通知</a>', URL: DETAIL})
        n = self.store.list_notices(mode='live')['items'][0]
        self.assertEqual('教学教务', n['category'])
        self.assertIn('登录教务系统', n['summary'])
        self.assertEqual(1, len(self.store.list_messages(mode='live')['items']))

    def test_checkpoints_are_batched(self):
        pages = {BASE: ''.join(f'<a href="section{i}.htm">公开栏目{i}</a>' for i in range(79))}
        pages.update({BASE + f'section{i}.htm': '' for i in range(79)})
        with patch.object(self.store, 'save_coverage', wraps=self.store.save_coverage) as save:
            self.crawl(pages)
            self.assertLessEqual(save.call_count, 10)
        self.assertEqual(80, len(self.store.get_coverage(35)['pages']))

    def test_source_health_separates_backfill_verification_and_errors(self):
        report = {'pages': [{'url': BASE, 'label': '首页', 'status': '正常'}, {'url': URL, 'label': '通知', 'status': '待核验'}], 'pending': [{'url': BASE + 'archive.htm', 'label': '历史'}], 'round_pages': 0}
        def collect(store, site):
            store.save_coverage(35, report)
            return 0
        with patch.object(c, 'collect_site', side_effect=collect):
            c.run_collection(self.store, 35)
        self.assertEqual('正常', self.store.get_site(35)['status'])
        coverage = next(s for s in self.store.list_sites() if s['id'] == 35)['coverage']
        self.assertEqual(0, coverage['failed'])
        self.assertEqual(1, coverage['unverified'])


    def test_unverified_detail_is_retried_on_next_round(self):
        missing = '<h2>课程补退选通知</h2><div class="news-content">请办理课程补退选。</div>'
        pages = {BASE: '<a href="/info/1/2.htm">课程补退选通知</a>', URL: missing}
        self.crawl(pages)
        self.crawl({**pages, URL: DETAIL})
        n = self.store.list_notices(mode='live')['items'][0]
        self.assertTrue(n['date_verified'])
        self.assertEqual('2026-09-22 10:30', n['published_at'])

    def test_permanent_failures_do_not_starve_continuation(self):
        failures = [{'url': BASE + f'bad{i}.htm', 'label': '失败页', 'status': '失败'} for i in range(80)]
        self.store.save_coverage(35, {'version': 2, 'metadata_version': 5, 'pages': failures,
                                    'pending': [{'url': BASE + 'archive.htm', 'label': '历史'}]})
        site = {**self.store.get_site(35), '_continuation': True, '_refresh': False}
        pages = {p['url']: TimeoutError('timeout') for p in failures}
        pages[BASE + 'archive.htm'] = ''
        with patch.object(self.store, 'get_site', return_value=site):
            self.crawl(pages, 4)
        self.assertIn(BASE + 'archive.htm', self.calls)
        self.assertFalse(self.store.get_coverage(35)['pending'])

    def test_shared_undated_article_keeps_all_sections_across_restart(self):
        pages = {BASE: '<a href="one.htm">教学通知</a><a href="two.htm">学院新闻</a>',
                 BASE + 'one.htm': '<a href="two.htm">学院新闻</a><a href="/info/1/2.htm">课程补退选通知</a>',
                 BASE + 'two.htm': '<a href="/info/1/2.htm">课程补退选通知</a>', URL: DETAIL}
        # The two sections are inspected while the article is still queued.
        self.store.save_coverage(35, {'version': 2, 'metadata_version': 5, 'pages': [], 'pending': [
            {'url': BASE + 'one.htm', 'label': '教学通知', 'kind': 'section'},
            {'url': BASE + 'two.htm', 'label': '学院新闻', 'kind': 'section'},
            {'url': URL, 'title': '课程补退选通知', 'label': '教学通知', 'section_url': BASE + 'one.htm', 'kind': 'article'}]})
        site = {**self.store.get_site(35), '_continuation': True, '_refresh': False}
        with patch.object(self.store, 'get_site', return_value=site):
            self.crawl(pages, 2)
        self.store.close()
        self.store = Store(self.path, ROOT / 'data/sites.json')
        with patch.object(self.store, 'get_site', return_value=site):
            self.crawl(pages, 2)
        notice = self.store.list_notices(mode='live')['items'][0]
        self.assertEqual({'教学通知', '学院新闻'}, set(notice['sections'].split(',')))

    def test_incremental_scan_follows_new_articles_onto_known_next_page(self):
        url2, url3 = BASE + 'info/1/3.htm', BASE + 'info/1/4.htm'
        pages = {BASE: '<a href="news.htm">教学动态</a>',
                 BASE + 'news.htm': '<a href="/info/1/2.htm">课程补退选通知</a><a href="news/1.htm">下一页</a>',
                 BASE + 'news/1.htm': '<a href="/info/1/2.htm">课程补退选通知</a>', URL: DETAIL}
        self.crawl(pages)
        self.crawl({**pages, BASE + 'news.htm': '<a href="/info/1/4.htm">新课程通知</a><a href="news/1.htm">下一页</a>',
                    BASE + 'news/1.htm': '<a href="/info/1/3.htm">第二条新课程通知</a><a href="/info/1/2.htm">课程补退选通知</a>',
                    url2: DETAIL, url3: DETAIL})
        self.assertEqual(3, self.store.list_notices(mode='live')['total'])
        self.assertIn(BASE + 'news/1.htm', self.calls)
        self.assertNotIn(URL, self.calls)

    def test_incremental_flag_survives_preexisting_pending_pagination(self):
        url2, url3 = BASE + 'info/1/3.htm', BASE + 'info/1/4.htm'
        page1, page2 = BASE + 'news/1.htm', BASE + 'news/2.htm'
        self.store.save_coverage(35, {'version': 2, 'metadata_version': 5,
                                    'pages': [{'url': page2, 'label': '通知', 'kind': 'pagination', 'status': '正常'}],
                                    'pending': [{'url': page1, 'label': '通知', 'kind': 'pagination'}]})
        pages = {BASE: '<a href="/info/1/2.htm">第一条课程通知</a><a href="news/1.htm">下一页</a>',
                 page1: '<a href="/info/1/3.htm">第二条课程通知</a><a href="2.htm">下一页</a>',
                 page2: '<a href="/info/1/4.htm">第三条课程通知</a>', URL: DETAIL, url2: DETAIL, url3: DETAIL}
        site = {**self.store.get_site(35), '_refresh': True, '_continuation': False}
        with patch.object(self.store, 'get_site', return_value=site):
            self.crawl(pages, 2)
        site.update(_refresh=False, _continuation=True)
        with patch.object(self.store, 'get_site', return_value=site):
            self.crawl(pages, 4)
        self.assertEqual(3, self.store.list_notices(mode='live')['total'])
        self.assertIn(page2, self.calls)
