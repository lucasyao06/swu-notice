import tempfile,unittest
from pathlib import Path
from backend.collector import extract_notices,LinkParser
from backend.store import Store
ROOT=Path(__file__).resolve().parents[1]
TITLE='学院高远东教授团队在关税冲击与供应链韧性研究领域发表重要成果'
class TitleTests(unittest.TestCase):
 def test_anchor_title_attribute_excludes_summary_but_keeps_date(self):
  html=f'<a href="info/1.htm" title="{TITLE}"><div>{TITLE}</div><div class="summary">近期，团队发表了研究成果...</div><span>2026-09-22</span></a>'
  self.assertEqual([(TITLE,'2026-09-22','https://smxy.swu.edu.cn/info/1.htm')],extract_notices(html,'https://smxy.swu.edu.cn/'))
 def test_nested_heading_excludes_sibling_summary(self):
  html=f'<li><a href="info/2.htm"><div class="title"><span>{TITLE}</span></div><div class="intro">近期，一大段正文。</div></a><time>2026-09-22</time></li>'
  self.assertEqual([(TITLE,'2026-09-22','https://smxy.swu.edu.cn/info/2.htm')],extract_notices(html,'https://smxy.swu.edu.cn/'))
 def test_plain_title_with_english_and_punctuation_is_not_truncated(self):
  title='学术报告：From uncertainty to resilience — 供应链研究'
  html=f'<li><a href="info/3.htm">{title}</a><span>2026-09-22</span></li>'
  self.assertEqual(title,extract_notices(html,'https://smxy.swu.edu.cn/')[0][0])
 def test_correcting_existing_title_preserves_user_state_and_message(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(Path(d)/'test.sqlite3',ROOT/'data/sites.json')
   store.save_subscriptions([35],[],[],True)
   old,created=store.upsert_live_notice(35,TITLE+' 近期，正文。','2026-09-22','校园服务','','https://smxy.swu.edu.cn/info/1.htm')
   store.update_notice(old['id'],read=True,favorite=True)
   new,created=store.upsert_live_notice(35,TITLE,'2026-09-22','校园服务','','https://smxy.swu.edu.cn/info/1.htm')
   self.assertFalse(created);self.assertEqual(old['id'],new['id']);self.assertEqual(TITLE,new['title'])
   self.assertTrue(new['read']);self.assertTrue(new['favorite'])
   messages=store.list_messages('live')['items'];self.assertEqual(1,len(messages));self.assertEqual(TITLE,messages[0]['title'])
   store.close()
