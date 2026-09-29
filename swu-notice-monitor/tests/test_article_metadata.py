import unittest
from backend import collector as c
BASE='https://xsc.swu.edu.cn/'
class ArticleMetadataTests(unittest.TestCase):
 def test_publication_not_event(self):
  html='<title>学术活动通知-西南大学</title><h2>学术活动通知</h2><span>发布时间：2026-09-19</span><div class="v_news_content">活动时间2026年9月25日</div>'
  self.assertEqual('2026-09-19',c.extract_article_metadata(html)['published_at'])
 def test_header_unlabelled_date_and_body_date(self):
  html='<h2>因公临时出国（境）团组信息公示</h2><div class="wzxq_title2"><span>2026-09-16 13:33</span>作者：某某</div><div class="v_news_content">出国时间2026-11-01</div>'
  r=c.extract_article_metadata(html);self.assertEqual('2026-09-16',r['published_at']);self.assertEqual('因公临时出国（境）团组信息公示',r['title'])
 def test_body_only_date_is_not_publication(self):
  self.assertIsNone(c.extract_article_metadata('<h2>活动通知</h2><div class="v_news_content">时间：2026-09-25</div>')['published_at'])
 def test_meta_published_wins_over_modified(self):
  r=c.extract_article_metadata('<meta property="article:modified_time" content="2026-09-22"><meta name="ArticleTitle" content="通知全文标题"><meta name="PubDate" content="2026-09-10 11:22">');self.assertEqual('2026-09-10',r['published_at'])
 def test_split_dates_div_cards_and_no_summary_dates(self):
  html='<div class="item"><a href="info/1/2.htm"><div class="date"><strong>13</strong><span>2026-09</span></div><p>完整通知标题</p></a><p class="summary">截止时间2026-12-12</p></div>'
  self.assertEqual([('完整通知标题','2026-09-13',BASE+'info/1/2.htm')],c.extract_notices(html,BASE))
 def test_missing_date_article_still_discovered(self):
  items=c.discover_articles('<a href="info/1/3.htm">开学</a><a href="info/1/4.htm" title="新生须知"><img src="a.png"></a>',BASE)
  self.assertEqual(2,len(items))
 def test_title_date_does_not_become_publish_date(self):
  self.assertEqual([],c.extract_notices('<li><a href="info/1/3.htm">2026年12月12日活动安排通知</a></li>',BASE))

class VerifiedPersistenceTests(unittest.TestCase):
 def test_list_recrawl_cannot_overwrite_verified_publication(self):
  import tempfile
  from pathlib import Path
  from backend.store import Store
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'test.db',Path(__file__).resolve().parents[1]/'data/sites.json')
   try:
    n,_=s.upsert_live_notice(13,'正确标题','2026-09-13','校园服务','','https://xsc.swu.edu.cn/info/1/2.htm',True,'原文发布时间')
    s.upsert_live_notice(13,'混入正文的标题','2026-12-12','校园服务','','https://xsc.swu.edu.cn/info/1/2.htm')
    r=s.get_notice(n['id']);self.assertEqual('2026-09-13',r['published_at']);self.assertEqual('正确标题',r['title'])
   finally:s.close()

class SplitCardRegression(unittest.TestCase):
 def test_numeric_heading_is_day_not_article_title(self):
  html='<li><a href="info/1/2.htm"><div class="jxzx_l"><h2>16</h2><p>2026-09</p></div><div class="jxzx_r"><h2>因公临时出国团组公示</h2><p>出访时间2026.11.1-2026.11.5</p></div></a></li>'
  self.assertEqual('因公临时出国团组公示',c.discover_articles(html,BASE)[0]['title'])
  self.assertEqual('2026-09-16',c.extract_notices(html,BASE)[0][1])

class ArticleWrapperTests(unittest.TestCase):
 def test_generic_wrapper_contains_header_and_body(self):
  html='<div class="article-content indent"><div class="column-name">学校成功举办2026年新入职教师教学能力提升培训</div><div style="text-align:center">发布时间：2026-09-22 17:06&nbsp;作者：本站编辑 来源：本站原创 浏览次数：<script>show(4582)</script></div><div class="v_news_content"><p>活动安排2026-10-01</p></div></div>'
  r=c.extract_article_metadata(html)
  self.assertEqual('学校成功举办2026年新入职教师教学能力提升培训',r['title']);self.assertEqual('2026-09-22',r['published_at']);self.assertEqual('2026-09-22 17:06',r['published_time'])
 def test_summary_before_header_does_not_end_metadata_search(self):
  html='<aside class="summary">其他栏目</aside><div class="article-content"><h2>真正的文章标题</h2><span>发布时间：2026-09-22</span><div class="v_news_content">发布时间：2026-10-01</div></div>'
  self.assertEqual('2026-09-22',c.extract_article_metadata(html)['published_at'])
 def test_body_publication_label_is_not_header(self):
  html='<div class="article-content"><div class="column-name">通知标题</div><div class="v_news_content"><p>转发文件发布时间：2026-09-01</p></div></div>'
  self.assertIsNone(c.extract_article_metadata(html)['published_at'])
